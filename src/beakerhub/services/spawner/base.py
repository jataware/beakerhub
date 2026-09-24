from typing import Any, cast
from uuid import uuid4

from jupyterhub.spawner import Spawner
from traitlets import Dict, Unicode, default, validate

from beakerhub import orm
from beakerhub.auth.user import BeakerhubUser
from beakerhub.services.secrets import VAULT_ENV_VAR_LIST_KEY

class BeakerSpawner(Spawner):

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


    def __init__(self, **kwargs: Any) -> None:
        domain = kwargs.pop("domain", None)
        super().__init__(**kwargs)
        if domain:
            self.proxy_spec = f"{self.name}.{domain}/"

    @property
    def name(self) -> str:
        name = super().name
        return name

    @name.setter
    def name(self, value: str) -> str:
        if self.orm_spawner and self.orm_spawner.name != value:
            self.orm_spawner.name = value
            self.orm_spawner.save()
        return value

    @property
    def session_id(self) -> str:
        if not self.name:
            self.name = str(uuid4())
        return self.name

    def get_env(self):
        env = super().get_env()
        return self._extend_env(env)

    def _extend_env(self, env: dict[str, str]) -> dict[str, str]:
        """Add BeakerHub-specific values to a runtime environment."""
        user = cast(BeakerhubUser, self.user)
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

    def start(self):
        raise NotImplementedError()

    def stop(self, now=False):
        raise NotImplementedError()

    def poll(self):
        raise NotImplementedError()

    def apply_user_options(self, _spawner, user_options: dict):
        node_record: orm.NodeImages | None = None
        context_slug: str | None = None

        if (node_slug := user_options.get("nodeSlug", None)):
            node_record = self.db.query(orm.NodeImages).filter(orm.NodeImages.slug == node_slug).first()

        if (context := user_options.get("contextSlug", None)):
            if ':' in context:
                context = context.split(":")[-1]
            context_slug = context
            self.beaker_context = context

        if (context_config := user_options.get("contextOptions", None)):
            self.context_config = context_config

        # Inject secrets from the vault: globals first, then node-specific overrides
        # Build the set of secret IDs explicitly disabled for this context
        disabled_secret_ids: set[int] = set()
        if context_slug:
            context_record = (
                self.db.query(orm.Context)
                .filter(orm.Context.slug == context_slug)
                .first()
            )
            if context_record:
                disabled_rows = self.db.execute(
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
            self.db.query(orm.NodeSecret)
            .filter(orm.NodeSecret.node_image_id.is_(None))
            .all()
        )
        for secret in global_secrets:
            collect(secret)

        # Node-specific secrets (override globals)
        if node_record:
            node_secrets = (
                self.db.query(orm.NodeSecret)
                .filter(orm.NodeSecret.node_image_id == node_record.id)
                .all()
            )
            for secret in node_secrets:
                collect(secret)

        self.node_env = secrets_env or {}
        self.node_policy_overrides = secrets_policies or {}

class BeakerhubImageSpawner(BeakerSpawner):

    default_registry = Unicode(
        config=True,
    ).tag(config=True)
    default_image = Unicode(
        config=True,
    ).tag(config=True)
    default_tag = Unicode(
        "latest",
        config=True,
    )

    image = Unicode(
        "beakerhub/default-node:latest",
        config=True,
        help="""
        Docker image to use for spawning user's containers.
        """,
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

    def apply_user_options(self, _spawner, user_options: dict):
        node_record: orm.NodeImages | None = None

        super().apply_user_options(_spawner, user_options)

        if (node_slug := user_options.get("nodeSlug", None)):
            node_record = self.db.query(orm.NodeImages).filter(orm.NodeImages.slug == node_slug).first()
            if node_record:
                tag = ("debug" if self.debug else node_record.default_tag) or self.default_tag
                image_spec = f"{node_record.default_registry}/{node_record.repository}:{tag}"
                self.image = image_spec
