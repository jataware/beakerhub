import os
from jupyter_server.base.handlers import JupyterHandler
import requests
from typing import Awaitable

from jupyter_server.auth.identity import IdentityProvider, User

from beaker_notebook.services.auth import BeakerIdentityProvider, BeakerUser, BeakerRole, BeakerAuthorizer, BeakerPermission
from tornado.web import RequestHandler

class AuthCache(dict[str, tuple[str, User]]):
    pass

auth_cache = AuthCache()

class BeakerhubNodeIdentityProvider(BeakerIdentityProvider):

    def get_user(self, handler: RequestHandler) -> User | None | Awaitable[User | None]:
        hub_token = os.environ.get("JUPYTERHUB_API_TOKEN", None)
        hub_api_url = os.environ.get("JUPYTERHUB_API_URL", None)
        username = os.environ.get("JUPYTERHUB_USER", None)
        if username and username in auth_cache:
            auth_token, auth_user = auth_cache[username]
            if auth_token != hub_token:
                raise ValueError("Auth token doesn't match expected value")
            return auth_user
        if hub_token:
            auth_check = requests.get(f"{hub_api_url}/user", headers={"Authorization": f"Bearer {hub_token}"})
            if not auth_check.ok:
                return None
            auth_details: dict = auth_check.json()
            if username is not None and username == auth_details.get("name", None):
                user = User(
                    username=auth_details["name"],
                )
                auth_cache[username] = (hub_token, user)
                return user
        return super().get_user(handler)

class BeakerhubNodeAuthorizer(BeakerAuthorizer):
    def is_authorized(self, handler: JupyterHandler, user: User, action: str, resource: str) -> Awaitable[bool] | bool:
        return True
