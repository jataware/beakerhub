from typing import Any, cast
from uuid import uuid4

from jupyterhub.spawner import Spawner
from traitlets import Dict, Unicode, default, validate

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
