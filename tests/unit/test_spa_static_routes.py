"""Tests for the SPA's public static asset routes."""
import re

from tornado.web import StaticFileHandler

from beakerhub.handlers import get_override_handlers


def test_public_assets_use_ui_static_directory(tmp_path):
    handlers = get_override_handlers(str(tmp_path))
    public_route = next(handler for handler in handlers if handler[0] == r"/(favicon\.ico|videos/.*)")

    assert public_route[1] is StaticFileHandler
    assert public_route[2] == {"path": str(tmp_path)}
    assert re.fullmatch(public_route[0], "/favicon.ico")
    assert re.fullmatch(public_route[0], "/videos/beaker_demo.mp4")
