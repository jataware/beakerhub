# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""Unit tests for BeakerhubSecretsManager policy-override handling.

The spawner passes each policy axis as its own environment variable named
`<ENV_VAR>_<policy_field><suffix>`. This manager matches those apart, consumes them,
and applies the policies to the matching secret.
"""

import os

import pytest
from traitlets.config import Configurable

from beaker_notebook.lib.secrets import policies
from beaker_notebook.lib.secrets.secret_types import EnvironmentSecret
from beaker_notebook.lib.secrets.secret_types import SystemEnvironmentSecret
from beakerhub.services.secrets import VAULT_ENV_VAR_LIST_KEY
from beakerhub.services.secrets.beakerhub import (
    BeakerhubSecretsManager,
    _POLICY_FIELDS,
    policy_by_name,
    policy_map,
)

SUFFIX = "_secret_policy"


class FakeApp(Configurable):
    """Minimal parent: the manager appends its API handlers to parent.handlers."""
    handlers: list = []


@pytest.fixture
def clean_env():
    """Run with an isolated os.environ, since the manager consumes entries from it."""
    original = os.environ.copy()
    os.environ.clear()
    yield os.environ
    os.environ.clear()
    os.environ.update(original)


@pytest.fixture
def manager():
    FakeApp.handlers = []
    return BeakerhubSecretsManager(parent=FakeApp())


def policy_key(env_var: str, policy_field: str) -> str:
    return f"{env_var}_{policy_field}{SUFFIX}"


def env_secrets(secrets) -> dict:
    """Index the environment secrets by name; the registry holds other kinds too."""
    return {s.name: s for s in secrets if isinstance(s, EnvironmentSecret)}


class TestPolicyMap:
    def test_exposes_the_selectable_policies(self):
        assert set(policy_map) == {"allow", "redact", "remove", "last4"}

    def test_internal_policies_are_not_selectable(self):
        """MappingKey is an implementation detail and must not be reachable by name."""
        assert "mapping-key" not in policy_map

    def test_unknown_name_resolves_to_none(self):
        assert policy_by_name("nonsense") is None

    def test_policy_fields_match_the_secret_dataclass(self):
        assert _POLICY_FIELDS == {
            "ui_message_policy",
            "agent_message_policy",
            "subkernel_message_policy",
            "beaker_kernel_environment_policy",
            "subkernel_environment_policy",
        }


class TestPolicyKeyRegex:
    def test_splits_env_var_from_policy_field(self, manager):
        match = manager.policy_key_regex.match(
            policy_key("SHARED_API_KEY", "subkernel_environment_policy")
        )
        assert match.groups() == ("SHARED_API_KEY", "subkernel_environment_policy")

    @pytest.mark.parametrize("env_var", ["S3_API_KEY", "GPT4_TOKEN", "lower_key", "A1"])
    def test_accepts_digits_and_lowercase(self, manager, env_var):
        """Env var names are not restricted to A-Z and _; policies must survive them."""
        match = manager.policy_key_regex.match(policy_key(env_var, "ui_message_policy"))
        assert match is not None, env_var
        assert match.group(1) == env_var

    def test_ignores_unrelated_variables(self, manager):
        for key in ("SHARED_API_KEY", "PATH", "SHARED_API_KEY_not_a_policy_secret_policy"):
            assert manager.policy_key_regex.match(key) is None, key

    def test_requires_the_suffix_to_end_the_name(self, manager):
        key = policy_key("SHARED_API_KEY", "ui_message_policy") + "_TRAILING"
        assert manager.policy_key_regex.match(key) is None


class TestCollectSystemSecrets:
    async def test_applies_an_override_to_a_discovered_secret(self, manager, clean_env):
        clean_env["SHARED_API_KEY"] = "the-real-value"
        clean_env[policy_key("SHARED_API_KEY", "subkernel_environment_policy")] = "allow"

        secrets = env_secrets(await manager.collect_system_secrets(None))

        assert isinstance(secrets["SHARED_API_KEY"].subkernel_environment_policy, policies.Allow)

    async def test_applies_the_policy_as_an_instance(self, manager, clean_env):
        """Downstream compares with isinstance, so a class here would never match."""
        clean_env["SHARED_API_KEY"] = "v"
        clean_env[policy_key("SHARED_API_KEY", "ui_message_policy")] = "last4"

        secrets = env_secrets(await manager.collect_system_secrets(None))
        policy = secrets["SHARED_API_KEY"].ui_message_policy

        assert not isinstance(policy, type)
        assert isinstance(policy, policies.Last4)

    async def test_untouched_axes_keep_their_defaults(self, manager, clean_env):
        clean_env["SHARED_API_KEY"] = "v"
        clean_env[policy_key("SHARED_API_KEY", "subkernel_environment_policy")] = "allow"

        secrets = env_secrets(await manager.collect_system_secrets(None))
        secret = secrets["SHARED_API_KEY"]

        assert isinstance(secret.beaker_kernel_environment_policy, policies.Allow)
        assert isinstance(secret.ui_message_policy, policies.Redact)
        assert isinstance(secret.agent_message_policy, policies.Redact)

    async def test_applies_every_axis(self, manager, clean_env):
        clean_env["SHARED_API_KEY"] = "v"
        for field, value in (
            ("subkernel_environment_policy", "allow"),
            ("beaker_kernel_environment_policy", "remove"),
            ("ui_message_policy", "last4"),
            ("agent_message_policy", "remove"),
            ("subkernel_message_policy", "allow"),
        ):
            clean_env[policy_key("SHARED_API_KEY", field)] = value

        secrets = env_secrets(await manager.collect_system_secrets(None))
        secret = secrets["SHARED_API_KEY"]

        assert isinstance(secret.subkernel_environment_policy, policies.Allow)
        assert isinstance(secret.beaker_kernel_environment_policy, policies.Remove)
        assert isinstance(secret.ui_message_policy, policies.Last4)
        assert isinstance(secret.agent_message_policy, policies.Remove)
        assert isinstance(secret.subkernel_message_policy, policies.Allow)

    async def test_ignores_an_unknown_policy_name(self, manager, clean_env):
        clean_env["SHARED_API_KEY"] = "v"
        clean_env[policy_key("SHARED_API_KEY", "ui_message_policy")] = "nonsense"

        secrets = env_secrets(await manager.collect_system_secrets(None))

        assert isinstance(secrets["SHARED_API_KEY"].ui_message_policy, policies.Redact)

    async def test_consumes_the_carrier_variables(self, manager, clean_env):
        """They are configuration, not environment the kernel or subkernel should see."""
        clean_env["SHARED_API_KEY"] = "v"
        carrier = policy_key("SHARED_API_KEY", "subkernel_environment_policy")
        clean_env[carrier] = "allow"

        await manager.collect_system_secrets(None)

        assert carrier not in os.environ
        assert os.environ["SHARED_API_KEY"] == "v"

    async def test_carriers_are_not_themselves_registered_as_secrets(self, manager, clean_env):
        """Regression guard for a subtle and damaging interaction.

        The default suffix contains "secret", so a carrier left in the environment is
        picked up by upstream's env-name heuristics and registered as a secret whose
        value is a policy name such as "allow". Message scrubbing would then redact that
        word out of notebook output wherever it appeared. Consuming the carriers before
        discovery runs is what prevents it.
        """
        clean_env["SHARED_API_KEY"] = "v"
        carrier = policy_key("SHARED_API_KEY", "subkernel_environment_policy")
        clean_env[carrier] = "allow"
        assert "secret" in carrier.lower(), "premise: the suffix looks secret-ish"

        secrets = await manager.collect_system_secrets(None)
        names = {getattr(s, "name", None) for s in secrets}

        assert carrier not in names
        assert not any(
            getattr(s, "name", "").endswith(SUFFIX) for s in secrets
        ), "a policy carrier was registered as a secret"

    async def test_handles_env_var_names_containing_digits(self, manager, clean_env):
        clean_env["S3_API_KEY"] = "v"
        clean_env[policy_key("S3_API_KEY", "subkernel_environment_policy")] = "allow"

        secrets = env_secrets(await manager.collect_system_secrets(None))

        assert isinstance(secrets["S3_API_KEY"].subkernel_environment_policy, policies.Allow)

    async def test_registers_a_vault_secret_discovery_missed(self, manager, clean_env):
        """Everything in the vault is a secret, whatever its name looks like.

        Upstream discovers secrets by name heuristic, so an innocuous name is never
        registered -- and an unregistered secret gets neither its policies nor the default
        of being withheld from the subkernel. The hub sends the vault's env var list so
        this can be closed.
        """
        clean_env["SHARED_ENDPOINT"] = "v"
        clean_env[VAULT_ENV_VAR_LIST_KEY] = "SHARED_ENDPOINT"

        secrets = env_secrets(await manager.collect_system_secrets(None))

        assert "SHARED_ENDPOINT" in secrets
        secret = secrets["SHARED_ENDPOINT"]
        assert isinstance(secret, SystemEnvironmentSecret)
        # Defaults for a system secret: kept from the subkernel, scrubbed from messages.
        assert isinstance(secret.subkernel_environment_policy, policies.Remove)
        assert isinstance(secret.ui_message_policy, policies.Redact)

    async def test_applies_overrides_to_a_newly_registered_vault_secret(self, manager, clean_env):
        clean_env["SHARED_ENDPOINT"] = "v"
        clean_env[VAULT_ENV_VAR_LIST_KEY] = "SHARED_ENDPOINT"
        clean_env[policy_key("SHARED_ENDPOINT", "subkernel_environment_policy")] = "allow"

        secrets = env_secrets(await manager.collect_system_secrets(None))

        assert isinstance(
            secrets["SHARED_ENDPOINT"].subkernel_environment_policy, policies.Allow
        )

    async def test_does_not_duplicate_an_already_discovered_secret(self, manager, clean_env):
        clean_env["SHARED_API_KEY"] = "v"
        clean_env[VAULT_ENV_VAR_LIST_KEY] = "SHARED_API_KEY"

        matching = [
            s for s in await manager.collect_system_secrets(None)
            if getattr(s, "name", None) == "SHARED_API_KEY"
        ]

        assert len(matching) == 1

    async def test_skips_a_listed_var_absent_from_the_environment(self, manager, clean_env):
        """No value reached the pod, so there is nothing to police."""
        clean_env[VAULT_ENV_VAR_LIST_KEY] = "NEVER_ARRIVED"

        secrets = env_secrets(await manager.collect_system_secrets(None))

        assert "NEVER_ARRIVED" not in secrets

    async def test_consumes_the_vault_list_variable(self, manager, clean_env):
        clean_env["SHARED_ENDPOINT"] = "v"
        clean_env[VAULT_ENV_VAR_LIST_KEY] = "SHARED_ENDPOINT"

        await manager.collect_system_secrets(None)

        assert VAULT_ENV_VAR_LIST_KEY not in os.environ

    async def test_tolerates_whitespace_and_empty_entries(self, manager, clean_env):
        clean_env["SHARED_ENDPOINT"] = "v"
        clean_env["OTHER_ENDPOINT"] = "v"
        clean_env[VAULT_ENV_VAR_LIST_KEY] = " SHARED_ENDPOINT , ,OTHER_ENDPOINT,"

        secrets = env_secrets(await manager.collect_system_secrets(None))

        assert "SHARED_ENDPOINT" in secrets
        assert "OTHER_ENDPOINT" in secrets

    async def test_vault_list_variable_is_not_itself_a_secret(self, manager, clean_env):
        """Its value is a list of env var names; scrubbing those from output would be bad."""
        clean_env["SHARED_ENDPOINT"] = "v"
        clean_env[VAULT_ENV_VAR_LIST_KEY] = "SHARED_ENDPOINT"

        secrets = env_secrets(await manager.collect_system_secrets(None))

        assert VAULT_ENV_VAR_LIST_KEY not in secrets

    async def test_no_overrides_leaves_defaults_alone(self, manager, clean_env):
        clean_env["SHARED_API_KEY"] = "v"

        secrets = env_secrets(await manager.collect_system_secrets(None))

        assert isinstance(secrets["SHARED_API_KEY"].subkernel_environment_policy, policies.Remove)


class TestSubkernelEnvironmentOutcome:
    """What actually reaches the subkernel, which is the behavior that matters.

    Exercises the real sequence: collect_system_secrets, then add_secrets (as
    beaker_notebook's app.initialize does), then the subkernel env sanitizer.
    """

    async def test_shared_key_passes_and_private_key_is_withheld(self, manager, clean_env):
        """Both names are deliberately free of "secret", "private", "token", "_key" etc,
        so neither is discovered on its own and the vault list is the only thing that
        makes them secrets at all."""
        clean_env["SHARED_ENDPOINT"] = "shared-value"
        clean_env["INTERNAL_ENDPOINT"] = "internal-value"
        clean_env[VAULT_ENV_VAR_LIST_KEY] = "SHARED_ENDPOINT,INTERNAL_ENDPOINT"
        clean_env[policy_key("SHARED_ENDPOINT", "subkernel_environment_policy")] = "allow"

        manager.add_secrets(await manager.collect_system_secrets(None))
        env = await manager.sanitize_subkernel_envionment_vars(user=None, env=dict(os.environ))

        assert env["SHARED_ENDPOINT"] == "shared-value"
        assert "INTERNAL_ENDPOINT" not in env

    async def test_bookkeeping_variables_never_reach_the_subkernel(self, manager, clean_env):
        clean_env["SHARED_ENDPOINT"] = "v"
        clean_env[VAULT_ENV_VAR_LIST_KEY] = "SHARED_ENDPOINT"
        clean_env[policy_key("SHARED_ENDPOINT", "ui_message_policy")] = "last4"

        manager.add_secrets(await manager.collect_system_secrets(None))
        env = await manager.sanitize_subkernel_envionment_vars(user=None, env=dict(os.environ))

        assert VAULT_ENV_VAR_LIST_KEY not in env
        assert not [key for key in env if key.endswith(SUFFIX)]
