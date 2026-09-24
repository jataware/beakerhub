"""Tests for provider-neutral runtime contracts."""

from traitlets import Unicode

from beakerhub.runtimes.base import (
    BaseDefinition,
    BaseProcess,
    BaseRuntime,
    BaseRuntimeBundle,
    ProcessStatus,
)


class ExampleDefinition(BaseDefinition):
    value = Unicode("example", config=True)


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

    # default_dashboard_class =
    # default_spawner_class =
    # default_task_runner_class =

def test_bundle_creates_definition_and_process_with_application_runtime():
    bundle = ExampleBundle()
    runtime = ExampleRuntime()

    definition = bundle.create_definition(runtime=runtime, value="configured")
    process = bundle.start_process(definition, runtime=runtime)

    assert isinstance(definition, ExampleDefinition)
    assert definition.value == "configured"
    assert definition.parent is runtime
    assert definition.runtime is runtime
    assert isinstance(process.runtime, ExampleRuntime)
    assert process.parent is runtime
    assert process.runtime is runtime
    assert process.external_id == "example-process"
    assert process.status == ProcessStatus("running")


def test_process_status_marks_only_terminal_states_done():
    assert ProcessStatus("pending").done is False
    assert ProcessStatus("running").done is False
    assert ProcessStatus("completed").done is True
    assert ProcessStatus("failed").done is True


def test_process_status_retains_an_optional_exit_code():
    assert ProcessStatus("failed", exit_code=23).exit_code == 23
