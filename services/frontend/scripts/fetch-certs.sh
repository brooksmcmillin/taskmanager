#!/bin/bash
set -e

DOMAIN="todo-stage.brooksmcmillin.com"
CERT_DIR="$(dirname "$0")/../.certs"
ACME_SERVER="https://certs.lan/acme/acme/directory"
EMAIL="certbot@ralki.com"

echo "🔐 Fetching certificate for $DOMAIN..."

# Create cert directory if it doesn't exist
mkdir -p "$CERT_DIR"

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    echo "❌ certbot not found. Please install it:"
    echo "   brew install certbot  (macOS)"
    echo "   apt-get install certbot  (Ubuntu/Debian)"
    exit 1
fi

# Use standalone mode to temporarily bind port 80 for validation
# This requires no web server to be running on port 80
sudo certbot certonly \
    --standalone \
    --non-interactive \
    --domain "$DOMAIN" \
    --server "$ACME_SERVER" \
    --email "$EMAIL" \
    --agree-tos \
    --preferred-challenges http \
    2>&1 | grep -v "^Saving debug log"

# Check if certificate was obtained
if [ $? -eq 0 ]; then
    # Copy certificates to our .certs directory
    sudo cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$CERT_DIR/cert.pem"
    sudo cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$CERT_DIR/key.pem"

    # Make readable by current user
    sudo chown $(whoami) "$CERT_DIR/cert.pem" "$CERT_DIR/key.pem"
    sudo chmod 644 "$CERT_DIR/cert.pem"
    sudo chmod 600 "$CERT_DIR/key.pem"

    echo "✅ Certificate fetched and installed successfully"

    # Show expiry
    EXPIRY=$(openssl x509 -enddate -noout -in "$CERT_DIR/cert.pem" | cut -d= -f2)
    echo "📅 Certificate expires: $EXPIRY"
else
    echo "❌ Failed to fetch certificate"
    echo ""
    echo "Troubleshooting:"
    echo "  - Ensure $DOMAIN resolves to this machine ($(hostname -I | awk '{print $1}'))"
    echo "  - Ensure no service is using port 80"
    echo "  - Check that https://certs.lan is accessible"
    exit 1
fi
