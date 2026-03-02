#!/usr/bin/env bash
#
# mcp-refresh-token.sh - Refresh the MCP OAuth access token using the stored
# refresh token and update Claude Code's credentials file.
#
# Designed to run as a cron job to keep the token fresh without human
# interaction. The refresh token has a 7-day TTL and is rotated on each use,
# so running this hourly (or every 30 minutes) keeps the session alive
# indefinitely.
#
# Finds ALL MCP server entries that share the same auth backend and writes the
# refreshed token to each, so a single refresh covers multiple servers (e.g.
# mcp-resource and mcp-relay).
#
# Usage:
#   NTFY_TOKEN=tk_... ./scripts/mcp-refresh-token.sh
#
# Cron example (every 45 minutes):
#   */45 * * * * set -a; . /path/to/.env; set +a; /path/to/scripts/mcp-refresh-token.sh >> ~/.local/log/mcp-refresh.log 2>&1
#
# Environment variables:
#   NTFY_TOKEN  - (required) ntfy bearer token for push notifications
#   NTFY_URL    - (optional) ntfy topic URL, defaults to https://ntfy.brooksmcmillin.com/mcp-alerts
#
# Requirements: curl, jq

set -euo pipefail

# --- Configuration ---
CREDENTIALS_FILE="$HOME/.claude/.credentials.json"
AUTH_SERVER="https://mcp-auth.brooksmcmillin.com"
AUTH_SERVER_URL="$AUTH_SERVER/"
TOKEN_ENDPOINT="$AUTH_SERVER/token"
NTFY_URL="${NTFY_URL:-https://ntfy.brooksmcmillin.com/mcp-alerts}"
: "${NTFY_TOKEN:?Error: NTFY_TOKEN environment variable is not set}"

# --- Alert helper: send push notification on failure ---
send_alert() {
    local title="$1" message="$2" priority="${3:-high}"
    curl -s -o /dev/null \
        -H "Authorization: Bearer $NTFY_TOKEN" \
        -H "Title: $title" \
        -H "Priority: $priority" \
        -H "Tags: warning" \
        -d "$message" \
        "$NTFY_URL" || true
}

# --- Preflight checks ---
for cmd in curl jq; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "$(date -Iseconds) Error: '$cmd' is required but not installed." >&2
        exit 1
    fi
done

if [[ ! -f "$CREDENTIALS_FILE" ]]; then
    echo "$(date -Iseconds) Error: Credentials file not found at $CREDENTIALS_FILE" >&2
    exit 1
fi

# --- Helper: validate that a value is a positive integer ---
assert_integer() {
    local name="$1" value="$2"
    if ! [[ "$value" =~ ^[0-9]+$ ]]; then
        echo "$(date -Iseconds) Error: Invalid $name value from server: $value" >&2
        exit 1
    fi
}

# --- Find all MCP OAuth entries sharing this auth server ---
mapfile -t MCP_KEYS < <(jq -r --arg auth_url "$AUTH_SERVER_URL" \
    '.mcpOAuth | to_entries[]
     | select((.value.discoveryState.authorizationServerUrl // "") | rtrimstr("/") == ($auth_url | rtrimstr("/")))
     | .key' "$CREDENTIALS_FILE")

if [[ ${#MCP_KEYS[@]} -eq 0 ]]; then
    echo "$(date -Iseconds) Error: No MCP OAuth entries found using auth server $AUTH_SERVER_URL" >&2
    exit 1
fi

# --- Use the first entry's credentials for the refresh ---
PRIMARY_KEY="${MCP_KEYS[0]}"
CLIENT_ID=$(jq -r --arg key "$PRIMARY_KEY" '.mcpOAuth[$key].clientId' "$CREDENTIALS_FILE")
CLIENT_SECRET=$(jq -r --arg key "$PRIMARY_KEY" '.mcpOAuth[$key].clientSecret' "$CREDENTIALS_FILE")
REFRESH_TOKEN=$(jq -r --arg key "$PRIMARY_KEY" '.mcpOAuth[$key].refreshToken' "$CREDENTIALS_FILE")

if [[ -z "$CLIENT_ID" || "$CLIENT_ID" == "null" ]]; then
    echo "$(date -Iseconds) Error: No client_id found. Run mcp-device-auth.sh first." >&2
    exit 1
fi

if [[ -z "$CLIENT_SECRET" || "$CLIENT_SECRET" == "null" ]]; then
    echo "$(date -Iseconds) Error: No client_secret found. Run mcp-device-auth.sh first." >&2
    exit 1
fi

if [[ -z "$REFRESH_TOKEN" || "$REFRESH_TOKEN" == "null" ]]; then
    echo "$(date -Iseconds) Error: No refresh_token found. Run mcp-device-auth.sh first." >&2
    send_alert "MCP Token: No Refresh Token" "No refresh_token in credentials. Run mcp-device-auth.sh to re-authenticate."
    exit 1
fi

# --- Check if access token is still valid (skip refresh if not expiring soon) ---
EXPIRES_AT=$(jq -r --arg key "$PRIMARY_KEY" '.mcpOAuth[$key].expiresAt // 0' "$CREDENTIALS_FILE")
NOW_MS=$(( $(date +%s) * 1000 ))
# Refresh if token expires within 10 minutes (600000ms)
BUFFER_MS=600000
if [[ "$EXPIRES_AT" =~ ^[0-9]+$ ]] && (( EXPIRES_AT - NOW_MS > BUFFER_MS )); then
    REMAINING_MIN=$(( (EXPIRES_AT - NOW_MS) / 60000 ))
    echo "$(date -Iseconds) Token still valid for ~${REMAINING_MIN} minutes, skipping refresh. (${#MCP_KEYS[@]} server(s) covered)"
    exit 0
fi

echo "$(date -Iseconds) Refreshing access token for ${#MCP_KEYS[@]} server(s)..."

# --- Request new token using refresh_token grant ---
HTTP_CODE=0
TOKEN_RESPONSE=$(curl -s --fail-with-body -w '\n%{http_code}' -X POST "$TOKEN_ENDPOINT" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "grant_type=refresh_token" \
    --data-urlencode "refresh_token=$REFRESH_TOKEN" \
    --data-urlencode "client_id=$CLIENT_ID" \
    --data-urlencode "client_secret=$CLIENT_SECRET") || true
HTTP_CODE=$(echo "$TOKEN_RESPONSE" | tail -n1)
TOKEN_RESPONSE=$(echo "$TOKEN_RESPONSE" | sed '$d')

# Check for HTTP-level failures (non-JSON 502/503, connection errors, etc.)
if [[ -z "$TOKEN_RESPONSE" ]] || ! echo "$TOKEN_RESPONSE" | jq empty 2>/dev/null; then
    echo "$(date -Iseconds) Error: Auth server returned non-JSON response (HTTP $HTTP_CODE)" >&2
    echo "$(date -Iseconds) Response body: ${TOKEN_RESPONSE:-(empty)}" >&2
    send_alert "MCP Token: Auth Server Error" "Auth server returned HTTP $HTTP_CODE with non-JSON response. Check server health."
    exit 1
fi

# --- Check for OAuth errors ---
ERROR=$(echo "$TOKEN_RESPONSE" | jq -r '.error // empty')
if [[ -n "$ERROR" ]]; then
    DESC=$(echo "$TOKEN_RESPONSE" | jq -r '.error_description // "No description"')
    echo "$(date -Iseconds) Error: $ERROR - $DESC" >&2
    if [[ "$ERROR" == "invalid_grant" ]]; then
        echo "$(date -Iseconds) Refresh token is invalid or expired. Run mcp-device-auth.sh to re-authenticate." >&2
        send_alert "MCP Token: Refresh Token Expired" "Refresh token is invalid or expired. Run mcp-device-auth.sh to re-authenticate." "urgent"
    else
        send_alert "MCP Token: Refresh Failed" "Token refresh failed: $ERROR - $DESC"
    fi
    exit 1
fi

# --- Extract new tokens ---
ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token // empty')
if [[ -z "$ACCESS_TOKEN" ]]; then
    echo "$(date -Iseconds) Error: No access_token in response." >&2
    send_alert "MCP Token: Unexpected Response" "Token endpoint returned no access_token. Check auth server health."
    exit 1
fi

EXPIRES_IN=$(echo "$TOKEN_RESPONSE" | jq -r '.expires_in // 3600')
NEW_REFRESH_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.refresh_token // empty')

assert_integer "expires_in" "$EXPIRES_IN"
NEW_EXPIRES_AT=$(( $(date +%s) * 1000 + EXPIRES_IN * 1000 ))

# --- Update ALL matching entries in Claude Code credentials ---
TMPFILE=""
cp "$CREDENTIALS_FILE" "$CREDENTIALS_FILE.bak"
chmod 600 "$CREDENTIALS_FILE.bak"
trap 'rm -f "$CREDENTIALS_FILE.bak" "$TMPFILE"' EXIT

UPDATED=$(cat "$CREDENTIALS_FILE")
for key in "${MCP_KEYS[@]}"; do
    JQ_FILTER='.mcpOAuth[$key].accessToken = $token | .mcpOAuth[$key].expiresAt = $expires'
    JQ_ARGS=(--arg key "$key" --arg token "$ACCESS_TOKEN" --argjson expires "$NEW_EXPIRES_AT")

    if [[ -n "$NEW_REFRESH_TOKEN" ]]; then
        JQ_FILTER="$JQ_FILTER | .mcpOAuth[\$key].refreshToken = \$refresh"
        JQ_ARGS+=(--arg refresh "$NEW_REFRESH_TOKEN")
    fi

    UPDATED=$(echo "$UPDATED" | jq "${JQ_ARGS[@]}" "$JQ_FILTER")
done

# Write atomically via temp file
TMPFILE=$(mktemp "${CREDENTIALS_FILE}.tmp.XXXXXX")
chmod 600 "$TMPFILE"
echo "$UPDATED" > "$TMPFILE"
mv "$TMPFILE" "$CREDENTIALS_FILE"

EXPIRY_DATE=$(date -d @$((NEW_EXPIRES_AT / 1000)) 2>/dev/null || date -r $((NEW_EXPIRES_AT / 1000)) 2>/dev/null || echo "${NEW_EXPIRES_AT}ms")
echo "$(date -Iseconds) Token refreshed successfully for ${#MCP_KEYS[@]} server(s). Expires at: $EXPIRY_DATE"
