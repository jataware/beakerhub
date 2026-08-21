"""AWS ECS implementation skeleton for the task-runner service."""

from typing import TYPE_CHECKING

from beakerhub.services.task.base import BaseTaskRunnerService

if TYPE_CHECKING:
    from beakerhub.orm import NodeImages


class AwsEcsTaskRunnerService(BaseTaskRunnerService):
    """Run BeakerHub background tasks as AWS ECS tasks."""

    def submit_image_import(
        self,
        node_image: "NodeImages",
        callback_url: str,
        callback_token: str,
    ) -> str:
        raise NotImplementedError("AWS ECS task submission is not implemented")

    def get_status(self, task_id: str) -> dict:
        raise NotImplementedError("AWS ECS task status polling is not implemented")

    def delete(self, task_id: str) -> None:
        raise NotImplementedError("AWS ECS task deletion is not implemented")
