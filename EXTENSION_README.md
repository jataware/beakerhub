# BeakerHub Extensions

A BeakerHub extension is a Python class that inherits from
`beakerhub.lib.extensions.BaseExtension`. Enable it in Hub configuration with
an extension class or instance:

```python
from my_extension import MyExtension

c.BeakerHub.extensions = [MyExtension]
```

BeakerHub creates extension tables during Hub startup. It also adds extension
roles, services, scopes, and handlers to the Hub configuration.

## Extension definition

```python
from sqlalchemy import Column, Integer

from beakerhub.lib.extensions import (
    BaseExtension,
    BaseExtensionHandler,
    ExtensionTable,
)


class Widget(ExtensionTable):
    __tablename__ = "widgets"

    id = Column(Integer, primary_key=True)


class HealthHandler(BaseExtensionHandler):
    async def get(self):
        self.write({"status": "ok"})


class MyExtension(BaseExtension):
    slug = "my-extension"

    scopes = {
        "custom:my-extension": {
            "description": "Use the My Extension API.",
        },
        "custom:my-extension:read": {
            "description": "Read My Extension data.",
        },
    }

    roles = [
        {
            "name": "my-extension-service",
            "scopes": ["custom:my-extension"],
            "services": ["my-extension-service"],
        },
    ]

    services = [{"name": "my-extension-service"}]
    handlers = [
        (r"/extensions/my-extension/health", HealthHandler),
    ]
    orm_tables = [Widget]
```

## Naming and routes

- `slug` must contain lowercase ASCII letters, numbers, and hyphens.
- Handler routes must begin with `/extensions/<slug>/`. Hub routes outside this
  namespace are reserved.
- BeakerHub always creates `custom:<slug>`. An extension can provide its own
  description for that scope and can define child scopes below
  `custom:<slug>:`.
- Each scope definition requires `description`. A `subscopes` value must be a
  list of scope names defined by the extension.
- Role names, service names, handler routes, and extension slugs must not
  duplicate configured Hub or extension resources.

## Database tables

`ExtensionTable` defers declarative mapping until Hub startup. BeakerHub maps
it into metadata owned by the extension and names its physical table as:

```
beakerhub_ext_<slug>__<tablename>
```

BeakerHub creates missing initial tables during startup, including when an
extension is added to an existing database. String foreign keys to Hub or other
extensions' tables do not resolve automatically across metadata boundaries.
BeakerHub does not detect, repair, or migrate incompatible existing schemas.

`orm_migration_path` is reserved for future project-wide migration support. It
is intentionally inactive. Until migration support exists, repair extension
schema conflicts manually.

## Failure behavior

If BeakerHub cannot validate an extension or create one of its tables, it
disables that extension and continues Hub startup. Tables that were created
before a later table-creation failure can remain in the database.
