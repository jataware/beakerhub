"""Base contract for dashboard data services."""

from typing import Any

from traitlets.config import LoggingConfigurable


class DashboardServiceError(Exception):
    """An error that a dashboard handler can expose as an HTTP response."""

    def __init__(self, status_code: int, reason: str):
        super().__init__(reason)
        self.status_code = status_code
        self.reason = reason


class BaseDashboardService(LoggingConfigurable):
    """Provide runtime inventory and session logs to dashboard handlers."""

    def get_dashboard(self) -> dict[str, Any]:
        """Return normalized runtime inventory for the admin dashboard.

        Implementations return ``available`` and, when available, ``runtime``,
        ``summary``, ``workloads``, ``resources``, and ``alerts``. The values
        describe container-runtime concepts rather than provider API objects.
        """
        raise NotImplementedError

    def get_session_logs(
        self,
        session_id: str,
        container: str,
        tail_lines: int,
    ) -> dict[str, Any]:
        """Return logs for a session runtime."""
        raise NotImplementedError
