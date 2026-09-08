"""Tests for the Kubernetes task-runner runtime adapter."""

from types import SimpleNamespace
from unittest.mock import Mock

from beakerhub.runtimes.kubernetes import KubernetesRuntime
from beakerhub.services.task.kubernetes_task_runner import KubernetesTaskRunnerService
from beakerhub.tasks.image_import.task import ImageImportTask


def runtime(**overrides):
    values = {
        "namespace": "runtime-namespace",
        "node_selector": {"pool": "runtime"},
        "tolerations": [{"key": "runtime", "operator": "Exists"}],
    }
    values.update(overrides)
    instance = KubernetesRuntime(**values)
    instance.batch_api = Mock()
    instance.core_api = Mock()
    return instance


def image_import_task():
    return ImageImportTask.from_node_image(
        SimpleNamespace(default_img_string="registry.example/node:latest")
    )


def test_submit_uses_the_shared_runtime_defaults():
    shared_runtime = runtime()
    runner = KubernetesTaskRunnerService(runtime=shared_runtime)

    process = runner.submit(image_import_task())

    request = shared_runtime.batch_api.create_namespaced_job.call_args.kwargs
    pod_spec = request["body"].spec.template.spec
    assert process.runtime is shared_runtime
    assert request["namespace"] == "runtime-namespace"
    assert pod_spec.node_selector == {"pool": "runtime"}
    assert pod_spec.tolerations[0].key == "runtime"
    assert request["body"].metadata.labels["beakerhub/task-type"] == "context_import"


def test_runner_configuration_overrides_runtime_defaults_and_reconstructs_processes():
    shared_runtime = runtime()
    runner = KubernetesTaskRunnerService(
        runtime=shared_runtime,
        namespace="task-namespace",
        node_selector={"pool": "tasks"},
        tolerations=[{"key": "tasks", "operator": "Exists"}],
    )

    runner.submit(image_import_task())
    submitted = shared_runtime.batch_api.create_namespaced_job.call_args.kwargs["body"]
    restored = runner.get_process("beaker-task-context-import-123")

    assert submitted.metadata.namespace == "task-namespace"
    assert submitted.spec.template.spec.node_selector == {"pool": "tasks"}
    assert submitted.spec.template.spec.tolerations[0].key == "tasks"
    assert restored.runtime is shared_runtime
    assert restored.definition.namespace == "task-namespace"
