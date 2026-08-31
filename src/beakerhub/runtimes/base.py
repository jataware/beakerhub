"""Provider-neutral runtime workload contracts and composition helpers."""

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from traitlets import Instance, Type, default
from traitlets.config import LoggingConfigurable


ProcessState = Literal["pending", "running", "completed", "failed"]
ProcessType = Literal["task", "service"]


@dataclass(frozen=True)
class ProcessStatus:
    """The runtime's current view of a launched process."""

    state: ProcessState
    message: str | None = None

    @property
    def done(self) -> bool:
        """Return true when the process has reached a terminal state."""
        return self.state in {"completed", "failed"}


@dataclass(frozen=True)
class ProcessOutput:
    """Captured standard streams for a process."""

    stdout: str
    stderr: str


@dataclass(frozen=True, kw_only=True)
class BaseDefinition:
    """Provider-neutral description of an OCI workload.

    A definition describes the workload to launch, not its runtime identity or
    lifecycle. Provider definitions may add scheduling and launch fields.
    """

    image: str | None = None
    entrypoint: tuple[str, ...] = ()
    command: tuple[str, ...] = ()
    working_directory: str | None = None
    environment: Mapping[str, str] = field(default_factory=dict)
    labels: Mapping[str, str] = field(default_factory=dict)


class BaseRuntime(LoggingConfigurable):
    """Own a provider connection and provider-wide runtime defaults."""


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
        self.id = kwargs.pop("id", uuid.uuid4().hex)
        self.process_type = process_type
        self.external_id = external_id
        self.definition = definition
        super().__init__(**kwargs)

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


class BaseRuntimeBundle(LoggingConfigurable):
    """Compose compatible runtime, definition, and process implementations."""

    runtime_class = Type(klass=BaseRuntime, default_value=BaseRuntime, config=True)
    process_class = Type(klass=BaseProcess, default_value=BaseProcess, config=True)
    definition_class = Type(
        klass=BaseDefinition,
        default_value=BaseDefinition,
        config=True,
    )
    runtime = Instance(BaseRuntime, allow_none=False)

    @default("runtime")
    def _default_runtime(self) -> BaseRuntime:
        return self.runtime_class(parent=self)

    def create_definition(self, **kwargs: Any) -> BaseDefinition:
        """Create a definition using this bundle's provider implementation."""
        return self.definition_class(**kwargs)

    def start_process(
        self,
        definition: BaseDefinition,
        *,
        process_type: ProcessType = "task",
        **kwargs: Any,
    ) -> BaseProcess:
        """Launch a provider process using this bundle's shared runtime."""
        if not isinstance(definition, self.definition_class):
            raise TypeError(
                f"{self.__class__.__name__} requires "
                f"{self.definition_class.__name__}, not {type(definition).__name__}"
            )
        return self.process_class.start(
            definition,
            process_type=process_type,
            runtime=self.runtime,
            parent=self,
            **kwargs,
        )
