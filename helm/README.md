# Helm and kind Tooling

This directory contains the generic BeakerHub Helm chart and the tooling used
by the local kind development environment.

## Layout

```text
helm/
├── beakerhub/          # Generic Helm chart
├── kind/
│   ├── dev-setup.py   # Development configuration generator
│   ├── certs.d/       # Generated local certificates and registry host config
│   ├── install-ingress-kind.sh
│   ├── install-metallb-kind.sh
│   └── update-hosts.sh
├── Makefile           # Helm and local infrastructure operations
└── values-local.yaml  # Local kind values overlay
```

Machine-specific files such as `kind/kind-config.yaml`, certificates, and
`values-secret.yaml` are generated locally and ignored by Git.

## Local development

Install mkcert and the platform NSS tools before creating the cluster. Linux
requires the package that supplies `certutil`, such as `libnss3-tools` on
Debian/Ubuntu. Run `mkcert -install` once so browsers trust the development CA.
See the
[Quick Start](../docs/QUICKSTART.md#install-the-local-certificate-tools-first).

Use the top-level setup for a complete environment:

```bash
make dev-setup
```

After setup, apply source and configuration changes with:

```bash
make sync
```

The top-level workflow coordinates generated local files, the image registry,
kind cluster, image builds, and Helm release. Direct targets in this directory
are useful after that environment exists.

## Make targets

Run targets from the repository root with `make -C helm <target>`.

### Chart validation and release operations

| Target | Purpose |
| --- | --- |
| `help` | List targets that have built-in command help |
| `lint` | Run `helm lint` |
| `template` | Render the chart with generic defaults |
| `validate` | Lint the chart and verify that it renders |
| `dry-run` | Perform a Helm dry-run install |
| `install` | Install or upgrade with generic chart defaults |
| `install-local` | Install or upgrade with the local kind overlays |
| `upgrade` | Upgrade with generic defaults |
| `upgrade-local` | Upgrade the local development release |
| `rollback` | Roll back the release |
| `uninstall` | Uninstall the release |
| `status` | Show release status |
| `get-values` | Show user-supplied release values |
| `get-all` | Show all release information |
| `history` | Show Helm release history |
| `package` | Package the chart under `helm/packages/` |
| `clean` | Remove packaged chart archives and the kind helper virtual environment |
| `full-clean` | Also remove generated kind configuration, local secrets, and certificates |
| `check-local-config` | Verify local values files |
| `check-local-prereqs` | Verify tools needed by the local install |

### Inspection and troubleshooting

| Target | Purpose |
| --- | --- |
| `pods` | List BeakerHub pods |
| `services` | List BeakerHub services |
| `logs-hub` | Follow hub logs |
| `logs-proxy` | Follow proxy logs |
| `describe-hub` | Describe hub pods |
| `describe-proxy` | Describe proxy pods |
| `get-url` | Print the proxy LoadBalancer address |
| `port-forward` | Forward the proxy to `localhost:8080` |
| `rollout` | Restart deployments in the namespace |
| `check-lb` | Inspect LoadBalancer status |

### Local infrastructure

| Target | Purpose |
| --- | --- |
| `install-metallb` | Install MetalLB in kind |
| `install-ingress` | Install ingress-nginx in kind |
| `install-certs` | Generate mkcert certificates and install the TLS secret |
| `openssl-certs` | Generate a local CA and certificate with OpenSSL |
| `install-certs-secret` | Apply existing certificate files as a TLS secret |
| `update-hosts` | Update local host mappings |
| `setup-local-dns` | Install ingress, certificates, and host mappings |

## Configuration files

### `beakerhub/values.yaml`

This is the generic chart configuration. It must remain free of deployment
credentials, private infrastructure identifiers, and real environment
hostnames. The default authentication mode is JupyterHub's dummy authenticator.

### `values-local.yaml`

This overlay adapts the chart for the local kind environment. It configures the
local registry, ingress hostnames, development resource sizes, and optional
Vite server.

### `values-secret.yaml`

The top-level Makefile generates this ignored overlay with a local Fernet key
for the BeakerHub vault. Both `install-local` and `upgrade-local` apply it after
`values-local.yaml`. The key remains stable across normal upgrades and cluster
recreation unless the file is explicitly removed. If the key is regenerated,
previously encrypted vault data cannot be decrypted.

### Deployment values

Create a separate values file for each real deployment. Store it in the
deployment repository, not here. Keep credentials out of ordinary values files
and supply them through an appropriate secret-management mechanism.

## Chart development

Validate every chart change:

```bash
make -C helm validate
```

To inspect the exact rendered resources:

```bash
helm template beakerhub ./helm/beakerhub --namespace beakerhub
```

To test a custom values file without installing:

```bash
helm template beakerhub ./helm/beakerhub \
  --namespace beakerhub \
  --values /path/to/my-values.yaml
```

The chart source is documented in the [Helm chart reference](beakerhub/README.md).

## Networking and TLS

The local overlay uses these hostnames:

- `beakerhub.internal` for the application
- `vite.beakerhub.internal` for the optional Vite server
- First-level subdomains of `beakerhub.internal` for notebook sessions

The generated certificate must cover both `beakerhub.internal` and
`*.beakerhub.internal`. mkcert is the recommended path because it installs a
trusted local CA. The OpenSSL path requires a manual CA import. See
[Local TLS](../docs/local-tls.md).

## Cleanup

Remove only the Helm release:

```bash
make -C helm uninstall
```

Remove the local development cluster through the top-level Makefile:

```bash
make delete-dev-cluster
```

This keeps generated configuration, certificates, local service containers,
and built images so that you can create the cluster again without recreating
all local state.

Run the normal top-level cleanup to delete the cluster, packaged charts, the
kind helper virtual environment, and locally built images labeled as
development images:

```bash
make clean
```

This keeps `helm/kind/kind-config.yaml`, `helm/values-secret.yaml`, local TLS
files, the DNS and registry containers, and non-development BeakerHub images.

To remove all repository-managed and Docker state for the local development
environment, run:

```bash
make full-clean
```

In addition to the normal cleanup, this removes:

- Generated kind configuration and the local vault-encryption key
- Generated TLS certificates and OpenSSL CA files
- All locally built images labeled as BeakerHub images
- The local DNS container and volume
- The local registry container
- The `doll` registry and `dnsmasq` support images

The command prints any platform-specific resolver configuration that might
still need manual removal. If `full-clean` removes an OpenSSL-generated CA, the
next `make -C helm openssl-certs` creates a new CA that must be imported into
the browser trust store.

The direct `make -C helm clean` and `make -C helm full-clean` targets remove
only their Helm-generated files. They do not delete the kind cluster,
containers, or images.

## Troubleshooting

Start with:

```bash
make -C helm pods
make -C helm services
kubectl get events -n beakerhub --sort-by=.lastTimestamp
```

For image-pull failures, compare the rendered image references with
`make -C images print`. For ingress or certificate failures, run
`make -C helm setup-local-dns` and review [Local TLS](../docs/local-tls.md).
