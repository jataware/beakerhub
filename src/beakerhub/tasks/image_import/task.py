"""Orchestration for importing context metadata from a node image."""

import logging
from datetime import datetime, timezone
from secrets import token_urlsafe
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from beakerhub.orm import NodeImages, NodeImageTask

if TYPE_CHECKING:
    from beakerhub.app import BeakerHub


log = logging.getLogger(__name__)


def launch_import_task(
    db: Session,
    app: "BeakerHub",
    node_image: NodeImages,
) -> NodeImageTask:
    """Create and submit a context-import task for a node image."""
    existing_task = (
        db.query(NodeImageTask)
        .filter(
            NodeImageTask.node_image_id == node_image.id,
            NodeImageTask.task_type == "context_import",
            NodeImageTask.status.in_(["pending", "running"]),
        )
        .first()
    )
    if existing_task:
        raise ValueError(
            f"Import already in progress for image '{node_image.slug}' "
            f"(job: {existing_task.job_name})"
        )

    callback_token = token_urlsafe(48)
    task = NodeImageTask(
        node_image_id=node_image.id,
        task_type="context_import",
        status="pending",
        callback_token=callback_token,
    )
    db.add(task)
    db.commit()

    hub_url = getattr(app, "hub_connect_url", "http://localhost:8888")
    callback_url = (
        f"{hub_url.rstrip('/')}/api/beakerhub/internal/task-callback/"
        f"{callback_token}"
    )
    try:
        external_task_id = app.task_runner.submit_image_import(
            node_image=node_image,
            callback_url=callback_url,
            callback_token=callback_token,
        )
    except Exception as error:
        task.status = "failed"
        task.error = f"Failed to create task: {error}"
        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        log.exception("Failed to create import task for %s", node_image.slug)
        raise RuntimeError(f"Failed to create import task: {error}") from error

    task.job_name = external_task_id
    task.status = "running"
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    log.info(
        "Launched import task %s for node image %s",
        external_task_id,
        node_image.slug,
    )
    return task
