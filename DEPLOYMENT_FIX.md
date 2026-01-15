# Todo Loading Fix - Deployment Guide

## Problem Summary

The new SvelteKit frontend at `https://todo2.brooksmcmillin.com` was unable to load todos because:

1. **Missing API Proxy Configuration**: The frontend's server-side API proxy was hardcoded to `http://backend:8000` (Docker service name), which doesn't work in production deployments outside Docker.

2. **Cookie Forwarding Issue**: Client-side code was trying to make direct requests to the backend, bypassing SvelteKit's server-side proxy that handles cookie forwarding.

3. **CORS Configuration**: The backend's CORS allowed origins didn't include `https://todo2.brooksmcmillin.com`.

4. **Error Response Format**: The login page wasn't correctly parsing FastAPI's error format (`detail.message` instead of `error.message`).

## Fixes Applied

### 1. Frontend API Proxy (`frontend/src/hooks.server.ts`)
- Made the backend URL configurable via environment variables
- Priority: `BACKEND_URL` > `VITE_API_URL` > `http://backend:8000` (fallback)
- **Server-side only** - ensures proper cookie forwarding

### 2. API Client (`frontend/src/lib/api/client.ts`)
- **Removed VITE_API_URL usage** - client-side code now always uses relative URLs
- All API requests go through SvelteKit's server proxy at `/api/*`
- This ensures session cookies are properly forwarded in both directions

### 3. Backend CORS (`backend/app/config.py`)
- Added `https://todo2.brooksmcmillin.com` to default allowed origins

### 4. Login Error Handling (`frontend/src/routes/login/+page.svelte`)
- Updated to parse FastAPI error format: `data.detail.message`
- Maintains backward compatibility with legacy format

### 5. Production Environment Template (`frontend/.env.production`)
- Created template with clear documentation
- **Important**: `BACKEND_URL` is runtime-only, not a build variable

## Architecture Overview

```
Browser → SvelteKit Frontend (localhost:3000)
                ↓ /api/* requests go through hooks.server.ts
                ↓ (cookies forwarded automatically)
                ↓
          FastAPI Backend (localhost:8000)
```

**Key Point**: Client-side code MUST use relative URLs (`/api/todos`) so requests go through the SvelteKit server proxy. Direct backend URLs bypass the proxy and break cookie forwarding.

## Deployment Steps

### Step 1: Set Environment Variables

On your production server, set this **runtime** environment variable for the frontend service:

```bash
# For the SvelteKit frontend container/process
export BACKEND_URL=https://api.brooksmcmillin.com
```

**Important**: Do NOT set `VITE_API_URL` as it will cause client-side code to bypass the proxy.

### Step 2: Remove Any Incorrect Environment Variables

**CRITICAL**: If you previously set `VITE_API_URL`, you MUST remove it:

```bash
# In your docker-compose.yml or deployment config, remove:
# - VITE_API_URL=https://api.brooksmcmillin.com  ← DELETE THIS

# Only keep:
# - BACKEND_URL=https://api.brooksmcmillin.com   ← KEEP THIS
```

### Step 3: Rebuild and Deploy

```bash
# Pull latest changes
git pull

# Rebuild containers (includes the API client fix)
docker compose build backend frontend

# Restart services
docker compose up -d backend frontend

# Or if deployed differently, restart your Node.js process
# with the BACKEND_URL environment variable set
```

### Step 4: Verify the Fix

1. **Check backend is accessible:**
   ```bash
   curl https://api.brooksmcmillin.com/health
   # Should return: {"status":"healthy"}
   ```

2. **Check frontend proxy works:**
   ```bash
   curl https://todo2.brooksmcmillin.com/api/todos
   # Should return: {"detail":{"code":"AUTH_002","message":"Authentication required",...}}
   # (401 error is expected when not logged in)
   ```

3. **Test in browser:**
   - Go to https://todo2.brooksmcmillin.com
   - Login with your credentials
   - Verify todos load correctly (no JSON parse errors)

## Docker Compose Configuration

If you're using docker-compose for production, add the environment variable:

```yaml
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - BACKEND_URL=https://api.brooksmcmillin.com
      # OR use a .env file
    env_file:
      - ./frontend/.env.production
```

## Nginx/Reverse Proxy Notes

If you're using Nginx or another reverse proxy in front of your services, ensure:

1. **CORS headers aren't duplicated**: The backend already sends CORS headers, so don't add them again in Nginx
2. **Cookies are forwarded**: Session cookies must be forwarded between frontend and backend
3. **WebSocket support** (if you plan to add real-time features later)

Example Nginx config:
```nginx
# Frontend (SvelteKit)
server {
    server_name todo2.brooksmcmillin.com;
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Backend (FastAPI)
server {
    server_name api.brooksmcmillin.com;
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Troubleshooting

### Issue: Still getting JSON parse errors

**Check:**
1. Is `BACKEND_URL` set correctly in the frontend environment?
2. Can the frontend container reach the backend URL?
3. Are there any firewall rules blocking the connection?

**Debug:**
```bash
# From inside the frontend container
docker exec -it taskmanager-frontend sh
wget -O- $BACKEND_URL/health
```

### Issue: CORS errors in browser console

**Check:**
1. Backend logs for CORS-related errors
2. Verify `https://todo2.brooksmcmillin.com` is in the allowed origins list
3. Check if Nginx is adding duplicate CORS headers

**Fix:**
```bash
# Check backend CORS configuration
docker logs taskmanager-backend | grep -i cors
```

### Issue: Cookies not being set/sent

**Check:**
1. Browser developer tools > Application > Cookies
2. Verify `session` cookie is being set after login
3. Check cookie attributes (SameSite, Secure, HttpOnly)

## Testing Checklist

- [ ] Backend health check responds correctly
- [ ] Frontend can reach backend API
- [ ] Login works and sets session cookie
- [ ] Todos load without JSON parse errors
- [ ] Create/update/delete todo operations work
- [ ] Projects page works
- [ ] Calendar drag-and-drop works
- [ ] OAuth flows work (if configured)

## Rollback Plan

If issues occur, you can quickly rollback:

```bash
# Restore previous container versions
docker compose down
git checkout <previous-commit>
docker compose up -d

# Or revert specific changes
git revert <commit-hash>
```

## Files Changed

- `frontend/src/hooks.server.ts` - Made backend URL configurable
- `frontend/src/routes/login/+page.svelte` - Fixed error format parsing
- `backend/app/config.py` - Added todo2 subdomain to CORS
- `frontend/.env.production` - Added production environment template

## Next Steps

After verifying the fix works:

1. Monitor logs for any errors: `docker compose logs -f backend frontend`
2. Check browser console for any remaining issues
3. Test all main features (todos, projects, calendar, OAuth)
4. Consider adding monitoring/alerting for the API proxy

---

**Created:** 2026-01-15
**Issue:** Todo loading failure due to API proxy misconfiguration
**Status:** ✅ Fixed - Ready for deployment
