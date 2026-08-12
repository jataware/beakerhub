# BeakerHub

BeakerHub is a multi-user, Kubernetes-hosted environment for Beaker Notebook.
It uses JupyterHub to manage users and notebook sessions, a Vue application for
the user interface, and a configurable HTTP proxy to route traffic.

## Prerequisites

Local development requires:

- Docker with Buildx support
- [kind](https://kind.sigs.k8s.io/docs/user/quick-start/) 0.20 or later
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Helm](https://helm.sh/docs/intro/install/) 3.12 or later
- Python 3.10 or later
- GNU Make

### Local certificate prerequisites

Install [mkcert](https://github.com/FiloSottile/mkcert) before running the
development setup. On Linux, also install the NSS tools that provide `certutil`;
mkcert uses them to add its development CA to browser trust stores.

```bash
# Debian or Ubuntu
sudo apt install libnss3-tools

# Fedora or RHEL
sudo dnf install nss-tools

# Arch Linux
sudo pacman -S nss
```

On macOS, install both packages with `brew install mkcert nss`. After mkcert and
the platform NSS equivalent are installed, create and trust the development CA:

```bash
mkcert -install
```

Doing this before `make dev-setup` avoids interrupting cluster creation and
ensures that browsers trust notebook subdomains and their secure WebSocket
connections. OpenSSL is available as a manual alternative; see
[Local TLS](docs/local-tls.md).

## Quick start

Clone the repository and run the development setup from its root:

```bash
git clone https://github.com/jataware/beakerhub.git
cd beakerhub
make dev-setup
```

The setup creates a kind cluster, configures local image and DNS services,
builds the BeakerHub images, generates the local vault key, and installs the
Helm chart. Generated kind configuration, certificates, and secret values are
ignored by Git.

After setup, open `https://beakerhub.internal`. The local development
authenticator accepts any valid email address and any nonempty password; it
does not verify the credentials. See the [Quick Start](docs/QUICKSTART.md) for
the complete local authentication behavior, access alternatives, and
troubleshooting.

## Development workflow

After you change backend, frontend, image, or Helm sources, rebuild and apply
the development deployment:

```bash
make sync
```

Useful commands include:

```bash
# Application status and logs
make -C helm pods
make -C helm services
make -C helm logs-hub
make -C helm logs-proxy

# Helm operations
make -C helm validate
make -C helm upgrade-local
make -C helm rollout

# Images
make -C images build
make -C images server
make -C images default-node
make -C images images
make -C images print

# Local environment lifecycle
make recreate-dev-cluster
make delete-dev-cluster
make clean
make full-clean
```

Run `make -C helm help` for Helm and cluster-management command help.
`make clean` removes the cluster and development build artifacts but
keeps generated configuration, certificates, and local service containers.
`make full-clean` removes all repository-managed local state, service
containers, and labeled images. See [Helm and kind
tooling](helm/README.md#cleanup) for the exact cleanup scope.

## Architecture

BeakerHub contains these runtime components:

- **Hub** — the BeakerHub/JupyterHub server that handles authentication,
  sessions, notebook spawning, and the application API.
- **Proxy** — the configurable HTTP proxy that routes browser and notebook
  traffic.
- **Notebook nodes** — per-user Beaker Notebook pods spawned in Kubernetes.
- **Task reporter** — reports the status of asynchronous node-image tasks.
- **UI** — the Vue/Vite single-page application served by the hub image.

The image build is defined in `images/docker-bake.hcl`. Its runnable targets
are `server`, `proxy`, `default-node`, and `task-reporter`. `base` and the UI
build target are build intermediates.

Kubernetes resources are in the `helm/beakerhub` chart. Local kind tooling and
the local values overlay are under `helm/`.

## Repository layout

```text
beakerhub/
├── docs/                  # User and developer documentation
├── helm/
│   ├── beakerhub/         # Generic Helm chart
│   ├── kind/              # Local kind support
│   ├── Makefile           # Helm and cluster operations
│   └── values-local.yaml  # Local development overlay
├── images/                # Dockerfiles and Docker Bake configuration
├── src/beakerhub/         # Python package
├── tests/                 # Python unit and integration tests
├── ui/                    # Vue application and UI tests
├── Makefile               # Top-level development and test commands
└── pyproject.toml         # Python package metadata
```

## Configuration

`helm/beakerhub/values.yaml` contains generic chart defaults. It uses
JupyterHub's dummy authenticator by default so that the chart can be evaluated
without access to an external identity provider. The local development overlay
uses BeakerHub's custom development authenticator instead; see the [Quick
Start](docs/QUICKSTART.md#local-authentication).

For a real deployment, create a separate values file and configure at least:

- Public image repositories and immutable tags
- Authentication and administrator access
- Ingress, DNS, and TLS
- Persistent storage classes and access modes
- Resource requests and limits
- Secret delivery

Do not commit credentials to a values file. Supply them through your deployment
system or a Kubernetes secret-management solution. See the
[Helm chart documentation](helm/beakerhub/README.md) for the available settings.

## Testing

Run tests from the repository root:

```bash
make test                 # Python and UI unit tests
make test-python          # Python unit tests
make test-python-cov      # Python unit tests with coverage
make test-ui              # UI unit tests
make test-e2e             # Playwright tests
make test-integration     # Tests against the development cluster
```

The integration tests require a running development cluster. See the
[Development Guide](docs/DEVELOPMENT.md#testing) for component-specific commands.

## Documentation

- [Quick Start](docs/QUICKSTART.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [Contributing Guide](CONTRIBUTING.md)
- [Helm and kind tooling](helm/README.md)
- [Helm chart reference](helm/beakerhub/README.md)
- [Local TLS](docs/local-tls.md)
- [Vue and JupyterHub integration](docs/vue-jupyterhub-integration.md)

## License

BeakerHub is available under the [MIT License](LICENSE.txt).
