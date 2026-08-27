"""Base contracts for background task-runner services."""

import asyncio
from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING, Literal

from traitlets.config import LoggingConfigurable

if TYPE_CHECKING:
    from beakerhub.tasks.base import BaseTaskDefinition


TaskState = Literal["pending", "running", "completed", "failed"]


@dataclass(frozen=True)
class TaskStatus:
    """The runner's current view of a submitted task."""

    state: TaskState
    message: str | None = None

    @property
    def done(self) -> bool:
        """Return true when the task has reached a terminal state."""
        return self.state in {"completed", "failed"}


@dataclass(frozen=True)
class TaskOutput:
    """Captured standard streams for a completed task."""

    stdout: str
    stderr: str


@dataclass(frozen=True)
class RunningTask:
    """An in-memory handle for a task submitted to a runner."""

    external_id: str
    task_definition: "BaseTaskDefinition"
    runner: "BaseTaskRunnerService"

    @property
    def status(self) -> TaskStatus:
        """Return the current status from the runner."""
        return self.runner.get_status(self.external_id)

    @property
    def done(self) -> bool:
        """Return true when the runner reports a terminal state."""
        return self.status.done

    @property
    def output(self) -> TaskOutput | None:
        """Return captured output after the runner reports task completion."""
        return self.runner.get_output(self.external_id)

    async def await_completion(self, timeout: float | None = 600) -> TaskStatus:
        """Wait for terminal status, or raise ``TimeoutError``."""
        started_at = monotonic()
        while True:
            status = self.status
            if status.done:
                return status
            if timeout is not None and monotonic() - started_at >= timeout:
                raise TimeoutError(
                    f"Task {self.external_id!r} did not complete within {timeout} seconds"
                )
            await asyncio.sleep(0.2)


class BaseTaskRunnerService(LoggingConfigurable):
    """Submit and manage background workloads for BeakerHub tasks."""

    def submit(self, task: "BaseTaskDefinition") -> RunningTask:
        """Submit a task and return its in-memory runtime handle."""
        raise NotImplementedError

    def get_status(self, external_id: str) -> TaskStatus:
        """Return the current state and diagnostics for a submitted task."""
        raise NotImplementedError

    def get_output(self, external_id: str) -> TaskOutput | None:
        """Return output for a terminal task, if the backend retains it."""
        raise NotImplementedError

    def delete(self, external_id: str) -> None:
        """Remove a known submitted workload during normal task completion."""
        raise NotImplementedError

    def reap_stale_tasks(self) -> None:
        """Find and clean backend workloads orphaned from normal completion."""
        raise NotImplementedError
