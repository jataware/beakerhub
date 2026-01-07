from __future__ import annotations

from uuid import uuid4

import alembic.command
import alembic.config
import sqlalchemy
from alembic.script import ScriptDirectory
from cryptography.fernet import Fernet
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    Table,
    Unicode,
    UniqueConstraint,
    BLOB,
    create_engine,
    event,
    exc,
    inspect,
    or_,
    select,
    text,
)
from sqlalchemy.orm import (
    Session as SQLSession,
    Mapped,
    declarative_base,
    declared_attr,
    interfaces,
    joinedload,
    object_session,
    relationship,
    sessionmaker,
)
from sqlalchemy.types import TypeDecorator

from jupyterhub.orm import (
    Base, JSONDict, JSONList, Server, User, utcnow
)


# ============================================
# Custom Column Types
# ============================================

class EncryptedString(TypeDecorator):
    """Stores a string value encrypted at rest using Fernet symmetric encryption.

    The encryption key must be set once at app startup via :meth:`set_key`
    before any DB operations touch encrypted columns.
    """
    impl = LargeBinary
    cache_ok = True

    _fernet: Fernet | None = None

    @classmethod
    def set_key(cls, key: str | bytes) -> None:
        """Initialize the Fernet instance with the vault encryption key."""
        if isinstance(key, str):
            key = key.encode("utf-8")
        cls._fernet = Fernet(key)

    @classmethod
    def _get_fernet(cls) -> Fernet:
        if cls._fernet is None:
            raise RuntimeError(
                "EncryptedString.set_key() must be called before using encrypted columns. "
                "Set c.BeakerHub.vault_encryption_key in your config."
            )
        return cls._fernet

    def process_bind_param(self, value: str | None, dialect) -> bytes | None:
        if value is None:
            return None
        return self._get_fernet().encrypt(value.encode("utf-8"))

    def process_result_value(self, value: bytes | None, dialect) -> str | None:
        if value is None:
            return None
        return self._get_fernet().decrypt(value).decode("utf-8")


# ============================================
# Junction Tables
# ============================================

session_server_mapping_table = Table(
    "session_server_map",
    Base.metadata,
    Column("session_id", ForeignKey("beaker_sessions.id"), primary_key=True),
    Column("server_id", ForeignKey("servers.id"), primary_key=True),
)

beaker_context_integrations = Table(
    "beaker_context_integrations",
    Base.metadata,
    Column("context_id", ForeignKey("beaker_contexts.id", ondelete="CASCADE"), primary_key=True),
    Column("integration_id", ForeignKey("beaker_integrations.id", ondelete="CASCADE"), primary_key=True),
    Column("sort_order", Integer, default=0),
)

beaker_context_api_keys = Table(
    "beaker_context_api_keys",
    Base.metadata,
    Column("context_id", ForeignKey("beaker_contexts.id", ondelete="CASCADE"), primary_key=True),
    Column("api_key_id", ForeignKey("beaker_api_keys.id", ondelete="CASCADE"), primary_key=True),
    Column("required", Boolean, default=True),
)

beaker_context_languages = Table(
    "beaker_context_languages",
    Base.metadata,
    Column("context_id", ForeignKey("beaker_contexts.id", ondelete="CASCADE"), primary_key=True),
    Column("language_slug", ForeignKey("beaker_languages.slug", ondelete="CASCADE"), primary_key=True),
)

beaker_context_workflows = Table(
    "beaker_context_workflows",
    Base.metadata,
    Column("context_id", ForeignKey("beaker_contexts.id", ondelete="CASCADE"), primary_key=True),
    Column("workflow_id", ForeignKey("beaker_workflows.id", ondelete="CASCADE"), primary_key=True),
    Column("is_context_default", Boolean, default=False),
    Column("sort_order", Integer, default=0),
)

beaker_context_roles = Table(
    "beaker_context_roles",
    Base.metadata,
    Column("context_id", ForeignKey("beaker_contexts.id", ondelete="CASCADE"), primary_key=True),
    Column("role_name", Unicode(255), primary_key=True),
)

beaker_context_secrets = Table(
    "beaker_context_secrets",
    Base.metadata,
    Column("context_id", ForeignKey("beaker_contexts.id", ondelete="CASCADE"), primary_key=True),
    Column("node_secret_id", ForeignKey("beaker_node_secrets.id", ondelete="CASCADE"), primary_key=True),
    Column("enabled", Boolean, default=True),
)

class BeakerSession(Base):
    """
    Beaker session store in database
    """

    __tablename__ = 'beaker_sessions'
    id = Column(Integer, primary_key=True)
    session_id = Column(Unicode(128), default=uuid4)
    started = Column(DateTime)

    # TODO: Add sharing (possibly using Shares table, but that expects a specific spawner)
    # shares: Mapped["Share"] = relationship()

    notebook_id = Column(Integer, ForeignKey("beaker_notebook.id", ondelete="SET NULL"), nullable=True)
    notebook: Mapped["Notebook"] = relationship()
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    user: Mapped["User"] = relationship()
    servers: Mapped[list["Server"]] = relationship(secondary=session_server_mapping_table)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)


class Notebook(Base):
    """
    Stores the notebook contents in the database
    """

    __tablename__ = 'beaker_notebook'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(128))
    content = Column(JSONDict)

    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    owner = relationship("User")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)


class NodeImages(Base):
    """
    Docker images which contain the beaker notebook, and some set of contexts installed
    """

    __tablename__ = 'beaker_node_images'
    id = Column(Integer, primary_key=True)
    slug = Column(Unicode(100), unique=True, nullable=False)
    default_registry = Column(Unicode(128))
    repository = Column(Unicode(255))
    default_tag = Column(Unicode(128))
    metadata_ = Column("metadata", JSONDict, default={})
    enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)

    # Relationships
    tasks: Mapped[list["NodeImageTask"]] = relationship(
        "NodeImageTask",
        back_populates="node_image",
        cascade="all, delete-orphan",
        order_by="NodeImageTask.created_at.desc()",
    )
    secrets: Mapped[list["NodeSecret"]] = relationship(
        "NodeSecret",
        back_populates="node_image",
        cascade="all, delete-orphan",
    )

    @property
    def default_img_string(self) -> str:
        return f"{self.default_registry}/{self.repository}:{self.default_tag}"


class NodeImageTask(Base):
    """
    Tracks tasks (K8s Jobs) run against node images.

    Each task represents a single Job execution — e.g., running `beaker context dump`
    to import context data from an image.
    """
    __tablename__ = 'beaker_node_image_tasks'
    id = Column(Integer, primary_key=True)

    node_image_id = Column(
        Integer,
        ForeignKey("beaker_node_images.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_image: Mapped["NodeImages"] = relationship("NodeImages", back_populates="tasks")

    task_type = Column(Unicode(64), nullable=False)        # "context_import", etc.
    status = Column(Unicode(32), nullable=False, default="pending")  # pending, running, completed, failed
    job_name = Column(Unicode(255), nullable=True)         # K8s Job name
    callback_token = Column(Unicode(128), nullable=True)   # Auth token for reporter callback
    result = Column(JSONDict, nullable=True)               # Ingestion stats on success
    error = Column(Unicode(4096), nullable=True)           # Error message on failure

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)


class NodeSecret(Base):
    """Encrypted secret key-value pairs associated with a node image.

    Secrets with ``node_image_id = NULL`` are global defaults that apply to
    every spawned node.  Per-node secrets override globals when the same
    ``env_var`` exists.

    ``policies`` holds admin overrides for the secret-handling policies defined by
    ``beaker_notebook.lib.secrets``, keyed on the policy field name, e.g.::

        {"subkernel_environment_policy": "allow", "ui_message_policy": "last4"}

    The dict is *sparse*: an absent key means "use the default for a system secret"
    (upstream's ``SystemEnvironmentSecret``), so an unrecognized or newly-added policy
    axis simply stays at its default rather than breaking existing rows.  Values are
    upstream's ``PolicyTypes``: ``allow``, ``redact``, ``remove``, ``last4``.
    """
    __tablename__ = 'beaker_node_secrets'
    __table_args__ = (
        UniqueConstraint("node_image_id", "env_var", name="uq_node_secret_env_var"),
    )

    id = Column(Integer, primary_key=True)
    node_image_id = Column(
        Integer,
        ForeignKey("beaker_node_images.id", ondelete="CASCADE"),
        nullable=True,
    )
    env_var = Column(Unicode(255), nullable=False)
    value = Column(EncryptedString, nullable=False)
    description = Column(Unicode(1024), nullable=True)
    policies = Column(
        JSONDict,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)

    node_image: Mapped[NodeImages | None] = relationship(
        "NodeImages",
        back_populates="secrets",
    )


class Context(Base):
    """
    Stores information about contexts.

    Contexts are discovered from Python packages installed in Docker images.
    They can be shared across multiple workflows and have associated integrations,
    API keys, and languages.
    """
    __tablename__ = 'beaker_contexts'
    id = Column(Integer, primary_key=True)

    # Source tracking
    source_key = Column(Unicode(255), unique=True)     # "package_name:context_slug"
    source_package = Column(Unicode(255))              # e.g., "beaker-weather"
    slug = Column(Unicode(100), nullable=False)

    # Display metadata
    display_name = Column(Unicode(255), nullable=False)
    description = Column(Unicode(4096))
    icon = Column(Unicode(512))                        # URL or vue:// scheme
    theme = Column(Unicode(50), default='data-science')
    icon_file = Column(Unicode(256))                   # deprecated, use icon

    # Technical metadata

    weight = Column(Integer, default=50)
    default_payload = Column(JSONDict, default={})

    # Image relationship (SET NULL on delete - don't cascade delete context when image removed)
    image_id = Column(Integer, ForeignKey("beaker_node_images.id", ondelete="SET NULL"), nullable=True)
    image: Mapped["NodeImages"] = relationship("NodeImages")

    # Status
    enabled = Column(Boolean, default=False)
    version = Column(Unicode(32), nullable=True, default=None)

    # Timestamps
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)

    # Relationships
    integrations: Mapped[list["Integration"]] = relationship(
        "Integration",
        secondary=beaker_context_integrations,
        back_populates="contexts"
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(
        "ApiKey",
        secondary=beaker_context_api_keys,
        back_populates="contexts"
    )
    languages: Mapped[list["Language"]] = relationship(
        "Language",
        secondary=beaker_context_languages,
        back_populates="contexts"
    )
    workflows: Mapped[list["Workflow"]] = relationship(
        "Workflow",
        secondary=beaker_context_workflows,
        back_populates="contexts"
    )
    vault_secrets: Mapped[list["NodeSecret"]] = relationship(
        "NodeSecret",
        secondary=beaker_context_secrets,
    )


# ============================================
# Reference Tables
# ============================================

class ApiKey(Base):
    """API key definitions that contexts may require."""
    __tablename__ = 'beaker_api_keys'
    id = Column(Integer, primary_key=True)
    env_var = Column(Unicode(100), unique=True, nullable=False)  # e.g., "API_WINDY_POINT_FORECAST"
    display_name = Column(Unicode(255), nullable=False)          # e.g., "Windy API"
    description = Column(Unicode(1024))
    required = Column(Boolean, default=True)

    contexts: Mapped[list["Context"]] = relationship(
        "Context",
        secondary=beaker_context_api_keys,
        back_populates="api_keys"
    )


class WorkflowCategory(Base):
    """Categories for organizing workflows."""
    __tablename__ = 'beaker_workflow_categories'
    slug = Column(Unicode(100), primary_key=True)        # e.g., "aviation-weather"
    display_name = Column(Unicode(255), nullable=False)
    description = Column(Unicode(1024))
    sort_order = Column(Integer, default=0)


class Language(Base):
    """Available subkernels/languages."""
    __tablename__ = 'beaker_languages'
    slug = Column(Unicode(50), primary_key=True)         # e.g., "python3"
    subkernel = Column(Unicode(50), nullable=False)
    display_name = Column(Unicode(100))

    contexts: Mapped[list["Context"]] = relationship(
        "Context",
        secondary=beaker_context_languages,
        back_populates="languages"
    )


# ============================================
# Integration
# ============================================

class Integration(Base):
    """Integration definitions, deduplicated across contexts."""
    __tablename__ = 'beaker_integrations'
    id = Column(Integer, primary_key=True)

    # Identity
    slug = Column(Unicode(100), unique=True, nullable=False)  # namespaced: "beaker-weather:noaa_weather_api"
    source_package = Column(Unicode(255))
    source_uuid = Column(Unicode(36))                         # UUID from api.yaml
    source_path = Column(Unicode(500))                        # relative path in package

    # Content
    name = Column(Unicode(255), nullable=False)
    description = Column(Unicode(4096))
    content_hash = Column(Unicode(64))                        # SHA256 for change detection

    # Status
    enabled = Column(Boolean, default=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)

    contexts: Mapped[list["Context"]] = relationship(
        "Context",
        secondary=beaker_context_integrations,
        back_populates="integrations"
    )


# ============================================
# Workflow
# ============================================

class Workflow(Base):
    """
    Workflow definitions.

    Workflows can be shared across multiple contexts via junction table.
    When a workflow is deleted, its stages are cascade deleted.
    When a context is deleted, the workflow is NOT deleted (just the junction record).
    """
    __tablename__ = 'beaker_workflows'
    id = Column(Integer, primary_key=True)

    # Identity & Source
    source_key = Column(Unicode(500), unique=True)            # "package:file_path"
    source_package = Column(Unicode(255))
    source_path = Column(Unicode(500))
    content_hash = Column(Unicode(64))

    # Content
    title = Column(Unicode(255), nullable=False)
    human_description = Column(Unicode(4096))
    agent_description = Column(Unicode(8192))
    example_prompt = Column(Unicode(2048))
    category_slug = Column(
        Unicode(100),
        ForeignKey("beaker_workflow_categories.slug", ondelete="SET NULL"),
        nullable=True
    )
    category: Mapped["WorkflowCategory"] = relationship("WorkflowCategory")

    # Flags
    hidden = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)
    metadata_ = Column("metadata", JSONDict, default={})

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)

    # Relationships
    contexts: Mapped[list["Context"]] = relationship(
        "Context",
        secondary=beaker_context_workflows,
        back_populates="workflows"
    )
    stages: Mapped[list["WorkflowStage"]] = relationship(
        "WorkflowStage",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowStage.sort_order"
    )


class WorkflowStage(Base):
    """Stages within workflows."""
    __tablename__ = 'beaker_workflow_stages'
    id = Column(Integer, primary_key=True)

    workflow_id = Column(
        Integer,
        ForeignKey("beaker_workflows.id", ondelete="CASCADE"),
        nullable=False
    )
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="stages")

    name = Column(Unicode(255), nullable=False)
    sort_order = Column(Integer, nullable=False)
    description = Column(JSONList, default=[])                # Array of strings
    metadata_ = Column("metadata", JSONDict, default={})
