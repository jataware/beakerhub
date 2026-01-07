# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""Shared fixtures for unit tests."""

import pytest
import boto3
from moto import mock_aws


@pytest.fixture
def cognito_user_pool():
    """
    Create a mocked Cognito User Pool with an app client.

    Yields a dictionary containing:
        - client: boto3 cognito-idp client
        - pool_id: User Pool ID
        - client_id: App Client ID
        - client_secret: App Client Secret
        - region: AWS region
    """
    with mock_aws():
        client = boto3.client("cognito-idp", region_name="us-east-1")

        # Create user pool
        pool_response = client.create_user_pool(
            PoolName="test-pool",
            Policies={
                "PasswordPolicy": {
                    "MinimumLength": 8,
                    "RequireUppercase": True,
                    "RequireLowercase": True,
                    "RequireNumbers": True,
                    "RequireSymbols": False,
                }
            },
            AutoVerifiedAttributes=["email"],
            UsernameAttributes=["email"],
        )
        pool_id = pool_response["UserPool"]["Id"]

        # Create app client with secret
        client_response = client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName="test-client",
            GenerateSecret=True,
            ExplicitAuthFlows=[
                "ALLOW_USER_PASSWORD_AUTH",
                "ALLOW_REFRESH_TOKEN_AUTH",
            ],
        )

        yield {
            "client": client,
            "pool_id": pool_id,
            "client_id": client_response["UserPoolClient"]["ClientId"],
            "client_secret": client_response["UserPoolClient"]["ClientSecret"],
            "region": "us-east-1",
        }


@pytest.fixture
def cognito_user_pool_no_secret():
    """
    Create a mocked Cognito User Pool without a client secret.

    Useful for testing authenticator behavior when no secret hash is required.
    """
    with mock_aws():
        client = boto3.client("cognito-idp", region_name="us-east-1")

        pool_response = client.create_user_pool(
            PoolName="test-pool-no-secret",
            AutoVerifiedAttributes=["email"],
            UsernameAttributes=["email"],
        )
        pool_id = pool_response["UserPool"]["Id"]

        client_response = client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName="test-client-no-secret",
            GenerateSecret=False,
            ExplicitAuthFlows=[
                "ALLOW_USER_PASSWORD_AUTH",
                "ALLOW_REFRESH_TOKEN_AUTH",
            ],
        )

        yield {
            "client": client,
            "pool_id": pool_id,
            "client_id": client_response["UserPoolClient"]["ClientId"],
            "client_secret": None,
            "region": "us-east-1",
        }


@pytest.fixture
def test_user(cognito_user_pool):
    """
    Create a confirmed test user in the mocked Cognito pool.

    Returns the cognito_user_pool fixture data plus:
        - username: The test user's email/username
        - password: The test user's password
    """
    username = "testuser@example.com"
    password = "TestPass123!"

    # Create user
    cognito_user_pool["client"].admin_create_user(
        UserPoolId=cognito_user_pool["pool_id"],
        Username=username,
        UserAttributes=[
            {"Name": "email", "Value": username},
            {"Name": "email_verified", "Value": "true"},
        ],
        MessageAction="SUPPRESS",
    )

    # Set permanent password (confirms user)
    cognito_user_pool["client"].admin_set_user_password(
        UserPoolId=cognito_user_pool["pool_id"],
        Username=username,
        Password=password,
        Permanent=True,
    )

    return {
        **cognito_user_pool,
        "username": username,
        "password": password,
    }
