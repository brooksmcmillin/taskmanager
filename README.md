# TaskManager

A modern task management platform with OAuth 2.0 API access and MCP (Model Context Protocol) integration for AI-powered workflows.

## Overview

TaskManager is a full-stack application consisting of:

- **Frontend** - SvelteKit-based task management UI
- **Backend** - FastAPI REST API with PostgreSQL
- **MCP Authorization Server** - OAuth 2.0 server for MCP client authentication
- **MCP Resource Server** - MCP tools for AI assistants to manage tasks
- **Python SDK** - Client library for programmatic API access

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         External Clients                            │
│  (Claude, MCP Inspector, SDK consumers, Web browsers)               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Nginx Reverse Proxy                         │
│                    (SSL termination, CORS headers)                  │
└─────────────────────────────────────────────────────────────────────┘
          │                         │                        │
          ▼                         ▼                        ▼
┌─────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│   Frontend      │   │  MCP Auth Server    │   │ MCP Resource Server │
│  (Port 3000)    │   │    (Port 9000)      │   │    (Port 8001)      │
│                 │   │                     │   │                     │
│  - SvelteKit UI │   │  - OAuth 2.0 flows  │   │  - MCP tools        │
│  - API proxy    │   │  - Token issuance   │   │  - Token validation │
└────────┬────────┘   │  - Client registry  │   │  - Task operations  │
         │            └─────────────────────┘   └──────────┬──────────┘
         │                                                  │
         │            ┌─────────────────┐                  │
         └───────────►│    Backend      │◄─────────────────┘
                      │   (Port 8000)   │
                      │                 │
                      │  - FastAPI REST │
                      │  - User auth    │
                      │  - OAuth server │
                      └────────┬────────┘
                               │
                               ▼
                      ┌─────────────────┐
                      │   PostgreSQL    │
                      │   (Port 5432)   │
                      └─────────────────┘
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 22+ (for local development)
- Python 3.12+ (backend and SDK)
- Python 3.13+ (for MCP servers)

### Running with Docker Compose

1. Clone the repository and set up environment:
```bash
git clone <repository-url>
cd taskmanager
cp .env.example .env
# Edit .env with your configuration
```

2. Start all services:
```bash
docker compose up -d
```

3. Run database migrations:
```bash
cd services/backend
uv sync
uv run alembic upgrade head
```

4. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - MCP Resource Server: http://localhost:8001
   - MCP Auth Server: http://localhost:9000

### Initial Setup

1. Register a user account at http://localhost:3000/register
2. Create an OAuth client for MCP authentication at http://localhost:3000/settings
3. Configure your MCP client (Claude, etc.) to connect to the resource server

## Project Structure

```
taskmanager/
├── services/
│   ├── frontend/             # SvelteKit task management UI
│   ├── backend/              # FastAPI REST API
│   ├── mcp-auth/             # OAuth 2.0 authorization server for MCP
│   ├── mcp-resource/         # MCP resource server with tools
│   └── db/                   # Database configuration & SSL certs
├── packages/
│   └── taskmanager-sdk/      # Python SDK for TaskManager API
├── docker-compose.yml        # Container orchestration
└── .env                      # Environment configuration
```

## Services

### Frontend (SvelteKit)

The task management UI built with SvelteKit, featuring:
- User authentication with session management
- Project and task management interface
- Real-time updates and responsive design

**[View Frontend Documentation](services/frontend/README.md)**

### Backend (FastAPI)

The REST API built with FastAPI, featuring:
- Async SQLAlchemy ORM with PostgreSQL
- Full API with Pydantic validation
- Session-based authentication
- Rate limiting and security features

**[View Backend Documentation](services/backend/README.md)**

### MCP Authorization Server

OAuth 2.0 authorization server that enables MCP clients to authenticate:
- Dynamic client registration (RFC 7591)
- Authorization Code flow with PKCE
- Device Authorization Grant (RFC 8628)
- Token introspection (RFC 7662)

**[View MCP Auth Documentation](services/mcp-auth/README.md)**

### MCP Resource Server

MCP server providing AI assistants with task management tools:
- `get_all_projects()` - List all projects
- `get_all_tasks()` - List all tasks
- `create_task()` - Create new tasks
- OAuth-protected endpoints

**[View MCP Resource Documentation](services/mcp-resource/README.md)**

### Python SDK

Client library for programmatic access to the TaskManager API:
- Session-based and OAuth authentication
- Full API coverage for projects, todos, and OAuth
- Type hints and comprehensive error handling

**[View SDK Documentation](packages/taskmanager-sdk/README.md)**

## Environment Variables

Key configuration options (see `.env.example` for full list):

| Variable | Description |
|----------|-------------|
| `POSTGRES_DB` | PostgreSQL database name |
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `TASKMANAGER_CLIENT_ID` | OAuth client ID for MCP servers |
| `TASKMANAGER_CLIENT_SECRET` | OAuth client secret for MCP servers |
| `MCP_AUTH_SERVER_PUBLIC_URL` | Public URL for MCP auth server |
| `MCP_SERVER_URL` | Public URL for MCP resource server |

## Development

### Running Services Locally

**Frontend:**
```bash
cd services/frontend
npm install
npm run dev
```

**Backend:**
```bash
cd services/backend
uv sync
uv run uvicorn app.main:app --reload
```

**MCP Servers:**
```bash
cd services/mcp-auth
uv sync
uv run python -m mcp_auth.auth_server --port 9000

cd services/mcp-resource
uv sync
uv run python -m mcp_resource.server --port 8001
```

### Running Tests

```bash
# Frontend tests (Playwright)
cd services/frontend && npm test

# Backend tests
cd services/backend && uv run pytest

# SDK tests
cd packages/taskmanager-sdk && uv run pytest
```

## Security Notice

This application is designed for educational and personal use. While it implements standard security practices including OAuth 2.0, PKCE, bcrypt password hashing, and secure session management, it has not undergone comprehensive security auditing for production environments. Use appropriate caution if deploying publicly.

## License

MIT License
