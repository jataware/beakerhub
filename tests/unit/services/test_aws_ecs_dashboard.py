"""Tests for the ECS dashboard service."""

from unittest.mock import MagicMock

import boto3

from traitlets.config import LoggingConfigurable

from beakerhub.runtimes.aws_ecs import AwsEcsRuntime
from beakerhub.services.dashboard.aws_ecs_dashboard import AwsEcsDashboardService


def make_service():
    ecs_client = boto3.client(
        "ecs",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    logs_client = boto3.client(
        "logs",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    runtime = AwsEcsRuntime(
        aws_region="us-east-1",
        cluster_name="beakerhub",
        log_group="/beakerhub/sessions",
        log_stream_prefix="beakerhub",
        ecs_client=ecs_client,
        logs_client=logs_client,
    )
    for method in (
        "describe_clusters", "list_services", "describe_services", "list_tasks",
        "describe_tasks", "list_container_instances", "describe_container_instances",
    ):
        setattr(runtime.ecs_client, method, MagicMock())
    runtime.logs_client.get_log_events = MagicMock()
    parent = LoggingConfigurable()
    parent.runtime = runtime
    return AwsEcsDashboardService(parent=parent), runtime


def test_dashboard_returns_provider_neutral_runtime_information():
    service, runtime = make_service()
    runtime.ecs_client.describe_clusters.return_value = {
        "clusters": [{"clusterArn": "arn:aws:ecs:region:account:cluster/beakerhub"}]
    }
    runtime.ecs_client.list_services.return_value = {"serviceArns": ["service-arn"]}
    runtime.ecs_client.describe_services.return_value = {
        "services": [
            {
                "serviceName": "sessions",
                "status": "ACTIVE",
                "runningCount": 2,
                "desiredCount": 2,
            }
        ]
    }
    runtime.ecs_client.list_tasks.return_value = {"taskArns": ["task-arn"]}
    runtime.ecs_client.describe_tasks.return_value = {
        "tasks": [
            {
                "taskArn": "task-arn",
                "group": "service:sessions",
                "lastStatus": "RUNNING",
            }
        ]
    }
    runtime.ecs_client.list_container_instances.return_value = {
        "containerInstanceArns": []
    }

    result = service.get_dashboard()

    assert result["available"] is True
    assert result["runtime"] == {"provider": "Amazon ECS", "scope": "beakerhub"}
    assert result["summary"][0]["label"] == "Services"
    assert result["summary"][2]["detail"] == (
        "Compute is managed by AWS Fargate. This cluster has no registered "
        "container instances."
    )
    assert result["resources_empty_message"] == (
        "AWS Fargate manages the underlying compute resources. Per-instance "
        "capacity is not available."
    )
    assert result["workloads"][0]["name"] == "sessions"
    assert result["workloads"][0]["kind"] == "Service"
    assert result["workloads"][0]["status"] == "active"
    assert result["workloads"][0]["detail"] == "2 running / 2 desired"
    assert result["workloads"][0]["children"] == [
        {
            "name": "task-arn",
            "kind": "Task",
            "status": "running",
            "detail": "",
        }
    ]


def test_dashboard_reports_recent_stopped_tasks_that_failed():
    service, runtime = make_service()
    runtime.ecs_client.describe_clusters.return_value = {
        "clusters": [{"clusterArn": "arn:aws:ecs:region:account:cluster/beakerhub"}]
    }
    runtime.ecs_client.list_services.return_value = {"serviceArns": []}
    runtime.ecs_client.list_tasks.side_effect = [
        {"taskArns": []},
        {"taskArns": ["failed-task"]},
    ]
    runtime.ecs_client.describe_tasks.return_value = {
        "tasks": [
            {
                "taskArn": "failed-task",
                "lastStatus": "STOPPED",
                "stoppedReason": "Essential container exited",
                "containers": [{"exitCode": 1}],
            }
        ]
    }
    runtime.ecs_client.list_container_instances.return_value = {
        "containerInstanceArns": []
    }

    result = service.get_dashboard()

    assert result["summary"][1]["detail"] == "0 running, 0 pending, 1 failed"
    assert result["summary"][1]["severity"] == "danger"
    assert result["alerts"][0]["object"] == "failed-task"


def test_dashboard_does_not_report_user_stopped_tasks_as_failures():
    service, _ = make_service()

    assert service._failed_tasks(
        [{"stopCode": "UserInitiated", "containers": [{"exitCode": 137}]}]
    ) == []


def test_dashboard_reports_task_start_failures_without_container_exit_codes():
    service, _ = make_service()

    assert service._failed_tasks([{"stopCode": "TaskFailedToStart", "containers": []}])


def test_session_logs_uses_the_task_container_when_notebook_is_requested():
    service, runtime = make_service()
    task_arn = "arn:aws:ecs:region:account:task/beakerhub/task-id"
    runtime.ecs_client.describe_tasks.return_value = {
        "tasks": [
            {
                "taskArn": task_arn,
                "containers": [{"name": "task-container"}],
            }
        ]
    }
    runtime.logs_client.get_log_events.side_effect = [
        {"events": [{"message": "second"}], "nextBackwardToken": "previous"},
        {"events": [{"message": "first"}], "nextBackwardToken": "previous"},
    ]

    result = service.get_session_logs(task_arn, "notebook", 5000)

    assert result["runtime_name"] == "task-id"
    assert result["container"] == "task-container"
    assert result["logs"] == "first\nsecond"
    assert result["truncated"] is False
    runtime.logs_client.get_log_events.assert_called_with(
        logGroupName="/beakerhub/sessions",
        logStreamName="beakerhub/task-container/task-id",
        startFromHead=False,
        limit=4999,
        nextToken="previous",
    )
