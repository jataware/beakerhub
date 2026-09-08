"""Tests for the ECS task-runner runtime adapter."""

from dataclasses import dataclass
from unittest.mock import Mock

import boto3

from beakerhub.runtimes.aws_ecs import AwsEcsRuntime
from beakerhub.services.task.aws_ecs_task_runner import AwsEcsTaskRunnerService
from beakerhub.tasks.base import BaseImageTask


@dataclass(frozen=True)
class ExampleImageTask(BaseImageTask):
    @property
    def task_type(self) -> str:
        return "example"


def runtime(**overrides) -> AwsEcsRuntime:
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
        "execution_role_arn": "arn:aws:iam::123456789012:role/execution",
        "task_role_arn": "arn:aws:iam::123456789012:role/task",
        "launch_options": {"enableExecuteCommand": True},
    }
    values.update(overrides)
    return AwsEcsRuntime(**values)


def test_runner_defaults_to_the_shared_runtime_configuration():
    shared_runtime = runtime()
    runner = AwsEcsTaskRunnerService(runtime=shared_runtime)

    assert runner.runtime is shared_runtime
    assert runner.cluster_name == "runtime-cluster"
    assert runner.subnets == ["subnet-runtime"]
    assert runner.security_groups == ["sg-runtime"]
    assert runner.log_group == "/beakerhub/runtime"
    assert runner.execution_role_arn.endswith("role/execution")
    assert runner.launch_options == {"enableExecuteCommand": True}


def test_submit_builds_a_runtime_definition_and_launches_the_process():
    shared_runtime = runtime()
    shared_runtime.ecs_client.list_task_definitions = Mock(
        return_value={"taskDefinitionArns": []}
    )
    shared_runtime.ecs_client.register_task_definition = Mock(
        return_value={"taskDefinition": {"taskDefinitionArn": "definition-arn"}}
    )
    shared_runtime.ecs_client.run_task = Mock(
        return_value={"tasks": [{"taskArn": "task-arn"}]}
    )
    runner = AwsEcsTaskRunnerService(
        runtime=shared_runtime,
        security_groups=["sg-task"],
        assign_public_ip=True,
    )

    process = runner.submit(
        ExampleImageTask(
            image="example:latest",
            environment={"FROM_TASK": "value"},
        )
    )

    assert process.runtime is shared_runtime
    assert process.external_id == "task-arn"
    definition_request = shared_runtime.ecs_client.register_task_definition.call_args.kwargs
    assert definition_request["executionRoleArn"].endswith("role/execution")
    assert definition_request["taskRoleArn"].endswith("role/task")
    task_request = shared_runtime.ecs_client.run_task.call_args.kwargs
    assert task_request["cluster"] == "runtime-cluster"
    assert task_request["networkConfiguration"] == {
        "awsvpcConfiguration": {
            "subnets": ["subnet-runtime"],
            "securityGroups": ["sg-task"],
            "assignPublicIp": "ENABLED",
        }
    }
    assert task_request["overrides"]["containerOverrides"] == [
        {
            "name": "task-container",
            "environment": [{"name": "FROM_TASK", "value": "value"}],
        }
    ]
    assert {tag["key"]: tag["value"] for tag in task_request["tags"]} == {
        "beakerhub/task-type": "example",
        "beakerhub-process": "true",
        "beakerhub-process-type": "task",
    }


def test_runner_overrides_are_used_when_reconstructing_a_process():
    shared_runtime = runtime()
    runner = AwsEcsTaskRunnerService(
        runtime=shared_runtime,
        cluster_name="task-cluster",
        log_group="/beakerhub/tasks",
        task_overrides={"cpu": "512"},
    )

    process = runner.get_process("task-arn")

    assert process.runtime is shared_runtime
    assert process.external_id == "task-arn"
    assert process.definition.cluster_name == "task-cluster"
    assert process.definition.log_group == "/beakerhub/tasks"
    assert process.definition.task_overrides == {"cpu": "512"}
