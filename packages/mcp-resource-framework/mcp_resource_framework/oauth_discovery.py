"""OAuth 2.0 discovery endpoints for MCP resource servers.

Registers the standard set of well-known endpoints that MCP clients need
to discover OAuth configuration and complete the authorization flow:

- RFC 9908: Protected Resource Metadata
- RFC 8414: Authorization Server Metadata
- OpenID Connect Discovery (alias for RFC 8414)

Usage:
    from mcp_resource_framework.oauth_discovery import register_oauth_discovery_endpoints

    app = FastMCP(...)
    register_oauth_discovery_endpoints(
        app,
        server_url="https://mcp.example.com",
        auth_server_public_url="https://auth.example.com",
    )
"""

from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp.server import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

# Type for an optional CORS header builder: (request) -> headers dict
CorsHeaderBuilder = Callable[[Request], dict[str, str]]

DEFAULT_SCOPES: tuple[str, ...] = ("read",)


def _build_oauth_metadata(
    auth_base: str,
    scopes: list[str],
    **extra: Any,
) -> dict[str, Any]:
    """Build OAuth 2.0 Authorization Server Metadata (RFC 8414)."""
    metadata: dict[str, Any] = {
        "issuer": auth_base,
        "authorization_endpoint": f"{auth_base}/authorize",
        "token_endpoint": f"{auth_base}/token",
        "introspection_endpoint": f"{auth_base}/introspect",
        "registration_endpoint": f"{auth_base}/register",
        "revocation_endpoint": f"{auth_base}/revoke",
        "scopes_supported": scopes,
        "response_types_supported": ["code"],
        "grant_types_supported": [
            "authorization_code",
            "refresh_token",
            "urn:ietf:params:oauth:grant-type:device_code",
        ],
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
        "code_challenge_methods_supported": ["S256"],
    }
    metadata.update(extra)
    return metadata


def _build_protected_resource_metadata(
    resource_url: str,
    auth_url: str,
    scopes: list[str],
    *,
    resource_documentation: str | None = None,
) -> dict[str, Any]:
    """Build OAuth 2.0 Protected Resource Metadata (RFC 9908)."""
    metadata: dict[str, Any] = {
        "resource": resource_url,
        "authorization_servers": [auth_url],
        "scopes_supported": scopes,
        "bearer_methods_supported": ["header"],
    }
    if resource_documentation:
        metadata["resource_documentation"] = resource_documentation
    return metadata


def register_oauth_discovery_endpoints(
    app: FastMCP,
    *,
    server_url: str,
    auth_server_public_url: str,
    scopes: list[str] | None = None,
    cors_header_builder: CorsHeaderBuilder | None = None,
    resource_documentation: str | None = None,
) -> None:
    """Register all OAuth 2.0 discovery endpoints on a FastMCP app.

    This registers the full set of well-known endpoints that MCP clients
    expect when performing OAuth discovery:

    - GET /.well-known/oauth-protected-resource  (RFC 9908)
    - GET /mcp/.well-known/oauth-protected-resource  (path-specific)
    - GET /.well-known/oauth-authorization-server  (RFC 8414)
    - GET /.well-known/oauth-authorization-server/mcp  (path-specific)
    - GET /.well-known/openid-configuration  (OIDC alias)

    Args:
        app: The FastMCP server instance to register endpoints on.
        server_url: Public URL of this resource server.
        auth_server_public_url: Public URL of the authorization server
            (used in metadata responses so clients know where to register/authorize).
        scopes: Supported OAuth scopes. Defaults to ["read"].
        cors_header_builder: Optional callable that takes a Request and returns
            a dict of CORS headers. When provided, the authorization server
            metadata endpoints will include CORS headers and handle OPTIONS
            preflight requests. When None, no CORS headers are added.
        resource_documentation: Optional URL to resource documentation, included
            in protected resource metadata responses when provided.
    """
    resolved_scopes = list(scopes) if scopes is not None else list(DEFAULT_SCOPES)

    # Strip trailing slashes once
    resource_url = server_url.rstrip("/")
    auth_url = auth_server_public_url.rstrip("/")

    # --- RFC 9908: Protected Resource Metadata ---

    @app.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
    async def oauth_protected_resource(request: Request) -> JSONResponse:  # noqa: ARG001
        """OAuth 2.0 Protected Resource Metadata (RFC 9908)."""
        return JSONResponse(
            _build_protected_resource_metadata(
                resource_url,
                auth_url,
                resolved_scopes,
                resource_documentation=resource_documentation,
            )
        )

    @app.custom_route("/mcp/.well-known/oauth-protected-resource", methods=["GET"])
    async def oauth_protected_resource_mcp(request: Request) -> JSONResponse:  # noqa: ARG001
        """OAuth 2.0 Protected Resource Metadata for /mcp path (RFC 9908)."""
        return JSONResponse(
            _build_protected_resource_metadata(
                resource_url,
                auth_url,
                resolved_scopes,
                resource_documentation=resource_documentation,
            )
        )

    # --- RFC 8414: Authorization Server Metadata ---

    if cors_header_builder:
        _cors = cors_header_builder

        @app.custom_route(
            "/.well-known/oauth-authorization-server", methods=["GET", "OPTIONS"]
        )
        async def oauth_authorization_server(request: Request) -> JSONResponse:
            """OAuth 2.0 Authorization Server Metadata (RFC 8414)."""
            if request.method == "OPTIONS":
                return JSONResponse({}, headers=_cors(request))
            return JSONResponse(
                _build_oauth_metadata(auth_url, resolved_scopes),
                headers=_cors(request),
            )

        @app.custom_route("/.well-known/openid-configuration", methods=["GET", "OPTIONS"])
        async def openid_configuration(request: Request) -> JSONResponse:
            """OpenID Connect Discovery (aliases OAuth Authorization Server Metadata)."""
            if request.method == "OPTIONS":
                return JSONResponse({}, headers=_cors(request))
            return JSONResponse(
                _build_oauth_metadata(auth_url, resolved_scopes),
                headers=_cors(request),
            )

        @app.custom_route(
            "/.well-known/oauth-authorization-server/mcp", methods=["GET", "OPTIONS"]
        )
        async def oauth_authorization_server_mcp(request: Request) -> JSONResponse:
            """Resource-specific OAuth 2.0 Authorization Server Metadata for /mcp."""
            if request.method == "OPTIONS":
                return JSONResponse({}, headers=_cors(request))
            return JSONResponse(
                _build_oauth_metadata(auth_url, resolved_scopes, resource=resource_url),
                headers=_cors(request),
            )
    else:

        @app.custom_route("/.well-known/oauth-authorization-server", methods=["GET"])
        async def oauth_authorization_server(request: Request) -> JSONResponse:  # noqa: ARG001
            """OAuth 2.0 Authorization Server Metadata (RFC 8414)."""
            return JSONResponse(_build_oauth_metadata(auth_url, resolved_scopes))

        @app.custom_route("/.well-known/openid-configuration", methods=["GET"])
        async def openid_configuration(request: Request) -> JSONResponse:  # noqa: ARG001
            """OpenID Connect Discovery (aliases OAuth Authorization Server Metadata)."""
            return JSONResponse(_build_oauth_metadata(auth_url, resolved_scopes))

        @app.custom_route("/.well-known/oauth-authorization-server/mcp", methods=["GET"])
        async def oauth_authorization_server_mcp(request: Request) -> JSONResponse:  # noqa: ARG001
            """Resource-specific OAuth 2.0 Authorization Server Metadata for /mcp."""
            return JSONResponse(
                _build_oauth_metadata(auth_url, resolved_scopes, resource=resource_url)
            )
