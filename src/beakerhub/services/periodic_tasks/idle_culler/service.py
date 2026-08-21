import asyncio
import datetime
import json
from functools import partial
from urllib.parse import quote

import traitlets
from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPResponse

from beakerhub.services import Seconds, ServiceTask


class IdleSessionCuller(ServiceTask):
    """Shut down user servers that have been idle for longer than a limit."""

    idle_limit = Seconds(
        config=True,
        help="Time a server can be idle before it is culled. Either an integer "
             "number of seconds or a datetime.timedelta instance.",
    )
    shutdown_timeout = Seconds(
        config=True,
        help="Time to wait for a cull to complete. After this, the shutdown is "
             "treated as stuck and the server becomes a candidate again.",
    )
    remove_stopped_servers = traitlets.Bool(
        True,
        config=True,
        help="If True, delete the spawner orm record in the spawner table when "
             "stopping the server. If false, it leaves a record in the spawner "
             "table allowing the session to be resumed by starting a new server "
             "with the same session id and user options."
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._in_progress_shutdowns: dict[str, datetime.datetime] = {}
        self._background_tasks: set[asyncio.Task] = set()

    @traitlets.default("idle_limit")
    def _default_idle_limit(self):
        return datetime.timedelta(hours=48)

    @traitlets.default("interval")
    def _default_interval(self):
        return datetime.timedelta(minutes=5)

    @traitlets.default("shutdown_timeout")
    def _default_shutdown_timeout(self):
        return datetime.timedelta(minutes=5)

    @staticmethod
    def _now() -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)

    @staticmethod
    def _error_detail(response: HTTPResponse) -> str:
        """Return a readable body from a failed response.

        The body is not always JSON. A proxy or an unhandled server error can
        return HTML, so decode as text rather than parsing.
        """
        if not response.body:
            return response.reason or ""
        return response.body.decode("utf-8", errors="replace")[:500]

    async def _api_request(self, path: str, method: str = "GET", body=None) -> HTTPResponse:
        """Make an authenticated request against the Hub API."""
        headers = {"Authorization": f"token {self.auth.api_token}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = HTTPRequest(
            url=f"{self.auth.api_url}{path}",
            method=method,
            headers=headers,
            body=json.dumps(body) if body is not None else None,
            # Tornado rejects a body on DELETE unless this is set.
            allow_nonstandard_methods=True,
        )
        return await AsyncHTTPClient().fetch(request, raise_error=False)

    def _is_cullable(self, server: dict) -> bool:
        if server["name"] in self._in_progress_shutdowns:
            return False

        # Use the start time when the server has recorded no activity.
        timestamp = server.get("last_activity") or server.get("started")
        if not timestamp:
            self.log.warning(
                "Server %r has no activity time and no start time. Skipping it.",
                server["name"],
            )
            return False

        last_activity = datetime.datetime.fromisoformat(timestamp)
        return last_activity < self._now() - self.idle_limit

    def _expire_stale_shutdowns(self):
        """Forget culls that did not complete, so their servers are retried."""
        now = self._now()
        for server_name, started in list(self._in_progress_shutdowns.items()):
            if now - started > self.shutdown_timeout:
                self.log.error(
                    "The cull of server %r did not complete in %s. It could be "
                    "stuck. The server becomes a candidate again.",
                    server_name,
                    self.shutdown_timeout,
                )
                del self._in_progress_shutdowns[server_name]

    async def collect_idle_servers(self) -> list[dict]:
        response = await self._api_request("/beakerhub/admin/sessions")
        if response.error:
            self.log.error(
                "Could not list sessions: HTTP %s %s",
                response.code,
                self._error_detail(response),
            )
            return []
        all_servers = json.loads(response.body)
        return [server for server in all_servers if self._is_cullable(server)]

    async def shutdown_idle_server(self, server: dict):
        server_name = server["name"]
        user_name = server["user_name"]
        self.log.info("Culling server %r of user %r.", server_name, user_name)

        path = (
            f"/users/{quote(user_name, safe='')}"
            f"/servers/{quote(server_name, safe='')}"
        )
        response = await self._api_request(
            path,
            method="DELETE",
            body={"remove": self.remove_stopped_servers},
        )
        if response.error:
            self.log.error(
                "Could not cull server %r: HTTP %s %s",
                server_name,
                response.code,
                self._error_detail(response),
            )
        else:
            self.log.info("Server %r was culled.", server_name)

    def _resolve_shutdown(self, server_name: str, task: asyncio.Task):
        """Release the in-progress record when a cull finishes, or fails."""
        self._background_tasks.discard(task)
        self._in_progress_shutdowns.pop(server_name, None)

        if task.cancelled():
            self.log.warning("The cull of server %r was cancelled.", server_name)
            return
        error = task.exception()
        if error is not None:
            self.log.error("Error while culling server %r: %s", server_name, error)

    async def task(self):
        self._expire_stale_shutdowns()

        idle_servers = await self.collect_idle_servers()
        if not idle_servers:
            self.log.debug("No servers need to be culled.")
            return

        for server in idle_servers:
            server_name = server["name"]
            # Record before the coroutine is scheduled, so that the next run of
            # the task sees the server as in progress and does not cull it twice.
            self._in_progress_shutdowns[server_name] = self._now()
            shutdown = asyncio.create_task(self.shutdown_idle_server(server))
            self._background_tasks.add(shutdown)
            shutdown.add_done_callback(partial(self._resolve_shutdown, server_name))


if __name__ == "__main__":
    IdleSessionCuller.launch_instance()
