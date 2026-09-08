"""Kubernetes Job implementation of the task-runner service."""

from typing import Any

from traitlets import Dict, Instance, Integer, List, Unicode, default

from beakerhub.runtimes.kubernetes import (
    KubernetesDefinition,
    KubernetesProcess,
    KubernetesRuntime,
)
from beakerhub.services.task.base import BaseTaskRunnerService
from beakerhub.tasks.base import BaseImageTask, BaseTaskDefinition


class KubernetesTaskRunnerService(BaseTaskRunnerService):
    """Adapt Kubernetes Job runtime processes to the task-runner contract."""

    node_image_resources = Dict(
        config=True,
        help="Resource requests and limits for the node-image task container.",
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
        config=True,
        help="Kubernetes namespace for task Jobs.",
    )
    runtime = Instance(KubernetesRuntime, allow_none=False)

    @default("runtime")
    def _default_runtime(self) -> KubernetesRuntime:
        parent_runtime = getattr(self.parent, "runtime", None)
        if isinstance(parent_runtime, KubernetesRuntime):
            return parent_runtime
        return KubernetesRuntime(
            parent=self,
            namespace=self._trait_values.get("namespace", "beakerhub"),
            node_selector=self._trait_values.get("node_selector", {}),
            tolerations=self._trait_values.get("tolerations", []),
        )

    @default("namespace")
    def _default_namespace(self) -> str:
        return self.runtime.namespace

    @default("node_selector")
    def _default_node_selector(self) -> dict[str, str]:
        return dict(self.runtime.node_selector)

    @default("tolerations")
    def _default_tolerations(self) -> list[dict[str, Any]]:
        return list(self.runtime.tolerations)

    def submit(self, task: BaseTaskDefinition) -> KubernetesProcess:
        """Submit a supported task as a Kubernetes Job."""
        if not isinstance(task, BaseImageTask):
            raise ValueError(
                "KubernetesTaskRunnerService only supports image tasks, not "
                f"{task.task_type!r}"
            )
        task_definition = KubernetesDefinition(
            runtime=self.runtime,
            namespace=self.namespace,
            image=task.image,
            entrypoint=tuple(task.entrypoint),
            command=tuple(task.command),
            working_directory=task.working_directory,
            environment=task.environment,
            resources=dict(task.resources) or self.node_image_resources,
            node_selector=dict(self.node_selector),
            tolerations=list(self.tolerations),
            labels={"beakerhub/task-type": task.task_type},
            backoff_limit=self.backoff_limit,
            active_deadline_seconds=self.active_deadline_seconds,
            ttl_seconds_after_finished=self.ttl_seconds_after_finished,
            name_prefix=f"beaker-task-{task.task_type.replace('_', '-')}",
        )
        return KubernetesProcess.start(task_definition, runtime=self.runtime)

    def get_process(self, external_id: str) -> KubernetesProcess:
        """Reconstruct a Job process using the task runner's namespace."""
        return KubernetesProcess(
            KubernetesDefinition(runtime=self.runtime, namespace=self.namespace),
            runtime=self.runtime,
            external_id=external_id,
        )
