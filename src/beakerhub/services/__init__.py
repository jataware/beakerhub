import abc
import datetime
import logging
import os

import traitlets
from jupyterhub.services.auth import HubAuth
from tornado.ioloop import IOLoop, PeriodicCallback
from traitlets.config import Application


class ABCMetaHasTraits(abc.ABCMeta, traitlets.MetaHasTraits):
    """Metaclass that combines ``abc.ABCMeta`` with traitlets' ``MetaHasTraits``.

    Both metaclasses derive directly from ``type``, so a class that inherits
    from an ABC and from a ``HasTraits`` subclass must name a metaclass that
    derives from both.
    """


class Seconds(traitlets.Union):
    """A ``datetime.timedelta`` trait that also accepts an integer of seconds.

    Config files and command-line arguments usually supply a plain number, so
    the integer form is coerced to a ``timedelta`` on assignment.
    """

    def __init__(self, **kwargs):
        super().__init__(
            trait_types=[
                traitlets.Instance(klass=datetime.timedelta),
                traitlets.Integer(),
            ],
            **kwargs,
        )

    def validate(self, obj, value):
        value = super().validate(obj, value)
        if isinstance(value, int):
            return datetime.timedelta(seconds=value)
        return value


class ServiceTask(Application, PeriodicCallback, metaclass=ABCMetaHasTraits):
    """A JupyterHub managed service that runs a coroutine on a fixed interval.

    Subclasses implement :meth:`task`. The Hub starts the service as a
    subprocess and passes its own config file with ``--config``, so the service
    reads the same ``c.<ClassName>.*`` settings that configure the Hub.
    """

    # ``traitlets.Application`` supplies only ``--log-level``. The Hub's own
    # ``--config`` alias belongs to JupyterHub, so declare an equivalent here.
    aliases = {
        **Application.aliases,
        "f": "ServiceTask.config_file",
        "config": "ServiceTask.config_file",
    }

    config_file = traitlets.Unicode(
        "",
        config=True,
        help="Path of a config file to load. The Hub passes its own config file here.",
    )
    auth = traitlets.Instance(
        klass=HubAuth,
        config=True,
        help="Authentication instance used to talk to the Hub API.",
    )
    interval = Seconds(
        config=True,
        help="Time between executions of the task. Either an integer number of "
             "seconds or a datetime.timedelta instance.",
    )

    @traitlets.default("auth")
    def _default_auth(self):
        return HubAuth()

    @traitlets.default("name")
    def _default_name(self):
        return self.__class__.__name__

    @traitlets.default("log_level")
    def _default_log_level(self):
        # Application defaults to WARNING, which hides the record of what the
        # task did on each run.
        return logging.INFO

    def initialize(self, argv=None):
        """Parse the command line, load the config file, then arm the timer.

        ``PeriodicCallback`` is initialized here and not in ``__init__`` so that
        it reads ``interval`` after the configuration has been applied.
        """
        super().initialize(argv)
        if self.config_file:
            config_path = os.path.abspath(self.config_file)
            if not os.path.isfile(config_path):
                # traitlets only reports a missing file at DEBUG level. Without
                # this warning the service starts on its defaults and gives no
                # sign that its configuration was never applied.
                self.log.warning(
                    "Config file %s does not exist. %s uses its default settings.",
                    config_path,
                    self.name,
                )
            self.load_config_file(
                os.path.basename(config_path),
                path=[os.path.dirname(config_path)],
            )
        PeriodicCallback.__init__(
            self,
            callback=self.task,
            callback_time=self.interval,
        )

    def start(self):
        """Run the task on its interval until the process is interrupted.

        This replaces ``Application.start`` so that ``launch_instance`` runs the
        event loop.
        """
        self.log.info("Starting %s. The task runs every %s.", self.name, self.interval)
        loop = IOLoop.current()
        PeriodicCallback.start(self)
        try:
            loop.start()
        except KeyboardInterrupt:
            self.log.info("Interrupted. Stopping %s.", self.name)
        finally:
            PeriodicCallback.stop(self)

    @abc.abstractmethod
    async def task(self):
        """Do the periodic work. Implemented by subclasses."""
        ...
