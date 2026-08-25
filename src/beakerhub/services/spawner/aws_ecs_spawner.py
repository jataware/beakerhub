"""ECS-backed JupyterHub spawner.

This module deliberately contains only ECS control-plane behavior.  Moto can
exercise that behavior in unit tests; a Docker-backed ECS implementation such
as LocalStack is needed to verify that a task image actually starts.
"""

from typing import Any

import boto3
from traitlets import Bool, Dict, List, Unicode

from beakerhub.services.spawner.base import BeakerhubImageSpawner


class BeakerAwsECSSpawner(BeakerhubImageSpawner):
    """Launch a Beaker session as one ECS task.

    Networking/proxy registration is intentionally not implemented here yet.
    ``start`` therefore launches and records the ECS task but does not claim
    that the Jupyter server is reachable.
    """

    cluster_name = Unicode("default", config=True, help="ECS cluster name or ARN.")
    task_definition = Unicode(
        config=True,
        help="ECS task-definition family, revision, or ARN for notebook tasks.",
    )
    container_name = Unicode(
        config=True,
        help="Name of the notebook container in the ECS task definition.",
    )
    container_tags = Dict(
        Unicode(), Unicode(), default_value={}, config=True,
        help="Tags applied to every ECS notebook task.",
    )
    subnets = List(
        Unicode(), default_value=[], config=True,
        help="Subnets used by the task's awsvpc network configuration.",
    )
    security_groups = List(Unicode(), default_value=[], config=True)
    assign_public_ip = Bool(False, config=True)
    fargate = Bool(False, config=True)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.boto = boto3.client("ecs")
        self.task_arn: str | None = None

    @property
    def volume_configs(self) -> list[dict[str, Any]]:
        """Return ECS managed-volume configuration overrides, if configured."""
        return []

    def _task_tags(self) -> list[dict[str, str]]:
        tags = dict(self.container_tags)
        # The session tag is owned by BeakerHub and must not be overridden.
        tags["beaker-session"] = self.session_id
        return [{"key": key, "value": value} for key, value in tags.items()]

    def _network_configuration(self) -> dict[str, Any] | None:
        if not self.subnets:
            if self.fargate:
                raise ValueError("BeakerAwsECSSpawner.subnets is required for Fargate tasks")
            return None
        return {
            "awsvpcConfiguration": {
                "subnets": self.subnets,
                "securityGroups": self.security_groups,
                "assignPublicIp": "ENABLED" if self.assign_public_ip else "DISABLED",
            }
        }

    def _run_task_request(self) -> dict[str, Any]:
        if not self.task_definition:
            raise ValueError("BeakerAwsECSSpawner.task_definition must be configured")
        if not self.container_name:
            raise ValueError("BeakerAwsECSSpawner.container_name must be configured")

        request: dict[str, Any] = {
            "cluster": self.cluster_name,
            "taskDefinition": self.task_definition,
            "count": 1,
            "overrides": {
                "containerOverrides": [{
                    "name": self.container_name,
                    "environment": [
                        {"name": name, "value": str(value)}
                        for name, value in self.get_env().items()
                    ],
                }],
            },
            "tags": self._task_tags(),
        }
        if self.fargate:
            request["launchType"] = "FARGATE"
        network_configuration = self._network_configuration()
        if network_configuration:
            request["networkConfiguration"] = network_configuration
        if self.volume_configs:
            request["volumeConfigurations"] = self.volume_configs
        return request

    def start(self) -> None:
        """Request one ECS task and retain its ARN for later lifecycle calls."""
        response = self.boto.run_task(**self._run_task_request())
        tasks = response.get("tasks", [])
        if not tasks:
            failures = response.get("failures", [])
            raise RuntimeError(f"ECS did not start a task: {failures!r}")
        self.task_arn = tasks[0]["taskArn"]

    def stop(self, now: bool = False) -> None:
        """Stop the task, if this spawner has launched one."""
        if self.task_arn:
            self.boto.stop_task(
                cluster=self.cluster_name,
                task=self.task_arn,
                reason="Stopped by BeakerHub server",
            )

    def poll(self) -> int | None:
        """Return ``None`` while ECS is provisioning/running, otherwise an exit code."""
        if not self.task_arn:
            return 0
        response = self.boto.describe_tasks(cluster=self.cluster_name, tasks=[self.task_arn])
        task = next(
            (item for item in response.get("tasks", []) if item.get("taskArn") == self.task_arn),
            None,
        )
        if task is None:
            return 1
        if task.get("lastStatus") in {"PROVISIONING", "PENDING", "ACTIVATING", "RUNNING"}:
            return None
        for container in task.get("containers", []):
            exit_code = container.get("exitCode")
            if exit_code is not None:
                return int(exit_code)
        return 1

    def get_state(self) -> dict[str, Any]:
        state = super().get_state()
        if self.task_arn:
            state["task_arn"] = self.task_arn
        return state

    def load_state(self, state: dict[str, Any]) -> None:
        super().load_state(state)
        self.task_arn = state.get("task_arn")

    def clear_state(self) -> None:
        super().clear_state()
        self.task_arn = None
