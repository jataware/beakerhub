from typing import TYPE_CHECKING

from jupyterhub.apihandlers.base import APIHandler
from jupyterhub.user import User
from jupyterhub.utils import url_path_join
from jupyterhub._xsrf_utils import _set_xsrf_cookie
from tornado import web

from beakerhub.utils import to_json

if TYPE_CHECKING:
    from beakerhub.auth.base import BeakerhubAuthenticator


class AuthAPIHandler(APIHandler):
    authenticator: "BeakerhubAuthenticator"

    _accept_cookie_auth = True
    _accept_token_auth = False
    # Ensure get methods are allowed without xsrf checks on these endpoints.
    _xsrf_safe_methods = set(APIHandler._xsrf_safe_methods).union({"GET",})

    @staticmethod
    def default_url(self: "AuthAPIHandler"):
        return url_path_join(self.hub.base_url)


class LoginHandler(AuthAPIHandler):

    async def get(self):
        self.statsd.incr('login.request')

        user = self.current_user
        if user:
            # set new login cookie
            # because single-user cookie may have been cleared or incorrect
            self.log.warning("Setting login cookie")
            self.set_login_cookie(user)
            # set_login_cookie() may have rewritten the _xsrf cookie with the
            # authenticated token id; bust the memoized token and hand the fresh
            # value back so the front end stops sending a stale header token.
            if hasattr(self, "_xsrf_token"):
                delattr(self, "_xsrf_token")
            self.add_header("X-SET-XSRFTOKEN", self.xsrf_token)
            response = {
                "status": "logged_in",
                "user": {
                    "admin": user.admin,
                    "created": user.created,
                    "name": user.name,
                    "last_activity": user.last_activity,
                    "roles": [role.name for role in user.roles],
                    "groups": [group.name for group in user.groups],
                },
            }
        else:
            # always set a fresh xsrf cookie when the login page is rendered
            # ensures we are as far from expiration as possible
            # to restart the timer
            xsrf_token = self.xsrf_token
            self.log.warning(f"Setting xsrf cookie to {xsrf_token}")
            _set_xsrf_cookie(
                self,
                self._xsrf_token_id,
                cookie_path=self.hub.base_url,
                xsrf_token=xsrf_token,
            )
            response = {"status": "proceed"}
            self.add_header("X-SET-XSRFTOKEN", self.xsrf_token)

        next_url = self.get_next_url(user)
        if next_url:
            response["next"] = next_url
        self.write(to_json(response))


    async def post(self):
        data = self.get_json_body()

        auth_timer = self.statsd.timer('login.authenticate').start()
        user: User = await self.login_user(data)
        auth_timer.stop(send=False)

        if not user:
            raise web.HTTPError(403, f"Couldn't log in to service {self.authenticator.login_service}")

        # login_user() -> set_login_cookie() rewrote the session and _xsrf cookies,
        # which changes the xsrf token id. The xsrf_token property is memoized on
        # _xsrf_token (cached during the pre-login xsrf check in prepare()), so it
        # would otherwise return the stale anonymous token here. Bust the cache so we
        # emit the token that matches the cookie we just set.
        if hasattr(self, "_xsrf_token"):
            delattr(self, "_xsrf_token")

        self.add_header("X-SET-XSRFTOKEN", self.xsrf_token)
        self.write(to_json({
            "admin": user.admin,
            "created": user.created,
            "name": user.name,
            "last_activity": user.last_activity,
            "roles": [role.name for role in user.roles],
            "groups": [group.name for group in user.groups],
        }))


class LogoutHandler(AuthAPIHandler):

    def check_xsrf_cookie(self):
        # Checking xsrf in not required for logging out.
        return

    async def post(self):
        old_token = self.xsrf_token
        user: User = self.current_user
        if user:
            self.clear_login_cookie()
            try:
                await self.authenticator.logout(user)
            except Exception:
                pass
        if hasattr(self, "_xsrf_token"):
            delattr(self, "_xsrf_token")

        new_token = self.xsrf_token
        self.log.warning(f"\n{old_token}\n{new_token}")
        _set_xsrf_cookie(
            self,
            self._xsrf_token_id,
            cookie_path=self.hub.base_url,
            xsrf_token=new_token,
        )
        self.add_header("X-SET-XSRFTOKEN", new_token)


class SignupHandler(AuthAPIHandler):

    async def post(self):
        data = self.get_json_body()
        user_info = await self.authenticator.signup(self, data)
        self.write(to_json({
            "user": user_info,
        }))

class ConfirmSignupHandler(AuthAPIHandler):

    async def post(self):
        data = self.get_json_body()
        confirmed = await self.authenticator.confirm_signup(self, data)
        self.write(to_json({"confirmed": confirmed}))

class ForgotPasswordHandler(AuthAPIHandler):

    async def post(self):
        data = self.get_json_body()
        sent = await self.authenticator.forgot_password(self, data)
        self.write(to_json({"sent": sent}))

class ConfirmPasswordHandler(AuthAPIHandler):

    async def post(self):
        data = self.get_json_body()
        confirmed = await self.authenticator.confirm_password(self, data)
        self.write(to_json({"reset": confirmed}))
