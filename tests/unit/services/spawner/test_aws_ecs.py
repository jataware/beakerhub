"""Tests for the ECS runtime-backed JupyterHub spawner."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import boto3
import pytest

from beakerhub.runtimes.aws_ecs import AwsEcsRuntime
from beakerhub.runtimes.base import ProcessStatus
from beakerhub.services.spawner.aws_ecs_spawner import BeakerAwsECSSpawner


TASK_ARN = "arn:aws:ecs:us-east-1:123456789012:task/test/task-123"


def runtime(**overrides) -> AwsEcsRuntime:
    ecs = boto3.client(
        "ecs",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    values = {
        "ecs_client": ecs,
        "cluster_name": "runtime-cluster",
        "subnets": ["subnet-runtime"],
        "security_groups": ["sg-runtime"],
        "launch_options": {"enableExecuteCommand": True},
        "task_overrides": {"cpu": "512"},
        "log_group": "/beakerhub/runtime",
        "log_stream_prefix": "runtime-session",
        "execution_role_arn": "arn:aws:iam::123456789012:role/execution",
        "task_role_arn": "arn:aws:iam::123456789012:role/task",
        "task_group": "runtime-group",
        "default_task_cpu": "2 vcpu",
        "default_task_memory": "8GB",
        "default_task_ephemeral_storage": 40,
    }
    values.update(overrides)
    return AwsEcsRuntime(**values)


def configured_spawner(**overrides):
    """A minimal object sufficient to exercise unbound spawner methods."""
    shared_runtime = overrides.get("runtime", runtime())
    values = {
        "runtime": shared_runtime,
        "user": SimpleNamespace(id=1, name="ada"),
        "cluster_name": "notebooks",
        "task_definition": "beaker-notebook:3",
        "container_name": "notebook",
        "container_tags": {"environment": "test"},
        "session_id": "session-123",
        "subnets": ["subnet-123"],
        "security_groups": ["sg-123"],
        "assign_public_ip": True,
        "launch_options": {"enableExecuteCommand": True},
        "efs_volume_configuration": {},
        "efs_mount_path": "",
        "efs_volume_name": "beakerhub-efs",
        "task_overrides": dict(shared_runtime.task_overrides or {}),
        "log_group": shared_runtime.log_group,
        "log_stream_prefix": shared_runtime.log_stream_prefix,
        "execution_role_arn": shared_runtime.execution_role_arn,
        "task_role_arn": shared_runtime.task_role_arn,
        "cpu_architecture": shared_runtime.cpu_architecture,
        "task_group": shared_runtime.task_group,
        "launch_type": shared_runtime.launch_type,
        "default_task_cpu": shared_runtime.default_task_cpu,
        "default_task_memory": shared_runtime.default_task_memory,
        "default_task_ephemeral_storage": shared_runtime.default_task_ephemeral_storage,
        "volume_configs": [],
        "image": "registry.example/beaker-node:latest",
        "get_env": lambda: {"BEAKERHUB_USER": "ada", "NUMBER": 2},
        "_notebook_config": lambda: "",
        "task_arn": None,
        "debug": False,
        "log": Mock(),
    }
    values.update(overrides)
    values.setdefault(
        "task_definition_name",
        "beakerhub-notebook_d25e4b5db3dca83c3aae6b9fe0d9c3e9fc019ced629567804f94092004ac0316",
    )
    spawner = SimpleNamespace(**values)
    spawner._task_tags = lambda: BeakerAwsECSSpawner._task_tags(spawner)
    spawner._efs_volumes = lambda: BeakerAwsECSSpawner._efs_volumes(spawner)
    spawner._efs_access_point_id = (
        lambda file_system_id, user_id, user_subdir:
        BeakerAwsECSSpawner._efs_access_point_id(
            spawner, file_system_id, user_id, user_subdir
        )
    )
    spawner._find_efs_access_point = BeakerAwsECSSpawner._find_efs_access_point
    spawner._efs_access_point_token = BeakerAwsECSSpawner._efs_access_point_token
    spawner._wait_for_efs_access_point = BeakerAwsECSSpawner._wait_for_efs_access_point
    spawner._task_overrides = lambda: BeakerAwsECSSpawner._task_overrides(spawner)
    spawner._config_writer_container = (
        lambda: BeakerAwsECSSpawner._config_writer_container(spawner)
    )
    spawner._definition = lambda: BeakerAwsECSSpawner._definition(spawner)
    spawner._process = lambda: BeakerAwsECSSpawner._process(spawner)
    spawner._wait_for_task_ip = AsyncMock(return_value="10.0.0.42")
    return spawner


def test_definition_contains_session_overrides_and_runtime_launch_options():
    spawner = configured_spawner(
        volume_configs=[{"name": "session-volume", "managedEBSVolume": {}}]
    )

    definition = BeakerAwsECSSpawner._definition(spawner)

    assert definition.runtime is spawner.runtime
    assert definition.image == "registry.example/beaker-node:latest"
    assert definition.task_definition_arn == "beaker-notebook:3"
    assert definition.container_name == "notebook"
    assert definition.environment == {}
    assert definition.task_overrides == {
        "cpu": "512",
        "containerOverrides": [
            {
                "name": "notebook",
                "environment": [
                    {"name": "BEAKERHUB_USER", "value": "ada"},
                    {"name": "NUMBER", "value": "2"},
                ],
            }
        ]
    }
    assert definition.tags == {
        "environment": "test",
        "beaker-session": "session-123",
    }
    assert definition.cluster_name == "notebooks"
    assert definition.subnets == ["subnet-123"]
    assert definition.security_groups == ["sg-123"]
    assert definition.assign_public_ip is True
    assert definition.log_group == "/beakerhub/runtime"
    assert definition.log_stream_prefix == "runtime-session"
    assert definition.execution_role_arn.endswith("role/execution")
    assert definition.task_role_arn.endswith("role/task")
    assert definition.cpu_architecture == "X86_64"
    assert definition.task_group == "runtime-group"
    assert definition.launch_type == "FARGATE"
    assert definition.cpu == "2 vcpu"
    assert definition.memory == "8GB"
    assert definition.ephemeral_storage == 40
    assert definition.launch_options == {
        "enableExecuteCommand": False,
        "volumeConfigurations": [{"name": "session-volume", "managedEBSVolume": {}}],
    }


def test_definition_enables_ecs_exec_when_spawner_debug_is_enabled():
    spawner = configured_spawner(debug=True)

    definition = BeakerAwsECSSpawner._definition(spawner)

    assert definition.launch_options["enableExecuteCommand"] is True


def test_definition_adds_an_optional_efs_volume_and_mount(monkeypatch):
    shared_runtime = runtime()
    tagging = Mock()
    tagging.get_resources.return_value = {"ResourceTagMappingList": []}
    efs = Mock()
    efs.create_access_point.return_value = {"AccessPointId": "fsap-12345678"}
    efs.describe_access_points.return_value = {
        "AccessPoints": [{"LifeCycleState": "available"}]
    }
    boto3_client = boto3.client

    def aws_client(service_name, **kwargs):
        if service_name == "efs":
            return efs
        if service_name == "resourcegroupstaggingapi":
            return tagging
        return boto3_client(service_name, **kwargs)

    monkeypatch.setattr(
        "beakerhub.services.spawner.aws_ecs_spawner.boto3.client",
        aws_client,
    )
    spawner = configured_spawner(
        runtime=shared_runtime,
        efs_volume_configuration={
            "fileSystemId": "fs-12345678",
            "rootDirectory": "/notebooks",
            "transitEncryption": "ENABLED",
        },
        efs_mount_path="/home/beaker",
        efs_volume_name="user-storage",
    )

    volumes, mount_points = BeakerAwsECSSpawner._efs_volumes(spawner)

    assert volumes == [
        {
            "name": "user-storage",
            "efsVolumeConfiguration": {
                "fileSystemId": "fs-12345678",
                "transitEncryption": "ENABLED",
                "authorizationConfig": {"accessPointId": "fsap-12345678"},
            },
        }
    ]
    assert mount_points == [
        {
            "sourceVolume": "user-storage",
            "containerPath": "/home/beaker",
            "readOnly": False,
        }
    ]
    efs.create_access_point.assert_called_once_with(
        ClientToken="580d2dbbb845c84be8c83a0f6188bbf573b7bed4850770030bb762ed79e89203",
        FileSystemId="fs-12345678",
        RootDirectory={
            "Path": "/user-storage/ada---fdee430d",
            "CreationInfo": {
                "OwnerUid": 1000,
                "OwnerGid": 1000,
                "Permissions": "755",
            },
        },
        Tags=[
            {"Key": "beakerhub-user-id", "Value": "1"},
            {"Key": "beakerhub-user-name", "Value": "ada"},
            {
                "Key": "beakerhub-user-subdir",
                "Value": "/user-storage/ada---fdee430d",
            },
        ],
    )


def test_dynamic_definition_includes_config_writer_sidecar():
    spawner = configured_spawner(
        task_definition="",
        _notebook_config=lambda: "c.Foo.bar = 'baz'",
    )

    definition = BeakerAwsECSSpawner._definition(spawner)

    assert definition.sidecar_containers == [
        {
            "name": "config-writer",
            "image": "busybox:latest",
            "command": [
                "/bin/sh",
                "-ec",
                "printf '%s' \"$BEAKER_NOTEBOOK_CONFIG\" > "
                "/opt/beaker/config/beaker_config.py",
            ],
            "environment": [
                {"name": "BEAKER_NOTEBOOK_CONFIG", "value": "c.Foo.bar = 'baz'"}
            ],
            "mountPoints": [
                {
                    "containerPath": "/opt/beaker/config",
                    "sourceVolume": "config",
                }
            ],
            "essential": False,
        }
    ]
    assert definition.aws_task_definition["containerDefinitions"][0]["dependsOn"] == [
        {"containerName": "config-writer", "condition": "SUCCESS"}
    ]
    assert definition.aws_task_definition["containerDefinitions"][1] == (
        definition.sidecar_containers[0]
    )


def test_session_tag_cannot_be_overridden_by_configuration():
    spawner = configured_spawner(container_tags={"beaker-session": "incorrect"})

    assert BeakerAwsECSSpawner._task_tags(spawner) == {
        "beaker-session": "session-123"
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"efs_volume_configuration": {"fileSystemId": "fs-123"}},
        {"efs_mount_path": "/home/beaker"},
        {
            "efs_volume_configuration": {"rootDirectory": "/"},
            "efs_mount_path": "/home/beaker",
        },
    ],
)
def test_definition_rejects_incomplete_efs_configuration(overrides):
    spawner = configured_spawner(**overrides)

    with pytest.raises(ValueError, match="efs_"):
        BeakerAwsECSSpawner._definition(spawner)


def test_definition_rejects_an_empty_container_name():
    spawner = configured_spawner(container_name="")

    with pytest.raises(ValueError, match="container_name"):
        BeakerAwsECSSpawner._definition(spawner)


async def test_start_uses_the_runtime_process_and_persists_its_arn():
    shared_runtime = runtime()
    shared_runtime.ecs_client.run_task = Mock(
        return_value={"tasks": [{"taskArn": TASK_ARN}]}
    )
    shared_runtime.ecs_client.register_task_definition = Mock()
    spawner = configured_spawner(runtime=shared_runtime)

    await BeakerAwsECSSpawner.start(spawner)

    assert spawner.task_arn == TASK_ARN
    request = shared_runtime.ecs_client.run_task.call_args.kwargs
    assert request["taskDefinition"] == "beaker-notebook:3"
    assert request["cluster"] == "notebooks"
    assert request["networkConfiguration"] == {
        "awsvpcConfiguration": {
            "subnets": ["subnet-123"],
            "securityGroups": ["sg-123"],
            "assignPublicIp": "ENABLED",
        }
    }
    assert {tag["key"]: tag["value"] for tag in request["tags"]} == {
        "environment": "test",
        "beaker-session": "session-123",
        "beakerhub-process": "true",
        "beakerhub-process-type": "service",
    }
    shared_runtime.ecs_client.register_task_definition.assert_not_called()


async def test_start_registers_and_reuses_an_image_specific_definition():
    shared_runtime = runtime()
    shared_runtime.ecs_client.list_task_definitions = Mock(
        return_value={"taskDefinitionArns": []}
    )
    shared_runtime.ecs_client.register_task_definition = Mock(
        return_value={"taskDefinition": {"taskDefinitionArn": "definition-arn"}}
    )
    shared_runtime.ecs_client.run_task = Mock(
        return_value={"tasks": [{"taskArn": TASK_ARN}]}
    )
    spawner = configured_spawner(runtime=shared_runtime, task_definition="")

    await BeakerAwsECSSpawner.start(spawner)

    registered = shared_runtime.ecs_client.register_task_definition.call_args.kwargs
    assert registered["family"] == (
        "beakerhub-notebook_"
        "d25e4b5db3dca83c3aae6b9fe0d9c3e9fc019ced629567804f94092004ac0316"
    )
    assert registered["containerDefinitions"][0]["image"] == (
        "registry.example/beaker-node:latest"
    )
    assert "environment" not in registered["containerDefinitions"][0]
    existing = {
        **registered,
        "taskDefinitionArn": "definition-arn",
        "revision": 1,
        "status": "ACTIVE",
    }
    shared_runtime.ecs_client.list_task_definitions = Mock(
        return_value={"taskDefinitionArns": ["definition-arn"]}
    )
    shared_runtime.ecs_client.describe_task_definition = Mock(
        return_value={"taskDefinition": existing}
    )
    shared_runtime.ecs_client.register_task_definition.reset_mock()

    await BeakerAwsECSSpawner.start(spawner)

    shared_runtime.ecs_client.register_task_definition.assert_not_called()


async def test_start_validates_fargate_networking_from_the_shared_runtime():
    shared_runtime = runtime(subnets=[])
    spawner = configured_spawner(runtime=shared_runtime, subnets=[])

    with pytest.raises(ValueError, match="subnets"):
        await BeakerAwsECSSpawner.start(spawner)


async def test_capacity_provider_launch_options_omit_launch_type():
    shared_runtime = runtime()
    shared_runtime.ecs_client.run_task = Mock(
        return_value={"tasks": [{"taskArn": TASK_ARN}]}
    )
    spawner = configured_spawner(
        runtime=shared_runtime,
        launch_options={
            "capacityProviderStrategy": [
                {"capacityProvider": "FARGATE", "weight": 1}
            ]
        },
    )

    await BeakerAwsECSSpawner.start(spawner)

    request = shared_runtime.ecs_client.run_task.call_args.kwargs
    assert "launchType" not in request
    assert request["capacityProviderStrategy"] == [
        {"capacityProvider": "FARGATE", "weight": 1}
    ]


async def test_wait_for_task_ip_raises_when_the_task_stops():
    shared_runtime = runtime()
    shared_runtime.ecs_client.describe_tasks = Mock(
        return_value={
            "tasks": [
                {
                    "lastStatus": "STOPPED",
                    "stoppedReason": "CannotPullContainerError",
                    "containers": [
                        {"name": "notebook", "reason": "Image pull failed"}
                    ],
                }
            ]
        }
    )
    spawner = configured_spawner(runtime=shared_runtime)
    process = SimpleNamespace(
        definition=SimpleNamespace(cluster_name="notebooks", container_name="notebook"),
        external_id=TASK_ARN,
    )

    with pytest.raises(RuntimeError, match="Image pull failed"):
        await BeakerAwsECSSpawner._wait_for_task_ip(spawner, process)


async def test_stop_waits_for_ecs_to_deprovision_the_session_task():
    process = SimpleNamespace(
        stop=Mock(),
        await_completion=AsyncMock(),
    )
    spawner = configured_spawner(task_arn=TASK_ARN)
    spawner._process = lambda: process

    await BeakerAwsECSSpawner.stop(spawner)

    process.stop.assert_called_once_with()
    process.await_completion.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ProcessStatus("pending"), None),
        (ProcessStatus("running"), None),
        (ProcessStatus("completed", exit_code=0), 0),
        (ProcessStatus("failed", exit_code=23), 23),
        (ProcessStatus("completed"), 0),
        (ProcessStatus("failed"), 1),
    ],
)
async def test_poll_maps_runtime_status_to_jupyterhub_semantics(status, expected):
    spawner = configured_spawner(task_arn=TASK_ARN)
    spawner._process = lambda: SimpleNamespace(status=status)

    assert await BeakerAwsECSSpawner.poll(spawner) == expected


async def test_poll_reports_stopped_when_no_session_task_was_started():
    spawner = configured_spawner(task_arn=None)

    assert await BeakerAwsECSSpawner.poll(spawner) == 0


def test_state_round_trip_restores_the_session_task_arn():
    shared_runtime = runtime()
    user = SimpleNamespace(settings={"app": SimpleNamespace(runtime=shared_runtime)})
    source = BeakerAwsECSSpawner(
        user=user,
        task_definition="beaker-notebook:3",
        container_name="notebook",
    )
    source.task_arn = TASK_ARN
    restored = BeakerAwsECSSpawner(
        user=user,
        task_definition="beaker-notebook:3",
        container_name="notebook",
    )

    restored.load_state(source.get_state())

    assert restored.runtime is shared_runtime
    assert restored.task_arn == TASK_ARN


def test_notebook_config_configures_the_notebook_service(monkeypatch):
    from beakerhub.app import BeakerHub
    from traitlets.config import Config

    class NotebookConfigSpawner:
        log = Mock()

    monkeypatch.setattr(
        BeakerHub,
        "instance",
        classmethod(lambda cls: SimpleNamespace(subdomain_host="notebooks.example.test")),
    )
    BeakerAwsECSSpawner._notebook_config.cache_clear()
    try:
        config_text = BeakerAwsECSSpawner._notebook_config(NotebookConfigSpawner())
    finally:
        BeakerAwsECSSpawner._notebook_config.cache_clear()

    config = Config()
    exec(config_text, {"get_config": lambda: config})

    assert config.BaseBeakerApp.allow_origin_pat == "^notebooks.example.test$"
    assert config.BaseBeakerApp.tornado_settings == {
        "headers": {
            "Content-Security-Policy": (
                "frame-ancestors 'self' notebooks.example.test"
            )
        }
    }
    assert config.BaseBeakerApp.identity_provider_class == (
        "beakerhub.auth.node.BeakerhubNodeIdentityProvider"
    )
    assert config.BaseBeakerApp.authorizer_class == (
        "beakerhub.auth.node.BeakerhubNodeAuthorizer"
    )
    assert config.BaseBeakerApp.secrets_manager_class == (
        "beakerhub.services.secrets.beakerhub.BeakerhubSecretsManager"
    )
    assert config.BeakerhubSecretsManager.policy_override_env_key_suffix == "_secret_policy"
    assert config.FileNotebookManager.notebook_path == ".notebooks"
    assert config.FileNotebookManager.snapshot_path == ".notebooks"


def test_default_runtime_uses_the_application_runtime():
    shared_runtime = runtime()
    user = SimpleNamespace(
        id=1,
        settings={"app": SimpleNamespace(runtime=shared_runtime)},
    )

    spawner = BeakerAwsECSSpawner(
        user=user,
        image="registry.example/beaker-node:latest",
        task_definition="beaker-notebook:3",
        container_name="notebook",
    )

    assert spawner.runtime is shared_runtime
    assert spawner.log_group == "/beakerhub/runtime"
    assert spawner.execution_role_arn.endswith("role/execution")
    assert spawner.task_group == "runtime-group"
    assert spawner.default_task_cpu == "2 vcpu"
    assert spawner.task_definition_name == (
        "beakerhub-notebook_"
        "d25e4b5db3dca83c3aae6b9fe0d9c3e9fc019ced629567804f94092004ac0316"
    )
