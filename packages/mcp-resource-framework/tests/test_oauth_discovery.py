"""Tests for OAuth 2.0 discovery endpoint registration."""

from __future__ import annotations

from starlette.requests import Request
from starlette.testclient import TestClient

from mcp_resource_framework.oauth_discovery import (
    CorsHeaderBuilder,
    register_oauth_discovery_endpoints,
)

SERVER_URL = "https://mcp.example.com"
AUTH_URL = "https://auth.example.com"
SCOPES = ["read"]


def _make_app_with_discovery(
    cors_header_builder: CorsHeaderBuilder | None = None,
    scopes: list[str] | None = None,
    resource_documentation: str | None = None,
) -> TestClient:
    """Create a minimal Starlette app with OAuth discovery endpoints via FastMCP."""
    from mcp.server.fastmcp.server import FastMCP

    app = FastMCP(name="test-server")
    register_oauth_discovery_endpoints(
        app,
        server_url=SERVER_URL,
        auth_server_public_url=AUTH_URL,
        scopes=scopes or SCOPES,
        cors_header_builder=cors_header_builder,
        resource_documentation=resource_documentation,
    )

    # Get the underlying Starlette app
    starlette_app = app.streamable_http_app()
    return TestClient(starlette_app)


class TestProtectedResourceMetadata:
    """RFC 9908: Protected Resource Metadata endpoints."""

    def test_main_endpoint(self) -> None:
        client = _make_app_with_discovery()
        resp = client.get("/.well-known/oauth-protected-resource")
        assert resp.status_code == 200
        data = resp.json()
        assert data["resource"] == SERVER_URL
        assert data["authorization_servers"] == [AUTH_URL]
        assert data["scopes_supported"] == SCOPES
        assert data["bearer_methods_supported"] == ["header"]

    def test_mcp_path_endpoint(self) -> None:
        client = _make_app_with_discovery()
        resp = client.get("/mcp/.well-known/oauth-protected-resource")
        assert resp.status_code == 200
        data = resp.json()
        assert data["resource"] == SERVER_URL
        assert data["authorization_servers"] == [AUTH_URL]

    def test_trailing_slash_stripped(self) -> None:
        """server_url and auth_server_public_url trailing slashes are stripped."""
        from mcp.server.fastmcp.server import FastMCP

        app = FastMCP(name="test")
        register_oauth_discovery_endpoints(
            app,
            server_url="https://mcp.example.com/",
            auth_server_public_url="https://auth.example.com/",
        )
        client = TestClient(app.streamable_http_app())
        resp = client.get("/.well-known/oauth-protected-resource")
        data = resp.json()
        assert data["resource"] == "https://mcp.example.com"
        assert data["authorization_servers"] == ["https://auth.example.com"]

    def test_resource_documentation_included_when_provided(self) -> None:
        client = _make_app_with_discovery(
            resource_documentation="https://mcp.example.com/docs"
        )
        resp = client.get("/.well-known/oauth-protected-resource")
        assert resp.json()["resource_documentation"] == "https://mcp.example.com/docs"

    def test_resource_documentation_on_mcp_path(self) -> None:
        client = _make_app_with_discovery(
            resource_documentation="https://mcp.example.com/docs"
        )
        resp = client.get("/mcp/.well-known/oauth-protected-resource")
        assert resp.json()["resource_documentation"] == "https://mcp.example.com/docs"

    def test_resource_documentation_omitted_by_default(self) -> None:
        client = _make_app_with_discovery()
        assert "resource_documentation" not in client.get(
            "/.well-known/oauth-protected-resource"
        ).json()


class TestAuthorizationServerMetadata:
    """RFC 8414: Authorization Server Metadata endpoints."""

    def test_main_endpoint(self) -> None:
        client = _make_app_with_discovery()
        resp = client.get("/.well-known/oauth-authorization-server")
        assert resp.status_code == 200
        data = resp.json()
        assert data["issuer"] == AUTH_URL
        assert data["authorization_endpoint"] == f"{AUTH_URL}/authorize"
        assert data["token_endpoint"] == f"{AUTH_URL}/token"
        assert data["introspection_endpoint"] == f"{AUTH_URL}/introspect"
        assert data["registration_endpoint"] == f"{AUTH_URL}/register"
        assert data["scopes_supported"] == SCOPES
        assert "S256" in data["code_challenge_methods_supported"]

    def test_mcp_path_endpoint_includes_resource(self) -> None:
        client = _make_app_with_discovery()
        resp = client.get("/.well-known/oauth-authorization-server/mcp")
        assert resp.status_code == 200
        data = resp.json()
        assert data["issuer"] == AUTH_URL
        assert data["resource"] == SERVER_URL

    def test_revocation_endpoint(self) -> None:
        client = _make_app_with_discovery()
        resp = client.get("/.well-known/oauth-authorization-server")
        data = resp.json()
        assert data["revocation_endpoint"] == f"{AUTH_URL}/revoke"

    def test_grant_types(self) -> None:
        client = _make_app_with_discovery()
        resp = client.get("/.well-known/oauth-authorization-server")
        data = resp.json()
        assert "authorization_code" in data["grant_types_supported"]
        assert "refresh_token" in data["grant_types_supported"]
        assert (
            "urn:ietf:params:oauth:grant-type:device_code" in data["grant_types_supported"]
        )


class TestOpenIDConfiguration:
    """OpenID Connect Discovery endpoint."""

    def test_aliases_oauth_metadata(self) -> None:
        client = _make_app_with_discovery()
        resp = client.get("/.well-known/openid-configuration")
        assert resp.status_code == 200
        data = resp.json()
        assert data["issuer"] == AUTH_URL
        assert data["authorization_endpoint"] == f"{AUTH_URL}/authorize"
        assert data["registration_endpoint"] == f"{AUTH_URL}/register"


class TestCorsSupport:
    """CORS header builder integration."""

    @staticmethod
    def _mock_cors_builder(request: Request) -> dict[str, str]:
        return {
            "Access-Control-Allow-Origin": "https://app.example.com",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
        }

    def test_cors_headers_on_auth_server_metadata(self) -> None:
        client = _make_app_with_discovery(cors_header_builder=self._mock_cors_builder)
        resp = client.get("/.well-known/oauth-authorization-server")
        assert resp.status_code == 200
        assert resp.headers["Access-Control-Allow-Origin"] == "https://app.example.com"

    def test_cors_options_preflight(self) -> None:
        client = _make_app_with_discovery(cors_header_builder=self._mock_cors_builder)
        resp = client.options("/.well-known/oauth-authorization-server")
        assert resp.status_code == 200
        assert resp.headers["Access-Control-Allow-Origin"] == "https://app.example.com"

    def test_cors_headers_on_openid_config(self) -> None:
        client = _make_app_with_discovery(cors_header_builder=self._mock_cors_builder)
        resp = client.get("/.well-known/openid-configuration")
        assert resp.headers["Access-Control-Allow-Origin"] == "https://app.example.com"

    def test_cors_headers_on_mcp_auth_server_metadata(self) -> None:
        client = _make_app_with_discovery(cors_header_builder=self._mock_cors_builder)
        resp = client.get("/.well-known/oauth-authorization-server/mcp")
        assert resp.headers["Access-Control-Allow-Origin"] == "https://app.example.com"

    def test_cors_options_on_mcp_auth_server_metadata(self) -> None:
        client = _make_app_with_discovery(cors_header_builder=self._mock_cors_builder)
        resp = client.options("/.well-known/oauth-authorization-server/mcp")
        assert resp.status_code == 200
        assert resp.headers["Access-Control-Allow-Origin"] == "https://app.example.com"

    def test_no_cors_by_default(self) -> None:
        client = _make_app_with_discovery()
        resp = client.get("/.well-known/oauth-authorization-server")
        assert "Access-Control-Allow-Origin" not in resp.headers

    def test_no_cors_on_mcp_endpoint_by_default(self) -> None:
        client = _make_app_with_discovery()
        resp = client.get("/.well-known/oauth-authorization-server/mcp")
        assert "Access-Control-Allow-Origin" not in resp.headers


class TestCustomScopes:
    """Custom scope configuration."""

    def test_custom_scopes_in_protected_resource(self) -> None:
        client = _make_app_with_discovery(scopes=["read", "write", "admin"])
        resp = client.get("/.well-known/oauth-protected-resource")
        assert resp.json()["scopes_supported"] == ["read", "write", "admin"]

    def test_custom_scopes_in_auth_metadata(self) -> None:
        client = _make_app_with_discovery(scopes=["read", "write"])
        resp = client.get("/.well-known/oauth-authorization-server")
        assert resp.json()["scopes_supported"] == ["read", "write"]

    def test_default_scopes(self) -> None:
        from mcp.server.fastmcp.server import FastMCP

        app = FastMCP(name="test")
        register_oauth_discovery_endpoints(
            app,
            server_url=SERVER_URL,
            auth_server_public_url=AUTH_URL,
        )
        client = TestClient(app.streamable_http_app())
        resp = client.get("/.well-known/oauth-protected-resource")
        assert resp.json()["scopes_supported"] == ["read"]
