# SPDX-FileCopyrightText: 2024-present Jataware Corp
#
# SPDX-License-Identifier: MIT
"""
Integration tests for BeakerHub API endpoints.

These tests run against a deployed BeakerHub instance in a kind cluster.
"""

import pytest


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_proxy_health_check(self, api_client, test_cluster):
        """Proxy health check endpoint should return 200."""
        response = api_client.get(f"{test_cluster['base_url']}/_chp_healthz")

        assert response.status_code == 200

    def test_hub_health_check(self, api_client, test_cluster):
        """Hub health check should be accessible."""
        response = api_client.get(f"{test_cluster['base_url']}/hub/health")

        # May return 200 or 302 depending on auth state
        assert response.status_code in [200, 302, 401]


class TestAuthEndpoints:
    """Tests for authentication API endpoints."""

    def test_login_get_returns_proceed(self, api_client, test_cluster):
        """GET /api/auth/login should return proceed status for unauthenticated users."""
        response = api_client.get(f"{test_cluster['base_url']}/api/auth/login")

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "proceed"

    def test_login_get_sets_xsrf_header(self, api_client, test_cluster):
        """GET /api/auth/login should set X-SET-XSRFTOKEN header."""
        response = api_client.get(f"{test_cluster['base_url']}/api/auth/login")

        assert response.status_code == 200
        assert "X-SET-XSRFTOKEN" in response.headers or "x-set-xsrftoken" in response.headers

    def test_login_post_invalid_credentials(self, api_client, test_cluster):
        """POST /api/auth/login with invalid credentials should return 403."""
        response = api_client.post(
            f"{test_cluster['base_url']}/api/auth/login",
            json={
                "username": "nonexistent@example.com",
                "password": "InvalidPassword123!",
            },
        )

        assert response.status_code == 403

    def test_logout_clears_session(self, api_client, test_cluster):
        """POST /api/auth/logout should not error."""
        response = api_client.post(f"{test_cluster['base_url']}/api/auth/logout")

        # Should succeed even if not logged in
        assert response.status_code in [200, 204]


class TestUserEndpoints:
    """Tests for user API endpoints."""

    def test_user_api_unauthenticated(self, api_client, test_cluster):
        """GET /api/user should return 401/403 for unauthenticated requests."""
        response = api_client.get(f"{test_cluster['base_url']}/api/user")

        # Should require authentication
        assert response.status_code in [401, 403]

    @pytest.mark.skipif(
        True,  # Skip unless we have authenticated client
        reason="Requires authenticated client"
    )
    def test_user_api_authenticated(self, authenticated_client, test_cluster):
        """GET /api/user should return user info for authenticated users."""
        response = authenticated_client.get(f"{test_cluster['base_url']}/api/user")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data


class TestContextsEndpoints:
    """Tests for BeakerHub contexts API endpoints."""

    def test_contexts_detail_unauthenticated(self, api_client, test_cluster):
        """GET /api/beakerhub/contexts/details may require auth."""
        response = api_client.get(
            f"{test_cluster['base_url']}/api/beakerhub/contexts/details"
        )

        # Depending on configuration, might require auth or be public
        assert response.status_code in [200, 401, 403]

    @pytest.mark.skipif(
        True,  # Skip unless we have authenticated client
        reason="Requires authenticated client"
    )
    def test_contexts_detail_returns_contexts(self, authenticated_client, test_cluster):
        """GET /api/beakerhub/contexts/details should return context data."""
        response = authenticated_client.get(
            f"{test_cluster['base_url']}/api/beakerhub/contexts/details"
        )

        assert response.status_code == 200
        data = response.json()
        # Response should be a dict of contexts
        assert isinstance(data, dict)


class TestStaticAssets:
    """Tests for static asset serving."""

    def test_root_returns_html(self, api_client, test_cluster):
        """Root path should return HTML (Vue SPA)."""
        response = api_client.get(test_cluster['base_url'])

        assert response.status_code == 200
        assert "text/html" in response.headers.get("Content-Type", "")

    def test_static_assets_accessible(self, api_client, test_cluster):
        """Static assets should be served."""
        # First get the index page to find asset URLs
        response = api_client.get(test_cluster['base_url'])

        assert response.status_code == 200
        # The page should contain references to static assets
        assert "script" in response.text.lower() or "link" in response.text.lower()


class TestProxyRouting:
    """Tests for proxy routing behavior."""

    def test_api_routes_to_hub(self, api_client, test_cluster):
        """API routes should be proxied to the hub."""
        # The login endpoint is handled by the hub
        response = api_client.get(f"{test_cluster['base_url']}/api/auth/login")

        assert response.status_code == 200
        # Should have JSON response from hub
        data = response.json()
        assert "status" in data

    def test_nonexistent_api_returns_404(self, api_client, test_cluster):
        """Nonexistent API endpoints should return 404."""
        response = api_client.get(
            f"{test_cluster['base_url']}/api/nonexistent/endpoint"
        )

        assert response.status_code in [404, 401, 403]
