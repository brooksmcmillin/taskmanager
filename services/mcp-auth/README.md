# MCP Authorization Server

OAuth 2.0 authorization server for the TaskManager MCP ecosystem. This server handles authentication flows for MCP clients (like Claude) and issues tokens for accessing the MCP Resource Server.

## Overview

The authorization server acts as an intermediary between MCP clients and TaskManager:

1. MCP clients register dynamically and initiate OAuth flows
2. Users authenticate via TaskManager's OAuth consent screen
3. The auth server issues MCP-specific tokens after successful authentication
4. The resource server validates tokens via introspection

## Features

- **Dynamic Client Registration** (RFC 7591) - Automatic client credential generation
- **Authorization Code Flow with PKCE** - Secure browser-based authentication
- **Device Authorization Grant** (RFC 8628) - CLI and limited-input device support
- **Token Introspection** (RFC 7662) - Real-time token validation for resource servers
- **OAuth Discovery** (RFC 8414) - Auto-configuration for MCP clients

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TASKMANAGER_CLIENT_ID` | OAuth client ID registered in TaskManager | Required |
| `TASKMANAGER_CLIENT_SECRET` | OAuth client secret | Required |
| `TASKMANAGER_OAUTH_HOST` | TaskManager API URL | `http://backend:8000` |
| `MCP_AUTH_SERVER_URL` | Public URL of this auth server | Required |
| `MCP_SERVER` | URL of the MCP resource server | `http://mcp-resource:8001` |
| `DATABASE_URL` | PostgreSQL connection string (for persistent token storage) | Optional |

### Command Line Options

```bash
python -m mcp_auth.auth_server [OPTIONS]

Options:
  --port INTEGER              Server port (default: 9000)
  --taskmanager-url TEXT      TaskManager OAuth host URL
  --public-url TEXT           Public URL for this server
  --mcp-server TEXT           MCP resource server URL
```

## OAuth Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /.well-known/oauth-authorization-server` | OAuth discovery metadata |
| `POST /register` | Dynamic client registration |
| `GET /authorize` | Authorization endpoint |
| `POST /token` | Token exchange |
| `POST /introspect` | Token introspection |
| `POST /device/code` | Device authorization request |
| `GET /oauth/callback` | TaskManager OAuth callback |

## Authentication Flow

```
MCP Client                Auth Server              TaskManager
    │                          │                        │
    │──── Register Client ────►│                        │
    │◄─── Client Credentials ──│                        │
    │                          │                        │
    │──── Authorization Req ──►│                        │
    │                          │──── Redirect User ────►│
    │                          │                        │
    │                          │◄─── Auth Code ─────────│
    │                          │                        │
    │◄─── MCP Access Token ────│                        │
    │                          │                        │
```

## Development

### Running Locally

```bash
cd services/mcp-auth
uv sync
uv run python -m mcp_auth.auth_server \
  --port 9000 \
  --taskmanager-url http://localhost:8000
```

### Running with Docker

```bash
docker compose up mcp-auth
```

### Project Structure

```
mcp_auth/
├── __init__.py
├── auth_server.py              # Main server entry point
├── taskmanager_oauth_provider.py  # OAuth provider implementation
├── token_storage.py            # Token persistence (memory/PostgreSQL)
└── config.py                   # Token TTL configuration
```

## Token Storage

The server supports two token storage modes:

- **In-Memory** (default) - Tokens stored in memory, lost on restart
- **PostgreSQL** - Persistent storage when `DATABASE_URL` is configured

For production deployments, configure PostgreSQL storage for token persistence across restarts.

## Troubleshooting

### Invalid redirect_uri Error

Ensure the OAuth client in TaskManager has the correct redirect URI:
```
https://your-auth-server.com/oauth/callback
```

### Token Introspection Failing

Check that the resource server can reach the introspection endpoint. For Docker deployments, use internal hostnames (`http://mcp-auth:9000`).

### OAuth Loop (Keeps Re-authorizing)

This usually indicates token validation failures. Check:
1. Auth server logs for introspection errors
2. Network connectivity between containers
3. Token expiration settings
