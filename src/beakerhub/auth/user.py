import asyncio
from uuid import uuid4
from urllib.parse import urlparse, urlunparse

from jupyterhub import orm, roles, scopes
from jupyterhub.user import User, UserDict
from jupyterhub.objects import Server
from jupyterhub.utils import ( url_path_join, maybe_future,
    AnyTimeoutError,
    _strict_dns_safe,
    make_ssl_context,
    maybe_future,
    subdomain_hook_legacy,
    url_escape_path,
    url_path_join,
    utcnow,
)


class BeakerhubUserDict(UserDict):
    # Return Beakerhub Users instead of vanilla users
    def from_orm(self, orm_user):
        return BeakerhubUser(orm_user, self.settings)

    def __getitem__(self, key):
        # Ensure we are generating users with the correct class
        if isinstance(key, orm.User) and key.id not in self:
            user = self[key.id] = self.from_orm(key)
            return user
        return super().__getitem__(key)


class BeakerhubUser(User):
    def __init__(self, orm_user, settings=None, db=None):
        super().__init__(orm_user, settings, db)

        self.base_url = url_path_join(self.settings.get('base_url', '/'))
        self.prefix = self.base_url

    def _new_spawner(self, server_name, spawner_class=None, **kwargs):
        # Add extra values available now to kwargs so we can use them later when they would otherwise not be
        # avaialable.
        kwargs.setdefault("subdomain_host", self.settings.get("subdomain_host", None))
        kwargs.setdefault("domain", self.settings.get("domain", None))
        return super()._new_spawner(server_name, spawner_class, **kwargs)

    def get_spawner(self, server_name="", replace_failed=False):
        return super().get_spawner(server_name, replace_failed)

    @property
    def host(self) -> str:
        if (subdomain_host := self.settings.get('subdomain_host', None)):
            return subdomain_host
        elif (public_url := self.settings.get("public_url", None)):
            # no subdomain, use public host url without path
            return urlunparse(public_url._replace(path=""))
        else:
            return ""

    @property
    def url(self):
        if self.settings.get("subdomain_host"):
            return f"{self.host}{self.base_url}"
        else:
            return self.base_url

    def server_url(self, server_name='') -> str:
        if not server_name:
            raise ValueError("All beaker servers must have a server name")
        if self.settings.get('subdomain_host'):
            parsed = urlparse(self.url)
            h = f"{parsed.scheme}://{server_name}.{parsed.hostname}"
            if parsed.port:
                h = f"{h}:{parsed.port}"
            return h
        else:
            return super().server_url(server_name=server_name)

    @property
    def running(self):
        return any((spawner.ready for spawner in self.spawners.values()))

    @property
    def spawner(self):
        return None

    @spawner.setter
    def spawner(self, spawner):
        return None

    # TODO: It stinks that we have to duplicate this entire function just to change how the urls are generated.
    # Hopefully this can be fixed upstream so we can simplify.
    async def spawn(self, server_name='', options=None, handler=None):
        """Start the user's spawner

        depending from the value of JupyterHub.allow_named_servers

        if False:
        JupyterHub expects only one single-server per user
        url of the server will be /user/:name

        if True:
        JupyterHub expects more than one single-server per user
        url of the server will be /user/:name/:server_name
        """
        db = self.db

        if handler:
            await self.refresh_auth(handler)

        base_url = "/"

        orm_server = orm.Server(base_url=base_url)
        db.add(orm_server)
        note = f"Server at {base_url}"
        db.commit()

        spawner = self.get_spawner(server_name, replace_failed=True)
        spawner.server = server = Server(orm_server=orm_server)
        assert spawner.orm_spawner.server is orm_server

        requested_scopes = spawner.server_token_scopes
        if callable(requested_scopes):
            requested_scopes = await maybe_future(requested_scopes(spawner))
        if not requested_scopes:
            # nothing requested, default to 'server' role
            requested_scopes = orm.Role.find(db, "server").scopes
        requested_scopes = set(requested_scopes)
        # resolve !server filter, which won't resolve elsewhere,
        # because this token is not owned by the server's own oauth client
        server_filter = f"={self.name}/{server_name}"
        requested_scopes = {
            scope + server_filter if scope.endswith("!server") else scope
            for scope in requested_scopes
        }
        # ensure activity scope is requested, since activity doesn't work without
        activity_scope = "users:activity!user"
        if not {activity_scope, "users:activity", "inherit"}.intersection(
            requested_scopes
        ):
            self.log.warning(
                f"Adding required scope {activity_scope} to server token, missing from Spawner.server_token_scopes. Please make sure to add it!"
            )
            requested_scopes |= {activity_scope}

        have_scopes = roles.roles_to_scopes(roles.get_roles_for(self.orm_user))
        have_scopes |= {"inherit"}
        jupyterhub_client = (
            db.query(orm.OAuthClient)
            .filter_by(
                identifier="jupyterhub",
            )
            .one()
        )

        resolved_scopes, excluded_scopes = scopes._resolve_requested_scopes(
            requested_scopes, have_scopes, self.orm_user, jupyterhub_client, db
        )
        if excluded_scopes:
            # what level should this be?
            # for admins-get-more use case, this is going to happen for most users
            # but for misconfiguration, folks will want to know!
            self.log.debug(
                "Not assigning requested scopes for %s: requested=%s, assigned=%s, excluded=%s",
                spawner._log_name,
                requested_scopes,
                resolved_scopes,
                excluded_scopes,
            )

        api_token = self.new_api_token(note=note, scopes=resolved_scopes)

        # pass requesting handler to the spawner
        # e.g. for processing GET params
        spawner.handler = handler

        # Passing user_options to the spawner
        if options is None:
            # options unspecified, load from db which should have the previous value
            options = spawner.orm_spawner.user_options or {}
        else:
            # options specified, save for use as future defaults
            spawner.orm_spawner.user_options = options
            db.commit()

        spawner.user_options = options
        # we are starting a new server, make sure it doesn't restore state
        spawner.clear_state()

        # create API and OAuth tokens
        spawner.api_token = api_token
        spawner.admin_access = self.settings.get('admin_access', False)
        client_id = spawner.oauth_client_id
        oauth_provider = self.settings.get('oauth_provider')
        if oauth_provider:
            allowed_scopes = await spawner._get_oauth_client_allowed_scopes()
            oauth_client = oauth_provider.add_client(
                client_id,
                api_token,
                url_path_join(base_url, 'oauth_callback'),
                allowed_scopes=allowed_scopes,
                description=f"Server at {url_path_join(base_url, '/')}",
            )
            spawner.orm_spawner.oauth_client = oauth_client
        db.commit()

        # trigger pre-spawn hook on authenticator
        authenticator = self.authenticator
        try:
            spawner._start_pending = True

            if authenticator:
                # pre_spawn_start can throw errors that can lead to a redirect loop
                # if left uncaught (see https://github.com/jupyterhub/jupyterhub/issues/2683)
                await maybe_future(authenticator.pre_spawn_start(self, spawner))

            # trigger auth_state hook
            auth_state = await self.get_auth_state()
            await spawner.run_auth_state_hook(auth_state)

            # update spawner start time, and activity for both spawner and user
            self.last_activity = spawner.orm_spawner.started = (
                spawner.orm_spawner.last_activity
            ) = utcnow(with_tz=False)
            db.commit()
            # wait for spawner.start to return
            # run optional preparation work to bootstrap the notebook
            await spawner.apply_group_overrides()
            await spawner._run_apply_user_options(spawner.user_options)
            await maybe_future(spawner.run_pre_spawn_hook())
            if self.settings.get('internal_ssl'):
                self.log.debug("Creating internal SSL certs for %s", spawner._log_name)
                hub_paths = await maybe_future(spawner.create_certs())
                spawner.cert_paths = await maybe_future(spawner.move_certs(hub_paths))
            self.log.debug("Calling Spawner.start for %s", spawner._log_name)
            f = maybe_future(spawner.start())
            # commit any changes in spawner.start (always commit db changes before await)
            db.commit()
            # gen.with_timeout protects waited-for tasks from cancellation,
            # whereas wait_for cancels tasks that don't finish within timeout.
            # we want this task to halt if it doesn't return in the time limit.
            await asyncio.wait_for(f, timeout=spawner.start_timeout)
            url = f.result()
            if url:
                # get url from return value of start()
                if not isinstance(url, str):
                    # older Spawners return (ip, port)
                    proto = 'https' if self.settings['internal_ssl'] else 'http'
                    ip, port = url
                    # check if spawner returned an IPv6 address
                    if ':' in ip:
                        # ipv6 needs [::] in url
                        ip = f'[{ip}]'
                    url = f'{proto}://{ip}:{int(port)}'
                urlinfo = urlparse(url)
                server.proto = urlinfo.scheme
                server.ip = urlinfo.hostname
                port = urlinfo.port
                if not port:
                    if urlinfo.scheme == 'https':
                        port = 443
                    else:
                        port = 80
                server.port = port
                db.commit()
            else:
                # prior to 0.7, spawners had to store this info in user.server themselves.
                # Handle < 0.7 behavior with a warning, assuming info was stored in db by the Spawner.
                self.log.warning(
                    "DEPRECATION: Spawner.start should return a url or (ip, port) tuple in JupyterHub >= 0.9"
                )
            if spawner.api_token and spawner.api_token != api_token:
                # Spawner re-used an API token, discard the unused api_token
                orm_token = orm.APIToken.find(self.db, api_token)
                if orm_token is not None:
                    self.db.delete(orm_token)
                    self.db.commit()
                # check if the re-used API token is valid
                found = orm.APIToken.find(self.db, spawner.api_token)
                if found:
                    if found.user is not self.orm_user:
                        self.log.error(
                            "%s's server is using %s's token! Revoking this token.",
                            self.name,
                            (found.user or found.service).name,
                        )
                        self.db.delete(found)
                        self.db.commit()
                        raise ValueError(f"Invalid token for {self.name}!")
                else:
                    # Spawner.api_token has changed, but isn't in the db.
                    # What happened? Maybe something unclean in a resumed container.
                    self.log.warning(
                        "%s's server specified its own API token that's not in the database",
                        self.name,
                    )
                    # use generated=False because we don't trust this token
                    # to have been generated properly
                    self.new_api_token(
                        spawner.api_token,
                        generated=False,
                        note=f"retrieved from spawner {server_name}",
                        scopes=resolved_scopes,
                    )
                # update OAuth client secret with updated API token
                if oauth_provider:
                    oauth_provider.add_client(
                        client_id,
                        spawner.api_token,
                        url_path_join(
                            base_url, 'oauth_callback'
                        ),
                    )
                    db.commit()

        except Exception as e:
            if isinstance(e, AnyTimeoutError):
                self.log.warning(
                    f"{self.name}'s server failed to start"
                    f" in {spawner.start_timeout} seconds, giving up."
                    f"\n{start_timeout_message}"
                )
                e.reason = 'timeout'
                self.settings['statsd'].incr('spawner.failure.timeout')
            else:
                self.log.exception(
                    f"Unhandled error starting {self.name}'s server: {e}"
                )
                self.settings['statsd'].incr('spawner.failure.error')
                e.reason = 'error'
            try:
                await self.stop(spawner.name)
            except Exception:
                self.log.exception(
                    f"Failed to cleanup {self.name}'s server that failed to start",
                    exc_info=True,
                )
            # raise original exception
            spawner._start_pending = False
            raise e
        finally:
            # clear reference to handler after start finishes
            spawner.handler = None
        spawner.start_polling()

        # store state
        if self.state is None:
            self.state = {}
        spawner.orm_spawner.state = spawner.get_state()
        db.commit()
        spawner._waiting_for_response = True
        await self._wait_up(spawner)
