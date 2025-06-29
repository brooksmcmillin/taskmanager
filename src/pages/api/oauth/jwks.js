export async function GET({ request }) {
  try {
    // TODO: Replace with your actual RSA public key
    // Generate with: openssl genrsa -out private.pem 2048 && openssl rsa -in private.pem -pubout -out public.pem
    const jwks = {
      "keys": [
        {
          "kty": "RSA",
          "use": "sig",
          "kid": "taskmanager-mcp-key-1",
          "alg": "RS256",
          // TODO: Replace these with your actual RSA public key components
          // You can generate these from your public key using crypto libraries
          "n": "REPLACE_WITH_BASE64URL_ENCODED_MODULUS",
          "e": "AQAB"
        }
      ]
    };

    return new Response(JSON.stringify(jwks), {
      status: 200,
      headers: { 
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=3600'
      }
    });
  } catch (error) {
    console.error('JWKS endpoint error:', error);
    return new Response(JSON.stringify({
      error: 'server_error',
      error_description: 'Failed to retrieve JWKS'
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}