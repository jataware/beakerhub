# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""Unit tests for integration-test fixtures."""

import subprocess
from unittest.mock import MagicMock

import pytest

from tests.integration import conftest as integration_conftest


def completed_command(cmd: list[str]) -> subprocess.CompletedProcess:
    """Create a successful command result."""
    return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


def test_cluster_deletes_new_cluster_when_setup_fails(monkeypatch):
    """A setup failure should not leave a newly created cluster running."""
    commands = []

    def run_command(cmd, check=True, capture=True):
        commands.append(cmd)
        if cmd[0] == "helm":
            raise subprocess.CalledProcessError(1, cmd)
        return completed_command(cmd)

    monkeypatch.delenv("KEEP_TEST_CLUSTER", raising=False)
    monkeypatch.setattr(integration_conftest, "run_command", run_command)

    fixture = integration_conftest.test_cluster.__wrapped__()
    with pytest.raises(subprocess.CalledProcessError):
        next(fixture)

    assert [
        "kind",
        "delete",
        "cluster",
        "-n",
        integration_conftest.TEST_CLUSTER_NAME,
    ] in commands


def test_cluster_uses_current_helm_paths_and_cleans_up(monkeypatch):
    """A successful run should use current paths and release its resources."""
    commands = []
    port_forward_proc = MagicMock()

    def run_command(cmd, check=True, capture=True):
        commands.append(cmd)
        return completed_command(cmd)

    monkeypatch.delenv("KEEP_TEST_CLUSTER", raising=False)
    monkeypatch.setattr(integration_conftest, "run_command", run_command)
    monkeypatch.setattr(integration_conftest, "wait_for_url", lambda url: True)
    monkeypatch.setattr(
        integration_conftest.subprocess,
        "Popen",
        MagicMock(return_value=port_forward_proc),
    )

    fixture = integration_conftest.test_cluster.__wrapped__()
    connection_info = next(fixture)

    assert connection_info["cluster_name"] == integration_conftest.TEST_CLUSTER_NAME

    with pytest.raises(StopIteration):
        next(fixture)

    helm_command = next(cmd for cmd in commands if cmd[0] == "helm")
    assert helm_command[4].endswith("/helm/beakerhub")
    assert helm_command[9].endswith("/helm/values-local.yaml")
    port_forward_proc.terminate.assert_called_once_with()
    port_forward_proc.wait.assert_called_once_with()
    assert [
        "kind",
        "delete",
        "cluster",
        "-n",
        integration_conftest.TEST_CLUSTER_NAME,
    ] in commands
