# MCP Resource Server

Model Context Protocol (MCP) server providing OAuth-protected access to TaskManager functionality. This server exposes tools that AI assistants like Claude can use to manage tasks and projects.

## Overview

The resource server provides MCP tools for task management, protected by OAuth 2.0 authentication. It validates tokens via the MCP Authorization Server's introspection endpoint.

## MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_time()` | Get current server time | None |
| `get_all_projects()` | Retrieve all projects | None |
| `get_all_tasks()` | Retrieve all tasks | None |
| `create_task()` | Create a new task | `title`, `project_id`, `description`, `priority`, `due_date` |

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_AUTH_SERVER` | Internal URL of auth server | `http://mcp-auth:9000` |
| `MCP_AUTH_SERVER_PUBLIC_URL` | Public URL of auth server | Required |
| `MCP_SERVER_URL` | Public URL of this server | Required |
| `TASKMANAGER_OAUTH_HOST` | TaskManager API URL | `http://app:4321` |

### Command Line Options

```bash
python -m mcp_resource.server [OPTIONS]

Options:
  --port INTEGER                Server port (default: 8001)
  --auth-server TEXT            Internal auth server URL
  --auth-server-public-url TEXT Public auth server URL
  --public-url TEXT             Public URL for this server
```

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /.well-known/oauth-protected-resource` | Resource server metadata |
| `POST /mcp` | MCP protocol endpoint (Streamable HTTP) |
| `GET /mcp` | MCP SSE endpoint |

## Connecting MCP Clients

### Claude Desktop / Claude Code

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "taskmanager": {
      "url": "https://your-mcp-server.com/mcp/",
      "transport": "streamable-http"
    }
  }
}
```

### MCP Inspector

1. Open MCP Inspector in your browser
2. Enter the server URL with trailing slash: `https://your-mcp-server.com/mcp/`
3. Click "Connect" to initiate OAuth flow
4. Authenticate via TaskManager
5. Use the available tools

**Important**: The trailing slash is required for Streamable HTTP transport.

## Development

### Running Locally

```bash
cd services/mcp-resource
uv sync
uv run python -m mcp_resource.server \
  --port 8001 \
  --auth-server http://localhost:9000 \
  --auth-server-public-url http://localhost:9000
```

### Running with Docker

```bash
docker compose up mcp-resource
```

### Project Structure

```
mcp_resource/
├── __init__.py
├── server.py           # Main MCP server with tool definitions
├── token_verifier.py   # OAuth token introspection
└── config.py           # Configuration settings
```

## Token Validation

The server validates OAuth tokens using RFC 7662 Token Introspection:

1. Client sends request with Bearer token
2. Server calls auth server's `/introspect` endpoint
3. Auth server returns token metadata (active, scopes, expiration)
4. Server grants or denies access based on response

### Allowed Introspection Endpoints

For security, the token verifier only accepts introspection endpoints from:
- `https://` URLs
- `http://localhost` or `http://127.0.0.1`
- `http://mcp-auth:` (Docker internal network)

## Troubleshooting

### 401 Unauthorized on All Requests

Check that:
1. The auth server is reachable from the resource server
2. The introspection endpoint URL is correctly configured
3. Tokens haven't expired

### "Rejecting introspection endpoint with unsafe scheme"

The token verifier is blocking an HTTP endpoint. For Docker deployments, ensure you're using the internal Docker hostname (`http://mcp-auth:9000`).

### 307 Redirect on POST /mcp

Missing trailing slash in URL. Use `https://your-server.com/mcp/` (with trailing slash).

### Tools Not Appearing

Ensure the OAuth flow completed successfully and the token has the required scopes (`read` for listing, `write` for creating tasks).
