from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, TypedDict

from jinja2.loaders import FileSystemLoader
from jupyter_client.jsonutil import json_default
from sqlalchemy import insert
from sqlalchemy.orm import Session

from .orm import (
    Context,
    Integration,
    Language,
    NodeImages,
    Workflow,
    WorkflowCategory,
    WorkflowStage,
    beaker_context_integrations,
    beaker_context_languages,
    beaker_context_workflows,
)


def to_json(obj) -> str:
    """Simple wrapper to ease ensuring compliant json"""
    return json.dumps(obj, default=json_default)


# ============================================
# Type Definitions for Original Format
# (context_details.json structure)
# ============================================

class OriginalLanguageDict(TypedDict):
    slug: str
    subkernel: str


class OriginalIntegrationDict(TypedDict):
    slug: str
    name: str
    description: str


class OriginalWorkflowStageDict(TypedDict):
    name: str
    metadata: dict[str, Any]
    description: list[str]


class OriginalWorkflowDict(TypedDict):
    title: str
    agent_description: str
    human_description: str
    example_prompt: str
    stages: list[OriginalWorkflowStageDict]
    hidden: bool
    is_context_default: bool
    category: str
    metadata: dict[str, Any]


class OriginalContextDict(TypedDict):
    slug: str
    display_name: str
    description: str
    image: str
    weight: int
    languages: list[OriginalLanguageDict]
    defaultPayload: str
    integrations: list[OriginalIntegrationDict]
    workflows: list[OriginalWorkflowDict]


OriginalContextDetailsDict = dict[str, OriginalContextDict]


# ============================================
# Type Definitions for Interchange Format
# ============================================

class InterchangePackageInfo(TypedDict):
    name: str
    version: str
    source_path: str


class InterchangeIntegration(TypedDict):
    uuid: str
    slug: str
    specification_path: str
    name: str
    description: str
    content_hash: str


class InterchangeApiKey(TypedDict):
    env_var: str
    display_name: str
    description: str | None


class InterchangeWorkflowStage(TypedDict):
    name: str
    sort_order: int
    description: list[str]
    metadata: dict[str, Any]


class InterchangeWorkflow(TypedDict):
    file_path: str
    content_hash: str
    title: str
    human_description: str
    agent_description: str
    example_prompt: str
    category_slug: str | None
    hidden: bool
    metadata: dict[str, Any]
    stages: list[InterchangeWorkflowStage]


class InterchangeWorkflowRef(TypedDict):
    file_path: str
    is_context_default: bool
    sort_order: int


class InterchangeContext(TypedDict):
    slug: str
    class_name: str
    module_path: str
    display_name: str | None
    description: str | None
    icon: str | None
    theme: str | None
    weight: int
    image: str | None
    default_payload: str
    integration_uuids: list[str]
    api_key_env_vars: list[str]
    language_slugs: list[str]
    workflow_refs: list[InterchangeWorkflowRef]


class InterchangeDump(TypedDict):
    dump_version: str
    generated_at: str
    package: InterchangePackageInfo
    integrations: list[InterchangeIntegration]
    api_keys: list[InterchangeApiKey]
    workflows: list[InterchangeWorkflow]
    contexts: list[InterchangeContext]


# ============================================
# Icon/Theme Inference Utilities
# ============================================

def infer_icon_from_slug(slug: str) -> str:
    """
    Infer a default icon URL from the context slug.
    Returns a vue:// scheme URL for built-in Vue components.
    """
    lower = slug.lower()
    if "weather" in lower or "aviation" in lower or "space" in lower:
        return "vue://components/icons/WeatherIcon.vue"
    elif "bio" in lower or "medical" in lower:
        return "vue://components/icons/BiomedicalIcon.vue"
    elif "geo" in lower or "spatial" in lower:
        return "vue://components/icons/GeospatialIcon.vue"
    elif "fire" in lower or "wildfire" in lower:
        return "vue://components/icons/WildfireIcon.vue"
    return "vue://components/icons/DataScienceIcon.vue"


def infer_theme_from_slug(slug: str) -> str:
    """Infer a default theme from the context slug."""
    lower = slug.lower()
    if "weather" in lower or "aviation" in lower or "space" in lower:
        return "weather"
    elif "bio" in lower or "medical" in lower:
        return "biomedical"
    return "data-science"


# ============================================
# Content Hash Utilities
# ============================================

def compute_content_hash(content: str | dict | list) -> str:
    """Compute SHA256 hash of content for change detection."""
    if isinstance(content, (dict, list)):
        content = json.dumps(content, sort_keys=True, default=str)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ============================================
# Original Format Ingestion
# ============================================

def ingest_original_format(
    db: Session,
    data: OriginalContextDetailsDict,
    source_package: str = "legacy",
    enable_contexts: bool = True,
) -> dict[str, Any]:
    """
    Ingest context data from the original context_details.json format into the database.

    This function handles:
    - Deduplication of integrations across contexts
    - Creation of languages
    - Creation of workflow categories
    - Creation of workflows and stages
    - Junction table relationships

    Args:
        db: SQLAlchemy session
        data: Dictionary of contexts from context_details.json
        source_package: Package name to use for source tracking
        enable_contexts: Whether to enable contexts by default

    Returns:
        Dictionary with counts of created/updated records
    """
    stats = {
        "contexts_created": 0,
        "contexts_updated": 0,
        "integrations_created": 0,
        "workflows_created": 0,
        "workflow_stages_created": 0,
        "languages_created": 0,
        "categories_created": 0,
    }

    # Track integrations by slug to deduplicate
    integration_cache: dict[str, Integration] = {}
    language_cache: dict[str, Language] = {}
    category_cache: dict[str, WorkflowCategory] = {}
    workflow_cache: dict[str, Workflow] = {}

    # First pass: collect all unique integrations, languages, and categories
    all_integrations: dict[str, OriginalIntegrationDict] = {}
    all_languages: dict[str, OriginalLanguageDict] = {}
    all_categories: set[str] = set()

    for context_slug, context_data in data.items():
        for integration in context_data.get("integrations", []):
            all_integrations[integration["slug"]] = integration

        for language in context_data.get("languages", []):
            all_languages[language["slug"]] = language

        for workflow in context_data.get("workflows", []):
            if workflow.get("category"):
                all_categories.add(workflow["category"])

    # Create/update languages
    for lang_slug, lang_data in all_languages.items():
        existing = db.query(Language).filter(Language.slug == lang_slug).first()
        if existing:
            language_cache[lang_slug] = existing
        else:
            language = Language(
                slug=lang_slug,
                subkernel=lang_data["subkernel"],
                display_name=lang_slug.replace("_", " ").title(),
            )
            db.add(language)
            language_cache[lang_slug] = language
            stats["languages_created"] += 1

    # Create/update workflow categories
    for category_slug in all_categories:
        existing = db.query(WorkflowCategory).filter(WorkflowCategory.slug == category_slug).first()
        if existing:
            category_cache[category_slug] = existing
        else:
            category = WorkflowCategory(
                slug=category_slug,
                display_name=category_slug.replace("-", " ").title(),
            )
            db.add(category)
            category_cache[category_slug] = category
            stats["categories_created"] += 1

    # Create/update integrations
    for int_slug, int_data in all_integrations.items():
        namespaced_slug = f"{source_package}:{int_slug}"
        existing = db.query(Integration).filter(Integration.slug == namespaced_slug).first()

        if existing:
            # Update if changed
            existing.name = int_data["name"]
            existing.description = int_data["description"]
            integration_cache[int_slug] = existing
        else:
            integration = Integration(
                slug=namespaced_slug,
                source_package=source_package,
                name=int_data["name"],
                description=int_data["description"],
                content_hash=compute_content_hash(int_data),
                enabled=True,
            )
            db.add(integration)
            integration_cache[int_slug] = integration
            stats["integrations_created"] += 1

    db.flush()  # Ensure IDs are assigned

    # Create/update contexts
    for context_slug, context_data in data.items():
        source_key = f"{source_package}:{context_slug}"
        existing_context = db.query(Context).filter(Context.slug == context_slug).first()

        if existing_context:
            # Update existing context
            existing_context.display_name = context_data["display_name"]
            existing_context.description = context_data["description"]
            existing_context.weight = context_data.get("weight", 50)
            existing_context.default_payload = _parse_payload(context_data.get("defaultPayload", "{}"))
            context = existing_context
            stats["contexts_updated"] += 1
        else:
            # Create new context
            context = Context(
                slug=context_slug,
                source_key=source_key,
                source_package=source_package,
                display_name=context_data["display_name"],
                description=context_data["description"],
                icon=infer_icon_from_slug(context_slug),
                theme=infer_theme_from_slug(context_slug),
                weight=context_data.get("weight", 50),
                default_payload=_parse_payload(context_data.get("defaultPayload", "{}")),
                enabled=enable_contexts,
            )
            db.add(context)
            stats["contexts_created"] += 1

        db.flush()  # Ensure context ID is assigned

        # Link integrations
        context.integrations = []
        for idx, int_data in enumerate(context_data.get("integrations", [])):
            integration = integration_cache.get(int_data["slug"])
            if integration:
                context.integrations.append(integration)

        # Link languages
        context.languages = []
        for lang_data in context_data.get("languages", []):
            language = language_cache.get(lang_data["slug"])
            if language:
                context.languages.append(language)

        # Create/update workflows for this context
        for idx, workflow_data in enumerate(context_data.get("workflows", [])):
            workflow_source_key = f"{source_package}:{context_slug}:{workflow_data['title']}"

            # Check if workflow already exists
            existing_workflow = db.query(Workflow).filter(Workflow.source_key == workflow_source_key).first()

            if existing_workflow:
                workflow = existing_workflow
                # Update workflow fields
                workflow.title = workflow_data["title"]
                workflow.human_description = workflow_data.get("human_description", "")
                workflow.agent_description = workflow_data.get("agent_description", "")
                workflow.example_prompt = workflow_data.get("example_prompt", "")
                workflow.hidden = workflow_data.get("hidden", False)
                workflow.metadata_ = workflow_data.get("metadata", {})

                # Update category
                category_slug = workflow_data.get("category")
                workflow.category_slug = category_slug if category_slug else None

                # Clear and recreate stages
                workflow.stages = []
                db.flush()
            else:
                category_slug = workflow_data.get("category")
                workflow = Workflow(
                    source_key=workflow_source_key,
                    source_package=source_package,
                    title=workflow_data["title"],
                    human_description=workflow_data.get("human_description", ""),
                    agent_description=workflow_data.get("agent_description", ""),
                    example_prompt=workflow_data.get("example_prompt", ""),
                    category_slug=category_slug if category_slug else None,
                    hidden=workflow_data.get("hidden", False),
                    enabled=True,
                    metadata_=workflow_data.get("metadata", {}),
                    content_hash=compute_content_hash(workflow_data),
                )
                db.add(workflow)
                stats["workflows_created"] += 1

            db.flush()

            # Create stages
            for stage_idx, stage_data in enumerate(workflow_data.get("stages", [])):
                stage = WorkflowStage(
                    workflow_id=workflow.id,
                    name=stage_data["name"],
                    sort_order=stage_idx,
                    description=stage_data.get("description", []),
                    metadata_=stage_data.get("metadata", {}),
                )
                db.add(stage)
                stats["workflow_stages_created"] += 1

            # Link workflow to context via junction table
            if workflow not in context.workflows:
                # Use raw insert for junction table to set is_context_default
                db.execute(
                    insert(beaker_context_workflows).values(
                        context_id=context.id,
                        workflow_id=workflow.id,
                        is_context_default=workflow_data.get("is_context_default", False),
                        sort_order=idx,
                    ).prefix_with("OR IGNORE")
                )

    db.commit()
    return stats


def _parse_payload(payload: str | dict) -> dict:
    """Parse defaultPayload which may be a JSON string or dict."""
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            return json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            return {}
    return {}


# ============================================
# Interchange Format Serialization
# ============================================

def serialize_interchange_dump(
    db: Session,
    package_name: str,
    package_version: str = "0.0.0",
    source_path: str = "",
) -> InterchangeDump:
    """
    Serialize database records for a given package into the interchange format.

    Args:
        db: SQLAlchemy session
        package_name: Filter by source package name
        package_version: Version to include in dump
        source_path: Source path to include in dump

    Returns:
        InterchangeDump dictionary
    """
    # Query contexts for this package
    contexts = db.query(Context).filter(Context.source_package == package_name).all()

    # Collect all related integrations
    integration_set: dict[int, Integration] = {}
    workflow_set: dict[int, Workflow] = {}

    for context in contexts:
        for integration in context.integrations:
            integration_set[integration.id] = integration
        for workflow in context.workflows:
            workflow_set[workflow.id] = workflow

    # Serialize integrations
    integrations: list[InterchangeIntegration] = []
    for integration in integration_set.values():
        integrations.append({
            "uuid": integration.source_uuid or "",
            "slug": integration.slug.split(":")[-1] if ":" in integration.slug else integration.slug,
            "specification_path": integration.source_path or "",
            "name": integration.name,
            "description": integration.description or "",
            "content_hash": integration.content_hash or "",
        })

    # Serialize workflows
    workflows: list[InterchangeWorkflow] = []
    for workflow in workflow_set.values():
        stages: list[InterchangeWorkflowStage] = []
        for stage in workflow.stages:
            stages.append({
                "name": stage.name,
                "sort_order": stage.sort_order,
                "description": stage.description or [],
                "metadata": stage.metadata_ or {},
            })

        workflows.append({
            "file_path": workflow.source_path or workflow.source_key or "",
            "content_hash": workflow.content_hash or "",
            "title": workflow.title,
            "human_description": workflow.human_description or "",
            "agent_description": workflow.agent_description or "",
            "example_prompt": workflow.example_prompt or "",
            "category_slug": workflow.category_slug,
            "hidden": workflow.hidden,
            "metadata": workflow.metadata_ or {},
            "stages": stages,
        })

    # Serialize contexts
    context_records: list[InterchangeContext] = []
    for context in contexts:
        # Get workflow refs with junction table data
        workflow_refs: list[InterchangeWorkflowRef] = []
        for idx, workflow in enumerate(context.workflows):
            # Query junction table for is_context_default
            junction = db.execute(
                beaker_context_workflows.select().where(
                    beaker_context_workflows.c.context_id == context.id,
                    beaker_context_workflows.c.workflow_id == workflow.id,
                )
            ).first()

            workflow_refs.append({
                "file_path": workflow.source_path or workflow.source_key or "",
                "is_context_default": junction.is_context_default if junction else False,
                "sort_order": junction.sort_order if junction else idx,
            })

        context_records.append({
            "slug": context.slug,
            "class_name": "",  # Not stored in DB currently
            "module_path": "",  # Not stored in DB currently
            "display_name": context.display_name,
            "description": context.description,
            "icon": context.icon,
            "theme": context.theme,
            "weight": context.weight,
            "image": None,  # Image is relationship, not stored directly
            "default_payload": json.dumps(context.default_payload) if context.default_payload else "{}",
            "integration_uuids": [i.source_uuid or "" for i in context.integrations],
            "api_key_env_vars": [ak.env_var for ak in context.api_keys],
            "language_slugs": [lang.slug for lang in context.languages],
            "workflow_refs": workflow_refs,
        })

    return {
        "dump_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package": {
            "name": package_name,
            "version": package_version,
            "source_path": source_path,
        },
        "integrations": integrations,
        "api_keys": [],  # API keys not in original format
        "workflows": workflows,
        "contexts": context_records,
    }


def serialize_interchange_to_json(dump: InterchangeDump) -> str:
    """Serialize an InterchangeDump to JSON string."""
    return json.dumps(dump, indent=2, default=str)


# ============================================
# Interchange Format Deserialization
# ============================================

def deserialize_interchange_dump(json_str: str) -> InterchangeDump:
    """Deserialize JSON string to InterchangeDump."""
    return json.loads(json_str)


def ingest_interchange_dump(
    db: Session,
    dump: InterchangeDump,
    node_image: "NodeImages",
    enable_contexts: bool = True,
    preserve_curated: bool = True,
) -> dict[str, Any]:
    """
    Ingest context data from the interchange format into the database.

    All entities are scoped to the given node_image. Within a single image,
    contexts share integrations/workflows/languages. Identical slugs from
    different images are treated as separate records (via source_key prefixing).

    This function handles:
    - Scoping all source_keys to the node image
    - Deduplication of integrations by (image_slug, package_name, uuid)
    - Content hash comparison for updates
    - Preservation of curated fields (icon, theme, display_name) if preserve_curated=True
    - Setting Context.image_id for all created/updated contexts

    Args:
        db: SQLAlchemy session
        dump: InterchangeDump dictionary
        node_image: The NodeImages record this dump came from
        enable_contexts: Whether to enable new contexts by default
        preserve_curated: Whether to preserve manually curated fields on update

    Returns:
        Dictionary with counts of created/updated records
    """
    stats = {
        "contexts_created": 0,
        "contexts_updated": 0,
        "integrations_created": 0,
        "integrations_updated": 0,
        "workflows_created": 0,
        "workflows_updated": 0,
        "workflow_stages_created": 0,
        "languages_created": 0,
        "categories_created": 0,
    }

    image_slug = node_image.slug
    package_name = dump["package"]["name"]
    package_version = dump["package"]["version"]

    # Caches for lookups
    integration_cache: dict[str, Integration] = {}  # uuid -> Integration
    workflow_cache: dict[str, Workflow] = {}  # file_path -> Workflow
    language_cache: dict[str, Language] = {}
    category_cache: dict[str, WorkflowCategory] = {}

    # Collect all categories from workflows
    all_categories: set[str] = set()
    for workflow in dump.get("workflows", []):
        if workflow.get("category_slug"):
            all_categories.add(workflow["category_slug"])

    # Create/update workflow categories (shared globally — not image-scoped)
    for category_slug in all_categories:
        existing = db.query(WorkflowCategory).filter(WorkflowCategory.slug == category_slug).first()
        if existing:
            category_cache[category_slug] = existing
        else:
            category = WorkflowCategory(
                slug=category_slug,
                display_name=category_slug.replace("-", " ").title(),
            )
            db.add(category)
            category_cache[category_slug] = category
            stats["categories_created"] += 1

    # Create/update integrations (scoped to image)
    for int_data in dump.get("integrations", []):
        namespaced_slug = f"{image_slug}:{package_name}:{int_data['slug']}"

        existing = db.query(Integration).filter(
            Integration.slug == namespaced_slug,
        ).first()

        if existing:
            # Check if content changed
            if existing.content_hash != int_data["content_hash"]:
                existing.name = int_data["name"]
                existing.description = int_data["description"]
                existing.content_hash = int_data["content_hash"]
                existing.source_path = int_data["specification_path"]
                stats["integrations_updated"] += 1
            integration_cache[int_data["uuid"]] = existing
        else:
            integration = Integration(
                slug=namespaced_slug,
                source_package=package_name,
                source_uuid=int_data["uuid"],
                source_path=int_data["specification_path"],
                name=int_data["name"],
                description=int_data["description"],
                content_hash=int_data["content_hash"],
                enabled=True,
            )
            db.add(integration)
            integration_cache[int_data["uuid"]] = integration
            stats["integrations_created"] += 1

    db.flush()

    # Create/update workflows (scoped to image)
    for wf_data in dump.get("workflows", []):
        source_key = f"{image_slug}:{package_name}:{wf_data['file_path']}"

        existing = db.query(Workflow).filter(Workflow.source_key == source_key).first()

        if existing:
            # Check if content changed
            if existing.content_hash != wf_data["content_hash"]:
                existing.title = wf_data["title"]
                existing.human_description = wf_data["human_description"]
                existing.agent_description = wf_data["agent_description"]
                existing.example_prompt = wf_data["example_prompt"]
                existing.category_slug = wf_data["category_slug"]
                existing.hidden = wf_data["hidden"]
                existing.metadata_ = wf_data["metadata"]
                existing.content_hash = wf_data["content_hash"]

                # Recreate stages
                existing.stages = []
                db.flush()

                for stage_data in wf_data.get("stages", []):
                    stage = WorkflowStage(
                        workflow_id=existing.id,
                        name=stage_data["name"],
                        sort_order=stage_data["sort_order"],
                        description=stage_data["description"],
                        metadata_=stage_data["metadata"],
                    )
                    db.add(stage)
                    stats["workflow_stages_created"] += 1

                stats["workflows_updated"] += 1

            workflow_cache[wf_data["file_path"]] = existing
        else:
            workflow = Workflow(
                source_key=source_key,
                source_package=package_name,
                source_path=wf_data["file_path"],
                title=wf_data["title"],
                human_description=wf_data["human_description"],
                agent_description=wf_data["agent_description"],
                example_prompt=wf_data["example_prompt"],
                category_slug=wf_data["category_slug"],
                hidden=wf_data["hidden"],
                enabled=True,
                metadata_=wf_data["metadata"],
                content_hash=wf_data["content_hash"],
            )
            db.add(workflow)
            db.flush()

            # Create stages
            for stage_data in wf_data.get("stages", []):
                stage = WorkflowStage(
                    workflow_id=workflow.id,
                    name=stage_data["name"],
                    sort_order=stage_data["sort_order"],
                    description=stage_data["description"],
                    metadata_=stage_data["metadata"],
                )
                db.add(stage)
                stats["workflow_stages_created"] += 1

            workflow_cache[wf_data["file_path"]] = workflow
            stats["workflows_created"] += 1

    db.flush()

    # Create/update contexts (scoped to image)
    for ctx_data in dump.get("contexts", []):
        source_key = f"{image_slug}:{package_name}:{ctx_data['slug']}"
        # Context slugs are also scoped to the image to avoid collisions
        scoped_slug = f"{image_slug}:{ctx_data['slug']}"

        # Ensure languages exist (shared globally — not image-scoped)
        for lang_slug in ctx_data.get("language_slugs", []):
            if lang_slug not in language_cache:
                existing_lang = db.query(Language).filter(Language.slug == lang_slug).first()
                if existing_lang:
                    language_cache[lang_slug] = existing_lang
                else:
                    language = Language(
                        slug=lang_slug,
                        subkernel=lang_slug,
                        display_name=lang_slug.replace("_", " ").title(),
                    )
                    db.add(language)
                    language_cache[lang_slug] = language
                    stats["languages_created"] += 1

        db.flush()

        existing = db.query(Context).filter(Context.source_key == source_key).first()

        if existing:
            # Preserve curated fields if requested
            if preserve_curated:
                curated_icon = existing.icon
                curated_theme = existing.theme
                curated_display_name = existing.display_name if existing.display_name else ctx_data.get("display_name")
                curated_description = existing.description if existing.description else ctx_data.get("description")
            else:
                curated_icon = ctx_data.get("icon") or infer_icon_from_slug(ctx_data["slug"])
                curated_theme = ctx_data.get("theme") or infer_theme_from_slug(ctx_data["slug"])
                curated_display_name = ctx_data.get("display_name") or ctx_data["slug"]
                curated_description = ctx_data.get("description")

            existing.display_name = curated_display_name or ctx_data["slug"]
            existing.description = curated_description
            existing.icon = curated_icon
            existing.theme = curated_theme
            existing.weight = ctx_data.get("weight", 50)
            existing.default_payload = _parse_payload(ctx_data.get("default_payload", "{}"))
            existing.version = package_version
            existing.image_id = node_image.id
            context = existing
            stats["contexts_updated"] += 1
        else:
            # If another context already has the same display name, import
            # this one as disabled to avoid user-facing name collisions.
            ctx_display_name = ctx_data.get("display_name") or ctx_data["slug"]
            should_enable = enable_contexts
            if should_enable:
                name_collision = db.query(Context).filter(
                    Context.display_name == ctx_display_name,
                    Context.slug != scoped_slug,
                ).first()
                if name_collision:
                    should_enable = False

            context = Context(
                slug=scoped_slug,
                source_key=source_key,
                source_package=package_name,
                display_name=ctx_display_name,
                description=ctx_data.get("description"),
                icon=ctx_data.get("icon") or infer_icon_from_slug(ctx_data["slug"]),
                theme=ctx_data.get("theme") or infer_theme_from_slug(ctx_data["slug"]),
                weight=ctx_data.get("weight", 50),
                default_payload=_parse_payload(ctx_data.get("default_payload", "{}")),
                enabled=should_enable,
                version=package_version,
                image_id=node_image.id,
            )
            db.add(context)
            stats["contexts_created"] += 1

        db.flush()

        # Link integrations
        context.integrations = []
        for uuid in ctx_data.get("integration_uuids", []):
            integration = integration_cache.get(uuid)
            if integration:
                context.integrations.append(integration)

        # Link languages
        context.languages = []
        for lang_slug in ctx_data.get("language_slugs", []):
            language = language_cache.get(lang_slug)
            if language:
                context.languages.append(language)

        # Link workflows via junction table
        for wf_ref in ctx_data.get("workflow_refs", []):
            workflow = workflow_cache.get(wf_ref["file_path"])
            if workflow:
                # Use raw insert for junction table to set is_context_default
                db.execute(
                    insert(beaker_context_workflows).values(
                        context_id=context.id,
                        workflow_id=workflow.id,
                        is_context_default=wf_ref.get("is_context_default", False),
                        sort_order=wf_ref.get("sort_order", 0),
                    ).prefix_with("OR IGNORE")
                )

    db.commit()
    return stats


class ConfiguredVuePageLoader(FileSystemLoader):
    def __init__(self, searchpath, template_file, encoding = "utf-8", followlinks = False, config=None):
        super().__init__(searchpath, encoding, followlinks)
        self.template_file = template_file
        self.config = config or {}

    def list_templates(self):
        return [self.template_file]

    def load(self, environment, name, globals = None):
        global_override = {
            "siteConfig": self.config
        }
        if isinstance(globals, dict):
            globals.update(global_override)
        else:
            globals = global_override
        return super().load(environment, self.template_file, globals)
