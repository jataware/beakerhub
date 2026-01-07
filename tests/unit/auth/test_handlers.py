# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""Unit tests for auth API handlers."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tornado.web import HTTPError

from beakerhub.auth.handlers import (
    AuthAPIHandler,
    LoginHandler,
    LogoutHandler,
    SignupHandler,
    ConfirmSignupHandler,
    ForgotPasswordHandler,
    ConfirmPasswordHandler,
)


class MockUser:
    """Mock JupyterHub User object."""

    def __init__(
        self,
        name: str = "testuser",
        admin: bool = False,
        created=None,
        last_activity=None,
        roles=None,
        groups=None,
    ):
        self.name = name
        self.admin = admin
        self.created = created
        self.last_activity = last_activity
        self.roles = roles or []
        self.groups = groups or []


class MockRole:
    """Mock role object."""

    def __init__(self, name: str):
        self.name = name


class MockGroup:
    """Mock group object."""

    def __init__(self, name: str):
        self.name = name


@pytest.fixture
def mock_handler():
    """Create a mock handler with common dependencies."""

    def _create_handler(handler_class, current_user=None):
        handler = MagicMock(spec=handler_class)
        handler.current_user = current_user

        # Mock common methods
        handler.write = MagicMock()
        handler.get_json_body = MagicMock(return_value={})
        handler.set_login_cookie = MagicMock()
        handler.clear_login_cookie = MagicMock()
        handler.add_header = MagicMock()
        handler.get_next_url = MagicMock(return_value=None)
        handler.xsrf_token = "mock-xsrf-token"
        handler._xsrf_token_id = "mock-token-id"

        # Mock hub
        handler.hub = MagicMock()
        handler.hub.base_url = "/"

        # Mock statsd
        handler.statsd = MagicMock()
        timer_mock = MagicMock()
        timer_mock.start = MagicMock(return_value=timer_mock)
        timer_mock.stop = MagicMock()
        handler.statsd.timer = MagicMock(return_value=timer_mock)
        handler.statsd.incr = MagicMock()

        # Mock authenticator
        handler.authenticator = MagicMock()
        handler.authenticator.login_service = "TestService"
        handler.authenticator.logout = AsyncMock()
        handler.authenticator.signup = AsyncMock(return_value={"username": "new-user"})
        handler.authenticator.confirm_signup = AsyncMock(return_value=True)
        handler.authenticator.forgot_password = AsyncMock(return_value=True)
        handler.authenticator.confirm_password = AsyncMock(return_value=True)

        # Mock login_user
        handler.login_user = AsyncMock(return_value=current_user)

        # Mock log
        handler.log = MagicMock()

        return handler

    return _create_handler


class TestLoginHandlerGet:
    """Tests for LoginHandler.get method."""

    async def test_get_when_logged_in(self, mock_handler):
        """Should return user info and set cookie when user is logged in."""
        user = MockUser(
            name="testuser",
            admin=True,
            roles=[MockRole("user"), MockRole("admin")],
            groups=[MockGroup("scientists")],
        )
        handler = mock_handler(LoginHandler, current_user=user)

        await LoginHandler.get(handler)

        handler.set_login_cookie.assert_called_once_with(user)
        handler.write.assert_called_once()

        # Parse the written JSON
        written_data = json.loads(handler.write.call_args[0][0])
        assert written_data["status"] == "logged_in"
        assert written_data["user"]["name"] == "testuser"
        assert written_data["user"]["admin"] is True
        assert "user" in written_data["user"]["roles"]
        assert "admin" in written_data["user"]["roles"]
        assert "scientists" in written_data["user"]["groups"]

    async def test_get_when_not_logged_in(self, mock_handler):
        """Should return proceed status and set XSRF cookie when not logged in."""
        handler = mock_handler(LoginHandler, current_user=None)

        with patch("beakerhub.auth.handlers._set_xsrf_cookie") as mock_set_xsrf:
            await LoginHandler.get(handler)

            mock_set_xsrf.assert_called_once()
            handler.add_header.assert_called_with("X-SET-XSRFTOKEN", "mock-xsrf-token")

        handler.write.assert_called_once()
        written_data = json.loads(handler.write.call_args[0][0])
        assert written_data["status"] == "proceed"

    async def test_get_includes_next_url(self, mock_handler):
        """Should include next URL in response if available."""
        handler = mock_handler(LoginHandler, current_user=None)
        handler.get_next_url.return_value = "/dashboard"

        with patch("beakerhub.auth.handlers._set_xsrf_cookie"):
            await LoginHandler.get(handler)

        written_data = json.loads(handler.write.call_args[0][0])
        assert written_data["next"] == "/dashboard"


class TestLoginHandlerPost:
    """Tests for LoginHandler.post method."""

    async def test_post_successful_login(self, mock_handler):
        """Should return user info on successful login."""
        user = MockUser(
            name="testuser",
            admin=False,
            roles=[MockRole("user")],
            groups=[],
        )
        handler = mock_handler(LoginHandler, current_user=user)
        handler.get_json_body.return_value = {"username": "testuser", "password": "pass"}

        await LoginHandler.post(handler)

        handler.login_user.assert_called_once()
        handler.add_header.assert_called_with("X-SET-XSRFTOKEN", "mock-xsrf-token")
        handler.write.assert_called_once()

        written_data = json.loads(handler.write.call_args[0][0])
        assert written_data["name"] == "testuser"
        assert written_data["admin"] is False

    async def test_post_failed_login(self, mock_handler):
        """Should raise 403 error on failed login."""
        handler = mock_handler(LoginHandler, current_user=None)
        handler.login_user.return_value = None
        handler.get_json_body.return_value = {"username": "bad", "password": "bad"}

        with pytest.raises(HTTPError) as exc_info:
            await LoginHandler.post(handler)

        assert exc_info.value.status_code == 403


class TestLogoutHandler:
    """Tests for LogoutHandler."""

    def test_check_xsrf_cookie_returns_none(self, mock_handler):
        """check_xsrf_cookie should not enforce XSRF for logout."""
        handler = mock_handler(LogoutHandler)

        # Should return None (no exception)
        result = LogoutHandler.check_xsrf_cookie(handler)
        assert result is None

    async def test_post_with_user(self, mock_handler):
        """Should clear cookies and call authenticator.logout when user exists."""
        user = MockUser(name="testuser")
        handler = mock_handler(LogoutHandler, current_user=user)

        with patch("beakerhub.auth.handlers._set_xsrf_cookie"):
            await LogoutHandler.post(handler)

        handler.clear_login_cookie.assert_called_once()
        handler.authenticator.logout.assert_called_once_with(user)
        handler.add_header.assert_called_with("X-SET-XSRFTOKEN", "mock-xsrf-token")

    async def test_post_without_user(self, mock_handler):
        """Should still set new XSRF token when no user."""
        handler = mock_handler(LogoutHandler, current_user=None)

        with patch("beakerhub.auth.handlers._set_xsrf_cookie"):
            await LogoutHandler.post(handler)

        handler.clear_login_cookie.assert_not_called()
        handler.authenticator.logout.assert_not_called()

    async def test_post_handles_logout_exception(self, mock_handler):
        """Should handle exceptions from authenticator.logout gracefully."""
        user = MockUser(name="testuser")
        handler = mock_handler(LogoutHandler, current_user=user)
        handler.authenticator.logout.side_effect = Exception("Logout failed")

        with patch("beakerhub.auth.handlers._set_xsrf_cookie"):
            # Should not raise
            await LogoutHandler.post(handler)

        handler.clear_login_cookie.assert_called_once()


class TestSignupHandler:
    """Tests for SignupHandler."""

    async def test_post_calls_authenticator_signup(self, mock_handler):
        """Should call authenticator.signup and return user info."""
        handler = mock_handler(SignupHandler)
        handler.get_json_body.return_value = {
            "username": "newuser@example.com",
            "password": "NewPass123!",
        }
        handler.authenticator.signup.return_value = {
            "username": "user-uuid",
            "userConfirmed": False,
        }

        await SignupHandler.post(handler)

        handler.authenticator.signup.assert_called_once_with(
            handler,
            {"username": "newuser@example.com", "password": "NewPass123!"},
        )
        handler.write.assert_called_once()

        written_data = json.loads(handler.write.call_args[0][0])
        assert written_data["user"]["username"] == "user-uuid"
        assert written_data["user"]["userConfirmed"] is False


class TestConfirmSignupHandler:
    """Tests for ConfirmSignupHandler."""

    async def test_post_calls_authenticator_confirm_signup(self, mock_handler):
        """Should call authenticator.confirm_signup and return confirmation."""
        handler = mock_handler(ConfirmSignupHandler)
        handler.get_json_body.return_value = {
            "username": "user@example.com",
            "code": "123456",
        }

        await ConfirmSignupHandler.post(handler)

        handler.authenticator.confirm_signup.assert_called_once_with(
            handler,
            {"username": "user@example.com", "code": "123456"},
        )
        handler.write.assert_called_once()

        written_data = json.loads(handler.write.call_args[0][0])
        assert written_data["confirmed"] is True


class TestForgotPasswordHandler:
    """Tests for ForgotPasswordHandler."""

    async def test_post_calls_authenticator_forgot_password(self, mock_handler):
        """Should call authenticator.forgot_password and return status."""
        handler = mock_handler(ForgotPasswordHandler)
        handler.get_json_body.return_value = {"username": "user@example.com"}

        await ForgotPasswordHandler.post(handler)

        handler.authenticator.forgot_password.assert_called_once_with(
            handler,
            {"username": "user@example.com"},
        )
        handler.write.assert_called_once()

        written_data = json.loads(handler.write.call_args[0][0])
        assert written_data["sent"] is True


class TestConfirmPasswordHandler:
    """Tests for ConfirmPasswordHandler."""

    async def test_post_calls_authenticator_confirm_password(self, mock_handler):
        """Should call authenticator.confirm_password and return status."""
        handler = mock_handler(ConfirmPasswordHandler)
        handler.get_json_body.return_value = {
            "username": "user@example.com",
            "code": "123456",
            "password": "NewSecurePass123!",
        }

        await ConfirmPasswordHandler.post(handler)

        handler.authenticator.confirm_password.assert_called_once_with(
            handler,
            {
                "username": "user@example.com",
                "code": "123456",
                "password": "NewSecurePass123!",
            },
        )
        handler.write.assert_called_once()

        written_data = json.loads(handler.write.call_args[0][0])
        assert written_data["reset"] is True


class FakeXsrfHandler:
    """Stand-in handler that reproduces JupyterHub's ``xsrf_token`` memoization.

    The real bug this guards against: JupyterHub caches the xsrf token on
    ``self._xsrf_token`` the first time ``xsrf_token`` is read. For a login
    POST that read happens during the pre-login XSRF check in ``prepare()``,
    while the request is still anonymous. ``login_user`` -> ``set_login_cookie``
    then rewrites the session and ``_xsrf`` cookies with the now-authenticated
    token id, but it does NOT bust that cache. Unless the handler deletes
    ``_xsrf_token`` itself, ``self.xsrf_token`` keeps returning the stale
    pre-login value -- which is what gets sent to the front end in the
    ``X-SET-XSRFTOKEN`` header, leaving it sending a token that no longer
    matches the cookie.

    ``MagicMock(spec=...)`` can't model this (its ``xsrf_token`` is a static
    value), so we use a minimal real object that mimics the memoization.
    """

    ANON_TOKEN = "anon-xsrf-token"
    AUTH_TOKEN = "auth-xsrf-token"

    def __init__(self, current_user=None, prime_cache=True):
        self.current_user = current_user
        self._authenticated = False
        # Simulate the pre-login xsrf check (or any earlier access) having
        # already read and cached the token while still anonymous.
        if prime_cache:
            self._xsrf_token = self.ANON_TOKEN
        self.added_headers = {}
        self.written = None
        self.log = MagicMock()
        self._json_body = {}

        # statsd timer/incr plumbing used by the handler methods
        self.statsd = MagicMock()
        timer = MagicMock()
        timer.start.return_value = timer
        self.statsd.timer.return_value = timer

        self.authenticator = MagicMock()
        self.authenticator.login_service = "TestService"

    # --- JupyterHub-like xsrf memoization --------------------------------
    @property
    def xsrf_token(self):
        if hasattr(self, "_xsrf_token"):
            return self._xsrf_token
        token = self.AUTH_TOKEN if self._authenticated else self.ANON_TOKEN
        self._xsrf_token = token
        return token

    # --- minimal handler API surface -------------------------------------
    def get_json_body(self):
        return self._json_body

    def set_login_cookie(self, user):
        # Rewrites session + _xsrf cookies for the authenticated user, changing
        # the token id -- but, like the real method, leaves the memoized token.
        self._authenticated = True

    async def login_user(self, data=None):
        if self.current_user is not None:
            self.set_login_cookie(self.current_user)
        return self.current_user

    def add_header(self, name, value):
        self.added_headers[name] = value

    def write(self, body):
        self.written = body

    def get_next_url(self, user=None):
        return None


class TestLoginHandlerXsrfRefresh:
    """Regression tests: the login response must hand the front end the
    post-login xsrf token, not the stale pre-login one."""

    async def test_post_emits_post_login_xsrf_token(self):
        """POST must bust the cached token so X-SET-XSRFTOKEN matches the new cookie."""
        user = MockUser(name="testuser", roles=[MockRole("user")], groups=[])
        handler = FakeXsrfHandler(current_user=user)
        handler._json_body = {"username": "testuser", "password": "pass"}

        # Sanity: the stale token is cached going in (as it would be after the
        # pre-login xsrf check in prepare()).
        assert handler._xsrf_token == FakeXsrfHandler.ANON_TOKEN

        await LoginHandler.post(handler)

        assert (
            handler.added_headers["X-SET-XSRFTOKEN"] == FakeXsrfHandler.AUTH_TOKEN
        ), "login POST leaked the stale pre-login xsrf token to the front end"

        written = json.loads(handler.written)
        assert written["name"] == "testuser"

    async def test_get_logged_in_emits_post_login_xsrf_token(self):
        """GET (already logged in) must also refresh and emit the token."""
        user = MockUser(name="testuser", roles=[MockRole("user")], groups=[])
        handler = FakeXsrfHandler(current_user=user)
        # Model set_login_cookie having rewritten the cookie for this request.
        handler._authenticated = True

        await LoginHandler.get(handler)

        assert (
            handler.added_headers.get("X-SET-XSRFTOKEN") == FakeXsrfHandler.AUTH_TOKEN
        ), "login GET did not emit the refreshed xsrf token"

        written = json.loads(handler.written)
        assert written["status"] == "logged_in"

    async def test_post_recomputes_when_no_cache_primed(self):
        """If nothing cached the token earlier, the fresh post-login value is used."""
        user = MockUser(name="testuser", roles=[], groups=[])
        handler = FakeXsrfHandler(current_user=user, prime_cache=False)
        handler._json_body = {"username": "testuser", "password": "pass"}

        await LoginHandler.post(handler)

        assert handler.added_headers["X-SET-XSRFTOKEN"] == FakeXsrfHandler.AUTH_TOKEN

    async def test_post_failed_login_does_not_emit_token(self):
        """A failed login should raise 403 before touching the xsrf header."""
        handler = FakeXsrfHandler(current_user=None)
        handler._json_body = {"username": "bad", "password": "bad"}

        with pytest.raises(HTTPError) as exc_info:
            await LoginHandler.post(handler)

        assert exc_info.value.status_code == 403
        assert "X-SET-XSRFTOKEN" not in handler.added_headers


class TestAuthAPIHandler:
    """Tests for AuthAPIHandler base class."""

    def test_xsrf_safe_methods_includes_get(self):
        """GET should be in XSRF safe methods for auth endpoints."""
        assert "GET" in AuthAPIHandler._xsrf_safe_methods

    def test_accept_cookie_auth_is_true(self):
        """Should accept cookie authentication."""
        assert AuthAPIHandler._accept_cookie_auth is True

    def test_accept_token_auth_is_false(self):
        """Should not accept token authentication."""
        assert AuthAPIHandler._accept_token_auth is False
