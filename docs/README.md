# BeakerHub Documentation

## Getting started

- [Project README](../README.md) — overview, prerequisites, architecture, and
  common commands.
- [Quick Start](QUICKSTART.md) — create and use a local kind deployment.
- [Local TLS](local-tls.md) — trust development certificates for BeakerHub and
  notebook subdomains.

## Development

- [Development Guide](DEVELOPMENT.md) — backend, frontend, images, Helm,
  testing, and debugging.
- [Contributing Guide](../CONTRIBUTING.md) — contribution workflow and project
  standards.

## Deployment and operations

- [Helm and kind tooling](../helm/README.md) — local cluster infrastructure and
  Make targets.
- [Helm chart reference](../helm/beakerhub/README.md) — chart installation,
  values, security, and production considerations.

The public repository contains a generic chart and local kind workflow. Keep
cloud-account settings, real hostnames, credentials, and environment-specific
values in a separate deployment repository.

## Architecture and integration

- [Vue SPA and JupyterHub Integration](vue-jupyterhub-integration.md) — request
  routing, runtime configuration, authentication, and static assets.

## Where to make documentation changes

| Change | Primary document |
| --- | --- |
| First-run or prerequisite changes | `docs/QUICKSTART.md` |
| Common project commands or repository layout | `README.md` |
| Contributor development workflow | `docs/DEVELOPMENT.md` |
| Local kind, ingress, DNS, or TLS tooling | `helm/README.md` |
| Generic chart values or templates | `helm/beakerhub/README.md` |
| Contribution policy | `CONTRIBUTING.md` |

Update commands, paths, and cross-links when their implementation changes.
Examples must use generic hostnames and placeholders and must not contain
credentials or private deployment details.
