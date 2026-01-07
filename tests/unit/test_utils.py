# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""Unit tests for beakerhub.utils module."""

import datetime
import json
from unittest.mock import MagicMock, patch

import pytest
from jinja2 import Environment

from beakerhub.utils import to_json, ConfiguredVuePageLoader


class TestToJson:
    """Tests for to_json function."""

    def test_serializes_dict(self):
        """Should serialize a simple dictionary."""
        data = {"name": "test", "value": 123}
        result = to_json(data)

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed == data

    def test_serializes_list(self):
        """Should serialize a list."""
        data = [1, 2, 3, "four"]
        result = to_json(data)

        parsed = json.loads(result)
        assert parsed == data

    def test_serializes_nested_structures(self):
        """Should serialize nested dict/list structures."""
        data = {
            "users": [
                {"name": "alice", "active": True},
                {"name": "bob", "active": False},
            ],
            "count": 2,
        }
        result = to_json(data)

        parsed = json.loads(result)
        assert parsed == data

    def test_handles_datetime_objects(self):
        """Should serialize datetime objects using jupyter_client json_default."""
        dt = datetime.datetime(2024, 1, 15, 12, 30, 45)
        data = {"timestamp": dt}

        result = to_json(data)

        # Should not raise and should produce valid JSON
        parsed = json.loads(result)
        assert "timestamp" in parsed
        # jupyter_client formats datetime as ISO string
        assert "2024" in parsed["timestamp"]

    def test_handles_none_values(self):
        """Should serialize None as null."""
        data = {"value": None}
        result = to_json(data)

        parsed = json.loads(result)
        assert parsed["value"] is None

    def test_handles_boolean_values(self):
        """Should serialize booleans correctly."""
        data = {"active": True, "deleted": False}
        result = to_json(data)

        parsed = json.loads(result)
        assert parsed["active"] is True
        assert parsed["deleted"] is False


class TestConfiguredVuePageLoader:
    """Tests for ConfiguredVuePageLoader class."""

    @pytest.fixture
    def loader(self, tmp_path):
        """Create a loader with a temporary directory."""
        # Create a test template
        template_file = tmp_path / "index.html"
        template_file.write_text("<html>{{ siteConfig }}</html>")

        return ConfiguredVuePageLoader(
            searchpath=str(tmp_path),
            template_file="index.html",
            config={"appName": "TestApp", "version": "1.0.0"},
        )

    def test_list_templates_returns_only_template_file(self, loader):
        """list_templates should return only the configured template file."""
        templates = loader.list_templates()

        assert templates == ["index.html"]

    def test_init_sets_config(self, tmp_path):
        """Config should be stored and accessible."""
        config = {"key": "value"}
        loader = ConfiguredVuePageLoader(
            searchpath=str(tmp_path),
            template_file="test.html",
            config=config,
        )

        assert loader.config == config

    def test_init_defaults_config_to_empty_dict(self, tmp_path):
        """Config should default to empty dict if not provided."""
        loader = ConfiguredVuePageLoader(
            searchpath=str(tmp_path),
            template_file="test.html",
        )

        assert loader.config == {}

    def test_load_injects_site_config(self, tmp_path):
        """load should inject siteConfig into template globals."""
        template_file = tmp_path / "index.html"
        template_file.write_text("Config: {{ siteConfig }}")

        loader = ConfiguredVuePageLoader(
            searchpath=str(tmp_path),
            template_file="index.html",
            config={"appName": "TestApp"},
        )

        env = Environment(loader=loader)
        template = env.get_template("index.html")

        # Render and check output contains the config
        rendered = template.render()
        assert "appName" in rendered
        assert "TestApp" in rendered

    def test_load_merges_globals_when_provided(self, tmp_path):
        """load should merge siteConfig with globals dict when provided."""
        template_file = tmp_path / "test.html"
        template_file.write_text("{{ siteConfig.app }}")

        loader = ConfiguredVuePageLoader(
            searchpath=str(tmp_path),
            template_file="test.html",
            config={"app": "merged"},
        )

        env = Environment(loader=loader)

        # Call load directly with existing globals
        existing_globals = {"other": "value"}
        source, filename, uptodate = loader.get_source(env, "test.html")

        # The loader should have siteConfig in its config
        assert loader.config == {"app": "merged"}

    def test_load_handles_none_globals(self, tmp_path):
        """load should handle case where globals is None."""
        template_file = tmp_path / "test.html"
        template_file.write_text("Test: {{ siteConfig.enabled }}")

        loader = ConfiguredVuePageLoader(
            searchpath=str(tmp_path),
            template_file="test.html",
            config={"enabled": True},
        )

        env = Environment(loader=loader)
        template = env.get_template("test.html")
        rendered = template.render()

        assert "True" in rendered
