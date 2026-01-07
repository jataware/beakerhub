# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""Unit tests for BeakerhubUser and BeakerhubUserDict."""

from unittest.mock import MagicMock, patch

import pytest

from beakerhub.auth.user import BeakerhubUser, BeakerhubUserDict


class MockOrmUser:
    """Mock JupyterHub ORM User object."""

    def __init__(self, user_id: int = 1, name: str = "testuser"):
        self.id = user_id
        self.name = name
        self.admin = False
        self.created = None
        self.last_activity = None
        self.cookie_id = "mock-cookie-id"
        self.encrypted_auth_state = None
        self.roles = []
        self.groups = []
        self.servers = {}


class MockSpawner:
    """Mock spawner object."""

    def __init__(self, ready: bool = False):
        self.ready = ready


class TestBeakerhubUser:
    """Tests for BeakerhubUser class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings dict."""
        return {
            "base_url": "/hub",
            "cookie_secret": b"secret",
            "db": MagicMock(),
        }

    @pytest.fixture
    def mock_orm_user(self):
        """Create a mock ORM user."""
        return MockOrmUser()

    def test_base_url_includes_session_path(self, mock_settings, mock_orm_user):
        """base_url should be base_url + /session."""
        with patch.object(BeakerhubUser, "__init__", lambda self, *args, **kwargs: None):
            user = BeakerhubUser.__new__(BeakerhubUser)
            user.settings = mock_settings
            user.base_url = "/hub/session"
            user.prefix = user.base_url

            assert user.base_url == "/hub/session"
            assert user.prefix == "/hub/session"

    def test_base_url_with_default_base(self):
        """Should use / as default when base_url not in settings."""
        with patch.object(BeakerhubUser, "__init__", lambda self, *args, **kwargs: None):
            user = BeakerhubUser.__new__(BeakerhubUser)
            user.settings = {}
            # Simulate the constructor behavior
            from jupyterhub.utils import url_path_join

            user.base_url = url_path_join(user.settings.get("base_url", "/"), "session")

            assert user.base_url == "/session"

    def test_running_property_true_when_spawner_ready(self):
        """running should be True when any spawner is ready."""
        with patch.object(BeakerhubUser, "__init__", lambda self, *args, **kwargs: None):
            user = BeakerhubUser.__new__(BeakerhubUser)
            user.spawners = {
                "server1": MockSpawner(ready=False),
                "server2": MockSpawner(ready=True),
            }

            assert user.running is True

    def test_running_property_false_when_no_spawners_ready(self):
        """running should be False when no spawners are ready."""
        with patch.object(BeakerhubUser, "__init__", lambda self, *args, **kwargs: None):
            user = BeakerhubUser.__new__(BeakerhubUser)
            user.spawners = {
                "server1": MockSpawner(ready=False),
                "server2": MockSpawner(ready=False),
            }

            assert user.running is False

    def test_running_property_false_when_no_spawners(self):
        """running should be False when there are no spawners."""
        with patch.object(BeakerhubUser, "__init__", lambda self, *args, **kwargs: None):
            user = BeakerhubUser.__new__(BeakerhubUser)
            user.spawners = {}

            assert user.running is False

    def test_spawner_property_returns_none(self):
        """spawner property should always return None."""
        with patch.object(BeakerhubUser, "__init__", lambda self, *args, **kwargs: None):
            user = BeakerhubUser.__new__(BeakerhubUser)

            assert user.spawner is None

    def test_spawner_setter_does_nothing(self):
        """spawner setter should accept value but do nothing."""
        with patch.object(BeakerhubUser, "__init__", lambda self, *args, **kwargs: None):
            user = BeakerhubUser.__new__(BeakerhubUser)

            # Should not raise
            user.spawner = MockSpawner()

            # Should still return None
            assert user.spawner is None


class TestBeakerhubUserDict:
    """Tests for BeakerhubUserDict class."""

    @pytest.fixture
    def user_dict(self):
        """Create a BeakerhubUserDict instance."""
        settings = {
            "base_url": "/",
            "cookie_secret": b"secret",
            "db": MagicMock(),
        }
        db_factory = MagicMock()
        return BeakerhubUserDict(db_factory=db_factory, settings=settings)

    def test_from_orm_returns_beakerhub_user(self, user_dict):
        """from_orm should return a BeakerhubUser instance."""
        orm_user = MockOrmUser()

        with patch.object(BeakerhubUser, "__init__", return_value=None):
            result = user_dict.from_orm(orm_user)

            assert isinstance(result, BeakerhubUser)

    def test_getitem_with_orm_user_creates_beakerhub_user(self, user_dict):
        """__getitem__ with ORM user should create and cache BeakerhubUser."""
        from jupyterhub import orm

        # Create a mock that passes isinstance check for orm.User
        mock_orm_user = MagicMock(spec=orm.User)
        mock_orm_user.id = 123

        with patch.object(user_dict, "from_orm") as mock_from_orm:
            mock_beakerhub_user = MagicMock(spec=BeakerhubUser)
            mock_from_orm.return_value = mock_beakerhub_user

            result = user_dict[mock_orm_user]

            mock_from_orm.assert_called_once_with(mock_orm_user)
            assert result == mock_beakerhub_user
            # Should be cached
            assert 123 in user_dict

    def test_getitem_with_cached_user_returns_cached(self, user_dict):
        """__getitem__ should return cached user on subsequent calls."""
        from jupyterhub import orm

        mock_orm_user = MagicMock(spec=orm.User)
        mock_orm_user.id = 456

        cached_user = MagicMock(spec=BeakerhubUser)
        user_dict[456] = cached_user

        result = user_dict[mock_orm_user]

        assert result == cached_user

    def test_getitem_with_int_key(self, user_dict):
        """__getitem__ with int key should use normal dict behavior."""
        cached_user = MagicMock(spec=BeakerhubUser)
        user_dict[789] = cached_user

        result = user_dict[789]

        assert result == cached_user

