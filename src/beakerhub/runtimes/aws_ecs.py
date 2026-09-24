"""AWS ECS runtime workloads.

This module owns ECS control-plane mechanics. Task-runner and JupyterHub
spawner adapters should retain their respective persistence and lifecycle
policies while delegating provider operations to these classes.
"""

import hashlib
import re
from typing import Any, Literal

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

    def get_log_tail(
        self,
        log_group: str,
        stream_name: str,
        tail_lines: int,
    ) -> tuple[list[str], bool]:
        """Read recent events and report whether older events remain."""
        messages: list[str] = []
        next_token: str | None = None
        while True:
            request: dict[str, Any] = {
                "logGroupName": log_group,
                "logStreamName": stream_name,
                "startFromHead": False,
                "limit": min(10_000, tail_lines - len(messages)),
            }
            if next_token:
                request["nextToken"] = next_token
            try:
                response = self.logs_client.get_log_events(**request)
            except ClientError as error:
                raise RuntimeError(
                    f"CloudWatch failed to get output from {stream_name}: {error}"
                ) from error
            messages[0:0] = [
                event["message"] for event in response.get("events", [])
            ]
            token = response.get("nextBackwardToken")
            has_older_events = bool(token and token != next_token)
            if len(messages) >= tail_lines or not has_older_events:
                return messages[-tail_lines:], has_older_events
            next_token = token


class AwsEcsDefinition(BaseDefinition):
    """An ECS workload definition.

    Set ``task_definition_arn`` for a deployment-managed ECS definition, as session
    spawners normally do. Without it, :class:`AwsEcsProcess` registers a
    definition from the image fields before launch, as task runners need.
    """

    runtime = traitlets.Instance(AwsEcsRuntime, allow_none=True)
    task_definition_arn = traitlets.Unicode(allow_none=True, default_value=None, config=True)
    container_name = traitlets.Unicode("task-container", config=True)
    cpu = traitlets.Unicode(config=True)
    memory = traitlets.Unicode(config=True)
    ephemeral_storage = traitlets.Int(config=True)
    tags = traitlets.Dict(traitlets.Unicode(), traitlets.Unicode(), default_value={}, config=True)
    definition_tags = traitlets.Dict(
        traitlets.Unicode(), traitlets.Unicode(), default_value={}, config=True
    )
    log_group = traitlets.Unicode(config=True)
    log_stream_prefix = traitlets.Unicode(config=True)
    execution_role_arn = traitlets.Unicode(config=True)
    task_role_arn = traitlets.Unicode(config=True)
    subnets = traitlets.List(traitlets.Unicode(), config=True)
    security_groups = traitlets.List(traitlets.Unicode(), config=True)
    assign_public_ip = traitlets.Bool(config=True)
    cpu_architecture = traitlets.Enum(["X86_64", "ARM64"], config=True)
    task_definition_name = traitlets.Unicode(config=True)
    cluster_name = traitlets.Unicode(config=True)
    task_group = traitlets.Unicode(config=True)
    launch_type = traitlets.Enum(
        ["EC2", "FARGATE", "EXTERNAL", "MANAGED_INSTANCES"], config=True
    )
    launch_options = traitlets.Dict(config=True)
    task_overrides = traitlets.Dict(allow_none=True, config=True)
    volumes = traitlets.List(traitlets.Dict(), default_value=[], config=True)
    mount_points = traitlets.List(traitlets.Dict(), default_value=[], config=True)
    sidecar_containers = traitlets.List(traitlets.Dict(), default_value=[], config=True)

    @traitlets.default("cpu")
    def _default_cpu(self) -> str:
        return self.runtime.default_task_cpu

    @traitlets.default("memory")
    def _default_memory(self) -> str:
        return self.runtime.default_task_memory

    @traitlets.default("ephemeral_storage")
    def _default_ephemeral_storage(self) -> int:
        return self.runtime.default_task_ephemeral_storage

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
        base = re.sub(r"[^A-Za-z0-9_-]", "_", self.runtime.task_definition_name)
        image = self.image.rsplit("/", maxsplit=1)[-1]
        image_name = re.sub(r"[^A-Za-z0-9_-]", "_", image)
        image_hash = hashlib.sha256(self.image.encode()).hexdigest()[:12]
        base = base or "beakerhub"
        image_name = image_name or "image"
        max_base_length = 255 - len(image_hash) - 3
        base = base[:max_base_length]
        max_image_length = 255 - len(base) - len(image_hash) - 2
        image_name = image_name[:max_image_length]
        return f"{base}_{image_name}_{image_hash}"

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

    def validate_configuration(self) -> None:
        """Validate this definition's ECS launch configuration."""
        if not self.image:
            raise ValueError("AwsEcsDefinition.image must be configured")
        if not self.cluster_name.strip():
            raise ValueError("AwsEcsDefinition.cluster_name must be configured")
        if self.launch_type == "FARGATE":
            network_configuration = self.launch_options.get("networkConfiguration")
            subnets = (
                network_configuration.get("awsvpcConfiguration", {}).get("subnets", [])
                if network_configuration
                else self.subnets
            )
            if not subnets:
                raise ValueError(
                    "AwsEcsDefinition.subnets must be configured for Fargate workloads"
                )
        elif self.ephemeral_storage and not self.task_definition_arn:
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

    def find_or_register_task_definition(self) -> str:
        """Return an equivalent ECS task-definition ARN, registering it if needed."""
        if self.task_definition_arn:
            return self.task_definition_arn

        expected = self._normalize_task_definition(self.aws_task_definition)
        next_token: str | None = None
        while True:
            request: dict[str, Any] = {
                "familyPrefix": self.task_definition_name,
                "sort": "DESC",
            }
            if next_token:
                request["nextToken"] = next_token
            response = self.runtime.ecs_client.list_task_definitions(**request)
            for arn in response.get("taskDefinitionArns", []):
                described = self.runtime.ecs_client.describe_task_definition(
                    taskDefinition=arn
                )
                existing = described.get("taskDefinition", described)
                if self._normalize_task_definition(existing) == expected:
                    self.task_definition_arn = existing.get("taskDefinitionArn", arn)
                    return self.task_definition_arn
            next_token = response.get("nextToken")
            if not next_token:
                break

        try:
            response = self.runtime.ecs_client.register_task_definition(
                **self.aws_task_definition
            )
        except ClientError as error:
            raise RuntimeError(f"ECS failed to register task definition: {error}") from error
        self.task_definition_arn = response["taskDefinition"]["taskDefinitionArn"]
        return self.task_definition_arn

    @staticmethod
    def _normalize_task_definition(definition: dict[str, Any]) -> dict[str, Any]:
        """Remove ECS-generated fields and empty defaults before comparison."""
        generated_fields = {
            "taskDefinitionArn",
            "revision",
            "status",
            "requiresAttributes",
            "compatibilities",
            "registeredAt",
            "registeredBy",
            "deregisteredAt",
            "tags",
        }

        def normalize(value: Any) -> Any:
            if isinstance(value, dict):
                return {
                    key: normalized
                    for key, item in value.items()
                    if key not in generated_fields
                    and (normalized := normalize(item)) not in (None, [], {}, False)
                }
            if isinstance(value, list):
                return [normalize(item) for item in value]
            return value

        return normalize(definition)

    @property
    def aws_task_definition(self):
        container: dict[str, Any] = {
            "name": self.container_name,
            "image": self.image,
            "essential": True,
        }
        if self.entrypoint:
            container["entryPoint"] = list(self.entrypoint)
        if self.command:
            container["command"] = list(self.command)
        if self.working_directory:
            container["workingDirectory"] = self.working_directory
        if self.environment:
            container["environment"] = [
                {"name": name, "value": value}
                for name, value in self.environment.items()
            ]
        if self.mount_points:
            container["mountPoints"] = [dict(mount) for mount in self.mount_points]
        if self.sidecar_containers:
            container["dependsOn"] = [
                {"containerName": sidecar["name"], "condition": "SUCCESS"}
                for sidecar in self.sidecar_containers
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

        definition_dict: dict[str, Any] = {
            "family": self.task_definition_name,
            "containerDefinitions": [container, *self.sidecar_containers],
            "cpu": self.cpu,
            "memory": self.memory,
            "runtimePlatform": {
                "cpuArchitecture": self.cpu_architecture,
                "operatingSystemFamily": "LINUX",
            },
        }
        if self.volumes:
            definition_dict["volumes"] = [dict(volume) for volume in self.volumes]
        if self.launch_type == "FARGATE":
            definition_dict.update(
                {
                    "ephemeralStorage": {
                        "sizeInGiB": self.ephemeral_storage
                    },
                    "networkMode": "awsvpc",
                    "requiresCompatibilities": ["FARGATE"],
                }
            )
        if self.definition_tags:
            definition_dict["tags"] = [
                {"key": key, "value": value}
                for key, value in self.definition_tags.items()
            ]
        if self.execution_role_arn:
            definition_dict["executionRoleArn"] = self.execution_role_arn
        if self.task_role_arn:
            definition_dict["taskRoleArn"] = self.task_role_arn
        return definition_dict

class AwsEcsProcess(BaseProcess):
    """A single launched ECS workload."""

    definition: AwsEcsDefinition
    runtime = traitlets.Instance(AwsEcsRuntime, allow_none=False)

    def __init__(self, definition: AwsEcsDefinition, **kwargs: Any) -> None:
        if not isinstance(definition, AwsEcsDefinition):
            raise TypeError("AwsEcsProcess requires an AwsEcsDefinition")
        super().__init__(definition, **kwargs)

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
        definition.validate_configuration()
        task_definition_arn = definition.find_or_register_task_definition()
        external_id = self.runtime.run_task(
            self._run_task_request(task_definition_arn)
        )
        self.external_id = external_id
        return self

    def _run_task_request(self, task_definition_arn: str) -> dict[str, Any]:
        definition = self.definition
        tags = dict(definition.tags)
        tags.setdefault("beakerhub-process", "true")
        tags.setdefault("beakerhub-process-type", self.process_type)
        request: dict[str, Any] = {
            "cluster": definition.cluster_name,
            "taskDefinition": task_definition_arn,
            "overrides": self._build_overrides(),
            "tags": [{"key": key, "value": value} for key, value in tags.items()],
        }
        if definition.task_group:
            request["group"] = definition.task_group
        if (
            definition.launch_type == "FARGATE"
            and "networkConfiguration" not in definition.launch_options
        ):
            request["networkConfiguration"] = self.runtime.awsvpc_network_configuration(
                definition.subnets,
                definition.security_groups,
                definition.assign_public_ip,
            )
        if "capacityProviderStrategy" not in definition.launch_options:
            request["launchType"] = definition.launch_type
        request.update(definition.launch_options)
        return request

    def _build_overrides(self) -> dict[str, Any]:
        definition = self.definition
        overrides = dict(definition.task_overrides or {})
        containers: list[dict[str, Any]] = []
        task_container: dict[str, Any] = {"name": definition.container_name}
        environment: dict[str, str] = {}
        for container in overrides.pop("containerOverrides", []):
            container = dict(container)
            if container.get("name") != definition.container_name:
                containers.append(container)
                continue
            environment.update(
                {item["name"]: item["value"] for item in container.pop("environment", [])}
            )
            task_container.update(container)
        environment.update(definition.environment)
        if environment:
            task_container["environment"] = [
                {"name": name, "value": value} for name, value in environment.items()
            ]
        containers.append(task_container)
        overrides["containerOverrides"] = containers
        return overrides

    def describe(self) -> ProcessStatus:
        """Return normalized lifecycle status for this ECS workload."""
        if not self.external_id:
            return ProcessStatus("pending", "ECS task has not been submitted")
        task = self.runtime.describe_task(self.definition.cluster_name, self.external_id)
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
        exit_code = (container or {}).get("exitCode")
        if exit_code == 0:
            return ProcessStatus(
                "completed",
                "ECS task completed successfully",
                exit_code=exit_code,
            )
        reason = (
            (container or {}).get("reason")
            or task.get("stoppedReason")
            or "Unknown failure"
        )
        return ProcessStatus(
            "failed",
            f"ECS task failed ({reason})",
            exit_code=exit_code,
        )

    def collect_output(self) -> ProcessOutput | None:
        """Return retained CloudWatch output for this ECS workload."""
        if not self.definition.log_group or not self.external_id:
            return None
        task = self.runtime.describe_task(self.definition.cluster_name, self.external_id)
        if task is None:
            return None
        container = self._task_container(task)
        task_id = self.external_id.rsplit("/", maxsplit=1)[-1]
        container_name = (container or {}).get("name", self.definition.container_name)
        stream_name = (container or {}).get(
            "logStreamName",
            f"{self.definition.log_stream_prefix}/{container_name}/{task_id}",
        )
        return ProcessOutput(
            stdout="\n".join(self.runtime.get_log_events(self.definition.log_group, stream_name)),
            stderr="",
        )

    def stop(self) -> None:
        """Request normal cleanup of this ECS workload."""
        if not self.external_id:
            return
        self.runtime.stop_task(
            self.definition.cluster_name,
            self.external_id,
            f"Stopped BeakerHub {self.process_type} cleanup",
        )

    def _task_container(self, task: dict[str, Any]) -> dict[str, Any] | None:
        return next(
            (
                item
                for item in task.get("containers", [])
                if item.get("name") == self.definition.container_name
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

    default_dashboard_class = traitlets.Type(
        klass="beakerhub.services.dashboard.aws_ecs_dashboard.AwsEcsDashboardService",
        default_value="beakerhub.services.dashboard.aws_ecs_dashboard.AwsEcsDashboardService",
        config=True
    )
    default_spawner_class = traitlets.Type(
        klass="beakerhub.services.spawner.aws_ecs_spawner.BeakerAwsECSSpawner",
        default_value="beakerhub.services.spawner.aws_ecs_spawner.BeakerAwsECSSpawner",
        config=True
    )
    default_task_runner_class = traitlets.Type(
        klass="beakerhub.services.task.aws_ecs_task_runner.AwsEcsTaskRunnerService",
        default_value="beakerhub.services.task.aws_ecs_task_runner.AwsEcsTaskRunnerService",
        config=True
    )


# Task persistence/completion handling and JupyterHub proxy/session behavior
# deliberately remain in their respective service adapters.
