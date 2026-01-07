"""Custom Tornado handlers for serving Vue SPA."""
import json
import logging
import os


from tornado import web
from jupyterhub.handlers import BaseHandler, static
from jupyterhub.user import User
from jupyterhub import _xsrf_utils

from beakerhub.auth.handlers import LoginHandler, LogoutHandler, SignupHandler, ConfirmSignupHandler, ForgotPasswordHandler, ConfirmPasswordHandler
from beakerhub.types import HandlerTuple


DEFAULT_FOOTER_CONFIG = {
    "productName": "BeakerHub",
    "tagline": "Your AI-powered co-scientist.",
    "documentationUrl": "https://jataware.github.io/beaker-notebook",
    "githubUrl": "https://github.com/jataware/beaker-notebook",
    "contactEmail": "contact@beakerhub.com",
    "copyrightYears": "2024-present",
    "copyrightHolder": "Jataware Corp",
    "copyrightUrl": "https://jataware.com",
}


def get_footer_config(app: object) -> dict[str, str]:
    """Return footer defaults merged with deployment-specific overrides."""
    return {
        **DEFAULT_FOOTER_CONFIG,
        **getattr(app, "footer", {}),
    }


class VueSPAHandler(BaseHandler):
    """
    Handler that serves the Vue SPA index.html for client-side routing.

    This allows Vue Router to handle all routing for the SPA while
    JupyterHub handles authentication and API endpoints.
    """

    # @web.authenticated
    async def get(self, path=None, *args, **kwargs):
        """Serve the Vue index.html with injected configuration."""
        # Get the path to the built Vue app
        static_path = str(self.app.beaker_static_path)
        index_path = os.path.join(static_path, 'index.html')

        # Read the index.html
        with open(index_path, 'r') as f:
            html = f.read()

        # Build configuration object
        config = {
            'pathPrefix': self.hub.base_url,
            'username': self.current_user.name if self.current_user else None,
            '_xsrf': self.xsrf_token.decode(),
            'footer': get_footer_config(self.app),
        }

        # Replace the Jinja2 placeholder with actual JSON
        # The index.html has: <script id="site-config" type="application/json">{{ siteConfig }}</script>
        config_json = json.dumps(config).replace("</", "<\\/")
        # html = html.replace('{{ siteConfig }}', config_json)
        html = html.replace("</head>", f'<script id="site-config" type="application/json">{config_json}</script>\n</head>')

        self.set_header('Content-Type', 'text/html')
        self.write(html)


class HierarchicalStaticHandler(static.CacheControlStaticFilesHandler):
    beaker_static_path: str|None

    @property
    def log(self) -> logging.Logger:
        return self.settings.get("log", logging.getLogger("BeakerHub"))

    def initialize(self, path, default_filename = None):
        super().initialize(path, default_filename)
        app = self.settings.get("app", None)
        self.beaker_static_path = getattr(app, "beaker_static_path", None)

    async def get(self, path, include_body = True):
        default_root = self.root
        try:
            if self.beaker_static_path:
                self.root = self.beaker_static_path
                await super().get(path, include_body)
                return
        except Exception as e:
            self.log.debug(f"{path} not found in {self.beaker_static_path}. Falling back to check in {default_root}")
            pass
        finally:
            self.root = default_root
        return await super().get(path, include_body)


def get_override_handlers(base_url: str = '/', ui_path: str = "./ui") -> list[HandlerTuple]:
    """
    Return list of extra handlers to register with JupyterHub, overriding any existing rules with identical match strings.

    Args:
        base_url: The hub's base URL (default: '/' for root deployment)
                  Can be overridden to '/hub/' or other prefix in config

    Returns:
        List of (route_pattern, handler_class) tuples
    """

    handlers = [
        (rf"{base_url}", VueSPAHandler),
        (rf"{base_url}(beakerhub/static/.*)", web.StaticFileHandler, {"path": ui_path}),
        (r'/api/auth/login', LoginHandler),
        (r'/api/auth/logout', LogoutHandler),
    ]

    routefile_path = os.path.join(ui_path, "routes.json")
    if os.path.isfile(routefile_path):
        with open(routefile_path) as route_file:
            routes  = json.load(route_file)
        if isinstance(routes, dict):
            route_options = list(routes.keys())
        route_regex = rf'{base_url}({"|".join(opt.strip("/") for opt in route_options if opt.strip("/"))})/?'
        handlers.append((route_regex, VueSPAHandler))

    return handlers
