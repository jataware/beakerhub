"""Tests for BeakerHub service selection and task delegation."""

from unittest.mock import MagicMock

from traitlets.config import Config

from beakerhub.app import BeakerHub
from beakerhub.services.dashboard.base import BaseDashboardService
from beakerhub.services.task.base import BaseTaskRunnerService
from beakerhub.tasks.image_import.task import launch_import_task


class DummyTaskRunnerService(BaseTaskRunnerService):
    """Task runner used to verify application service selection."""


class DummyDashboardService(BaseDashboardService):
    """Dashboard service used to verify application service selection."""


def test_application_instantiates_configured_services():
    config = Config()
    config.BeakerHub.task_runner_class = DummyTaskRunnerService
    config.BeakerHub.dashboard_service_class = DummyDashboardService

    app = BeakerHub(config=config)

    assert isinstance(app.task_runner, DummyTaskRunnerService)
    assert app.task_runner.parent is app
    assert isinstance(app.dashboard_service, DummyDashboardService)
    assert app.dashboard_service.parent is app


def test_application_registers_service_classes():
    app = BeakerHub()

    assert BaseTaskRunnerService in app.classes
    assert BaseDashboardService in app.classes


def test_task_runner_receives_config_loaded_after_its_creation():
    app = BeakerHub()
    runner = app.task_runner
    config = Config()
    config.KubernetesTaskRunnerService.reporter_image = "registry.example/reporter:v1"

    app.update_config(config)

    assert runner.reporter_image == "registry.example/reporter:v1"


def test_image_import_delegates_submission_to_task_runner():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    node_image = MagicMock(id=12, slug="example")
    app = MagicMock(hub_connect_url="http://hub.internal")
    app.task_runner.submit_image_import.return_value = "external-task-id"

    task = launch_import_task(db, app, node_image)

    app.task_runner.submit_image_import.assert_called_once()
    assert task.job_name == "external-task-id"
    assert task.status == "running"
    assert db.commit.call_count == 2
