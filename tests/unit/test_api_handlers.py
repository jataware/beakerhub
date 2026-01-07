# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""Unit tests for beakerhub.api_handlers module."""

import json
import pathlib
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from tornado import web

from beakerhub.api_handlers import (
    UserInfoHandler,
    ContextDetailsHandler,
    filter_contexts_by_role,
    get_context_role_map,
    get_override_handlers,
    handlers,
)
from beakerhub.orm import beaker_context_roles


class TestUserInfoHandler:
    """Tests for UserInfoHandler class."""

    @pytest.fixture
    def mock_handler(self):
        """Create a mock UserInfoHandler instance."""
        handler = MagicMock(spec=UserInfoHandler)
        handler.get_query_argument = MagicMock(return_value=None)
        handler.set_status = MagicMock()
        handler.add_header = MagicMock()
        handler.write = MagicMock()
        handler.xsrf_token = "test-xsrf-token"
        handler.current_user = None
        # Mock request headers so Authorization check returns None.
        # Use PropertyMock because `request` is an instance attr not on the spec class.
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        type(handler).request = PropertyMock(return_value=mock_request)
        return handler

    def test_check_xsrf_cookie_returns_none(self, mock_handler):
        """check_xsrf_cookie should return without checking."""
        result = UserInfoHandler.check_xsrf_cookie(mock_handler)
        assert result is None

    @pytest.mark.asyncio
    async def test_head_returns_401_when_not_authenticated(self, mock_handler):
        """head() should set 401 when user is not authenticated."""
        mock_handler.current_user = None
        mock_handler.get_query_argument.return_value = "testuser"

        await UserInfoHandler.head(mock_handler)

        mock_handler.set_status.assert_called_once_with(401, "Not authenticated")

    @pytest.mark.asyncio
    async def test_head_returns_401_when_username_mismatch(self, mock_handler):
        """head() should set 401 when query user doesn't match current user."""
        mock_user = MagicMock()
        mock_user.name = "actualuser"
        mock_handler.current_user = mock_user
        mock_handler.get_query_argument.return_value = "differentuser"

        await UserInfoHandler.head(mock_handler)

        mock_handler.set_status.assert_called_once_with(401, "Not authenticated")

    @pytest.mark.asyncio
    async def test_head_succeeds_when_user_matches(self, mock_handler):
        """head() should not set 401 when user matches query param."""
        mock_user = MagicMock()
        mock_user.name = "testuser"
        mock_handler.current_user = mock_user
        mock_handler.get_query_argument.return_value = "testuser"

        await UserInfoHandler.head(mock_handler)

        mock_handler.set_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_adds_xsrf_header(self, mock_handler):
        """get() should add X-SET-XSRFTOKEN header when xsrf_token exists."""
        mock_handler.xsrf_token = "test-token-123"

        # Mock the parent get() to succeed
        with patch.object(
            UserInfoHandler.__bases__[0], "get", new_callable=AsyncMock
        ) as mock_parent_get:
            await UserInfoHandler.get(mock_handler)

        mock_handler.add_header.assert_called_once_with(
            "X-SET-XSRFTOKEN", "test-token-123"
        )

    @pytest.mark.asyncio
    async def test_get_handles_403_without_raising(self, mock_handler):
        """get() should set 403 status without raising when parent raises 403."""
        mock_handler.xsrf_token = "test-token"

        # Mock parent get() to raise 403
        with patch.object(
            UserInfoHandler.__bases__[0],
            "get",
            new_callable=AsyncMock,
            side_effect=web.HTTPError(403, reason="Forbidden"),
        ):
            # Should not raise
            await UserInfoHandler.get(mock_handler)

        mock_handler.set_status.assert_called_once_with(403, "Forbidden")

    @pytest.mark.asyncio
    async def test_get_reraises_non_403_errors(self, mock_handler):
        """get() should re-raise non-403 HTTP errors."""
        mock_handler.xsrf_token = "test-token"

        with patch.object(
            UserInfoHandler.__bases__[0],
            "get",
            new_callable=AsyncMock,
            side_effect=web.HTTPError(500, reason="Server Error"),
        ):
            with pytest.raises(web.HTTPError) as exc_info:
                await UserInfoHandler.get(mock_handler)

            assert exc_info.value.status_code == 500


class TestContextDetailsHandler:
    """Tests for ContextDetailsHandler class."""

    @pytest.fixture
    def mock_handler(self):
        """Create a mock ContextDetailsHandler instance."""
        handler = MagicMock(spec=ContextDetailsHandler)
        handler.write = MagicMock()
        handler.set_header = MagicMock()

        # Mock authenticated user with no roles
        mock_user = MagicMock()
        mock_user.roles = []
        handler.current_user = mock_user

        # Set up mock DB that returns empty query results
        mock_query = MagicMock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        handler.db.query.return_value = mock_query

        # Mock db.execute for role map queries
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        handler.db.execute.return_value = mock_result

        return handler

    @pytest.mark.asyncio
    async def test_get_returns_empty_contexts_and_nodes_when_db_empty(
        self, mock_handler
    ):
        """get() should return empty contexts and nodes when database has no records."""
        await ContextDetailsHandler.get(mock_handler)

        written = mock_handler.write.call_args[0][0]
        result = json.loads(written)
        assert result == {"contexts": {}, "nodes": {}}

    @pytest.mark.asyncio
    async def test_get_returns_403_when_not_authenticated(self, mock_handler):
        """get() should raise 403 when user is not authenticated."""
        mock_handler.current_user = None

        with pytest.raises(web.HTTPError) as exc_info:
            await ContextDetailsHandler.get(mock_handler)

        assert exc_info.value.status_code == 403


class TestGetOverrideHandlers:
    """Tests for get_override_handlers function."""

    def test_returns_expected_handlers(self):
        """get_override_handlers should return the expected handler list."""
        result = get_override_handlers()

        assert len(result) == 2

        # Check routes
        routes = [r[0] for r in result]
        assert r"/api/user" in routes
        assert r"/api/beakerhub/contexts/details" in routes

        # Check handler classes
        handler_classes = [r[1] for r in result]
        assert UserInfoHandler in handler_classes
        assert ContextDetailsHandler in handler_classes

    def test_accepts_base_url_parameter(self):
        """get_override_handlers should accept base_url parameter."""
        result = get_override_handlers(base_url="/hub/")

        # Should still work (base_url is accepted but not currently used in routes)
        assert len(result) == 2


class TestHandlersList:
    """Tests for the handlers module-level list."""

    def test_handlers_list_contains_expected_routes(self):
        """handlers list should contain all expected routes."""
        routes = [h[0] for h in handlers]

        expected_routes = [
            r"/api/user",
            r"/api/users/([^/]+)/server",
            r"/api/users/([^/]+)/servers/([^/]*)",
            r"/api/users/([^/]+)/servers/([^/]*)/progress",
            r"/api/beakerhub/contexts/details",
        ]

        for expected in expected_routes:
            assert expected in routes, f"Missing route: {expected}"


class TestFilterContextsByRole:
    """Tests for the filter_contexts_by_role function."""

    @staticmethod
    def _make_context(context_id: int) -> MagicMock:
        """Create a mock Context with a given ID."""
        ctx = MagicMock()
        ctx.id = context_id
        return ctx

    @staticmethod
    def _make_db(role_rows: list[tuple[int, str]]) -> MagicMock:
        """Create a mock DB that returns given (context_id, role_name) rows."""
        db = MagicMock()
        mock_result = MagicMock()
        rows = [MagicMock(context_id=cid, role_name=rn) for cid, rn in role_rows]
        mock_result.fetchall.return_value = rows
        db.execute.return_value = mock_result
        return db

    def test_no_roles_returns_all(self):
        """Contexts with no role restrictions are returned for any user."""
        ctx_a = self._make_context(1)
        ctx_b = self._make_context(2)
        db = self._make_db([])  # No role rows

        result = filter_contexts_by_role(db, [ctx_a, ctx_b], {"TEAM_1"})

        assert result == [ctx_a, ctx_b]

    def test_matching_role(self):
        """Context restricted to TEAM_1 is returned when user has TEAM_1."""
        ctx = self._make_context(1)
        db = self._make_db([(1, "TEAM_1")])

        result = filter_contexts_by_role(db, [ctx], {"TEAM_1"})

        assert result == [ctx]

    def test_no_matching_role(self):
        """Context restricted to TEAM_1 is NOT returned when user only has TEAM_2."""
        ctx = self._make_context(1)
        db = self._make_db([(1, "TEAM_1")])

        result = filter_contexts_by_role(db, [ctx], {"TEAM_2"})

        assert result == []

    def test_multiple_roles_union(self):
        """User with multiple roles sees contexts restricted to any of them."""
        ctx_a = self._make_context(1)  # Restricted to TEAM_1
        ctx_b = self._make_context(2)  # Restricted to TEAM_2
        ctx_c = self._make_context(3)  # Restricted to TEAM_3
        db = self._make_db([
            (1, "TEAM_1"),
            (2, "TEAM_2"),
            (3, "TEAM_3"),
        ])

        result = filter_contexts_by_role(
            db, [ctx_a, ctx_b, ctx_c], {"TEAM_1", "TEAM_2"}
        )

        assert result == [ctx_a, ctx_b]

    def test_empty_user_roles_only_sees_unrestricted(self):
        """User with no roles only sees unrestricted contexts."""
        ctx_unrestricted = self._make_context(1)
        ctx_restricted = self._make_context(2)
        db = self._make_db([(2, "TEAM_1")])

        result = filter_contexts_by_role(
            db, [ctx_unrestricted, ctx_restricted], set()
        )

        assert result == [ctx_unrestricted]

    def test_mixed_restricted_and_unrestricted(self):
        """Mix of restricted and unrestricted contexts returns correct subset."""
        ctx_all = self._make_context(1)       # No restrictions
        ctx_team1 = self._make_context(2)     # TEAM_1 only
        ctx_team2 = self._make_context(3)     # TEAM_2 only
        ctx_both = self._make_context(4)      # TEAM_1 and TEAM_2
        db = self._make_db([
            (2, "TEAM_1"),
            (3, "TEAM_2"),
            (4, "TEAM_1"),
            (4, "TEAM_2"),
        ])

        # User with TEAM_1 should see: ctx_all, ctx_team1, ctx_both
        result = filter_contexts_by_role(
            db, [ctx_all, ctx_team1, ctx_team2, ctx_both], {"TEAM_1"}
        )

        assert result == [ctx_all, ctx_team1, ctx_both]

    def test_empty_context_list(self):
        """Empty context list returns empty list without querying DB."""
        db = MagicMock()

        result = filter_contexts_by_role(db, [], {"TEAM_1"})

        assert result == []
        db.execute.assert_not_called()
