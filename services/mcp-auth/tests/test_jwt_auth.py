"""Tests for JWT client authentication (private_key_jwt / RFC 7523)."""

import os
import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

# Set required env vars before imports
os.environ.setdefault("TASKMANAGER_OAUTH_HOST", "http://localhost:4321")
os.environ.setdefault("MCP_SERVER", "http://localhost:9000")
os.environ.setdefault("TASKMANAGER_CLIENT_ID", "test-client")
os.environ.setdefault("TASKMANAGER_CLIENT_SECRET", "test-secret")  # pragma: allowlist secret

from mcp_auth.jwt_auth import (  # noqa: E402
    ALLOWED_JWT_ALGORITHMS,
    BLOCKED_JWT_ALGORITHMS,
    JWTAuthError,
    JWTClientAuthenticator,
)


def _generate_rsa_keypair():
    """Generate an RSA key pair for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()
    return private_key, public_key


def _create_authenticator(token_endpoint: str = "https://auth.example.com/token"):
    """Create a JWTClientAuthenticator with a mock CIMD fetcher."""
    mock_fetcher = MagicMock()
    mock_fetcher.get_jwks = AsyncMock(return_value=None)
    return JWTClientAuthenticator(
        token_endpoint=token_endpoint,
        cimd_fetcher=mock_fetcher,
    )


def _make_jwks_from_public_key(public_key, kid: str = "test-key-1"):
    """Convert a public key to JWKS format."""
    from jwt.algorithms import RSAAlgorithm

    jwk = RSAAlgorithm.to_jwk(public_key, as_dict=True)
    jwk["kid"] = kid
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"

    return {"keys": [jwk]}


def _sign_jwt(
    private_key,
    client_id: str = "https://client.example.com",
    audience: str = "https://auth.example.com/token",
    kid: str = "test-key-1",
    algorithm: str = "RS256",
    extra_claims: dict | None = None,
    iat_offset: int = 0,
    exp_offset: int = 300,
) -> str:
    """Create a signed JWT assertion for testing."""
    now = int(time.time())
    payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": audience,
        "iat": now + iat_offset,
        "exp": now + exp_offset,
        "jti": f"test-jti-{now}",
    }
    if extra_claims:
        payload.update(extra_claims)

    headers = {"kid": kid, "alg": algorithm}
    return jwt.encode(payload, private_key, algorithm=algorithm, headers=headers)


class TestAlgorithmWhitelist:
    """Test algorithm validation."""

    def test_allowed_algorithms_are_asymmetric(self) -> None:
        """Only asymmetric algorithms should be in the allowed set."""
        for alg in ALLOWED_JWT_ALGORITHMS:
            assert alg.startswith(("RS", "ES", "PS"))

    def test_blocked_algorithms_include_symmetric(self) -> None:
        """Symmetric and 'none' algorithms must be blocked."""
        assert "none" in BLOCKED_JWT_ALGORITHMS
        assert "HS256" in BLOCKED_JWT_ALGORITHMS
        assert "HS384" in BLOCKED_JWT_ALGORITHMS
        assert "HS512" in BLOCKED_JWT_ALGORITHMS

    def test_no_overlap_between_allowed_and_blocked(self) -> None:
        """No algorithm should be in both allowed and blocked sets."""
        assert ALLOWED_JWT_ALGORITHMS.isdisjoint(BLOCKED_JWT_ALGORITHMS)


class TestJTIReplayProtection:
    """Test JWT replay protection via jti tracking."""

    def test_new_jti_is_accepted(self) -> None:
        """A new JTI should be recorded and accepted."""
        auth = _create_authenticator()
        assert auth._check_and_record_jti("jti-1", time.time() + 300) is True

    def test_duplicate_jti_is_rejected(self) -> None:
        """A previously seen JTI should be rejected."""
        auth = _create_authenticator()
        exp = time.time() + 300
        auth._check_and_record_jti("jti-dup", exp)
        assert auth._check_and_record_jti("jti-dup", exp) is False

    def test_expired_jtis_are_cleaned_up(self) -> None:
        """Expired JTIs should be removed during cleanup."""
        auth = _create_authenticator()
        # Record a JTI that has already expired
        auth._used_jtis["old-jti"] = time.time() - 100
        # Force cleanup by setting last cleanup far in the past
        auth._last_cleanup = 0

        auth._cleanup_expired_jtis()
        assert "old-jti" not in auth._used_jtis


class TestAuthenticate:
    """Test the authenticate() method."""

    @pytest.mark.asyncio
    async def test_invalid_assertion_type_raises(self) -> None:
        """Wrong client_assertion_type is rejected."""
        auth = _create_authenticator()
        with pytest.raises(JWTAuthError, match="Invalid client_assertion_type"):
            await auth.authenticate(
                client_id="test",
                client_assertion="some-jwt",
                client_assertion_type="wrong-type",
            )

    @pytest.mark.asyncio
    async def test_missing_assertion_raises(self) -> None:
        """Empty client_assertion is rejected."""
        auth = _create_authenticator()
        with pytest.raises(JWTAuthError, match="Missing client_assertion"):
            await auth.authenticate(
                client_id="test",
                client_assertion="",
                client_assertion_type="urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            )

    @pytest.mark.asyncio
    async def test_missing_jwks_raises(self) -> None:
        """Client with no retrievable JWKS is rejected."""
        auth = _create_authenticator()
        auth.cimd_fetcher.get_jwks = AsyncMock(return_value=None)

        with pytest.raises(JWTAuthError, match="Could not retrieve JWKS"):
            await auth.authenticate(
                client_id="https://client.example.com",
                client_assertion="some.jwt.here",
                client_assertion_type="urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            )

    @pytest.mark.asyncio
    async def test_successful_authentication(self) -> None:
        """Valid JWT with matching JWKS authenticates successfully."""
        private_key, public_key = _generate_rsa_keypair()
        auth = _create_authenticator()

        client_id = "https://client.example.com"
        jwks = _make_jwks_from_public_key(public_key)
        auth.cimd_fetcher.get_jwks = AsyncMock(return_value=jwks)

        assertion = _sign_jwt(private_key, client_id=client_id)

        result = await auth.authenticate(
            client_id=client_id,
            client_assertion=assertion,
            client_assertion_type="urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        )
        assert result is True


class TestVerifyJWT:
    """Test the _verify_jwt() method."""

    @pytest.mark.asyncio
    async def test_blocked_algorithm_rejected(self) -> None:
        """JWT using a blocked algorithm (HS256) is rejected."""
        auth = _create_authenticator()
        # Create a JWT with HS256 (symmetric - blocked)
        payload = {
            "iss": "client",
            "sub": "client",
            "aud": auth.token_endpoint,
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
        }
        token = jwt.encode(payload, "secret", algorithm="HS256")

        with pytest.raises(JWTAuthError, match="explicitly blocked"):
            await auth._verify_jwt("client", token, {"keys": []})

    @pytest.mark.asyncio
    async def test_unknown_algorithm_rejected(self) -> None:
        """JWT using an unknown algorithm is rejected."""
        auth = _create_authenticator()
        # Manually craft a header with an unknown algorithm
        import base64
        import json

        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "XX999", "typ": "JWT"}).encode()
        ).rstrip(b"=")
        payload_part = base64.urlsafe_b64encode(json.dumps({"iss": "x"}).encode()).rstrip(b"=")
        fake_token = f"{header.decode()}.{payload_part.decode()}.fake-sig"

        with pytest.raises(JWTAuthError, match="not allowed"):
            await auth._verify_jwt("client", fake_token, {"keys": []})

    @pytest.mark.asyncio
    async def test_expired_jwt_rejected(self) -> None:
        """Expired JWT is rejected."""
        private_key, public_key = _generate_rsa_keypair()
        auth = _create_authenticator()
        jwks = _make_jwks_from_public_key(public_key)

        # JWT that expired 10 minutes ago
        assertion = _sign_jwt(
            private_key,
            audience=auth.token_endpoint,
            exp_offset=-600,
            iat_offset=-900,
        )

        with pytest.raises(JWTAuthError, match="expired"):
            await auth._verify_jwt(
                "https://client.example.com",
                assertion,
                jwks,
            )

    @pytest.mark.asyncio
    async def test_wrong_audience_rejected(self) -> None:
        """JWT with wrong audience is rejected."""
        private_key, public_key = _generate_rsa_keypair()
        auth = _create_authenticator()
        jwks = _make_jwks_from_public_key(public_key)

        assertion = _sign_jwt(
            private_key,
            audience="https://wrong-audience.example.com/token",
        )

        with pytest.raises(JWTAuthError, match="audience"):
            await auth._verify_jwt(
                "https://client.example.com",
                assertion,
                jwks,
            )

    @pytest.mark.asyncio
    async def test_wrong_issuer_rejected(self) -> None:
        """JWT with wrong issuer is rejected."""
        private_key, public_key = _generate_rsa_keypair()
        auth = _create_authenticator()
        jwks = _make_jwks_from_public_key(public_key)

        assertion = _sign_jwt(
            private_key,
            client_id="https://wrong-issuer.example.com",
            audience=auth.token_endpoint,
        )

        with pytest.raises(JWTAuthError, match="issuer"):
            await auth._verify_jwt(
                "https://correct-client.example.com",
                assertion,
                jwks,
            )

    @pytest.mark.asyncio
    async def test_subject_mismatch_rejected(self) -> None:
        """JWT where sub != client_id is rejected."""
        private_key, public_key = _generate_rsa_keypair()
        auth = _create_authenticator()
        jwks = _make_jwks_from_public_key(public_key)

        client_id = "https://client.example.com"
        assertion = _sign_jwt(
            private_key,
            client_id=client_id,
            audience=auth.token_endpoint,
            extra_claims={"sub": "https://different.example.com"},
        )

        with pytest.raises(JWTAuthError, match="Subject mismatch"):
            await auth._verify_jwt(client_id, assertion, jwks)

    @pytest.mark.asyncio
    async def test_too_old_jwt_rejected(self) -> None:
        """JWT with iat too far in the past is rejected."""
        private_key, public_key = _generate_rsa_keypair()
        auth = _create_authenticator()
        jwks = _make_jwks_from_public_key(public_key)

        client_id = "https://client.example.com"
        # iat is 10 minutes ago, which exceeds JWT_MAX_LIFETIME_SECONDS (5 min)
        assertion = _sign_jwt(
            private_key,
            client_id=client_id,
            audience=auth.token_endpoint,
            iat_offset=-700,
            exp_offset=300,
        )

        with pytest.raises(JWTAuthError, match="too old"):
            await auth._verify_jwt(client_id, assertion, jwks)

    @pytest.mark.asyncio
    async def test_jti_replay_rejected(self) -> None:
        """Replayed JWT (same jti) is rejected."""
        private_key, public_key = _generate_rsa_keypair()
        auth = _create_authenticator()
        jwks = _make_jwks_from_public_key(public_key)

        client_id = "https://client.example.com"
        now = int(time.time())
        payload = {
            "iss": client_id,
            "sub": client_id,
            "aud": auth.token_endpoint,
            "iat": now,
            "exp": now + 300,
            "jti": "replay-test-jti",
        }
        assertion = jwt.encode(
            payload, private_key, algorithm="RS256", headers={"kid": "test-key-1"}
        )

        # First verification should succeed
        result = await auth._verify_jwt(client_id, assertion, jwks)
        assert result is not None

        # Second verification with same jti should fail
        with pytest.raises(JWTAuthError, match="replay"):
            await auth._verify_jwt(client_id, assertion, jwks)

    @pytest.mark.asyncio
    async def test_valid_jwt_returns_payload(self) -> None:
        """Valid JWT returns the decoded payload."""
        private_key, public_key = _generate_rsa_keypair()
        auth = _create_authenticator()
        jwks = _make_jwks_from_public_key(public_key)

        client_id = "https://client.example.com"
        assertion = _sign_jwt(
            private_key,
            client_id=client_id,
            audience=auth.token_endpoint,
        )

        result = await auth._verify_jwt(client_id, assertion, jwks)
        assert result["iss"] == client_id
        assert result["sub"] == client_id
        assert result["aud"] == auth.token_endpoint


class TestFindSigningKey:
    """Test the _find_signing_key() method."""

    def test_matching_key_found(self) -> None:
        """Finds a key matching kid and algorithm."""
        _, public_key = _generate_rsa_keypair()
        auth = _create_authenticator()
        jwks = _make_jwks_from_public_key(public_key, kid="my-key")

        key = auth._find_signing_key(jwks, kid="my-key", alg="RS256")
        assert key is not None

    def test_wrong_kid_returns_none(self) -> None:
        """Returns None when kid doesn't match."""
        _, public_key = _generate_rsa_keypair()
        auth = _create_authenticator()
        jwks = _make_jwks_from_public_key(public_key, kid="key-1")

        key = auth._find_signing_key(jwks, kid="key-2", alg="RS256")
        assert key is None

    def test_wrong_algorithm_returns_none(self) -> None:
        """Returns None when algorithm doesn't match."""
        _, public_key = _generate_rsa_keypair()
        auth = _create_authenticator()
        jwks = _make_jwks_from_public_key(public_key, kid="key-1")

        key = auth._find_signing_key(jwks, kid="key-1", alg="ES256")
        assert key is None

    def test_empty_jwks_returns_none(self) -> None:
        """Returns None when JWKS has no keys."""
        auth = _create_authenticator()
        key = auth._find_signing_key({"keys": []}, kid="any", alg="RS256")
        assert key is None

    def test_key_with_wrong_use_skipped(self) -> None:
        """Keys with use != 'sig' are skipped."""
        _, public_key = _generate_rsa_keypair()
        auth = _create_authenticator()
        jwks = _make_jwks_from_public_key(public_key, kid="enc-key")
        jwks["keys"][0]["use"] = "enc"  # Encryption key, not signing

        key = auth._find_signing_key(jwks, kid="enc-key", alg="RS256")
        assert key is None


class TestGetJWTAuthenticator:
    """Test the global authenticator factory."""

    def test_creates_authenticator(self) -> None:
        """get_jwt_authenticator creates an instance."""
        from mcp_auth.jwt_auth import get_jwt_authenticator

        auth = get_jwt_authenticator("https://example.com/token")
        assert isinstance(auth, JWTClientAuthenticator)
        assert auth.token_endpoint == "https://example.com/token"
