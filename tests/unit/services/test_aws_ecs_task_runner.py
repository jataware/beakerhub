"""Tests for the ECS task-runner task-definition configuration."""

from dataclasses import dataclass
from unittest.mock import Mock

import boto3
import pytest

from beakerhub.services.task.aws_ecs_task_runner import AwsEcsTaskRunnerService
from beakerhub.tasks.base import BaseImageTask


@dataclass(frozen=True)
class ExampleImageTask(BaseImageTask):
    @property
    def task_type(self) -> str:
        return "example"


def test_task_definition_includes_configured_iam_roles():
    ecs = boto3.client(
        "ecs",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    ecs.register_task_definition = Mock(
        return_value={
            "taskDefinition": {"taskDefinitionArn": "task-definition-arn"}
        }
    )
    runner = AwsEcsTaskRunnerService(
        boto_client=ecs,
        log_group="/beakerhub/tasks",
        execution_role_arn="arn:aws:iam::123456789012:role/ecs-task-execution",
        task_role_arn="arn:aws:iam::123456789012:role/beakerhub-task",
    )

    assert runner._register_task_definition(ExampleImageTask(image="example:latest")) == (
        "task-definition-arn"
    )

    request = ecs.register_task_definition.call_args.kwargs
    assert request["executionRoleArn"] == (
        "arn:aws:iam::123456789012:role/ecs-task-execution"
    )
    assert request["taskRoleArn"] == "arn:aws:iam::123456789012:role/beakerhub-task"


def configured_runner(**overrides):
    values = {
        "cluster_name": "tasks",
        "log_group": "/beakerhub/tasks",
        "aws_region": "us-east-1",
        "execution_role_arn": "arn:aws:iam::123456789012:role/ecs-task-execution",
        "subnets": ["subnet-123"],
    }
    values.update(overrides)
    return AwsEcsTaskRunnerService(**values)


def test_submit_uses_configured_fargate_networking():
    ecs = boto3.client(
        "ecs",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    ecs.run_task = Mock(return_value={"tasks": [{"taskArn": "task-arn"}]})
    runner = configured_runner(
        boto_client=ecs,
        security_groups=["sg-123"],
        assign_public_ip=True,
    )
    runner._register_task_definition = Mock(return_value="task-definition-arn")

    runner.submit(ExampleImageTask(image="example:latest"))

    request = ecs.run_task.call_args.kwargs
    assert request["networkConfiguration"] == {
        "awsvpcConfiguration": {
            "subnets": ["subnet-123"],
            "securityGroups": ["sg-123"],
            "assignPublicIp": "ENABLED",
        }
    }


def test_task_definition_uses_configured_cpu_architecture():
    ecs = boto3.client(
        "ecs",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    ecs.register_task_definition = Mock(
        return_value={"taskDefinition": {"taskDefinitionArn": "task-definition-arn"}}
    )
    runner = configured_runner(boto_client=ecs, cpu_architecture="ARM64")

    runner._register_task_definition(ExampleImageTask(image="example:latest"))

    request = ecs.register_task_definition.call_args.kwargs
    assert request["runtimePlatform"]["cpuArchitecture"] == "ARM64"


def test_task_overrides_merge_the_task_container_environment():
    runner = configured_runner(
        task_overrides={
            "containerOverrides": [
                {
                    "name": "task-container",
                    "command": ["configured-command"],
                    "environment": [
                        {"name": "FROM_CONFIG", "value": "configured"},
                        {"name": "SHARED", "value": "configured"},
                    ],
                },
                {"name": "sidecar", "command": ["sidecar-command"]},
            ]
        }
    )

    overrides = runner._build_overrides(
        ExampleImageTask(
            image="example:latest",
            environment={"SHARED": "task", "FROM_TASK": "task"},
        )
    )

    assert overrides["containerOverrides"] == [
        {"name": "sidecar", "command": ["sidecar-command"]},
        {
            "name": "task-container",
            "command": ["configured-command"],
            "environment": [
                {"name": "FROM_CONFIG", "value": "configured"},
                {"name": "SHARED", "value": "task"},
                {"name": "FROM_TASK", "value": "task"},
            ],
        },
    ]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"cluster_name": ""}, "cluster_name"),
        ({"log_group": ""}, "log_group"),
        ({"aws_region": ""}, "aws_region"),
        ({"execution_role_arn": ""}, "execution_role_arn"),
        ({"subnets": []}, "subnets"),
        (
            {"launch_type": "EC2"},
            "default_task_ephemeral_storage",
        ),
        (
            {
                "launch_type": "MANAGED_INSTANCES",
                "default_task_ephemeral_storage": 0,
            },
            "capacityProviderStrategy",
        ),
    ],
)
def test_configuration_validation_rejects_incompatible_settings(overrides, message):
    runner = configured_runner(**overrides)

    with pytest.raises(ValueError, match=message):
        runner._validate_configuration()
