"""Tests for the Kubernetes dashboard service."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from kubernetes import config as k8s_config
from traitlets.config import LoggingConfigurable

from beakerhub.runtimes.kubernetes import KubernetesRuntime
from beakerhub.services.dashboard.base import DashboardServiceError
from beakerhub.services.dashboard.kubernetes_dashboard import KubernetesDashboardService


def make_service(monkeypatch):
    monkeypatch.setattr(k8s_config, "load_incluster_config", lambda: None)
    runtime = KubernetesRuntime()
    runtime.core_api = MagicMock()
    runtime.batch_api = MagicMock()
    parent = LoggingConfigurable()
    parent.runtime = runtime
    return KubernetesDashboardService(parent=parent, namespace="test"), runtime


def test_dashboard_uses_runtime_clients(monkeypatch):
    service, runtime = make_service(monkeypatch)
    empty = SimpleNamespace(items=[])
    runtime.core_api.list_namespaced_pod.return_value = empty
    runtime.core_api.list_namespaced_persistent_volume_claim.return_value = empty
    runtime.core_api.list_namespaced_event.return_value = empty
    runtime.core_api.list_node.return_value = empty
    runtime.core_api.list_pod_for_all_namespaces.return_value = empty
    runtime.batch_api.list_namespaced_job.return_value = empty

    result = service.get_dashboard()

    assert result["available"] is True
    assert result["runtime"] == {"provider": "Kubernetes", "scope": "test"}
    assert result["summary"][0]["value"] == 0
    runtime.core_api.list_namespaced_pod.assert_called_once_with(namespace="test")
    runtime.batch_api.list_namespaced_job.assert_called_once_with(
        namespace="test", label_selector="app.kubernetes.io/name=beakerhub"
    )


def test_session_logs_use_runtime_core_client(monkeypatch):
    service, runtime = make_service(monkeypatch)
    pod = SimpleNamespace(metadata=SimpleNamespace(name="session-pod"))
    runtime.core_api.list_namespaced_pod.return_value = SimpleNamespace(items=[pod])
    runtime.core_api.read_namespaced_pod_log.return_value = "hello"

    result = service.get_session_logs("server", "notebook", 100)

    assert result["logs"] == "hello"
    assert result["pod_name"] == "session-pod"
    runtime.core_api.list_namespaced_pod.assert_called_once_with(
        namespace="test", label_selector="hub.jupyter.org/servername=server"
    )
    runtime.core_api.read_namespaced_pod_log.assert_called_once_with(
        name="session-pod", namespace="test", container="notebook", tail_lines=100
    )


def test_missing_kubernetes_config(monkeypatch):
    service = KubernetesDashboardService()

    def missing_config():
        raise k8s_config.ConfigException("missing")

    monkeypatch.setattr(k8s_config, "load_incluster_config", missing_config)
    monkeypatch.setattr(k8s_config, "load_kube_config", missing_config)

    assert service.get_dashboard() == {
        "available": False, "error": "No K8s configuration found"
    }
    with pytest.raises(DashboardServiceError) as error:
        service.get_session_logs("server", "notebook", 100)
    assert error.value.status_code == 503
