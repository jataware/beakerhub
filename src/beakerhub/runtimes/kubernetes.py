"""Kubernetes runtime workloads.

This module owns Kubernetes Job mechanics shared by finite container workloads.
KubeSpawner remains responsible for JupyterHub session Pod construction and
proxy readiness until it is explicitly adapted to this runtime layer.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import uuid4

from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from traitlets import Dict, Instance, List, Unicode
import traitlets

from beakerhub.runtimes.base import (
    BaseDefinition,
    BaseProcess,
    BaseRuntime,
    BaseRuntimeBundle,
    ProcessOutput,
    ProcessStatus,
    ProcessType,
)


class KubernetesRuntime(BaseRuntime):
    """Shared Kubernetes clients and namespace defaults."""

    namespace = Unicode(
        "beakerhub",
        config=True,
        help="Kubernetes namespace for runtime workloads.",
    )
    node_selector: dict[str, str] = Dict(
        Unicode(),
        Unicode(),
        default_value={},
        config=True,
        help="Default node selector for runtime workloads.",
    )
    tolerations: list[dict[str, Any]] = List(
        Dict(),
        default_value=[],
        config=True,
        help="Default tolerations for runtime workloads.",
    )
    service_account: str = Unicode(
        "",
        config=True,
        help="Default service account for runtime workload Pods.",
    )
    base_labels: dict[str, str] = Dict(
        Unicode(),
        Unicode(),
        default_value={},
        config=True,
        help="Labels applied to every runtime workload.",
    )

    @staticmethod
    def get_clients() -> tuple[k8s_client.BatchV1Api, k8s_client.CoreV1Api]:
        """Load Kubernetes configuration and create the required API clients."""
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()
        return k8s_client.BatchV1Api(), k8s_client.CoreV1Api()

    @staticmethod
    def build_resource_requirements(
        resources: Mapping[str, Any],
    ) -> k8s_client.V1ResourceRequirements | None:
        """Convert request/limit mappings to Kubernetes resource requirements."""
        if not resources:
            return None
        return k8s_client.V1ResourceRequirements(
            requests=resources.get("requests"),
            limits=resources.get("limits"),
        )

    @staticmethod
    def container_failure_message(status: Any, label: str) -> str | None:
        """Return a useful message for a failed or waiting container."""
        if status.state and status.state.waiting:
            reason = status.state.waiting.reason or "Unknown"
            message = status.state.waiting.message or ""
            return f"{label} '{status.name}' waiting: {reason}. {message}".strip()
        if (
            status.state
            and status.state.terminated
            and status.state.terminated.exit_code != 0
        ):
            reason = status.state.terminated.reason or "Error"
            message = status.state.terminated.message or ""
            return (
                f"{label} '{status.name}' failed ({reason}, exit code "
                f"{status.state.terminated.exit_code}). {message}"
            ).strip()
        return None


@dataclass(frozen=True, kw_only=True)
class KubernetesDefinition(BaseDefinition):
    """A Kubernetes Job workload definition."""

    namespace: str | None = None
    resources: Mapping[str, Any] = field(default_factory=dict)
    node_selector: Mapping[str, str] | None = None
    tolerations: tuple[Mapping[str, Any], ...] | None = None
    service_account: str | None = None
    backoff_limit: int = 0
    active_deadline_seconds: int | None = 300
    ttl_seconds_after_finished: int | None = 600
    name_prefix: str = "beaker-process"


class KubernetesProcess(BaseProcess):
    """A Kubernetes Job-backed process."""

    runtime = Instance(KubernetesRuntime, allow_none=False)

    def __init__(self, definition: KubernetesDefinition, **kwargs: Any) -> None:
        super().__init__(definition, **kwargs)

    @property
    def _definition(self) -> KubernetesDefinition:
        if not isinstance(self.definition, KubernetesDefinition):
            raise TypeError("KubernetesProcess requires a KubernetesDefinition")
        return self.definition

    @property
    def namespace(self) -> str:
        return self._definition.namespace or self.runtime.namespace

    @property
    def node_selector(self) -> Mapping[str, str]:
        if self._definition.node_selector is not None:
            return self._definition.node_selector
        return self.runtime.node_selector

    @property
    def tolerations(self) -> tuple[Mapping[str, Any], ...] | list[dict[str, Any]]:
        if self._definition.tolerations is not None:
            return self._definition.tolerations
        return self.runtime.tolerations

    @property
    def service_account(self) -> str:
        if self._definition.service_account is not None:
            return self._definition.service_account
        return self.runtime.service_account

    @classmethod
    def start(
        cls,
        definition: KubernetesDefinition,
        *,
        process_type: ProcessType = "task",
        **kwargs: Any,
    ) -> "KubernetesProcess":
        """Create a Kubernetes Job and return its process handle."""
        if process_type != "task":
            raise NotImplementedError(
                "KubernetesProcess currently launches run-to-completion Jobs only"
            )
        self = cls(definition, process_type=process_type, **kwargs)
        self.external_id = self._job_name()
        batch_api, _ = self.runtime.get_clients()
        batch_api.create_namespaced_job(namespace=self.namespace, body=self._job())
        self.log.info("Created Kubernetes Job %s", self.external_id)
        return self

    def _job_name(self) -> str:
        prefix = self._definition.name_prefix.rstrip("-") or "beaker-process"
        return f"{prefix}-{uuid4().hex[:8]}"

    def _job(self) -> k8s_client.V1Job:
        definition = self._definition
        labels = {
            **self.runtime.base_labels,
            **definition.labels,
            "app.kubernetes.io/name": "beakerhub",
            "app.kubernetes.io/component": "task",
            "beakerhub/process-type": self.process_type,
        }
        container = k8s_client.V1Container(
            name="task",
            image=definition.image,
            command=list(definition.entrypoint) or None,
            args=list(definition.command) or None,
            working_dir=definition.working_directory,
            env=[
                k8s_client.V1EnvVar(name=name, value=value)
                for name, value in definition.environment.items()
            ]
            or None,
            resources=self.runtime.build_resource_requirements(definition.resources),
        )
        pod_spec = k8s_client.V1PodSpec(
            containers=[container],
            restart_policy="Never",
            node_selector=dict(self.node_selector) or None,
            tolerations=(
                [k8s_client.V1Toleration(**item) for item in self.tolerations]
                if self.tolerations
                else None
            ),
            service_account_name=self.service_account or None,
        )
        return k8s_client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=k8s_client.V1ObjectMeta(
                name=self.external_id,
                namespace=self.namespace,
                labels=labels,
            ),
            spec=k8s_client.V1JobSpec(
                template=k8s_client.V1PodTemplateSpec(
                    metadata=k8s_client.V1ObjectMeta(labels=labels),
                    spec=pod_spec,
                ),
                backoff_limit=definition.backoff_limit,
                active_deadline_seconds=definition.active_deadline_seconds,
                ttl_seconds_after_finished=definition.ttl_seconds_after_finished,
            ),
        )

    def describe(self) -> ProcessStatus:
        """Return normalized lifecycle status for this Kubernetes Job."""
        if not self.external_id:
            return ProcessStatus("pending", "Kubernetes Job has not been submitted")
        batch_api, core_api = self.runtime.get_clients()
        try:
            job = batch_api.read_namespaced_job(
                name=self.external_id,
                namespace=self.namespace,
            )
        except k8s_client.ApiException as error:
            if error.status == 404:
                return ProcessStatus("failed", f"Job {self.external_id} not found")
            raise

        status = job.status
        if status.succeeded and status.succeeded > 0:
            return ProcessStatus("completed", "Job completed successfully")
        if status.failed and status.failed > 0:
            return ProcessStatus(
                "failed",
                self._failure_message(core_api),
            )
        if status.active and status.active > 0:
            return ProcessStatus("running", "Job is running")
        return ProcessStatus("pending", "Job is pending")

    def _failure_message(self, core_api: k8s_client.CoreV1Api) -> str:
        try:
            pods = core_api.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f"job-name={self.external_id}",
            )
        except k8s_client.ApiException:
            return "Job failed (could not retrieve pod details)"
        if not pods.items:
            return "Job failed (no pods found)"
        pod = pods.items[0]
        for status in pod.status.init_container_statuses or []:
            message = self.runtime.container_failure_message(status, "Init container")
            if message:
                return message
        for status in pod.status.container_statuses or []:
            message = self.runtime.container_failure_message(status, "Container")
            if message:
                return message
        phase = pod.status.phase or "Unknown"
        reason = pod.status.reason or ""
        return f"Job failed (pod phase: {phase}). {reason}".strip()

    def collect_output(self) -> ProcessOutput | None:
        """Return the combined Kubernetes container log for this Job."""
        if not self.external_id:
            return None
        _, core_api = self.runtime.get_clients()
        pods = core_api.list_namespaced_pod(
            namespace=self.namespace,
            label_selector=f"job-name={self.external_id}",
        )
        if not pods.items:
            return None
        response = core_api.read_namespaced_pod_log(
            name=pods.items[0].metadata.name,
            namespace=self.namespace,
            container="task",
            _preload_content=False,
        )
        logs = response.data.decode("utf-8")
        return ProcessOutput(stdout=logs or "", stderr="")

    def stop(self) -> None:
        """Delete this Kubernetes Job and its associated Pods."""
        if not self.external_id:
            return
        batch_api, _ = self.runtime.get_clients()
        try:
            batch_api.delete_namespaced_job(
                name=self.external_id,
                namespace=self.namespace,
                body=k8s_client.V1DeleteOptions(propagation_policy="Background"),
            )
        except k8s_client.ApiException as error:
            if error.status != 404:
                raise


class KubernetesRuntimeBundle(BaseRuntimeBundle):
    """Composition bundle for Kubernetes Job workloads."""

    runtime_class = traitlets.Type(
        klass=KubernetesRuntime,
        default_value=KubernetesRuntime,
        config=True,
    )
    process_class = traitlets.Type(
        klass=KubernetesProcess,
        default_value=KubernetesProcess,
        config=True,
    )
    definition_class = traitlets.Type(
        klass=KubernetesDefinition,
        default_value=KubernetesDefinition,
        config=True,
    )


# KubeSpawner owns session Pod creation, state, and proxy readiness today. A
# future session adapter can share KubernetesRuntime client/configuration logic
# without making Kubernetes Jobs imitate JupyterHub server semantics.
