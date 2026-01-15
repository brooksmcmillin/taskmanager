# Session Cookie Fix - Root Cause Analysis

## The Problem

After setting `VITE_API_URL=https://api.brooksmcmillin.com`, users could log in successfully, but the todos wouldn't load and they'd get logged out immediately. Looking at the backend logs revealed:

```
INFO: 172.20.0.4:xxx - "POST /api/auth/login HTTP/1.1" 200 OK      # ✓ Login works
INFO: 172.20.0.4:xxx - "GET /api/auth/session HTTP/1.1" 200 OK    # ✓ Session works from frontend
INFO: 172.20.0.1:xxx - "GET /api/todos?status=pending HTTP/1.1" 401 Unauthorized  # ✗ Fails from browser
```

Two different IP addresses = Two different request paths!

## Root Cause

The `VITE_API_URL` environment variable causes **client-side JavaScript** to bypass SvelteKit's server-side proxy and make direct requests to the backend:

```
❌ WRONG (with VITE_API_URL set):
Browser JavaScript → https://api.brooksmcmillin.com
                     ↑ Direct request, cookies lost!

✓ CORRECT (without VITE_API_URL):
Browser JavaScript → /api/todos (relative URL)
                  ↓
SvelteKit Server → hooks.server.ts proxy
                  ↓ (forwards cookies properly)
FastAPI Backend
```

### Why Cookies Get Lost

1. **Login request** goes through SvelteKit server proxy → Backend sets `session` cookie for `todo2.brooksmcmillin.com`
2. **Subsequent requests** go directly to `api.brooksmcmillin.com` → Browser doesn't send the cookie (different domain!)

Even if we used SameSite=None, direct browser→backend requests would still bypass the server-side proxy, breaking other functionality.

## The Fix

**Changed `frontend/src/lib/api/client.ts`:**
```typescript
// Before:
const BASE_URL = import.meta.env.VITE_API_URL || '';

// After:
const BASE_URL = '';  // Always use relative URLs
```

This ensures ALL API requests go through the SvelteKit server proxy at `/api/*`, which:
- Properly forwards session cookies in both directions
- Handles CORS correctly
- Works in all deployment scenarios

## Deployment Instructions

### For Docker Deployments

In your `docker-compose.yml`:
```yaml
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      # Server-side proxy configuration (runtime variable)
      - BACKEND_URL=https://api.brooksmcmillin.com
      # DO NOT set VITE_API_URL - it breaks cookie forwarding!
```

### For Non-Docker Deployments

Set the environment variable before starting the Node.js process:
```bash
export BACKEND_URL=https://api.brooksmcmillin.com
node build/index.js
```

### Important Notes

1. **Do NOT set `VITE_API_URL`** - This will cause the bug to return
2. **`BACKEND_URL` is server-side only** - Used by `hooks.server.ts`, not compiled into client code
3. **Client code always uses relative URLs** - `/api/todos` gets proxied to the backend automatically

## Testing the Fix

### 1. Verify API Proxy Works
```bash
curl http://localhost:3000/api/auth/session
# Should return: {"detail":{"code":"AUTH_002","message":"Authentication required",...}}
```

### 2. Test Login Flow
1. Open browser dev tools → Network tab
2. Login at http://localhost:3000/login
3. Verify:
   - Login request goes to: `http://localhost:3000/api/auth/login` (NOT directly to backend)
   - Response includes `Set-Cookie: session=...`
   - Subsequent API requests include `Cookie: session=...`

### 3. Check Backend Logs
```bash
docker logs taskmanager-backend --tail=20
```

You should see all requests coming from the same IP (frontend container), NOT from different IPs.

## Why This Architecture?

### Browser Request Flow
```
User Action in Browser
    ↓
Svelte Component calls: api.get('/api/todos')
    ↓ (fetch to relative URL)
SvelteKit Server receives request at /api/todos
    ↓
hooks.server.ts intercepts request
    ↓
Proxies to: BACKEND_URL + /api/todos
    ↓ (forwards cookies automatically)
FastAPI Backend processes request
    ↓ (returns data + Set-Cookie if needed)
hooks.server.ts forwards response
    ↓ (forwards cookies back to browser)
Browser receives response with cookies set
```

### Why Not Direct Backend Access?

1. **Cookie Domains**: Browser won't send `todo2.brooksmcmillin.com` cookies to `api.brooksmcmillin.com`
2. **CORS Complexity**: Would need complex CORS configuration with credentials
3. **Security**: Server-side proxy can add security headers, rate limiting, etc.
4. **Flexibility**: Easy to change backend URL without rebuilding frontend

## Files Changed

- ✅ `frontend/src/lib/api/client.ts` - Removed VITE_API_URL, always use relative URLs
- ✅ `frontend/src/hooks.server.ts` - Made backend URL configurable (already done)
- ✅ `backend/app/config.py` - Added todo2 subdomain to CORS (already done)
- ✅ `frontend/src/routes/login/+page.svelte` - Fixed error format parsing (already done)

## Rollback

If issues occur, the old behavior can be restored by:
```bash
git checkout <previous-commit> frontend/src/lib/api/client.ts
docker compose build frontend
docker compose up -d frontend
```

However, this will re-introduce the cookie forwarding bug.

---

**Issue**: Session cookies not forwarded, causing 401 errors after login
**Root Cause**: `VITE_API_URL` causing client-side code to bypass server proxy
**Fix**: Always use relative URLs in client code
**Status**: ✅ Fixed and tested
**Created**: 2026-01-15
