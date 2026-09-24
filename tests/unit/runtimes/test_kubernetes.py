"""Tests for Kubernetes runtime Job process construction."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from beakerhub.runtimes.kubernetes import (
    KubernetesDefinition,
    KubernetesProcess,
    KubernetesRuntime,
)


def runtime(**overrides):
    values = {
        "namespace": "runtime-namespace",
        "node_selector": {"pool": "compute"},
        "tolerations": [{"key": "dedicated", "operator": "Exists"}],
        "service_account": "runtime-workload",
        "base_labels": {"environment": "test"},
    }
    values.update(overrides)
    return KubernetesRuntime(**values)


def test_job_inherits_runtime_pod_defaults_and_base_labels():
    process = KubernetesProcess(
        KubernetesDefinition(image="example:latest"),
        runtime=runtime(),
        external_id="beaker-process-123",
    )

    job = process._job()
    pod_spec = job.spec.template.spec

    assert job.metadata.namespace == "runtime-namespace"
    assert job.metadata.labels["environment"] == "test"
    assert job.spec.template.metadata.labels["environment"] == "test"
    assert pod_spec.node_selector == {"pool": "compute"}
    assert pod_spec.tolerations[0].key == "dedicated"
    assert pod_spec.service_account_name == "runtime-workload"


def test_definition_can_override_or_disable_runtime_pod_defaults():
    process = KubernetesProcess(
        KubernetesDefinition(
            image="example:latest",
            namespace="definition-namespace",
            node_selector={},
            tolerations=(),
            service_account="",
            labels={"environment": "definition"},
        ),
        runtime=runtime(),
        external_id="beaker-process-123",
    )

    job = process._job()
    pod_spec = job.spec.template.spec

    assert job.metadata.namespace == "definition-namespace"
    assert job.metadata.labels["environment"] == "definition"
    assert pod_spec.node_selector is None
    assert pod_spec.tolerations is None
    assert pod_spec.service_account_name is None


def test_start_creates_job_and_records_the_provider_identifier(monkeypatch):
    batch_api = Mock()
    core_api = Mock()
    instance = runtime()
    instance.batch_api = batch_api
    instance.core_api = core_api

    process = KubernetesProcess.start(
        KubernetesDefinition(image="example:latest", name_prefix="image-import"),
        runtime=instance,
    )

    assert process.external_id.startswith("image-import-")
    request = batch_api.create_namespaced_job.call_args.kwargs
    assert request["namespace"] == "runtime-namespace"
    assert request["body"].metadata.name == process.external_id


def test_service_processes_are_not_mistaken_for_jobs():
    with pytest.raises(NotImplementedError, match="run-to-completion Jobs"):
        KubernetesProcess.start(
            KubernetesDefinition(image="example:latest"),
            runtime=runtime(),
            process_type="service",
        )


def test_describe_reports_job_completion(monkeypatch):
    batch_api = Mock()
    batch_api.read_namespaced_job.return_value = SimpleNamespace(
        status=SimpleNamespace(succeeded=1, failed=None, active=None)
    )
    instance = runtime()
    instance.batch_api = batch_api
    instance.core_api = Mock()
    process = KubernetesProcess(
        KubernetesDefinition(image="example:latest"),
        runtime=instance,
        external_id="beaker-process-123",
    )

    status = process.describe()

    assert status.state == "completed"
    assert status.message == "Job completed successfully"
