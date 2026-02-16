# Service Account Authentication for Agents

## Goal

Enable AI agents and bots to authenticate to TaskManager (including via MCP) with their own identity and explicit, project-scoped permissions. Actions taken by agents — task creation, comments, status changes — are attributed to the agent's service account rather than a human user or an anonymous client.

## Current State

- **Client Credentials grant** exists but produces tokens with `user_id = NULL` — no identity attribution.
- **OAuth scopes** (`read`, `write`) are stored on tokens and clients but **not enforced** at the endpoint level.
- **API Keys** exist per-user with scopes, but no project-level granularity.
- **Projects** have an `owner` (`user_id`) but no shared-access model or ACL.
- **MCP auth server** proxies all token operations to the backend and issues its own `mcp_*` tokens. It already supports introspection, so changes to the backend token model flow through to MCP automatically.

## Design Decisions

- **Service accounts are users.** A service account is a row in the `User` table with `is_service_account = True`. This means every existing query that filters or joins on `user_id` (tasks, comments, projects, audit) attributes actions to the bot with zero changes to those queries.
- **Client Credentials carry identity.** When an `OAuthClient` is linked to a service account user (via its existing `user_id` FK), the Client Credentials grant populates `user_id` on the issued token instead of leaving it NULL.
- **Project access is a new join table**, not a scope string. Scopes control *what operations* an agent can perform; the project access table controls *which resources* it can see.
- **Scope enforcement is additive.** New fine-grained scopes (`tasks:read`, `tasks:write`, etc.) are introduced alongside the existing `read`/`write` scopes for backward compatibility.

---

## Implementation Steps

### Phase 1: Service Account Identity

**Outcome:** Admins can create service accounts that are distinct from human users.

#### 1.1 Add `is_service_account` to User model

- File: `services/backend/app/models/user.py`
- Add `is_service_account: Mapped[bool]` column, default `False`.
- Add `display_name: Mapped[str | None]` column for a human-readable bot name (e.g., "CI Bot").
- Create an Alembic migration.

#### 1.2 Admin API for service account CRUD

- File: new router at `services/backend/app/api/admin/service_accounts.py`
- Endpoints:
  - `POST /api/admin/service-accounts` — Create a service account. Generates a `User` row with `is_service_account=True`, a locked password hash, and a linked `OAuthClient` with `client_credentials` grant type. Returns the `client_id` and `client_secret` (shown once).
  - `GET /api/admin/service-accounts` — List all service accounts.
  - `GET /api/admin/service-accounts/{id}` — Get details including linked OAuth client and project access.
  - `PATCH /api/admin/service-accounts/{id}` — Update display name, active status, scopes.
  - `DELETE /api/admin/service-accounts/{id}` — Deactivate (soft delete: sets `is_active=False` on both User and OAuthClient).
- All endpoints require `get_admin_user` dependency.

#### 1.3 Tests

- Unit tests for service account creation, listing, update, deactivation.
- Verify that a deactivated service account's tokens are rejected.

---

### Phase 2: Client Credentials with Identity

**Outcome:** Tokens issued via Client Credentials carry the service account's `user_id`, so all existing `get_current_user_oauth()` paths attribute actions to the bot.

#### 2.1 Modify Client Credentials token grant

- File: `services/backend/app/api/oauth/token.py`
- When `grant_type=client_credentials` and the `OAuthClient` has a non-null `user_id`, set `user_id` on the created `AccessToken` instead of `None`.
- If the linked user is inactive or not a service account, reject the request.

#### 2.2 Update token verification / introspection

- File: `services/backend/app/api/oauth/verify.py`
- Ensure the `/api/oauth/verify` response includes `user_id` for client credentials tokens that have one.
- The MCP auth server's `/introspect` endpoint already proxies to `/api/oauth/verify`, so this flows through automatically.

#### 2.3 Tests

- Issue a client credentials token for a service account, verify `user_id` is set.
- Use the token to create a task, verify the task's `user_id` matches the service account.
- Verify tokens for clients without a linked user still get `user_id=None` (backward compatibility).

---

### Phase 3: Project-Scoped Access Control

**Outcome:** Service accounts (and optionally human users) can be granted explicit access to specific projects with a defined role.

#### 3.1 Create ProjectAccess model

- File: new model at `services/backend/app/models/project_access.py`
- Schema:
  ```
  project_access
  ├── id (PK)
  ├── user_id (FK → users.id)
  ├── project_id (FK → projects.id)
  ├── role (enum: viewer, commenter, editor, admin)
  ├── created_at
  └── unique constraint on (user_id, project_id)
  ```
- Create an Alembic migration.

#### 3.2 Enforce project access in queries

- Modify project and task query functions (in `app/api/` route handlers and any CRUD helpers) to filter results:
  - **Project owner** — full access (unchanged).
  - **Admin user** — full access (unchanged).
  - **ProjectAccess row exists** — access at the granted role level.
  - **Service account with no ProjectAccess row** — no access.
- For human users without a ProjectAccess row, decide on default behavior (e.g., owner-only or open access). This can be toggled via a setting to avoid breaking existing behavior.

#### 3.3 Admin API for project access grants

- Add to the service accounts router or a new router:
  - `POST /api/admin/service-accounts/{id}/project-access` — Grant access to a project with a role.
  - `GET /api/admin/service-accounts/{id}/project-access` — List project access grants.
  - `DELETE /api/admin/service-accounts/{id}/project-access/{project_id}` — Revoke access.
- Require `get_admin_user`.

#### 3.4 Tests

- Service account with `viewer` role can list tasks in a project but cannot create.
- Service account with `editor` role can create tasks.
- Service account with no access row gets 403 on project endpoints.
- Project owner retains full access regardless of ProjectAccess table.

---

### Phase 4: Scope Enforcement

**Outcome:** OAuth scopes are checked at the endpoint level, controlling *what operations* a token can perform.

#### 4.1 Define fine-grained scopes

- File: new or extend `services/backend/app/core/scopes.py`
- Scopes:
  - `tasks:read` — List and view tasks.
  - `tasks:write` — Create, update, delete tasks.
  - `projects:read` — List and view projects.
  - `projects:write` — Create, update, delete projects.
  - `comments:read` — View comments.
  - `comments:write` — Create comments.
  - `admin` — Admin operations.
- The legacy `read` scope implies all `*:read` scopes; `write` implies all `*:write` scopes (backward compatible).

#### 4.2 Add scope-checking dependency

- File: `services/backend/app/dependencies.py`
- New dependency factory:
  ```python
  def require_scopes(*scopes: str) -> Depends:
      """Dependency that checks the current token has all required scopes."""
  ```
- Works with both OAuth tokens and API keys (both store scopes).

#### 4.3 Apply to route handlers

- Add `require_scopes(...)` as a dependency to each endpoint:
  ```python
  @router.get("", dependencies=[Depends(require_scopes("tasks:read"))])
  async def list_tasks(...): ...
  ```
- Start with task and project endpoints. Expand to other endpoints incrementally.

#### 4.4 Tests

- Token with `tasks:read` can list tasks but gets 403 on `POST /api/todos`.
- Token with `tasks:write` can create tasks.
- Legacy `read` scope still grants `tasks:read` access.

---

### Phase 5: MCP Integration Verification

**Outcome:** Service account tokens work end-to-end through the MCP auth/resource servers with no MCP-side code changes.

#### 5.1 Verify introspection carries identity

- The MCP auth server calls `POST /introspect` which proxies to `/api/oauth/verify`.
- Confirm the response now includes `user_id` and the resource server receives it.
- File: `services/mcp-auth/mcp_auth/taskmanager_oauth_provider.py` — verify no filtering of `user_id` from introspection response.

#### 5.2 Verify MCP tools respect project access

- Call `get_all_projects()` and `get_all_tasks()` MCP tools with a service account token.
- Confirm only projects/tasks the service account has access to are returned.

#### 5.3 Verify task creation attribution

- Call `create_task()` MCP tool with a service account token.
- Confirm the created task's `user_id` is the service account, not NULL.

#### 5.4 Tests

- End-to-end test: register MCP client for service account, get token via device flow or client credentials, call MCP tools, verify results are scoped and attributed.

---

## File Change Summary

| File | Change |
|---|---|
| `services/backend/app/models/user.py` | Add `is_service_account`, `display_name` columns |
| `services/backend/app/models/project_access.py` | New model |
| `services/backend/app/models/__init__.py` | Register new model |
| `services/backend/alembic/versions/` | Two migrations (user columns, project_access table) |
| `services/backend/app/api/admin/service_accounts.py` | New router: service account CRUD + project access |
| `services/backend/app/api/oauth/token.py` | Client credentials populates `user_id` from linked service account |
| `services/backend/app/api/oauth/verify.py` | Include `user_id` in client credentials verification response |
| `services/backend/app/core/scopes.py` | Scope definitions and legacy mapping |
| `services/backend/app/dependencies.py` | `require_scopes()` dependency |
| `services/backend/app/api/` (various routers) | Add scope dependencies to endpoints |
| `services/backend/app/api/` (project/task handlers) | Filter by ProjectAccess |
| `services/backend/tests/` | Tests for all of the above |

## Out of Scope (for now)

- **UI for managing service accounts.** Admin API only in this iteration; a frontend page can be added later.
- **Audit logging.** A future enhancement to log all actions with actor identity (human vs. service account).
- **Rate limiting per service account.** Currently rate limiting is IP-based; per-identity limits can be added later.
- **Token rotation policies.** Automatic credential rotation for service accounts.
- **Cross-organization access.** Multi-tenancy is not addressed here.
