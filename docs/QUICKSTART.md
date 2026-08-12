# BeakerHub Quick Start

This guide creates a local BeakerHub development deployment on a kind cluster.

## Prerequisites

Install these tools before you start:

- Docker with Buildx support
- kind 0.20 or later
- kubectl
- Helm 3.12 or later
- Python 3.10 or later
- GNU Make

## Install the local certificate tools first

BeakerHub uses HTTPS for the application and its dynamically created notebook
subdomains. Install [mkcert](https://github.com/FiloSottile/mkcert) before you
run the setup. On Linux, mkcert also needs the NSS `certutil` command to install
its CA into browser trust stores.

Install the NSS tools for your platform:

```bash
# Debian or Ubuntu
sudo apt update
sudo apt install libnss3-tools

# Fedora or RHEL
sudo dnf install nss-tools

# Arch Linux
sudo pacman -S nss
```

On macOS:

```bash
brew install mkcert nss
```

Install mkcert through your package manager or from its release page, then
create and trust the development CA:

```bash
mkcert -install
```

Do this before cluster setup. It prevents the setup from stopping for a missing
certificate tool and makes the CA available before BeakerHub starts. Without a
trusted CA, browsers can silently reject notebook iframe and secure WebSocket
connections even after you accept a warning for the main page.

See [Local TLS](local-tls.md) for browser-specific details and the manual
OpenSSL alternative.

## Install

```bash
git clone https://github.com/jataware/beakerhub.git
cd beakerhub
make dev-setup
```

The first run generates the kind configuration and a local vault-encryption
key, then creates the cluster and deploys BeakerHub. Generated configuration,
certificates, and local secrets are ignored by Git.

## Open BeakerHub

The normal local URL is:

```text
https://beakerhub.internal
```

### Local authentication

The local deployment uses `DummyBeakerhubAuthenticator`. It does not verify
credentials. In the browser login form, use:

- **Username:** any valid email address, such as `developer@example.com`
- **Password:** any nonempty value

The supplied username becomes the BeakerHub username. Log in as
`admin@example.com` for administrator access. Other usernames are regular
users. The local administrator is configured explicitly through
`auth.adminUsers` in `helm/values-local.yaml`.

The underlying authentication API accepts any nonempty username and also
accepts an empty password. The browser form imposes the stricter email-address
and nonempty-password requirements above.

Signup, signup confirmation, and password reset are not available with the
local authenticator. Those operations return HTTP 501 even though their links
can appear in the UI.

This authenticator is only for local development and evaluation. Do not use it
for a deployment that untrusted users can reach.

If the hostname does not resolve, update the local hostname configuration:

```bash
make -C helm update-hosts
```

The local certificate covers `beakerhub.internal` and its first-level
subdomains. If the browser does not trust it, follow the instructions in
[Local TLS](local-tls.md).

You can bypass ingress and TLS with a port forward:

```bash
make -C helm port-forward
```

Then open `http://localhost:8080`. To inspect the assigned LoadBalancer address,
run:

```bash
make -C helm get-url
```

## Make changes

Apply backend, frontend, image, or chart changes with:

```bash
make sync
```

Inspect the deployment while it updates:

```bash
make -C helm pods
make -C helm logs-hub
make -C helm logs-proxy
```

The local values overlay is `helm/values-local.yaml`. The generic chart and its
defaults are in `helm/beakerhub/`.

## Frontend development

The local deployment can run a Vite development server for the Vue UI. You can
also run Vite directly on the host:

```bash
cd ui
npm ci
npm run dev
```

The in-cluster Vite hostname is `http://vite.beakerhub.internal` when the local
overlay enables it.

## Common commands

```bash
# Kubernetes resources
make -C helm pods
make -C helm services
make -C helm status

# Rebuild and redeploy
make sync
make -C helm rollout

# Validate the Helm chart
make -C helm validate

# Recreate or remove local development state
make recreate-dev-cluster
make delete-dev-cluster
make clean
make full-clean
```

`make clean` removes the cluster and development build artifacts while keeping
generated configuration, certificates, and the local DNS and registry
services. `make full-clean` also removes generated local secrets and
certificates, all labeled BeakerHub images, and the local service containers.
See [Helm and kind tooling](../helm/README.md#cleanup) for the complete list.

## Troubleshooting

### Cluster creation fails

Check for an existing cluster, then recreate it if necessary:

```bash
kind get clusters
make recreate-dev-cluster
```

### Pods do not start

```bash
make -C helm pods
make -C helm describe-hub
make -C helm describe-proxy
kubectl get events -n beakerhub --sort-by=.lastTimestamp
```

### Images cannot be pulled

Rebuild the development images and inspect the image configuration:

```bash
make build-dev-images
make -C images print
kubectl describe pod -n beakerhub <pod-name>
```

### Ingress or TLS fails

```bash
make -C helm setup-local-dns
kubectl get ingress -n beakerhub
kubectl get pods -n ingress-nginx
```

For certificate trust and WebSocket failures, see [Local TLS](local-tls.md).

### LoadBalancer remains pending

```bash
make -C helm check-lb
make -C helm install-metallb
```

Port forwarding remains available when a LoadBalancer address is not assigned.

## Next steps

- Read the [Development Guide](DEVELOPMENT.md).
- Review the [Helm and kind tooling](../helm/README.md).
- Review the [Helm chart reference](../helm/beakerhub/README.md).
- Read the [Contributing Guide](../CONTRIBUTING.md).
