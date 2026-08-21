import json
from typing import cast, Optional

import boto3
from jupyterhub.spawner import Spawner
from kubespawner.spawner import KubeSpawner
from traitlets import default, validate, Unicode, Dict, List, Bool
from traitlets.config import Application

from beakerhub.auth.user import BeakerhubUser
from beakerhub.services.spawner.base import BeakerSpawner, BeakerhubImageSpawner
from beakerhub.services.secrets import VAULT_ENV_VAR_LIST_KEY
from beakerhub import orm


class BeakerAwsECSSpawner(BeakerhubImageSpawner):
    cluster_name: str = Unicode(
        config=True,
    )
    container_type: str = Unicode(
        config=True,
    )
    container_tags: dict[str, str] = Dict(
        Unicode,
        config=True,
    )
    fargate: bool = Bool(
        False,
        config=True,
    )

    boto: boto3.client
    # session_key: str
    task_arn = Optional[str]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.boto = boto3.client("ecs")
        self.task_arn = None

    @property
    def volume_configs(self) -> list[dict]:
        return []


    def start(self):
        overrides = {}
        tasks = self.boto.run_task(
            cluster=self.cluster_name,
            count=1,
            networkConfiguration={
                "assignPublicIp": "ENABLED",
            },
            overrides=overrides,
            tags=(self.container_tags + [{"key": "beaker-session", "value": self.session_id}]),
            volumeConfigurations=self.volume_configs
        )
        self.tasks = tasks

    def stop(self, now=False):
        self.boto.stop_task(
            cluster=self.cluster_name,
            task=self.task_arn,
            reason="Stopped by BeakerHub server"
        )


    def poll(self):
        """
        Check if the pod is still running.

        Uses the same interface as subprocess.Popen.poll(): if the pod is
        still running, returns None.  If the pod has exited, return the
        exit code if we can determine it, or 1 if it has exited but we
        don't know how.  These are the return values JupyterHub expects.

        Note that a clean exit will have an exit code of zero, so it is
        necessary to check that the returned value is None, rather than
        just Falsy, to determine that the pod is still running.
        """
        task_response = self.boto.describe_tasks(
            cluster=self.cluster_name,
            tasks=[self.task_arn],
        )
        task = next((task for task in task_response.get("tasks", []) if task["taskArn"] == self.task_arn), None)
        if task is None:
            return 1
        status = task.get("lastStatus", None)
        desired_status = task.get("desiredStatus", None)
        stop_code = task.get("stopCode", None)
        stopped_reason = task.get("stoppedReason", None)
        stopped_at = task.get("stoppedAt", None)

        if status == "RUNNING" and desired_status == "RUNNING":
            # TODO: Also check starting/provisioning statuses
            return None

        self.log.warning(f"============\n\n{status=}\n\n{desired_status=}\n\n{stop_code=}\n\n{stopped_reason=}\n\n{stopped_at=}")

        try:
            return int(stop_code)
        except ValueError:
            return 1




