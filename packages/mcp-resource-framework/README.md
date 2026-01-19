# MCP Resource Framework

Reusable Resource Server framework for OAuth-protected MCP servers.

## Features

- **Token Verification**: RFC 7662 OAuth token introspection with SSRF protection
- **Security Screening**: Lakera Guard integration for AI security threats
- **Response Validation**: Utilities for validating API responses
- **ASGI Middleware**: Path normalization and request logging

## Installation

```bash
uv add mcp-resource-framework
```

## Usage

### Token Verification

```python
from mcp_resource_framework.auth import IntrospectionTokenVerifier

verifier = IntrospectionTokenVerifier(
    introspection_endpoint="https://auth.example.com/introspect",
    server_url="https://resource.example.com",
    validate_resource=True
)

access_token = await verifier.verify_token("token_123")
```

### Security Screening

```python
from mcp_resource_framework.security import guard_tool

@mcp.tool()
@guard_tool(input_params=["query"])
async def search_tasks(query: str) -> str:
    # Tool implementation
    ...
```

### Response Validation

```python
from mcp_resource_framework.validation import require_list, json_error

# Validate API response contains a list
tasks = require_list(api_response, context="tasks")
if isinstance(tasks, str):  # Error occurred
    return tasks  # Return JSON error
```

### ASGI Middleware

```python
from mcp_resource_framework.middleware import NormalizePathMiddleware, create_logging_middleware

app = Starlette()
app.add_middleware(NormalizePathMiddleware)
app = create_logging_middleware(app, mask_auth=True)
```

## License

MIT
