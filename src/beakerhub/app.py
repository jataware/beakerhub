import os.path
from pathlib import Path

import traitlets
from jupyterhub.app import JupyterHub
from traitlets import Dict, Instance, Type, Unicode, default

# Import orm tables so that they can be added.
import beakerhub.orm # type: ignore
from beakerhub import __version__
from beakerhub.orm import EncryptedString
from beakerhub.auth.cognito import  CognitoBotoAuthenticator
from beakerhub.handlers import get_override_handlers, HierarchicalStaticHandler, VueSPAHandler
from beakerhub.api_handlers import handlers as api_handlers
from beakerhub.admin_handlers import admin_handlers
from beakerhub.services.dashboard.base import BaseDashboardService
from beakerhub.services.dashboard.aws_ecs_dashboard import AwsEcsDashboardService
from beakerhub.services.dashboard.handlers import handlers as dashboard_handlers
from beakerhub.services.dashboard.kubernetes_dashboard import (
    KubernetesDashboardService,
)
from beakerhub.services.task.base import BaseTaskRunnerService
from beakerhub.services.task.aws_ecs_task_runner import AwsEcsTaskRunnerService
from beakerhub.services.task.handlers import handlers as task_handlers
from beakerhub.services.task.kubernetes_task_runner import (
    KubernetesTaskRunnerService,
)


PACKAGE_ROOT = Path(__file__).resolve().parent


class BeakerHub(JupyterHub):
    name = "beakerhub"
    version = __version__

    description = "Beakerhub version of: \n" + str(JupyterHub.description)
    example = "Beakerhub version of: \n" + str(JupyterHub.examples)

    task_runner_class = Type(
        KubernetesTaskRunnerService,
        klass=BaseTaskRunnerService,
        config=True,
        help="Task-runner service used for background workloads.",
    )
    task_runner = Instance(
        BaseTaskRunnerService,
        allow_none=False,
    )
    dashboard_service_class = Type(
        KubernetesDashboardService,
        klass=BaseDashboardService,
        config=True,
        help="Service used to collect runtime dashboard data and session logs.",
    )
    dashboard_service = Instance(
        BaseDashboardService,
        allow_none=False,
    )

    enable_idle_session_culling = traitlets.Bool(
        default_value=True,
        config=True,
        help="If enabled, culls sessions."
    )

    # ---- Secret vault ----
    vault_encryption_key = Unicode(
        "",
        config=True,
        help="Fernet-compatible encryption key for the secret vault. "
             "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
    )

    vault_encryption_key_file = Unicode(
        'beakerhub_vault_secret', help="""File in which to store the vault secret."""
    ).tag(config=True)

    # Configurable path to Vue build output
    beaker_static_path = Unicode(
        str(PACKAGE_ROOT / "ui"),
        config=True,
        help="Path to the built Vue application static files"
    )

    footer = Dict(
        key_trait=Unicode(),
        value_trait=Unicode(),
        default_value={},
        config=True,
        help="Footer branding and link overrides exposed to the web UI.",
    )

    tornado_settings = {
        # Override base handler to allow split static handling.
        # Will check beakerhub static first, then jupyterhub's static.
        "static_handler_class": HierarchicalStaticHandler,
        "default_handler_class": VueSPAHandler
    }

    @default("base_url")
    def _default_base_url(self):
        return "/"

    @default("hub_prefix")
    def _default_hub_prefix(self):
        return self.base_url

    @default("authenticator_class")
    def _default_authenticator_class(self):
        return CognitoBotoAuthenticator

    @default("spawner_class")
    def _default_spawner_class(self):
        from beakerhub.services.spawner.kubernetes_spawner import BeakerKubeSpawner
        return BeakerKubeSpawner

    @default("task_runner")
    def _default_task_runner(self):
        return self.task_runner_class(parent=self)

    @default("dashboard_service")
    def _default_dashboard_service(self):
        return self.dashboard_service_class(parent=self)

    def update_config(self, config):
        """Refresh services created before JupyterHub loads its config file.

        Child ``Configurable`` instances inherit their parent's config only at
        construction time. JupyterHub loads ``beakerhub_config.py`` after the
        application is constructed, so an already-created task runner would
        otherwise retain its trait defaults.
        """
        super().update_config(config)
        if "task_runner" in self._trait_values:
            self.task_runner.update_config(config)
        if "dashboard_service" in self._trait_values:
            self.dashboard_service.update_config(config)

    @default("config_file")
    def _default_config_file(self):
        return "beakerhub_config.py"

    @default("allow_named_servers")
    def _default_allowed_named_servers(self):
        return True

    @default('users')
    def _users_default(self):
        from beakerhub.auth.user import BeakerhubUserDict
        assert self.tornado_settings
        return BeakerhubUserDict(db_factory=lambda: self.db, settings=self.tornado_settings)

    @default('db_url')
    def _default_db_url(self):
        return 'sqlite:///beakerhub.sqlite'

    @default('cookie_secret_file')
    def _default_cookie_secret_file(self):
        return 'beakerhub_cookie_secret'

    @default("classes")
    def _default_classes(self):
        return [
            self.__class__,
            BaseTaskRunnerService,
            KubernetesTaskRunnerService,
            AwsEcsTaskRunnerService,
            BaseDashboardService,
            KubernetesDashboardService,
            AwsEcsDashboardService,
        ]

    def init_db(self):
        if self.vault_encryption_key:
            EncryptedString.set_key(self.vault_encryption_key)
        else:
            self.log.warning(
                "vault_encryption_key is not set. "
                "Encrypted secret storage will not be available."
            )
        return super().init_db()

    def init_handlers(self):
        """Initialize handlers, including custom Vue SPA handlers."""
        super().init_handlers()

        override_handlers = (
            get_override_handlers(self.base_url, self.beaker_static_path)
            + api_handlers
            + admin_handlers
            + task_handlers
            + dashboard_handlers
        )
        overridden_paths = {handler[0] for handler in override_handlers}
        overridden_paths.add(r'(.*)')  # 404NotFound path
        overridden_paths.update({path for path, *args in self.handlers if path.startswith("/admin")})
        self.handlers = override_handlers + [handler for handler in self.handlers if handler[0] not in overridden_paths]
        self.handlers.append((r'(.*)', VueSPAHandler))

    def init_secrets(self):
        # Due to expectations in lower level code, stash the vault_encryption_key as
        # an env variable where it will be found.
        os.environ.setdefault("JUPYTERHUB_CRYPT_KEY", self.vault_encryption_key)
        super().init_secrets()


    async def init_role_creation(self):
        """Register the role that grants the idle culler its permissions.

        This runs before `init_services`, but roles are only bound to services
        later, in `init_role_assignment`, so the ordering is safe.
        """
        if self.enable_idle_session_culling:
            from beakerhub.services.periodic_tasks.idle_culler import SERVICE_ROLE
            self.load_roles = [*self.load_roles, SERVICE_ROLE]
        await super().init_role_creation()

    def init_services(self):
        if self.enable_idle_session_culling:
            from beakerhub.services.periodic_tasks.idle_culler import SERVICE_DEFINITION
            # Copy the definition. Mutating the module-level dict would make
            # this method unsafe to call more than once.
            service = dict(SERVICE_DEFINITION)
            # Give the service the Hub's own config file so that it reads the
            # same `c.IdleSessionCuller.*` settings. The path must be absolute,
            # because the service does not inherit the Hub's working directory
            # in every deployment.
            service["command"] = [
                *service["command"],
                f"--config={os.path.abspath(self.config_file)}",
            ]
            self.services = [*self.services, service]
        super().init_services()


main = BeakerHub.launch_instance

if __name__ == "__main__":
    # Reimport any class(es) defined above directly because __main__.BeakerHub is different than beakerhub.BeakerHub
    from beakerhub.app import BeakerHub
    BeakerHub.launch_instance()
