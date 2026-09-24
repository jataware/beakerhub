"""API handlers for BeakerHub dashboard services."""

import json
import logging

from jupyterhub.apihandlers import APIHandler
from jupyterhub.orm import Spawner, User
from jupyterhub.scopes import needs_scope
from sqlalchemy import func
from tornado import web

from beakerhub import __version__
from beakerhub.orm import (
    BeakerSession,
    Context,
    Integration,
    Language,
    NodeImages,
    NodeImageTask,
    NodeSecret,
    Workflow,
)
from beakerhub.services.dashboard.base import DashboardServiceError


log = logging.getLogger(__name__)


class AdminDashboardSummaryHandler(APIHandler):
    """Return application-level counts for the admin dashboard."""

    def compute_etag(self) -> None:
        return None

    @needs_scope("admin:users")
    async def get(self):
        db = self.db
        images_total = db.query(func.count(NodeImages.id)).scalar() or 0
        images_enabled = (
            db.query(func.count(NodeImages.id))
            .filter(NodeImages.enabled.is_(True))
            .scalar()
            or 0
        )
        contexts_total = db.query(func.count(Context.id)).scalar() or 0
        contexts_enabled = (
            db.query(func.count(Context.id))
            .filter(Context.enabled.is_(True))
            .scalar()
            or 0
        )
        workflows_total = db.query(func.count(Workflow.id)).scalar() or 0
        workflows_enabled = (
            db.query(func.count(Workflow.id))
            .filter(Workflow.enabled.is_(True))
            .scalar()
            or 0
        )
        integrations_total = db.query(func.count(Integration.id)).scalar() or 0
        integrations_enabled = (
            db.query(func.count(Integration.id))
            .filter(Integration.enabled.is_(True))
            .scalar()
            or 0
        )
        languages_total = db.query(func.count(Language.slug)).scalar() or 0
        secrets_total = db.query(func.count(NodeSecret.id)).scalar() or 0
        secrets_global = (
            db.query(func.count(NodeSecret.id))
            .filter(NodeSecret.node_image_id.is_(None))
            .scalar()
            or 0
        )
        users_total = db.query(func.count(User.id)).scalar() or 0
        users_admin = (
            db.query(func.count(User.id)).filter(User.admin.is_(True)).scalar() or 0
        )
        active_servers = (
            db.query(func.count(Spawner.id))
            .filter(Spawner.server_id.isnot(None))
            .scalar()
            or 0
        )
        beaker_sessions_total = db.query(func.count(BeakerSession.id)).scalar() or 0
        recent_tasks = (
            db.query(NodeImageTask)
            .join(NodeImages, NodeImageTask.node_image_id == NodeImages.id)
            .order_by(NodeImageTask.updated_at.desc())
            .limit(5)
            .all()
        )
        recent_imports = [
            {
                "task_id": task.id,
                "node_image_slug": (
                    task.node_image.slug if task.node_image else None
                ),
                "task_type": task.task_type,
                "status": task.status,
                "job_name": task.job_name,
                "created_at": (
                    task.created_at.isoformat() if task.created_at else None
                ),
                "updated_at": (
                    task.updated_at.isoformat() if task.updated_at else None
                ),
                "error": task.error,
                "result": task.result,
            }
            for task in recent_tasks
        ]
        result = {
            "app_version": __version__,
            "counts": {
                "images": {"total": images_total, "enabled": images_enabled},
                "contexts": {"total": contexts_total, "enabled": contexts_enabled},
                "workflows": {"total": workflows_total, "enabled": workflows_enabled},
                "integrations": {
                    "total": integrations_total,
                    "enabled": integrations_enabled,
                },
                "languages": {"total": languages_total},
                "secrets": {
                    "total": secrets_total,
                    "global": secrets_global,
                    "per_node": secrets_total - secrets_global,
                },
                "users": {"total": users_total, "admin": users_admin},
                "sessions": {
                    "active_servers": active_servers,
                    "beaker_sessions_total": beaker_sessions_total,
                },
            },
            "recent_imports": recent_imports,
        }
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


class AdminDashboardClusterHandler(APIHandler):
    """Return data from the configured dashboard service."""

    def compute_etag(self) -> None:
        return None

    @needs_scope("admin:users")
    async def get(self):
        try:
            result = self.settings["app"].dashboard_service.get_dashboard()
            self._add_task_sessions(result)
        except Exception as error:
            log.warning("Failed to fetch dashboard data: %s", error)
            result = {"available": False, "error": str(error)}
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


    def _add_task_sessions(self, dashboard: dict) -> None:
        """Attach JupyterHub session ownership to task workload rows.

        ECS session spawners persist their task ARN in state. Matching that ARN
        avoids one ECS tag request per task and also identifies the session owner.
        """
        task_sessions: dict[str, list[dict[str, str]]] = {}
        for spawner in (
            self.db.query(Spawner)
            .join(User)
            .filter(Spawner.server_id.isnot(None))
            .all()
        ):
            state = spawner.state if isinstance(spawner.state, dict) else {}
            task_arn = state.get("task_arn")
            if not task_arn:
                continue
            task_id = task_arn.rsplit("/", maxsplit=1)[-1]
            task_sessions.setdefault(task_id, []).append(
                {"user": spawner.user.name, "name": spawner.name}
            )

        def add_sessions(workload: dict) -> None:
            if workload.get("kind") == "Task":
                sessions = task_sessions.get(workload.get("name", ""))
                if sessions:
                    workload["sessions"] = sessions
            for child in workload.get("children", []):
                add_sessions(child)

        for workload in dashboard.get("workloads", []):
            add_sessions(workload)


class AdminSessionLogsHandler(APIHandler):
    """Return logs from the configured dashboard service."""

    def compute_etag(self) -> None:
        return None

    @needs_scope("admin:users")
    async def get(self, owner: str, session_id: str):
        container = self.get_argument("container", "notebook")
        try:
            tail_lines = int(self.get_argument("tail_lines", "5000"))
        except ValueError:
            tail_lines = 5000
        tail_lines = max(1, min(tail_lines, 100000))

        runtime_id = session_id
        spawner = (
            self.db.query(Spawner)
            .join(User)
            .filter(User.name == owner, Spawner.name == session_id)
            .first()
        )
        if spawner and isinstance(spawner.state, dict):
            runtime_id = spawner.state.get("task_arn", session_id)

        try:
            result = self.settings["app"].dashboard_service.get_session_logs(
                runtime_id,
                container,
                tail_lines,
            )
        except DashboardServiceError as error:
            raise web.HTTPError(error.status_code, reason=error.reason) from error
        except Exception as error:
            log.warning(
                "Failed to fetch session logs for %s/%s: %s",
                owner,
                session_id,
                error,
            )
            raise web.HTTPError(500, reason=str(error)) from error

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


handlers = [
    (r"/api/beakerhub/admin/dashboard/summary", AdminDashboardSummaryHandler),
    (r"/api/beakerhub/admin/dashboard/cluster", AdminDashboardClusterHandler),
    (
        r"/api/beakerhub/admin/dashboard/session-logs/([^/]+)/([^/]+)",
        AdminSessionLogsHandler,
    ),
    # Compatibility path for existing admin clients.
    (
        r"/api/beakerhub/admin/dashboard/pod-logs/([^/]+)/([^/]+)",
        AdminSessionLogsHandler,
    ),
]

api_handlers = handlers
