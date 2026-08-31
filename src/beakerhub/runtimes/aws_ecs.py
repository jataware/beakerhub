"""AWS ECS runtime workloads.

This module owns ECS control-plane mechanics. Task-runner and JupyterHub
spawner adapters should retain their respective persistence and lifecycle
policies while delegating provider operations to these classes.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

import boto3
import traitlets
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from beakerhub.runtimes.base import (
    BaseDefinition,
    BaseProcess,
    BaseRuntime,
    BaseRuntimeBundle,
    ProcessOutput,
    ProcessStatus,
    ProcessType,
)


class AwsEcsRuntime(BaseRuntime):
    """Shared ECS and CloudWatch clients for ECS-backed workloads."""

    ecs_client: BaseClient = traitlets.Instance(klass=BaseClient, config=False)
    logs_client: BaseClient = traitlets.Instance(klass=BaseClient, config=False)
    aws_region: str = traitlets.Unicode(
        help="AWS Region in which the ECS cluster resides.",
        config=True,
    )

    @traitlets.default("ecs_client")
    def _default_ecs_client(self) -> BaseClient:
        return boto3.client("ecs", region_name=self.aws_region or None)

    @traitlets.default("logs_client")
    def _default_logs_client(self) -> BaseClient:
        return boto3.client("logs", region_name=self.aws_region or None)

    @traitlets.default("aws_region")
    def _default_aws_region(self) -> str:
        session = boto3._get_default_session()
        return (session.region_name if session else None) or "us-east-1"

    # These provider-wide values are copied into a process only when that
    # process does not receive an explicit override. This keeps one runtime
    # bundle from repeating the same deployment configuration per service.
    log_group: str = traitlets.Unicode(
        default_value="",
        help="Default CloudWatch Logs group for ECS containers.",
        config=True,
    )
    log_stream_prefix: str = traitlets.Unicode(
        default_value="beakerhub-task",
        help="Default CloudWatch Logs stream prefix for ECS containers.",
        config=True,
    )
    execution_role_arn: str = traitlets.Unicode(
        default_value="",
        help="Default IAM execution role for dynamically registered definitions.",
        config=True,
    )
    task_role_arn: str = traitlets.Unicode(
        default_value="",
        help="Default IAM role for dynamically registered task containers.",
        config=True,
    )
    subnets: list[str] = traitlets.List(
        traitlets.Unicode(),
        default_value=[],
        help="Default subnets for Fargate awsvpc workloads.",
        config=True,
    )
    security_groups: list[str] = traitlets.List(
        traitlets.Unicode(),
        default_value=[],
        help="Default security groups for Fargate awsvpc workloads.",
        config=True,
    )
    assign_public_ip: bool = traitlets.Bool(
        False,
        help="Default public-IP assignment for Fargate workloads.",
        config=True,
    )
    cpu_architecture: Literal["X86_64", "ARM64"] = traitlets.Enum(
        values=["X86_64", "ARM64"],
        default_value="X86_64",
        help="Default CPU architecture for dynamically registered definitions.",
        config=True,
    )
    task_definition_name: str = traitlets.Unicode(
        default_value="beakerhub-tasks",
        help="Default family for dynamically registered ECS task definitions.",
        config=True,
    )
    cluster_name: str = traitlets.Unicode(
        help="Default ECS cluster name or ARN.",
        config=True,
    )
    task_group: str = traitlets.Unicode(
        help="Default ECS task group.",
        config=True,
    )
    launch_type: Literal["EC2", "FARGATE", "EXTERNAL", "MANAGED_INSTANCES"] = (
        traitlets.Enum(
            values=["EC2", "FARGATE", "EXTERNAL", "MANAGED_INSTANCES"],
            default_value="FARGATE",
            help="Default ECS launch type.",
            config=True,
        )
    )
    launch_options: dict[str, Any] = traitlets.Dict(
        default_value={},
        help="Default ECS run_task options.",
        config=True,
    )
    task_overrides: dict[str, Any] | None = traitlets.Dict(
        default_value=None,
        allow_none=True,
        help="Default ECS task overrides.",
        config=True,
    )
    default_task_cpu: str = traitlets.Unicode(
        default_value="4 vcpu",
        help="Default CPU for dynamically registered task definitions.",
        config=True,
    )
    default_task_memory: str = traitlets.Unicode(
        default_value="16GB",
        help="Default memory for dynamically registered task definitions.",
        config=True,
    )
    default_task_ephemeral_storage: int = traitlets.Int(
        default_value=50,
        help="Default ephemeral storage in GiB for Fargate definitions.",
        config=True,
    )

    def run_task(self, request: dict[str, Any]) -> str:
        """Run one ECS task and return its ARN."""
        try:
            response = self.ecs_client.run_task(**request)
        except ClientError as error:
            raise RuntimeError(f"ECS failed to run task: {error}") from error
        tasks = response.get("tasks", [])
        if not tasks:
            raise RuntimeError(f"ECS did not start a task: {response.get('failures', [])!r}")
        return tasks[0]["taskArn"]

    def describe_task(self, cluster_name: str, external_id: str) -> dict[str, Any] | None:
        """Return an ECS task description, or ``None`` when it no longer exists."""
        try:
            response = self.ecs_client.describe_tasks(
                cluster=cluster_name,
                tasks=[external_id],
            )
        except ClientError as error:
            raise RuntimeError(f"ECS failed to describe task {external_id}: {error}") from error
        tasks = response.get("tasks", [])
        return tasks[0] if tasks else None

    def stop_task(self, cluster_name: str, external_id: str, reason: str) -> None:
        """Request that ECS stop a task."""
        try:
            self.ecs_client.stop_task(
                cluster=cluster_name,
                task=external_id,
                reason=reason,
            )
        except ClientError as error:
            raise RuntimeError(f"ECS failed to stop task {external_id}: {error}") from error

    @staticmethod
    def awsvpc_network_configuration(
        subnets: list[str],
        security_groups: list[str],
        assign_public_ip: bool,
    ) -> dict[str, Any]:
        """Build an ECS awsvpc network configuration."""
        return {
            "awsvpcConfiguration": {
                "subnets": list(subnets),
                "securityGroups": list(security_groups),
                "assignPublicIp": "ENABLED" if assign_public_ip else "DISABLED",
            }
        }

    def get_log_events(
        self,
        log_group: str,
        stream_name: str,
    ) -> list[str]:
        """Read all currently retained events from a CloudWatch log stream."""
        messages: list[str] = []
        next_token: str | None = None
        while True:
            request: dict[str, Any] = {
                "logGroupName": log_group,
                "logStreamName": stream_name,
                "startFromHead": True,
            }
            if next_token:
                request["nextToken"] = next_token
            try:
                response = self.logs_client.get_log_events(**request)
            except ClientError as error:
                raise RuntimeError(
                    f"CloudWatch failed to get output from {stream_name}: {error}"
                ) from error
            messages.extend(event["message"] for event in response.get("events", []))
            token = response.get("nextForwardToken")
            if not token or token == next_token:
                return messages
            next_token = token


@dataclass(frozen=True, kw_only=True)
class AwsEcsDefinition(BaseDefinition):
    """An ECS workload definition.

    Set ``task_definition`` for a deployment-managed ECS definition, as session
    spawners normally do. Without it, :class:`AwsEcsProcess` registers a
    definition from the image fields before launch, as task runners need.
    """

    task_definition: str | None = None
    container_name: str = "task-container"
    cpu: str | None = None
    memory: str | None = None
    ephemeral_storage: int | None = None
    tags: Mapping[str, str] = field(default_factory=dict)


class AwsEcsProcess(BaseProcess):
    """A single launched ECS workload."""

    runtime = traitlets.Instance(AwsEcsRuntime, allow_none=False)

    # Process traits remain configurable as service-specific overrides. Their
    # defaults are resolved from the runtime after its configuration is loaded.
    log_group: str = traitlets.Unicode(config=True)
    log_stream_prefix: str = traitlets.Unicode(config=True)
    execution_role_arn: str = traitlets.Unicode(config=True)
    task_role_arn: str = traitlets.Unicode(config=True)
    subnets: list[str] = traitlets.List(traitlets.Unicode(), config=True)
    security_groups: list[str] = traitlets.List(traitlets.Unicode(), config=True)
    assign_public_ip: bool = traitlets.Bool(config=True)
    cpu_architecture: Literal["X86_64", "ARM64"] = traitlets.Enum(
        values=["X86_64", "ARM64"],
        config=True,
    )
    task_definition_name: str = traitlets.Unicode(config=True)
    cluster_name: str = traitlets.Unicode(config=True)
    task_group: str = traitlets.Unicode(config=True)
    launch_type: Literal["EC2", "FARGATE", "EXTERNAL", "MANAGED_INSTANCES"] = (
        traitlets.Enum(
            values=["EC2", "FARGATE", "EXTERNAL", "MANAGED_INSTANCES"],
            config=True,
        )
    )
    launch_options: dict[str, Any] = traitlets.Dict(config=True)
    task_overrides: dict[str, Any] | None = traitlets.Dict(
        allow_none=True,
        config=True,
    )
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

    @classmethod
    def start(
        cls,
        definition: AwsEcsDefinition,
        *,
        process_type: ProcessType = "task",
        **kwargs: Any,
    ) -> "AwsEcsProcess":
        """Launch an ECS workload from a fixed or dynamically registered definition."""
        self = cls(definition, process_type=process_type, **kwargs)
        self._validate_configuration()
        task_definition = definition.task_definition or self._register_task_definition()
        external_id = self.runtime.run_task(self._run_task_request(task_definition))
        self.external_id = external_id
        return self

    def _run_task_request(self, task_definition: str) -> dict[str, Any]:
        definition = self._definition
        request: dict[str, Any] = {
            "cluster": self.cluster_name,
            "taskDefinition": task_definition,
            "overrides": self._build_overrides(),
            "tags": self._tags(),
        }
        if self.task_group:
            request["group"] = self.task_group
        if self.launch_type == "FARGATE" and "networkConfiguration" not in self.launch_options:
            request["networkConfiguration"] = self.runtime.awsvpc_network_configuration(
                self.subnets,
                self.security_groups,
                self.assign_public_ip,
            )
        if "capacityProviderStrategy" not in self.launch_options:
            request["launchType"] = self.launch_type
        request.update(self.launch_options)
        return request

    @property
    def _definition(self) -> AwsEcsDefinition:
        if not isinstance(self.definition, AwsEcsDefinition):
            raise TypeError("AwsEcsProcess requires an AwsEcsDefinition")
        return self.definition

    def _tags(self) -> list[dict[str, str]]:
        tags = dict(self._definition.tags)
        tags.setdefault("beakerhub-process", "true")
        tags.setdefault("beakerhub-process-type", self.process_type)
        return [{"key": key, "value": value} for key, value in tags.items()]

    def _register_task_definition(self) -> str:
        definition = self._definition
        if not definition.image:
            raise ValueError("AwsEcsDefinition.image is required without task_definition")
        container: dict[str, Any] = {
            "name": definition.container_name,
            "image": definition.image,
            "essential": True,
        }
        if definition.entrypoint:
            container["entryPoint"] = list(definition.entrypoint)
        if definition.command:
            container["command"] = list(definition.command)
        if definition.working_directory:
            container["workingDirectory"] = definition.working_directory
        if definition.environment:
            container["environment"] = [
                {"name": name, "value": value}
                for name, value in definition.environment.items()
            ]
        if self.log_group:
            container["logConfiguration"] = {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": self.log_group,
                    "awslogs-region": self.runtime.aws_region,
                    "awslogs-stream-prefix": self.log_stream_prefix,
                },
            }

        request: dict[str, Any] = {
            "family": self.task_definition_name,
            "containerDefinitions": [container],
            "cpu": definition.cpu or self.runtime.default_task_cpu,
            "memory": definition.memory or self.runtime.default_task_memory,
            "runtimePlatform": {
                "cpuArchitecture": self.cpu_architecture,
                "operatingSystemFamily": "LINUX",
            },
        }
        if self.launch_type == "FARGATE":
            request.update(
                {
                    "ephemeralStorage": {
                        "sizeInGiB": self._ephemeral_storage
                    },
                    "networkMode": "awsvpc",
                    "requiresCompatibilities": ["FARGATE"],
                }
            )
        if self.execution_role_arn:
            request["executionRoleArn"] = self.execution_role_arn
        if self.task_role_arn:
            request["taskRoleArn"] = self.task_role_arn

        try:
            response = self.runtime.ecs_client.register_task_definition(**request)
        except ClientError as error:
            raise RuntimeError(f"ECS failed to register task definition: {error}") from error
        return response["taskDefinition"]["taskDefinitionArn"]

    def _build_overrides(self) -> dict[str, Any]:
        overrides = dict(self.task_overrides or {})
        containers: list[dict[str, Any]] = []
        task_container: dict[str, Any] = {"name": self._definition.container_name}
        environment: dict[str, str] = {}
        for container in overrides.pop("containerOverrides", []):
            container = dict(container)
            if container.get("name") != self._definition.container_name:
                containers.append(container)
                continue
            environment.update(
                {item["name"]: item["value"] for item in container.pop("environment", [])}
            )
            task_container.update(container)
        environment.update(self._definition.environment)
        if environment:
            task_container["environment"] = [
                {"name": name, "value": value} for name, value in environment.items()
            ]
        containers.append(task_container)
        overrides["containerOverrides"] = containers
        return overrides

    def _validate_configuration(self) -> None:
        if not self.cluster_name.strip():
            raise ValueError("AwsEcsProcess.cluster_name must be configured")
        if self.launch_type == "FARGATE":
            network_configuration = self.launch_options.get("networkConfiguration")
            subnets = (
                network_configuration.get("awsvpcConfiguration", {}).get("subnets", [])
                if network_configuration
                else self.subnets
            )
            if not subnets:
                raise ValueError("AwsEcsProcess.subnets must be configured for Fargate workloads")
        elif self._ephemeral_storage and not self._definition.task_definition:
            raise ValueError(
                "ephemeral_storage is supported only for Fargate workloads"
            )
        if (
            self.launch_type == "MANAGED_INSTANCES"
            and not self.launch_options.get("capacityProviderStrategy")
        ):
            raise ValueError(
                "Managed Instances workloads require launch_options.capacityProviderStrategy"
            )

    @property
    def _ephemeral_storage(self) -> int:
        value = self._definition.ephemeral_storage
        return value if value is not None else self.runtime.default_task_ephemeral_storage

    def describe(self) -> ProcessStatus:
        """Return normalized lifecycle status for this ECS workload."""
        if not self.external_id:
            return ProcessStatus("pending", "ECS task has not been submitted")
        task = self.runtime.describe_task(self.cluster_name, self.external_id)
        if task is None:
            return ProcessStatus("failed", f"ECS task {self.external_id} was not found")
        status = task.get("lastStatus", "UNKNOWN")
        if status in {"PROVISIONING", "PENDING", "ACTIVATING"}:
            return ProcessStatus("pending", f"ECS task is {status.lower()}")
        if status in {"RUNNING", "DEACTIVATING", "DEPROVISIONING", "STOPPING"}:
            return ProcessStatus("running", f"ECS task is {status.lower()}")
        if status != "STOPPED":
            return ProcessStatus("failed", f"ECS task has unexpected status {status!r}")

        container = self._task_container(task)
        if container and container.get("exitCode") == 0:
            return ProcessStatus("completed", "ECS task completed successfully")
        reason = (
            (container or {}).get("reason")
            or task.get("stoppedReason")
            or "Unknown failure"
        )
        return ProcessStatus("failed", f"ECS task failed ({reason})")

    def collect_output(self) -> ProcessOutput | None:
        """Return retained CloudWatch output for this ECS workload."""
        if not self.log_group or not self.external_id:
            return None
        task = self.runtime.describe_task(self.cluster_name, self.external_id)
        if task is None:
            return None
        container = self._task_container(task)
        task_id = self.external_id.rsplit("/", maxsplit=1)[-1]
        container_name = (container or {}).get("name", self._definition.container_name)
        stream_name = f"{self.log_stream_prefix}/{container_name}/{task_id}"
        return ProcessOutput(
            stdout="\n".join(self.runtime.get_log_events(self.log_group, stream_name)),
            stderr="",
        )

    def stop(self) -> None:
        """Request normal cleanup of this ECS workload."""
        if not self.external_id:
            return
        self.runtime.stop_task(
            self.cluster_name,
            self.external_id,
            f"Stopped BeakerHub {self.process_type} cleanup",
        )

    def _task_container(self, task: dict[str, Any]) -> dict[str, Any] | None:
        return next(
            (
                item
                for item in task.get("containers", [])
                if item.get("name") == self._definition.container_name
            ),
            None,
        )


class AwsEcsRuntimeBundle(BaseRuntimeBundle):
    """Composition bundle for ECS workloads."""

    runtime_class = traitlets.Type(
        klass=AwsEcsRuntime,
        default_value=AwsEcsRuntime,
        config=True,
    )
    process_class = traitlets.Type(
        klass=AwsEcsProcess,
        default_value=AwsEcsProcess,
        config=True,
    )
    definition_class = traitlets.Type(
        klass=AwsEcsDefinition,
        default_value=AwsEcsDefinition,
        config=True,
    )


# Task persistence/completion handling and JupyterHub proxy/session behavior
# deliberately remain in their respective service adapters.
