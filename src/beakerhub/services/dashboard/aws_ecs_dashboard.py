"""AWS ECS implementation skeleton for the dashboard service."""

from typing import Any

from beakerhub.services.dashboard.base import BaseDashboardService


class AwsEcsDashboardService(BaseDashboardService):
    """Provide AWS ECS runtime data to the BeakerHub dashboard."""

    def get_dashboard(self) -> dict[str, Any]:
        raise NotImplementedError("AWS ECS dashboard data is not implemented")

    def get_session_logs(
        self,
        session_id: str,
        container: str,
        tail_lines: int,
    ) -> dict[str, Any]:
        raise NotImplementedError("AWS ECS session logs are not implemented")
