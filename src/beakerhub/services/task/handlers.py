"""API handlers for background tasks."""
import json
import logging
from datetime import datetime, timezone
from typing import Any

from tornado import web
from jupyterhub.apihandlers import APIHandler
from jupyterhub.scopes import needs_scope
from beakerhub.orm import NodeImages, NodeImageTask
from beakerhub.tasks.image_import.task import launch_import_task
from beakerhub.utils import ingest_interchange_dump

log = logging.getLogger(__name__)


class NodeImageImportHandler(APIHandler):
    """Trigger a context import for a node image."""

    @needs_scope('admin:users')
    async def post(self, image_id: str):
        """Create a task to import context data from the node image."""
        node = self.db.query(NodeImages).filter(NodeImages.id == int(image_id)).first()
        if not node:
            raise web.HTTPError(404, f"Node image not found: {image_id}")

        app = self.settings.get("app")
        try:
            task = launch_import_task(self.db, app, node)
        except ValueError as e:
            raise web.HTTPError(409, str(e))
        except RuntimeError as e:
            raise web.HTTPError(500, str(e))

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({
            "task_id": task.id,
            "job_name": task.job_name,
            "status": task.status,
        }))


class NodeImageImportStatusHandler(APIHandler):
    """Poll the status of an import task."""

    def compute_etag(self) -> None:
        return None

    @needs_scope('admin:users')
    async def get(self, image_id: str):
        """Get the current import status for a node image."""
        node = self.db.query(NodeImages).filter(NodeImages.id == int(image_id)).first()
        if not node:
            raise web.HTTPError(404, f"Node image not found: {image_id}")

        # Get the most recent task for this image
        task = self.db.query(NodeImageTask).filter(
            NodeImageTask.node_image_id == node.id,
            NodeImageTask.task_type == "context_import",
        ).order_by(NodeImageTask.created_at.desc()).first()

        if not task:
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps({"status": "none", "message": "No import has been run"}))
            return

        # If the task is still running, poll the configured task runner.
        if task.status == "running" and task.job_name:
            try:
                app = self.settings["app"]
                job_status = app.task_runner.get_status(task.job_name)
                if job_status["status"] == "failed":
                    task.status = "failed"
                    task.error = job_status["message"]
                    task.updated_at = datetime.now(timezone.utc)
                    self.db.commit()
            except Exception as e:
                log.warning(f"Failed to poll job status for {task.job_name}: {e}")

        result: dict[str, Any] = {
            "task_id": task.id,
            "status": task.status,
            "job_name": task.job_name,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        }
        if task.error:
            result["error"] = task.error
        if task.result:
            result["result"] = task.result

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


class TaskCallbackHandler(APIHandler):
    """
    Internal callback endpoint for the task reporter container.

    Authenticates via a per-task token (not admin scope).
    Receives the interchange dump JSON and ingests it.
    """

    def check_xsrf_cookie(self):
        # Internal endpoint called by a task workload, with no XSRF cookie.
        return

    def get_current_user(self):
        # Override auth — this endpoint uses token-based auth, not session auth
        return None

    async def post(self, callback_token: str):
        """Receive import results from the reporter container."""
        # Validate callback token
        task = self.db.query(NodeImageTask).filter(
            NodeImageTask.callback_token == callback_token,
            NodeImageTask.status == "running",
        ).first()
        if not task:
            raise web.HTTPError(404, "Invalid or expired callback token")

        node_image = task.node_image

        # Parse the request body
        try:
            body = json.loads(self.request.body)
        except (json.JSONDecodeError, TypeError) as e:
            task.status = "failed"
            task.error = f"Invalid JSON in callback: {e}"
            task.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            raise web.HTTPError(400, f"Invalid JSON: {e}")

        # The output is an array of InterchangeDump objects (one per package)
        if not isinstance(body, list):
            body = [body]

        # Ingest each package dump
        combined_stats: dict[str, int] = {}
        try:
            for dump in body:
                stats = ingest_interchange_dump(
                    db=self.db,
                    dump=dump,
                    node_image=node_image,
                    enable_contexts=True,
                    preserve_curated=True,
                )
                for key, value in stats.items():
                    combined_stats[key] = combined_stats.get(key, 0) + value
        except Exception as e:
            self.db.rollback()
            task.status = "failed"
            task.error = f"Ingestion failed: {e}"
            task.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            log.exception(f"Ingestion failed for task {task.id}")
            raise web.HTTPError(500, f"Ingestion failed: {e}")

        # Mark task as completed
        task.status = "completed"
        task.result = combined_stats
        task.error = None
        task.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        log.info(f"Import completed for node image {node_image.slug}: {combined_stats}")

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({"status": "ok", "stats": combined_stats}))


handlers = [
    (r"/api/beakerhub/admin/node-images/(\d+)/import", NodeImageImportHandler),
    (r"/api/beakerhub/admin/node-images/(\d+)/import-status", NodeImageImportStatusHandler),
    (r"/api/beakerhub/internal/task-callback/([^/]+)", TaskCallbackHandler),
]

api_handlers = handlers
