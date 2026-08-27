"""API handlers for background tasks."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from jupyterhub.apihandlers import APIHandler
from jupyterhub.scopes import needs_scope
from tornado import web

from beakerhub.orm import NodeImages, NodeImageTask
from beakerhub.tasks.image_import.task import ingest_import_output, launch_import_task


log = logging.getLogger(__name__)


class NodeImageImportHandler(APIHandler):
    """Trigger a context import for a node image."""

    @needs_scope("admin:users")
    async def post(self, image_id: str):
        node = self.db.query(NodeImages).filter(NodeImages.id == int(image_id)).first()
        if not node:
            raise web.HTTPError(404, f"Node image not found: {image_id}")

        try:
            task = launch_import_task(self.db, self.settings.get("app"), node)
        except ValueError as error:
            raise web.HTTPError(409, str(error)) from error
        except RuntimeError as error:
            raise web.HTTPError(500, str(error)) from error

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({
            "task_id": task.id,
            "job_name": task.job_name,
            "status": task.status,
        }))


class NodeImageImportStatusHandler(APIHandler):
    """Poll and collect the result of a node-image import task."""

    def compute_etag(self) -> None:
        return None

    @needs_scope("admin:users")
    async def get(self, image_id: str):
        node = self.db.query(NodeImages).filter(NodeImages.id == int(image_id)).first()
        if not node:
            raise web.HTTPError(404, f"Node image not found: {image_id}")

        task = self.db.query(NodeImageTask).filter(
            NodeImageTask.node_image_id == node.id,
            NodeImageTask.task_type == "context_import",
        ).order_by(NodeImageTask.created_at.desc()).first()

        if not task:
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps({"status": "none", "message": "No import has been run"}))
            return

        if task.status == "running" and task.job_name:
            try:
                runner = self.settings["app"].task_runner
                status = runner.get_status(task.job_name)
                if status.state == "completed":
                    output = runner.get_output(task.job_name)
                    if output is None:
                        raise RuntimeError("Task completed but no output is available")
                    task.result = ingest_import_output(self.db, node, output)
                    task.status = "completed"
                    task.error = None
                    task.updated_at = datetime.now(timezone.utc)
                    self.db.commit()
                    runner.delete(task.job_name)
                elif status.state == "failed":
                    output = runner.get_output(task.job_name)
                    messages = [status.message]
                    if output and output.stderr:
                        messages.append(output.stderr)
                    task.status = "failed"
                    task.error = ". ".join(message for message in messages if message)
                    task.updated_at = datetime.now(timezone.utc)
                    self.db.commit()
                    runner.delete(task.job_name)
            except Exception as error:
                log.error("Failed to poll task status for %s: %s", task.job_name, error, exc_info=error)

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


handlers = [
    (r"/api/beakerhub/admin/node-images/(\d+)/import", NodeImageImportHandler),
    (r"/api/beakerhub/admin/node-images/(\d+)/import-status", NodeImageImportStatusHandler),
]

api_handlers = handlers
