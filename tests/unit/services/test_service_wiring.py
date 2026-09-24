"""Tests for BeakerHub service selection and task delegation."""

from unittest.mock import MagicMock

from traitlets.config import Config

from beakerhub.app import BeakerHub
from beakerhub.runtimes.aws_ecs import AwsEcsRuntime, AwsEcsRuntimeBundle
from beakerhub.runtimes.kubernetes import KubernetesRuntime, KubernetesRuntimeBundle
from beakerhub.services.dashboard.aws_ecs_dashboard import AwsEcsDashboardService
from beakerhub.services.dashboard.base import BaseDashboardService
from beakerhub.services.dashboard.kubernetes_dashboard import KubernetesDashboardService
from beakerhub.services.task.aws_ecs_task_runner import AwsEcsTaskRunnerService
from beakerhub.services.task.kubernetes_task_runner import KubernetesTaskRunnerService
from beakerhub.services.task.base import BaseTaskRunnerService
from beakerhub.tasks.image_import.task import ImageImportTask, launch_import_task


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


def test_runtime_bundle_selects_services_with_application_owned_runtime():
    config = Config()
    config.BeakerHub.runtime_bundle_class = KubernetesRuntimeBundle
    config.KubernetesRuntime.namespace = "configured-runtime"
    config.KubernetesRuntime.node_selector = {"pool": "compute"}
    config.KubernetesRuntime.tolerations = [{"key": "dedicated", "operator": "Exists"}]
    config.KubernetesRuntime.service_account = "runtime-workload"
    config.KubernetesRuntime.base_labels = {"environment": "test"}

    app = BeakerHub(config=config)

    assert isinstance(app.runtime_bundle, KubernetesRuntimeBundle)
    assert app.runtime.parent is app
    assert app.runtime.namespace == "configured-runtime"
    assert app.runtime.node_selector == {"pool": "compute"}
    assert app.runtime.tolerations == [{"key": "dedicated", "operator": "Exists"}]
    assert app.runtime.service_account == "runtime-workload"
    assert app.runtime.base_labels == {"environment": "test"}
    assert isinstance(app.task_runner, KubernetesTaskRunnerService)
    assert app.task_runner.runtime is app.runtime
    assert isinstance(app.dashboard_service, KubernetesDashboardService)
    assert app.dashboard_service._runtime() is app.runtime
    assert app.spawner_class.__name__ == "BeakerKubeSpawner"


def test_ecs_runtime_bundle_selects_ecs_services_and_runtime_values():
    config = Config()
    config.BeakerHub.runtime_bundle_class = AwsEcsRuntimeBundle
    config.AwsEcsRuntime.aws_region = "us-west-2"
    config.AwsEcsRuntime.cluster_name = "configured-cluster"
    config.AwsEcsRuntime.subnets = ["subnet-123"]
    config.AwsEcsRuntime.log_group = "/beakerhub/ecs"

    app = BeakerHub(config=config)

    assert isinstance(app.runtime, AwsEcsRuntime)
    assert app.runtime.parent is app
    assert app.runtime.aws_region == "us-west-2"
    assert app.runtime.cluster_name == "configured-cluster"
    assert app.runtime.subnets == ["subnet-123"]
    assert app.runtime.log_group == "/beakerhub/ecs"
    assert isinstance(app.task_runner, AwsEcsTaskRunnerService)
    assert app.task_runner.runtime is app.runtime
    assert isinstance(app.dashboard_service, AwsEcsDashboardService)
    assert app.spawner_class.__name__ == "BeakerAwsECSSpawner"


def test_runtime_bundle_runtime_receives_late_configuration_updates():
    config = Config()
    config.BeakerHub.runtime_bundle_class = KubernetesRuntimeBundle
    app = BeakerHub(config=config)
    runtime = app.runtime

    update = Config()
    update.KubernetesRuntime.namespace = "updated-runtime"
    update.KubernetesRuntime.node_selector = {"pool": "updated"}
    app.update_config(update)

    assert runtime.namespace == "updated-runtime"
    assert runtime.node_selector == {"pool": "updated"}


def test_default_runtime_is_kubernetes_without_a_bundle():
    app = BeakerHub()

    assert isinstance(app.runtime, KubernetesRuntime)
    assert app.runtime_bundle is None


def test_task_runner_receives_config_loaded_after_its_creation():
    app = BeakerHub()
    runner = app.task_runner
    config = Config()
    config.KubernetesTaskRunnerService.node_image_resources = {
        "limits": {"cpu": "1"}
    }

    app.update_config(config)

    assert runner.node_image_resources == {"limits": {"cpu": "1"}}


def test_image_import_delegates_submission_to_task_runner():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    node_image = MagicMock(id=12, slug="example")
    app = MagicMock(hub_connect_url="http://hub.internal")
    app.task_runner.submit.return_value = MagicMock(external_id="external-task-id")

    task = launch_import_task(db, app, node_image)

    app.task_runner.submit.assert_called_once()
    submitted_task = app.task_runner.submit.call_args.args[0]
    assert isinstance(submitted_task, ImageImportTask)
    assert submitted_task.node_image is node_image
    assert submitted_task.image == node_image.default_img_string
    assert submitted_task.entrypoint == ("sh", "-c")
    assert submitted_task.command == ("beaker context dump",)
    assert task.job_name == "external-task-id"
    assert task.status == "running"
    assert db.commit.call_count == 2
