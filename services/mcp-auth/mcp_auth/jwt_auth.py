"""
JWT Client Authentication (private_key_jwt)

This module implements RFC 7523 (JWT Profile for OAuth 2.0 Client Authentication)
for CIMD clients that use private_key_jwt authentication.

When a client uses private_key_jwt:
1. Client signs a JWT with its private key
2. Client sends JWT as client_assertion in token request
3. Server fetches client's public key (JWKS) from metadata
4. Server verifies JWT signature and claims

Security features:
- Algorithm whitelist to prevent algorithm confusion attacks
- JWT replay protection via jti tracking
- Short expiration times enforced
"""

import logging
import threading
import time
from typing import Any

import jwt
from jwt import PyJWKClient

from .cimd import CIMDFetcher, get_cimd_fetcher

logger = logging.getLogger(__name__)

# JWT validation constants
JWT_MAX_CLOCK_SKEW_SECONDS = 60  # Allow 60 seconds of clock skew
JWT_MAX_LIFETIME_SECONDS = 300  # JWT should not be valid for more than 5 minutes
JWT_REPLAY_CACHE_CLEANUP_INTERVAL = 60  # Clean up expired JTIs every 60 seconds

# Allowed JWT algorithms (explicit whitelist to prevent algorithm confusion)
# Only asymmetric algorithms are allowed for private_key_jwt
ALLOWED_JWT_ALGORITHMS = {
    "RS256",
    "RS384",
    "RS512",  # RSA with SHA-2
    "ES256",
    "ES384",
    "ES512",  # ECDSA with SHA-2
    "PS256",
    "PS384",
    "PS512",  # RSA-PSS with SHA-2
}

# Explicitly blocked algorithms
BLOCKED_JWT_ALGORITHMS = {
    "none",  # No signature - never allowed
    "HS256",
    "HS384",
    "HS512",  # Symmetric algorithms - not allowed for private_key_jwt
}


class JWTAuthError(Exception):
    """Error during JWT client authentication."""

    pass


class JWTClientAuthenticator:
    """
    Authenticates clients using private_key_jwt (RFC 7523).

    This is used by CIMD confidential clients that sign JWTs
    with their private key for client authentication.

    Security features:
    - Algorithm whitelist (only asymmetric algorithms allowed)
    - JWT replay protection via jti tracking
    - Short expiration time enforcement
    """

    def __init__(
        self,
        token_endpoint: str,
        cimd_fetcher: CIMDFetcher | None = None,
    ):
        """
        Initialize the JWT authenticator.

        Args:
            token_endpoint: The token endpoint URL (used as audience claim)
            cimd_fetcher: Optional CIMD fetcher for getting client JWKS
        """
        self.token_endpoint = token_endpoint
        self.cimd_fetcher = cimd_fetcher or get_cimd_fetcher()
        self._jwk_clients: dict[str, PyJWKClient] = {}

        # JWT replay protection: track used jti values with their expiry times
        # Key: jti, Value: expiry timestamp
        self._used_jtis: dict[str, float] = {}
        self._jti_lock = threading.Lock()
        self._last_cleanup = time.time()

    def _cleanup_expired_jtis(self) -> None:
        """Remove expired JTIs from the replay cache."""
        now = time.time()

        # Only cleanup periodically to avoid lock contention
        if now - self._last_cleanup < JWT_REPLAY_CACHE_CLEANUP_INTERVAL:
            return

        with self._jti_lock:
            # Double-check after acquiring lock
            if now - self._last_cleanup < JWT_REPLAY_CACHE_CLEANUP_INTERVAL:
                return

            expired_jtis = [jti for jti, exp in self._used_jtis.items() if now > exp]
            for jti in expired_jtis:
                del self._used_jtis[jti]

            if expired_jtis:
                logger.debug(f"Cleaned up {len(expired_jtis)} expired JTIs from replay cache")

            self._last_cleanup = now

    def _check_and_record_jti(self, jti: str, exp: float) -> bool:
        """
        Check if a JTI has been used and record it if not.

        Args:
            jti: The JWT ID
            exp: The expiry timestamp

        Returns:
            True if the JTI is new (not a replay), False if it's been seen before
        """
        # Cleanup expired entries periodically
        self._cleanup_expired_jtis()

        with self._jti_lock:
            if jti in self._used_jtis:
                return False  # Replay detected
            self._used_jtis[jti] = exp
            return True

    async def authenticate(
        self,
        client_id: str,
        client_assertion: str,
        client_assertion_type: str,
    ) -> bool:
        """
        Authenticate a client using private_key_jwt.

        Args:
            client_id: The client's identifier (CIMD URL)
            client_assertion: The signed JWT
            client_assertion_type: Must be "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"

        Returns:
            True if authentication succeeds

        Raises:
            JWTAuthError: If authentication fails
        """
        # Validate assertion type
        if client_assertion_type != "urn:ietf:params:oauth:client-assertion-type:jwt-bearer":
            raise JWTAuthError(
                f"Invalid client_assertion_type: {client_assertion_type}. "
                "Expected urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
            )

        if not client_assertion:
            raise JWTAuthError("Missing client_assertion")

        # Get the client's JWKS
        jwks = await self._get_client_jwks(client_id)
        if not jwks:
            raise JWTAuthError(f"Could not retrieve JWKS for client {client_id}")

        # Verify the JWT
        try:
            await self._verify_jwt(client_id, client_assertion, jwks)
            logger.info(f"Successfully authenticated client {client_id} via private_key_jwt")
            return True
        except JWTAuthError:
            raise
        except Exception as e:
            raise JWTAuthError(f"JWT verification failed: {e}") from e

    async def _get_client_jwks(self, client_id: str) -> dict[str, Any] | None:
        """
        Get the JWKS for a client.

        Args:
            client_id: The client's CIMD URL

        Returns:
            JWKS dictionary or None
        """
        return await self.cimd_fetcher.get_jwks(client_id)

    async def _verify_jwt(
        self,
        client_id: str,
        assertion: str,
        jwks: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Verify a JWT client assertion.

        Args:
            client_id: The expected issuer and subject
            assertion: The JWT to verify
            jwks: The client's JWKS for signature verification

        Returns:
            Verified JWT payload

        Raises:
            JWTAuthError: If verification fails
        """
        # First, decode without verification to get the header
        try:
            unverified_header = jwt.get_unverified_header(assertion)
        except jwt.exceptions.DecodeError as e:
            raise JWTAuthError(f"Invalid JWT format: {e}") from e

        # Get the key ID and algorithm from the header
        kid = unverified_header.get("kid")
        alg = unverified_header.get("alg", "RS256")

        # SECURITY: Validate algorithm against whitelist to prevent algorithm confusion
        if alg in BLOCKED_JWT_ALGORITHMS:
            raise JWTAuthError(f"Algorithm '{alg}' is explicitly blocked for security reasons")

        if alg not in ALLOWED_JWT_ALGORITHMS:
            raise JWTAuthError(
                f"Algorithm '{alg}' is not allowed. "
                f"Allowed algorithms: {sorted(ALLOWED_JWT_ALGORITHMS)}"
            )

        # Find the matching key in JWKS
        signing_key = self._find_signing_key(jwks, kid, alg)
        if not signing_key:
            raise JWTAuthError(f"No matching key found in JWKS for kid={kid}, alg={alg}")

        # Verify the JWT
        now = time.time()

        try:
            payload = jwt.decode(
                assertion,
                signing_key,
                algorithms=[alg],  # Only allow the specific algorithm from the whitelist
                audience=self.token_endpoint,
                issuer=client_id,
                options={
                    "require": ["iss", "sub", "aud", "exp", "iat"],
                    "verify_iss": True,
                    "verify_sub": True,
                    "verify_aud": True,
                    "verify_exp": True,
                    "verify_iat": True,
                },
                leeway=JWT_MAX_CLOCK_SKEW_SECONDS,
            )
        except jwt.ExpiredSignatureError as e:
            raise JWTAuthError("JWT has expired") from e
        except jwt.InvalidAudienceError as e:
            raise JWTAuthError(f"Invalid audience: expected {self.token_endpoint}") from e
        except jwt.InvalidIssuerError as e:
            raise JWTAuthError(f"Invalid issuer: expected {client_id}") from e
        except jwt.DecodeError as e:
            raise JWTAuthError(f"JWT decode error: {e}") from e
        except jwt.InvalidTokenError as e:
            raise JWTAuthError(f"Invalid JWT: {e}") from e

        # Verify subject matches client_id (required by RFC 7523)
        if payload.get("sub") != client_id:
            raise JWTAuthError(f"Subject mismatch: expected {client_id}, got {payload.get('sub')}")

        # Check that JWT is not too old
        iat = payload.get("iat", 0)
        if now - iat > JWT_MAX_LIFETIME_SECONDS + JWT_MAX_CLOCK_SKEW_SECONDS:
            raise JWTAuthError("JWT is too old (iat too far in the past)")

        # SECURITY: Check jti for replay protection
        jti = payload.get("jti")
        if jti:
            exp = payload.get("exp", now + JWT_MAX_LIFETIME_SECONDS)
            if not self._check_and_record_jti(jti, exp):
                raise JWTAuthError("JWT replay detected: this token has already been used")
        else:
            # jti is recommended but not required by RFC 7523
            # Log a warning for tokens without jti
            logger.warning(
                f"JWT from client {client_id} does not include jti claim - "
                "replay protection not available for this token"
            )

        return payload

    def _find_signing_key(
        self,
        jwks: dict[str, Any],
        kid: str | None,
        alg: str,
    ) -> Any:
        """
        Find a signing key in a JWKS.

        Args:
            jwks: The JWKS dictionary
            kid: Optional key ID to match
            alg: The algorithm to match

        Returns:
            The signing key or None
        """
        keys = jwks.get("keys", [])
        if not keys:
            return None

        for key_data in keys:
            # Check key ID if specified
            if kid and key_data.get("kid") != kid:
                continue

            # Check algorithm compatibility
            key_alg = key_data.get("alg")
            if key_alg and key_alg != alg:
                continue

            # Check key use (should be "sig" or unspecified)
            use = key_data.get("use")
            if use and use != "sig":
                continue

            # Check key type matches algorithm
            kty = key_data.get("kty")
            if alg.startswith("RS") and kty != "RSA":
                continue
            if alg.startswith("ES") and kty != "EC":
                continue

            # Try to construct the key
            try:
                return self._construct_key(key_data)
            except Exception as e:
                logger.warning(f"Failed to construct key: {e}")
                continue

        return None

    def _construct_key(self, key_data: dict[str, Any]) -> Any:
        """
        Construct a public key from JWK data.

        Args:
            key_data: The JWK dictionary

        Returns:
            A public key suitable for jwt.decode()
        """
        from jwt import PyJWK

        jwk = PyJWK.from_dict(key_data)
        return jwk.key


# Global JWT authenticator instance
_jwt_authenticator: JWTClientAuthenticator | None = None


def get_jwt_authenticator(token_endpoint: str) -> JWTClientAuthenticator:
    """Get or create the global JWT authenticator instance."""
    global _jwt_authenticator
    if _jwt_authenticator is None or _jwt_authenticator.token_endpoint != token_endpoint:
        _jwt_authenticator = JWTClientAuthenticator(token_endpoint)
    return _jwt_authenticator
