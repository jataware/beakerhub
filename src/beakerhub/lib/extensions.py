import re
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, DeclarativeBaseNoMeta, registry as Registry
from traitlets.config import LoggingConfigurable

from beakerhub.handlers import BaseHandler

if TYPE_CHECKING:
    from beakerhub.app import BeakerHub


class BaseExtensionHandler(BaseHandler):
    ...


class ExtensionTable(DeclarativeBaseNoMeta):
    """Deferred declarative model base for tables owned by an extension."""

    _mapped: ClassVar[bool] = False
    _extension_original_tablename: ClassVar[str]

    def __init_subclass__(cls, **kwargs: object):
        # Do not call super() to defer registering the model until its extension
        # has supplied its metadata and table namespace.
        pass

    @classmethod
    def register(cls, extension: "BaseExtension") -> None:
        """Map this model into the extension's ORM metadata."""
        if cls._mapped:
            return

        original_tablename = cls.__dict__.get(
            "_extension_original_tablename", cls.__tablename__
        )
        cls._extension_original_tablename = original_tablename
        cls.__tablename__ = f"beakerhub_ext_{extension.slug}__{original_tablename}"

        # Use the extension's metadata instead of the model base's metadata.
        cls.metadata = extension._orm_base.metadata
        extension._orm_base.registry.map_declaratively(cls)
        cls._mapped = True


class BaseExtension(LoggingConfigurable):
    """Base class for BeakerHub extensions."""

    slug: ClassVar[str]
    services: ClassVar[list[dict]] = []
    roles: ClassVar[list[dict]] = []
    handlers: ClassVar[list] = []
    scopes: ClassVar[dict[str, dict]] = {}
    orm_tables: ClassVar[list[type[ExtensionTable]]] = []
    # Intentionally inactive until BeakerHub has a project-wide migration design.
    orm_migration_path: ClassVar[str]
    _orm_base: DeclarativeBase | None = None

    def __init_subclass__(cls, **kwargs: object):
        from beakerhub.orm import Base
        base_metadata: MetaData = Base.metadata
        metadata = MetaData(
            schema=base_metadata.schema,
            naming_convention=base_metadata.naming_convention,
            info=base_metadata.info,
        )

        registry_base = type(
            f"{cls.__name__}OrmBase",
            (DeclarativeBase,),
            {"registry": Registry(metadata=metadata)},
        )
        cls._orm_base = registry_base
        return super().__init_subclass__(**kwargs)

    def scope_definitions(self) -> dict[str, dict]:
        """Return the generated base scope merged with extension scopes."""
        base_scope = f"custom:{self.slug}"
        scopes = {
            base_scope: {
                "description": (
                    f"Scope for the {type(self).__module__}."
                    f"{type(self).__name__} ({self.slug}) extension."
                ),
            }
        }
        scopes.update(self.scopes)
        return scopes

    def validate(self) -> None:
        """Validate this extension's self-contained resource definitions."""
        if not isinstance(self.slug, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9-]*", self.slug
        ):
            raise ValueError("slug must contain lowercase letters, numbers, and hyphens")

        base_scope = f"custom:{self.slug}"
        scopes = self.scope_definitions()
        for scope_name, scope in scopes.items():
            if not re.fullmatch(
                r"custom:[a-z0-9][a-z0-9_\-:*]+[a-z0-9_*]", scope_name
            ):
                raise ValueError(f"invalid custom scope name: {scope_name!r}")
            if not isinstance(scope, dict):
                raise TypeError(f"scope {scope_name!r} must be a dictionary")
            if "description" not in scope:
                raise ValueError(f"scope {scope_name!r} must define a description")
            if scope_name != base_scope and not scope_name.startswith(f"{base_scope}:"):
                raise ValueError(f"scope {scope_name!r} is outside {base_scope}")
            if "subscopes" in scope:
                subscopes = scope["subscopes"]
                if not isinstance(subscopes, list) or not all(
                    isinstance(subscope, str) for subscope in subscopes
                ):
                    raise TypeError(
                        f"scope {scope_name!r} subscopes must be a list of strings"
                    )
                unknown_subscopes = set(subscopes).difference(scopes)
                if unknown_subscopes:
                    raise ValueError(
                        f"scope {scope_name!r} has unknown subscopes: "
                        f"{sorted(unknown_subscopes)!r}"
                    )

        role_names = set()
        for role in self.roles:
            name = role.get("name") if isinstance(role, dict) else None
            if not name:
                raise TypeError("extension roles must be role-spec dictionaries with names")
            if name in role_names:
                raise ValueError(f"duplicate role name: {name}")
            role_names.add(name)

        service_names = set()
        for service in self.services:
            name = service.get("name") if isinstance(service, dict) else None
            if not name:
                raise TypeError("extension services must be service-spec dictionaries with names")
            if name in service_names:
                raise ValueError(f"duplicate service name: {name}")
            service_names.add(name)

        route_prefix = f"/extensions/{self.slug}/"
        handler_routes = set()
        for handler in self.handlers:
            if not isinstance(handler, tuple) or len(handler) not in (2, 3):
                raise TypeError("extension handlers must be two- or three-item tuples")
            if not isinstance(handler[0], str) or not handler[0].startswith(route_prefix):
                raise ValueError(f"handler route must start with {route_prefix}")
            if handler[0] in handler_routes:
                raise ValueError(f"duplicate handler route: {handler[0]}")
            handler_routes.add(handler[0])

        for table in self.orm_tables:
            if not isinstance(table, type) or not issubclass(table, ExtensionTable):
                raise TypeError("extension ORM tables must inherit ExtensionTable")
            if not isinstance(getattr(table, "__tablename__", None), str):
                raise TypeError("extension ORM tables must define __tablename__")

    def create_tables(self, bind) -> None:
        self._orm_base.metadata.create_all(bind=bind)

    def remove_tables(self, *tables, bind=None) -> None:
        tables = tables or None
        self._orm_base.metadata.drop_all(bind=bind, tables=tables)

    def teardown(self) -> None:
        """Remove resources registered in application configuration.

        Database tables are deliberately retained. Service processes are managed
        by JupyterHub and are reconciled from ``app.services`` on startup.
        """
        if not self.parent:
            return

        app = self.parent
        app.handlers = [handler for handler in app.handlers if handler not in self.handlers]
        role_names = {role["name"] for role in self.roles}
        app.load_roles = [
            role for role in app.load_roles if role.get("name") not in role_names
        ]
        app.services = [service for service in app.services if service not in self.services]

        scope_names = {f"custom:{self.slug}", *self.scopes}
        # JupyterHub copies scopes into process-global scope_definitions during
        # role creation. This only removes the application configuration entry.
        app.custom_scopes = {
            name: definition
            for name, definition in app.custom_scopes.items()
            if name not in scope_names
        }

