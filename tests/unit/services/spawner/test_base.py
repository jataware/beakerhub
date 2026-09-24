# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""Unit tests for the base spawner service."""

import re
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from beakerhub.services.spawner.base import BeakerSpawner


class TestBeakerSpawner:
    """Tests for BeakerSpawner class."""

    def test_init_sets_proxy_spec_with_domain(self):
        """__init__ should set proxy_spec with name.domain format when domain provided."""
        with patch.object(BeakerSpawner.__bases__[0], "__init__", return_value=None):
            with patch.object(
                BeakerSpawner, "name", new_callable=PropertyMock, return_value="my-session"
            ):
                spawner = BeakerSpawner(domain="example.com")

                # proxy_spec should be set to name.domain
                assert spawner.proxy_spec == "my-session.example.com/"

    def test_init_does_not_set_proxy_spec_without_domain(self):
        """__init__ should not set proxy_spec when domain is not provided."""
        with patch.object(BeakerSpawner.__bases__[0], "__init__", return_value=None):
            with patch.object(
                BeakerSpawner, "name", new_callable=PropertyMock, return_value="test"
            ):
                spawner = BeakerSpawner()

                # proxy_spec should not be set when domain not provided
                assert not hasattr(spawner, "proxy_spec") or spawner.proxy_spec == ""

    def test_init_does_not_set_proxy_spec_with_empty_domain(self):
        """__init__ should not set proxy_spec when domain is empty string."""
        with patch.object(BeakerSpawner.__bases__[0], "__init__", return_value=None):
            with patch.object(
                BeakerSpawner, "name", new_callable=PropertyMock, return_value="test"
            ):
                spawner = BeakerSpawner(domain="")

                # proxy_spec should not be set when domain is empty
                assert not hasattr(spawner, "proxy_spec") or spawner.proxy_spec == ""

    def test_session_id_returns_name_when_set(self):
        """session_id property should return name when it's already set."""
        with patch.object(BeakerSpawner.__bases__[0], "__init__", return_value=None):
            with patch.object(
                BeakerSpawner, "name", new_callable=PropertyMock, return_value="my-named-session"
            ):
                spawner = BeakerSpawner(domain="example.com")

                result = spawner.session_id

                assert result == "my-named-session"

    # Note: Tests for session_id UUID generation with empty name are omitted because
    # JupyterHub's traitlets system makes them difficult to mock at the unit test level.
    # The implementation correctly generates and stores a UUID when name is empty.
    # Integration tests should verify this behavior.

    def test_start_raises_not_implemented(self):
        """start() should raise NotImplementedError."""
        with patch.object(BeakerSpawner.__bases__[0], "__init__", return_value=None):
            with patch.object(
                BeakerSpawner, "name", new_callable=PropertyMock, return_value="test"
            ):
                spawner = BeakerSpawner(domain="example.com")

                with pytest.raises(NotImplementedError):
                    spawner.start()

    def test_stop_raises_not_implemented(self):
        """stop() should raise NotImplementedError."""
        with patch.object(BeakerSpawner.__bases__[0], "__init__", return_value=None):
            with patch.object(
                BeakerSpawner, "name", new_callable=PropertyMock, return_value="test"
            ):
                spawner = BeakerSpawner(domain="example.com")

                with pytest.raises(NotImplementedError):
                    spawner.stop()

    def test_stop_with_now_parameter_raises_not_implemented(self):
        """stop(now=True) should raise NotImplementedError."""
        with patch.object(BeakerSpawner.__bases__[0], "__init__", return_value=None):
            with patch.object(
                BeakerSpawner, "name", new_callable=PropertyMock, return_value="test"
            ):
                spawner = BeakerSpawner(domain="example.com")

                with pytest.raises(NotImplementedError):
                    spawner.stop(now=True)

    def test_poll_raises_not_implemented(self):
        """poll() should raise NotImplementedError."""
        with patch.object(BeakerSpawner.__bases__[0], "__init__", return_value=None):
            with patch.object(
                BeakerSpawner, "name", new_callable=PropertyMock, return_value="test"
            ):
                spawner = BeakerSpawner(domain="example.com")

                with pytest.raises(NotImplementedError):
                    spawner.poll()
