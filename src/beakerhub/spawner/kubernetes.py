import json
from typing import cast

from jupyterhub.spawner import Spawner
from kubespawner.spawner import KubeSpawner
from traitlets import default, validate, Unicode, Dict, List
from traitlets.config import Application

from beakerhub.auth.user import BeakerhubUser
from beakerhub.spawner.base import BeakerSpawner
from beakerhub.services.secrets import VAULT_ENV_VAR_LIST_KEY
from beakerhub import orm


class BeakerKubeSpawner(KubeSpawner, BeakerSpawner):

    default_registry = Unicode().tag(config=True)
    default_image = Unicode().tag(config=True)
    default_tag = Unicode(default_value="latest").tag(config=True)

    default_beaker_context = Unicode(
        default_value="default",
        help="Slug of context the Beaker kernel should be started with."
    ).tag(config=True)

    beaker_context = Unicode()
    context_config = Dict()
    node_env = Dict()
    policy_override_env_key_suffix = Unicode(
        default_value="_secret_policy",
        help="",
        config=True,
    )
    node_policy_overrides = Dict(
        help="Secret-handling policy overrides for this launch, keyed by environment "
             "variable name, e.g. {'SHARED_API_KEY': {'subkernel_environment_policy': 'allow'}}. "
             "Resolved from the vault at spawn time and passed to the node as JSON."
    )

    @staticmethod
    def image_has_defined_registry(image: str) -> bool:
        image_parts = image.split("/")
        if len(image_parts) == 1:
            return False
        return "." in image_parts[0] or ":" in image_parts[0]

    @validate("default_registry")
    def _validate_default_registry(self, proposal):
        return proposal["value"].rstrip("/")

    @default("delete_stopped_pods")
    def _default_delete_stopped_pods(self):
        return False

    @default("namespace")
    def _default_namespace(self):
        return "beakerhub"

    @default("default_image")
    def _default_default_image(self):
        return f"{self.default_registry}/beakerhub/default-node:{self.default_tag}"

    @validate("default_image")
    def _validate_default_image(self, proposal):
        value = proposal["value"]
        if not self.image_has_defined_registry(value):
            return f"{self.default_registry}/{value}"
        else:
            return value

    @default("image")
    def _default_image(self):
        return self.default_image

    @validate("image")
    def _validate_image(self, proposal):
        value = proposal["value"]
        if not self.image_has_defined_registry(value):
            return f"{self.default_registry}/{value}"
        else:
            return value

    @default("pod_name_template")
    def _default_pod_name_template(self):
        return "session-{user_server}"

    @property
    def node_type(self) -> str | None:
        pod_name = self.image.split("/")[-1]
        if "node" not in pod_name:
            return None
        return pod_name

    def get_env(self):
        user: BeakerhubUser = cast(BeakerhubUser, self.user)
        env = super().get_env()
        env.setdefault("JUPYTER_BASE_URL", user.server_url(server_name=self.name))
        env.setdefault("BEAKER_DEFAULT_CONTEXT", self.beaker_context or self.default_beaker_context)
        env.setdefault("BEAKERHUB_USER", user.name)
        env.setdefault("BEAKER_UI_HIDE_CONTEXT_SELECTOR", "true")
        env.update(self.node_env)
        # Tell the node which variables came from the vault. It discovers secrets by name
        # heuristic, which misses anything innocuous-looking, and an unrecognized vault
        # secret gets no policies applied *and* no default protection either.
        if self.node_env:
            env.setdefault(VAULT_ENV_VAR_LIST_KEY, ",".join(sorted(self.node_env)))
        # Policy metadata is not itself sensitive, so it travels as a plain env var.
        # Only set it when there is something to say, so the node keeps its own default
        # of "no overrides" rather than parsing an empty object.
        for env_name, policy_dict in self.node_policy_overrides.items():
            for policy_name, policy_value in policy_dict.items():
                policy_key = f"{env_name}_{policy_name}{self.policy_override_env_key_suffix}"
                env.setdefault(policy_key, policy_value)

        return env

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
