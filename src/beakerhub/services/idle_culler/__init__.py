import sys

SERVICE_NAME: str = "beakerhub-idle-culler"

SERVICE_DEFINITION: dict = {
    "name": SERVICE_NAME,
    "command": [
        sys.executable,
        "-m",
        "beakerhub.services.idle_culler.idle_culler_service",
    ],
}

# `admin:servers` expands to `delete:servers` and `read:users:name`, which is
# everything the culler needs. It replaces `"admin": True` on the service, which
# would have granted every scope.
SERVICE_ROLE: dict = {
    "name": "beakerhub-idle-culler",
    "description": "Lets the idle culler list and shut down user servers.",
    "scopes": ["admin:servers"],
    "services": [SERVICE_NAME],
}
