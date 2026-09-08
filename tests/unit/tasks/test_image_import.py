"""Tests for node-image import task definition behavior."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from beakerhub.runtimes.base import ProcessOutput, ProcessStatus
from beakerhub.tasks.image_import.task import ImageImportTask


def node_image():
    return SimpleNamespace(default_img_string="registry.example/node:latest")


def test_from_node_image_builds_the_standard_context_dump_workload():
    task = ImageImportTask.from_node_image(node_image())

    assert task.image == "registry.example/node:latest"
    assert task.entrypoint == ("sh", "-c")
    assert task.command == ("beaker context dump",)
    assert task.task_type == "context_import"


def test_on_success_ingests_output_into_the_persisted_task():
    node = node_image()
    definition = ImageImportTask.from_node_image(node)
    persisted_task = SimpleNamespace(result=None)
    db = Mock()
    output = ProcessOutput('{"contexts": []}', "")

    with (
        patch(
            "beakerhub.tasks.image_import.task.object_session", return_value=db
        ),
        patch(
            "beakerhub.tasks.image_import.task.ingest_import_output",
            return_value={"contexts": 1},
        ) as ingest,
    ):
        definition.on_success(persisted_task, ProcessStatus("completed"), output)

    ingest.assert_called_once_with(db, node, output)
    assert persisted_task.result == {"contexts": 1}


def test_on_failure_stores_runtime_diagnostics():
    definition = ImageImportTask.from_node_image(node_image())
    persisted_task = SimpleNamespace(error=None)

    definition.on_failure(
        persisted_task,
        ProcessStatus("failed", "Container exited unsuccessfully"),
        ProcessOutput("", "Import command failed"),
    )

    assert persisted_task.error == "Container exited unsuccessfully. Import command failed"
