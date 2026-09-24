# BeakerHub Development Guide

This guide describes the repository layout and the normal workflows for the
Python backend, Vue frontend, container images, Helm chart, and local kind
deployment.

## Development environment

The full local stack requires Docker with Buildx, kind, kubectl, Helm, Python
3.10 or later, and GNU Make. Node.js and npm are required for direct frontend
development.

Install mkcert before creating the cluster. Linux developers must also install
the package that provides NSS `certutil`: `libnss3-tools` on Debian/Ubuntu,
`nss-tools` on Fedora/RHEL, or `nss` on Arch. On macOS, use
`brew install mkcert nss`. Run `mkcert -install` once before `make dev-setup`.
The [Quick Start](QUICKSTART.md#install-the-local-certificate-tools-first)
contains the complete sequence.

Create the development environment from the repository root:

```bash
make dev-setup
```

The setup generates `helm/kind/kind-config.yaml` and
`helm/values-secret.yaml`. These files, local certificates, and other runtime
state are machine-specific and ignored by Git. Make durable chart changes in
`helm/beakerhub/`, local overlay changes in `helm/values-local.yaml`, image
changes in `images/`, and kind-generation changes in
`helm/kind/dev-setup.py`.

## Repository layout

```text
beakerhub/
├── docs/                   # Project documentation
├── helm/
│   ├── beakerhub/          # Generic Helm chart
│   ├── kind/               # kind generator and support scripts
│   ├── Makefile            # Helm and cluster operations
│   └── values-local.yaml   # Local development overlay
├── images/
│   ├── config_files/       # Files copied into runtime images
│   ├── docker-bake.hcl     # Build graph and image tags
│   └── *.Dockerfile
├── src/beakerhub/          # Python package
├── tests/
│   ├── unit/
│   └── integration/
├── ui/
│   ├── e2e/                # Playwright tests
│   ├── src/                # Vue application and unit tests
│   └── package.json
├── Makefile                # Top-level development and test commands
└── pyproject.toml          # Package and test configuration
```

## Daily workflow

The normal loop is:

```bash
# Edit source, image, or chart files.
make sync

# Observe the rollout.
make -C helm pods
make -C helm logs-hub
```

`make sync` upgrades the Helm release, rebuilds the local images, pulls images
into the kind node, and restarts the workloads.

Make suppresses recipe-command echo and recursive directory messages during
normal operation. Set `V=1` to show recipe commands that are not explicitly
marked as quiet.

Use component-specific commands when a full synchronization is not necessary:

```bash
make -C images server
make -C helm upgrade-local
make -C helm rollout
```

## Local authentication

`helm/values-local.yaml` replaces the generic chart's JupyterHub
`DummyAuthenticator` with BeakerHub's `DummyBeakerhubAuthenticator`. This
custom authenticator accepts every nonempty username without verifying the
password. It returns the username unchanged. Administrator access follows
JupyterHub's standard `Authenticator.admin_users` configuration. The local
overlay configures `admin@example.com` as the administrator through
`auth.adminUsers`.

The Vue login form requires the username to be a valid email address and the
password to be nonempty. Therefore, normal browser login uses any valid email
address and any nonempty password. Direct API requests are less restrictive:
the authenticator accepts an empty password and does not require an email-shaped
username.

The local authenticator does not implement signup, signup confirmation, or
password reset. These operations return HTTP 501. It provides no security and
must not be used for a deployment that untrusted users can reach.

## Python backend

Backend code is in `src/beakerhub/`. BeakerHub extends JupyterHub with custom
authentication, handlers, Kubernetes spawning, node-image tasks, and services.

For development outside the cluster, create a virtual environment and install
the package in editable mode:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install pytest pytest-asyncio pytest-cov pytest-mock "moto[cognitoidp]"
```

Run the backend unit tests with:

```bash
python -m pytest tests/unit
```

When you change the in-cluster backend, rebuild the server image and roll out
the deployment:

```bash
make -C images server
make -C helm rollout
make -C helm logs-hub
```

The server image also contains the production UI build. Use `make sync` when a
change affects both components or their generated configuration.

## Frontend

The UI is a Vue 3 application built with Vite and TypeScript. Its source is in
`ui/src/`.

Run the UI directly on the host:

```bash
cd ui
npm ci
npm run dev
```

Useful UI commands are:

```bash
npm run type-check
npm run lint
npm run test:unit -- --run
npm run test:e2e
npm run build
npm run preview
```

The local Helm overlay can also run Vite inside the cluster. Its default local
hostname is `http://vite.beakerhub.internal`.

The backend injects runtime configuration into the SPA and serves its static
assets. Read [Vue SPA and JupyterHub Integration](vue-jupyterhub-integration.md)
before changing routing, base URLs, authentication redirects, or asset paths.

## Container images

Docker Bake defines the image graph in `images/docker-bake.hcl`. The runnable
image targets are:

| Target | Purpose |
| --- | --- |
| `server` | BeakerHub/JupyterHub server and built UI |
| `proxy` | Configurable HTTP proxy |
| `default-node` | Default Beaker Notebook environment |
| `task-reporter` | Reports asynchronous task status |

`base`, `node-base`, and the UI target are build intermediates.

Build images from the repository root:

```bash
make -C images build
make -C images server
make -C images default-node
make -C images print
```

Inspect and remove locally built BeakerHub images by their build labels:

```bash
make -C images images       # List labeled BeakerHub images
make -C images clean        # Remove images labeled as development images
make -C images full-clean   # Remove all labeled BeakerHub images
```

The development setup supplies local registry and tag configuration. Do not add
deployment-specific images or registry credentials to the public build graph.
Custom deployment images must build on the published public images in the
private deployment repository.

## Helm and Kubernetes

The generic chart is in `helm/beakerhub`. Its defaults are in
`helm/beakerhub/values.yaml`. Local kind overrides are in
`helm/values-local.yaml`, and the generated vault key is in the ignored
`helm/values-secret.yaml` overlay.

Validate chart changes before deployment:

```bash
make -C helm validate
```

Apply local chart changes and inspect the release:

```bash
make -C helm upgrade-local
make -C helm status
make -C helm pods
make -C helm services
```

Common diagnostic commands are:

```bash
make -C helm logs-hub
make -C helm logs-proxy
make -C helm describe-hub
make -C helm describe-proxy
kubectl get events -n beakerhub --sort-by=.lastTimestamp
```

Use the standard Helm CLI for operations that are not exposed by the Makefile:

```bash
helm get values beakerhub -n beakerhub
helm get manifest beakerhub -n beakerhub
helm history beakerhub -n beakerhub
helm rollback beakerhub -n beakerhub
```

See [Helm and kind tooling](../helm/README.md) for the local infrastructure
workflow and [Helm chart reference](../helm/beakerhub/README.md) for chart
configuration.

## Local networking and TLS

Local ingress uses `beakerhub.internal` and notebook subdomains beneath it. The
development tooling configures DNS or host mappings and generates the TLS
secret.

```bash
make -C helm setup-local-dns
make -C helm update-hosts
```

mkcert is the preferred certificate generator. If it is not available, generate
a local CA and certificate with OpenSSL:

```bash
make -C helm openssl-certs
```

The OpenSSL path requires a one-time CA import. See [Local TLS](local-tls.md).

## Cleanup

Use `make delete-dev-cluster` when you only need to remove the kind cluster.
Generated configuration, certificates, images, and local service containers
remain available for the next setup.

Use `make clean` to delete the cluster, Helm packaging and helper artifacts,
and locally built development images. It keeps generated kind configuration,
the vault-encryption key, TLS files, local DNS and registry services, and
non-development BeakerHub images.

Use `make full-clean` to remove all repository-managed and Docker state for the
local environment. It also removes generated configuration, local secrets and
certificates, all labeled BeakerHub images, DNS and registry containers, the
DNS volume, and their support images. Review the resolver instructions printed
by the command for any remaining platform configuration. See
[Helm and kind tooling](../helm/README.md#cleanup) for details.

## Testing

### Top-level commands

```bash
make test
make test-python
make test-python-cov
make test-ui
make test-e2e
make test-integration
```

### Python unit tests

```bash
python -m pytest tests/unit
python -m pytest tests/unit/test_utils.py
python -m pytest tests/unit/test_utils.py::TestToJson::test_serializes_dict
```

The authentication tests use Moto to emulate Cognito. ECS-spawner unit tests
use botocore's `Stubber` to validate ECS API requests and responses without AWS
credentials or network access; they do not start containers. A future
Docker-enabled LocalStack suite should cover ECS task image execution.

### UI unit tests

```bash
cd ui
npm ci
npm run test:unit -- --run
```

### End-to-end tests

```bash
cd ui
npm ci
npx playwright install chromium
npm run test:e2e
```

### Integration tests

Integration tests require a configured cluster and exercise BeakerHub through
its deployed services:

```bash
make test-integration
```

Use unit tests for isolated behavior. Use integration tests when behavior
depends on JupyterHub, Kubernetes, image spawning, or the deployed HTTP API.

## Debugging

### Hub startup

```bash
make -C helm logs-hub
make -C helm describe-hub
kubectl get events -n beakerhub --sort-by=.lastTimestamp
```

### Notebook spawning

```bash
kubectl get pods -n beakerhub
kubectl describe pod -n beakerhub <notebook-pod>
make -C helm logs-hub
```

### Proxy routing

```bash
make -C helm logs-proxy
make -C helm describe-proxy
kubectl get svc -n beakerhub
```

### Image pulls

```bash
make -C images print
kubectl describe pod -n beakerhub <pod-name>
```

Look at the pod events for the exact image reference and registry error before
changing image or cluster configuration.

## Documentation and contributions

Update documentation in the same change as the behavior it describes. Keep:

- `README.md` focused on project orientation and common commands.
- `docs/QUICKSTART.md` focused on the shortest working local path.
- This guide focused on development workflows.
- `helm/README.md` focused on local Helm/kind tooling.
- `helm/beakerhub/README.md` focused on chart consumers.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution and review
requirements.
