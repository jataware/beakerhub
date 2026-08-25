"""Unit tests for the ECS control-plane spawner scaffold.

These use botocore's request-validating Stubber rather than Docker: they are
fast tests for the ECS contract.  A future LocalStack suite should cover actual
container execution separately.
"""

from types import SimpleNamespace

import boto3
import pytest
from botocore.stub import Stubber

from beakerhub.services.spawner.aws_ecs_spawner import BeakerAwsECSSpawner


TASK_ARN = "arn:aws:ecs:us-east-1:123456789012:task/test/task-123"


def configured_spawner(**overrides):
    """A minimal object sufficient to exercise unbound ECS-spawner methods."""
    values = {
        "cluster_name": "notebooks",
        "task_definition": "beaker-notebook:3",
        "container_name": "notebook",
        "container_tags": {"environment": "test"},
        "session_id": "session-123",
        "subnets": ["subnet-123"],
        "security_groups": ["sg-123"],
        "assign_public_ip": True,
        "fargate": True,
        "volume_configs": [],
        "get_env": lambda: {"BEAKERHUB_USER": "ada", "NUMBER": 2},
    }
    values.update(overrides)
    spawner = SimpleNamespace(**values)
    spawner._task_tags = lambda: BeakerAwsECSSpawner._task_tags(spawner)
    spawner._network_configuration = lambda: BeakerAwsECSSpawner._network_configuration(spawner)
    return spawner


def test_run_task_request_contains_environment_tags_and_fargate_networking():
    spawner = configured_spawner()

    request = BeakerAwsECSSpawner._run_task_request(spawner)

    assert request == {
        "cluster": "notebooks",
        "taskDefinition": "beaker-notebook:3",
        "count": 1,
        "launchType": "FARGATE",
        "networkConfiguration": {
            "awsvpcConfiguration": {
                "subnets": ["subnet-123"],
                "securityGroups": ["sg-123"],
                "assignPublicIp": "ENABLED",
            }
        },
        "overrides": {
            "containerOverrides": [{
                "name": "notebook",
                "environment": [
                    {"name": "BEAKERHUB_USER", "value": "ada"},
                    {"name": "NUMBER", "value": "2"},
                ],
            }]
        },
        "tags": [
            {"key": "environment", "value": "test"},
            {"key": "beaker-session", "value": "session-123"},
        ],
    }


def test_session_tag_cannot_be_overridden_by_configuration():
    spawner = configured_spawner(container_tags={"beaker-session": "incorrect"})

    assert BeakerAwsECSSpawner._task_tags(spawner) == [
        {"key": "beaker-session", "value": "session-123"}
    ]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"task_definition": ""}, "task_definition"),
        ({"container_name": ""}, "container_name"),
        ({"subnets": []}, "subnets"),
    ],
)
def test_run_task_request_rejects_incomplete_fargate_configuration(overrides, message):
    spawner = configured_spawner(**overrides)

    with pytest.raises(ValueError, match=message):
        BeakerAwsECSSpawner._run_task_request(spawner)


def test_start_stop_and_poll_use_ecs_control_plane():
    client = boto3.client(
        "ecs",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    request = {"cluster": "notebooks", "taskDefinition": "beaker-notebook:3", "count": 1}
    spawner = configured_spawner(boto=client, task_arn=None)
    spawner._run_task_request = lambda: request

    with Stubber(client) as stubber:
        stubber.add_response("run_task", {"tasks": [{"taskArn": TASK_ARN}]}, request)
        BeakerAwsECSSpawner.start(spawner)
        assert spawner.task_arn == TASK_ARN

        stubber.add_response(
            "describe_tasks",
            {"tasks": [{"taskArn": TASK_ARN, "lastStatus": "RUNNING"}]},
            {"cluster": "notebooks", "tasks": [TASK_ARN]},
        )
        assert BeakerAwsECSSpawner.poll(spawner) is None

        stubber.add_response(
            "stop_task",
            {"task": {"taskArn": TASK_ARN, "lastStatus": "STOPPED"}},
            {
                "cluster": "notebooks",
                "task": TASK_ARN,
                "reason": "Stopped by BeakerHub server",
            },
        )
        BeakerAwsECSSpawner.stop(spawner)


def test_poll_returns_container_exit_code_for_stopped_task():
    client = boto3.client(
        "ecs", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test"
    )
    spawner = configured_spawner(boto=client, task_arn=TASK_ARN)
    with Stubber(client) as stubber:
        stubber.add_response(
            "describe_tasks",
            {
                "tasks": [{
                    "taskArn": TASK_ARN,
                    "lastStatus": "STOPPED",
                    "containers": [{"name": "notebook", "exitCode": 23}],
                }]
            },
            {"cluster": "notebooks", "tasks": [TASK_ARN]},
        )
        assert BeakerAwsECSSpawner.poll(spawner) == 23
