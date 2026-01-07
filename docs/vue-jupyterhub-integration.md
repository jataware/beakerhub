# Vue SPA + JupyterHub Integration

This document explains how BeakerHub integrates its Vue.js single-page application (SPA) with JupyterHub while preserving JupyterHub's native functionality.

## Overview

BeakerHub uses custom Tornado handlers to serve the Vue SPA alongside JupyterHub's built-in pages. This approach allows the Vue app to handle the main user interface while leaving JupyterHub's admin interface, authentication, and API intact.

## Why Custom Handlers?

**The Problem**: Early attempts used `ConfiguredVuePageLoader` to override all Jinja2 templates, which broke:
- JupyterHub's admin interface (`/hub/admin`)
- Token management pages
- User management
- Any page expecting specific templates

**The Solution**: Custom Tornado handlers that:
1. Serve the Vue SPA at specific routes (e.g., `/app/*`)
2. Leave JupyterHub's native routes intact
3. Inject configuration dynamically into HTML
4. Handle authentication via JupyterHub's `@web.authenticated` decorator

## Request Routing

BeakerHub serves from root (`/`) by default. Here's how requests are routed:

| Path | Handler | Purpose |
|------|---------|---------|
| `/` | `VueSPAHandler` | Serves Vue SPA with client-side routing |
| `/*` | `VueSPAHandler` | Serves Vue SPA with client-side routing |
| `/login` | JupyterHub | OAuth login flow (Cognito) |
| `/logout` | JupyterHub | Logout handler |
| `/oauth_callback` | JupyterHub | OAuth callback |
| `/api/*` | JupyterHub/Proxy | API endpoints (proxied to beaker-kernel) |
| `/home` | `VueHomeHandler` | Redirects to `/app/` |
| `/static/*` | `StaticFileHandler` | Serves Vue build artifacts |

**Custom Prefix**: To serve from a path like `/hub/`, set `c.JupyterHub.base_url = '/hub/'` in `jupyterhub_config.py`.

## Key Components

### Backend (`src/beakerhub/`)

**`handlers.py`** - Custom Tornado handlers
- **VueSPAHandler**: Serves `index.html` from `ui/dist/`, injects config, handles auth, supports catch-all routing for Vue Router

**`app.py`** - Application setup
- Registers custom handlers via `init_handlers()`
- Adds static file handler for `/static/*`
- Configures base URL (default: `/`)

### Frontend (`ui/src/`)

**`router/index.ts`** - Vue Router configuration
- Reads `pathPrefix` from injected config
- Prepends prefix to all routes (e.g., `/app/notebook` or `/hub/app/notebook`)
- Uses HTML5 history mode

## Development vs Production

| Mode | Setup | Description |
|------|-------|-------------|
| **Development** | `cd ui && npm run dev` | Vite dev server on port 8080 with HMR. Proxies API calls to BeakerHub (port 8000). No build needed. |
| **Production** | `cd ui && npm run build` | Build to `ui/dist/`. JupyterHub serves via `VueSPAHandler`. |

## Configuration Injection

The Vue app receives runtime configuration through a script tag injected into `index.html`:

```html
<script id="site-config" type="application/json">
{"pathPrefix": "/", "username": "alice", "footer": {"contactEmail": "contact@beakerhub.com"}}
</script>
```

`VueSPAHandler` injects JSON containing:
- `pathPrefix`: Base URL for routing (e.g., `/` or `/hub/`)
- `username`: Current authenticated user
- `_xsrf`: JupyterHub's cross-site request forgery token
- `footer`: Runtime footer branding and link configuration

The Vue entry point resolves defaults and provides this object to the component
tree. The router consumes `pathPrefix`, and the footer consumes `footer`. Helm
deployments configure the footer through `hub.footer`; direct deployments can
set `c.BeakerHub.footer`.

## Authentication

BeakerHub uses **cookie-based authentication** via JupyterHub's `@web.authenticated` decorator:
1. JupyterHub handles OAuth login (Cognito)
2. Session cookies are set
3. Vue app makes API calls with `credentials: 'include'`

```typescript
// API calls from Vue
fetch('/api/users', {
  credentials: 'include'  // Include session cookies
})
```

## Static Assets

Static assets are served from `/static/*` (or `{base_url}static/*` with custom prefix):

- Vite builds to `ui/dist/static/` (CSS, JS, images)
- JupyterHub serves via `StaticFileHandler`
- Vite's `base` config must match deployment path

**Root deployment** (default):
```typescript
export default defineConfig({ base: '/' })
```

**Custom prefix** (e.g., `/hub/`):
```typescript
export default defineConfig({ base: '/hub/' })
```

## Troubleshooting

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| 404 on static assets | Build artifacts missing or wrong path | Check `beaker_static_path` points to `ui/dist/` and run `npm run build` |
| Vue router refreshes cause 404 | Handler routing misconfigured | Ensure `VueSPAHandler` catch-all route `(.*)` is registered |
| Blank page on load | JavaScript error or config issue | Check browser console. Verify `siteConfig` in HTML source and network tab |
| Authentication loop | Cookie/handler issue | Ensure `@web.authenticated` is on handler and cookies are sent with requests |
| Base URL mismatch | Vite config doesn't match deployment | Update Vite's `base` config to match `c.JupyterHub.base_url` |

## Configuring Base URL

To serve from a custom path like `/hub/` instead of root:

1. **Update `jupyterhub_config.py`**:
   ```python
   c.JupyterHub.base_url = '/hub/'  # Or any prefix
   c.CognitoAuthenticator.oauth_callback_url = "http://localhost:8000/hub/oauth_callback"
   ```

2. **Update Vite config** (for production):
   ```typescript
   export default defineConfig({ base: '/hub/' })
   ```

3. **Rebuild**:
   ```bash
   cd ui && npm run build
   ```

The Vue Router automatically adjusts routes based on the injected `pathPrefix`.
