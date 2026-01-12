# TODO

## MCP Refresh Token Implementation

**Priority:** Medium
**Estimated Effort:** 3-4 hours

### Background
Currently, MCP access tokens expire after 1 hour with no way to refresh them. Users must re-authenticate through the full OAuth flow when tokens expire. Implementing refresh tokens would allow clients (like Claude Web) to automatically obtain new access tokens without user interaction.

### Current State
- Access tokens issued with 1-hour expiry
- `load_refresh_token()` returns `None` (stub)
- `exchange_refresh_token()` raises `NotImplementedError`
- No refresh token storage exists

### Implementation Steps

#### 1. Database Schema
Add new table for refresh tokens:

```sql
CREATE TABLE mcp_refresh_tokens (
    token VARCHAR(255) PRIMARY KEY,
    access_token VARCHAR(255),
    client_id VARCHAR(255) NOT NULL,
    scopes TEXT,
    resource TEXT,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_refresh_tokens_access_token ON mcp_refresh_tokens(access_token);
CREATE INDEX idx_refresh_tokens_client_id ON mcp_refresh_tokens(client_id);
```

#### 2. Token Storage (`token_storage.py`)
Add methods:
- `store_refresh_token(token, access_token, client_id, scopes, expires_at, resource)`
- `load_refresh_token(token)` - returns token data dict or None
- `delete_refresh_token(token)`
- `delete_refresh_tokens_for_access_token(access_token)` - cleanup when access token revoked

#### 3. OAuth Provider (`taskmanager_oauth_provider.py`)

**Modify `exchange_authorization_code()`:**
- Generate refresh token (e.g., `mcp_refresh_{secrets.token_hex(32)}`)
- Store refresh token in database with longer expiry (e.g., 30 days)
- Include `refresh_token` in `OAuthToken` response

**Implement `load_refresh_token()`:**
- Look up refresh token in database via token_storage
- Validate token is not expired
- Return `RefreshToken` object with client_id, scopes, etc.

**Implement `exchange_refresh_token()`:**
- Validate the refresh token exists and is not expired
- Optionally validate requested scopes are subset of original scopes
- Revoke old access token (and optionally old refresh token for rotation)
- Generate new access token + new refresh token
- Store new tokens in database
- Return new `OAuthToken` with both tokens

#### 4. Testing
- Test refresh token issuance during authorization code exchange
- Test refresh token exchange for new access token
- Test expired refresh token rejection
- Test scope downgrade during refresh
- Test token rotation (old refresh token invalidated)

### Files to Modify
- `taskmanager_mcp/token_storage.py` - Add refresh token storage methods
- `taskmanager_mcp/taskmanager_oauth_provider.py` - Implement refresh token logic
- Database migration script for new table

### References
- RFC 6749 Section 6 (Refreshing an Access Token)
- Current stub implementations at `taskmanager_oauth_provider.py:562-577`
