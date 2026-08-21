"""Base contract for background task-runner services."""

from typing import TYPE_CHECKING

from traitlets.config import LoggingConfigurable

if TYPE_CHECKING:
    from beakerhub.orm import NodeImages


class BaseTaskRunnerService(LoggingConfigurable):
    """Submit and manage background workloads for BeakerHub tasks."""

    def submit_image_import(
        self,
        node_image: "NodeImages",
        callback_url: str,
        callback_token: str,
    ) -> str:
        """Submit an image-import workload and return its external identifier."""
        raise NotImplementedError

    def get_status(self, task_id: str) -> dict:
        """Return the current state and diagnostic message for a workload."""
        raise NotImplementedError

    def delete(self, task_id: str) -> None:
        """Delete or cancel a workload."""
        raise NotImplementedError
