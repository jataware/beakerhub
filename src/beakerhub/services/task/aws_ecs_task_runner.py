"""AWS ECS implementation skeleton for the task-runner service."""

from beakerhub.services.task.base import (
    BaseTaskRunnerService,
    RunningTask,
    TaskStatus,
)
from beakerhub.tasks.base import BaseTaskDefinition


class AwsEcsTaskRunnerService(BaseTaskRunnerService):
    """Run BeakerHub background tasks as AWS ECS tasks."""

    def submit(self, task: BaseTaskDefinition) -> RunningTask:
        raise NotImplementedError("AWS ECS task submission is not implemented")

    def get_status(self, task_id: str) -> TaskStatus:
        raise NotImplementedError("AWS ECS task status polling is not implemented")

    def delete(self, task_id: str) -> None:
        raise NotImplementedError("AWS ECS task deletion is not implemented")
