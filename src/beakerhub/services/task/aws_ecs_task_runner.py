"""AWS ECS implementation of the task-runner service."""

from typing import Any, Literal

import traitlets

from beakerhub.runtimes.aws_ecs import AwsEcsDefinition, AwsEcsProcess, AwsEcsRuntime
from beakerhub.services.task.base import BaseTaskRunnerService
from beakerhub.tasks.base import BaseImageTask, BaseTaskDefinition


class AwsEcsTaskRunnerService(BaseTaskRunnerService):
    """Adapt image tasks to ECS runtime processes."""

    runtime = traitlets.Instance(AwsEcsRuntime, allow_none=False)

    log_group = traitlets.Unicode(config=True)
    log_stream_prefix = traitlets.Unicode(config=True)
    execution_role_arn = traitlets.Unicode(config=True)
    task_role_arn = traitlets.Unicode(config=True)
    subnets = traitlets.List(traitlets.Unicode(), config=True)
    security_groups = traitlets.List(traitlets.Unicode(), config=True)
    assign_public_ip = traitlets.Bool(config=True)
    cpu_architecture: Literal["X86_64", "ARM64"] = traitlets.Enum(
        ["X86_64", "ARM64"], config=True
    )
    task_definition_name = traitlets.Unicode(config=True)
    cluster_name = traitlets.Unicode(config=True)
    task_group = traitlets.Unicode(config=True)
    launch_type: Literal["EC2", "FARGATE", "EXTERNAL", "MANAGED_INSTANCES"] = (
        traitlets.Enum(
            ["EC2", "FARGATE", "EXTERNAL", "MANAGED_INSTANCES"], config=True
        )
    )
    launch_options = traitlets.Dict(config=True)
    task_overrides = traitlets.Dict(default_value=None, allow_none=True, config=True)
    default_task_cpu = traitlets.Unicode(config=True)
    default_task_memory = traitlets.Unicode(config=True)
    default_task_ephemeral_storage = traitlets.Int(config=True)

    @traitlets.default("runtime")
    def _default_runtime(self) -> AwsEcsRuntime:
        parent_runtime = getattr(self.parent, "runtime", None)
        if isinstance(parent_runtime, AwsEcsRuntime):
            return parent_runtime
        return AwsEcsRuntime(parent=self)

    @traitlets.default("log_group")
    def _default_log_group(self) -> str:
        return self.runtime.log_group

    @traitlets.default("log_stream_prefix")
    def _default_log_stream_prefix(self) -> str:
        return self.runtime.log_stream_prefix

    @traitlets.default("execution_role_arn")
    def _default_execution_role_arn(self) -> str:
        return self.runtime.execution_role_arn

    @traitlets.default("task_role_arn")
    def _default_task_role_arn(self) -> str:
        return self.runtime.task_role_arn

    @traitlets.default("subnets")
    def _default_subnets(self) -> list[str]:
        return list(self.runtime.subnets)

    @traitlets.default("security_groups")
    def _default_security_groups(self) -> list[str]:
        return list(self.runtime.security_groups)

    @traitlets.default("assign_public_ip")
    def _default_assign_public_ip(self) -> bool:
        return self.runtime.assign_public_ip

    @traitlets.default("cpu_architecture")
    def _default_cpu_architecture(self) -> Literal["X86_64", "ARM64"]:
        return self.runtime.cpu_architecture

    @traitlets.default("task_definition_name")
    def _default_task_definition_name(self) -> str:
        return self.runtime.task_definition_name

    @traitlets.default("cluster_name")
    def _default_cluster_name(self) -> str:
        return self.runtime.cluster_name

    @traitlets.default("task_group")
    def _default_task_group(self) -> str:
        return self.runtime.task_group

    @traitlets.default("launch_type")
    def _default_launch_type(
        self,
    ) -> Literal["EC2", "FARGATE", "EXTERNAL", "MANAGED_INSTANCES"]:
        return self.runtime.launch_type

    @traitlets.default("launch_options")
    def _default_launch_options(self) -> dict[str, Any]:
        return dict(self.runtime.launch_options)

    @traitlets.default("task_overrides")
    def _default_task_overrides(self) -> dict[str, Any] | None:
        return (
            dict(self.runtime.task_overrides)
            if self.runtime.task_overrides is not None
            else None
        )

    @traitlets.default("default_task_cpu")
    def _default_task_cpu(self) -> str:
        return self.runtime.default_task_cpu

    @traitlets.default("default_task_memory")
    def _default_task_memory(self) -> str:
        return self.runtime.default_task_memory

    @traitlets.default("default_task_ephemeral_storage")
    def _default_task_ephemeral_storage(self) -> int:
        return self.runtime.default_task_ephemeral_storage

    def submit(self, task: BaseTaskDefinition) -> AwsEcsProcess:
        """Create an ECS definition and launch one image task."""
        if not isinstance(task, BaseImageTask):
            raise ValueError(
                "AwsEcsTaskRunnerService only supports image tasks, not "
                f"{task.task_type!r}"
            )
        return AwsEcsProcess.start(self._definition(task), runtime=self.runtime)

    def _definition(self, task: BaseImageTask | None = None) -> AwsEcsDefinition:
        """Translate task and service overrides to an ECS runtime definition."""
        return AwsEcsDefinition(
            runtime=self.runtime,
            image=task.image if task else "",
            entrypoint=list(task.entrypoint) if task else [],
            command=list(task.command) if task else [],
            working_directory=task.working_directory if task else None,
            environment=dict(task.environment) if task else {},
            tags={"beakerhub/task-type": task.task_type} if task else {},
            cpu=self.default_task_cpu,
            memory=self.default_task_memory,
            ephemeral_storage=self.default_task_ephemeral_storage,
            log_group=self.log_group,
            log_stream_prefix=self.log_stream_prefix,
            execution_role_arn=self.execution_role_arn,
            task_role_arn=self.task_role_arn,
            subnets=list(self.subnets),
            security_groups=list(self.security_groups),
            assign_public_ip=self.assign_public_ip,
            cpu_architecture=self.cpu_architecture,
            task_definition_name=self.task_definition_name,
            cluster_name=self.cluster_name,
            task_group=self.task_group,
            launch_type=self.launch_type,
            launch_options=dict(self.launch_options),
            task_overrides=(
                dict(self.task_overrides) if self.task_overrides is not None else None
            ),
        )

    def get_process(self, external_id: str) -> AwsEcsProcess:
        """Reconstruct an ECS process from its persisted task ARN."""
        return AwsEcsProcess(
            self._definition(),
            runtime=self.runtime,
            external_id=external_id,
        )
