"""Tests for task-runner delegation to runtime processes."""

import pytest

from beakerhub.runtimes.base import (
    BaseDefinition,
    BaseProcess,
    BaseRuntime,
    ProcessOutput,
    ProcessStatus,
)
from beakerhub.services.task.base import BaseTaskRunnerService, TaskOutput, TaskStatus


class CompleteProcess(BaseProcess):
    def describe(self) -> ProcessStatus:
        return ProcessStatus("completed")

    def collect_output(self) -> ProcessOutput:
        return ProcessOutput("output", "")

    def stop(self) -> None:
        return None


class PendingProcess(CompleteProcess):
    def describe(self) -> ProcessStatus:
        return ProcessStatus("running")


class ProcessTaskRunner(BaseTaskRunnerService):
    def __init__(self, process: BaseProcess, **kwargs):
        self.process = process
        super().__init__(**kwargs)

    def get_process(self, external_id: str) -> BaseProcess:
        assert external_id == self.process.external_id
        return self.process


def complete_process() -> CompleteProcess:
    return CompleteProcess(
        BaseDefinition(),
        runtime=BaseRuntime(),
        external_id="runtime-123",
    )


def test_task_status_and_output_are_runtime_contract_aliases():
    assert TaskStatus is ProcessStatus
    assert TaskOutput is ProcessOutput


def test_task_runner_delegates_persisted_identifier_to_process():
    process = complete_process()
    runner = ProcessTaskRunner(process)

    assert runner.get_status("runtime-123") == ProcessStatus("completed")
    assert runner.get_output("runtime-123") == ProcessOutput("output", "")


@pytest.mark.asyncio
async def test_process_returns_terminal_status():
    process = complete_process()

    assert await process.await_completion() == ProcessStatus("completed")


@pytest.mark.asyncio
async def test_process_raises_on_timeout():
    process = PendingProcess(
        BaseDefinition(),
        runtime=BaseRuntime(),
        external_id="runtime-123",
    )

    with pytest.raises(TimeoutError, match="runtime-123"):
        await process.await_completion(timeout=0)
