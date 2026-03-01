#!/usr/bin/env bash
#
# install-cron.sh - Install the MCP OAuth token refresh cron job.
#
# Idempotent: safe to run multiple times; will not create duplicate entries.
#
# Usage:
#   ./scripts/install-cron.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REFRESH_SCRIPT="$SCRIPT_DIR/mcp-refresh-token.sh"
ENV_FILE="$PROJECT_DIR/.env"
LOG_FILE="/tmp/mcp-refresh.log"
CRON_MARKER="mcp-refresh-token.sh"

if [[ ! -f "$REFRESH_SCRIPT" ]]; then
    echo "Error: $REFRESH_SCRIPT not found." >&2
    exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: $ENV_FILE not found. Copy .env.example to .env and configure it." >&2
    exit 1
fi

if ! grep -q 'NTFY_TOKEN' "$ENV_FILE"; then
    echo "Error: NTFY_TOKEN not found in $ENV_FILE. Add it before installing the cron job." >&2
    exit 1
fi

# Check if already installed
if crontab -l 2>/dev/null | grep -qF "$CRON_MARKER"; then
    echo "Cron job already installed. No changes made."
    crontab -l | grep -F "$CRON_MARKER"
    exit 0
fi

# Append to existing crontab
CRON_LINE="*/45 * * * * set -a; . $ENV_FILE; set +a; $REFRESH_SCRIPT >> $LOG_FILE 2>&1"
(crontab -l 2>/dev/null; echo ""; echo "# MCP OAuth token refresh (every 45 min)"; echo "$CRON_LINE") | crontab -

echo "Cron job installed:"
echo "  $CRON_LINE"
