#! /usr/bin/env python3
"""
Dev Setup - Configuration tool for BeakerHub local development environment.

Manages dev-config.yaml (development settings) and generates kind-config.yaml
for Kind cluster setup. The dev config can also be passed to Helm as values.
"""

import click
import json
import os.path
import traceback
import yaml
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from functools import reduce
from pathlib import Path
from typing import Any, TypeAlias

# =============================================================================
# Constants
# =============================================================================

BEAKERHUB_CONTAINER_PATH = "/opt/development/packages/beakerhub"
EXTRA_PACKAGE_PATH = "/opt/development/packages"

SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = next(
    (path for path in SCRIPT_DIR.parents if (path / "pyproject.toml").is_file()),
    None
) or SCRIPT_DIR.parent.parent
BAKE_DIR = ROOT_DIR / "images"
K8S_DIR = ROOT_DIR / "kubernetes"

DEFAULT_DEV_CONFIG_FILE = ROOT_DIR / "dev-config.yaml"
DEFAULT_KIND_CONFIG_FILE = SCRIPT_DIR / "kind-config.yaml"

# Special key for packages that should be installed on all node types
ALL_NODES_KEY = "all"

REGISTRY_URL = os.environ.get("REGISTRY_URL", None)

# File headers
DEV_CONFIG_HEADER = f"""
# Notice: After editing this file, you likely will need to recreate your kind kubernetes cluster.
#
# This can be done by running `make recreate-dev-cluster`.
"""

KIND_CONFIG_HEADER = f"""
###  Auto-generated file. Do not Edit.  ###
#
# If you need changes to this file, update your dev-config.yaml file and run `make {DEFAULT_KIND_CONFIG_FILE.relative_to(ROOT_DIR)}`
"""


# =============================================================================
# Configuration Dataclasses
# =============================================================================

@dataclass
class PackageConfig:
    """Custom package definition"""
    name: str
    package_spec: str|None = field(default=None)
    src_path: str|None = field(default=None)
    build_from_src: bool = field(default=False)
    prebuild_commands: list[str] = field(default_factory=list)
    postbuild_commands: list[str] = field(default_factory=list)

    def __post_init__(self):
        # A package that can't be installed... What's the point?
        if self.package_spec is None and self.src_path is None:
            raise ValueError("At least one of 'package_spec' or 'src_path' must be set.")
        # Ensure we have an absolute path that exists
        if self.src_path:
            path = Path(self.src_path).resolve()
            if not (path.exists() and path.is_dir()):
                raise ValueError(f"Package {self.name}'s source path ({path}) does not point to an existing directory.")
            self.src_path = str(path)

    @classmethod
    def from_dict(cls, data: dict) -> "PackageConfig":
        """Create config from dictionary, handling missing keys gracefully."""
        known_fields = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known_fields})

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        return asdict(self)

@dataclass
class DevSetupConfig:
    """Main configuration structure."""
    cluster_name: str = field(default="beakerhub-dev")
    packages: dict[str, PackageConfig] = field(default_factory=dict)
    packages_by_node: dict[str, list[str]] = field(default_factory=lambda: {ALL_NODES_KEY: list()})
    extra_mounts: list[str] = field(default_factory=list)
    networking: dict[str, Any] = field(default_factory=dict)
    secrets: dict[str, Any] = field(default_factory=dict)
    debug: bool = False
    registries: list[str] = field(default_factory=list)

    def __post_init__(self):
        unknown_packages = {
            pkg
            for node_packages in self.packages_by_node.values()
            for pkg in node_packages
            if pkg not in self.packages
        }
        if unknown_packages:
            raise ValueError(
                f"packages_by_node references undefined packages: {', '.join(sorted(unknown_packages))}"
            )
        for package_name, package in self.packages.items():
            if isinstance(package, dict):
                self.packages[package_name] = PackageConfig(**package)

    @classmethod
    def from_dict(cls, data: dict) -> "DevSetupConfig":
        """Create config from dictionary, handling missing keys gracefully."""
        known_fields = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known_fields})

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        result = asdict(self)
        print(result)
        for key, value in self.packages.items():
            print(key, value)
            result["packages"][key] = value.to_dict()
        print(result)
        return result

    def get_all_packages(self) -> dict[str, PackageConfig]:
        """
        Returns a mapping of packages by name for all packages used.
        """
        used_packages = reduce(lambda a, b: set(a) | set(b), self.packages_by_node.values(), set())
        return {
            key: self.packages[key]
            for key in used_packages
            if key in self.packages
        }


# =============================================================================
# Default Configuration
# =============================================================================

DEFAULT_ARGS = {
    "kind_config_file": DEFAULT_KIND_CONFIG_FILE,
}


def get_default_config() -> DevSetupConfig:
    """Get default configuration, auto-detecting beaker-kernel if present."""
    config = DevSetupConfig()

    # Auto-detect beaker-kernel path if it exists adjacent to beakerhub
    beaker_kernel_path = ROOT_DIR.parent / "beaker-kernel"

    config.packages["beaker-kernel"] = PackageConfig(
        name="beaker-kernel",
        src_path=str(beaker_kernel_path.absolute()) if beaker_kernel_path.exists() else None,
        build_from_src=beaker_kernel_path.is_dir(),
        package_spec="beaker-kernel",
        prebuild_commands=[
            "curl -fsSL https://deb.nodesource.com/setup_24.x | bash -",
            "apt update -y && apt install -y rsync nodejs make",
            "make beaker_kernel/app/ui/index.html"
        ]
    )
    config.packages_by_node[ALL_NODES_KEY] = ["beaker-kernel"]

    return config


def get_kind_config_template() -> dict:
    """Get the base Kind cluster configuration template."""
    return {
        "kind": "Cluster",
        "apiVersion": "kind.x-k8s.io/v1alpha4",
        "name": None,
        "nodes": [
            {
                "role": "control-plane",
                "extraMounts": [
                    {
                        "hostPath": str((SCRIPT_DIR / "certs.d").absolute()),
                        "containerPath": "/etc/containerd/certs.d"
                    },
                    {
                        "hostPath": str(ROOT_DIR.absolute()),
                        "containerPath": BEAKERHUB_CONTAINER_PATH
                    }
                ]
            }
        ]
    }


# =============================================================================
# YAML Utilities
# =============================================================================

def render_config_yaml(config: dict) -> str:
    """Render configuration dictionary as YAML string."""
    return yaml.safe_dump(config, sort_keys=False)


def is_valid_yaml(yaml_str: str) -> bool:
    """Check if string is valid YAML."""
    try:
        yaml.safe_load(yaml_str)
        return True
    except yaml.YAMLError:
        return False


def write_config_file(
    config_file_path: Path | str,
    config: dict,
    dry_run: bool = False,
    header: str | None = None,
) -> None:
    """Write configuration to file (or just display if dry_run).

    Args:
        config_file_path: Path to write the config file.
        config: Configuration dictionary to serialize as YAML.
        dry_run: If True, only display what would be written.
        header: Optional comment text to prepend to the file.
                Should already include '#' prefixes if desired.
    """
    if not isinstance(config_file_path, Path):
        config_file_path = Path(config_file_path)

    content = yaml.safe_dump(config, sort_keys=False)
    if header:
        content = header.rstrip("\n") + "\n\n" + content

    if dry_run:
        click.echo(click.style(f"[DRY RUN] Would write to {config_file_path}:", fg="yellow"))
    else:
        click.echo(f"Writing output to {config_file_path}")
        if not config_file_path.parent.exists():
            config_file_path.parent.mkdir(parents=True)
        config_file_path.write_text(content)


def echo_config(config_file_path: Path | str, config: dict) -> None:
    """Display configuration with file header."""
    click.echo(f"======== START {config_file_path} ========")
    click.echo(render_config_yaml(config), nl=False)
    click.echo(f"========= END {config_file_path} =========")


# =============================================================================
# Kind Config Generation
# =============================================================================

def generate_kind_config(cluster_name: str) -> dict:
    """Generate Kind cluster configuration from dev config."""
    kind_config = get_kind_config_template()
    kind_config["name"] = cluster_name

    nodes: list = kind_config.setdefault("nodes", [])

    # Get the control plane node (create if missing)
    control_plane: dict | None = next(
        (node for node in nodes if node.get("role") == "control-plane"),
        None
    )
    if not control_plane:
        control_plane = {"role": "control-plane"}
        nodes.append(control_plane)

    control_plane.setdefault("extraMounts", [])

    return kind_config


# =============================================================================
# CLI Commands
# =============================================================================

@click.group(invoke_without_command=True)
@click.option("-c", "--kind-config-file", "kind_config_file", type=click.Path(dir_okay=False))
@click.option("--dry-run", is_flag=True, help="Show what would be written without writing files.")
@click.pass_context
def main(ctx: click.core.Context, kind_config_file, dry_run: bool):
    """Dev Setup - Configure BeakerHub local development environment."""
    if ctx.default_map is None:
        ctx.default_map = {}

    # Store dry_run in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["dry_run"] = dry_run

    if kind_config_file:
        kind_config_file = Path(kind_config_file)
        ctx.default_map["kind_config_file"] = kind_config_file

    # Propagate defaults to subcommands
    if ctx.invoked_subcommand:
        ctx.default_map[ctx.invoked_subcommand] = ctx.default_map

    # Default action: update kind config
    if not ctx.invoked_subcommand:
        ctx.default_map["update-kind-config"] = ctx.default_map
        ctx.invoke(update_kind_config)


@main.command("update-kind-config")
@click.option("-c", "--kind-config-file", "kind_config_file", type=click.Path(dir_okay=False))
@click.argument("cluster_name", type=str)
@click.pass_context
def update_kind_config(ctx, cluster_name, kind_config_file: Path):
    """Generate Kind cluster configuration from dev config."""
    kind_config_file = kind_config_file or DEFAULT_ARGS["kind_config_file"]
    dry_run = ctx.obj.get("dry_run", False) if ctx.obj else False

    if isinstance(kind_config_file, str):
        kind_config_file = Path(kind_config_file)

    kind_config = generate_kind_config(cluster_name)
    echo_config(kind_config_file, kind_config)

    write_config_file(kind_config_file, kind_config, dry_run=dry_run)


if __name__ == "__main__":
    main(default_map=DEFAULT_ARGS)
