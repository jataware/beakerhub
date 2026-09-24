"""AWS ECS-backed JupyterHub spawner."""

import asyncio
import hashlib
import os
import time
from functools import cache
from typing import Any, Literal

import boto3
import traitlets
from kubespawner.slugs import strip_and_hash
from traitlets import Bool, Dict, Integer, Instance, List, Unicode, default
from traitlets.config import Config

from beakerhub import orm
from beakerhub.runtimes.aws_ecs import AwsEcsDefinition, AwsEcsProcess, AwsEcsRuntime
from beakerhub.runtimes.base import ProcessStatus
from beakerhub.services.spawner.base import BeakerhubImageSpawner


_CONFIG_VOLUME_NAME = "config"
_CONFIG_WRITER_NAME = "config-writer"
_CONFIG_WRITER_IMAGE = "busybox:latest"
_CONFIG_WRITER_MOUNT_PATH = "/opt/beaker/config"
_NOTEBOOK_CONFIG_PATH = "/root/.config"


class BeakerAwsECSSpawner(BeakerhubImageSpawner):
    """Launch a Beaker session as an ECS runtime process."""

    runtime = Instance(AwsEcsRuntime, allow_none=False)

    cluster_name = Unicode(config=True, help="ECS cluster name or ARN.")
    task_definition = Unicode(
        config=True,
        help="Optional ECS task-definition family, revision, or ARN. When unset, "
        "BeakerHub registers and reuses an image-specific definition.",
    )
    container_name = Unicode(
        "task-container",
        config=True,
        help="Name of the notebook container in the ECS task definition.",
    )
    container_tags = Dict(
        Unicode(), Unicode(), default_value={}, config=True,
        help="Tags applied to every ECS notebook task.",
    )
    subnets = List(
        Unicode(), config=True,
        help="Subnets used by the task's awsvpc network configuration.",
    )
    security_groups = List(Unicode(), config=True)
    assign_public_ip = Bool(config=True)
    launch_options = Dict(
        config=True,
        help="ECS run_task options for notebook tasks.",
    )
    efs_volume_configuration = Dict(
        default_value={},
        config=True,
        help="Optional ECS efsVolumeConfiguration mapping for the notebook task.",
    )
    efs_mount_path = Unicode(
        "",
        config=True,
        help="Container path for the optional EFS volume mount.",
    )
    efs_volume_name = Unicode(
        "beakerhub-efs",
        config=True,
        help="Task-definition volume name for the optional EFS mount.",
    )
    task_overrides = Dict(default_value=None, allow_none=True, config=True)
    log_group = Unicode(config=True)
    log_stream_prefix = Unicode(config=True)
    execution_role_arn = Unicode(config=True)
    task_role_arn = Unicode(config=True)
    cpu_architecture: Literal["X86_64", "ARM64"] = traitlets.Enum(
        ["X86_64", "ARM64"], config=True
    )
    task_definition_name = Unicode(config=True)
    task_group = Unicode(config=True)
    launch_type: Literal["EC2", "FARGATE", "EXTERNAL", "MANAGED_INSTANCES"] = (
        traitlets.Enum(
            ["EC2", "FARGATE", "EXTERNAL", "MANAGED_INSTANCES"], config=True
        )
    )
    default_task_cpu = Unicode(config=True)
    default_task_memory = Unicode(config=True)
    default_task_ephemeral_storage = traitlets.Int(config=True)

    task_arn: str | None = None

    @default("http_timeout")
    def _default_http_timeout(self):
        return 600

    @default("runtime")
    def _default_runtime(self) -> AwsEcsRuntime:
        app = self.user.settings.get("app")
        runtime = getattr(app, "runtime", None)
        if not isinstance(runtime, AwsEcsRuntime):
            raise RuntimeError(
                "BeakerAwsECSSpawner requires the application to use AwsEcsRuntime"
            )
        return runtime

    @default("cluster_name")
    def _default_cluster_name(self) -> str:
        return self.runtime.cluster_name

    @default("subnets")
    def _default_subnets(self) -> list[str]:
        return list(self.runtime.subnets)

    @default("security_groups")
    def _default_security_groups(self) -> list[str]:
        return list(self.runtime.security_groups)

    @default("assign_public_ip")
    def _default_assign_public_ip(self) -> bool:
        return self.runtime.assign_public_ip

    @default("launch_options")
    def _default_launch_options(self) -> dict[str, Any]:
        return dict(self.runtime.launch_options)

    @default("task_overrides")
    def _default_task_overrides(self) -> dict[str, Any] | None:
        return (
            dict(self.runtime.task_overrides)
            if self.runtime.task_overrides is not None
            else None
        )

    @default("log_group")
    def _default_log_group(self) -> str:
        return self.runtime.log_group

    @default("log_stream_prefix")
    def _default_log_stream_prefix(self) -> str:
        return self.runtime.log_stream_prefix

    @default("execution_role_arn")
    def _default_execution_role_arn(self) -> str:
        return self.runtime.execution_role_arn

    @default("task_role_arn")
    def _default_task_role_arn(self) -> str:
        return self.runtime.task_role_arn

    @default("cpu_architecture")
    def _default_cpu_architecture(self) -> Literal["X86_64", "ARM64"]:
        return self.runtime.cpu_architecture

    @default("task_definition_name")
    def _default_task_definition_name(self) -> str:
        identifier = b"\x1f".join(
            str(value).encode("utf-8") for value in (self.user.id, self.image)
        )
        return f"beakerhub-notebook_{hashlib.sha256(identifier).hexdigest()}"

    @default("task_group")
    def _default_task_group(self) -> str:
        return self.runtime.task_group

    @default("launch_type")
    def _default_launch_type(
        self,
    ) -> Literal["EC2", "FARGATE", "EXTERNAL", "MANAGED_INSTANCES"]:
        return self.runtime.launch_type

    @default("default_task_cpu")
    def _default_task_cpu(self) -> str:
        return self.runtime.default_task_cpu

    @default("default_task_memory")
    def _default_task_memory(self) -> str:
        return self.runtime.default_task_memory

    @default("default_task_ephemeral_storage")
    def _default_task_ephemeral_storage(self) -> int:
        return self.runtime.default_task_ephemeral_storage

    @property
    def volume_configs(self) -> list[dict[str, Any]]:
        """Return ECS managed-volume configuration overrides, if configured."""
        return []

    def _task_tags(self) -> dict[str, str]:
        tags = dict(self.container_tags)
        # The session tag is owned by BeakerHub and must not be overridden.
        tags["beaker-session"] = self.session_id
        return tags

    def _efs_volumes(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Build optional EFS task-definition volumes and container mounts."""
        configured = bool(self.efs_volume_configuration)
        has_mount_path = bool(self.efs_mount_path)
        if configured != has_mount_path:
            raise ValueError(
                "efs_volume_configuration and efs_mount_path must be configured together"
            )
        if not configured:
            return [], []

        file_system_id = self.efs_volume_configuration.get("fileSystemId")
        if not file_system_id:
            raise ValueError("efs_volume_configuration.fileSystemId must be configured")

        user_subdir = f"/user-storage/{strip_and_hash(self.user.name)}"
        access_point_id = self._efs_access_point_id(
            file_system_id,
            str(self.user.id),
            user_subdir,
        )
        volume_configuration = dict(self.efs_volume_configuration)
        authorization_config = dict(volume_configuration.get("authorizationConfig", {}))
        authorization_config["accessPointId"] = access_point_id
        volume_configuration["authorizationConfig"] = authorization_config
        volume_configuration.pop("rootDirectory", None)

        return (
            [
                {
                    "name": self.efs_volume_name,
                    "efsVolumeConfiguration": volume_configuration,
                }
            ],
            [
                {
                    "sourceVolume": self.efs_volume_name,
                    "containerPath": self.efs_mount_path,
                    "readOnly": False,
                }
            ],
        )

    def _efs_access_point_id(
        self,
        file_system_id: str,
        user_id: str,
        user_subdir: str,
    ) -> str:
        """Find or create the EFS access point for one user's storage."""
        efs_client = boto3.client("efs", region_name=self.runtime.aws_region)
        tagging_client = boto3.client(
            "resourcegroupstaggingapi",
            region_name=self.runtime.aws_region,
        )
        access_point_id = self._find_efs_access_point(
            efs_client,
            tagging_client,
            file_system_id,
            user_id,
            user_subdir,
        )
        if access_point_id is not None:
            return access_point_id

        response = efs_client.create_access_point(
            ClientToken=self._efs_access_point_token(file_system_id, user_id),
            FileSystemId=file_system_id,
            RootDirectory={
                "Path": user_subdir,
                "CreationInfo": {
                    "OwnerUid": 1000,
                    "OwnerGid": 1000,
                    "Permissions": "755",
                },
            },
            Tags=[
                {"Key": "beakerhub-user-id", "Value": user_id},
                {"Key": "beakerhub-user-name", "Value": str(self.user.name)},
                {"Key": "beakerhub-user-subdir", "Value": user_subdir},
            ],
        )
        access_point_id = response["AccessPointId"]
        self._wait_for_efs_access_point(efs_client, access_point_id)
        return access_point_id

    @staticmethod
    def _efs_access_point_token(file_system_id: str, user_id: str) -> str:
        return hashlib.sha256(
            b"\x1f".join(
                value.encode("utf-8") for value in (file_system_id, user_id)
            )
        ).hexdigest()

    @staticmethod
    def _find_efs_access_point(
        efs_client: Any,
        tagging_client: Any,
        file_system_id: str,
        user_id: str,
        user_subdir: str,
    ) -> str | None:
        """Find the matching access point among resources tagged for this user."""
        pagination_token = ""
        while True:
            request: dict[str, Any] = {
                "TagFilters": [{"Key": "beakerhub-user-id", "Values": [user_id]}],
                "ResourceTypeFilters": ["elasticfilesystem:access-point"],
            }
            if pagination_token:
                request["PaginationToken"] = pagination_token
            response = tagging_client.get_resources(**request)
            for resource in response.get("ResourceTagMappingList", []):
                candidate_id = resource["ResourceARN"].rsplit("/", maxsplit=1)[-1]
                described = efs_client.describe_access_points(
                    AccessPointId=candidate_id
                )
                access_points = described.get("AccessPoints", [])
                if not access_points:
                    continue
                access_point = access_points[0]
                if (
                    access_point.get("FileSystemId") == file_system_id
                    and access_point.get("RootDirectory", {}).get("Path") == user_subdir
                ):
                    return access_point["AccessPointId"]
            if not response.get("PaginationToken"):
                return None
            pagination_token = response["PaginationToken"]

    @staticmethod
    def _wait_for_efs_access_point(efs_client: Any, access_point_id: str) -> None:
        """Wait until a newly created EFS access point is usable."""
        for _ in range(60):
            described = efs_client.describe_access_points(AccessPointId=access_point_id)
            access_points = described.get("AccessPoints", [])
            state = access_points[0].get("LifeCycleState") if access_points else None
            if state == "available":
                return
            if state in {"deleted", "deleting", "error"}:
                raise RuntimeError(
                    f"EFS access point {access_point_id} entered state {state!r}"
                )
            time.sleep(1)
        raise RuntimeError(
            f"EFS access point {access_point_id} did not become available"
        )

    def get_env(self) -> dict[str, str]:
        """Add the hub URLs needed by an ECS-hosted notebook server."""
        env = super().get_env()
        hub_host = os.environ.get("HOSTNAME", "hub")
        env.update(
            {
                "JUPYTERHUB_API_URL": f"http://{hub_host}:8888/api",
                "JUPYTERHUB_ACTIVITY_URL": (
                    f"http://{hub_host}:8888/api/users/matt@jataware.com/activity"
                ),
                "JUPYTERHUB_SERVICE_URL": f"http://{hub_host}:8888/",
            }
        )
        return env

    def _task_overrides(self) -> dict[str, Any]:
        """Merge session environment into runtime task overrides.

        Session values are run-task overrides, rather than task-definition
        values, so image-specific definitions can be reused by multiple users.
        """
        overrides = dict(self.task_overrides or {})
        containers: list[dict[str, Any]] = []
        session_container: dict[str, Any] = {"name": self.container_name}
        environment: dict[str, str] = {}
        for container in overrides.pop("containerOverrides", []):
            container = dict(container)
            if container.get("name") != self.container_name:
                containers.append(container)
                continue
            environment.update(
                {item["name"]: item["value"] for item in container.pop("environment", [])}
            )
            session_container.update(container)
        environment.update({name: str(value) for name, value in self.get_env().items()})
        if environment:
            session_container["environment"] = [
                {"name": name, "value": value} for name, value in environment.items()
            ]
        containers.append(session_container)
        overrides["containerOverrides"] = containers
        return overrides

    def _config_writer_container(self) -> dict[str, Any]:
        """Build the sidecar that writes the generated notebook config."""
        return {
            "name": _CONFIG_WRITER_NAME,
            "image": _CONFIG_WRITER_IMAGE,
            "command": [
                "/bin/sh",
                "-ec",
                "printf '%s' \"$BEAKER_NOTEBOOK_CONFIG\" > "
                f"{_CONFIG_WRITER_MOUNT_PATH}/beaker_config.py",
            ],
            "environment": [
                {
                    "name": "BEAKER_NOTEBOOK_CONFIG",
                    "value": str(self._notebook_config()),
                }
            ],
            "mountPoints": [
                {
                    "containerPath": _CONFIG_WRITER_MOUNT_PATH,
                    "sourceVolume": _CONFIG_VOLUME_NAME,
                }
            ],
            "essential": False,
        }

    def _definition(self) -> AwsEcsDefinition:
        """Build the ECS definition for this notebook session."""
        if not self.container_name:
            raise ValueError("BeakerAwsECSSpawner.container_name must be configured")

        launch_options = dict(self.launch_options)
        if self.volume_configs:
            launch_options["volumeConfigurations"] = self.volume_configs
        volumes, mount_points = self._efs_volumes()

        volumes.append({"name": _CONFIG_VOLUME_NAME})
        mount_points.append(
            {
                "containerPath": _NOTEBOOK_CONFIG_PATH,
                "sourceVolume": _CONFIG_VOLUME_NAME,
            }
        )

        # This flag allows an AWS user/accout with a proper role to "log into" running tasks.
        # As such, it is only enabled when running in debug mode.
        launch_options["enableExecuteCommand"] = self.debug

        return AwsEcsDefinition(
            runtime=self.runtime,
            image=self.image,
            task_definition_arn=self.task_definition or None,
            container_name=self.container_name,
            tags=self._task_tags(),
            definition_tags={
                "beakerhub-user-id": str(self.user.id),
                "beakerhub-image-uri": self.image,
            },
            cluster_name=self.cluster_name,
            subnets=list(self.subnets),
            security_groups=list(self.security_groups),
            assign_public_ip=self.assign_public_ip,
            log_group=self.log_group,
            log_stream_prefix=self.log_stream_prefix,
            execution_role_arn=self.execution_role_arn,
            task_role_arn=self.task_role_arn,
            cpu_architecture=self.cpu_architecture,
            task_definition_name=self.task_definition_name,
            task_group=self.task_group,
            launch_type=self.launch_type,
            launch_options=launch_options,
            task_overrides=self._task_overrides(),
            cpu=self.default_task_cpu,
            memory=self.default_task_memory,
            ephemeral_storage=self.default_task_ephemeral_storage,
            volumes=volumes,
            mount_points=mount_points,
            sidecar_containers=[self._config_writer_container()],
        )

    def _process(self) -> AwsEcsProcess:
        """Reconstruct the runtime process for this session, if it was launched."""
        return AwsEcsProcess(
            self._definition(),
            runtime=self.runtime,
            external_id=self.task_arn,
            process_type="service",
        )

    @cache
    def _notebook_config(self) -> str:
        from beakerhub.app import BeakerHub
        beakerhub = BeakerHub.instance()
        subdomain_host = beakerhub.subdomain_host

        c = Config()
        c.BaseBeakerApp.allow_origin_pat = rf"^{subdomain_host}$"
        c.BaseBeakerApp.tornado_settings = {
            "headers": {
                "Content-Security-Policy": f"frame-ancestors 'self' {subdomain_host}"
            }
        }
        c.BaseBeakerApp.identity_provider_class = (
            "beakerhub.auth.node.BeakerhubNodeIdentityProvider"
        )
        c.BaseBeakerApp.authorizer_class = (
            "beakerhub.auth.node.BeakerhubNodeAuthorizer"
        )
        c.BaseBeakerApp.secrets_manager_class = (
            "beakerhub.services.secrets.beakerhub.BeakerhubSecretsManager"
        )
        c.BeakerhubSecretsManager.policy_override_env_key_suffix = "_secret_policy"
        c.FileNotebookManager.notebook_path = ".notebooks"
        c.FileNotebookManager.snapshot_path = ".notebooks"

        lines = [
            "# Beaker Notebook Service Configuration File",
            "",
            "c = get_config()  # noqa # type: ignore",
            "",
        ]

        for cls_name, cls_configs in c.items():
            for config_name, config_value in cls_configs.items():
                lines.append(f"c.{cls_name}.{config_name} = {repr(config_value)}")
        config_text = "\n".join(lines)

        return config_text

    async def start(self) -> tuple[str, int]:
        """Launch the session task and retain its ARN for later lifecycle calls."""
        process = AwsEcsProcess.start(
            self._definition(),
            runtime=self.runtime,
            process_type="service",
        )
        self.task_arn = process.external_id
        local_ip = await self._wait_for_task_ip(process=process)

        port = 8888
        self.log.warning("ECS notebook task is available at http://%s:%s", local_ip, port)
        return str(local_ip), port

    async def stop(self, now: bool = False) -> None:
        """Stop the session task and wait for ECS to deprovision it."""
        if self.task_arn:
            process = self._process()
            process.stop()
            await process.await_completion()

    async def poll(self) -> int | None:
        """Map normalized ECS process status to JupyterHub poll semantics."""
        if not self.task_arn:
            return 0
        status: ProcessStatus = self._process().status
        if status.state in {"pending", "running"}:
            return None
        if status.exit_code is not None:
            return status.exit_code
        return 0 if status.state == "completed" else 1

    def get_state(self) -> dict[str, Any]:
        state = super().get_state()
        if self.task_arn:
            state["task_arn"] = self.task_arn
        return state

    def load_state(self, state: dict[str, Any]) -> None:
        super().load_state(state)
        self.task_arn = state.get("task_arn")

    def clear_state(self) -> None:
        super().clear_state()
        self.task_arn = None

    async def _wait_for_task_ip(
        self,
        process: AwsEcsProcess,
        timeout: float = 120.0,
    ) -> str:
        """Return the task's private IPv4 address once ECS has assigned one."""
        def _request_ip() -> str | None:
            task = self.runtime.describe_task(
                process.definition.cluster_name,
                process.external_id,
            )
            if task is None:
                raise RuntimeError(f"Task `{process.external_id}` was not found")
            if task.get("lastStatus") == "STOPPED":
                container = next(
                    (
                        item
                        for item in task.get("containers", [])
                        if item.get("name") == process.definition.container_name
                    ),
                    None,
                )
                reason = (
                    (container or {}).get("reason")
                    or task.get("stoppedReason")
                    or "Unknown failure"
                )
                raise RuntimeError(
                    f"Task `{process.external_id}` stopped before receiving an "
                    f"internal IP: {reason}"
                )
            return next(
                (
                    detail["value"]
                    for attachment in task.get("attachments", [])
                    if attachment.get("type") == "ElasticNetworkInterface"
                    for detail in attachment.get("details", [])
                    if detail.get("name") == "privateIPv4Address"
                ),
                None,
            )

        start = time.monotonic()
        while not (task_ip := _request_ip()):
            if time.monotonic() - start > timeout:
                raise TimeoutError(
                    f"Task `{process.external_id}` did not receive an internal IP "
                    f"within {timeout} seconds."
                )
            await asyncio.sleep(5)
        return task_ip
