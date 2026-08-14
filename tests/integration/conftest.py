# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""
Fixtures for integration tests.

Integration tests run against a deployed BeakerHub instance in a kind cluster.
The cluster is separate from the dev cluster but shares the local registry.

Setup:
    1. Ensure the local registry is running (from dev setup)
    2. Create a test kind cluster
    3. Deploy BeakerHub via helm
    4. Run tests against the deployed instance
    5. Tear down the test cluster
"""

import os
import subprocess
import tempfile
import time
from typing import Generator

import pytest
import requests

# Test cluster configuration
TEST_CLUSTER_NAME = "beakerhub-test"
TEST_NAMESPACE = "beakerhub"
HELM_RELEASE_NAME = "beakerhub-test"
REGISTRY_NAME = "beaker-local-registry"


def run_command(cmd: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
    )


def wait_for_url(url: str, timeout: int = 120, interval: int = 2) -> bool:
    """Wait for a URL to become available."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code < 500:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(interval)
    return False


@pytest.fixture(scope="session")
def test_cluster() -> Generator[dict, None, None]:
    """
    Create and manage a test kind cluster for integration tests.

    This fixture:
    1. Creates a new kind cluster (if not exists)
    2. Installs BeakerHub via helm
    3. Waits for the deployment to be ready
    4. Yields connection info for tests
    5. Optionally tears down the cluster (controlled by env var)

    Set KEEP_TEST_CLUSTER=1 to preserve the cluster after tests.
    """
    keep_cluster = os.environ.get("KEEP_TEST_CLUSTER", "0") == "1"
    cluster_created = False
    port_forward_proc: subprocess.Popen | None = None

    try:
        # Check if cluster already exists
        result = run_command(["kind", "get", "clusters"], check=False)
        cluster_exists = (
            result.returncode == 0
            and TEST_CLUSTER_NAME in result.stdout.split()
        )
        if cluster_exists:
            print(f"Test cluster '{TEST_CLUSTER_NAME}' already exists, reusing...")
        else:
            print(f"Creating test cluster '{TEST_CLUSTER_NAME}'...")
            cluster_created = True

            # Create kind cluster config
            kind_config = f"""
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: {TEST_CLUSTER_NAME}
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:5000"]
    endpoint = ["http://{REGISTRY_NAME}:5000"]
  [plugins."io.containerd.grpc.v1.cri".registry.mirrors."{REGISTRY_NAME}:5000"]
    endpoint = ["http://{REGISTRY_NAME}:5000"]
"""
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".yaml",
            ) as config_file:
                config_file.write(kind_config)
                config_file.flush()
                run_command(
                    [
                        "kind",
                        "create",
                        "cluster",
                        "--config",
                        config_file.name,
                    ]
                )

            # Connect registry to kind network (if not already connected)
            run_command(
                ["docker", "network", "connect", "kind", REGISTRY_NAME],
                check=False,  # May already be connected
            )

        # Set kubectl context
        run_command(
            ["kubectl", "config", "use-context", f"kind-{TEST_CLUSTER_NAME}"]
        )

        # Get project root directory
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        helm_chart_path = os.path.join(project_root, "helm", "beakerhub")
        values_local_path = os.path.join(project_root, "helm", "values-local.yaml")

        # Install/upgrade BeakerHub
        print("Installing BeakerHub via helm...")
        helm_cmd = [
            "helm",
            "upgrade",
            "--install",
            HELM_RELEASE_NAME,
            helm_chart_path,
            "-n",
            TEST_NAMESPACE,
            "--create-namespace",
            "-f",
            values_local_path,
            "--wait",
            "--timeout",
            "5m",
        ]
        run_command(helm_cmd)

        # Get service URL (using port-forward for simplicity)
        # In a more complete setup, you'd use an ingress or LoadBalancer
        print("Setting up port-forward to BeakerHub...")

        # Start port-forward in background
        port_forward_proc = subprocess.Popen(
            [
                "kubectl",
                "port-forward",
                "-n",
                TEST_NAMESPACE,
                "svc/proxy-public",
                "8888:80",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        base_url = "http://localhost:8888"

        # Wait for service to be ready
        print("Waiting for BeakerHub to be ready...")
        if not wait_for_url(f"{base_url}/_chp_healthz"):
            raise RuntimeError("BeakerHub failed to become ready within timeout")

        print(f"BeakerHub is ready at {base_url}")

        yield {
            "base_url": base_url,
            "cluster_name": TEST_CLUSTER_NAME,
            "namespace": TEST_NAMESPACE,
            "port_forward_proc": port_forward_proc,
        }
    finally:
        try:
            if port_forward_proc is not None:
                port_forward_proc.terminate()
                port_forward_proc.wait()
        finally:
            if cluster_created and not keep_cluster:
                print(f"Deleting test cluster '{TEST_CLUSTER_NAME}'...")
                run_command(
                    ["kind", "delete", "cluster", "-n", TEST_CLUSTER_NAME],
                    check=False,
                )
            elif cluster_created:
                print(
                    f"Keeping test cluster '{TEST_CLUSTER_NAME}' "
                    "because KEEP_TEST_CLUSTER=1"
                )
            else:
                print(f"Keeping pre-existing test cluster '{TEST_CLUSTER_NAME}'")


@pytest.fixture(scope="session")
def api_client(test_cluster):
    """Create a requests session for API testing."""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
    })

    # Store base URL for convenience
    session.base_url = test_cluster["base_url"]

    yield session

    session.close()


@pytest.fixture(scope="function")
def authenticated_client(api_client, test_cluster):
    """
    Create an authenticated API client.

    Note: This requires a test user to be set up in the Cognito pool
    or moto to be running.
    """
    # For integration tests with real Cognito, you'd need test credentials
    # For tests with moto, you'd need moto running alongside the cluster

    # This is a placeholder - actual implementation depends on test environment
    test_email = os.environ.get("TEST_USER_EMAIL", "test@example.com")
    test_password = os.environ.get("TEST_USER_PASSWORD", "TestPass123!")

    # Attempt login
    login_response = api_client.post(
        f"{test_cluster['base_url']}/api/auth/login",
        json={"username": test_email, "password": test_password},
    )

    if login_response.status_code == 200:
        # Session cookies are automatically stored in the session
        pass
    else:
        pytest.skip("Could not authenticate - test user may not exist")

    yield api_client
