#!/bin/bash

# OAuth Flow Test Script for TaskManager
# This script tests the complete OAuth 2.0 authorization code flow

set -e

# Configuration
BASE_URL="http://localhost:4321"
REDIRECT_URI="http://localhost:8080/callback"
SCOPE="read write"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    log_error "jq is required but not installed. Please install jq to run this test."
    exit 1
fi

# Check if server is running
log_info "Checking if server is running at $BASE_URL..."
if ! curl -s "$BASE_URL" > /dev/null 2>&1; then
    log_error "Server is not running at $BASE_URL. Please start the server with 'npm run dev'"
    exit 1
fi
log_success "Server is running"

# Get session cookie for authenticated requests
log_info "You need to be logged in to create OAuth clients."
echo "Please provide your session cookie from the browser:"
echo "1. Go to $BASE_URL in your browser"
echo "2. Log in to your account"
echo "3. Open Developer Tools (F12)"
echo "4. Go to Application/Storage tab"
echo "5. Find the session cookie value"
echo ""
read -p "Enter your session cookie value: " SESSION_COOKIE

if [ -z "$SESSION_COOKIE" ]; then
    log_error "Session cookie is required to create OAuth clients"
    exit 1
fi

# Test 1: Create OAuth Client
log_info "Step 1: Creating OAuth client..."
CLIENT_RESPONSE=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$BASE_URL/api/oauth/clients" \
    -H "Content-Type: application/json" \
    -H "Cookie: session=$SESSION_COOKIE" \
    -d "{
        \"name\": \"Test OAuth App\",
        \"redirectUris\": [\"$REDIRECT_URI\"],
        \"grantTypes\": [\"authorization_code\"],
        \"scopes\": [\"read\", \"write\"]
    }" || {
        log_error "Failed to create OAuth client"
        exit 1
    })

# Extract HTTP status and body
HTTP_STATUS=$(echo "$CLIENT_RESPONSE" | sed -n 's/.*HTTPSTATUS:\([0-9]*\)$/\1/p')
CLIENT_BODY=$(echo "$CLIENT_RESPONSE" | sed 's/HTTPSTATUS:[0-9]*$//')

log_info "HTTP Status: $HTTP_STATUS"
log_info "Response Body: $CLIENT_BODY"

# Check if request was successful
if [ "$HTTP_STATUS" != "201" ]; then
    log_error "Failed to create OAuth client. Status: $HTTP_STATUS, Response: $CLIENT_BODY"
    if [ "$HTTP_STATUS" = "401" ]; then
        log_error "Authentication failed. Please check your session cookie."
        log_info "Make sure you're logged in and copied the correct session cookie value."
    fi
    exit 1
fi

# Check if response is valid JSON
if ! echo "$CLIENT_BODY" | jq . > /dev/null 2>&1; then
    log_error "Invalid JSON response: $CLIENT_BODY"
    exit 1
fi

# Extract client credentials
CLIENT_ID=$(echo "$CLIENT_BODY" | jq -r '.client_id // empty')
CLIENT_SECRET=$(echo "$CLIENT_BODY" | jq -r '.client_secret // empty')

if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
    log_error "Failed to extract client credentials. Response: $CLIENT_BODY"
    exit 1
fi

log_success "OAuth client created successfully"
log_info "Client ID: $CLIENT_ID"
log_info "Client Secret: $CLIENT_SECRET"

# Test 2: Generate PKCE parameters (optional but recommended)
log_info "Step 2: Generating PKCE parameters..."
CODE_VERIFIER=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-43)
CODE_CHALLENGE=$(echo -n "$CODE_VERIFIER" | openssl dgst -sha256 -binary | openssl base64 | tr -d "=+/" | cut -c1-43)
CODE_CHALLENGE_METHOD="S256"

log_info "Code Verifier: $CODE_VERIFIER"
log_info "Code Challenge: $CODE_CHALLENGE"

# Test 3: Build authorization URL
log_info "Step 3: Building authorization URL..."
STATE=$(openssl rand -hex 16)
AUTH_URL="$BASE_URL/api/oauth/authorize?client_id=$CLIENT_ID&redirect_uri=$REDIRECT_URI&response_type=code&scope=$SCOPE&state=$STATE&code_challenge=$CODE_CHALLENGE&code_challenge_method=$CODE_CHALLENGE_METHOD"

log_success "Authorization URL generated"
echo ""
echo "=================================================="
echo "MANUAL STEP REQUIRED:"
echo "=================================================="
echo "1. Open this URL in your browser:"
echo ""
echo "$AUTH_URL"
echo ""
echo "2. Authorize the application"
echo "3. You will be redirected to: $REDIRECT_URI?code=...&state=..."
echo "4. Copy the 'code' parameter from the URL"
echo ""
read -p "Enter the authorization code from the redirect URL: " AUTH_CODE

if [ -z "$AUTH_CODE" ]; then
    log_error "Authorization code is required"
    exit 1
fi

# Test 4: Exchange authorization code for access token
log_info "Step 4: Exchanging authorization code for access token..."
TOKEN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/oauth/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=authorization_code" \
    -d "client_id=$CLIENT_ID" \
    -d "client_secret=$CLIENT_SECRET" \
    -d "code=$AUTH_CODE" \
    -d "redirect_uri=$REDIRECT_URI" \
    -d "code_verifier=$CODE_VERIFIER" || {
        log_error "Failed to exchange authorization code"
        exit 1
    })

# Extract tokens
ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token // empty')
REFRESH_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.refresh_token // empty')
TOKEN_TYPE=$(echo "$TOKEN_RESPONSE" | jq -r '.token_type // empty')
EXPIRES_IN=$(echo "$TOKEN_RESPONSE" | jq -r '.expires_in // empty')

if [ -z "$ACCESS_TOKEN" ]; then
    log_error "Failed to get access token. Response: $TOKEN_RESPONSE"
    exit 1
fi

log_success "Access token obtained successfully"
log_info "Access Token: ${ACCESS_TOKEN:0:20}..."
log_info "Token Type: $TOKEN_TYPE"
log_info "Expires In: $EXPIRES_IN seconds"
log_info "Refresh Token: ${REFRESH_TOKEN:0:20}..."

# Test 5: Test API access with access token
log_info "Step 5: Testing API access with access token..."
API_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
    "$BASE_URL/api/todos" || {
        log_error "Failed to access API with access token"
        exit 1
    })

if echo "$API_RESPONSE" | jq -e 'type == "array"' > /dev/null 2>&1; then
    TODO_COUNT=$(echo "$API_RESPONSE" | jq 'length')
    log_success "API access successful - Retrieved $TODO_COUNT todos"
else
    log_error "API access failed. Response: $API_RESPONSE"
    exit 1
fi

# Test 6: Test refresh token
log_info "Step 6: Testing refresh token..."
REFRESH_RESPONSE=$(curl -s -X POST "$BASE_URL/api/oauth/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=refresh_token" \
    -d "client_id=$CLIENT_ID" \
    -d "client_secret=$CLIENT_SECRET" \
    -d "refresh_token=$REFRESH_TOKEN" || {
        log_error "Failed to refresh token"
        exit 1
    })

NEW_ACCESS_TOKEN=$(echo "$REFRESH_RESPONSE" | jq -r '.access_token // empty')
NEW_REFRESH_TOKEN=$(echo "$REFRESH_RESPONSE" | jq -r '.refresh_token // empty')

if [ -z "$NEW_ACCESS_TOKEN" ]; then
    log_error "Failed to refresh token. Response: $REFRESH_RESPONSE"
    exit 1
fi

log_success "Token refresh successful"
log_info "New Access Token: ${NEW_ACCESS_TOKEN:0:20}..."
log_info "New Refresh Token: ${NEW_REFRESH_TOKEN:0:20}..."

# Test 7: Test API with new access token
log_info "Step 7: Testing API with refreshed access token..."
NEW_API_RESPONSE=$(curl -s -H "Authorization: Bearer $NEW_ACCESS_TOKEN" \
    "$BASE_URL/api/todos" || {
        log_error "Failed to access API with refreshed token"
        exit 1
    })

if echo "$NEW_API_RESPONSE" | jq -e 'type == "array"' > /dev/null 2>&1; then
    log_success "API access with refreshed token successful"
else
    log_error "API access with refreshed token failed"
    exit 1
fi

# Test 8: Test scope validation (try to create a todo)
log_info "Step 8: Testing write scope by creating a todo..."
CREATE_TODO_RESPONSE=$(curl -s -X POST "$BASE_URL/api/todos" \
    -H "Authorization: Bearer $NEW_ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
        \"title\": \"OAuth Test Todo\",
        \"description\": \"Created via OAuth API\",
        \"priority\": 1
    }" || {
        log_warning "Failed to create todo (might be expected if write scope not granted)"
    })

if echo "$CREATE_TODO_RESPONSE" | jq -e '.id' > /dev/null 2>&1; then
    TODO_ID=$(echo "$CREATE_TODO_RESPONSE" | jq -r '.id')
    log_success "Todo created successfully via OAuth (ID: $TODO_ID)"
    
    # Clean up - delete the test todo
    DELETE_RESPONSE=$(curl -s -X DELETE "$BASE_URL/api/todos/$TODO_ID" \
        -H "Authorization: Bearer $NEW_ACCESS_TOKEN" || true)
    log_info "Test todo cleaned up"
else
    log_warning "Could not create todo - check if write scope was granted"
fi

echo ""
echo "=================================================="
echo "OAuth Flow Test Results:"
echo "=================================================="
log_success "✓ OAuth client creation"
log_success "✓ Authorization URL generation"
log_success "✓ Authorization code exchange"
log_success "✓ Access token validation"
log_success "✓ API access with Bearer token"
log_success "✓ Token refresh"
log_success "✓ API access with refreshed token"

echo ""
log_info "OAuth implementation is working correctly!"
echo ""
echo "Summary:"
echo "- Client ID: $CLIENT_ID"
echo "- Access Token: ${NEW_ACCESS_TOKEN:0:20}..."
echo "- Refresh Token: ${NEW_REFRESH_TOKEN:0:20}..."
echo ""
echo "You can now integrate with this OAuth server using these credentials."