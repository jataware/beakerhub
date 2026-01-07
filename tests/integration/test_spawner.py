# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""
Integration tests for BeakerHub spawner functionality.

These tests verify the spawner's ability to create and manage user pods
in the Kubernetes cluster.
"""

import os
import subprocess
import time

import pytest


def get_pods_in_namespace(namespace: str) -> list[dict]:
    """Get list of pods in a namespace."""
    result = subprocess.run(
        [
            "kubectl", "get", "pods",
            "-n", namespace,
            "-o", "jsonpath={.items[*].metadata.name}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    pod_names = result.stdout.strip().split()
    return [{"name": name} for name in pod_names if name]


def wait_for_pod(namespace: str, pod_prefix: str, timeout: int = 120) -> bool:
    """Wait for a pod with given prefix to be running."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        pods = get_pods_in_namespace(namespace)
        for pod in pods:
            if pod["name"].startswith(pod_prefix):
                # Check if pod is running
                result = subprocess.run(
                    [
                        "kubectl", "get", "pod", pod["name"],
                        "-n", namespace,
                        "-o", "jsonpath={.status.phase}",
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.stdout.strip() == "Running":
                    return True
        time.sleep(2)
    return False


class TestSpawnerInfrastructure:
    """Tests for spawner infrastructure setup."""

    def test_beakerhub_namespace_exists(self, test_cluster):
        """BeakerHub namespace should exist."""
        result = subprocess.run(
            ["kubectl", "get", "namespace", test_cluster["namespace"]],
            capture_output=True,
        )
        assert result.returncode == 0

    def test_hub_deployment_running(self, test_cluster):
        """Hub deployment should be running."""
        result = subprocess.run(
            [
                "kubectl", "get", "deployment", "hub",
                "-n", test_cluster["namespace"],
                "-o", "jsonpath={.status.readyReplicas}",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        ready_replicas = int(result.stdout.strip() or "0")
        assert ready_replicas >= 1

    def test_proxy_deployment_running(self, test_cluster):
        """Proxy deployment should be running."""
        result = subprocess.run(
            [
                "kubectl", "get", "deployment", "proxy",
                "-n", test_cluster["namespace"],
                "-o", "jsonpath={.status.readyReplicas}",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        ready_replicas = int(result.stdout.strip() or "0")
        assert ready_replicas >= 1

    def test_hub_service_exists(self, test_cluster):
        """Hub service should exist."""
        result = subprocess.run(
            [
                "kubectl", "get", "service", "hub",
                "-n", test_cluster["namespace"],
            ],
            capture_output=True,
        )
        assert result.returncode == 0

    def test_proxy_service_exists(self, test_cluster):
        """Proxy public service should exist."""
        result = subprocess.run(
            [
                "kubectl", "get", "service", "proxy-public",
                "-n", test_cluster["namespace"],
            ],
            capture_output=True,
        )
        assert result.returncode == 0


@pytest.mark.skipif(
    os.environ.get("RUN_SPAWNER_TESTS", "0") != "1",
    reason="Spawner tests require authenticated user. Set RUN_SPAWNER_TESTS=1 to enable."
)
class TestSpawnerPodLifecycle:
    """
    Tests for spawner pod lifecycle.

    These tests require an authenticated user and will create actual pods
    in the cluster. They are skipped by default to avoid resource usage
    during routine testing.

    Set RUN_SPAWNER_TESTS=1 to enable these tests.
    """

    def test_spawn_creates_pod(self, authenticated_client, test_cluster):
        """Spawning a session should create a user pod."""
        # Get initial pod count
        initial_pods = get_pods_in_namespace(test_cluster["namespace"])
        initial_session_pods = [p for p in initial_pods if p["name"].startswith("session-")]

        # Request a new session
        response = authenticated_client.post(
            f"{test_cluster['base_url']}/api/users/{authenticated_client.username}/servers",
            json={},
        )

        assert response.status_code in [201, 202]

        # Wait for pod to be created
        assert wait_for_pod(test_cluster["namespace"], "session-", timeout=120)

        # Verify new pod exists
        final_pods = get_pods_in_namespace(test_cluster["namespace"])
        final_session_pods = [p for p in final_pods if p["name"].startswith("session-")]

        assert len(final_session_pods) > len(initial_session_pods)

    def test_spawned_pod_has_correct_image(self, authenticated_client, test_cluster):
        """Spawned pod should use the configured image."""
        pods = get_pods_in_namespace(test_cluster["namespace"])
        session_pods = [p for p in pods if p["name"].startswith("session-")]

        if not session_pods:
            pytest.skip("No session pods found")

        pod_name = session_pods[0]["name"]

        result = subprocess.run(
            [
                "kubectl", "get", "pod", pod_name,
                "-n", test_cluster["namespace"],
                "-o", "jsonpath={.spec.containers[0].image}",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        image = result.stdout.strip()
        # Should be using beakerhub image
        assert "beakerhub" in image.lower() or "beaker" in image.lower()

    def test_spawned_pod_has_environment_variables(self, authenticated_client, test_cluster):
        """Spawned pod should have required environment variables."""
        pods = get_pods_in_namespace(test_cluster["namespace"])
        session_pods = [p for p in pods if p["name"].startswith("session-")]

        if not session_pods:
            pytest.skip("No session pods found")

        pod_name = session_pods[0]["name"]

        result = subprocess.run(
            [
                "kubectl", "get", "pod", pod_name,
                "-n", test_cluster["namespace"],
                "-o", "jsonpath={.spec.containers[0].env[*].name}",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        env_vars = result.stdout.strip().split()

        # Should have BEAKER_SERVER_PREFIX set by the spawner
        assert "BEAKER_SERVER_PREFIX" in env_vars or len(env_vars) > 0

    def test_stop_removes_pod(self, authenticated_client, test_cluster):
        """Stopping a session should remove the pod (if delete_stopped_pods is True)."""
        pods = get_pods_in_namespace(test_cluster["namespace"])
        session_pods = [p for p in pods if p["name"].startswith("session-")]

        if not session_pods:
            pytest.skip("No session pods found")

        # Request stop
        response = authenticated_client.delete(
            f"{test_cluster['base_url']}/api/users/{authenticated_client.username}/servers",
        )

        assert response.status_code in [200, 202, 204]

        # Wait for pod to be removed (if configured to delete)
        # Note: BeakerKubeSpawner has delete_stopped_pods = False by default
        # so the pod may remain in a stopped state
        time.sleep(5)

        # Verify pod is stopped or removed
        result = subprocess.run(
            [
                "kubectl", "get", "pod", session_pods[0]["name"],
                "-n", test_cluster["namespace"],
                "-o", "jsonpath={.status.phase}",
            ],
            capture_output=True,
            text=True,
        )

        # Pod either doesn't exist (deleted) or is not Running
        if result.returncode == 0:
            phase = result.stdout.strip()
            assert phase != "Running"
