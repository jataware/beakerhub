import json
from unittest.mock import MagicMock, patch

import pytest
import requests
from jupyterhub.scopes import has_scope, parse_scopes
from jupyterhub.user import User
from tornado.web import HTTPError

from beakerhub.api_handlers import BeakerhubServerInfoHandler
from beakerhub.node_app import BeakerNodeApp


def make_handler():
    handler = MagicMock()
    handler.current_user = MagicMock(spec=User)
    handler.current_user.name = "alice"
    handler.current_user.orm_user.id = 12
    handler.get_token.return_value = object()
    handler.parsed_scopes = {}
    return handler


def test_server_info_returns_stored_options():
    handler = make_handler()
    options = {"context": {"nested": [1, 2]}}
    handler.db.query.return_value.filter_by.return_value.one_or_none.return_value.user_options = options
    with patch("beakerhub.api_handlers.has_scope", return_value=True) as check_scope:
        BeakerhubServerInfoHandler.get(handler, "session-1")
    check_scope.assert_called_once_with(
        "access:servers!server=alice/session-1", handler.parsed_scopes, db=handler.db
    )
    handler.db.query.return_value.filter_by.assert_called_once_with(user_id=12, name="session-1")
    assert json.loads(handler.write.call_args.args[0]) == options


def test_server_scope_is_limited_to_named_server():
    scopes = parse_scopes({"access:servers!server=alice/session-1"})
    assert has_scope("access:servers!server=alice/session-1", scopes)
    assert not has_scope("access:servers!server=alice/session-2", scopes)


def test_server_info_rejects_missing_token():
    handler = make_handler()
    handler.get_token.return_value = None
    with pytest.raises(HTTPError) as error:
        BeakerhubServerInfoHandler.get(handler, "session-1")
    assert error.value.status_code == 403


def test_server_info_rejects_other_server():
    handler = make_handler()
    with patch("beakerhub.api_handlers.has_scope", return_value=False):
        with pytest.raises(HTTPError) as error:
            BeakerhubServerInfoHandler.get(handler, "session-2")
    assert error.value.status_code == 404
    handler.db.query.assert_not_called()


def test_server_info_missing_server():
    handler = make_handler()
    handler.db.query.return_value.filter_by.return_value.one_or_none.return_value = None
    with patch("beakerhub.api_handlers.has_scope", return_value=True):
        with pytest.raises(HTTPError) as error:
            BeakerhubServerInfoHandler.get(handler, "missing")
    assert error.value.status_code == 404


def test_node_request_returns_json_and_raises_http_errors():
    app = BeakerNodeApp(hub_api_url="http://hub/api", hub_api_token="token")
    response = MagicMock()
    response.json.return_value = {"context": {"key": "value"}}
    with patch("beakerhub.node_app.requests.get", return_value=response) as get:
        assert app._hub_request("beakerhub/server/session/info") == response.json.return_value
    get.assert_called_once_with(
        "http://hub/api/beakerhub/server/session/info",
        headers={"Authorization": "Bearer token"},
    )
    response.raise_for_status.side_effect = requests.HTTPError("failed")
    with patch("beakerhub.node_app.requests.get", return_value=response):
        with pytest.raises(requests.HTTPError):
            app._hub_request("beakerhub/server/session/info")


def test_node_initialization_stores_options():
    app = BeakerNodeApp(server_id="session id")
    options = {"context": {"key": "value"}}
    with patch("beakerhub.node_app.BaseBeakerApp.initialize"), patch.object(
        app, "_hub_request", return_value=options
    ) as request:
        app.initialize()
    request.assert_called_once_with("beakerhub/server/session%20id/info")
    assert app.server_options == options
