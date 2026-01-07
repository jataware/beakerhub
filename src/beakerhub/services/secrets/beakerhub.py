import inspect
import os
import re
from collections import defaultdict
from typing import get_args

import traitlets

from beaker_notebook.lib.secrets.secret_types import EnvironmentSecret, SystemEnvironmentSecret
from beaker_notebook.lib.secrets import policies
from beaker_notebook.services.secrets.manager import BeakerSecretsManager

from beakerhub.services.secrets import VAULT_ENV_VAR_LIST_KEY


# Policies an admin may select, indexed by their wire name. Derived from upstream's
# PolicyTypes so a policy added there becomes selectable here without further changes,
# while internal policies such as MappingKey (type "mapping-key") stay out of reach.
_SELECTABLE_POLICY_TYPES = frozenset(get_args(policies.PolicyTypes))

policy_map: dict[str, type[policies.BasePolicy]] = {
    policy.type: policy
    for _name, policy in inspect.getmembers(
        policies, lambda policy: isinstance(getattr(policy, "type", None), str)
    )
    if policy.type in _SELECTABLE_POLICY_TYPES
}


def policy_by_name(policy_name: str) -> type[policies.BasePolicy] | None:
    return policy_map.get(policy_name)


# The policy fields every secret carries. Used to reject unknown keys rather than
# silently setting an attribute nothing reads.
_POLICY_FIELDS = frozenset(
    name
    for name in SystemEnvironmentSecret.__dataclass_fields__
    if name.endswith("_policy")
)


class BeakerhubSecretsManager(BeakerSecretsManager):
    """Secrets manager that applies BeakerHub's admin-configured policy overrides.

    ``BeakerKubeSpawner`` resolves each vault secret's policies at spawn time and passes
    them in as one environment variable per axis, named
    ``<ENV_VAR>_<policy_field><suffix>`` -- for example
    ``SHARED_API_KEY_subkernel_environment_policy_secret_policy=allow``. This manager
    matches those apart, consumes them, and applies the policies to the matching secret.
    Only axes an admin actually overrode are sent; anything absent keeps the default for
    the secret's type.
    """

    policy_override_env_key_suffix = traitlets.Unicode(
        default_value="_secret_policy",
        help="Suffix marking an environment variable as carrying a policy override "
             "rather than a secret value. Must match BeakerKubeSpawner's setting, or "
             "the overrides will not be recognized.",
        config=True,
    )
    policy_key_regex = traitlets.CRegExp(
        help="Pattern splitting a carrier variable into (env var, policy field). "
             "Derived from policy_override_env_key_suffix.",
        read_only=True,
    )

    @traitlets.default("policy_key_regex")
    def _default_public_key_regex(self):
        # The name group allows digits and lowercase: env vars such as S3_API_KEY or
        # GPT4_TOKEN are legal and would otherwise never match, silently losing every
        # policy set on them. Fields are sorted so the pattern does not vary between
        # runs with set iteration order, and the suffix is escaped in case an operator
        # configures one containing regex metacharacters.
        regex = re.compile(
            rf'([A-Za-z0-9_]+)_({"|".join(sorted(_POLICY_FIELDS))})'
            rf'{re.escape(self.policy_override_env_key_suffix)}$'
        )
        return regex

    def _get_policy_overrides(self):
        overrides = defaultdict(list)
        for policy_key in os.environ.keys():
            if (matches := self.policy_key_regex.match(policy_key)):
                policy_value = os.environ.pop(policy_key)
                secret_key, policy_name = matches.groups()
                overrides[secret_key].append((policy_name, policy_value))
        return overrides

    def _get_vault_env_vars(self) -> set[str]:
        """Consume the list of environment variables that came from the vault.

        Everything in the vault is a secret by definition, but upstream discovers secrets
        by name heuristic, so one named innocuously -- no "secret", "token", "_key" and so
        on -- is never registered. Nothing then applies its policies, and nothing applies
        the default of withholding it from the subkernel either, because the sanitizers
        only act on registered secrets. Taking the hub's word for it closes that hole.
        """
        raw = os.environ.pop(VAULT_ENV_VAR_LIST_KEY, "")
        return {name for name in (part.strip() for part in raw.split(",")) if name}

    async def collect_system_secrets(self, app):
        # Consume the carrier variables *before* upstream discovery runs. Upstream scans
        # os.environ for secret-looking names, and the default suffix ("_secret_policy")
        # contains "secret" -- so any carrier still in the environment is registered as a
        # secret in its own right, whose value is a policy name like "allow". Message
        # scrubbing would then redact that word out of notebook output wherever it
        # appeared. Popping first removes them from view entirely.
        overrides = self._get_policy_overrides()
        vault_env_vars = self._get_vault_env_vars()

        default_secrets = await super().collect_system_secrets(app)
        secret_by_name = {
            secret.name: secret
            for secret in default_secrets
            if isinstance(secret, EnvironmentSecret)
        }

        # Register any vault secret upstream's name heuristics did not recognize, so that
        # its policies -- and failing that, the defaults for a system secret -- apply.
        # Sorted for a stable registration order; skipped when the value never made it
        # into the environment, to avoid registering a secret with nothing behind it.
        for env_var in sorted(vault_env_vars):
            if env_var in secret_by_name or env_var not in os.environ:
                continue
            secret = SystemEnvironmentSecret(name=env_var)
            default_secrets.append(secret)
            secret_by_name[env_var] = secret

        for secret_name, policy_overrides in overrides.items():
            secret = secret_by_name.get(secret_name, None)
            if not secret:
                continue
            for policy_name, policy_str in policy_overrides:
                policy_cls = policy_map.get(policy_str, None)
                if not policy_cls:
                    continue
                setattr(secret, policy_name, policy_cls())
        return default_secrets
