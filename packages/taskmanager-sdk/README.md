# TaskManager SDK

A Python SDK for interacting with the TaskManager API. This library provides a clean, Pythonic interface for authentication, project management, todo management, and OAuth 2.0 authorization.

## Installation

```bash
# From PyPI (when published)
pip install taskmanager-sdk

# From source
cd packages/taskmanager-sdk
uv sync
```

## Quick Start

### Session-Based Authentication

```python
from taskmanager_sdk import TaskManagerClient, create_authenticated_client

# Method 1: Manual authentication
client = TaskManagerClient("http://localhost:4321/api")
response = client.login("your_username", "your_password")

if response.success:
    print("Authenticated successfully!")

# Method 2: Create pre-authenticated client (recommended)
try:
    client = create_authenticated_client("your_username", "your_password")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
```

### OAuth 2.0 Client Credentials

For server-to-server authentication:

```python
from taskmanager_sdk import create_client_credentials_client

client = create_client_credentials_client(
    client_id="your_client_id",
    client_secret="your_client_secret",
    base_url="http://localhost:4321/api"
)

# Client is now authenticated with Bearer token
projects = client.get_projects()
```

## Working with Projects

```python
# Get all projects
projects = client.get_projects()
if projects.success:
    for project in projects.data:
        print(f"Project: {project['name']} ({project['color']})")

# Create a new project
new_project = client.create_project(
    name="My New Project",
    color="#FF5722",
    description="A project for important tasks"
)

if new_project.success:
    project_id = new_project.data['id']
    print(f"Created project with ID: {project_id}")
```

## Working with Todos

```python
# Get all todos
todos = client.get_todos()
if todos.success:
    for todo in todos.data:
        print(f"Todo: {todo['title']} (Status: {todo['status']})")

# Create a new todo
new_todo = client.create_todo(
    title="Complete the documentation",
    description="Write comprehensive docs for the new feature",
    priority="high",
    estimated_hours=4.0,
    due_date="2024-12-31T23:59:59Z",
    tags=["documentation", "high-priority"]
)

# Complete a todo
if new_todo.success:
    completion = client.complete_todo(new_todo.data['id'], actual_hours=3.5)
```

## Error Handling

The SDK provides specific exception types for different error conditions:

```python
from taskmanager_sdk import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    NetworkError
)

try:
    client = create_authenticated_client("invalid", "credentials")
except AuthenticationError:
    print("Invalid credentials provided")
except NetworkError:
    print("Could not connect to the server")
```

## API Reference

### TaskManagerClient

The main client class for interacting with the TaskManager API.

```python
TaskManagerClient(base_url="http://localhost:4321/api", session=None, access_token=None)
```

#### Authentication Methods

| Method | Description |
|--------|-------------|
| `login(username, password)` | Authenticate with username/password |
| `register(username, email, password)` | Register a new user account |
| `logout()` | Log out the current session |

#### Project Methods

| Method | Description |
|--------|-------------|
| `get_projects()` | Get all projects |
| `create_project(name, color, description=None)` | Create a new project |
| `get_project(project_id)` | Get a specific project |
| `update_project(project_id, ...)` | Update a project |
| `delete_project(project_id)` | Delete a project |

#### Todo Methods

| Method | Description |
|--------|-------------|
| `get_todos(project_id=None, status=None)` | Get todos with filters |
| `create_todo(title, ...)` | Create a new todo |
| `get_todo(todo_id)` | Get a specific todo |
| `update_todo(todo_id, ...)` | Update a todo |
| `delete_todo(todo_id)` | Delete a todo |
| `complete_todo(todo_id, actual_hours)` | Mark a todo as completed |

#### OAuth Methods

| Method | Description |
|--------|-------------|
| `get_oauth_clients()` | Get OAuth clients for the authenticated user |
| `create_oauth_client(name, redirect_uris, ...)` | Create a new OAuth client |
| `oauth_authorize(...)` | OAuth authorization endpoint |
| `oauth_token(...)` | Exchange authorization codes for tokens |
| `get_jwks()` | Get JSON Web Key Set |

### Factory Functions

| Function | Description |
|----------|-------------|
| `create_authenticated_client(username, password, base_url)` | Create session-authenticated client |
| `create_client_credentials_client(client_id, client_secret, base_url)` | Create OAuth-authenticated client |

## Models

The SDK includes typed data models for API responses:

| Model | Description |
|-------|-------------|
| `ApiResponse` | Standard API response wrapper |
| `User` | User account information |
| `Project` | Project details |
| `Todo` | Todo item details |
| `OAuthClient` | OAuth client information |
| `OAuthToken` | OAuth token response |

## Exception Hierarchy

```
TaskManagerError (base)
├── AuthenticationError (401)
├── AuthorizationError (403)
├── NotFoundError (404)
├── ValidationError (400)
├── RateLimitError (429)
├── ServerError (5xx)
└── NetworkError (connection issues)
```

## Development

### Running Tests

```bash
cd packages/taskmanager-sdk
uv sync --dev
uv run pytest
```

### Type Checking

```bash
uv run mypy taskmanager_sdk
```

## License

MIT License
