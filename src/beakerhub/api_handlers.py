"""Custom api handlers for augment or extend Jupyterhub api."""
import asyncio
import json
import pathlib
import urllib.parse
import uuid
from typing import Any, cast

from beakerhub.types import HandlerTuple

from tornado import web
from jupyterhub.apihandlers.users import SelfAPIHandler, UserServerAPIHandler, SpawnProgressAPIHandler
from jupyterhub.apihandlers import APIHandler
from jupyterhub.scopes import needs_scope
from jupyterhub.user import User
from jupyterhub.utils import isoformat, url_escape_path, url_path_join
from sqlalchemy.orm import joinedload

from jupyterhub import orm as JupyterOrm

from beakerhub.orm import (
    Context,
    Integration,
    NodeImages,
    Workflow,
    WorkflowStage,
    beaker_context_roles,
    beaker_context_workflows,
)


class UserInfoHandler(SelfAPIHandler):
    def check_xsrf_cookie(self):
        # Don't check xsrf cookie on this call as this provides the xsrf token when a user doesn't have one.
        return

    def user_model(self, user: User):
        # Rewrite urls to be based on user.server_url like it should have been.
        result = super().user_model(user)
        if (results := result.get("servers", None)):
            for server_name, server in results.items():
                server_url = user.server_url(server_name=server_name)
                server["url"] = server_url
                server["full_url"] = server_url
        return result

    async def head(self):
        provided_user = self.get_query_argument("user", None)
        user: User = cast(User, self.current_user)

        if not provided_user or not user or provided_user != user.name:
            self.set_status(401, "Not authenticated")


    async def get(self):
        if (authorization_header := self.request.headers.get("Authorization", None)):
            key, token = authorization_header.split(maxsplit=1)
            if key.lower() != "bearer":
                self.set_status(403, "Invalid authorization header")
                return
            api_token: JupyterOrm.APIToken | None = JupyterOrm.APIToken.find(self.db, token, kind="user")
            if api_token:
                orm_user = api_token.user
                self._current_user = self._user_from_orm(orm_user)
            else:
                self.set_status(403, "Invalid authorization header")
                return
        if self.xsrf_token:
            self.add_header("X-SET-XSRFTOKEN", self.xsrf_token)
        try:
            return await super().get()
        except web.HTTPError as err:
            # Default behavior when raising the exception is to strip headers. By setting the status manually and returning, we
            # can ensure the header is sent even if a user is not logged in.
            if err.status_code == 403:
                self.set_status(403, err.reason)
                return
            else:
                raise


class BeakerhubUserServerAPIHandler(UserServerAPIHandler):

    async def _spawn_server(self, spawner, user, server_name, options):
        # Check if server is already running and responding. If so, don't spawn a new instance.
        # If poll_and_notify returns None, the server process is still running
        # If it returns anything else, the process the spawner owns is dead and should be restarted.
        if spawner.ready:
            # include notify, so that a server that died is noticed immediately
            # set _spawn_pending flag to prevent races while we wait
            spawner._spawn_pending = True
            try:
                state = await spawner.poll_and_notify()
            finally:
                spawner._spawn_pending = False
            if state is None:
                return

        await self.spawn_single_user(user, server_name, options=options)


    @needs_scope('servers')
    async def post(self, user_name, server_name=''):
        # No "default" servers. Make sure all servers have names.
        if not server_name:
            server_name = str(uuid.uuid4())

        user = self.find_user(user_name)
        if user is None:
            # this can be reached if a token has `servers`
            # permission on *all* users
            raise web.HTTPError(404)

        spawner = user.get_spawner(server_name, replace_failed=True)

        # Check if this server is already pending. If pending is None, we should spawn the server.
        pending = spawner.pending
        match pending:
            case "spawn":
                self.set_status(202)
            case str():
                self.set_status(400)
            case None:
                options = self.get_json_body()
                # Run setup outside of the current loop action so that it does not block returning the request quickly.
                # asyncio.get_running_loop().call_soon_threadsafe(self._spawn_server, spawner, user, server_name, options)
                task = asyncio.create_task(self._spawn_server(spawner, user, server_name, options))
                # Discard results
                task.add_done_callback(lambda i: None)
                if spawner.pending == "spawn":
                    self.set_status(201)
                else:
                    self.set_status(202)

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({
            "type": "single-user",
            "session": server_name,
            'progress_url': user.progress_url(spawner.name),
            'user_options': spawner.user_options,
            'name': spawner.name,
            'full_name': f"{spawner.user.name}/{spawner.name}",
            'last_activity': isoformat(spawner.last_activity),
            'started': isoformat(spawner.orm_spawner.started),
            'pending': pending,
            'ready': spawner.ready,
            'stopped': not spawner.active,
            'url': user.server_url(spawner.name),
        }))


class BeakerhubSpawnProgressAPIHandler(SpawnProgressAPIHandler):
    async def send_event(self, event):
        # Modify event
        if "url" in event:
            orig_url = event["url"]
            parts = urllib.parse.urlparse(orig_url)
            server_name = parts.path.strip('/').split('/')[-1]
            new_url = str(urllib.parse.urlunparse(parts._replace(netloc=f"{server_name}.{parts.netloc}", path="/")))
            event["session_id"] = server_name

            for key, value in event.items():
                if isinstance(value, str):
                    event[key] = value.replace(orig_url, new_url)

        await super().send_event(event)


# ============================================
# Context Role Visibility Helpers
# ============================================

def get_context_role_map(db, context_ids: list[int]) -> dict[int, list[str]]:
    """Bulk-fetch role assignments for a set of context IDs.

    Returns a mapping of context_id -> list of role names.
    Contexts with no entries are not included in the mapping (meaning visible to all).
    """
    if not context_ids:
        return {}

    rows = db.execute(
        beaker_context_roles.select().where(
            beaker_context_roles.c.context_id.in_(context_ids)
        )
    ).fetchall()

    role_map: dict[int, list[str]] = {}
    for row in rows:
        role_map.setdefault(row.context_id, []).append(row.role_name)

    return role_map


def filter_contexts_by_role(
    db, contexts: list[Context], user_roles: set[str]
) -> list[Context]:
    """Filter contexts based on user roles.

    Contexts with no role restrictions are always included.
    Contexts with role restrictions are included only if the user has at least
    one matching role.
    """
    if not contexts:
        return contexts

    role_map = get_context_role_map(db, [c.id for c in contexts])

    result = []
    for context in contexts:
        required_roles = role_map.get(context.id)
        if required_roles is None:
            # No restrictions — visible to all
            result.append(context)
        elif user_roles & set(required_roles):
            # User has at least one matching role
            result.append(context)

    return result


# ============================================
# Context API Serialization Helpers
# ============================================

def serialize_language(lang) -> dict[str, Any]:
    """Serialize a Language ORM object."""
    return {
        "slug": lang.slug,
        "subkernel": lang.subkernel,
        "display_name": lang.display_name,
    }


def serialize_integration(integration: Integration) -> dict[str, Any]:
    """Serialize an Integration ORM object."""
    return {
        "id": integration.id,
        "slug": integration.slug,
        "name": integration.name,
        "description": integration.description or "",
        "enabled": integration.enabled,
        "source_package": integration.source_package,
        "source_uuid": integration.source_uuid,
    }


def serialize_integration_summary(integration: Integration) -> dict[str, Any]:
    """Serialize an Integration for lightweight listings."""
    return {
        "slug": integration.slug,
        "name": integration.name,
        "description": integration.description or "",
    }


def serialize_workflow_stage(stage: WorkflowStage) -> dict[str, Any]:
    """Serialize a WorkflowStage ORM object."""
    return {
        "id": stage.id,
        "name": stage.name,
        "sort_order": stage.sort_order,
        "description": stage.description or [],
        "metadata": stage.metadata_ or {},
    }


def serialize_workflow(
    workflow: Workflow,
    is_context_default: bool = False,
    include_stages: bool = True,
) -> dict[str, Any]:
    """Serialize a Workflow ORM object."""
    result: dict[str, Any] = {
        "id": workflow.id,
        "title": workflow.title,
        "human_description": workflow.human_description or "",
        "agent_description": workflow.agent_description or "",
        "example_prompt": workflow.example_prompt or "",
        "category": {
            "slug": workflow.category.slug,
            "display_name": workflow.category.display_name,
            "description": workflow.category.description or "",
            "sort_order": workflow.category.sort_order,
        } if workflow.category else None,
        "hidden": workflow.hidden,
        "enabled": workflow.enabled,
        "is_context_default": is_context_default,
        "source_package": workflow.source_package,
        "source_path": workflow.source_path,
    }

    if include_stages:
        result["stages"] = [serialize_workflow_stage(s) for s in workflow.stages]
        result["metadata"] = workflow.metadata_ or {}
    else:
        result["stage_count"] = len(workflow.stages)

    return result


def serialize_api_key_requirement(api_key, required: bool = True) -> dict[str, Any]:
    """Serialize an API key requirement."""
    return {
        "env_var": api_key.env_var,
        "display_name": api_key.display_name,
        "required": required,
    }


def serialize_node_image(node: NodeImages) -> dict[str, Any]:
    """Serialize a NodeImages ORM object."""
    return {
        "id": node.id,
        "slug": node.slug,
        "default_registry": node.default_registry,
        "repository": node.repository,
        "default_tag": node.default_tag,
        "metadata": node.metadata_ or {},
        "enabled": node.enabled,
        "created_at": node.created_at.isoformat() if node.created_at else None,
        "updated_at": node.updated_at.isoformat() if node.updated_at else None,
    }


def serialize_context_summary(
    context: Context,
    visible_to_roles: list[str] | None = None,
) -> dict[str, Any]:
    """Serialize a Context for lightweight dashboard listing."""
    return {
        "slug": context.slug,
        "display_name": context.display_name,
        "description": context.description or "",
        "icon": context.icon,
        "theme": context.theme,
        "weight": context.weight,
        "enabled": context.enabled,
        "image_enabled": context.image.enabled if context.image else None,
        "integration_count": len(context.integrations),
        "workflow_count": len(context.workflows),
        "integration_names": [i.name for i in context.integrations[:5]],
        "workflow_titles": [w.title for w in context.workflows[:5]],
        "visible_to_roles": visible_to_roles or [],
    }


def serialize_context_detail(
    context: Context,
    db,
    visible_to_roles: list[str] | None = None,
) -> dict[str, Any]:
    """Serialize a Context with workflow summaries (no stages)."""
    # Get junction table data for is_context_default
    junction_data = {}
    junction_results = db.execute(
        beaker_context_workflows.select().where(
            beaker_context_workflows.c.context_id == context.id
        )
    ).fetchall()
    for row in junction_results:
        junction_data[row.workflow_id] = {
            "is_context_default": row.is_context_default,
            "sort_order": row.sort_order,
        }

    workflows = []
    for workflow in context.workflows:
        jdata = junction_data.get(workflow.id, {})
        workflows.append(serialize_workflow(
            workflow,
            is_context_default=jdata.get("is_context_default", False),
            include_stages=False,
        ))

    return {
        "id": context.id,
        "slug": context.slug,
        "display_name": context.display_name,
        "description": context.description or "",
        "icon": context.icon,
        "theme": context.theme,
        "image": context.image.slug if context.image else None,
        "weight": context.weight,
        "enabled": context.enabled,
        "image_enabled": context.image.enabled if context.image else None,
        "default_payload": context.default_payload or {},
        "source_package": context.source_package,
        "source_key": context.source_key,
        "version": context.version,
        "languages": [serialize_language(lang) for lang in context.languages],
        "integrations": [serialize_integration(i) for i in context.integrations],
        "workflows": workflows,
        "api_keys": [serialize_api_key_requirement(ak) for ak in context.api_keys],
        "visible_to_roles": visible_to_roles or [],
    }


def serialize_context_full(
    context: Context,
    db,
    visible_to_roles: list[str] | None = None,
) -> dict[str, Any]:
    """Serialize a Context with full workflow details including stages."""
    # Get junction table data for is_context_default
    junction_data = {}
    junction_results = db.execute(
        beaker_context_workflows.select().where(
            beaker_context_workflows.c.context_id == context.id
        )
    ).fetchall()
    for row in junction_results:
        junction_data[row.workflow_id] = {
            "is_context_default": row.is_context_default,
            "sort_order": row.sort_order,
        }

    workflows = []
    for workflow in context.workflows:
        jdata = junction_data.get(workflow.id, {})
        workflows.append(serialize_workflow(
            workflow,
            is_context_default=jdata.get("is_context_default", False),
            include_stages=True,
        ))

    return {
        "id": context.id,
        "slug": context.slug,
        "display_name": context.display_name,
        "description": context.description or "",
        "icon": context.icon,
        "theme": context.theme,
        "image": context.image.slug if context.image else None,
        "weight": context.weight,
        "enabled": context.enabled,
        "image_enabled": context.image.enabled if context.image else None,
        "default_payload": context.default_payload or {},
        "source_package": context.source_package,
        "source_key": context.source_key,
        "version": context.version,
        "languages": [serialize_language(lang) for lang in context.languages],
        "integrations": [serialize_integration(i) for i in context.integrations],
        "workflows": workflows,
        "api_keys": [serialize_api_key_requirement(ak) for ak in context.api_keys],
        "visible_to_roles": visible_to_roles or [],
    }


# ============================================
# Context API Handlers
# ============================================

class ContextListHandler(APIHandler):
    """List all contexts with summary information."""

    async def get(self):
        user = self.current_user
        if not user:
            raise web.HTTPError(403, "Authentication required")

        contexts = self.db.query(Context).options(
            joinedload(Context.integrations),
            joinedload(Context.workflows),
            joinedload(Context.image),
        ).filter(Context.enabled == True).all()

        # Effective enabled: exclude contexts whose image is disabled
        contexts = [c for c in contexts if c.image is None or c.image.enabled]

        # Filter by user roles
        user_roles = {role.name for role in user.roles}
        contexts = filter_contexts_by_role(self.db, contexts, user_roles)

        role_map = get_context_role_map(self.db, [c.id for c in contexts])
        result = {
            "contexts": [
                serialize_context_summary(c, visible_to_roles=role_map.get(c.id, []))
                for c in contexts
            ]
        }
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


class ContextDetailsHandler(APIHandler):
    """
    Get all contexts with full details and node image information.
    Contexts are returned as a dict keyed by slug under the 'contexts' key.
    Node images are returned as a list under the 'nodes' key.
    """

    async def get(self):
        user = self.current_user
        if not user:
            raise web.HTTPError(403, "Authentication required")

        contexts = self.db.query(Context).options(
            joinedload(Context.integrations),
            joinedload(Context.workflows).joinedload(Workflow.stages),
            joinedload(Context.workflows).joinedload(Workflow.category),
            joinedload(Context.languages),
            joinedload(Context.api_keys),
            joinedload(Context.image),
        ).filter(Context.enabled == True).all()

        # Effective enabled: exclude contexts whose image is disabled
        contexts = [c for c in contexts if c.image is None or c.image.enabled]

        # Filter by user roles
        user_roles = {role.name for role in user.roles}
        contexts = filter_contexts_by_role(self.db, contexts, user_roles)

        role_map = get_context_role_map(self.db, [c.id for c in contexts])
        context_details = {}
        for context in contexts:
            context_details[context.slug] = serialize_context_full(
                context, self.db, visible_to_roles=role_map.get(context.id, [])
            )

        nodes = self.db.query(NodeImages).filter(NodeImages.enabled == True).all()

        result = {
            "contexts": context_details,
            "nodes": {n.slug: serialize_node_image(n) for n in nodes},
        }

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


class ContextDetailHandler(APIHandler):
    """Get a single context by slug with workflow summaries."""

    async def get(self, slug: str):
        user = self.current_user
        if not user:
            raise web.HTTPError(403, "Authentication required")

        context = self.db.query(Context).options(
            joinedload(Context.integrations),
            joinedload(Context.workflows).joinedload(Workflow.category),
            joinedload(Context.languages),
            joinedload(Context.api_keys),
            joinedload(Context.image),
        ).filter(Context.slug == slug, Context.enabled == True).first()

        # Effective enabled: also check that the image is not disabled
        if not context or (context.image is not None and not context.image.enabled):
            raise web.HTTPError(404, f"Context not found: {slug}")

        # Check role visibility
        user_roles = {role.name for role in user.roles}
        filtered = filter_contexts_by_role(self.db, [context], user_roles)
        if not filtered:
            raise web.HTTPError(404, f"Context not found: {slug}")

        role_map = get_context_role_map(self.db, [context.id])
        result = serialize_context_detail(
            context, self.db, visible_to_roles=role_map.get(context.id, [])
        )
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


class ContextFullHandler(APIHandler):
    """Get a single context by slug with full workflow details including stages."""

    async def get(self, slug: str):
        user = self.current_user
        if not user:
            raise web.HTTPError(403, "Authentication required")

        context = self.db.query(Context).options(
            joinedload(Context.integrations),
            joinedload(Context.workflows).joinedload(Workflow.stages),
            joinedload(Context.workflows).joinedload(Workflow.category),
            joinedload(Context.languages),
            joinedload(Context.api_keys),
            joinedload(Context.image),
        ).filter(Context.slug == slug, Context.enabled == True).first()

        # Effective enabled: also check that the image is not disabled
        if not context or (context.image is not None and not context.image.enabled):
            raise web.HTTPError(404, f"Context not found: {slug}")

        # Check role visibility
        user_roles = {role.name for role in user.roles}
        filtered = filter_contexts_by_role(self.db, [context], user_roles)
        if not filtered:
            raise web.HTTPError(404, f"Context not found: {slug}")

        role_map = get_context_role_map(self.db, [context.id])
        result = serialize_context_full(
            context, self.db, visible_to_roles=role_map.get(context.id, [])
        )
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


class SessionHandler(APIHandler):
    @needs_scope('servers')
    async def get(self):
        # TODO
        pass

    @needs_scope('servers')
    async def post(self):
        # TODO
        pass


def get_override_handlers(base_url: str = '/', ui_path: str = "./ui") -> list[HandlerTuple]:
    """
    Return list of extra handlers to register with JupyterHub, overriding any existing rules with identical match strings.

    Args:
        base_url: The hub's base URL (default: '/' for root deployment)
                  Can be overridden to '/hub/' or other prefix in config

    Returns:
        List of (route_pattern, handler_class) tuples
    """
    handlers = [
        (r"/api/user", UserInfoHandler),
        (r"/api/beakerhub/contexts/details", ContextDetailsHandler),
    ]

    return handlers

handlers = [
    (r"/api/user", UserInfoHandler),
    (r"/api/users/([^/]+)/server", BeakerhubUserServerAPIHandler),
    (r"/api/users/([^/]+)/servers/([^/]*)", BeakerhubUserServerAPIHandler),
    (r"/api/users/([^/]+)/servers/([^/]*)/progress", BeakerhubSpawnProgressAPIHandler),
    # Context API endpoints
    (r"/api/beakerhub/contexts", ContextListHandler),
    (r"/api/beakerhub/contexts/details", ContextDetailsHandler),
    (r"/api/beakerhub/contexts/([^/]+)", ContextDetailHandler),
    (r"/api/beakerhub/contexts/([^/]+)/full", ContextFullHandler),
]
