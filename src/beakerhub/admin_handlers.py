"""Admin API handlers for BeakerHub context management."""
import datetime
import json
import uuid
from typing import Any
from urllib.parse import quote

from tornado import web
from tornado.httpclient import AsyncHTTPClient, HTTPClientError, HTTPRequest
from jupyterhub.apihandlers import APIHandler
from jupyterhub.orm import Spawner
from jupyterhub.scopes import needs_scope
from sqlalchemy.orm import joinedload

from beakerhub.orm import (
    ApiKey,
    BeakerSession,
    Context,
    Integration,
    Language,
    NodeImages,
    NodeImageTask,
    NodeSecret,
    Server,
    Workflow,
    WorkflowStage,
    beaker_context_api_keys,
    beaker_context_integrations,
    beaker_context_languages,
    beaker_context_roles,
    beaker_context_secrets,
    beaker_context_workflows,
)
from beakerhub.api_handlers import (
    get_context_role_map,
    serialize_api_key_requirement,
    serialize_context_full,
    serialize_integration,
    serialize_language,
    serialize_node_image,
    serialize_workflow,
    serialize_workflow_stage,
)


# ============================================
# Admin Context CRUD Handlers
# ============================================

class AdminContextListHandler(APIHandler):
    """List all contexts (including disabled) and create new contexts."""

    @needs_scope('admin:users')
    async def get(self):
        """List all contexts with full details, including disabled ones."""
        contexts = self.db.query(Context).options(
            joinedload(Context.integrations),
            joinedload(Context.workflows).joinedload(Workflow.stages),
            joinedload(Context.workflows).joinedload(Workflow.category),
            joinedload(Context.languages),
            joinedload(Context.api_keys),
            joinedload(Context.image),
        ).all()

        role_map = get_context_role_map(self.db, [c.id for c in contexts])
        result = {
            "contexts": [
                serialize_context_full(c, self.db, visible_to_roles=role_map.get(c.id, []))
                for c in contexts
            ]
        }
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))

    def _generate_manual_source_key(self) -> str:
        """Generate a unique source_key for a manually-created context.

        Imported contexts use "image_slug:package:slug"; manual ones get a
        "manual:" prefix plus a short UUID. Retries on the (extremely unlikely)
        event of a collision.
        """
        while True:
            candidate = f"manual:{uuid.uuid4().hex[:12]}"
            exists = self.db.query(Context).filter(
                Context.source_key == candidate
            ).first()
            if not exists:
                return candidate

    @needs_scope('admin:users')
    async def post(self):
        """Create a new context."""
        body = self.get_json_body()
        if not body:
            raise web.HTTPError(400, "Request body is required")

        slug = body.get("slug")
        display_name = body.get("display_name")
        if not slug or not display_name:
            raise web.HTTPError(400, "slug and display_name are required")

        # Slugs are no longer globally unique (the same slug can exist across
        # multiple images), so manually-created contexts get a synthetic, unique
        # source_key. Imported contexts derive their source_key from the package.
        source_key = self._generate_manual_source_key()

        context = Context(
            slug=slug,
            source_key=source_key,
            display_name=display_name,
            description=body.get("description", ""),
            icon=body.get("icon"),
            theme=body.get("theme", "data-science"),
            weight=body.get("weight", 50),
            default_payload=body.get("default_payload", {}),
            enabled=body.get("enabled", False),
        )

        # Set image relationship
        image_id = body.get("image_id")
        if image_id is not None:
            image = self.db.query(NodeImages).filter(NodeImages.id == image_id).first()
            if not image:
                raise web.HTTPError(400, f"Node image with id {image_id} not found")
            context.image = image

        self.db.add(context)

        # Handle relationship assignments (must flush first so context.id is available)
        self.db.flush()
        self._assign_relationships(context, body)

        self.db.commit()

        role_map = get_context_role_map(self.db, [context.id])
        result = serialize_context_full(
            context, self.db, visible_to_roles=role_map.get(context.id, [])
        )
        self.set_status(201)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))

    def _assign_relationships(self, context: Context, body: dict) -> None:
        """Assign workflows, integrations, languages, API keys, and roles from request body."""
        workflow_ids = body.get("workflow_ids")
        if workflow_ids is not None:
            workflows = self.db.query(Workflow).filter(Workflow.id.in_(workflow_ids)).all()
            context.workflows = workflows

        integration_ids = body.get("integration_ids")
        if integration_ids is not None:
            integrations = self.db.query(Integration).filter(
                Integration.id.in_(integration_ids)
            ).all()
            context.integrations = integrations

        language_slugs = body.get("language_slugs")
        if language_slugs is not None:
            languages = self.db.query(Language).filter(
                Language.slug.in_(language_slugs)
            ).all()
            context.languages = languages

        api_key_ids = body.get("api_key_ids")
        if api_key_ids is not None:
            api_keys = self.db.query(ApiKey).filter(ApiKey.id.in_(api_key_ids)).all()
            context.api_keys = api_keys

        visible_to_roles = body.get("visible_to_roles")
        if visible_to_roles is not None:
            self.db.execute(
                beaker_context_roles.delete().where(
                    beaker_context_roles.c.context_id == context.id
                )
            )
            for role_name in visible_to_roles:
                self.db.execute(
                    beaker_context_roles.insert().values(
                        context_id=context.id, role_name=role_name
                    )
                )


class AdminContextDetailHandler(APIHandler):
    """Get, update, or soft-delete a single context by source_key.

    Contexts are identified by their globally-unique source_key. Slugs are no
    longer unique (the same slug can exist across multiple images), so they
    cannot be used to select a single context.
    """

    def _get_context(self, source_key: str) -> Context:
        context = self.db.query(Context).options(
            joinedload(Context.integrations),
            joinedload(Context.workflows).joinedload(Workflow.stages),
            joinedload(Context.workflows).joinedload(Workflow.category),
            joinedload(Context.languages),
            joinedload(Context.api_keys),
            joinedload(Context.image),
        ).filter(Context.source_key == source_key).first()
        if not context:
            raise web.HTTPError(404, f"Context not found: {source_key}")
        return context

    @needs_scope('admin:users')
    async def get(self, source_key: str):
        """Get full context detail."""
        context = self._get_context(source_key)
        role_map = get_context_role_map(self.db, [context.id])
        result = serialize_context_full(
            context, self.db, visible_to_roles=role_map.get(context.id, [])
        )
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))

    @needs_scope('admin:users')
    async def put(self, source_key: str):
        """Update a context. source_key, source_package, and version are not updatable."""
        context = self._get_context(source_key)
        body = self.get_json_body()
        if not body:
            raise web.HTTPError(400, "Request body is required")

        # Update scalar fields (excluding read-only source fields)
        updatable_fields = [
            "display_name", "description", "icon", "theme",
            "weight", "default_payload", "enabled",
        ]
        for field in updatable_fields:
            if field in body:
                setattr(context, field, body[field])

        # Update image relationship
        if "image_id" in body:
            image_id = body["image_id"]
            if image_id is None:
                context.image = None
            else:
                image = self.db.query(NodeImages).filter(NodeImages.id == image_id).first()
                if not image:
                    raise web.HTTPError(400, f"Node image with id {image_id} not found")
                context.image = image

        # Handle relationship assignments
        self._assign_relationships(context, body)

        self.db.commit()

        # Re-query to get fresh eager-loaded data
        context = self._get_context(source_key)
        role_map = get_context_role_map(self.db, [context.id])
        result = serialize_context_full(
            context, self.db, visible_to_roles=role_map.get(context.id, [])
        )
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))

    @needs_scope('admin:users')
    async def delete(self, source_key: str):
        """Hard-delete a context and cascade through association tables."""
        context = self._get_context(source_key)
        self.db.delete(context)
        self.db.commit()
        self.set_status(204)

    def _assign_relationships(self, context: Context, body: dict) -> None:
        """Assign workflows, integrations, languages, API keys, and roles from request body."""
        workflow_ids = body.get("workflow_ids")
        if workflow_ids is not None:
            workflows = self.db.query(Workflow).filter(Workflow.id.in_(workflow_ids)).all()
            context.workflows = workflows

        integration_ids = body.get("integration_ids")
        if integration_ids is not None:
            integrations = self.db.query(Integration).filter(
                Integration.id.in_(integration_ids)
            ).all()
            context.integrations = integrations

        language_slugs = body.get("language_slugs")
        if language_slugs is not None:
            languages = self.db.query(Language).filter(
                Language.slug.in_(language_slugs)
            ).all()
            context.languages = languages

        api_key_ids = body.get("api_key_ids")
        if api_key_ids is not None:
            api_keys = self.db.query(ApiKey).filter(ApiKey.id.in_(api_key_ids)).all()
            context.api_keys = api_keys

        visible_to_roles = body.get("visible_to_roles")
        if visible_to_roles is not None:
            self.db.execute(
                beaker_context_roles.delete().where(
                    beaker_context_roles.c.context_id == context.id
                )
            )
            for role_name in visible_to_roles:
                self.db.execute(
                    beaker_context_roles.insert().values(
                        context_id=context.id, role_name=role_name
                    )
                )


# ============================================
# Supporting Entity List Handlers
# ============================================

def serialize_node_image_with_contexts(
    node: NodeImages, db: Any
) -> dict[str, Any]:
    """Serialize a NodeImages ORM object including associated contexts."""
    result = serialize_node_image(node)
    contexts = db.query(Context).filter(Context.image_id == node.id).all()
    result["contexts"] = [
        {
            "slug": c.slug,
            "source_key": c.source_key,
            "display_name": c.display_name,
            "enabled": c.enabled,
        }
        for c in contexts
    ]

    # Include the most recent import task info
    latest_task = db.query(NodeImageTask).filter(
        NodeImageTask.node_image_id == node.id,
        NodeImageTask.task_type == "context_import",
    ).order_by(NodeImageTask.created_at.desc()).first()
    if latest_task:
        result["last_import"] = {
            "task_id": latest_task.id,
            "status": latest_task.status,
            "job_name": latest_task.job_name,
            "created_at": latest_task.created_at.isoformat() if latest_task.created_at else None,
            "updated_at": latest_task.updated_at.isoformat() if latest_task.updated_at else None,
            "error": latest_task.error,
        }
    else:
        result["last_import"] = None

    return result


def registry_api_url(registry: str, path: str) -> str:
    """Build a Docker Registry HTTP API v2 URL from an image registry setting."""
    registry = registry.rstrip("/")
    if not registry.startswith(("http://", "https://")):
        registry = f"https://{registry}"
    return f"{registry}/v2/{path.lstrip('/')}"


class AdminRegistryImageListHandler(APIHandler):
    """List repositories and tags from the configured default Docker registry.

    This deliberately uses the Registry HTTP API from the hub, rather than the
    browser, so the configured registry does not need to provide CORS headers.
    Authentication is not inferred from Kubernetes imagePullSecrets.
    """

    @needs_scope('admin:users')
    async def get(self):
        app = self.settings.get("app")
        registry = app.config.get("BeakerKubeSpawner", {}).get("default_registry", "") if app else ""
        registry = str(registry).rstrip("/")
        if not registry:
            raise web.HTTPError(400, "No default image registry is configured")

        client = AsyncHTTPClient()
        try:
            catalog_response = await client.fetch(
                HTTPRequest(registry_api_url(registry, "_catalog?n=1000"), request_timeout=10)
            )
            repositories = json.loads(catalog_response.body).get("repositories", [])
            if not isinstance(repositories, list):
                raise ValueError("Registry catalog response has an invalid repositories field")

            images: list[dict[str, str]] = []
            for repository in sorted(repo for repo in repositories if isinstance(repo, str)):
                tags_response = await client.fetch(
                    HTTPRequest(
                        registry_api_url(registry, f"{quote(repository, safe='/')}/tags/list?n=1000"),
                        request_timeout=10,
                    )
                )
                tags = json.loads(tags_response.body).get("tags") or []
                if not isinstance(tags, list):
                    raise ValueError(f"Registry tags response for '{repository}' has an invalid tags field")
                for tag in sorted(tag for tag in tags if isinstance(tag, str)):
                    images.append({"repository": repository, "tag": tag})
        except (HTTPClientError, ValueError, json.JSONDecodeError) as exc:
            status = exc.code if isinstance(exc, HTTPClientError) else 502
            if status in (401, 403):
                message = "The configured registry requires authentication; registry credentials are not yet configured for catalog access."
            else:
                message = f"Unable to list images from registry '{registry}': {exc}"
            raise web.HTTPError(status, message) from exc

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({"registry": registry, "images": images}))


class AdminNodeImageListHandler(APIHandler):
    """List all node images and create new ones."""

    @needs_scope('admin:users')
    async def get(self):
        nodes = self.db.query(NodeImages).all()
        result = {
            "node_images": [
                serialize_node_image_with_contexts(n, self.db) for n in nodes
            ]
        }
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))

    @needs_scope('admin:users')
    async def post(self):
        """Create a new node image and launch a context import job."""
        body = self.get_json_body()
        if not body:
            raise web.HTTPError(400, "Request body is required")

        slug = body.get("slug")
        if not slug:
            raise web.HTTPError(400, "slug is required")

        existing = self.db.query(NodeImages).filter(NodeImages.slug == slug).first()
        if existing:
            raise web.HTTPError(409, f"Node image with slug '{slug}' already exists")

        node = NodeImages(
            slug=slug,
            default_registry=body.get("default_registry", ""),
            repository=body.get("repository", ""),
            default_tag=body.get("default_tag", ""),
            metadata_=body.get("metadata", {}),
            enabled=body.get("enabled", False),
        )
        self.db.add(node)
        self.db.commit()

        # Launch context import job
        import_task = None
        import_error = None
        app = self.settings.get("app")
        if app:
            from beakerhub.nodes.import_handlers import launch_import_task
            try:
                import_task = launch_import_task(self.db, app, node)
            except Exception as e:
                import_error = str(e)
                self.log.warning(f"Failed to launch import for {slug}: {e}")

        result = serialize_node_image_with_contexts(node, self.db)
        if import_task:
            result["import_task"] = {
                "task_id": import_task.id,
                "job_name": import_task.job_name,
                "status": import_task.status,
            }
        elif import_error:
            result["import_task"] = {
                "status": "failed",
                "error": import_error,
            }
        self.set_status(201)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


class AdminNodeImageDetailHandler(APIHandler):
    """Get, update, or delete a single node image by ID."""

    def _get_node_image(self, image_id: int) -> NodeImages:
        node = self.db.query(NodeImages).filter(NodeImages.id == image_id).first()
        if not node:
            raise web.HTTPError(404, f"Node image not found: {image_id}")
        return node

    @needs_scope('admin:users')
    async def get(self, image_id: str):
        """Get a single node image with associated contexts."""
        node = self._get_node_image(int(image_id))
        result = serialize_node_image_with_contexts(node, self.db)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))

    @needs_scope('admin:users')
    async def put(self, image_id: str):
        """Update a node image."""
        node = self._get_node_image(int(image_id))
        body = self.get_json_body()
        if not body:
            raise web.HTTPError(400, "Request body is required")

        updatable_fields = [
            "slug", "default_registry", "repository", "default_tag", "enabled",
        ]
        for field in updatable_fields:
            if field in body:
                setattr(node, field, body[field])

        if "metadata" in body:
            node.metadata_ = body["metadata"]

        self.db.commit()

        result = serialize_node_image_with_contexts(node, self.db)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))

    @needs_scope('admin:users')
    async def delete(self, image_id: str):
        """Delete a node image. Contexts referencing it will have image_id set to NULL."""
        node = self._get_node_image(int(image_id))
        self.db.delete(node)
        self.db.commit()
        self.set_status(204)


class AdminWorkflowListHandler(APIHandler):
    """List all workflows."""

    @needs_scope('admin:users')
    async def get(self):
        workflows = self.db.query(Workflow).options(
            joinedload(Workflow.stages),
            joinedload(Workflow.category),
        ).all()
        result = {
            "workflows": [serialize_workflow(w, include_stages=False) for w in workflows]
        }
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


class AdminIntegrationListHandler(APIHandler):
    """List all integrations."""

    @needs_scope('admin:users')
    async def get(self):
        integrations = self.db.query(Integration).all()
        result = {
            "integrations": [serialize_integration(i) for i in integrations]
        }
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


class AdminIntegrationDetailHandler(APIHandler):
    """Get or update a single integration by ID."""

    def _get_integration(self, integration_id: int) -> Integration:
        integration = self.db.query(Integration).filter(
            Integration.id == integration_id
        ).first()
        if not integration:
            raise web.HTTPError(404, f"Integration not found: {integration_id}")
        return integration

    @needs_scope('admin:users')
    async def get(self, integration_id: str):
        """Get integration detail including which contexts reference it."""
        integration = self._get_integration(int(integration_id))
        result = serialize_integration(integration)
        result["contexts"] = [
            {"slug": c.slug, "source_key": c.source_key, "display_name": c.display_name}
            for c in integration.contexts
        ]
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))

    @needs_scope('admin:users')
    async def put(self, integration_id: str):
        """Update an integration. Source fields are not updatable."""
        integration = self._get_integration(int(integration_id))
        body = self.get_json_body()
        if not body:
            raise web.HTTPError(400, "Request body is required")

        updatable_fields = ["name", "description", "enabled"]
        for field in updatable_fields:
            if field in body:
                setattr(integration, field, body[field])

        self.db.commit()

        result = serialize_integration(integration)
        result["contexts"] = [
            {"slug": c.slug, "source_key": c.source_key, "display_name": c.display_name}
            for c in integration.contexts
        ]
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


class AdminLanguageListHandler(APIHandler):
    """List all languages."""

    @needs_scope('admin:users')
    async def get(self):
        languages = self.db.query(Language).all()
        result = {
            "languages": [serialize_language(lang) for lang in languages]
        }
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


def serialize_api_key(ak: ApiKey) -> dict[str, Any]:
    return {
        "id": ak.id,
        "env_var": ak.env_var,
        "display_name": ak.display_name,
        "description": ak.description,
        "required": ak.required,
    }


class AdminWorkflowDetailHandler(APIHandler):
    """Get or update a single workflow by ID."""

    def _get_workflow(self, workflow_id: int) -> Workflow:
        workflow = self.db.query(Workflow).options(
            joinedload(Workflow.stages),
            joinedload(Workflow.category),
        ).filter(Workflow.id == workflow_id).first()
        if not workflow:
            raise web.HTTPError(404, f"Workflow not found: {workflow_id}")
        return workflow

    @needs_scope('admin:users')
    async def get(self, workflow_id: str):
        """Get full workflow detail including stages."""
        workflow = self._get_workflow(int(workflow_id))
        result = serialize_workflow(workflow, include_stages=True)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))

    @needs_scope('admin:users')
    async def put(self, workflow_id: str):
        """Update a workflow. Source fields are not updatable."""
        workflow = self._get_workflow(int(workflow_id))
        body = self.get_json_body()
        if not body:
            raise web.HTTPError(400, "Request body is required")

        updatable_fields = [
            "title", "human_description", "agent_description",
            "example_prompt", "hidden", "enabled",
        ]
        for field in updatable_fields:
            if field in body:
                setattr(workflow, field, body[field])

        if "category_slug" in body:
            workflow.category_slug = body["category_slug"]

        if "metadata" in body:
            workflow.metadata_ = body["metadata"]

        self.db.commit()

        workflow = self._get_workflow(int(workflow_id))
        result = serialize_workflow(workflow, include_stages=True)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


class AdminWorkflowStageDetailHandler(APIHandler):
    """Get or update a single workflow stage."""

    def _get_stage(self, workflow_id: int, stage_id: int) -> WorkflowStage:
        stage = self.db.query(WorkflowStage).filter(
            WorkflowStage.id == stage_id,
            WorkflowStage.workflow_id == workflow_id,
        ).first()
        if not stage:
            raise web.HTTPError(404, f"Stage {stage_id} not found in workflow {workflow_id}")
        return stage

    @needs_scope('admin:users')
    async def get(self, workflow_id: str, stage_id: str):
        """Get a single stage."""
        stage = self._get_stage(int(workflow_id), int(stage_id))
        result = serialize_workflow_stage(stage)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))

    @needs_scope('admin:users')
    async def put(self, workflow_id: str, stage_id: str):
        """Update a stage."""
        stage = self._get_stage(int(workflow_id), int(stage_id))
        body = self.get_json_body()
        if not body:
            raise web.HTTPError(400, "Request body is required")

        updatable_fields = ["name", "sort_order", "description"]
        for field in updatable_fields:
            if field in body:
                setattr(stage, field, body[field])

        if "metadata" in body:
            stage.metadata_ = body["metadata"]

        self.db.commit()

        result = serialize_workflow_stage(stage)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


class AdminApiKeyListHandler(APIHandler):
    """List and create API key definitions."""

    @needs_scope('admin:users')
    async def get(self):
        api_keys = self.db.query(ApiKey).all()
        result = {"api_keys": [serialize_api_key(ak) for ak in api_keys]}
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))

    @needs_scope('admin:users')
    async def post(self):
        """Create a new API key definition."""
        body = self.get_json_body()
        if not body:
            raise web.HTTPError(400, "Request body is required")

        env_var = body.get("env_var")
        display_name = body.get("display_name")
        if not env_var or not display_name:
            raise web.HTTPError(400, "env_var and display_name are required")

        existing = self.db.query(ApiKey).filter(ApiKey.env_var == env_var).first()
        if existing:
            raise web.HTTPError(409, f"API key with env_var '{env_var}' already exists")

        api_key = ApiKey(
            env_var=env_var,
            display_name=display_name,
            description=body.get("description", ""),
            required=body.get("required", True),
        )
        self.db.add(api_key)
        self.db.commit()

        self.set_status(201)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(serialize_api_key(api_key)))


# ============================================
# Secret Vault Handlers
# ============================================

def serialize_node_secret(secret: NodeSecret) -> dict[str, Any]:
    """Serialize a NodeSecret. The value is intentionally omitted for list views."""
    return {
        "id": secret.id,
        "node_image_id": secret.node_image_id,
        "env_var": secret.env_var,
        "description": secret.description,
        "policies": secret.policies,
        "created_at": secret.created_at.isoformat() if secret.created_at else None,
        "updated_at": secret.updated_at.isoformat() if secret.updated_at else None,
    }


def serialize_node_secret_with_value(secret: NodeSecret) -> dict[str, Any]:
    """Serialize a NodeSecret including the decrypted value."""
    result = serialize_node_secret(secret)
    result["value"] = secret.value
    return result


# Fields a client may write on a vault secret, mapped to the value used when creating one
# without supplying it. Declared once, and applied by apply_node_secret_fields below, so
# that create and update cannot drift apart: adding a new field to the vault means adding
# one entry here and one to serialize_node_secret, and both POST and PUT pick it up.
#
# `env_var` and `node_image_id` are deliberately absent — together they identify the
# secret rather than describe it, so they are handled explicitly at each call site.
NODE_SECRET_WRITABLE_FIELDS: dict[str, Any] = {
    "value": None,          # required when creating; callers validate before calling
    "description": None,
    "policies": {},
}


def apply_node_secret_fields(secret: NodeSecret, body: dict[str, Any], *, creating: bool) -> None:
    """Copy the writable fields from a request body onto a secret.

    A field absent from the body means "leave it alone" when updating, and "use the
    default" when creating. So a PUT can change one field without restating the others,
    and a POST that lands on an existing secret only touches what it actually sent.
    """
    for field, default_value in NODE_SECRET_WRITABLE_FIELDS.items():
        if field in body:
            setattr(secret, field, body[field])
        elif creating:
            setattr(secret, field, default_value)


class AdminSecretVaultHandler(APIHandler):
    """List and create vault secrets.

    Query params:
        node_image_id (int|"global") — filter by node; "global" returns only
            secrets where node_image_id IS NULL.
        include_values (bool) — if "true", include decrypted values in response.
    """

    @needs_scope('admin:users')
    async def get(self):
        query = self.db.query(NodeSecret)

        node_filter = self.get_query_argument("node_image_id", None)
        if node_filter is not None:
            if node_filter == "global":
                query = query.filter(NodeSecret.node_image_id.is_(None))
            else:
                query = query.filter(NodeSecret.node_image_id == int(node_filter))

        secrets = query.order_by(NodeSecret.env_var).all()
        include_values = self.get_query_argument("include_values", "false").lower() == "true"
        serializer = serialize_node_secret_with_value if include_values else serialize_node_secret

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({"secrets": [serializer(s) for s in secrets]}))

    def _find_in_scope(self, node_image_id: int | None, env_var: str) -> NodeSecret | None:
        """Find the secret occupying a given (node_image_id, env_var) scope, if any.

        This mirrors the uq_node_secret_env_var unique constraint, so a hit here is
        exactly the row a plain insert would collide with. A node_image_id of None means
        the global scope, which has to be matched with IS NULL — SQL `= NULL` is never
        true, so using it would miss every existing global secret and then fail on the
        constraint instead of updating.
        """
        in_scope = (
            NodeSecret.node_image_id.is_(None) if node_image_id is None
            else NodeSecret.node_image_id == node_image_id
        )
        return self.db.query(NodeSecret).filter(in_scope, NodeSecret.env_var == env_var).first()

    @needs_scope('admin:users')
    async def post(self):
        """Create or update a vault secret.

        Upsert semantics: posting an env_var that already exists in the same scope updates
        that secret rather than colliding with the unique constraint. Which fields get
        written is decided entirely by NODE_SECRET_WRITABLE_FIELDS.
        """
        body = self.get_json_body()
        if not body:
            raise web.HTTPError(400, "Request body is required")

        env_var = body.get("env_var")
        if not env_var or body.get("value") is None:
            raise web.HTTPError(400, "env_var and value are required")

        node_image_id = body.get("node_image_id")  # None = global scope
        if node_image_id is not None:
            node = self.db.query(NodeImages).filter(NodeImages.id == node_image_id).first()
            if not node:
                raise web.HTTPError(400, f"Node image with id {node_image_id} not found")

        secret = self._find_in_scope(node_image_id, env_var)
        creating = secret is None
        if creating:
            secret = NodeSecret(node_image_id=node_image_id, env_var=env_var)
            self.db.add(secret)

        apply_node_secret_fields(secret, body, creating=creating)
        self.db.commit()

        self.set_status(201 if creating else 200)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(serialize_node_secret(secret)))


class AdminSecretVaultDetailHandler(APIHandler):
    """Get, update, or delete a single vault secret by ID."""

    def _get_secret(self, secret_id: int) -> NodeSecret:
        secret = self.db.query(NodeSecret).filter(NodeSecret.id == secret_id).first()
        if not secret:
            raise web.HTTPError(404, f"Secret not found: {secret_id}")
        return secret

    @needs_scope('admin:users')
    async def get(self, secret_id: str):
        secret = self._get_secret(int(secret_id))
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(serialize_node_secret_with_value(secret)))

    @needs_scope('admin:users')
    async def put(self, secret_id: str):
        secret = self._get_secret(int(secret_id))
        body = self.get_json_body()
        if not body:
            raise web.HTTPError(400, "Request body is required")

        # env_var identifies the secret rather than describing it, so it is not one of
        # NODE_SECRET_WRITABLE_FIELDS and is handled here on its own.
        if "env_var" in body:
            secret.env_var = body["env_var"]

        apply_node_secret_fields(secret, body, creating=False)

        self.db.commit()

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(serialize_node_secret(secret)))

    @needs_scope('admin:users')
    async def delete(self, secret_id: str):
        secret = self._get_secret(int(secret_id))
        self.db.delete(secret)
        self.db.commit()
        self.set_status(204)


class AdminContextSecretsHandler(APIHandler):
    """Manage which vault secrets are enabled/disabled for a specific context.

    GET returns the list of all applicable secrets (globals + node-specific)
    with their enabled state for this context.
    PUT accepts a list of {node_secret_id, enabled} to set overrides.
    """

    def _get_context(self, source_key: str) -> Context:
        context = self.db.query(Context).filter(Context.source_key == source_key).first()
        if not context:
            raise web.HTTPError(404, f"Context not found: {source_key}")
        return context

    @needs_scope('admin:users')
    async def get(self, source_key: str):
        context = self._get_context(source_key)

        # Get overrides for this context
        overrides = {}
        rows = self.db.execute(
            beaker_context_secrets.select().where(
                beaker_context_secrets.c.context_id == context.id
            )
        ).fetchall()
        for row in rows:
            overrides[row.node_secret_id] = row.enabled

        # Get all applicable secrets (globals + node-specific if context has an image)
        query = self.db.query(NodeSecret).filter(NodeSecret.node_image_id.is_(None))
        if context.image_id:
            query = self.db.query(NodeSecret).filter(
                (NodeSecret.node_image_id.is_(None)) | (NodeSecret.node_image_id == context.image_id)
            )
        secrets = query.order_by(NodeSecret.env_var).all()

        result = []
        for s in secrets:
            result.append({
                "id": s.id,
                "node_image_id": s.node_image_id,
                "env_var": s.env_var,
                "description": s.description,
                "enabled": overrides.get(s.id, True),  # default enabled
            })

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({"secrets": result}))

    @needs_scope('admin:users')
    async def put(self, source_key: str):
        """Set secret overrides for a context.

        Body: {"overrides": [{"node_secret_id": 1, "enabled": false}, ...]}
        Only secrets explicitly set to false need entries; others are enabled by default.
        """
        context = self._get_context(source_key)
        body = self.get_json_body()
        if not body:
            raise web.HTTPError(400, "Request body is required")

        overrides = body.get("overrides", [])

        # Clear existing overrides for this context
        self.db.execute(
            beaker_context_secrets.delete().where(
                beaker_context_secrets.c.context_id == context.id
            )
        )

        # Insert new overrides (only store disabled entries to save space,
        # but also store explicit enabled for clarity)
        for override in overrides:
            secret_id = override.get("node_secret_id")
            enabled = override.get("enabled", True)
            if secret_id is not None:
                self.db.execute(
                    beaker_context_secrets.insert().values(
                        context_id=context.id,
                        node_secret_id=secret_id,
                        enabled=enabled,
                    )
                )

        self.db.commit()
        self.set_status(200)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({"status": "ok"}))

class AdminSessionListHandler(APIHandler):
    """Manage Sessions on the server
    """

    @staticmethod
    def _as_utc(value: datetime.datetime | None) -> str | None:
        """Serialize a database timestamp with an explicit UTC offset.

        JupyterHub stores naive datetimes in UTC. Without the offset, a client
        that parses the value applies its own local timezone to it.
        """
        if value is None:
            return None
        return value.replace(tzinfo=datetime.timezone.utc).isoformat()

    @needs_scope('admin:servers')
    async def get(self):
        spawners = self.db.query(Spawner).options(
            joinedload(Spawner.server),
            joinedload(Spawner.user),
        ).all()

        server_output = [
            {
                "server_id": spawner.server.id,
                "name": spawner.name,
                "state": spawner.state,
                "user_id": spawner.user_id,
                "user_name": spawner.user.name,
                "last_activity": self._as_utc(spawner.last_activity),
                "started": self._as_utc(spawner.started),
            }
            for spawner in spawners
            if spawner.server
        ]
        self.set_status(200)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(server_output))

# ============================================
# Handler Registration
# ============================================

admin_handlers = [
    # Context CRUD
    (r"/api/beakerhub/admin/contexts", AdminContextListHandler),
    (r"/api/beakerhub/admin/contexts/([^/]+)", AdminContextDetailHandler),
    # Supporting entity lists
    (r"/api/beakerhub/admin/registry-images", AdminRegistryImageListHandler),
    (r"/api/beakerhub/admin/node-images", AdminNodeImageListHandler),
    (r"/api/beakerhub/admin/node-images/(\d+)", AdminNodeImageDetailHandler),
    (r"/api/beakerhub/admin/workflows", AdminWorkflowListHandler),
    (r"/api/beakerhub/admin/workflows/(\d+)", AdminWorkflowDetailHandler),
    (r"/api/beakerhub/admin/workflows/(\d+)/stages/(\d+)", AdminWorkflowStageDetailHandler),
    (r"/api/beakerhub/admin/integrations", AdminIntegrationListHandler),
    (r"/api/beakerhub/admin/integrations/(\d+)", AdminIntegrationDetailHandler),
    (r"/api/beakerhub/admin/languages", AdminLanguageListHandler),
    (r"/api/beakerhub/admin/api-keys", AdminApiKeyListHandler),
    # Secret vault
    (r"/api/beakerhub/admin/secrets", AdminSecretVaultHandler),
    (r"/api/beakerhub/admin/secrets/(\d+)", AdminSecretVaultDetailHandler),
    # Context-secret overrides
    (r"/api/beakerhub/admin/contexts/([^/]+)/secrets", AdminContextSecretsHandler),
    (r"/api/beakerhub/admin/sessions", AdminSessionListHandler),
]
