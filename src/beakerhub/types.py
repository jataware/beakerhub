"""Shared type definitions for beakerhub."""
from __future__ import annotations

from typing import Any, Protocol

from tornado.web import RequestHandler


# Handler tuple: (route_pattern, handler_class) or (route_pattern, handler_class, kwargs)
HandlerTuple = (
    tuple[str, type[RequestHandler]]
    | tuple[str, type[RequestHandler], dict[str, Any]]
)


class OverrideHandlerProvider(Protocol):
    """Protocol for get_override_handlers functions in handlers.py and api_handlers.py."""

    def __call__(self, base_url: str = '/', ui_path: str = "./ui") -> list[HandlerTuple]: ...
