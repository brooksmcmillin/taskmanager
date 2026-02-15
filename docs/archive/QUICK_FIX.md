# Quick Fix Guide - Session Cookie Issue

## TL;DR

**Problem**: Login works but todos won't load, get logged out immediately.

**Root Cause**: Setting `VITE_API_URL` made browser requests bypass the SvelteKit proxy, breaking cookie forwarding.

**Fix**: Remove `VITE_API_URL` from your environment and rebuild.

## Immediate Steps

1. **Edit your docker-compose.yml or deployment config:**
   ```yaml
   frontend:
     environment:
       - BACKEND_URL=https://api.brooksmcmillin.com  # ✓ Keep this
       # - VITE_API_URL=...  # ✗ Remove this line completely
   ```

2. **Pull and rebuild:**
   ```bash
   git pull
   docker compose build frontend
   docker compose up -d frontend
   ```

3. **Test:**
   - Login at https://todo2.brooksmcmillin.com
   - Todos should load correctly
   - Check backend logs - all requests should come from same IP

## What Changed

The frontend now always uses relative URLs (`/api/todos`) which automatically go through SvelteKit's server-side proxy. This ensures session cookies are properly forwarded between frontend and backend.

See `COOKIE_FIX_SUMMARY.md` for detailed technical explanation.
