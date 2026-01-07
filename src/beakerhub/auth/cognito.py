import base64
import hashlib
import hmac
import json

import boto3
import traitlets
from botocore.exceptions import ClientError
from jupyterhub.user import User
from jupyterhub.auth import Authenticator
from oauthenticator.oauth2 import OAuthenticator
from tornado import web

from beakerhub.auth.base import BeakerhubAuthenticator
from beakerhub.auth.handlers import LoginHandler, LogoutHandler, SignupHandler, ConfirmSignupHandler, ForgotPasswordHandler, ConfirmPasswordHandler


class CognitoOAuthAuthenticator(OAuthenticator, metaclass=BeakerhubAuthenticator):

    auth_domain: str = traitlets.Unicode(
        help="Domain used by cognito for authentication.",
        config=True,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    login_service = "AWS Cognito"

    def user_info_to_username(self, user_info: dict[str, str]):
        email = user_info.get("email", None)
        sub = user_info.get("sub", None)
        match (email, sub):
            case str(), str():
                return f"{email}_{sub}"
            case str(), None:
                return email
            case None, str():
                return sub
            case _:
                raise web.HTTPError(400, "OAuth user info missing required fields (email or sub)")

    @traitlets.default("authorize_url")
    def _default_authorize_url(self):
        return f"https://{self.auth_domain}/oauth2/authorize"

    @traitlets.default("token_url")
    def _default_token_url(self):
        return f"https://{self.auth_domain}/oauth2/token"

    @traitlets.default("userdata_url")
    def _default_userdata_url(self):
        return f"https://{self.auth_domain}/oauth2/userInfo"

    def get_handlers(self, app):
        return super().get_handlers(app)


class CognitoBotoAuthenticator(Authenticator, metaclass=BeakerhubAuthenticator):
    """
    Authenticate users against AWS Cognito using boto3.

    This authenticator uses boto3's cognito-idp client to authenticate
    users with username and password against a Cognito User Pool.
    """
    enable_auth_state = True

    user_pool_id = traitlets.Unicode(
        help="""
        AWS Cognito User Pool ID.

        Example: 'us-east-1_AbCdEfGhI'
        """,
        config=True,
    )

    client_id = traitlets.Unicode(
        help="""
        AWS Cognito App Client ID.

        This is the client ID for your Cognito User Pool App Client.
        The App Client must have USER_PASSWORD_AUTH flow enabled.
        """,
        config=True,
    )

    client_secret = traitlets.Unicode(
        default_value=None,
        allow_none=True,
        help="""
        AWS Cognito App Client ID.

        This is the client ID for your Cognito User Pool App Client.
        The App Client must have USER_PASSWORD_AUTH flow enabled.
        """,
        config=True,
    )

    region_name = traitlets.Unicode(
        default_value="us-east-1",
        help="""
        AWS Region where the Cognito User Pool is located.

        Defaults to 'us-east-1'.
        """,
        config=True,
    )

    endpoint_url = traitlets.Unicode(
        default_value=None,
        allow_none=True,
        help="""
        Custom endpoint URL for the Cognito service.

        Used for testing with moto or other Cognito-compatible services.
        When None (default), uses the standard AWS Cognito endpoint.
        """,
        config=True,
    )

    client: boto3.client

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client_kwargs = {"region_name": self.region_name}
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url
        self.client = boto3.client('cognito-idp', **client_kwargs)

    @property
    def boto3_client_options(self) -> dict:
        """
        Docstring for client_options

        :param self: Description
        """
        if self.client_secret is not None:
            return {
                "ClientId": self.client_id,
                "ClientSecret": self.client_secret,
            }
        else:
            return {
                "ClientId": self.client_id,
            }

    def get_boto3_auth_hash(self, username: str) -> str|None:
        if self.client_secret:
            return base64.b64encode(hmac.new(bytes(self.client_secret, 'utf-8'), bytes(
                username + self.client_id, 'utf-8'), digestmod=hashlib.sha256).digest()).decode()
        else:
            return None

    async def authenticate(self, handler, data):
        """
        Authenticate a user against AWS Cognito using boto3.

        Args:
            handler: The tornado request handler
            data: Dictionary containing 'username' and 'password' from login form

        Returns:
            A dictionary containing user details on successful authentication, None on failure
        """

        username = data.get("username", "")
        password = data.get("password", "")

        if not username or not password:
            self.log.warning("Empty username or password provided")
            return None

        if not self.user_pool_id or not self.client_id:
            self.log.error("user_pool_id and client_id must be configured")
            raise web.HTTPError(500, "Authentication service not properly configured")

        auth_params = {
            'USERNAME': username,
            'PASSWORD': password,
        }

        auth_hash = self.get_boto3_auth_hash(username)
        if auth_hash:
            auth_params["SECRET_HASH"] = auth_hash

        try:

            # Attempt authentication using USER_PASSWORD_AUTH flow
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters=auth_params,
            )

            # Check if authentication was successful
            if 'AuthenticationResult' in response:
                # Successfully authenticated with tokens
                self.log.info(f"Successfully authenticated user: {username}")

                # Decode the IdToken JWT to check Cognito group membership
                is_admin = False
                id_token = response["AuthenticationResult"].get("IdToken")
                if id_token:
                    try:
                        payload = id_token.split(".")[1]
                        # Add padding for base64url decoding
                        payload += "=" * (4 - len(payload) % 4)
                        claims = json.loads(base64.urlsafe_b64decode(payload))
                        cognito_groups = claims.get("cognito:groups", [])
                        is_admin = "admin" in cognito_groups
                    except (IndexError, json.JSONDecodeError, Exception) as e:
                        self.log.warning(
                            f"Failed to decode IdToken for user {username}: {e}"
                        )

                return {
                    "name": username,
                    "admin": is_admin,
                    "auth_state": response["AuthenticationResult"],
                }
            elif 'ChallengeName' in response:
                # Authentication requires additional steps (MFA, password reset, etc.)
                challenge = response['ChallengeName']
                self.log.warning(
                    f"Authentication for user {username} requires challenge: {challenge}. "
                    "This authenticator does not support authentication challenges."
                )
                return None
            else:
                # Unexpected response format
                self.log.error(f"Unexpected response format from Cognito for user {username}")
                return None

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', '')

            if error_code in ['NotAuthorizedException', 'UserNotFoundException']:
                self.log.warning(f"Authentication failed for user {username}: {error_message}")
                return None
            else:
                self.log.error(f"Cognito authentication error for user {username}: {error_code} - {error_message}")
                raise web.HTTPError(500, "Authentication service error")

        except Exception as e:
            self.log.error(f"Unexpected error during authentication for user {username}: {str(e)}")
            raise web.HTTPError(500, "Authentication service error")

    async def logout(self, user: User):
        if not user:
            return
        auth_state = await user.get_auth_state()
        if not auth_state:
            return
        access_token: str = auth_state.get("AccessToken", None)

        self.client.global_sign_out(
            AccessToken=access_token,
        )

    async def signup(self, handler, data):
        username = data.get("username", "")
        password = data.get("password", "")
        organization = data.get("organization", None)

        if not username or not password:
            raise web.HTTPError(400, "Username and password are required")

        # Prepare user attributes
        user_attributes = [
            {"Name": "email", "Value": username}
        ]

        # TODO: Map organization to Cognito custom attribute
        # Need to define custom attribute in Cognito User Pool (e.g., custom:organization)
        # if organization:
        #     user_attributes.append({"Name": "custom:organization", "Value": organization})

        secret_hash = self.get_boto3_auth_hash(username)
        kwargs = {
            "ClientId": self.client_id,
            "Username": username,
            "Password": password,
            "UserAttributes": user_attributes,
        }

        if secret_hash:
            kwargs["SecretHash"] = secret_hash

        try:
            response = self.client.sign_up(**kwargs)
        except ClientError as e:
            error_message = e.response.get("Error", {}).get("Message", "Signup failed")
            self.log.warning(f"Signup failed for {username}: {error_message}")
            raise web.HTTPError(400, error_message)

        # TODO: Validate this is the correct thing to return
        return {
            "username": response.get("UserSub"),
            "userConfirmed": response.get("UserConfirmed", False)
        }

    async def confirm_signup(self, handler, data):
        username = data.get("username", "")
        code = data.get("code", "")

        if not username or not code:
            raise web.HTTPError(400, "Username and confirmation code are required")

        secret_hash = self.get_boto3_auth_hash(username)
        kwargs = {
            "ClientId": self.client_id,
            "Username": username,
            "ConfirmationCode": code,
        }

        if secret_hash:
            kwargs["SecretHash"] = secret_hash

        try:
            self.client.confirm_sign_up(**kwargs)
        except ClientError as e:
            error_message = e.response.get("Error", {}).get("Message", "Verification failed")
            self.log.warning(f"Signup confirmation failed for {username}: {error_message}")
            raise web.HTTPError(400, error_message)
        return True

    async def forgot_password(self, handler, data):
        username = data.get("username", "")

        if not username:
            raise web.HTTPError(400, "Username is required")

        secret_hash = self.get_boto3_auth_hash(username)
        kwargs = {
            "ClientId": self.client_id,
            "Username": username,
        }

        if secret_hash:
            kwargs["SecretHash"] = secret_hash

        try:
            self.client.forgot_password(**kwargs)
        except ClientError as e:
            error_message = e.response.get("Error", {}).get("Message", "Failed to send reset code")
            self.log.warning(f"Forgot password failed for {username}: {error_message}")
            raise web.HTTPError(400, error_message)
        pass

    async def confirm_password(self, handler, data):
        username = data.get("username", "")
        code = data.get("code", "")
        password = data.get("password", "")

        if not username or not code or not password:
            raise web.HTTPError(400, "Username, confirmation code, and new password are required")

        secret_hash = self.get_boto3_auth_hash(username)
        kwargs = {
            "ClientId": self.client_id,
            "Username": username,
            "ConfirmationCode": code,
            "Password": password,
        }

        if secret_hash:
            kwargs["SecretHash"] = secret_hash

        try:
            self.client.confirm_forgot_password(**kwargs)
        except ClientError as e:
            error_message = e.response.get("Error", {}).get("Message", "Failed to reset password")
            self.log.warning(f"Password reset confirmation failed for {username}: {error_message}")
            raise web.HTTPError(400, error_message)

        return True

    def get_handlers(self, app):
        handlers = [
            (r'/api/auth/signup', SignupHandler),
            (r'/api/auth/signup-confirmation', ConfirmSignupHandler),
            (r'/api/auth/password-forgot', ForgotPasswordHandler),
            (r'/api/auth/password-confirm', ConfirmPasswordHandler),
        ]
        return handlers
