"""Tests for BeakerHub extension registration."""

from types import SimpleNamespace

from traitlets import Unicode
from traitlets.config import Config
from sqlalchemy import Column, Integer, String, create_engine, inspect
from sqlalchemy.orm import Session

from beakerhub.app import BeakerHub
from beakerhub.lib.extensions import (
    BaseExtension,
    BaseExtensionHandler,
    ExtensionTable,
)
from beakerhub.orm import Base


class ExampleTable(ExtensionTable):
    __tablename__ = "records"

    id = Column(Integer, primary_key=True)
    name = Column(String)


class ExampleHandler(BaseExtensionHandler):
    async def get(self):
        self.write("ok")


class ExampleExtension(BaseExtension):
    slug = "example"
    enabled_feature = Unicode("default", config=True)
    scopes = {
        "custom:example": {"description": "Extension-supplied base scope."},
        "custom:example:read": {"description": "Read example data."},
    }
    roles = [{"name": "example-service", "scopes": ["custom:example"]}]
    services = [{"name": "example-service"}]
    handlers = [(r"/extensions/example/health", ExampleHandler)]
    orm_tables = [ExampleTable]


class InvalidRouteExtension(BaseExtension):
    slug = "invalid-route"
    handlers = [(r"/api/invalid-route", ExampleHandler)]


class InvalidScopeExtension(BaseExtension):
    slug = "invalid-scope"
    scopes = {"custom:invalid-scope": {}}


class IdleCullerRoleCollisionExtension(BaseExtension):
    slug = "idle-culler-role-collision"
    roles = [{"name": "beakerhub-idle-culler"}]


class IdleCullerServiceCollisionExtension(BaseExtension):
    slug = "idle-culler-service-collision"
    services = [{"name": "beakerhub-idle-culler"}]


def test_extension_class_is_instantiated_and_receives_config():
    config = Config()
    config.ExampleExtension.enabled_feature = "configured"

    app = BeakerHub(config=config, extensions=[ExampleExtension])

    extension = app.extensions[0]
    assert isinstance(extension, ExampleExtension)
    assert extension.parent is app
    assert extension.enabled_feature == "configured"
    assert ExampleExtension in app.classes


def test_extension_added_by_late_config_is_registered_as_configurable():
    app = BeakerHub()
    _ = app.classes
    config = Config()
    config.BeakerHub.extensions = [ExampleExtension]
    config.ExampleExtension.enabled_feature = "late-configured"

    app.update_config(config)

    assert isinstance(app.extensions[0], ExampleExtension)
    assert app.extensions[0].enabled_feature == "late-configured"
    assert ExampleExtension in app.classes


def test_extension_scopes_include_base_and_prefer_extension_description():
    app = BeakerHub(extensions=[ExampleExtension])

    scopes = app.extensions[0].scope_definitions()

    assert scopes == {
        "custom:example": {"description": "Extension-supplied base scope."},
        "custom:example:read": {"description": "Read example data."},
    }


def test_prepare_extensions_disables_invalid_scope_definition():
    app = BeakerHub(extensions=[InvalidScopeExtension])

    app._prepare_extensions()

    assert app.extensions == []


def test_prepare_extensions_disables_idle_culler_resource_collisions():
    role_app = BeakerHub(extensions=[IdleCullerRoleCollisionExtension])
    service_app = BeakerHub(extensions=[IdleCullerServiceCollisionExtension])

    role_app._prepare_extensions()
    service_app._prepare_extensions()

    assert role_app.extensions == []
    assert service_app.extensions == []


def test_failed_extension_does_not_remove_existing_resource_reservations():
    class Collision(BaseExtension):
        slug = "collision"
        roles = [{"name": "existing-role"}]

    class LaterCollision(BaseExtension):
        slug = "later-collision"
        roles = [{"name": "existing-role"}]

    app = BeakerHub(
        extensions=[Collision, LaterCollision],
        load_roles=[{"name": "existing-role"}],
        enable_idle_session_culling=False,
    )

    app._prepare_extensions()

    assert app.extensions == []


def test_invalid_resource_does_not_prevent_disabling_extension():
    class InvalidRole(BaseExtension):
        slug = "invalid-role"
        roles = [{}]

    app = BeakerHub(extensions=[InvalidRole], enable_idle_session_culling=False)

    app._prepare_extensions()

    assert app.extensions == []


def test_mapping_failure_does_not_reserve_resource_names():
    class BrokenTable(ExtensionTable):
        __tablename__ = "broken"
        value = Column(String)

    class BrokenExtension(BaseExtension):
        slug = "broken-extension"
        roles = [{"name": "shared-role"}]
        orm_tables = [BrokenTable]

    class ValidExtension(BaseExtension):
        slug = "valid-extension"
        roles = [{"name": "shared-role"}]

    app = BeakerHub(
        extensions=[BrokenExtension, ValidExtension],
        enable_idle_session_culling=False,
    )

    app._prepare_extensions()

    assert len(app.extensions) == 1
    assert isinstance(app.extensions[0], ValidExtension)


def test_extension_validation_requires_reserved_handler_namespace():
    app = BeakerHub(extensions=[InvalidRouteExtension])
    try:
        app.extensions[0].validate()
    except ValueError as error:
        assert str(error) == "handler route must start with /extensions/invalid-route/"
    else:
        raise AssertionError("Expected invalid extension handler route to fail validation")


async def test_init_role_creation_registers_extension_roles_and_scopes(monkeypatch):
    async def init_role_creation(app):
        return None

    monkeypatch.setattr("jupyterhub.app.JupyterHub.init_role_creation", init_role_creation)
    app = BeakerHub(extensions=[ExampleExtension], enable_idle_session_culling=False)

    await app.init_role_creation()

    assert app.extensions[0].roles[0] in app.load_roles
    assert app.custom_scopes["custom:example"] == {
        "description": "Extension-supplied base scope."
    }
    assert app.custom_scopes["custom:example:read"] == {
        "description": "Read example data."
    }


def test_init_services_registers_extension_services(monkeypatch):
    monkeypatch.setattr("jupyterhub.app.JupyterHub.init_services", lambda app: None)
    app = BeakerHub(extensions=[ExampleExtension], enable_idle_session_culling=False)

    app.init_services()

    assert app.extensions[0].services[0] in app.services


def test_init_handlers_registers_extension_handlers(monkeypatch):
    def init_handlers(app):
        app.handlers = []

    monkeypatch.setattr("jupyterhub.app.JupyterHub.init_handlers", init_handlers)
    app = BeakerHub(extensions=[ExampleExtension])

    app.init_handlers()

    assert app.extensions[0].handlers[0] in app.handlers


def test_init_db_creates_extension_tables(monkeypatch):
    engine = create_engine("sqlite://")

    def init_db(app):
        app.db = SimpleNamespace(get_bind=lambda: engine)

    monkeypatch.setattr("jupyterhub.app.JupyterHub.init_db", init_db)
    app = BeakerHub(extensions=[ExampleExtension])
    app.init_db()

    assert "beakerhub_ext_example__records" in inspect(engine).get_table_names()


def test_extension_table_uses_separate_metadata_and_is_created():
    extension = ExampleExtension()
    ExampleTable.register(extension)

    assert ExampleTable.__tablename__ == "beakerhub_ext_example__records"
    assert ExampleTable.__table__.metadata is extension._orm_base.metadata
    assert ExampleTable.__table__.metadata is not Base.metadata

    engine = create_engine("sqlite://")
    ExampleTable.__table__.create(engine)
    assert "beakerhub_ext_example__records" in inspect(engine).get_table_names()

    with Session(engine) as session:
        session.add(ExampleTable(name="example"))
        session.commit()
        assert session.query(ExampleTable).one().name == "example"
