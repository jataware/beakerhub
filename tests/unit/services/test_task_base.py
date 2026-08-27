"""Tests for task-runner lifecycle value objects."""

from dataclasses import dataclass

import pytest

from beakerhub.services.task.base import (
    BaseTaskRunnerService,
    RunningTask,
    TaskOutput,
    TaskStatus,
)
from beakerhub.tasks.base import BaseTaskDefinition


@dataclass(frozen=True)
class ExampleTask(BaseTaskDefinition):
    @property
    def task_type(self) -> str:
        return "example"


class CompleteTaskRunner(BaseTaskRunnerService):
    def get_status(self, external_id: str) -> TaskStatus:
        return TaskStatus("completed")

    def get_output(self, external_id: str) -> TaskOutput:
        return TaskOutput("output", "")


def test_running_task_uses_its_external_id_for_runner_operations():
    runner = CompleteTaskRunner()
    task = RunningTask("runtime-123", ExampleTask(), runner)

    assert task.status == TaskStatus("completed")
    assert task.done is True
    assert task.output == TaskOutput("output", "")


@pytest.mark.asyncio
async def test_running_task_returns_terminal_status():
    runner = CompleteTaskRunner()
    task = RunningTask("runtime-123", ExampleTask(), runner)

    assert await task.await_completion() == TaskStatus("completed")


@pytest.mark.asyncio
async def test_running_task_raises_on_timeout():
    class PendingTaskRunner(CompleteTaskRunner):
        def get_status(self, external_id: str) -> TaskStatus:
            return TaskStatus("running")

    task = RunningTask("runtime-123", ExampleTask(), PendingTaskRunner())

    with pytest.raises(TimeoutError, match="runtime-123"):
        await task.await_completion(timeout=0)
