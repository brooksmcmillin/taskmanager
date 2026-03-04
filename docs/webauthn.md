# WebAuthn / Passkeys

TaskManager supports passkey authentication via the [WebAuthn](https://www.w3.org/TR/webauthn-3/) standard. Passkeys let users sign in securely without a password using device biometrics (Touch ID, Face ID, Windows Hello) or hardware security keys.

## Overview

- Users register one or more passkeys after creating an account.
- At login, instead of typing a password, the user taps a passkey prompt on their device.
- Each passkey is tied to a specific relying party (RP) origin, so it cannot be phished or reused on a different site.
- Multiple passkeys per user are supported (e.g., one for a laptop, one for a phone).
- The backend uses the [`py_webauthn`](https://github.com/duo-labs/py_webauthn) library (`webauthn>=2.0.0`).

## Setup and Configuration

### Environment Variables

WebAuthn requires two values that identify the site to the authenticator. By default both are derived from `FRONTEND_URL`, so no extra configuration is needed for local development.

| Variable | Default (derived) | Description |
|---|---|---|
| `WEBAUTHN_RP_ID` | hostname of `FRONTEND_URL` | Relying Party ID — must be the registrable domain of the origin (e.g. `example.com` or `localhost`). |
| `WEBAUTHN_RP_NAME` | `TaskManager` | Human-readable name shown by the authenticator during registration. |
| `WEBAUTHN_ORIGIN` | scheme+host of `FRONTEND_URL` | The exact origin the browser presents (e.g. `https://example.com` or `http://localhost:3000`). Must match the browser's `window.location.origin`. |
| `WEBAUTHN_CHALLENGE_TIMEOUT` | `300` | Seconds before a challenge expires. Default is 5 minutes. |

Example for production:

```
FRONTEND_URL=https://todo.example.com
# The two values below are inferred automatically from FRONTEND_URL:
#   WEBAUTHN_RP_ID=todo.example.com
#   WEBAUTHN_ORIGIN=https://todo.example.com
```

Override explicitly when the backend is served from a different origin than the frontend:

```
WEBAUTHN_RP_ID=todo.example.com
WEBAUTHN_ORIGIN=https://todo.example.com
```

### Challenge Store

Challenges are currently stored in-memory in the backend process. This means:

- Challenges do not survive a backend restart.
- Multi-process or multi-instance deployments will not share challenge state — every request must reach the same process that issued the challenge.

For production deployments with multiple backend instances, replace the in-memory store in `services/backend/app/api/webauthn.py` with a shared store (e.g. Redis).

### Database

A `webauthn_credentials` table is created by the Alembic migration `0012_add_webauthn_credentials.py`. No manual setup is required beyond running migrations:

```bash
uv run alembic upgrade head
```

## Authentication Flows

### Registration Flow

Registration adds a new passkey to an already-authenticated user's account (e.g. from the Settings page). The user must have an active session before they can register a passkey.

```
Browser (logged-in user)           Backend
        |                              |
        |-- POST /register/options --> |
        |   { device_name? }          |  1. Generate challenge + registration options
        |                              |  2. Store challenge (keyed by user_id)
        |<-- { challenge_id, options } |
        |                              |
        |  navigator.credentials       |
        |    .create(options)          |  (browser prompts for biometric / security key)
        |                              |
        |-- POST /register/verify ---> |
        |   { challenge_id,           |  3. Look up and validate challenge
        |     credential,             |  4. Verify registration response (origin, RP ID, sig)
        |     device_name? }          |  5. Check credential ID is not already registered
        |                              |  6. Store credential in database
        |<-- CredentialResponse ------- |
        |   { id, device_name,        |
        |     created_at, ... }        |
```

1. The client calls `POST /api/auth/webauthn/register/options` with an optional `device_name`.
2. The server generates a WebAuthn challenge and registration options including the RP info and excluded credentials (to prevent duplicate registration of the same authenticator).
3. The browser calls `navigator.credentials.create()` with the parsed options, prompting the user for biometric confirmation.
4. The client sends the resulting credential to `POST /api/auth/webauthn/register/verify`.
5. The server verifies the credential against the stored challenge, then saves the credential's public key and sign count to the `webauthn_credentials` table.

### Authentication (Login) Flow

Authentication works without an existing session. The user may optionally provide their email to limit which credentials are offered by the authenticator.

```
Browser (unauthenticated)          Backend
        |                              |
        |-- POST /authenticate/options |
        |   { email? }                |  1. Look up user's credentials (if email given)
        |                              |  2. Generate challenge
        |                              |  3. Store challenge (keyed by user_id or None)
        |<-- { challenge_id, options } |     Always returns 200 to prevent user enumeration
        |                              |
        |  navigator.credentials       |
        |    .get(options)             |  (browser prompts authenticator selection)
        |                              |
        |-- POST /authenticate/verify  |
        |   { challenge_id,           |  4. Look up stored challenge
        |     credential }            |  5. Find credential in database by ID
        |                              |  6. Look up user, verify user is active
        |                              |  7. Verify authentication response (sig, origin, RP ID)
        |                              |  8. Check sign count for cloned-authenticator detection
        |                              |  9. Update sign count + last_used_at
        |                              | 10. Create session, set session cookie
        |<-- { message, user } ------- |
```

#### Discoverable Credentials

If the user leaves the email field empty and their browser/device supports it, the authenticator can discover and offer passkeys for the current site without the user typing anything. This is controlled by the `ResidentKeyRequirement.PREFERRED` setting during registration.

#### User Enumeration Prevention

The `POST /authenticate/options` endpoint always returns a valid challenge regardless of whether the email address exists in the database or has any passkeys. An attacker cannot distinguish between "unknown email", "email with no passkeys", and "email with passkeys" from the response.

## API Endpoints

All endpoints are under the prefix `/api/auth/webauthn`.

### POST /api/auth/webauthn/register/options

Generates registration options for the authenticated user. Requires an active session.

**Rate limit:** 5 requests per user per 5 minutes.

**Request body:**

```json
{
  "device_name": "MacBook Touch ID"
}
```

`device_name` is optional (max 100 characters). It is stored as a label for the credential and shown in the Settings UI.

**Response:**

```json
{
  "challenge_id": "abc123...",
  "options": {
    "rp": {
      "id": "todo.example.com",
      "name": "TaskManager"
    },
    "user": {
      "id": "<base64url user ID>",
      "name": "user@example.com",
      "displayName": "user@example.com"
    },
    "challenge": "<base64url challenge>",
    "pubKeyCredParams": [
      { "type": "public-key", "alg": -7 },
      { "type": "public-key", "alg": -257 }
    ],
    "timeout": 60000,
    "excludeCredentials": [],
    "authenticatorSelection": {
      "residentKey": "preferred",
      "userVerification": "preferred"
    },
    "attestation": "none"
  }
}
```

The `challenge_id` must be passed back to `/register/verify`. The `options` object is passed directly to `navigator.credentials.create()` after converting binary fields from base64url to `ArrayBuffer`.

Supported public key algorithms:
- `-7` — ECDSA with SHA-256 (ES256, preferred)
- `-257` — RSASSA-PKCS1-v1_5 with SHA-256 (RS256, fallback)

---

### POST /api/auth/webauthn/register/verify

Verifies a registration response and saves the credential. Requires an active session.

**Request body:**

```json
{
  "challenge_id": "abc123...",
  "credential": {
    "id": "<credential ID>",
    "rawId": "<base64url credential ID>",
    "type": "public-key",
    "response": {
      "clientDataJSON": "<base64url>",
      "attestationObject": "<base64url>",
      "transports": ["internal"]
    }
  },
  "device_name": "MacBook Touch ID"
}
```

**Response (201):**

```json
{
  "id": 42,
  "device_name": "MacBook Touch ID",
  "created_at": "2026-03-03T12:00:00+00:00",
  "last_used_at": null
}
```

**Error responses:**

| Status | Code | Cause |
|---|---|---|
| 422 | `VALIDATION_001` | Missing or expired challenge |
| 422 | `VALIDATION_001` | Challenge belongs to a different user |
| 422 | `VALIDATION_001` | Credential already registered |
| 422 | `VALIDATION_001` | Registration verification failed (bad signature, wrong origin, etc.) |

---

### POST /api/auth/webauthn/authenticate/options

Generates authentication options. No session required.

**Rate limit:** 10 requests per IP per 5 minutes.

**Request body:**

```json
{
  "email": "user@example.com"
}
```

`email` is optional. When omitted, the response includes an empty `allowCredentials` list, relying on discoverable credentials.

**Response:**

```json
{
  "challenge_id": "xyz789...",
  "options": {
    "challenge": "<base64url challenge>",
    "timeout": 60000,
    "rpId": "todo.example.com",
    "allowCredentials": [
      {
        "type": "public-key",
        "id": "<base64url credential ID>",
        "transports": ["internal"]
      }
    ],
    "userVerification": "preferred"
  }
}
```

---

### POST /api/auth/webauthn/authenticate/verify

Verifies an authentication assertion and creates a session. No session required.

**Rate limit:** 10 attempts per IP per 5 minutes. Failed attempts increment the rate limit counter; successful authentication resets it.

**Request body:**

```json
{
  "challenge_id": "xyz789...",
  "credential": {
    "id": "<credential ID>",
    "rawId": "<base64url credential ID>",
    "type": "public-key",
    "response": {
      "clientDataJSON": "<base64url>",
      "authenticatorData": "<base64url>",
      "signature": "<base64url>",
      "userHandle": "<base64url or null>"
    }
  }
}
```

**Response (200):**

```json
{
  "message": "Login successful",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "is_admin": false
  }
}
```

A session cookie is set on the response. The frontend performs a full-page reload after this call so the SvelteKit layout can pick up the new session.

**Error responses:**

| Status | Code | Cause |
|---|---|---|
| 422 | `VALIDATION_001` | Missing or expired challenge |
| 422 | `VALIDATION_001` | Missing or invalid credential ID encoding |
| 401 | `AUTH_002` | Unknown credential |
| 401 | `AUTH_002` | User not found or inactive |
| 422 | `VALIDATION_001` | Assertion verification failed |

---

### GET /api/auth/webauthn/credentials

Lists all passkeys registered by the current user. Requires an active session.

**Response:**

```json
{
  "data": [
    {
      "id": 42,
      "device_name": "MacBook Touch ID",
      "created_at": "2026-03-03T12:00:00+00:00",
      "last_used_at": "2026-03-04T09:15:00+00:00"
    }
  ],
  "meta": {
    "count": 1
  }
}
```

---

### DELETE /api/auth/webauthn/credentials/{credential_id}

Removes a passkey. Requires an active session. Users can only delete their own credentials.

**Path parameter:** `credential_id` — integer ID from the credentials list.

**Response (200):**

```json
{
  "deleted": true,
  "id": 42
}
```

**Error responses:**

| Status | Code | Cause |
|---|---|---|
| 404 | `NOT_FOUND` | Credential not found or belongs to another user |

## Database Schema

```
webauthn_credentials
├── id            INTEGER PRIMARY KEY
├── user_id       INTEGER FK → users.id (CASCADE DELETE)
├── credential_id BYTEA UNIQUE NOT NULL (indexed)
├── public_key    BYTEA NOT NULL
├── sign_count    INTEGER DEFAULT 0
├── transports    VARCHAR(255) NULL  (comma-separated, e.g. "internal,hybrid")
├── device_name   VARCHAR(100) NULL
├── created_at    TIMESTAMPTZ DEFAULT now()
└── last_used_at  TIMESTAMPTZ NULL
```

When a user account is deleted, all their `webauthn_credentials` rows are deleted via the `CASCADE` constraint.

## Frontend Integration

The TypeScript helper library is at `services/frontend/src/lib/api/webauthn.ts`. It handles all base64url encoding/decoding and `ArrayBuffer` conversion required by the WebAuthn browser API.

### Browser Support Check

```typescript
import { isWebAuthnSupported, isConditionalUISupported } from '$lib/api/webauthn';

const supported = isWebAuthnSupported();          // synchronous
const autofill = await isConditionalUISupported(); // async — checks for passkey autofill
```

The login and settings pages both call `isWebAuthnSupported()` on mount and conditionally render passkey UI only when supported.

### Register a Passkey

```typescript
import { registerPasskey } from '$lib/api/webauthn';

// Must be called when the user already has an active session
const credential = await registerPasskey('MacBook Touch ID');
// credential: { id, device_name, created_at, last_used_at }
```

This function:
1. Calls `POST /api/auth/webauthn/register/options`
2. Invokes `navigator.credentials.create()` (triggers browser UI)
3. Calls `POST /api/auth/webauthn/register/verify`
4. Returns the stored credential record

### Authenticate with a Passkey

```typescript
import { authenticateWithPasskey } from '$lib/api/webauthn';

// Email is optional — omit to use discoverable credentials
await authenticateWithPasskey('user@example.com');
window.location.href = '/'; // reload to pick up new session cookie
```

This function:
1. Calls `POST /api/auth/webauthn/authenticate/options`
2. Invokes `navigator.credentials.get()` (triggers browser authenticator selection)
3. Calls `POST /api/auth/webauthn/authenticate/verify`
4. Returns `{ message, user }` on success

### Manage Passkeys

```typescript
import { listPasskeys, deletePasskey } from '$lib/api/webauthn';

const passkeys = await listPasskeys();
// passkeys: Array<{ id, device_name, created_at, last_used_at }>

await deletePasskey(42);
```

### UI Entry Points

- **Login page** (`/login`) — Shows a "Sign in with Passkey" button when WebAuthn is supported. The email field value is passed to `authenticateWithPasskey()` if filled in.
- **Settings page** (`/settings`) — Shows a "Passkeys" section listing registered passkeys with add and remove actions.

## Security Considerations

### Cloned Authenticator Detection

Every authentication response includes a signature counter. When the stored sign count is greater than zero and the received counter does not exceed the stored value, the backend logs a warning indicating a possible cloned authenticator. Sign count zero is intentionally excluded from the check because some authenticators legitimately do not implement counters (they always report zero).

The current implementation logs the warning but does not reject the authentication. Tighten this policy if your threat model requires it by raising an error in `verify_authentication` in `services/backend/app/api/webauthn.py`.

### User Enumeration

The `/authenticate/options` endpoint deliberately returns a valid challenge regardless of whether the provided email exists. This prevents an attacker from discovering valid email addresses by observing different responses.

### Rate Limiting

Each endpoint has its own independent rate limit counter:

| Endpoint | Limit | Key |
|---|---|---|
| `POST /register/options` | 5 per 5 minutes | Per user ID |
| `POST /authenticate/options` | 10 per 5 minutes | Per client IP |
| `POST /authenticate/verify` | 10 per 5 minutes | Per client IP |

`/register/verify` has no rate limit of its own — abuse is mitigated by the fact that a valid `challenge_id` is required, which can only be obtained from the rate-limited `/register/options` endpoint.

The `/authenticate/options` and `/authenticate/verify` limits are independent: an attacker can make up to 10 requests to each endpoint before triggering a limit. The counters use distinct keys (`webauthn_auth_options_<ip>` and `webauthn_auth_verify_<ip>`).

Failed authentication attempts count against the `/authenticate/verify` limit; successful authentication resets it.

### Origin and RP ID Binding

The backend verifies that:
- The `origin` in `clientDataJSON` matches `WEBAUTHN_ORIGIN` exactly.
- The RP ID in the authenticator data matches `WEBAUTHN_RP_ID`.

A passkey registered for `todo.example.com` cannot be used on `evil.example.com`, even if both are subdomains of the same parent domain.

### HTTPS Requirement

WebAuthn requires a secure context. Browsers only expose `navigator.credentials` on `https://` origins or `http://localhost`. Production deployments must be served over HTTPS.

### Credential Storage

Public keys and binary credential IDs are stored as raw bytes (`BYTEA`) in PostgreSQL. Private keys never leave the authenticator device and are not sent to the server.
