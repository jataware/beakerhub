from jupyterhub.auth import Authenticator
from jupyterhub.user import User
from tornado import web

from beakerhub.auth.base import BeakerhubAuthenticator
from beakerhub.types import HandlerTuple


class DummyBeakerhubAuthenticator(Authenticator, metaclass=BeakerhubAuthenticator):
    """
    A no-op authenticator for local development and evaluation.

    Any username is accepted and logged in as-is, with any password (including
    an empty one). This exists so that a local/dev instance can be used without
    provisioning a Cognito user pool. It performs NO real authentication and must
    never be used for a deployment that is reachable by untrusted users.

    Admin status follows the standard ``Authenticator.admin_users``
    configuration. ``Authenticator.allow_all`` should be enabled for anyone to
    be permitted in.
    """

    login_service = "Local (development)"

    async def authenticate(self, handler, data):
        """
        Accept any user with the username they provide and any password.

        Args:
            handler: The tornado request handler.
            data: Dictionary containing 'username' and 'password' from the login form.

        Returns:
            A dictionary with the provided username on success, None if no
            username was supplied.
        """
        username = data.get("username", "")

        if not username:
            self.log.warning("Empty username provided to DummyBeakerhubAuthenticator")
            return None

        self.log.info(f"DummyBeakerhubAuthenticator logging in user: {username}")
        return {"name": username}

    async def logout(self, user: User):
        # No upstream session to invalidate; the login cookie is cleared by the
        # LogoutHandler before this is called.
        return

    async def signup(self, handler, data):
        raise web.HTTPError(501, "Signup is not supported by the development authenticator")

    async def confirm_signup(self, handler, data):
        raise web.HTTPError(501, "Signup confirmation is not supported by the development authenticator")

    async def forgot_password(self, handler, data):
        raise web.HTTPError(501, "Password reset is not supported by the development authenticator")

    async def confirm_password(self, handler, data):
        raise web.HTTPError(501, "Password reset is not supported by the development authenticator")

    def get_handlers(self, app) -> list[HandlerTuple]:
        # Login/logout routes are registered globally (see beakerhub.handlers).
        # This authenticator supports no signup or password-reset flows, so it
        # registers no additional routes.
        return []
