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
# Usage:
#   NTFY_TOKEN=tk_... ./scripts/mcp-refresh-token.sh
#
# Cron example (every 45 minutes):
#   */45 * * * * NTFY_TOKEN=tk_... /path/to/taskmanager/scripts/mcp-refresh-token.sh >> /tmp/mcp-refresh.log 2>&1
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

# --- Extract credentials from Claude Code's stored config ---
MCP_KEY=$(jq -r '.mcpOAuth | keys[] | select(startswith("taskmanager|"))' "$CREDENTIALS_FILE" | head -n1)
if [[ -z "$MCP_KEY" ]]; then
    echo "$(date -Iseconds) Error: No taskmanager MCP OAuth entry found in credentials file." >&2
    exit 1
fi

CLIENT_ID=$(jq -r --arg key "$MCP_KEY" '.mcpOAuth[$key].clientId' "$CREDENTIALS_FILE")
CLIENT_SECRET=$(jq -r --arg key "$MCP_KEY" '.mcpOAuth[$key].clientSecret' "$CREDENTIALS_FILE")
REFRESH_TOKEN=$(jq -r --arg key "$MCP_KEY" '.mcpOAuth[$key].refreshToken' "$CREDENTIALS_FILE")

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
EXPIRES_AT=$(jq -r --arg key "$MCP_KEY" '.mcpOAuth[$key].expiresAt // 0' "$CREDENTIALS_FILE")
NOW_MS=$(( $(date +%s) * 1000 ))
# Refresh if token expires within 10 minutes (600000ms)
BUFFER_MS=600000
if [[ "$EXPIRES_AT" =~ ^[0-9]+$ ]] && (( EXPIRES_AT - NOW_MS > BUFFER_MS )); then
    REMAINING_MIN=$(( (EXPIRES_AT - NOW_MS) / 60000 ))
    echo "$(date -Iseconds) Token still valid for ~${REMAINING_MIN} minutes, skipping refresh."
    exit 0
fi

echo "$(date -Iseconds) Refreshing access token..."

# --- Request new token using refresh_token grant ---
TOKEN_RESPONSE=$(curl -s -X POST "$TOKEN_ENDPOINT" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "grant_type=refresh_token" \
    --data-urlencode "refresh_token=$REFRESH_TOKEN" \
    --data-urlencode "client_id=$CLIENT_ID" \
    --data-urlencode "client_secret=$CLIENT_SECRET")

# --- Check for errors ---
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

# --- Update Claude Code credentials ---
TMPFILE=""
cp "$CREDENTIALS_FILE" "$CREDENTIALS_FILE.bak"
chmod 600 "$CREDENTIALS_FILE.bak"
trap 'rm -f "$CREDENTIALS_FILE.bak" "$TMPFILE"' EXIT

JQ_FILTER='.mcpOAuth[$key].accessToken = $token | .mcpOAuth[$key].expiresAt = $expires'
JQ_ARGS=(--arg key "$MCP_KEY" --arg token "$ACCESS_TOKEN" --argjson expires "$NEW_EXPIRES_AT")

if [[ -n "$NEW_REFRESH_TOKEN" ]]; then
    JQ_FILTER="$JQ_FILTER | .mcpOAuth[\$key].refreshToken = \$refresh"
    JQ_ARGS+=(--arg refresh "$NEW_REFRESH_TOKEN")
fi

UPDATED=$(jq "${JQ_ARGS[@]}" "$JQ_FILTER" "$CREDENTIALS_FILE")

# Write atomically via temp file
TMPFILE=$(mktemp "${CREDENTIALS_FILE}.tmp.XXXXXX")
chmod 600 "$TMPFILE"
echo "$UPDATED" > "$TMPFILE"
mv "$TMPFILE" "$CREDENTIALS_FILE"

EXPIRY_DATE=$(date -d @$((NEW_EXPIRES_AT / 1000)) 2>/dev/null || date -r $((NEW_EXPIRES_AT / 1000)) 2>/dev/null || echo "${NEW_EXPIRES_AT}ms")
echo "$(date -Iseconds) Token refreshed successfully. Expires at: $EXPIRY_DATE"
