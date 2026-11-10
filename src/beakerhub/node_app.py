import json
import os
from urllib.parse import quote

from jupyterhub.utils import url_path_join
import requests
import traitlets

from beaker_notebook.app.base import BaseBeakerApp
from beaker_notebook.services.kernel import BeakerKernelManager, BeakerKernelMappingManager

class BeakerhubNodeKernelManager(BeakerKernelManager):

    def write_connection_file(self, **kwargs):
        app: BeakerNodeApp = self.app
        context_info = app.server_options.get("contextOptions", None)
        if context_info:
            context_config = kwargs.setdefault("context", {})
            context_name = app.server_options.get("contextSlug", None)
            if isinstance(context_name, str):
                context_name = context_name.split(":", 1)[-1]
            context_config["default_context"] = context_name
            context_config["default_context_payload"] = context_info
        return super().write_connection_file(**kwargs)

class BeakerhubNodeMappingKernelManager(BeakerKernelMappingManager):
    kernel_manager_class = "beakerhub.node_app.BeakerhubNodeKernelManager"

class BeakerNodeApp(BaseBeakerApp):
    defaults = {
        "log_requests": True,
        "ip": "0.0.0.0",
        "allow_root": True,
        "kernel_manager_class": BeakerhubNodeMappingKernelManager,
    }

    hub_url = traitlets.Unicode(
        config=True
    )
    hub_api_url = traitlets.Unicode(
        config=True
    )
    hub_api_token = traitlets.Unicode(
        config=True
    )
    server_id = traitlets.Unicode(
        config=True
    )

    server_options = traitlets.Dict(default_value={})

    @traitlets.default("hub_url")
    def _default_hub_url(self):
        return os.environ.get("JUPYTERHUB_SERVICE_URL", None)

    @traitlets.default("hub_api_url")
    def _default_hub_api_url(self):
        return os.environ.get("JUPYTERHUB_API_URL", None)

    @traitlets.default("hub_api_token")
    def _default_hub_api_token(self):
        return os.environ.get("JUPYTERHUB_API_TOKEN", None)

    @traitlets.default("server_id")
    def _default_server_id(self):
        return os.environ.get("JUPYTERHUB_SERVER_NAME", None)

    def _hub_request(self, api_path: str, decode_json: bool = True):
        response = requests.get(
            url_path_join(self.hub_api_url, api_path),
            headers={"Authorization": f"Bearer {self.hub_api_token}"}
        )
        response.raise_for_status()
        if decode_json:
            return response.json()
        else:
            return response


    def initialize(self, argv=None, find_extensions=False, new_httpserver=True, starter_extension=None, **kwargs):
        super().initialize(argv, find_extensions, new_httpserver, starter_extension, **kwargs)
        server_id = quote(self.server_id, safe="")
        server_options = self._hub_request(f"beakerhub/server/{server_id}/info")
        self.log.warning(server_options)
        if server_options:
            self.server_options = server_options


if __name__ == "__main__":
    BeakerNodeApp.launch_instance()

