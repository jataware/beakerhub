"""Tests for dashboard handler data enrichment."""

from unittest.mock import MagicMock

from beakerhub.services.dashboard.handlers import AdminDashboardClusterHandler


def test_dashboard_task_rows_include_the_owned_session():
    spawner = MagicMock()
    spawner.state = {
        "task_arn": "arn:aws:ecs:us-east-1:123456789:task/cluster/task-id"
    }
    spawner.user.name = "ada"
    spawner.name = "analysis"

    handler = MagicMock()
    handler.db.query.return_value.join.return_value.filter.return_value.all.return_value = [
        spawner
    ]
    dashboard = {
        "workloads": [
            {
                "name": "notebook-service",
                "kind": "Service",
                "children": [
                    {"name": "task-id", "kind": "Task"},
                ],
            }
        ]
    }

    AdminDashboardClusterHandler._add_task_sessions(handler, dashboard)

    assert dashboard["workloads"][0]["children"][0]["sessions"] == [
        {"user": "ada", "name": "analysis"}
    ]
