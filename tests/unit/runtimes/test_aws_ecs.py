"""Tests for ECS runtime process construction and control-plane behavior."""

import re
from unittest.mock import Mock

import boto3
import pytest

from beakerhub.runtimes.aws_ecs import (
    AwsEcsDefinition,
    AwsEcsProcess,
    AwsEcsRuntime,
)


def ecs_runtime(**overrides):
    ecs = boto3.client(
        "ecs",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    logs = boto3.client(
        "logs",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    values = {
        "ecs_client": ecs,
        "logs_client": logs,
        "cluster_name": "runtime-cluster",
        "subnets": ["subnet-runtime"],
        "security_groups": ["sg-runtime"],
        "log_group": "/beakerhub/runtime",
        "launch_options": {"enableExecuteCommand": True},
    }
    values.update(overrides)
    return AwsEcsRuntime(**values)


def test_definition_uses_runtime_defaults_and_allows_definition_overrides():
    runtime = ecs_runtime()
    definition = AwsEcsDefinition(
        image="example:latest",
        task_definition_arn="notebook:1",
        runtime=runtime,
    )
    overridden = AwsEcsDefinition(
        image="example:latest",
        task_definition_arn="notebook:1",
        runtime=runtime,
        cluster_name="definition-cluster",
        subnets=["subnet-definition"],
    )

    assert definition.cluster_name == "runtime-cluster"
    assert definition.subnets == ["subnet-runtime"]
    assert definition.security_groups == ["sg-runtime"]
    assert definition.log_group == "/beakerhub/runtime"
    assert definition.launch_options == {"enableExecuteCommand": True}
    assert overridden.cluster_name == "definition-cluster"
    assert overridden.subnets == ["subnet-definition"]

    definition.subnets.append("local-change")
    assert runtime.subnets == ["subnet-runtime"]


def test_dynamic_task_definition_family_is_ecs_safe_and_unique():
    runtime = ecs_runtime(task_definition_name="beaker.hub/tasks")
    digest = "a" * 300
    definition = AwsEcsDefinition(
        image=f"registry.example/notebook@sha256:{digest}",
        runtime=runtime,
    )
    similar = AwsEcsDefinition(
        image="registry.example/notebook.sha256:latest",
        runtime=runtime,
    )

    assert len(definition.task_definition_name) <= 255
    assert re.fullmatch(r"[A-Za-z0-9_-]+", definition.task_definition_name)
    assert definition.task_definition_name != similar.task_definition_name


def test_fixed_definition_launch_uses_runtime_networking_and_process_metadata():
    runtime = ecs_runtime()
    runtime.ecs_client.run_task = Mock(
        return_value={"tasks": [{"taskArn": "task-arn"}]}
    )
    runtime.ecs_client.register_task_definition = Mock()

    process = AwsEcsProcess.start(
        AwsEcsDefinition(
            image="notebook:latest",
            task_definition_arn="notebook:1",
            container_name="notebook",
            environment={"BEAKERHUB_USER": "ada"},
            tags={"beaker-session": "session-1"},
        ),
        process_type="service",
        runtime=runtime,
    )

    assert process.external_id == "task-arn"
    runtime.ecs_client.register_task_definition.assert_not_called()
    request = runtime.ecs_client.run_task.call_args.kwargs
    assert request["cluster"] == "runtime-cluster"
    assert request["networkConfiguration"] == {
        "awsvpcConfiguration": {
            "subnets": ["subnet-runtime"],
            "securityGroups": ["sg-runtime"],
            "assignPublicIp": "DISABLED",
        }
    }
    assert request["overrides"]["containerOverrides"] == [
        {
            "name": "notebook",
            "environment": [{"name": "BEAKERHUB_USER", "value": "ada"}],
        }
    ]
    assert {tag["key"]: tag["value"] for tag in request["tags"]} == {
        "beaker-session": "session-1",
        "beakerhub-process": "true",
        "beakerhub-process-type": "service",
    }


def test_dynamic_definition_includes_volumes_and_container_mount_points():
    definition = AwsEcsDefinition(
        image="example:latest",
        runtime=ecs_runtime(),
        volumes=[
            {
                "name": "user-storage",
                "efsVolumeConfiguration": {"fileSystemId": "fs-12345678"},
            }
        ],
        mount_points=[
            {
                "sourceVolume": "user-storage",
                "containerPath": "/home/beaker",
                "readOnly": False,
            }
        ],
    )

    task_definition = definition.aws_task_definition

    assert task_definition["volumes"] == definition.volumes
    assert task_definition["containerDefinitions"][0]["mountPoints"] == (
        definition.mount_points
    )


def test_dynamic_definition_resources_override_runtime_defaults():
    runtime = ecs_runtime(
        default_task_cpu="2 vcpu",
        default_task_memory="8GB",
        default_task_ephemeral_storage=40,
    )
    runtime.ecs_client.list_task_definitions = Mock(
        return_value={"taskDefinitionArns": []}
    )
    runtime.ecs_client.register_task_definition = Mock(
        return_value={"taskDefinition": {"taskDefinitionArn": "definition-arn"}}
    )
    runtime.ecs_client.run_task = Mock(
        return_value={"tasks": [{"taskArn": "task-arn"}]}
    )
    process = AwsEcsProcess.start(
        AwsEcsDefinition(
            image="example:latest",
            cpu="1 vcpu",
            memory="2GB",
            ephemeral_storage=25,
        ),
        runtime=runtime,
    )

    assert process.external_id == "task-arn"

    request = runtime.ecs_client.register_task_definition.call_args.kwargs
    assert request["cpu"] == "1 vcpu"
    assert request["memory"] == "2GB"
    assert request["ephemeralStorage"] == {"sizeInGiB": 25}


def test_definition_reuses_a_matching_task_definition():
    runtime = ecs_runtime()
    definition = AwsEcsDefinition(image="example:latest", runtime=runtime)
    existing = {
        **definition.aws_task_definition,
        "taskDefinitionArn": "definition-arn",
        "revision": 1,
        "status": "ACTIVE",
        "compatibilities": ["EC2", "FARGATE"],
        "requiresAttributes": [],
    }
    runtime.ecs_client.list_task_definitions = Mock(
        return_value={"taskDefinitionArns": ["definition-arn"]}
    )
    runtime.ecs_client.describe_task_definition = Mock(
        return_value={"taskDefinition": existing}
    )
    runtime.ecs_client.register_task_definition = Mock()

    assert definition.find_or_register_task_definition() == "definition-arn"
    runtime.ecs_client.register_task_definition.assert_not_called()



@pytest.mark.parametrize(
    ("runtime_values", "message"),
    [
        ({"cluster_name": ""}, "cluster_name"),
        ({"subnets": []}, "subnets"),
        ({"launch_type": "EC2"}, "ephemeral_storage"),
        (
            {
                "launch_type": "MANAGED_INSTANCES",
                "default_task_ephemeral_storage": 0,
            },
            "capacityProviderStrategy",
        ),
    ],
)
def test_definition_validates_its_runtime_derived_configuration(
    runtime_values,
    message,
):
    definition = AwsEcsDefinition(
        image="example:latest",
        runtime=ecs_runtime(**runtime_values),
    )

    with pytest.raises(ValueError, match=message):
        definition.validate_configuration()


@pytest.mark.parametrize(
    ("exit_code", "state"),
    [(0, "completed"), (23, "failed")],
)
def test_process_status_preserves_container_exit_code(exit_code, state):
    runtime = ecs_runtime()
    runtime.ecs_client.describe_tasks = Mock(
        return_value={
            "tasks": [
                {
                    "lastStatus": "STOPPED",
                    "containers": [
                        {"name": "task-container", "exitCode": exit_code}
                    ],
                }
            ]
        }
    )
    process = AwsEcsProcess(
        AwsEcsDefinition(image="example:latest", runtime=runtime),
        runtime=runtime,
        external_id="task-arn",
    )

    status = process.describe()

    assert status.state == state
    assert status.exit_code == exit_code


def test_runtime_reads_cloudwatch_log_pages():
    runtime = ecs_runtime()
    runtime.logs_client.get_log_events = Mock(
        side_effect=[
            {
                "events": [{"message": "first"}],
                "nextForwardToken": "next",
            },
            {
                "events": [{"message": "second"}],
                "nextForwardToken": "next",
            },
        ]
    )

    assert runtime.get_log_events("/logs", "stream") == ["first", "second"]
    assert runtime.logs_client.get_log_events.call_count == 2
