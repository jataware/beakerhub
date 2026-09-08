"""Orchestration for importing context metadata from a node image."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session, object_session

from beakerhub.orm import NodeImages, NodeImageTask
from beakerhub.services.task.base import TaskOutput, TaskStatus
from beakerhub.tasks.base import BaseImageTask
from beakerhub.utils import ingest_interchange_dump

if TYPE_CHECKING:
    from beakerhub.app import BeakerHub


log = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ImageImportTask(BaseImageTask):
    """Definition and completion behavior for a node-image context import."""

    node_image: NodeImages

    @classmethod
    def from_node_image(cls, node_image: NodeImages) -> "ImageImportTask":
        """Create the standard context-dump workload for ``node_image``."""
        return cls(
            image=node_image.default_img_string,
            entrypoint=("sh", "-c"),
            command=("beaker context dump",),
            node_image=node_image,
        )

    @property
    def task_type(self) -> str:
        return "context_import"

    def on_success(
        self,
        task: NodeImageTask,
        status: TaskStatus,
        output: TaskOutput,
    ) -> None:
        """Ingest the context dump into the image's metadata records."""
        db = object_session(task)
        if db is None:
            raise RuntimeError("Image import task is not attached to a database session")
        task.result = ingest_import_output(db, self.node_image, output)

    def on_failure(
        self,
        task: NodeImageTask,
        status: TaskStatus,
        output: TaskOutput | None,
    ) -> None:
        """Store normalized runtime diagnostics on the persisted task."""
        messages = [status.message]
        if output and output.stderr:
            messages.append(output.stderr)
        task.error = ". ".join(message for message in messages if message)


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

    task = NodeImageTask(
        node_image_id=node_image.id,
        task_type="context_import",
        status="pending",
    )
    db.add(task)
    db.commit()

    try:
        running_task = app.task_runner.submit(ImageImportTask.from_node_image(node_image))
    except Exception as error:
        task.status = "failed"
        task.error = f"Failed to create task: {error}"
        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        log.exception("Failed to create import task for %s", node_image.slug)
        raise RuntimeError(f"Failed to create import task: {error}") from error

    task.job_name = running_task.external_id
    task.status = "running"
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    log.info(
        "Launched import task %s for node image %s",
        running_task.external_id,
        node_image.slug,
    )
    return task


def ingest_import_output(
    db: Session,
    node_image: NodeImages,
    output: TaskOutput,
) -> dict[str, int]:
    """Ingest the context dumps written to an image-import task's stdout."""

    body = json.loads(output.stdout)
    if not isinstance(body, list):
        body = [body]

    combined_stats: dict[str, int] = {}
    for dump in body:
        stats = ingest_interchange_dump(
            db=db,
            dump=dump,
            node_image=node_image,
            enable_contexts=True,
            preserve_curated=True,
        )
        for key, value in stats.items():
            combined_stats[key] = combined_stats.get(key, 0) + value
    return combined_stats
