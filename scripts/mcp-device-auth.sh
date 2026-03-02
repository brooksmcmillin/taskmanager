#!/usr/bin/env bash
#
# mcp-device-auth.sh - Authenticate against the MCP server using the OAuth 2.0
# device authorization flow (RFC 8628) and update Claude Code's credentials.
#
# Finds ALL MCP server entries that share the same auth backend and writes the
# token to each, so a single auth flow covers multiple servers (e.g.
# mcp-resource and mcp-relay).
#
# Usage:
#   ./scripts/mcp-device-auth.sh
#
# Requirements: curl, jq

set -euo pipefail

# --- Configuration ---
CREDENTIALS_FILE="$HOME/.claude/.credentials.json"
AUTH_SERVER="https://mcp-auth.brooksmcmillin.com"
AUTH_SERVER_URL="$AUTH_SERVER/"
DEVICE_CODE_ENDPOINT="$AUTH_SERVER/device/code"
TOKEN_ENDPOINT="$AUTH_SERVER/token"
SCOPE="read"

# --- Preflight checks ---
for cmd in curl jq; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: '$cmd' is required but not installed." >&2
        exit 1
    fi
done

if [[ ! -f "$CREDENTIALS_FILE" ]]; then
    echo "Error: Claude Code credentials file not found at $CREDENTIALS_FILE" >&2
    exit 1
fi

# --- Helper: validate that a value is a positive integer ---
assert_integer() {
    local name="$1" value="$2"
    if ! [[ "$value" =~ ^[0-9]+$ ]]; then
        echo "Error: Invalid $name value from server: $value" >&2
        exit 1
    fi
}

# --- Find all MCP OAuth entries sharing this auth server ---
mapfile -t MCP_KEYS < <(jq -r --arg auth_url "$AUTH_SERVER_URL" \
    '.mcpOAuth | to_entries[]
     | select(.value.discoveryState.authorizationServerUrl == $auth_url)
     | .key' "$CREDENTIALS_FILE")

if [[ ${#MCP_KEYS[@]} -eq 0 ]]; then
    echo "Error: No MCP OAuth entries found using auth server $AUTH_SERVER_URL" >&2
    echo "Register at least one MCP server in Claude Code first." >&2
    exit 1
fi

echo "Found ${#MCP_KEYS[@]} MCP server(s) sharing auth backend:"
for key in "${MCP_KEYS[@]}"; do
    SERVER_NAME=$(jq -r --arg key "$key" '.mcpOAuth[$key].serverName // "unknown"' "$CREDENTIALS_FILE")
    SERVER_URL=$(jq -r --arg key "$key" '.mcpOAuth[$key].serverUrl // "unknown"' "$CREDENTIALS_FILE")
    echo "  - $SERVER_NAME ($SERVER_URL)"
done

# --- Use the first entry's client credentials for the device flow ---
PRIMARY_KEY="${MCP_KEYS[0]}"
CLIENT_ID=$(jq -r --arg key "$PRIMARY_KEY" '.mcpOAuth[$key].clientId' "$CREDENTIALS_FILE")
CLIENT_SECRET=$(jq -r --arg key "$PRIMARY_KEY" '.mcpOAuth[$key].clientSecret' "$CREDENTIALS_FILE")

if [[ -z "$CLIENT_ID" || "$CLIENT_ID" == "null" ]]; then
    echo "Error: No client_id found. Register the MCP server in Claude Code first." >&2
    exit 1
fi

if [[ -z "$CLIENT_SECRET" || "$CLIENT_SECRET" == "null" ]]; then
    echo "Error: No client_secret found. Register the MCP server in Claude Code first." >&2
    exit 1
fi

echo ""
echo "Using client_id: $CLIENT_ID"

# --- Step 1: Request device code ---
echo ""
echo "Requesting device code..."

DEVICE_RESPONSE=$(curl -s -X POST "$DEVICE_CODE_ENDPOINT" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "client_id=$CLIENT_ID" \
    --data-urlencode "scope=$SCOPE")

# Check for errors
if echo "$DEVICE_RESPONSE" | jq -e '.error' &>/dev/null; then
    ERROR=$(echo "$DEVICE_RESPONSE" | jq -r '.error')
    DESC=$(echo "$DEVICE_RESPONSE" | jq -r '.error_description // "No description"')
    echo "Error from server: $ERROR - $DESC" >&2
    exit 1
fi

DEVICE_CODE=$(echo "$DEVICE_RESPONSE" | jq -r '.device_code')
USER_CODE=$(echo "$DEVICE_RESPONSE" | jq -r '.user_code')
VERIFICATION_URI=$(echo "$DEVICE_RESPONSE" | jq -r '.verification_uri')
VERIFICATION_URI_COMPLETE=$(echo "$DEVICE_RESPONSE" | jq -r '.verification_uri_complete // empty')
EXPIRES_IN=$(echo "$DEVICE_RESPONSE" | jq -r '.expires_in // 300')
INTERVAL=$(echo "$DEVICE_RESPONSE" | jq -r '.interval // 5')

assert_integer "expires_in" "$EXPIRES_IN"
assert_integer "interval" "$INTERVAL"

echo ""
echo "========================================="
echo "  Open this URL in your browser:"
echo ""
echo "  ${VERIFICATION_URI_COMPLETE:-$VERIFICATION_URI}"
echo ""
echo "  Enter code: $USER_CODE"
echo "========================================="
echo ""
echo "Waiting for authorization (expires in ${EXPIRES_IN}s)..."

# --- Step 2: Poll for token ---
GRANT_TYPE="urn:ietf:params:oauth:grant-type:device_code"
DEADLINE=$((SECONDS + EXPIRES_IN))

while [[ $SECONDS -lt $DEADLINE ]]; do
    sleep "$INTERVAL"

    TOKEN_RESPONSE=$(curl -s -X POST "$TOKEN_ENDPOINT" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "grant_type=$GRANT_TYPE" \
        --data-urlencode "device_code=$DEVICE_CODE" \
        --data-urlencode "client_id=$CLIENT_ID" \
        --data-urlencode "client_secret=$CLIENT_SECRET")

    # Check if we got an access token
    ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token // empty')
    if [[ -n "$ACCESS_TOKEN" ]]; then
        EXPIRES_IN_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.expires_in // 3600')
        REFRESH_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.refresh_token // empty')

        assert_integer "expires_in (token)" "$EXPIRES_IN_TOKEN"
        EXPIRES_AT=$(( $(date +%s) * 1000 + EXPIRES_IN_TOKEN * 1000 ))

        echo ""
        echo "Authorization successful!"
        echo ""

        # --- Step 3: Update ALL matching entries in Claude Code credentials ---
        cp "$CREDENTIALS_FILE" "$CREDENTIALS_FILE.bak"
        chmod 600 "$CREDENTIALS_FILE.bak"
        trap 'rm -f "$CREDENTIALS_FILE.bak"' EXIT

        UPDATED=$(cat "$CREDENTIALS_FILE")
        for key in "${MCP_KEYS[@]}"; do
            JQ_FILTER='.mcpOAuth[$key].accessToken = $token | .mcpOAuth[$key].expiresAt = $expires'
            JQ_ARGS=(--arg key "$key" --arg token "$ACCESS_TOKEN" --argjson expires "$EXPIRES_AT")

            if [[ -n "$REFRESH_TOKEN" ]]; then
                JQ_FILTER="$JQ_FILTER | .mcpOAuth[\$key].refreshToken = \$refresh"
                JQ_ARGS+=(--arg refresh "$REFRESH_TOKEN")
            fi

            UPDATED=$(echo "$UPDATED" | jq "${JQ_ARGS[@]}" "$JQ_FILTER")
        done

        # Write atomically via temp file
        TMPFILE=$(mktemp "${CREDENTIALS_FILE}.tmp.XXXXXX")
        chmod 600 "$TMPFILE"
        echo "$UPDATED" > "$TMPFILE"
        mv "$TMPFILE" "$CREDENTIALS_FILE"

        EXPIRY_DATE=$(date -d @$((EXPIRES_AT / 1000)) 2>/dev/null || date -r $((EXPIRES_AT / 1000)) 2>/dev/null || echo "${EXPIRES_AT}ms")
        echo "Updated ${#MCP_KEYS[@]} credential entry/entries:"
        for key in "${MCP_KEYS[@]}"; do
            SERVER_NAME=$(jq -r --arg key "$key" '.mcpOAuth[$key].serverName // "unknown"' "$CREDENTIALS_FILE")
            echo "  - $SERVER_NAME ($key)"
        done
        echo ""
        echo "  Access token: ${ACCESS_TOKEN:0:20}..."
        echo "  Expires at: $EXPIRY_DATE"
        if [[ -n "$REFRESH_TOKEN" ]]; then
            echo "  Refresh token: ${REFRESH_TOKEN:0:20}..."
        fi
        echo ""
        echo "Restart Claude Code to use the new token."
        exit 0
    fi

    # Check for errors
    ERROR=$(echo "$TOKEN_RESPONSE" | jq -r '.error // empty')
    if [[ -z "$ERROR" ]]; then
        echo ""
        echo "Error: Unexpected response from server (no access_token or error field)" >&2
        exit 1
    fi
    case "$ERROR" in
        authorization_pending)
            printf "."
            ;;
        slow_down)
            INTERVAL=$((INTERVAL + 5))
            printf "s"
            ;;
        expired_token)
            echo ""
            echo "Error: Device code expired. Run the script again." >&2
            exit 1
            ;;
        access_denied)
            echo ""
            echo "Error: Authorization was denied." >&2
            exit 1
            ;;
        *)
            DESC=$(echo "$TOKEN_RESPONSE" | jq -r '.error_description // "Unknown error"')
            echo ""
            echo "Error: $ERROR - $DESC" >&2
            exit 1
            ;;
    esac
done

echo ""
echo "Error: Timed out waiting for authorization." >&2
exit 1
