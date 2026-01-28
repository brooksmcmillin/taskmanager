# Frontend Development Scripts

## Certificate Management for Staging

### Overview

The staging environment (`todo-stage.brooksmcmillin.com`) uses certificates from a Step CA instance via ACME. These certificates are typically short-lived (24 hours) and need to be refreshed regularly.

### Scripts

#### `fetch-certs.sh`

Fetches a new certificate from the Step CA ACME server and installs it to `.certs/`.

**Usage:**

```bash
./scripts/fetch-certs.sh
```

**Requirements:**

- `certbot` must be installed
- Port 80 must be available (no web server running)
- Domain must resolve to this machine via DNS
- Step CA ACME server must be accessible at `https://certs.lan`

**What it does:**

1. Uses certbot with standalone mode to get a certificate
2. Validates domain ownership via HTTP-01 challenge on port 80
3. Copies certificate files to `.certs/cert.pem` and `.certs/key.pem`
4. Sets proper permissions

#### `dev-with-certs.sh`

Wrapper script that fetches certificates (if needed) and starts the dev server.

**Usage:**

```bash
npm run dev:stage
```

**What it does:**

1. Checks if certificate exists and is valid for at least 1 hour
2. Fetches a new certificate if needed or expiring soon
3. Starts the Vite dev server

### Setup

1. **Install certbot:**

   ```bash
   # macOS
   brew install certbot

   # Ubuntu/Debian
   sudo apt-get install certbot
   ```

2. **Ensure DNS is configured:**
   - `todo-stage.brooksmcmillin.com` should resolve to this machine's IP
   - Test: `dig todo-stage.brooksmcmillin.com` or `nslookup todo-stage.brooksmcmillin.com`

3. **Update hosts file** (if using local DNS):

   ```bash
   sudo nano /etc/hosts
   ```

   Add: `10.0.13.55  todo-stage.brooksmcmillin.com`

4. **Start development:**
   ```bash
   cd services/frontend
   npm run dev:stage
   ```

### Troubleshooting

**"certbot not found"**

- Install certbot (see Setup above)

**"Address already in use" or port 80 errors**

- Another service is using port 80
- Stop any running web servers: `sudo lsof -i :80`

**"Failed to fetch certificate"**

- Check DNS resolution: `dig todo-stage.brooksmcmillin.com`
- Verify Step CA is accessible: `curl https://certs.lan/acme/acme/directory`
- Check firewall rules allow inbound port 80

**Certificate validation issues**

- Ensure domain resolves to this machine's IP (10.0.13.55)
- Check that Step CA can reach this machine on port 80

### Manual Certificate Fetch

If you need to manually fetch a certificate:

```bash
cd services/frontend
./scripts/fetch-certs.sh
```

### Certificate Locations

- **Certbot storage:** `/etc/letsencrypt/live/todo-stage.brooksmcmillin.com/`
- **Vite dev server:** `services/frontend/.certs/`
  - `cert.pem` - Full certificate chain
  - `key.pem` - Private key

### Security Notes

- The private key is stored with 600 permissions (owner read/write only)
- Certificates are fetched over HTTPS from the Step CA
- HTTP-01 challenge only requires temporary port 80 access
- Self-signed certificates in `.certs/` (for fallback) are NOT used when Step CA certs are available
