"""Tests for ECS runtime process construction and control-plane behavior."""

from unittest.mock import Mock

import boto3

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


def test_process_uses_runtime_defaults_and_allows_process_overrides():
    runtime = ecs_runtime()
    definition = AwsEcsDefinition(task_definition="notebook:1")

    process = AwsEcsProcess(definition, runtime=runtime)
    overridden = AwsEcsProcess(
        definition,
        runtime=runtime,
        cluster_name="process-cluster",
        subnets=["subnet-process"],
    )

    assert process.cluster_name == "runtime-cluster"
    assert process.subnets == ["subnet-runtime"]
    assert process.security_groups == ["sg-runtime"]
    assert process.log_group == "/beakerhub/runtime"
    assert process.launch_options == {"enableExecuteCommand": True}
    assert overridden.cluster_name == "process-cluster"
    assert overridden.subnets == ["subnet-process"]

    process.subnets.append("local-change")
    assert runtime.subnets == ["subnet-runtime"]


def test_fixed_definition_launch_uses_runtime_networking_and_process_metadata():
    runtime = ecs_runtime()
    runtime.ecs_client.run_task = Mock(
        return_value={"tasks": [{"taskArn": "task-arn"}]}
    )
    runtime.ecs_client.register_task_definition = Mock()

    process = AwsEcsProcess.start(
        AwsEcsDefinition(
            task_definition="notebook:1",
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


def test_dynamic_definition_resources_override_runtime_defaults():
    runtime = ecs_runtime(
        default_task_cpu="2 vcpu",
        default_task_memory="8GB",
        default_task_ephemeral_storage=40,
    )
    runtime.ecs_client.register_task_definition = Mock(
        return_value={"taskDefinition": {"taskDefinitionArn": "definition-arn"}}
    )
    process = AwsEcsProcess(
        AwsEcsDefinition(
            image="example:latest",
            cpu="1 vcpu",
            memory="2GB",
            ephemeral_storage=25,
        ),
        runtime=runtime,
    )

    assert process._register_task_definition() == "definition-arn"

    request = runtime.ecs_client.register_task_definition.call_args.kwargs
    assert request["cpu"] == "1 vcpu"
    assert request["memory"] == "2GB"
    assert request["ephemeralStorage"] == {"sizeInGiB": 25}


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
