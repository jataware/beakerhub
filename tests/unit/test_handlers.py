# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""Tests for the Vue application handlers."""

from types import SimpleNamespace

from beakerhub.handlers import DEFAULT_FOOTER_CONFIG, get_footer_config


def test_get_footer_config_returns_defaults():
    app = SimpleNamespace(footer={})

    assert get_footer_config(app) == DEFAULT_FOOTER_CONFIG
    assert get_footer_config(app) is not DEFAULT_FOOTER_CONFIG


def test_get_footer_config_merges_partial_overrides():
    app = SimpleNamespace(
        footer={
            "contactEmail": "help@example.com",
            "documentationUrl": "",
        }
    )

    footer = get_footer_config(app)

    assert footer["contactEmail"] == "help@example.com"
    assert footer["documentationUrl"] == ""
    assert footer["githubUrl"] == DEFAULT_FOOTER_CONFIG["githubUrl"]
