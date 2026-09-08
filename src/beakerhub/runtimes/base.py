"""Provider-neutral runtime workload contracts and composition helpers."""

import asyncio
import uuid
from dataclasses import dataclass
from time import monotonic
from typing import Any, Literal, TypeAlias

from traitlets import Dict, Instance, List, Type, Unicode, default
from traitlets.config import LoggingConfigurable


ProcessState: TypeAlias = Literal["pending", "running", "completed", "failed"]
ProcessType: TypeAlias = Literal["task", "service"]


@dataclass(frozen=True)
class ProcessStatus:
    """The runtime's current view of a launched process."""

    state: ProcessState
    message: str | None = None
    exit_code: int | None = None

    @property
    def done(self) -> bool:
        """Return true when the process has reached a terminal state."""
        return self.state in {"completed", "failed"}


@dataclass(frozen=True)
class ProcessOutput:
    """Captured standard streams for a process."""

    stdout: str
    stderr: str


class BaseRuntime(LoggingConfigurable):
    """Own a provider connection and provider-wide runtime defaults."""


class BaseDefinition(LoggingConfigurable):
    """Provider-neutral description of an OCI workload.

    A definition describes the workload to launch, not its runtime identity or
    lifecycle. Its unset provider fields resolve from ``runtime``. Provider
    definitions may add scheduling and launch fields.
    """

    runtime = Instance(BaseRuntime, allow_none=True)
    image = Unicode(default_value=None, config=True)
    entrypoint = List(Unicode(), default_value=[], config=True)
    command = List(Unicode(), default_value=[], config=True)
    working_directory = Unicode(allow_none=True, default_value=None, config=True)
    environment = Dict(Unicode(), Unicode(), default_value={}, config=True)
    labels = Dict(Unicode(), Unicode(), default_value={}, config=True)


    def __init__(self, **kwargs: Any) -> None:
        runtime = kwargs.get("runtime")
        parent = kwargs.get("parent")
        if runtime is None and isinstance(parent, BaseRuntime):
            kwargs["runtime"] = parent
        elif runtime is not None and parent is None:
            kwargs["parent"] = runtime
        elif runtime is not None and parent is not runtime:
            raise ValueError("A definition's parent and runtime must be the same")
        super().__init__(**kwargs)


class BaseProcess(LoggingConfigurable):
    """A launched provider workload with an external lifecycle identifier."""

    runtime = Instance(BaseRuntime, allow_none=False)

    def __init__(
        self,
        definition: BaseDefinition,
        *,
        external_id: str | None = None,
        process_type: ProcessType = "task",
        **kwargs: Any,
    ) -> None:
        runtime = kwargs.get("runtime")
        parent = kwargs.get("parent")
        if runtime is None and isinstance(parent, BaseRuntime):
            kwargs["runtime"] = parent
        elif runtime is not None and parent is None:
            kwargs["parent"] = runtime
        elif runtime is not None and parent is not runtime:
            raise ValueError("A process's parent and runtime must be the same")

        self.id = kwargs.pop("id", uuid.uuid4().hex)
        self.process_type = process_type
        self.external_id = external_id
        self.definition = definition
        super().__init__(**kwargs)
        if definition.runtime is None:
            definition.runtime = self.runtime
        elif definition.runtime is not self.runtime:
            raise ValueError("A process and its definition must use the same runtime")
        if definition.parent is None:
            definition.parent = self.runtime
        elif definition.parent is not self.runtime:
            raise ValueError("A definition's parent and runtime must be the same")

    @classmethod
    def start(
        cls,
        definition: BaseDefinition,
        *,
        process_type: ProcessType = "task",
        **kwargs: Any,
    ) -> "BaseProcess":
        """Launch a process for ``definition`` and return its runtime handle."""
        raise NotImplementedError

    def describe(self) -> ProcessStatus:
        """Return the latest provider status for this process."""
        raise NotImplementedError

    @property
    def status(self) -> ProcessStatus:
        """Return the latest provider status for this process."""
        return self.describe()

    def collect_output(self) -> ProcessOutput | None:
        """Return available process output, if the provider retains it."""
        raise NotImplementedError

    def stop(self) -> None:
        """Request that the provider stop this process."""
        raise NotImplementedError

    async def await_completion(self, timeout: float | None = 600) -> ProcessStatus:
        """Wait for this process to reach a terminal state."""
        started_at = monotonic()
        while True:
            status = self.status
            if status.done:
                return status
            if timeout is not None and monotonic() - started_at >= timeout:
                raise TimeoutError(
                    f"Process {self.external_id or self.id!r} did not complete within "
                    f"{timeout} seconds"
                )
            await asyncio.sleep(0.2)


class BaseRuntimeBundle(LoggingConfigurable):
    """Compose compatible runtime, definition, and process implementations."""

    runtime_class = Type(klass=BaseRuntime, default_value=BaseRuntime, config=True)
    process_class = Type(klass=BaseProcess, default_value=BaseProcess, config=True)
    definition_class = Type(
        klass=BaseDefinition,
        default_value=BaseDefinition,
        config=True,
    )
    # Services
    default_dashboard_class = Type(
        klass="beakerhub.services.dashboard.base.BaseDashboardService",
        default_value="beakerhub.services.dashboard.base.BaseDashboardService",
        config=True
    )
    default_spawner_class = Type(
        klass="beakerhub.services.spawner.base.BeakerhubImageSpawner",
        default_value="beakerhub.services.spawner.base.BeakerhubImageSpawner",
        config=True
    )
    default_task_runner_class = Type(
        klass="beakerhub.services.task.base.BaseTaskRunnerService",
        default_value="beakerhub.services.task.base.BaseTaskRunnerService",
        config=True
    )

    @property
    def runtime(self):
        """Resolve and return the runtime from the parent if defined."""
        if self.parent is not None:
            return getattr(self.parent, "runtime", None)

    def create_definition(
        self,
        *,
        runtime: BaseRuntime | None = None,
        **kwargs: Any,
    ) -> BaseDefinition:
        """Create a definition using this bundle's provider implementation."""
        runtime = runtime or self.runtime
        if runtime is not None:
            if not isinstance(runtime, self.runtime_class):
                raise TypeError(
                    f"{self.__class__.__name__} requires "
                    f"{self.runtime_class.__name__}, not {type(runtime).__name__}"
                )
            kwargs["runtime"] = runtime
        return self.definition_class(**kwargs)

    def start_process(
        self,
        definition: BaseDefinition,
        *,
        runtime: BaseRuntime | None = None,
        process_type: ProcessType = "task",
        **kwargs: Any,
    ) -> BaseProcess:
        """Launch a provider process using the application-owned runtime."""
        runtime = runtime or self.runtime
        if not isinstance(definition, self.definition_class):
            raise TypeError(
                f"{self.__class__.__name__} requires "
                f"{self.definition_class.__name__}, not {type(definition).__name__}"
            )
        if not isinstance(runtime, self.runtime_class):
            raise TypeError(
                f"{self.__class__.__name__} requires "
                f"{self.runtime_class.__name__}, not {type(runtime).__name__}"
            )
        return self.process_class.start(
            definition,
            process_type=process_type,
            runtime=runtime,
            parent=runtime,
            **kwargs,
        )
