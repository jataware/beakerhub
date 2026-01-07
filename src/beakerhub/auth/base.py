from abc import ABC, abstractmethod

from jupyterhub.user import User
from traitlets import MetaHasTraits

class BeakerhubAuthenticator(ABC, MetaHasTraits):
    @abstractmethod
    async def authenticate(self, handler, data): ...

    @abstractmethod
    async def logout(self, user: User): ...

    @abstractmethod
    async def signup(self, handler, data): ...

    @abstractmethod
    async def confirm_signup(self, handler, data): ...

    @abstractmethod
    async def forgot_password(self, handler, data): ...

    @abstractmethod
    async def confirm_password(self, handler, data): ...
