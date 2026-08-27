"""Kubernetes implementation of the task-runner service."""

from typing import Any
from uuid import uuid4

from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from traitlets import Dict, Integer, List, Unicode

from beakerhub.services.task.base import (
    BaseTaskRunnerService,
    RunningTask,
    TaskOutput,
    TaskStatus,
)
from beakerhub.tasks.base import BaseImageTask, BaseTaskDefinition


class KubernetesTaskRunnerService(BaseTaskRunnerService):
    """Run BeakerHub background tasks as Kubernetes Jobs."""

    node_image_resources = Dict(
        config=True,
        help="Resource requests and limits for the node-image init container.",
    )
    backoff_limit = Integer(
        0,
        config=True,
        help="Number of retries before a task Job is marked as failed.",
    )
    active_deadline_seconds = Integer(
        300,
        config=True,
        help="Maximum time in seconds that a task Job can run.",
    )
    ttl_seconds_after_finished = Integer(
        600,
        config=True,
        help="Time in seconds to retain completed task Jobs.",
    )
    node_selector = Dict(config=True, help="Node selector for task Pods.")
    tolerations: Any = List(config=True, help="Tolerations for task Pods.")
    namespace = Unicode(
        "beakerhub",
        config=True,
        help="Kubernetes namespace for task Jobs.",
    )

    @staticmethod
    def _get_clients() -> tuple[k8s_client.BatchV1Api, k8s_client.CoreV1Api]:
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()
        return k8s_client.BatchV1Api(), k8s_client.CoreV1Api()

    def submit(self, task: BaseTaskDefinition) -> RunningTask:
        """Submit a supported task as a Kubernetes Job."""
        if not isinstance(task, BaseImageTask):
            raise ValueError(
                f"KubernetesTaskRunnerService only supports image tasks, not "
                f"{task.task_type!r}"
            )
        external_id = self._submit_image_task(task)
        return RunningTask(
            external_id=external_id,
            task_definition=task,
            runner=self,
        )

    def _submit_image_task(self, task: BaseImageTask) -> str:
        """Create a Job for a runtime-neutral image-task definition."""
        batch_api, _ = self._get_clients()
        task_name = task.task_type.replace("_", "-")
        job_name = f"beaker-task-{task_name}-{uuid4().hex[:8]}"
        container = k8s_client.V1Container(
            name="task",
            image=task.image,
            command=list(task.entrypoint) or None,
            args=list(task.command) or None,
            working_dir=task.working_directory,
            env=[
                k8s_client.V1EnvVar(name=name, value=value)
                for name, value in task.environment.items()
            ] or None,
            resources=self._build_resource_requirements(
                dict(task.resources) or self.node_image_resources
            ),
        )
        pod_spec = k8s_client.V1PodSpec(
            containers=[container],
            restart_policy="Never",
            node_selector=self.node_selector or None,
            tolerations=(
                [k8s_client.V1Toleration(**item) for item in self.tolerations]
                if self.tolerations
                else None
            ),
        )
        job = k8s_client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=k8s_client.V1ObjectMeta(
                name=job_name,
                namespace=self.namespace,
                labels={
                    "app.kubernetes.io/name": "beakerhub",
                    "app.kubernetes.io/component": "task",
                    "beakerhub/task-type": task.task_type,
                },
            ),
            spec=k8s_client.V1JobSpec(
                template=k8s_client.V1PodTemplateSpec(
                    metadata=k8s_client.V1ObjectMeta(
                        labels={
                            "app.kubernetes.io/name": "beakerhub",
                            "app.kubernetes.io/component": "task",
                        }
                    ),
                    spec=pod_spec,
                ),
                backoff_limit=self.backoff_limit,
                active_deadline_seconds=self.active_deadline_seconds,
                ttl_seconds_after_finished=self.ttl_seconds_after_finished,
            ),
        )

        batch_api.create_namespaced_job(namespace=self.namespace, body=job)
        self.log.info(
            "Created task job %s for task type %s", job_name, task.task_type
        )
        return job_name

    def get_status(self, task_id: str) -> TaskStatus:
        """Query the status of a Kubernetes Job."""
        batch_api, core_api = self._get_clients()
        try:
            job = batch_api.read_namespaced_job(
                name=task_id,
                namespace=self.namespace,
            )
        except k8s_client.ApiException as error:
            if error.status == 404:
                return TaskStatus("failed", f"Job {task_id} not found")
            raise

        status = job.status
        if status.succeeded and status.succeeded > 0:
            return TaskStatus("completed", "Job completed successfully")
        if status.failed and status.failed > 0:
            return TaskStatus("failed", self._get_failure_message(core_api, task_id))
        if status.active and status.active > 0:
            return TaskStatus("running", "Job is running")
        return TaskStatus("pending", "Job is pending")

    def get_output(self, task_id: str) -> TaskOutput | None:
        """Return the task container log after its Job reaches a terminal state."""
        _, core_api = self._get_clients()
        pods = core_api.list_namespaced_pod(
            namespace=self.namespace,
            label_selector=f"job-name={task_id}",
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
        # Kubernetes exposes a combined container log stream through this API.
        return TaskOutput(stdout=logs or "", stderr="")

    def _get_failure_message(
        self,
        core_api: k8s_client.CoreV1Api,
        job_name: str,
    ) -> str:
        try:
            pods = core_api.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f"job-name={job_name}",
            )
        except k8s_client.ApiException:
            return "Job failed (could not retrieve pod details)"

        if not pods.items:
            return "Job failed (no pods found)"
        pod = pods.items[0]
        for status in pod.status.init_container_statuses or []:
            message = self._container_failure_message(status, "Init container")
            if message:
                return message
        for status in pod.status.container_statuses or []:
            message = self._container_failure_message(status, "Container")
            if message:
                return message
        phase = pod.status.phase or "Unknown"
        reason = pod.status.reason or ""
        return f"Job failed (pod phase: {phase}). {reason}".strip()

    @staticmethod
    def _container_failure_message(status, label: str) -> str | None:
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

    def delete(self, task_id: str) -> None:
        """Delete a Job and its associated Pods."""
        batch_api, _ = self._get_clients()
        try:
            batch_api.delete_namespaced_job(
                name=task_id,
                namespace=self.namespace,
                body=k8s_client.V1DeleteOptions(propagation_policy="Background"),
            )
        except k8s_client.ApiException as error:
            if error.status != 404:
                raise

    @staticmethod
    def _build_resource_requirements(
        resources: dict,
    ) -> k8s_client.V1ResourceRequirements | None:
        if not resources:
            return None
        return k8s_client.V1ResourceRequirements(
            requests=resources.get("requests"),
            limits=resources.get("limits"),
        )
