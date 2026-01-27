#!/bin/bash
set -e

SCRIPT_DIR="$(dirname "$0")"
CERT_DIR="$SCRIPT_DIR/../.certs"

# Check if certificates exist and are valid for at least 1 hour
NEEDS_REFRESH=true

if [ -f "$CERT_DIR/cert.pem" ]; then
    # Check if cert expires in less than 1 hour
    if openssl x509 -checkend 3600 -noout -in "$CERT_DIR/cert.pem" 2>/dev/null; then
        echo "✅ Certificate is still valid"
        NEEDS_REFRESH=false
    else
        echo "⚠️  Certificate expires soon, refreshing..."
    fi
else
    echo "📜 No certificate found, fetching..."
fi

# Fetch certificate if needed
if [ "$NEEDS_REFRESH" = true ]; then
    "$SCRIPT_DIR/fetch-certs.sh"
fi

# Start dev server
echo ""
echo "🚀 Starting dev server..."
npm run dev
