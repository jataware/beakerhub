"""Task-runner adapters for persisted BeakerHub background tasks."""

from typing import TYPE_CHECKING, TypeAlias

from beakerhub.runtimes.base import (
    BaseProcess,
    ProcessOutput,
    ProcessState,
    ProcessStatus,
)
from traitlets.config import LoggingConfigurable

if TYPE_CHECKING:
    from beakerhub.tasks.base import BaseTaskDefinition


# Keep task-service imports stable while using the runtime lifecycle contract.
TaskState: TypeAlias = ProcessState
TaskStatus = ProcessStatus
TaskOutput = ProcessOutput


class BaseTaskRunnerService(LoggingConfigurable):
    """Adapt logical BeakerHub tasks to provider runtime processes.

    Persisted tasks retain only an external provider identifier. Provider-specific
    subclasses reconstruct a process handle from that identifier when the task
    service later polls status, reads output, or requests cleanup.
    """

    def submit(self, task: "BaseTaskDefinition") -> BaseProcess:
        """Launch a runtime process for a logical task."""
        raise NotImplementedError

    def get_process(self, external_id: str) -> BaseProcess:
        """Reconstruct a process handle for a persisted external identifier."""
        raise NotImplementedError

    def get_status(self, external_id: str) -> ProcessStatus:
        """Return the current status of a persisted runtime process."""
        return self.get_process(external_id).status

    def get_output(self, external_id: str) -> ProcessOutput | None:
        """Return retained output for a persisted runtime process."""
        return self.get_process(external_id).collect_output()

    def delete(self, external_id: str) -> None:
        """Request cleanup of a persisted runtime process."""
        self.get_process(external_id).stop()

    def reap_stale_tasks(self) -> None:
        """Find and clean backend workloads orphaned from normal completion."""
        raise NotImplementedError
