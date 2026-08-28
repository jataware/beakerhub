"""AWS ECS implementation skeleton for the task-runner service."""

import typing
from typing import Any

import boto3
import traitlets
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from beakerhub.services.task.base import (
    BaseTaskRunnerService,
    RunningTask,
    TaskOutput,
    TaskStatus,
)
from beakerhub.tasks.base import BaseImageTask, BaseTaskDefinition


class AwsEcsTaskRunnerService(BaseTaskRunnerService):
    """Run BeakerHub background tasks as AWS ECS tasks."""

    boto_client: BaseClient = traitlets.Instance(klass=BaseClient, config=False)
    logs_client: BaseClient = traitlets.Instance(klass=BaseClient, config=False)

    log_group: str = traitlets.Unicode(
        default_value="",
        help="CloudWatch Logs group that receives ECS task container output.",
        config=True,
    )
    log_stream_prefix: str = traitlets.Unicode(
        default_value="beakerhub-task",
        help="CloudWatch Logs stream prefix for ECS task containers.",
        config=True,
    )
    execution_role_arn: str = traitlets.Unicode(
        default_value="",
        help=(
            "IAM role ARN used by ECS to pull images and write container logs. "
            "This role needs ECR access for private images and "
            "logs:CreateLogStream and logs:PutLogEvents for the log group."
        ),
        config=True,
    )
    task_role_arn: str = traitlets.Unicode(
        default_value="",
        help=(
            "IAM role ARN assumed by the task container. Grant it access to "
            "AWS services required by the task."
        ),
        config=True,
    )
    subnets: list[str] = traitlets.List(
        traitlets.Unicode(),
        default_value=[],
        help="Subnets used by Fargate task awsvpc network configuration.",
        config=True,
    )
    security_groups: list[str] = traitlets.List(
        traitlets.Unicode(),
        default_value=[],
        help="Security groups used by Fargate task awsvpc network configuration.",
        config=True,
    )
    assign_public_ip: bool = traitlets.Bool(
        False,
        help="Assign a public IP address to Fargate tasks.",
        config=True,
    )
    cpu_architecture: typing.Literal["X86_64", "ARM64"] = traitlets.Enum(
        values=["X86_64", "ARM64"],
        default_value="X86_64",
        help="CPU architecture for task containers.",
        config=True,
    )
    task_definition_name: str = traitlets.Unicode(
        default_value="beakerhub-tasks",
        help="""Name of task definition "family". This is should not include the colon or revision number. Will be created if it does not exist.""",
        config=True,
    )
    cluster_name: str = traitlets.Unicode(
        help="Name of ECS cluster to run task within",
        config=True,
    )
    task_group: str = traitlets.Unicode(
        help="Optional. Name of task group to associate with the task.",
        config=True,
    )
    launch_type: typing.Literal["EC2", "FARGATE", "EXTERNAL", "MANAGED_INSTANCES"] = traitlets.Enum(
        values=["EC2", "FARGATE", "EXTERNAL", "MANAGED_INSTANCES"],
        default_value="FARGATE",
        help="Method of launching ECS task",
        config=True,
    )
    launch_options: dict = traitlets.Dict(
        help="Optional. If provided, overrides keyword arguments passed to boto3.client.run_task. See https://docs.aws.amazon.com/boto3/latest/reference/services/ecs/client/run_task.html",
        config=True,
    )
    task_overrides: dict = traitlets.Dict(
        default_value=None,
        allow_none=True,
        help="Optional. ECS task TaskOverride values to be included. See https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_TaskOverride.html",
        config=True,
    )
    aws_region: str = traitlets.Unicode(
        help="Optional. AWS Region cluster resides in.",
        config=True,
    )
    default_task_cpu: str = traitlets.Unicode(
        default_value="4 vcpu",
        help="Optional. Default CPU for task nodes. Used to create the task_definition if it does not exist. Does not override per-task runs.",
        config=True,
    )
    default_task_memory: str = traitlets.Unicode(
        default_value="16GB",
        help="Optional. Default memory for task nodes. Used to create the task_definition if it does not exist. Does not override per-task runs.",
        config=True,
    )
    default_task_ephemeral_storage: str = traitlets.Int(
        default_value=50,
        help="Optional. Default ephemeral storage for task nodes in GB. Used to create the task_definition if it does not exist. Does not override per-task runs.",
        config=True,
    )

    @traitlets.default("boto_client")
    def _default_boto_client(self):
        return boto3.client("ecs", region_name=self.aws_region or None)

    @traitlets.default("logs_client")
    def _default_logs_client(self):
        return boto3.client("logs", region_name=self.aws_region or None)

    @traitlets.default('launch_options')
    def _default_launch_options(self):
        return {}

    @traitlets.default('aws_region')
    def _default_aws_region(self):
        session = boto3._get_default_session()
        return (session.region_name if session else None) or "us-east-1"

    def submit(self, task: BaseTaskDefinition) -> RunningTask:
        """Register an image-specific definition and launch one ECS task."""
        if not isinstance(task, BaseImageTask):
            raise ValueError(
                "AwsEcsTaskRunnerService only supports image tasks, not "
                f"{task.task_type!r}"
            )

        self._validate_configuration()
        definition_arn = self._register_task_definition(task)
        request: dict[str, Any] = {
            "cluster": self.cluster_name,
            "taskDefinition": definition_arn,
            "overrides": self._build_overrides(task),
            "tags": [
                {"key": "beakerhub-task", "value": "true"},
                {"key": "beakerhub-task-type", "value": task.task_type},
            ],
        }
        if self.task_group:
            request["group"] = self.task_group
        if self.launch_type == "FARGATE" and "networkConfiguration" not in self.launch_options:
            request["networkConfiguration"] = self._network_configuration()
        if "capacityProviderStrategy" not in self.launch_options:
            request["launchType"] = self.launch_type
        request.update(self.launch_options)

        try:
            response = self.boto_client.run_task(**request)
        except ClientError as error:
            raise RuntimeError(f"ECS failed to submit task: {error}") from error
        tasks = response.get("tasks", [])
        if not tasks:
            raise RuntimeError(f"ECS did not start a task: {response.get('failures', [])!r}")
        return RunningTask(tasks[0]["taskArn"], task, self)

    def _register_task_definition(self, task: BaseImageTask) -> str:
        """Register the image selected by a task as an ECS definition revision."""
        container: dict[str, Any] = {
            "name": "task-container",
            "image": task.image,
            "essential": True,
        }
        if task.entrypoint:
            container["entryPoint"] = list(task.entrypoint)
        if task.command:
            container["command"] = list(task.command)
        if task.working_directory:
            container["workingDirectory"] = task.working_directory
        if task.environment:
            container["environment"] = [
                {"name": name, "value": value}
                for name, value in task.environment.items()
            ]
        if self.log_group:
            container["logConfiguration"] = {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": self.log_group,
                    "awslogs-region": self.aws_region,
                    "awslogs-stream-prefix": self.log_stream_prefix,
                },
            }

        request: dict[str, Any] = {
            "family": self.task_definition_name,
            "containerDefinitions": [container],
            "cpu": self.default_task_cpu,
            "memory": self.default_task_memory,
            "runtimePlatform": {
                "cpuArchitecture": self.cpu_architecture,
                "operatingSystemFamily": "LINUX",
            },
        }
        if self.launch_type == "FARGATE":
            request["ephemeralStorage"] = {
                "sizeInGiB": self.default_task_ephemeral_storage
            }
        if self.execution_role_arn:
            request["executionRoleArn"] = self.execution_role_arn
        if self.task_role_arn:
            request["taskRoleArn"] = self.task_role_arn
        if self.launch_type == "FARGATE":
            request.update({
                "networkMode": "awsvpc",
                "requiresCompatibilities": ["FARGATE"],
            })

        try:
            response = self.boto_client.register_task_definition(**request)
        except ClientError as error:
            raise RuntimeError(f"ECS failed to register task definition: {error}") from error
        return response["taskDefinition"]["taskDefinitionArn"]

    def _build_overrides(self, task: BaseImageTask) -> dict[str, Any]:
        overrides = dict(self.task_overrides or {})
        containers: list[dict[str, Any]] = []
        task_container: dict[str, Any] = {"name": "task-container"}
        environment: dict[str, str] = {}
        for container in overrides.pop("containerOverrides", []):
            container = dict(container)
            if container.get("name") != "task-container":
                containers.append(container)
                continue
            environment.update({
                item["name"]: item["value"]
                for item in container.pop("environment", [])
            })
            task_container.update(container)
        environment.update(task.environment)
        if environment:
            task_container["environment"] = [
                {"name": name, "value": value}
                for name, value in environment.items()
            ]
        containers.append(task_container)
        overrides["containerOverrides"] = containers
        return overrides

    def _network_configuration(self) -> dict[str, Any]:
        return {
            "awsvpcConfiguration": {
                "subnets": list(self.subnets),
                "securityGroups": list(self.security_groups),
                "assignPublicIp": "ENABLED" if self.assign_public_ip else "DISABLED",
            }
        }

    def _validate_configuration(self) -> None:
        if not self.cluster_name.strip():
            raise ValueError("AwsEcsTaskRunnerService.cluster_name must be configured")
        if not self.log_group:
            raise ValueError("AwsEcsTaskRunnerService.log_group must be configured")
        if not self.aws_region:
            raise ValueError("AwsEcsTaskRunnerService.aws_region must be configured")
        if not self.execution_role_arn:
            raise ValueError(
                "AwsEcsTaskRunnerService.execution_role_arn must be configured"
            )
        if self.launch_type == "FARGATE":
            network_configuration = self.launch_options.get("networkConfiguration")
            subnets = (
                network_configuration.get("awsvpcConfiguration", {}).get("subnets", [])
                if network_configuration
                else self.subnets
            )
            if not subnets:
                raise ValueError(
                    "AwsEcsTaskRunnerService.subnets must be configured for Fargate tasks"
                )
        elif self.default_task_ephemeral_storage:
            raise ValueError(
                "default_task_ephemeral_storage is supported only for Fargate tasks"
            )
        if (
            self.launch_type == "MANAGED_INSTANCES"
            and not self.launch_options.get("capacityProviderStrategy")
        ):
            raise ValueError(
                "Managed Instances tasks require launch_options.capacityProviderStrategy"
            )

    def get_status(self, external_id: str) -> TaskStatus:
        task = self._describe_task(external_id)
        if task is None:
            return TaskStatus("failed", f"ECS task {external_id} was not found")
        status = task.get("lastStatus", "UNKNOWN")
        if status in {"PROVISIONING", "PENDING", "ACTIVATING"}:
            return TaskStatus("pending", f"ECS task is {status.lower()}")
        if status in {"RUNNING", "DEACTIVATING", "DEPROVISIONING", "STOPPING"}:
            return TaskStatus("running", f"ECS task is {status.lower()}")
        if status != "STOPPED":
            return TaskStatus("failed", f"ECS task has unexpected status {status!r}")

        container = self._task_container(task)
        if container and container.get("exitCode") == 0:
            return TaskStatus("completed", "ECS task completed successfully")
        reason = (container or {}).get("reason") or task.get("stoppedReason") or "Unknown failure"
        return TaskStatus("failed", f"ECS task failed ({reason})")

    def get_output(self, external_id: str) -> TaskOutput | None:
        """Return task output from the configured CloudWatch Logs group."""
        if not self.log_group:
            return None
        task = self._describe_task(external_id)
        if task is None:
            return None
        container = self._task_container(task)
        task_id = external_id.split('/')[-1]
        container_name = (container or {}).get('name', 'task-container')
        stream_name = f"{self.log_stream_prefix}/{container_name}/{task_id}"

        messages: list[str] = []
        next_token: str | None = None
        while True:
            request: dict[str, Any] = {
                "logGroupName": self.log_group,
                "logStreamName": stream_name,
                "startFromHead": True,
            }
            if next_token:
                request["nextToken"] = next_token
            try:
                response = self.logs_client.get_log_events(**request)
            except ClientError as error:
                raise RuntimeError(
                    f"CloudWatch failed to get output for ECS task {external_id}: {error}"
                ) from error
            messages.extend(event["message"] for event in response.get("events", []))
            token = response.get("nextForwardToken")
            if not token or token == next_token:
                break
            next_token = token
        return TaskOutput(stdout="\n".join(messages), stderr="")

    def delete(self, external_id: str) -> None:
        try:
            self.boto_client.stop_task(
                cluster=self.cluster_name,
                task=external_id,
                reason="Completed BeakerHub task cleanup",
            )
        except ClientError as error:
            raise RuntimeError(f"ECS failed to stop task {external_id}: {error}") from error

    def reap_stale_tasks(self) -> None:
        """Stale-task reconciliation needs persisted task ownership and is deferred."""
        self.log.warning("ECS stale-task reaping is not implemented")
        # TODO: Clean stale task-definition revisions as part of reaping tasks

    def _describe_task(self, external_id: str) -> dict[str, Any] | None:
        try:
            response = self.boto_client.describe_tasks(
                cluster=self.cluster_name,
                tasks=[external_id],
            )
        except ClientError as error:
            raise RuntimeError(f"ECS failed to describe task {external_id}: {error}") from error
        tasks = response.get("tasks", [])
        return tasks[0] if tasks else None

    @staticmethod
    def _task_container(task: dict[str, Any]) -> dict[str, Any] | None:
        return next(
            (item for item in task.get("containers", []) if item.get("name") == "task-container"),
            None,
        )
