# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""Unit tests for ORM cascade behavior."""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, event, exc, select, text
from sqlalchemy.orm import Session

from beakerhub.orm import (
    ApiKey,
    Context,
    EncryptedString,
    Integration,
    Language,
    NodeImages,
    NodeSecret,
    Workflow,
    WorkflowStage,
    beaker_context_api_keys,
    beaker_context_integrations,
    beaker_context_languages,
    beaker_context_workflows,
)
from jupyterhub.orm import Base


@pytest.fixture
def db():
    """Create an in-memory SQLite database with all tables and FK enforcement."""
    engine = create_engine("sqlite://", echo=False)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def context_with_relations(db: Session) -> Context:
    """Create a context with all relationship types populated."""
    # Create related entities
    language = Language(slug="python3", subkernel="python3", display_name="Python 3")
    api_key = ApiKey(env_var="TEST_KEY", display_name="Test Key")
    integration = Integration(slug="test-integration", name="Test Integration")
    workflow = Workflow(
        title="Test Workflow",
        source_key="test-pkg:test-workflow",
        source_package="test-pkg",
        source_path="workflows/test.yaml",
    )
    stage = WorkflowStage(
        workflow=workflow,
        name="Stage 1",
        sort_order=0,
    )
    db.add_all([language, api_key, integration, workflow, stage])
    db.flush()

    # Create context and attach relations
    context = Context(
        slug="test-context",
        display_name="Test Context",
        source_key="test-pkg:test-context",
        source_package="test-pkg",
    )
    context.languages.append(language)
    context.api_keys.append(api_key)
    context.integrations.append(integration)
    context.workflows.append(workflow)
    db.add(context)
    db.commit()

    return context


class TestContextCascadeDelete:
    """Verify that deleting a Context cascades through association tables
    but does NOT delete the related entities themselves."""

    def test_association_rows_removed_on_delete(self, db: Session, context_with_relations: Context):
        """Deleting a context should remove all association table rows."""
        ctx_id = context_with_relations.id

        # Verify associations exist before delete
        assert db.execute(select(beaker_context_languages).where(
            beaker_context_languages.c.context_id == ctx_id
        )).fetchall()
        assert db.execute(select(beaker_context_api_keys).where(
            beaker_context_api_keys.c.context_id == ctx_id
        )).fetchall()
        assert db.execute(select(beaker_context_integrations).where(
            beaker_context_integrations.c.context_id == ctx_id
        )).fetchall()
        assert db.execute(select(beaker_context_workflows).where(
            beaker_context_workflows.c.context_id == ctx_id
        )).fetchall()

        # Delete the context
        db.delete(context_with_relations)
        db.commit()

        # All association rows should be gone
        assert db.execute(select(beaker_context_languages).where(
            beaker_context_languages.c.context_id == ctx_id
        )).fetchall() == []
        assert db.execute(select(beaker_context_api_keys).where(
            beaker_context_api_keys.c.context_id == ctx_id
        )).fetchall() == []
        assert db.execute(select(beaker_context_integrations).where(
            beaker_context_integrations.c.context_id == ctx_id
        )).fetchall() == []
        assert db.execute(select(beaker_context_workflows).where(
            beaker_context_workflows.c.context_id == ctx_id
        )).fetchall() == []

    def test_related_entities_preserved_on_delete(self, db: Session, context_with_relations: Context):
        """Deleting a context should NOT delete related workflows, integrations, etc."""
        db.delete(context_with_relations)
        db.commit()

        # Related entities should still exist
        assert db.query(Language).filter(Language.slug == "python3").one()
        assert db.query(ApiKey).filter(ApiKey.env_var == "TEST_KEY").one()
        assert db.query(Integration).filter(Integration.slug == "test-integration").one()
        workflow = db.query(Workflow).filter(Workflow.source_key == "test-pkg:test-workflow").one()
        assert len(workflow.stages) == 1

    def test_context_row_removed_on_delete(self, db: Session, context_with_relations: Context):
        """The context row itself should be gone after delete."""
        db.delete(context_with_relations)
        db.commit()

        assert db.query(Context).filter(Context.slug == "test-context").first() is None


@pytest.fixture
def vault_key():
    """Initialize the encrypted-column key, restoring the prior one afterward."""
    previous = EncryptedString._fernet
    EncryptedString.set_key(Fernet.generate_key())
    yield
    EncryptedString._fernet = previous


class TestNodeSecretPolicies:
    """The sparse policy-override dict on NodeSecret.

    An absent axis means "use the default for a system secret", so an empty dict is
    the correct representation of "nothing overridden" -- see
    .plans/secrets-framework-background.md.
    """

    def test_defaults_to_empty_dict(self, db: Session, vault_key):
        secret = NodeSecret(env_var="SHARED_API_KEY", value="s3cret")
        db.add(secret)
        db.commit()
        db.expire_all()

        assert db.query(NodeSecret).one().policies == {}

    def test_explicit_none_falls_back_to_the_default(self, db: Session, vault_key):
        """An explicit None is indistinguishable from unset, so the default applies."""
        db.add(NodeSecret(env_var="SHARED_API_KEY", value="s3cret", policies=None))
        db.commit()
        db.expire_all()

        assert db.query(NodeSecret).one().policies == {}

    def test_column_rejects_null_at_the_db_level(self, db: Session, vault_key):
        """Rows written outside the ORM cannot leave policies NULL."""
        with pytest.raises(exc.IntegrityError):
            db.execute(text(
                "INSERT INTO beaker_node_secrets (env_var, value, policies) "
                "VALUES ('SHARED_API_KEY', X'00', NULL)"
            ))
        db.rollback()

    def test_round_trips_overrides(self, db: Session, vault_key):
        secret = NodeSecret(
            env_var="SHARED_API_KEY",
            value="s3cret",
            policies={
                "subkernel_environment_policy": "allow",
                "ui_message_policy": "last4",
            },
        )
        db.add(secret)
        db.commit()
        db.expire_all()

        assert db.query(NodeSecret).one().policies == {
            "subkernel_environment_policy": "allow",
            "ui_message_policy": "last4",
        }

    def test_stored_as_json_text(self, db: Session, vault_key):
        """JSONDict serializes to TEXT, which is what the migration adds."""
        db.add(NodeSecret(
            env_var="SHARED_API_KEY",
            value="s3cret",
            policies={"subkernel_environment_policy": "allow"},
        ))
        db.commit()

        raw = db.execute(text("SELECT policies FROM beaker_node_secrets")).scalar_one()
        assert raw == '{"subkernel_environment_policy": "allow"}'

    def test_overrides_are_replaced_not_merged(self, db: Session, vault_key):
        """Reassigning the dict is the update path; there is no partial merge."""
        secret = NodeSecret(
            env_var="SHARED_API_KEY",
            value="s3cret",
            policies={"subkernel_environment_policy": "allow"},
        )
        db.add(secret)
        db.commit()

        secret.policies = {"agent_message_policy": "remove"}
        db.commit()
        db.expire_all()

        assert db.query(NodeSecret).one().policies == {"agent_message_policy": "remove"}

    def test_policies_are_per_secret(self, db: Session, vault_key):
        """A node-scoped secret and a global secret carry independent policies."""
        node = NodeImages(slug="test-node", repository="beaker/test-node")
        db.add(node)
        db.commit()

        db.add_all([
            NodeSecret(env_var="PRIVATE_LLM_KEY", value="a", node_image_id=node.id),
            NodeSecret(
                env_var="SHARED_API_KEY",
                value="b",
                policies={"subkernel_environment_policy": "allow"},
            ),
        ])
        db.commit()
        db.expire_all()

        private = db.query(NodeSecret).filter_by(env_var="PRIVATE_LLM_KEY").one()
        shared = db.query(NodeSecret).filter_by(env_var="SHARED_API_KEY").one()
        assert private.policies == {}
        assert shared.policies == {"subkernel_environment_policy": "allow"}
