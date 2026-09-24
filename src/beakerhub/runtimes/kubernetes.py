"""Kubernetes runtime workloads.

This module owns Kubernetes Job mechanics shared by finite container workloads.
KubeSpawner remains responsible for JupyterHub session Pod construction and
proxy readiness until it is explicitly adapted to this runtime layer.
"""

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

    batch_api: k8s_client.BatchV1Api
    core_api: k8s_client.CoreV1Api


    def __init__(self, **kwargs):
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()
        self.batch_api = k8s_client.BatchV1Api()
        self.core_api = k8s_client.CoreV1Api()
        super().__init__(**kwargs)

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


class KubernetesDefinition(BaseDefinition):
    """A Kubernetes Job workload definition."""

    runtime = Instance(KubernetesRuntime, allow_none=True)
    namespace = Unicode(config=True)
    resources = Dict(default_value={}, config=True)
    node_selector = Dict(Unicode(), Unicode(), config=True)
    tolerations = List(Dict(), config=True)
    service_account = Unicode(config=True)
    backoff_limit = traitlets.Int(0, config=True)
    active_deadline_seconds = traitlets.Int(300, allow_none=True, config=True)
    ttl_seconds_after_finished = traitlets.Int(600, allow_none=True, config=True)
    name_prefix = Unicode("beaker-process", config=True)

    @traitlets.default("namespace")
    def _default_namespace(self) -> str:
        return self.runtime.namespace

    @traitlets.default("node_selector")
    def _default_node_selector(self) -> dict[str, str]:
        return dict(self.runtime.node_selector)

    @traitlets.default("tolerations")
    def _default_tolerations(self) -> list[dict[str, Any]]:
        return list(self.runtime.tolerations)

    @traitlets.default("service_account")
    def _default_service_account(self) -> str:
        return self.runtime.service_account


class KubernetesProcess(BaseProcess):
    """A Kubernetes Job-backed process."""

    definition: KubernetesDefinition
    runtime = Instance(KubernetesRuntime, allow_none=False)

    def __init__(self, definition: KubernetesDefinition, **kwargs: Any) -> None:
        if not isinstance(definition, KubernetesDefinition):
            raise TypeError("KubernetesProcess requires a KubernetesDefinition")
        super().__init__(definition, **kwargs)

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
        self.runtime.batch_api.create_namespaced_job(
            namespace=self.definition.namespace,
            body=self._job(),
        )
        self.log.info("Created Kubernetes Job %s", self.external_id)
        return self

    def _job_name(self) -> str:
        prefix = self.definition.name_prefix.rstrip("-") or "beaker-process"
        return f"{prefix}-{uuid4().hex[:8]}"

    def _job(self) -> k8s_client.V1Job:
        definition = self.definition
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
            node_selector=dict(definition.node_selector) or None,
            tolerations=(
                [k8s_client.V1Toleration(**item) for item in definition.tolerations]
                if definition.tolerations
                else None
            ),
            service_account_name=definition.service_account or None,
        )
        return k8s_client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=k8s_client.V1ObjectMeta(
                name=self.external_id,
                namespace=definition.namespace,
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
        try:
            job = self.runtime.batch_api.read_namespaced_job(
                name=self.external_id,
                namespace=self.definition.namespace,
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
                self._failure_message(self.runtime.core_api),
            )
        if status.active and status.active > 0:
            return ProcessStatus("running", "Job is running")
        return ProcessStatus("pending", "Job is pending")

    def _failure_message(self, core_api: k8s_client.CoreV1Api) -> str:
        try:
            pods = core_api.list_namespaced_pod(
                namespace=self.definition.namespace,
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
        pods = self.runtime.core_api.list_namespaced_pod(
            namespace=self.definition.namespace,
            label_selector=f"job-name={self.external_id}",
        )
        if not pods.items:
            return None
        response = self.runtime.core_api.read_namespaced_pod_log(
            name=pods.items[0].metadata.name,
            namespace=self.definition.namespace,
            container="task",
            _preload_content=False,
        )
        logs = response.data.decode("utf-8")
        return ProcessOutput(stdout=logs or "", stderr="")

    def stop(self) -> None:
        """Delete this Kubernetes Job and its associated Pods."""
        if not self.external_id:
            return
        try:
            self.runtime.batch_api.delete_namespaced_job(
                name=self.external_id,
                namespace=self.definition.namespace,
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

    default_dashboard_class = traitlets.Type(
        klass="beakerhub.services.dashboard.kubernetes_dashboard.KubernetesDashboardService",
        default_value="beakerhub.services.dashboard.kubernetes_dashboard.KubernetesDashboardService",
        config=True
    )
    default_spawner_class = traitlets.Type(
        klass="beakerhub.services.spawner.kubernetes_spawner.BeakerKubeSpawner",
        default_value="beakerhub.services.spawner.kubernetes_spawner.BeakerKubeSpawner",
        config=True
    )
    default_task_runner_class = traitlets.Type(
        klass="beakerhub.services.task.kubernetes_task_runner.KubernetesTaskRunnerService",
        default_value="beakerhub.services.task.kubernetes_task_runner.KubernetesTaskRunnerService",
        config=True
    )



# KubeSpawner owns session Pod creation, state, and proxy readiness today. A
# future session adapter can share KubernetesRuntime client/configuration logic
# without making Kubernetes Jobs imitate JupyterHub server semantics.
