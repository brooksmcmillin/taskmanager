# MCP Resource Server

Model Context Protocol (MCP) server providing OAuth-protected access to TaskManager functionality. This server exposes tools that AI assistants like Claude can use to manage tasks and projects.

## Overview

The resource server provides MCP tools for task management, protected by OAuth 2.0 authentication. It validates tokens via the MCP Authorization Server's introspection endpoint.

## MCP Tools

This server exposes 43 tools for task management, organized by resource type:

### Task Management

| Tool | Description |
|------|-------------|
| `get_tasks` | Retrieve tasks with filtering options (status, date range, category, priority) |
| `create_task` | Create a new task or subtask with optional due date and category |
| `create_tasks` | Create multiple tasks in a single batch request (up to 50 tasks) |
| `update_task` | Update an existing task (status, priority, due date, etc.) |
| `delete_task` | Delete a task (soft delete, can be restored) |
| `complete_task` | Mark a task as completed |
| `get_task` | Get full details of a single task by ID |
| `search_tasks` | Full-text search across task titles and descriptions |

### Task Details & Comments

| Tool | Description |
|------|-------------|
| `list_task_comments` | List all comments on a task |
| `add_task_comment` | Add a comment to a task |
| `list_task_attachments` | List all attachments for a task |

### Task Dependencies

| Tool | Description |
|------|-------------|
| `list_dependencies` | List all tasks that must be completed before this task |
| `add_dependency` | Add a dependency relationship between two tasks |

### Agent Integration

| Tool | Description |
|------|-------------|
| `get_agent_tasks` | Get tasks filtered for AI agent processing (actionable, unclassified, or due today) |
| `classify_task` | Classify a task with action type, autonomy tier, and agent actionability |
| `set_agent_status` | Set the agent processing status for a task (pending, in_progress, completed, blocked, needs_human) |
| `add_agent_note` | Add notes to a task for agent context and research findings |

### Projects

| Tool | Description |
|------|-------------|
| `create_project` | Create a new project for organizing tasks |

### Wiki Pages

| Tool | Description |
|------|-------------|
| `create_wiki_page` | Create a new wiki page with optional parent for hierarchy |
| `get_wiki_page` | Get a wiki page by slug or numeric ID |
| `update_wiki_page` | Update wiki page content, title, or slug |
| `delete_wiki_page` | Soft-delete a wiki page |
| `search_wiki_pages` | Search wiki pages by title or content |
| `link_wiki_page_to_task` | Link a wiki page to a task (bidirectional association) |
| `batch_link_wiki_page_to_tasks` | Link a wiki page to multiple tasks in one request |
| `get_wiki_page_linked_tasks` | Get all tasks linked to a wiki page |
| `get_task_wiki_pages` | Get all wiki pages linked to a task |

### Snippets (Dated Log Entries)

| Tool | Description |
|------|-------------|
| `list_snippets` | List snippets with optional filtering (category, date range, tags) |
| `create_snippet` | Create a new snippet (dated log entry for standups, TIL, meeting notes, etc.) |
| `get_snippet` | Get a snippet by ID |
| `update_snippet` | Update snippet content, category, or tags |
| `delete_snippet` | Soft-delete a snippet |

### Articles & RSS Feeds

| Tool | Description |
|------|-------------|
| `list_articles` | List news articles with filtering (read status, feed type, featured sources) |
| `get_article` | Get a single article by ID |
| `mark_article_read` | Mark an article as read or unread |
| `rate_article` | Rate an article (good, bad, not_interested) |
| `list_feed_sources` | List RSS/Atom feed sources with activity metadata |
| `create_feed_source` | Create a new RSS/Atom feed source (admin only) |
| `update_feed_source` | Update a feed source configuration (admin only) |
| `toggle_feed_source` | Enable or disable a feed source (admin only) |
| `delete_feed_source` | Delete a feed source and cascade-delete its articles (admin only) |
| `force_fetch_feed` | Immediately fetch articles from a feed source (admin only) |

### Unified Search

| Tool | Description |
|------|-------------|
| `unified_search` | Search across tasks, wiki pages, snippets, and articles simultaneously |

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_AUTH_SERVER` | Internal URL of auth server | `http://mcp-auth:9000` |
| `MCP_AUTH_SERVER_PUBLIC_URL` | Public URL of auth server | Required |
| `MCP_SERVER_URL` | Public URL of this server | Required |
| `TASKMANAGER_OAUTH_HOST` | TaskManager API URL | `http://backend:8000` |

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
services/mcp-resource/
├── mcp_resource/
│   ├── __init__.py     # Package initialization
│   └── server.py       # Main MCP server with all 43 tool definitions
├── tests/
│   ├── conftest.py     # pytest configuration and shared fixtures
│   ├── test_server.py  # Server initialization tests
│   ├── test_mcp_tools.py # Tool functionality tests
│   ├── test_token_verifier.py # Token validation tests
│   └── test_lakera_guard.py # Security guard tests
├── Dockerfile          # Docker image configuration
├── pyproject.toml      # Python project metadata and dependencies
└── README.md           # This file
```

**Key Files:**
- `mcp_resource/server.py` (2762 lines) - Defines all 43 MCP tools using FastMCP framework
- `pyproject.toml` - Declares Python 3.13+ requirement and dependencies
- Tests verify tool functionality, token validation, and security guards

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
