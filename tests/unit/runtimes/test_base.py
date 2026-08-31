"""Tests for provider-neutral runtime contracts."""

from dataclasses import dataclass

from beakerhub.runtimes.base import (
    BaseDefinition,
    BaseProcess,
    BaseRuntime,
    BaseRuntimeBundle,
    ProcessStatus,
)


@dataclass(frozen=True, kw_only=True)
class ExampleDefinition(BaseDefinition):
    value: str = "example"


class ExampleRuntime(BaseRuntime):
    pass


class ExampleProcess(BaseProcess):
    @classmethod
    def start(cls, definition, **kwargs):
        return cls(definition, external_id="example-process", **kwargs)

    def describe(self):
        return ProcessStatus("running")

    def collect_output(self):
        return None

    def stop(self):
        return None


class ExampleBundle(BaseRuntimeBundle):
    runtime_class = ExampleRuntime
    process_class = ExampleProcess
    definition_class = ExampleDefinition


def test_bundle_creates_definition_and_process_with_shared_runtime():
    bundle = ExampleBundle()

    definition = bundle.create_definition(value="configured")
    process = bundle.start_process(definition)

    assert isinstance(definition, ExampleDefinition)
    assert definition.value == "configured"
    assert isinstance(process.runtime, ExampleRuntime)
    assert process.runtime is bundle.runtime
    assert process.external_id == "example-process"
    assert process.status == ProcessStatus("running")


def test_process_status_marks_only_terminal_states_done():
    assert ProcessStatus("pending").done is False
    assert ProcessStatus("running").done is False
    assert ProcessStatus("completed").done is True
    assert ProcessStatus("failed").done is True
