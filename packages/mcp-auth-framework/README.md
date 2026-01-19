# MCP Auth Framework

Reusable OAuth Authorization Server framework for MCP servers.

## Features

- **OAuth 2.0 Error Responses**: Standardized error handling following RFC 6749
- **Token Storage**: Abstract interface with PostgreSQL and in-memory implementations
- **Rate Limiting**: Sliding window rate limiter for OAuth endpoints
- **Input Validation**: Client ID and scope validation utilities

## Installation

```bash
uv add mcp-auth-framework
```

## Usage

### OAuth Error Responses

```python
from mcp_auth_framework.responses import invalid_request, server_error

# Return standardized OAuth error
return invalid_request("client_id is required")
```

### Token Storage

```python
from mcp_auth_framework.storage import PostgresTokenStorage

storage = PostgresTokenStorage(database_url="postgresql://...")
await storage.initialize()

await storage.store_token(
    token="access_token_123",
    client_id="my-client",
    scopes=["read", "write"],
    expires_at=1234567890
)

token_data = await storage.load_token("access_token_123")
```

### Rate Limiting

```python
from mcp_auth_framework.rate_limiting import SlidingWindowRateLimiter

limiter = SlidingWindowRateLimiter(requests_per_window=10, window_seconds=3600)

if not limiter.is_allowed(client_id):
    retry_after = limiter.get_retry_after(client_id)
    return rate_limit_exceeded("Too many requests", retry_after)
```

## License

MIT
