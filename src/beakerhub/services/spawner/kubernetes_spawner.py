import json
from typing import cast

from jupyterhub.spawner import Spawner
from kubespawner.spawner import KubeSpawner
from traitlets import default, validate, Unicode, Dict, List
from traitlets.config import Application

from beakerhub.services.spawner.base import BeakerSpawner, BeakerhubImageSpawner
from beakerhub import orm


class BeakerKubeSpawner(KubeSpawner, BeakerhubImageSpawner):

    image = KubeSpawner.image

    def get_env(self):
        """Add BeakerHub variables after KubeSpawner builds its environment."""
        return BeakerSpawner._extend_env(self, super().get_env())

    @default("delete_stopped_pods")
    def _default_delete_stopped_pods(self):
        return False

    @default("namespace")
    def _default_namespace(self):
        return "beakerhub"

    @default("pod_name_template")
    def _default_pod_name_template(self):
        return "session-{user_server}"

    @property
    def node_type(self) -> str | None:
        pod_name = self.image.split("/")[-1]
        if "node" not in pod_name:
            return None
        return pod_name

    def apply_user_options(self, _spawner, user_options: dict):
        # Equivilent to calling method via super() when multiple inheritence
        BeakerhubImageSpawner.apply_user_options(self, _spawner, user_options)

        # Keep K8s secretRef as fallback for secrets not yet migrated to the vault
        if (node_slug := user_options.get("nodeSlug", None)):
            secret_name = f"{node_slug}-secrets"
            env_from: list = self.extra_container_config.setdefault("envFrom", [])
            env_from.append({
                "secretRef": {
                    "name": secret_name,
                    "optional": True  # Don't fail if secret doesn't exist
                }
            })
