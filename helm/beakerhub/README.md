# BeakerHub Helm Chart

This chart installs the BeakerHub server, configurable HTTP proxy, Kubernetes
permissions, storage, ingress, and configuration used to spawn notebook pods.

## Prerequisites

- Kubernetes 1.27 or later
- Helm 3.12 or later
- A storage provisioner that supports the access modes selected for hub and
  user storage
- Reachable BeakerHub server, proxy, default-node, and task-reporter images

Ingress, TLS, authentication, and secret-management prerequisites depend on the
deployment values.

## Install from the source tree

Render and validate the chart before installation:

```bash
helm lint ./helm/beakerhub
helm template beakerhub ./helm/beakerhub --namespace beakerhub
```

Install it with a deployment-specific values file:

```bash
helm upgrade --install beakerhub ./helm/beakerhub \
  --namespace beakerhub \
  --create-namespace \
  --values /path/to/my-values.yaml
```

The values file should be maintained outside this public source tree when it
contains environment-specific hostnames, infrastructure identifiers, or secret
references.

For the repository's local kind environment, use the top-level workflow instead:

```bash
make dev-setup
```

See [Helm and kind tooling](../README.md) for local operations.

## Images

The chart uses four runnable images:

| Value | Purpose |
| --- | --- |
| `hub.image` | BeakerHub/JupyterHub server and built UI |
| `proxy.image` | Configurable HTTP proxy |
| `notebook.image` | Default image for spawned notebook pods |
| `tasks.reporter.image` | Task-status reporter |

`defaultRegistry` is prepended to chart-managed image repositories. Set it to
an empty string when repositories already contain the complete registry path.
Use immutable tags for production deployments.

## Core configuration

The complete and authoritative set of values is in [values.yaml](values.yaml).
The sections below identify the settings most deployments must review.

### Namespace and registry

| Value | Description | Default |
| --- | --- | --- |
| `namespace` | Namespace written into chart resources | `beakerhub` |
| `defaultRegistry` | Prefix applied to chart-managed image repositories | `""` |
| `imagePullSecrets` | Kubernetes image-pull secret references | `[]` |

### Proxy

| Value | Description | Default |
| --- | --- | --- |
| `proxy.image.repository` | Proxy image repository | `beakerhub/proxy` |
| `proxy.image.tag` | Proxy image tag | `latest` |
| `proxy.service.type` | Public proxy service type | `LoadBalancer` |
| `proxy.service.port` | Public service port | `80` |
| `proxy.resources` | Proxy requests and limits | See `values.yaml` |
| `proxy.replicaCount` | Proxy replica count | `1` |

`proxy.targetGroupBinding` is optional support for clusters that use externally
managed AWS load-balancer target groups. It is disabled by default and is not
required for a generic deployment.

### Hub

| Value | Description | Default |
| --- | --- | --- |
| `hub.image.repository` | Server image repository | `beakerhub/server` |
| `hub.image.tag` | Server image tag | `latest` |
| `hub.baseUrl` | JupyterHub base URL | `/` |
| `hub.logLevel` | Server log level | `INFO` |
| `hub.serviceAccount.create` | Create the service account used by the hub pod | `true` |
| `hub.serviceAccount.name` | Service account used by the hub pod | `beakerhub-hub` |
| `hub.serviceAccount.annotations` | Annotations applied to the hub service account | `{}` |
| `hub.footer` | Runtime footer branding and links | See `values.yaml` |
| `hub.resources` | Hub requests and limits | See `values.yaml` |
| `hub.extraEnvFrom` | Additional `envFrom` entries | `[]` |
| `hub.extraVolumes` | Additional pod volumes | `[]` |
| `hub.extraVolumeMounts` | Additional server mounts | `[]` |

Startup, readiness, and liveness probes are configured under
`hub.healthcheck`.

The UI footer is configured at runtime, so the same server image can use
deployment-specific branding and links:

```yaml
hub:
  footer:
    productName: BeakerHub
    tagline: Your AI-powered co-scientist.
    documentationUrl: https://jataware.github.io/beaker-notebook
    githubUrl: https://github.com/jataware/beaker-notebook
    contactEmail: contact@beakerhub.com
    copyrightYears: 2024-present
    copyrightHolder: Jataware Corp
    copyrightUrl: https://jataware.com
```

Set `documentationUrl`, `githubUrl`, or `contactEmail` to an empty string to
hide that item. The chart maps this dictionary to `c.BeakerHub.footer`; direct
BeakerHub configurations can set the same traitlet. Partial direct overrides
are merged with the built-in defaults when the page is served.

### Notebook pods

| Value | Description | Default |
| --- | --- | --- |
| `notebook.image.repository` | Default notebook repository | `beakerhub/default-node` |
| `notebook.image.tag` | Default notebook tag | `latest` |
| `notebook.serviceAccount.create` | Create the service account used by notebook pods | `true` |
| `notebook.serviceAccount.name` | Service account used by notebook pods | `beakerhub-notebook` |
| `notebook.defaultResources` | Spawned-pod requests and limits | See `values.yaml` |
| `notebook.startTimeout` | Spawn timeout in seconds | `300` |
| `notebook.httpTimeout` | Notebook HTTP timeout in seconds | `60` |
| `notebook.deleteStoppedPods` | Delete pods after stop | `false` |
| `notebook.envKeep` | Hub environment names passed to notebooks | See `values.yaml` |
| `notebook.extraConfig` | Extra generated notebook configuration | `""` |

Review the default CPU and memory requests before installation. They are
intentionally explicit and may exceed the capacity of a small cluster.

### Kubernetes identities and RBAC

The hub and spawned notebook pods use separate Kubernetes service accounts.
The hub account is configured under `hub.serviceAccount`; the notebook account
is configured under `notebook.serviceAccount`. Set the corresponding `create`
value to `false` when an account is managed outside this chart, but keep `name`
set to the account that the pod must use.

`rbac.enabled` controls creation of the Roles and bindings required by the hub.
It does not control service-account selection. When RBAC is managed outside the
chart, set `rbac.enabled` to `false` and bind the required permissions to
`hub.serviceAccount.name` separately.

Annotations such as an AWS IAM role can be applied to the hub account through
`hub.serviceAccount.annotations`.

### Authentication

The chart defaults to JupyterHub's dummy authenticator:

```yaml
auth:
  authenticator_class: jupyterhub.auth.DummyAuthenticator
  allowAll: true
  adminUsers: []
  cognito:
    enabled: false
```

These defaults are suitable only for evaluation and local development. A real
deployment must configure an appropriate authenticator and explicit access
policy.

Cognito support is configured under `auth.cognito`. Do not commit client
secrets to a normal values file. Inject them with the deployment's secret
management system.

### Secrets

The chart can create Kubernetes secrets from values under `secrets`, including
the proxy authentication token, vault encryption key, Cognito values, API keys,
and per-node environment data.

Values passed directly to Helm can be stored in Helm release history. For a
production deployment, prefer externally managed Kubernetes secrets and use
`hub.extraEnvFrom` where applicable. Never commit real secret values to this
repository.

The vault encryption key must be a Fernet key. Generate one with:

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

### Storage

Hub working storage is configured under `persistence`. Shared user storage is
configured under `userStorage`.

Review these values for the target cluster:

- `enabled`
- `storageClass`
- `size`
- `accessMode`
- PVC name and mount paths
- Optional selectors and annotations

The generic user-storage default is `ReadWriteMany`. Many local or single-node
provisioners support only `ReadWriteOnce`, so the local overlay changes this
setting.

### Ingress and TLS

Ingress is disabled by default. A basic configuration is:

```yaml
ingress:
  enabled: true
  sslEnabled: true
  className: nginx
  hosts:
    proxy: hub.example.org
    vite: ""
  tls:
    - secretName: beakerhub-tls
      hosts:
        - hub.example.org
        - "*.hub.example.org"
```

Notebook sessions use subdomains. The certificate and DNS configuration must
cover the required notebook hostnames.

### Idle culling

Idle-session cleanup is configured under `culling`:

- `enabled`
- `interval`
- `idleLimit`
- `shutdownTimeout`
- `removeStoppedServers`

### Scheduling and resources

The proxy, hub, notebook, and task sections expose resource settings. Proxy,
hub, notebook, and task pods also support the relevant node selectors and
tolerations. Set these values to match cluster capacity and scheduling policy.

## Upgrade

Render the proposed configuration before applying it:

```bash
helm template beakerhub ./helm/beakerhub \
  --namespace beakerhub \
  --values /path/to/my-values.yaml
```

Then upgrade:

```bash
helm upgrade beakerhub ./helm/beakerhub \
  --namespace beakerhub \
  --values /path/to/my-values.yaml
```

Inspect history or roll back with:

```bash
helm history beakerhub --namespace beakerhub
helm rollback beakerhub --namespace beakerhub
```

## Uninstall

```bash
helm uninstall beakerhub --namespace beakerhub
```

Helm does not necessarily delete persistent volume claims. Review retained PVCs
before deleting them.

## Troubleshooting

Start with the release, pod, service, and event state:

```bash
helm status beakerhub --namespace beakerhub
kubectl get pods,services,ingress,pvc --namespace beakerhub
kubectl get events --namespace beakerhub --sort-by=.lastTimestamp
```

Inspect component logs:

```bash
kubectl logs -l app.kubernetes.io/component=hub \
  --namespace beakerhub --tail=100
kubectl logs -l app.kubernetes.io/component=proxy \
  --namespace beakerhub --tail=100
```

For image-pull failures, verify the rendered registry, repository, tag, and pull
secret. For storage failures, verify the requested access mode against the
storage provisioner. For ingress or WebSocket failures, verify wildcard DNS and
TLS coverage for notebook subdomains.
