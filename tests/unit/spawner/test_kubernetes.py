# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""Unit tests for beakerhub.spawner.kubernetes module."""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from beakerhub.spawner.kubernetes import BeakerKubeSpawner


class TestBeakerKubeSpawner:
    """Tests for BeakerKubeSpawner class."""

    @pytest.fixture
    def mock_spawner(self):
        """Create a mock BeakerKubeSpawner for testing."""
        spawner = MagicMock(spec=BeakerKubeSpawner)
        spawner.name = "test-session"
        spawner.beaker_context = ""
        spawner.default_beaker_context = "default"
        spawner.context_config = {}
        # Real Dict traits, not auto-specced Mocks: get_env serializes this one.
        spawner.node_env = {}
        spawner.node_policy_overrides = {}
        return spawner

    @pytest.fixture
    def mock_user(self):
        """Create a mock BeakerhubUser."""
        user = MagicMock()
        user.server_url = MagicMock(return_value="/user/testuser/test-session/")
        return user

    def test_default_delete_stopped_pods_returns_false(self):
        """_default_delete_stopped_pods should return False."""
        spawner = MagicMock(spec=BeakerKubeSpawner)

        result = BeakerKubeSpawner._default_delete_stopped_pods(spawner)

        assert result is False

    def test_default_namespace_returns_beakerhub(self):
        """_default_namespace should return 'beakerhub'."""
        spawner = MagicMock(spec=BeakerKubeSpawner)

        result = BeakerKubeSpawner._default_namespace(spawner)

        assert result == "beakerhub"

    def test_default_image_returns_default_image_trait(self):
        """_default_image should return the value of the default_image trait."""
        spawner = MagicMock(spec=BeakerKubeSpawner)
        spawner.default_image = "registry.example.com/beakerhub/default-node:latest"

        result = BeakerKubeSpawner._default_image(spawner)

        assert result == spawner.default_image

    def test_default_pod_name_template_returns_expected_template(self):
        """_default_pod_name_template should return expected template."""
        spawner = MagicMock(spec=BeakerKubeSpawner)

        result = BeakerKubeSpawner._default_pod_name_template(spawner)

        assert result == "session-{user_server}"

    def test_get_env_includes_jupyter_base_url(self, mock_spawner, mock_user):
        """get_env should include JUPYTER_BASE_URL from user.server_url()."""
        mock_spawner.user = mock_user
        mock_spawner.name = "test-session"

        # Mock super().get_env() to return a base dict
        with patch.object(
            BeakerKubeSpawner.__bases__[0], "get_env", return_value={"EXISTING": "value"}
        ):
            result = BeakerKubeSpawner.get_env(mock_spawner)

        assert "JUPYTER_BASE_URL" in result
        assert result["JUPYTER_BASE_URL"] == "/user/testuser/test-session/"
        mock_user.server_url.assert_called_once_with(server_name="test-session")

    def test_get_env_includes_beaker_default_context(self, mock_spawner, mock_user):
        """get_env should include BEAKER_DEFAULT_CONTEXT."""
        mock_spawner.user = mock_user
        mock_spawner.beaker_context = ""
        mock_spawner.default_beaker_context = "my-default-context"

        with patch.object(
            BeakerKubeSpawner.__bases__[0], "get_env", return_value={}
        ):
            result = BeakerKubeSpawner.get_env(mock_spawner)

        assert "BEAKER_DEFAULT_CONTEXT" in result
        assert result["BEAKER_DEFAULT_CONTEXT"] == "my-default-context"

    def test_get_env_uses_beaker_context_when_set(self, mock_spawner, mock_user):
        """get_env should use beaker_context over default when set."""
        mock_spawner.user = mock_user
        mock_spawner.beaker_context = "custom-context"
        mock_spawner.default_beaker_context = "default"

        with patch.object(
            BeakerKubeSpawner.__bases__[0], "get_env", return_value={}
        ):
            result = BeakerKubeSpawner.get_env(mock_spawner)

        assert result["BEAKER_DEFAULT_CONTEXT"] == "custom-context"

    def test_get_env_preserves_parent_env(self, mock_spawner, mock_user):
        """get_env should preserve environment variables from parent."""
        mock_spawner.user = mock_user
        parent_env = {
            "PATH": "/usr/bin",
            "HOME": "/home/user",
        }

        with patch.object(
            BeakerKubeSpawner.__bases__[0], "get_env", return_value=parent_env.copy()
        ):
            result = BeakerKubeSpawner.get_env(mock_spawner)

        assert result["PATH"] == "/usr/bin"
        assert result["HOME"] == "/home/user"


class TestApplyUserOptions:
    """Tests for BeakerKubeSpawner.apply_user_options static method."""

    def test_sets_beaker_context_from_user_options(self):
        """apply_user_options should set beaker_context from contextSlug."""
        spawner = MagicMock()
        spawner.beaker_context = ""
        spawner.context_config = {}

        user_options = {"contextSlug": "weather-context"}

        BeakerKubeSpawner.apply_user_options(spawner, user_options)

        assert spawner.beaker_context == "weather-context"

    def test_sets_beaker_context_strips_prefix(self):
        """apply_user_options should strip prefix from contextSlug if it contains ':'."""
        spawner = MagicMock()
        spawner.beaker_context = ""
        spawner.context_config = {}

        user_options = {"contextSlug": "pkg:weather-context"}

        BeakerKubeSpawner.apply_user_options(spawner, user_options)

        assert spawner.beaker_context == "weather-context"

    def test_sets_context_config_from_user_options(self):
        """apply_user_options should set context_config from contextOptions."""
        spawner = MagicMock()
        spawner.beaker_context = ""
        spawner.context_config = {}

        user_options = {
            "contextOptions": {"key1": "value1", "key2": "value2"}
        }

        BeakerKubeSpawner.apply_user_options(spawner, user_options)

        assert spawner.context_config == {"key1": "value1", "key2": "value2"}

    def test_handles_missing_context_option(self):
        """apply_user_options should handle missing contextSlug gracefully."""
        spawner = MagicMock()
        spawner.beaker_context = "original"
        spawner.context_config = {}

        user_options = {}

        BeakerKubeSpawner.apply_user_options(spawner, user_options)

        # beaker_context should not be modified
        assert spawner.beaker_context == "original"

    def test_handles_missing_context_options(self):
        """apply_user_options should handle missing contextOptions gracefully."""
        spawner = MagicMock()
        spawner.beaker_context = ""
        spawner.context_config = {"original": "config"}

        user_options = {"contextSlug": "new-context"}

        BeakerKubeSpawner.apply_user_options(spawner, user_options)

        # context_config should not be modified
        assert spawner.context_config == {"original": "config"}

    def test_handles_empty_user_options(self):
        """apply_user_options should handle empty options dict."""
        spawner = MagicMock()
        spawner.beaker_context = "original"
        spawner.context_config = {"original": "config"}

        user_options = {}

        # Should not raise
        BeakerKubeSpawner.apply_user_options(spawner, user_options)

        assert spawner.beaker_context == "original"
        assert spawner.context_config == {"original": "config"}


class TestPolicyOverridePassing:
    """Vault policy overrides are resolved at spawn time and passed to the node.

    The beaker-node-config ConfigMap is rendered once by Helm and shared by every node,
    so per-launch policies have to travel through the pod environment instead.
    See .plans/secrets-round-1-node-secret-policies.md.
    """

    @pytest.fixture
    def db(self):
        """In-memory DB with the vault tables and a usable encryption key."""
        from cryptography.fernet import Fernet
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from jupyterhub.orm import Base
        from beakerhub.orm import EncryptedString

        previous = EncryptedString._fernet
        EncryptedString.set_key(Fernet.generate_key())
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        session = Session(engine)
        yield session
        session.close()
        engine.dispose()
        EncryptedString._fernet = previous

    @pytest.fixture
    def spawner(self, db):
        spawner = MagicMock()
        spawner.db = db
        spawner.debug = False
        spawner.default_tag = "latest"
        spawner.extra_container_config = {}
        spawner.node_env = {}
        spawner.node_policy_overrides = {}
        return spawner

    def test_passes_only_secrets_with_overrides(self, db, spawner):
        """Secrets at their defaults send nothing; the node already assumes defaults."""
        from beakerhub import orm

        db.add_all([
            orm.NodeSecret(env_var="PRIVATE_LLM_KEY", value="a"),
            orm.NodeSecret(
                env_var="SHARED_API_KEY",
                value="b",
                policies={"subkernel_environment_policy": "allow"},
            ),
        ])
        db.commit()

        BeakerKubeSpawner.apply_user_options(spawner, {})

        # Both values reach the pod...
        assert spawner.node_env == {"PRIVATE_LLM_KEY": "a", "SHARED_API_KEY": "b"}
        # ...but only the customized one carries policies.
        assert spawner.node_policy_overrides == {
            "SHARED_API_KEY": {"subkernel_environment_policy": "allow"},
        }

    def test_node_secret_policies_override_global(self, db, spawner):
        """A node-specific secret wins for policies exactly as it does for the value."""
        from beakerhub import orm

        node = orm.NodeImages(slug="test-node", repository="beaker/test-node", default_tag="latest")
        db.add(node)
        db.commit()
        db.add_all([
            orm.NodeSecret(
                env_var="SHARED_API_KEY",
                value="global",
                policies={"subkernel_environment_policy": "allow"},
            ),
            orm.NodeSecret(
                env_var="SHARED_API_KEY",
                value="node",
                node_image_id=node.id,
                policies={"ui_message_policy": "last4"},
            ),
        ])
        db.commit()

        BeakerKubeSpawner.apply_user_options(spawner, {"nodeSlug": "test-node"})

        assert spawner.node_env["SHARED_API_KEY"] == "node"
        assert spawner.node_policy_overrides == {"SHARED_API_KEY": {"ui_message_policy": "last4"}}

    def test_node_secret_without_policies_clears_inherited_ones(self, db, spawner):
        """Shadowing a permissive global must not leave its policies applied."""
        from beakerhub import orm

        node = orm.NodeImages(slug="test-node", repository="beaker/test-node", default_tag="latest")
        db.add(node)
        db.commit()
        db.add_all([
            orm.NodeSecret(
                env_var="SHARED_API_KEY",
                value="global",
                policies={"subkernel_environment_policy": "allow"},
            ),
            orm.NodeSecret(env_var="SHARED_API_KEY", value="node", node_image_id=node.id),
        ])
        db.commit()

        BeakerKubeSpawner.apply_user_options(spawner, {"nodeSlug": "test-node"})

        assert spawner.node_env["SHARED_API_KEY"] == "node"
        assert spawner.node_policy_overrides == {}

    def test_context_disabled_secret_sends_no_policies(self, db, spawner):
        """A secret disabled for the context contributes neither value nor policies."""
        from beakerhub import orm

        secret = orm.NodeSecret(
            env_var="SHARED_API_KEY",
            value="b",
            policies={"subkernel_environment_policy": "allow"},
        )
        context = orm.Context(
            slug="weather", display_name="Weather", source_key="pkg:weather",
        )
        db.add_all([secret, context])
        db.commit()
        db.execute(orm.beaker_context_secrets.insert().values(
            context_id=context.id, node_secret_id=secret.id, enabled=False,
        ))
        db.commit()

        BeakerKubeSpawner.apply_user_options(spawner, {"contextSlug": "weather"})

        assert spawner.node_env == {}
        assert spawner.node_policy_overrides == {}


class TestPolicyOverrideEnv:
    """Resolved overrides become one environment variable per policy axis.

    Each carrier is named `<ENV_VAR>_<policy_field><suffix>`, e.g.
    SHARED_API_KEY_subkernel_environment_policy_secret_policy=allow. The node's
    BeakerhubSecretsManager matches these back apart and consumes them.
    """

    @pytest.fixture
    def mock_spawner(self):
        spawner = MagicMock(spec=BeakerKubeSpawner)
        spawner.name = "test-session"
        spawner.beaker_context = ""
        spawner.default_beaker_context = "default"
        spawner.node_env = {}
        spawner.node_policy_overrides = {}
        spawner.policy_override_env_key_suffix = "_secret_policy"
        spawner.user = MagicMock()
        spawner.user.server_url = MagicMock(return_value="/user/testuser/test-session/")
        spawner.user.name = "testuser"
        return spawner

    def test_emits_one_variable_per_policy_axis(self, mock_spawner):
        mock_spawner.node_policy_overrides = {
            "SHARED_API_KEY": {
                "subkernel_environment_policy": "allow",
                "ui_message_policy": "last4",
            },
        }
        with patch.object(BeakerKubeSpawner.__bases__[0], "get_env", return_value={}):
            env = BeakerKubeSpawner.get_env(mock_spawner)

        assert env["SHARED_API_KEY_subkernel_environment_policy_secret_policy"] == "allow"
        assert env["SHARED_API_KEY_ui_message_policy_secret_policy"] == "last4"

    def test_keeps_secrets_and_policies_in_separate_variables(self, mock_spawner):
        """The value and its policies travel independently, and both arrive."""
        mock_spawner.node_env = {"SHARED_API_KEY": "the-real-value"}
        mock_spawner.node_policy_overrides = {
            "SHARED_API_KEY": {"subkernel_environment_policy": "allow"},
        }
        with patch.object(BeakerKubeSpawner.__bases__[0], "get_env", return_value={}):
            env = BeakerKubeSpawner.get_env(mock_spawner)

        assert env["SHARED_API_KEY"] == "the-real-value"
        assert env["SHARED_API_KEY_subkernel_environment_policy_secret_policy"] == "allow"

    def test_emits_nothing_when_there_are_no_overrides(self, mock_spawner):
        mock_spawner.node_policy_overrides = {}
        with patch.object(BeakerKubeSpawner.__bases__[0], "get_env", return_value={}):
            env = BeakerKubeSpawner.get_env(mock_spawner)

        assert not [key for key in env if key.endswith("_secret_policy")]

    def test_honors_a_configured_suffix(self, mock_spawner):
        mock_spawner.policy_override_env_key_suffix = "__POLICY"
        mock_spawner.node_policy_overrides = {
            "SHARED_API_KEY": {"ui_message_policy": "remove"},
        }
        with patch.object(BeakerKubeSpawner.__bases__[0], "get_env", return_value={}):
            env = BeakerKubeSpawner.get_env(mock_spawner)

        assert env["SHARED_API_KEY_ui_message_policy__POLICY"] == "remove"

    def test_carrier_names_are_what_the_node_matches(self, mock_spawner):
        """Round-trip guard: every key the spawner emits must parse back on the node.

        The two sides build and match these names independently, so a change to either
        format would otherwise silently strip the overrides.
        """
        from beakerhub.services.secrets.beakerhub import BeakerhubSecretsManager

        overrides = {
            "SHARED_API_KEY": {
                "subkernel_environment_policy": "allow",
                "ui_message_policy": "last4",
                "agent_message_policy": "remove",
                "beaker_kernel_environment_policy": "remove",
                "subkernel_message_policy": "redact",
            },
            # Digits and lowercase are legal in env var names.
            "S3_API_KEY": {"ui_message_policy": "redact"},
            "gpt4_token": {"agent_message_policy": "remove"},
        }
        mock_spawner.node_policy_overrides = overrides
        with patch.object(BeakerKubeSpawner.__bases__[0], "get_env", return_value={}):
            env = BeakerKubeSpawner.get_env(mock_spawner)

        regex = BeakerhubSecretsManager._default_public_key_regex(
            MagicMock(policy_override_env_key_suffix="_secret_policy")
        )
        recovered: dict[str, dict[str, str]] = {}
        for key, value in env.items():
            if (match := regex.match(key)):
                env_name, policy_field = match.groups()
                recovered.setdefault(env_name, {})[policy_field] = value

        assert recovered == overrides

    def test_announces_which_variables_came_from_the_vault(self, mock_spawner):
        """The node needs the full list, not just the ones carrying overrides.

        Discovery is by name heuristic on the node, so an innocuous-looking vault secret
        would otherwise get neither its policies nor any default protection.
        """
        from beakerhub.services.secrets import VAULT_ENV_VAR_LIST_KEY

        mock_spawner.node_env = {"SHARED_ENDPOINT": "a", "PRIVATE_LLM_KEY": "b"}
        mock_spawner.node_policy_overrides = {}
        with patch.object(BeakerKubeSpawner.__bases__[0], "get_env", return_value={}):
            env = BeakerKubeSpawner.get_env(mock_spawner)

        assert env[VAULT_ENV_VAR_LIST_KEY] == "PRIVATE_LLM_KEY,SHARED_ENDPOINT"

    def test_announces_nothing_when_the_vault_contributed_nothing(self, mock_spawner):
        from beakerhub.services.secrets import VAULT_ENV_VAR_LIST_KEY

        mock_spawner.node_env = {}
        with patch.object(BeakerKubeSpawner.__bases__[0], "get_env", return_value={}):
            env = BeakerKubeSpawner.get_env(mock_spawner)

        assert VAULT_ENV_VAR_LIST_KEY not in env

    def test_vault_list_variable_cannot_be_mistaken_for_a_secret(self):
        """If the name tripped the heuristics, the node would scrub env var names from output."""
        from beaker_notebook.services.secrets.manager import BeakerSecretsManager
        from beakerhub.services.secrets import VAULT_ENV_VAR_LIST_KEY

        name = VAULT_ENV_VAR_LIST_KEY.lower()
        anywhere = BeakerSecretsManager.env_key_detection_anywhere.default()
        suffixes = BeakerSecretsManager.env_key_detection_suffix.default()

        assert not any(substring in name for substring in anywhere), name
        assert not name.endswith(tuple(suffixes)), name
