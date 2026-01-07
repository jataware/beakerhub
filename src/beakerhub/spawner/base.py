from typing import Any
from uuid import uuid4

from jupyterhub.spawner import Spawner
from traitlets import Unicode, default

class BeakerSpawner(Spawner):

    def __init__(self, **kwargs: Any) -> None:
        domain = kwargs.pop("domain", None)
        super().__init__(**kwargs)
        if domain:
            self.proxy_spec = f"{self.name}.{domain}/"

    @property
    def name(self) -> str:
        name = super().name
        return name

    @name.setter
    def name(self, value: str) -> str:
        if self.orm_spawner:
            self.orm_spawner.name = value
        return value

    @property
    def session_id(self) -> str:
        if not self.name:
            self.name = str(uuid4())
        return self.name

    def start(self):
        raise NotImplementedError()

    def stop(self, now=False):
        raise NotImplementedError()

    def poll(self):
        raise NotImplementedError()
