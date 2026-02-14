"""Tests for WebAuthn (passkey) authentication endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.webauthn_credential import WebAuthnCredential


class TestRegistrationOptions:
    """Tests for POST /api/auth/webauthn/register/options."""

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        """Registration options require authentication."""
        response = await client.post(
            "/api/auth/webauthn/register/options",
            json={},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_challenge_and_options(
        self, authenticated_client: AsyncClient, test_user: User
    ) -> None:
        """Authenticated user gets registration options with challenge."""
        response = await authenticated_client.post(
            "/api/auth/webauthn/register/options",
            json={"device_name": "Test Key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "challenge_id" in data
        assert "options" in data
        options = data["options"]
        assert "rp" in options
        assert "user" in options
        assert "challenge" in options
        assert "pubKeyCredParams" in options
        assert options["rp"]["name"] == "TaskManager"
        assert options["user"]["name"] == test_user.email

    @pytest.mark.asyncio
    async def test_excludes_existing_credentials(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Registration options exclude already-registered credentials."""
        # Create an existing credential
        cred = WebAuthnCredential(
            user_id=test_user.id,
            credential_id=b"existing-cred-id",
            public_key=b"fake-public-key",
            sign_count=0,
            device_name="Existing Key",
        )
        db_session.add(cred)
        await db_session.commit()

        response = await authenticated_client.post(
            "/api/auth/webauthn/register/options",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["options"]["excludeCredentials"]) == 1


class TestRegistrationVerify:
    """Tests for POST /api/auth/webauthn/register/verify."""

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        """Registration verify requires authentication."""
        response = await client.post(
            "/api/auth/webauthn/register/verify",
            json={"challenge_id": "fake", "credential": {}},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_challenge_returns_422(
        self, authenticated_client: AsyncClient
    ) -> None:
        """Invalid challenge ID is rejected."""
        response = await authenticated_client.post(
            "/api/auth/webauthn/register/verify",
            json={
                "challenge_id": "nonexistent-challenge",
                "credential": {"id": "test", "response": {}},
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_successful_registration(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Successful WebAuthn registration stores credential."""
        # Get registration options first to get a valid challenge
        options_response = await authenticated_client.post(
            "/api/auth/webauthn/register/options",
            json={"device_name": "My Passkey"},
        )
        assert options_response.status_code == 200
        challenge_id = options_response.json()["challenge_id"]

        # Mock the webauthn verification
        mock_verification = MagicMock()
        mock_verification.credential_id = b"new-credential-id"
        mock_verification.credential_public_key = b"new-public-key"
        mock_verification.sign_count = 0

        with patch(
            "app.api.webauthn.verify_registration_response",
            return_value=mock_verification,
        ):
            response = await authenticated_client.post(
                "/api/auth/webauthn/register/verify",
                json={
                    "challenge_id": challenge_id,
                    "credential": {
                        "id": "dGVzdA",
                        "rawId": "dGVzdA",
                        "type": "public-key",
                        "response": {
                            "attestationObject": "o2NmbXRkbm9uZQ",
                            "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uY3JlYXRlIn0",
                            "transports": ["internal"],
                        },
                    },
                    "device_name": "My Passkey",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["device_name"] == "My Passkey"
        assert "id" in data
        assert "created_at" in data

        # Verify credential stored in DB
        result = await db_session.execute(
            select(WebAuthnCredential).where(WebAuthnCredential.user_id == test_user.id)
        )
        creds = result.scalars().all()
        assert len(creds) == 1
        assert creds[0].device_name == "My Passkey"


class TestAuthenticationOptions:
    """Tests for POST /api/auth/webauthn/authenticate/options."""

    @pytest.mark.asyncio
    async def test_returns_challenge_without_auth(self, client: AsyncClient) -> None:
        """Authentication options work without being logged in."""
        response = await client.post(
            "/api/auth/webauthn/authenticate/options",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert "challenge_id" in data
        assert "options" in data
        assert "challenge" in data["options"]

    @pytest.mark.asyncio
    async def test_returns_empty_credentials_for_unknown_user(
        self, client: AsyncClient
    ) -> None:
        """Unknown email returns empty credentials (anti-enumeration)."""
        response = await client.post(
            "/api/auth/webauthn/authenticate/options",
            json={"email": "nonexistent@example.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["options"]["allowCredentials"] == []

    @pytest.mark.asyncio
    async def test_returns_credentials_for_known_user(
        self,
        client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Known email with credentials returns them in options."""
        cred = WebAuthnCredential(
            user_id=test_user.id,
            credential_id=b"test-cred-id",
            public_key=b"test-public-key",
            sign_count=0,
            transports="internal,hybrid",
        )
        db_session.add(cred)
        await db_session.commit()

        response = await client.post(
            "/api/auth/webauthn/authenticate/options",
            json={"email": test_user.email},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["options"]["allowCredentials"]) == 1


class TestAuthenticationVerify:
    """Tests for POST /api/auth/webauthn/authenticate/verify."""

    @pytest.mark.asyncio
    async def test_invalid_challenge_returns_422(self, client: AsyncClient) -> None:
        """Invalid challenge ID is rejected."""
        response = await client.post(
            "/api/auth/webauthn/authenticate/verify",
            json={
                "challenge_id": "bad-challenge",
                "credential": {"id": "test"},
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_unknown_credential_returns_401(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Unknown credential ID returns 401."""
        # Get a valid challenge first
        options_response = await client.post(
            "/api/auth/webauthn/authenticate/options",
            json={},
        )
        challenge_id = options_response.json()["challenge_id"]

        response = await client.post(
            "/api/auth/webauthn/authenticate/verify",
            json={
                "challenge_id": challenge_id,
                "credential": {
                    "id": "dW5rbm93bg",
                    "rawId": "dW5rbm93bg",
                    "type": "public-key",
                    "response": {
                        "authenticatorData": "dGVzdA",
                        "clientDataJSON": "dGVzdA",
                        "signature": "dGVzdA",
                    },
                },
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_successful_authentication_creates_session(
        self,
        client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Successful WebAuthn auth creates session and sets cookie."""
        # Create credential in DB
        cred = WebAuthnCredential(
            user_id=test_user.id,
            credential_id=b"auth-cred-id",
            public_key=b"auth-public-key",
            sign_count=0,
        )
        db_session.add(cred)
        await db_session.commit()
        await db_session.refresh(cred)

        # Get authentication challenge
        options_response = await client.post(
            "/api/auth/webauthn/authenticate/options",
            json={"email": test_user.email},
        )
        challenge_id = options_response.json()["challenge_id"]

        # Mock the webauthn verification
        mock_verification = MagicMock()
        mock_verification.new_sign_count = 1

        from base64 import urlsafe_b64encode

        encoded_cred_id = urlsafe_b64encode(b"auth-cred-id").rstrip(b"=").decode()

        with patch(
            "app.api.webauthn.verify_authentication_response",
            return_value=mock_verification,
        ):
            response = await client.post(
                "/api/auth/webauthn/authenticate/verify",
                json={
                    "challenge_id": challenge_id,
                    "credential": {
                        "id": encoded_cred_id,
                        "rawId": encoded_cred_id,
                        "type": "public-key",
                        "response": {
                            "authenticatorData": "dGVzdA",
                            "clientDataJSON": "dGVzdA",
                            "signature": "dGVzdA",
                        },
                    },
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Login successful"
        assert data["user"]["email"] == test_user.email
        assert "session" in response.cookies

    @pytest.mark.asyncio
    async def test_inactive_user_returns_401(
        self,
        client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Inactive user is rejected during WebAuthn auth."""
        test_user.is_active = False
        await db_session.commit()

        cred = WebAuthnCredential(
            user_id=test_user.id,
            credential_id=b"inactive-cred-id",
            public_key=b"inactive-public-key",
            sign_count=0,
        )
        db_session.add(cred)
        await db_session.commit()

        # Get challenge
        options_response = await client.post(
            "/api/auth/webauthn/authenticate/options",
            json={"email": test_user.email},
        )
        challenge_id = options_response.json()["challenge_id"]

        from base64 import urlsafe_b64encode

        encoded_cred_id = urlsafe_b64encode(b"inactive-cred-id").rstrip(b"=").decode()

        response = await client.post(
            "/api/auth/webauthn/authenticate/verify",
            json={
                "challenge_id": challenge_id,
                "credential": {
                    "id": encoded_cred_id,
                    "rawId": encoded_cred_id,
                    "type": "public-key",
                    "response": {
                        "authenticatorData": "dGVzdA",
                        "clientDataJSON": "dGVzdA",
                        "signature": "dGVzdA",
                    },
                },
            },
        )
        assert response.status_code == 401


class TestListCredentials:
    """Tests for GET /api/auth/webauthn/credentials."""

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        """Listing credentials requires authentication."""
        response = await client.get("/api/auth/webauthn/credentials")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_user_credentials(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Returns all credentials for the authenticated user."""
        cred1 = WebAuthnCredential(
            user_id=test_user.id,
            credential_id=b"cred-1",
            public_key=b"key-1",
            sign_count=0,
            device_name="Phone",
        )
        cred2 = WebAuthnCredential(
            user_id=test_user.id,
            credential_id=b"cred-2",
            public_key=b"key-2",
            sign_count=5,
            device_name="Laptop",
        )
        db_session.add_all([cred1, cred2])
        await db_session.commit()

        response = await authenticated_client.get("/api/auth/webauthn/credentials")
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["count"] == 2
        assert len(data["data"]) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_credentials(
        self, authenticated_client: AsyncClient
    ) -> None:
        """Returns empty list when user has no credentials."""
        response = await authenticated_client.get("/api/auth/webauthn/credentials")
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["count"] == 0
        assert data["data"] == []


class TestDeleteCredential:
    """Tests for DELETE /api/auth/webauthn/credentials/{id}."""

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        """Deleting credentials requires authentication."""
        response = await client.delete("/api/auth/webauthn/credentials/1")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_own_credential(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """User can delete their own credential."""
        cred = WebAuthnCredential(
            user_id=test_user.id,
            credential_id=b"delete-me",
            public_key=b"key",
            sign_count=0,
            device_name="Old Key",
        )
        db_session.add(cred)
        await db_session.commit()
        await db_session.refresh(cred)

        response = await authenticated_client.delete(
            f"/api/auth/webauthn/credentials/{cred.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_credential_returns_404(
        self, authenticated_client: AsyncClient
    ) -> None:
        """Deleting nonexistent credential returns 404."""
        response = await authenticated_client.delete(
            "/api/auth/webauthn/credentials/99999"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_delete_other_users_credential(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """User cannot delete another user's credential."""
        from app.core.security import hash_password

        other_user = User(
            email="other@example.com",
            password_hash=hash_password("OtherPass123!"),
        )
        db_session.add(other_user)
        await db_session.flush()

        cred = WebAuthnCredential(
            user_id=other_user.id,
            credential_id=b"not-yours",
            public_key=b"key",
            sign_count=0,
        )
        db_session.add(cred)
        await db_session.commit()
        await db_session.refresh(cred)

        response = await authenticated_client.delete(
            f"/api/auth/webauthn/credentials/{cred.id}"
        )
        assert response.status_code == 404


class TestChallengeExpiration:
    """Tests for challenge store behavior."""

    @pytest.mark.asyncio
    async def test_challenge_consumed_after_use(
        self, authenticated_client: AsyncClient
    ) -> None:
        """Challenge can only be used once."""
        # Get options to create a challenge
        response = await authenticated_client.post(
            "/api/auth/webauthn/register/options",
            json={},
        )
        challenge_id = response.json()["challenge_id"]

        # First attempt consumes the challenge
        await authenticated_client.post(
            "/api/auth/webauthn/register/verify",
            json={
                "challenge_id": challenge_id,
                "credential": {"id": "test"},
            },
        )
        # May fail on verification but challenge is consumed

        # Second attempt should fail with invalid challenge
        response2 = await authenticated_client.post(
            "/api/auth/webauthn/register/verify",
            json={
                "challenge_id": challenge_id,
                "credential": {"id": "test"},
            },
        )
        assert response2.status_code == 400
