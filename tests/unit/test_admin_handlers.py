# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""Unit tests for the vault secret write path in beakerhub.admin_handlers.

`apply_node_secret_fields` is the single place that decides which fields a client may
write, shared by POST (upsert) and PUT. These tests pin that contract, since a field
handled in one path but not the other fails silently -- the request succeeds and the
value is quietly dropped.
"""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from jupyterhub.orm import Base

from beakerhub.admin_handlers import (
    NODE_SECRET_WRITABLE_FIELDS,
    AdminSecretVaultHandler,
    apply_node_secret_fields,
    serialize_node_secret,
    serialize_node_secret_with_value,
)
from beakerhub.orm import EncryptedString, NodeImages, NodeSecret


@pytest.fixture
def db():
    previous = EncryptedString._fernet
    EncryptedString.set_key(Fernet.generate_key())
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()
    EncryptedString._fernet = previous


class TestWritableFieldContract:
    def test_covers_the_fields_the_ui_sends(self):
        assert set(NODE_SECRET_WRITABLE_FIELDS) == {"value", "description", "policies"}

    def test_every_writable_field_is_a_column_on_the_model(self):
        for field in NODE_SECRET_WRITABLE_FIELDS:
            assert hasattr(NodeSecret, field), field

    def test_every_writable_field_is_also_readable(self):
        """A write-only field would be settable but invisible to the client."""
        secret = NodeSecret(env_var="X", value="v")
        readable = set(serialize_node_secret_with_value(secret))
        assert set(NODE_SECRET_WRITABLE_FIELDS) <= readable

    def test_identity_fields_are_not_writable_in_bulk(self):
        """env_var and node_image_id identify the secret, so each caller handles them."""
        assert "env_var" not in NODE_SECRET_WRITABLE_FIELDS
        assert "node_image_id" not in NODE_SECRET_WRITABLE_FIELDS


class TestApplyNodeSecretFields:
    def test_creating_applies_defaults_for_absent_fields(self):
        secret = NodeSecret(env_var="SHARED_API_KEY")
        apply_node_secret_fields(secret, {"value": "v"}, creating=True)

        assert secret.value == "v"
        assert secret.description is None
        assert secret.policies == {}

    def test_updating_leaves_absent_fields_alone(self):
        secret = NodeSecret(
            env_var="SHARED_API_KEY",
            value="old",
            description="a description",
            policies={"ui_message_policy": "last4"},
        )
        apply_node_secret_fields(secret, {"value": "new"}, creating=False)

        assert secret.value == "new"
        assert secret.description == "a description"
        assert secret.policies == {"ui_message_policy": "last4"}

    def test_writes_every_supplied_field(self):
        secret = NodeSecret(env_var="SHARED_API_KEY")
        body = {
            "value": "v",
            "description": "d",
            "policies": {"subkernel_environment_policy": "allow"},
        }
        apply_node_secret_fields(secret, body, creating=True)

        assert secret.value == "v"
        assert secret.description == "d"
        assert secret.policies == {"subkernel_environment_policy": "allow"}

    def test_policies_survive_an_update(self):
        """The bug this consolidation removes: policies dropped on the upsert path."""
        secret = NodeSecret(env_var="SHARED_API_KEY", value="old", policies={})
        apply_node_secret_fields(
            secret,
            {"value": "new", "policies": {"subkernel_environment_policy": "allow"}},
            creating=False,
        )

        assert secret.policies == {"subkernel_environment_policy": "allow"}

    def test_explicit_none_clears_a_field(self):
        secret = NodeSecret(env_var="SHARED_API_KEY", value="v", description="d")
        apply_node_secret_fields(secret, {"description": None}, creating=False)

        assert secret.description is None

    def test_policies_can_be_reset_to_defaults(self):
        """Clearing every override in the UI sends {}, which must be stored, not ignored."""
        secret = NodeSecret(
            env_var="SHARED_API_KEY", value="v", policies={"ui_message_policy": "last4"}
        )
        apply_node_secret_fields(secret, {"policies": {}}, creating=False)

        assert secret.policies == {}


class TestFindInScope:
    """Scope lookup mirrors the uq_node_secret_env_var constraint."""

    @pytest.fixture
    def handler(self, db):
        class Stub:
            pass

        stub = Stub()
        stub.db = db
        return stub

    def test_finds_a_global_secret(self, db, handler):
        db.add(NodeSecret(env_var="SHARED_API_KEY", value="v"))
        db.commit()

        found = AdminSecretVaultHandler._find_in_scope(handler, None, "SHARED_API_KEY")

        assert found is not None
        assert found.node_image_id is None

    def test_does_not_confuse_scopes(self, db, handler):
        """A node-scoped secret must not satisfy a lookup for the global one, or the
        upsert would update the wrong row."""
        node = NodeImages(slug="n", repository="r", default_tag="latest")
        db.add(node)
        db.commit()
        db.add(NodeSecret(env_var="SHARED_API_KEY", value="node", node_image_id=node.id))
        db.commit()

        assert AdminSecretVaultHandler._find_in_scope(handler, None, "SHARED_API_KEY") is None
        assert AdminSecretVaultHandler._find_in_scope(handler, node.id, "SHARED_API_KEY") is not None

    def test_returns_none_when_absent(self, db, handler):
        assert AdminSecretVaultHandler._find_in_scope(handler, None, "NOPE") is None


class TestSerialization:
    def test_list_view_omits_the_value(self):
        secret = NodeSecret(env_var="SHARED_API_KEY", value="v")
        assert "value" not in serialize_node_secret(secret)

    def test_list_view_includes_policies(self):
        """Policies are not sensitive, so the UI gets them without a per-secret fetch."""
        secret = NodeSecret(
            env_var="SHARED_API_KEY", value="v", policies={"ui_message_policy": "last4"}
        )
        assert serialize_node_secret(secret)["policies"] == {"ui_message_policy": "last4"}
