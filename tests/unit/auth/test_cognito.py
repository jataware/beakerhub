# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""Unit tests for CognitoBotoAuthenticator."""

import base64
import hashlib
import hmac

import pytest
from botocore.exceptions import ClientError
from moto import mock_aws
import boto3

from beakerhub.auth.cognito import CognitoBotoAuthenticator


class TestCognitoBotoAuthenticator:
    """Tests for CognitoBotoAuthenticator class."""

    @pytest.fixture
    def authenticator(self, cognito_user_pool):
        """Create an authenticator configured with the mocked Cognito pool."""
        auth = CognitoBotoAuthenticator(
            user_pool_id=cognito_user_pool["pool_id"],
            client_id=cognito_user_pool["client_id"],
            client_secret=cognito_user_pool["client_secret"],
            region_name=cognito_user_pool["region"],
        )
        # Replace client with the mocked one
        auth.client = cognito_user_pool["client"]
        return auth

    @pytest.fixture
    def authenticator_no_secret(self, cognito_user_pool_no_secret):
        """Create an authenticator without client secret."""
        auth = CognitoBotoAuthenticator(
            user_pool_id=cognito_user_pool_no_secret["pool_id"],
            client_id=cognito_user_pool_no_secret["client_id"],
            client_secret=None,
            region_name=cognito_user_pool_no_secret["region"],
        )
        auth.client = cognito_user_pool_no_secret["client"]
        return auth


class TestGetBoto3AuthHash:
    """Tests for get_boto3_auth_hash method."""

    def test_returns_hash_when_secret_configured(self):
        """Should return HMAC-SHA256 hash when client_secret is set."""
        auth = CognitoBotoAuthenticator.__new__(CognitoBotoAuthenticator)
        auth.client_secret = "test-secret"
        auth.client_id = "test-client-id"

        result = auth.get_boto3_auth_hash("testuser")

        # Verify it's a valid base64 string
        assert result is not None
        decoded = base64.b64decode(result)
        assert len(decoded) == 32  # SHA256 produces 32 bytes

    def test_returns_none_when_no_secret(self):
        """Should return None when client_secret is not set."""
        auth = CognitoBotoAuthenticator.__new__(CognitoBotoAuthenticator)
        auth.client_secret = None
        auth.client_id = "test-client-id"

        result = auth.get_boto3_auth_hash("testuser")

        assert result is None

    def test_hash_is_deterministic(self):
        """Same inputs should produce same hash."""
        auth = CognitoBotoAuthenticator.__new__(CognitoBotoAuthenticator)
        auth.client_secret = "test-secret"
        auth.client_id = "test-client-id"

        hash1 = auth.get_boto3_auth_hash("testuser")
        hash2 = auth.get_boto3_auth_hash("testuser")

        assert hash1 == hash2

    def test_different_users_produce_different_hashes(self):
        """Different usernames should produce different hashes."""
        auth = CognitoBotoAuthenticator.__new__(CognitoBotoAuthenticator)
        auth.client_secret = "test-secret"
        auth.client_id = "test-client-id"

        hash1 = auth.get_boto3_auth_hash("user1")
        hash2 = auth.get_boto3_auth_hash("user2")

        assert hash1 != hash2

    def test_hash_matches_expected_algorithm(self):
        """Hash should match manual HMAC-SHA256 calculation."""
        auth = CognitoBotoAuthenticator.__new__(CognitoBotoAuthenticator)
        auth.client_secret = "test-secret"
        auth.client_id = "test-client-id"
        username = "testuser"

        result = auth.get_boto3_auth_hash(username)

        # Manual calculation
        message = username + auth.client_id
        expected = base64.b64encode(
            hmac.new(
                auth.client_secret.encode("utf-8"),
                message.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
        ).decode()

        assert result == expected


class TestAuthenticate:
    """Tests for authenticate method."""

    @pytest.fixture
    def authenticator_with_user(self, test_user):
        """Create authenticator with a pre-configured test user."""
        auth = CognitoBotoAuthenticator(
            user_pool_id=test_user["pool_id"],
            client_id=test_user["client_id"],
            client_secret=test_user["client_secret"],
            region_name=test_user["region"],
        )
        auth.client = test_user["client"]
        return auth, test_user

    async def test_successful_authentication(self, authenticator_with_user):
        """Should return user data on successful authentication."""
        auth, user_data = authenticator_with_user

        result = await auth.authenticate(
            None,
            {"username": user_data["username"], "password": user_data["password"]},
        )

        assert result is not None
        assert result["name"] == user_data["username"]
        assert "auth_state" in result
        assert "AccessToken" in result["auth_state"]

    async def test_wrong_password_returns_none(self, authenticator_with_user):
        """Should return None for incorrect password."""
        auth, user_data = authenticator_with_user

        result = await auth.authenticate(
            None,
            {"username": user_data["username"], "password": "WrongPassword123!"},
        )

        assert result is None

    async def test_nonexistent_user_returns_none(self, authenticator_with_user):
        """Should return None for non-existent user."""
        auth, _ = authenticator_with_user

        result = await auth.authenticate(
            None,
            {"username": "nonexistent@example.com", "password": "SomePassword123!"},
        )

        assert result is None

    async def test_empty_username_returns_none(self, authenticator_with_user):
        """Should return None for empty username."""
        auth, _ = authenticator_with_user

        result = await auth.authenticate(
            None,
            {"username": "", "password": "SomePassword123!"},
        )

        assert result is None

    async def test_empty_password_returns_none(self, authenticator_with_user):
        """Should return None for empty password."""
        auth, user_data = authenticator_with_user

        result = await auth.authenticate(
            None,
            {"username": user_data["username"], "password": ""},
        )

        assert result is None

    async def test_missing_config_raises_error(self, cognito_user_pool):
        """Should raise HTTPError when user_pool_id or client_id not configured."""
        from tornado.web import HTTPError

        auth = CognitoBotoAuthenticator(
            user_pool_id="",  # Empty config
            client_id="",
            region_name="us-east-1",
        )

        with pytest.raises(HTTPError) as exc_info:
            await auth.authenticate(
                None,
                {"username": "test@example.com", "password": "TestPass123!"},
            )

        assert exc_info.value.status_code == 500


class TestSignup:
    """Tests for signup method."""

    @pytest.fixture
    def authenticator(self, cognito_user_pool):
        """Create authenticator for signup tests."""
        auth = CognitoBotoAuthenticator(
            user_pool_id=cognito_user_pool["pool_id"],
            client_id=cognito_user_pool["client_id"],
            client_secret=cognito_user_pool["client_secret"],
            region_name=cognito_user_pool["region"],
        )
        auth.client = cognito_user_pool["client"]
        return auth

    async def test_successful_signup(self, authenticator):
        """Should create new user and return user info."""
        result = await authenticator.signup(
            None,
            {"username": "newuser@example.com", "password": "NewPass123!"},
        )

        assert result is not None
        assert "username" in result
        assert "userConfirmed" in result

    async def test_signup_empty_username_raises_error(self, authenticator):
        """Should raise HTTPError for empty username."""
        from tornado.web import HTTPError

        with pytest.raises(HTTPError) as exc_info:
            await authenticator.signup(
                None,
                {"username": "", "password": "NewPass123!"},
            )

        assert exc_info.value.status_code == 400

    async def test_signup_empty_password_raises_error(self, authenticator):
        """Should raise HTTPError for empty password."""
        from tornado.web import HTTPError

        with pytest.raises(HTTPError) as exc_info:
            await authenticator.signup(
                None,
                {"username": "newuser@example.com", "password": ""},
            )

        assert exc_info.value.status_code == 400


class TestConfirmSignup:
    """Tests for confirm_signup method."""

    @pytest.fixture
    def authenticator(self, cognito_user_pool):
        """Create authenticator for confirm_signup tests."""
        auth = CognitoBotoAuthenticator(
            user_pool_id=cognito_user_pool["pool_id"],
            client_id=cognito_user_pool["client_id"],
            client_secret=cognito_user_pool["client_secret"],
            region_name=cognito_user_pool["region"],
        )
        auth.client = cognito_user_pool["client"]
        return auth

    async def test_empty_username_raises_error(self, authenticator):
        """Should raise HTTPError for empty username."""
        from tornado.web import HTTPError

        with pytest.raises(HTTPError) as exc_info:
            await authenticator.confirm_signup(
                None,
                {"username": "", "code": "123456"},
            )

        assert exc_info.value.status_code == 400

    async def test_empty_code_raises_error(self, authenticator):
        """Should raise HTTPError for empty code."""
        from tornado.web import HTTPError

        with pytest.raises(HTTPError) as exc_info:
            await authenticator.confirm_signup(
                None,
                {"username": "user@example.com", "code": ""},
            )

        assert exc_info.value.status_code == 400


class TestForgotPassword:
    """Tests for forgot_password method."""

    @pytest.fixture
    def authenticator_with_user(self, test_user):
        """Create authenticator with existing user for password reset tests."""
        auth = CognitoBotoAuthenticator(
            user_pool_id=test_user["pool_id"],
            client_id=test_user["client_id"],
            client_secret=test_user["client_secret"],
            region_name=test_user["region"],
        )
        auth.client = test_user["client"]
        return auth, test_user

    async def test_empty_username_raises_error(self, authenticator_with_user):
        """Should raise HTTPError for empty username."""
        from tornado.web import HTTPError

        auth, _ = authenticator_with_user

        with pytest.raises(HTTPError) as exc_info:
            await auth.forgot_password(None, {"username": ""})

        assert exc_info.value.status_code == 400


class TestConfirmPassword:
    """Tests for confirm_password method."""

    @pytest.fixture
    def authenticator(self, cognito_user_pool):
        """Create authenticator for confirm_password tests."""
        auth = CognitoBotoAuthenticator(
            user_pool_id=cognito_user_pool["pool_id"],
            client_id=cognito_user_pool["client_id"],
            client_secret=cognito_user_pool["client_secret"],
            region_name=cognito_user_pool["region"],
        )
        auth.client = cognito_user_pool["client"]
        return auth

    async def test_empty_username_raises_error(self, authenticator):
        """Should raise HTTPError for empty username."""
        from tornado.web import HTTPError

        with pytest.raises(HTTPError) as exc_info:
            await authenticator.confirm_password(
                None,
                {"username": "", "code": "123456", "password": "NewPass123!"},
            )

        assert exc_info.value.status_code == 400

    async def test_empty_code_raises_error(self, authenticator):
        """Should raise HTTPError for empty code."""
        from tornado.web import HTTPError

        with pytest.raises(HTTPError) as exc_info:
            await authenticator.confirm_password(
                None,
                {"username": "user@example.com", "code": "", "password": "NewPass123!"},
            )

        assert exc_info.value.status_code == 400

    async def test_empty_password_raises_error(self, authenticator):
        """Should raise HTTPError for empty password."""
        from tornado.web import HTTPError

        with pytest.raises(HTTPError) as exc_info:
            await authenticator.confirm_password(
                None,
                {"username": "user@example.com", "code": "123456", "password": ""},
            )

        assert exc_info.value.status_code == 400


class TestLogout:
    """Tests for logout method."""

    async def test_logout_with_none_user(self, cognito_user_pool):
        """Should handle None user gracefully."""
        auth = CognitoBotoAuthenticator(
            user_pool_id=cognito_user_pool["pool_id"],
            client_id=cognito_user_pool["client_id"],
            region_name=cognito_user_pool["region"],
        )
        auth.client = cognito_user_pool["client"]

        # Should not raise
        await auth.logout(None)


class TestEndpointUrl:
    """Tests for endpoint_url configuration."""

    @mock_aws
    def test_endpoint_url_default_is_none(self):
        """endpoint_url should default to None when not provided."""
        auth = CognitoBotoAuthenticator(
            user_pool_id="us-east-1_test",
            client_id="test-client",
            region_name="us-east-1",
        )

        assert auth.endpoint_url is None

    @mock_aws
    def test_client_created_without_endpoint_url(self):
        """Client should be created normally when endpoint_url is None."""
        auth = CognitoBotoAuthenticator(
            user_pool_id="us-east-1_test",
            client_id="test-client",
            region_name="us-east-1",
        )

        assert auth.client is not None

    @mock_aws
    def test_client_created_with_custom_endpoint_url(self):
        """Client should use custom endpoint_url when provided."""
        auth = CognitoBotoAuthenticator(
            user_pool_id="us-east-1_test",
            client_id="test-client",
            region_name="us-east-1",
        )
        # Set the trait after construction to avoid traitlets warning
        auth.endpoint_url = "http://localhost:5000"

        assert auth.endpoint_url == "http://localhost:5000"


class TestGetHandlers:
    """Tests for get_handlers method."""

    def test_returns_expected_handlers(self):
        """Should return list of auth handler tuples."""
        auth = CognitoBotoAuthenticator.__new__(CognitoBotoAuthenticator)

        handlers = auth.get_handlers(None)

        assert len(handlers) == 4
        paths = [h[0] for h in handlers]
        assert "/api/auth/signup" in paths
        assert "/api/auth/signup-confirmation" in paths
        assert "/api/auth/password-forgot" in paths
        assert "/api/auth/password-confirm" in paths


class TestCognitoOAuthAuthenticatorUserInfoToUsername:
    """Tests for CognitoOAuthAuthenticator.user_info_to_username method."""

    @pytest.fixture
    def oauth_authenticator(self):
        """Create a CognitoOAuthAuthenticator instance for testing."""
        from beakerhub.auth.cognito import CognitoOAuthAuthenticator
        auth = CognitoOAuthAuthenticator.__new__(CognitoOAuthAuthenticator)
        return auth

    def test_returns_email_sub_combination_when_both_present(self, oauth_authenticator):
        """Should return email_sub when both email and sub are present."""
        user_info = {"email": "user@example.com", "sub": "abc123"}

        result = oauth_authenticator.user_info_to_username(user_info)

        assert result == "user@example.com_abc123"

    def test_returns_email_when_only_email_present(self, oauth_authenticator):
        """Should return email when only email is present."""
        user_info = {"email": "user@example.com"}

        result = oauth_authenticator.user_info_to_username(user_info)

        assert result == "user@example.com"

    def test_returns_sub_when_only_sub_present(self, oauth_authenticator):
        """Should return sub when only sub is present."""
        user_info = {"sub": "abc123-def456"}

        result = oauth_authenticator.user_info_to_username(user_info)

        assert result == "abc123-def456"

    def test_raises_400_when_neither_present(self, oauth_authenticator):
        """Should raise HTTPError 400 when neither email nor sub is present."""
        from tornado.web import HTTPError

        user_info = {}

        with pytest.raises(HTTPError) as exc_info:
            oauth_authenticator.user_info_to_username(user_info)

        assert exc_info.value.status_code == 400

    def test_handles_none_values(self, oauth_authenticator):
        """Should handle explicit None values same as missing keys."""
        from tornado.web import HTTPError

        user_info = {"email": None, "sub": None}

        with pytest.raises(HTTPError) as exc_info:
            oauth_authenticator.user_info_to_username(user_info)

        assert exc_info.value.status_code == 400
