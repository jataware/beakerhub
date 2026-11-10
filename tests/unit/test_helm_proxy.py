import shutil
import subprocess
from pathlib import Path

import pytest


CHART = Path(__file__).resolve().parents[2] / "helm" / "beakerhub"
pytestmark = pytest.mark.skipif(shutil.which("helm") is None, reason="helm not installed")


def render(*values: str) -> str:
    command = ["helm", "template", "test", str(CHART), "--set", "ingress.enabled=true"]
    for value in values:
        command.extend(["--set", value])
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def test_subdomain_routing_defaults():
    rendered = render()
    assert "- --host-routing" in rendered
    assert 'c.BeakerHub.subdomain_host = "http://beakerhub.internal"' in rendered
    assert 'host: "*.beakerhub.internal"' in rendered
    assert "path: /hub/health" in rendered


def test_subpath_routing():
    rendered = render(
        "proxy.hostRouting=false",
        "hub.baseUrl=/beaker/",
        "hub.publicOrigin=https://example.org:8443",
    )
    assert "- --host-routing" not in rendered
    assert 'c.BeakerHub.subdomain_host = ""' in rendered
    assert 'host: "*.beakerhub.internal"' not in rendered
    assert rendered.count("path: /beaker/hub/health") == 3
    assert 'hub_origin = "https://example.org:8443"' in rendered
    assert 'c.BaseBeakerApp.allow_origin_pat = rf"^{re.escape(hub_origin)}$"' in rendered
    assert "c.BaseBeakerApp.allow_credentials = True" in rendered
    assert '"Content-Security-Policy": f"frame-ancestors \'self\' {hub_origin}"' in rendered


def test_hub_extra_env():
    rendered = render('hub.extraEnv.EXAMPLE=hello', 'hub.extraEnv.NUMBER=123')
    assert '- name: "EXAMPLE"\n          value: "hello"' in rendered
    assert '- name: "NUMBER"\n          value: "123"' in rendered
    assert 'key: CONFIGPROXY_AUTH_TOKEN' in rendered


def test_custom_health_path_is_not_prefixed():
    rendered = render("hub.baseUrl=/beaker/", "hub.healthcheck.readiness.path=/custom")
    assert "path: /custom" in rendered
    assert rendered.count("path: /beaker/hub/health") == 2
