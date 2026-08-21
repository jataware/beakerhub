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

    @staticmethod
    def apply_user_options(spawner: "BeakerKubeSpawner", user_options: dict):
        node_record: orm.NodeImages | None = None
        context_slug: str | None = None

        if (node_slug := user_options.get("nodeSlug", None)):
            node_record = spawner.db.query(orm.NodeImages).filter(orm.NodeImages.slug == node_slug).first()
            if node_record:
                tag = ("debug" if spawner.debug else node_record.default_tag) or spawner.default_tag
                image_spec = f"{node_record.default_registry}/{node_record.repository}:{tag}"
                spawner.image = image_spec

        if (context := user_options.get("contextSlug", None)):
            if ':' in context:
                context = context.split(":")[-1]
            context_slug = context
            spawner.beaker_context = context

        # Inject secrets from the vault: globals first, then node-specific overrides
        # Build the set of secret IDs explicitly disabled for this context
        disabled_secret_ids: set[int] = set()
        if context_slug:
            context_record = (
                spawner.db.query(orm.Context)
                .filter(orm.Context.slug == context_slug)
                .first()
            )
            if context_record:
                disabled_rows = spawner.db.execute(
                    orm.beaker_context_secrets.select().where(
                        orm.beaker_context_secrets.c.context_id == context_record.id,
                        orm.beaker_context_secrets.c.enabled == False,
                    )
                ).fetchall()
                disabled_secret_ids = {row.node_secret_id for row in disabled_rows}

        secrets_env: dict[str, str] = {}
        # Policy overrides travel separately from the values: the value goes into the pod
        # environment, while the policies tell the node what it may do with that value.
        # Both are keyed by env_var, so a node-specific secret overrides a global one in
        # exactly the same way for each.
        secrets_policies: dict[str, dict[str, str]] = {}

        def collect(secret: orm.NodeSecret) -> None:
            if secret.id in disabled_secret_ids:
                return
            secrets_env[secret.env_var] = secret.value
            # An empty dict means "every axis at its default", which the node already
            # assumes, so there is nothing to send.
            if secret.policies:
                secrets_policies[secret.env_var] = secret.policies
            else:
                # A node-specific secret with no overrides must not inherit the policies
                # of the global secret it shadows.
                secrets_policies.pop(secret.env_var, None)

        # Global secrets (node_image_id IS NULL)
        global_secrets = (
            spawner.db.query(orm.NodeSecret)
            .filter(orm.NodeSecret.node_image_id.is_(None))
            .all()
        )
        for secret in global_secrets:
            collect(secret)

        # Node-specific secrets (override globals)
        if node_record:
            node_secrets = (
                spawner.db.query(orm.NodeSecret)
                .filter(orm.NodeSecret.node_image_id == node_record.id)
                .all()
            )
            for secret in node_secrets:
                collect(secret)

        spawner.node_env = secrets_env or {}
        spawner.node_policy_overrides = secrets_policies or {}

        # Keep K8s secretRef as fallback for secrets not yet migrated to the vault
        if node_slug:
            secret_name = f"{node_slug}-secrets"
            env_from: list = spawner.extra_container_config.setdefault("envFrom", [])
            env_from.append({
                "secretRef": {
                    "name": secret_name,
                    "optional": True  # Don't fail if secret doesn't exist
                }
            })

        if (context_config := user_options.get("contextOptions", None)):
            spawner.context_config = context_config
