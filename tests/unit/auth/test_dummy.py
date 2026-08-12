# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""Unit tests for DummyBeakerhubAuthenticator."""

from beakerhub.auth.dummy import DummyBeakerhubAuthenticator


class TestAuthenticate:
    """Tests for DummyBeakerhubAuthenticator.authenticate."""

    async def test_accepts_username_and_password(self):
        authenticator = DummyBeakerhubAuthenticator()

        result = await authenticator.authenticate(
            None,
            {"username": "developer@example.com", "password": "anything"},
        )

        assert result == {"name": "developer@example.com"}

    async def test_accepts_empty_password(self):
        authenticator = DummyBeakerhubAuthenticator()

        result = await authenticator.authenticate(
            None,
            {"username": "developer@example.com", "password": ""},
        )

        assert result == {"name": "developer@example.com"}

    async def test_rejects_empty_username(self):
        authenticator = DummyBeakerhubAuthenticator()

        result = await authenticator.authenticate(
            None,
            {"username": "", "password": "anything"},
        )

        assert result is None

    async def test_does_not_grant_admin_from_username(self):
        authenticator = DummyBeakerhubAuthenticator()

        result = await authenticator.authenticate(
            None,
            {"username": "notadmin@example.com", "password": "anything"},
        )

        assert result == {"name": "notadmin@example.com"}
