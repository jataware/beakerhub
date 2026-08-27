"""Runtime-neutral definitions for BeakerHub background tasks."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Mapping

from beakerhub.services.task.base import TaskOutput, TaskStatus

if TYPE_CHECKING:
    from beakerhub.orm import BeakerTask


class BaseTaskDefinition(ABC):
    """A logical task and its task-specific completion behavior.

    Definitions do not contain a runner's external identifier or lifecycle
    state. Those belong to the persisted task record and task runner.
    """

    @property
    @abstractmethod
    def task_type(self) -> str:
        """Return the stable type identifier for this task definition."""

    def on_before_start(self, task: "BeakerTask") -> None:
        """Run task-specific preparation after persistence and before submission."""

    def on_success(
        self,
        task: "BeakerTask",
        status: TaskStatus,
        output: TaskOutput,
    ) -> None:
        """Process captured output after successful completion."""

    def on_failure(
        self,
        task: "BeakerTask",
        status: TaskStatus,
        output: TaskOutput | None,
    ) -> None:
        """Process diagnostics after unsuccessful completion."""


@dataclass(frozen=True, kw_only=True)
class BaseImageTask(BaseTaskDefinition):
    """A task definition that executes a command in an OCI image."""

    image: str
    entrypoint: tuple[str, ...] = ()
    command: tuple[str, ...] = ()
    working_directory: str | None = None
    environment: Mapping[str, str] = field(default_factory=dict)
    resources: Mapping[str, str] = field(default_factory=dict)
