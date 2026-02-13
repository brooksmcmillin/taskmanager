"""WebAuthn API routes for passkey authentication."""

import logging
import secrets
from base64 import urlsafe_b64decode
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.config import settings
from app.core.errors import ApiError, errors
from app.core.rate_limit import RateLimiter
from app.core.security import generate_session_id, get_session_expiry
from app.dependencies import CurrentUser, DbSession
from app.models.session import Session
from app.models.user import User
from app.models.webauthn_credential import WebAuthnCredential

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/webauthn", tags=["webauthn"])

# Rate limiters for WebAuthn endpoints
# Authentication attempts: 10 per 5 minutes per IP
webauthn_auth_rate_limiter = RateLimiter(max_attempts=10, window_ms=300000)
# Registration attempts: 5 per 5 minutes per user (requires auth)
webauthn_register_rate_limiter = RateLimiter(max_attempts=5, window_ms=300000)

# In-memory challenge store (in production, use Redis or similar)
# Format: {challenge_id: {"challenge": bytes, "user_id": int|None, "expires_at": dt}}
_challenge_store: dict[str, dict] = {}


def _cleanup_expired_challenges() -> None:
    """Remove expired challenges from the store."""
    now = datetime.now(UTC)
    expired = [k for k, v in _challenge_store.items() if v["expires_at"] < now]
    for k in expired:
        del _challenge_store[k]


def _store_challenge(challenge: bytes, user_id: int | None = None) -> str:
    """Store a challenge and return its ID."""
    _cleanup_expired_challenges()
    challenge_id = secrets.token_urlsafe(32)
    _challenge_store[challenge_id] = {
        "challenge": challenge,
        "user_id": user_id,
        "expires_at": datetime.now(UTC)
        + timedelta(seconds=settings.webauthn_challenge_timeout),
    }
    return challenge_id


def _get_challenge(challenge_id: str) -> dict | None:
    """Retrieve and remove a challenge by ID."""
    _cleanup_expired_challenges()
    return _challenge_store.pop(challenge_id, None)


# Request/Response schemas
class RegisterOptionsRequest(BaseModel):
    """Request for registration options."""

    device_name: str | None = Field(None, max_length=100)


class RegisterOptionsResponse(BaseModel):
    """Registration options response."""

    challenge_id: str
    options: dict


class RegisterVerifyRequest(BaseModel):
    """Request to verify registration."""

    challenge_id: str
    credential: dict
    device_name: str | None = Field(None, max_length=100)


class CredentialResponse(BaseModel):
    """WebAuthn credential response."""

    id: int
    device_name: str | None
    created_at: str
    last_used_at: str | None


class AuthenticateOptionsRequest(BaseModel):
    """Request for authentication options."""

    email: str | None = None


class AuthenticateOptionsResponse(BaseModel):
    """Authentication options response."""

    challenge_id: str
    options: dict


class AuthenticateVerifyRequest(BaseModel):
    """Request to verify authentication."""

    challenge_id: str
    credential: dict


class AuthenticateVerifyResponse(BaseModel):
    """Authentication verification response."""

    message: str
    user: dict


@router.post("/register/options", response_model=RegisterOptionsResponse)
async def get_registration_options(
    request: RegisterOptionsRequest,
    user: CurrentUser,
    db: DbSession,
) -> RegisterOptionsResponse:
    """Generate WebAuthn registration options for authenticated user."""
    # Rate limit by user ID
    rate_limit_key = f"webauthn_register_{user.id}"
    webauthn_register_rate_limiter.check(rate_limit_key)

    logger.info("WebAuthn registration options requested for user %s", user.email)

    # Get existing credentials to exclude
    result = await db.execute(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
    )
    existing_credentials = result.scalars().all()

    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=cred.credential_id)
        for cred in existing_credentials
    ]

    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=str(user.id).encode(),
        user_name=user.email,
        user_display_name=user.email,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )

    challenge_id = _store_challenge(options.challenge, user_id=user.id)

    # Convert options to JSON-serializable dict
    options_dict = {
        "rp": {"id": options.rp.id, "name": options.rp.name},
        "user": {
            "id": bytes_to_base64url(options.user.id),
            "name": options.user.name,
            "displayName": options.user.display_name,
        },
        "challenge": bytes_to_base64url(options.challenge),
        "pubKeyCredParams": [
            {"type": p.type, "alg": p.alg} for p in options.pub_key_cred_params
        ],
        "timeout": options.timeout,
        "excludeCredentials": [
            {"type": c.type, "id": bytes_to_base64url(c.id)}
            for c in (options.exclude_credentials or [])
        ],
        "authenticatorSelection": {
            "residentKey": options.authenticator_selection.resident_key
            if options.authenticator_selection
            else None,
            "userVerification": options.authenticator_selection.user_verification
            if options.authenticator_selection
            else None,
        },
        "attestation": options.attestation,
    }

    return RegisterOptionsResponse(challenge_id=challenge_id, options=options_dict)


@router.post("/register/verify")
async def verify_registration(
    request: RegisterVerifyRequest,
    user: CurrentUser,
    db: DbSession,
) -> CredentialResponse:
    """Verify WebAuthn registration and store credential."""
    # Retrieve challenge
    challenge_data = _get_challenge(request.challenge_id)
    if not challenge_data:
        logger.warning(
            "WebAuthn registration failed: invalid challenge for user %s", user.email
        )
        raise errors.validation("Invalid or expired challenge")

    if challenge_data["user_id"] != user.id:
        logger.warning(
            "WebAuthn registration failed: challenge mismatch for user %s",
            user.email,
        )
        raise errors.validation("Challenge does not match user")

    try:
        # Parse credential from request
        credential = request.credential

        # Verify the registration response
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=challenge_data["challenge"],
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
        )
    except Exception as e:
        logger.warning(
            "WebAuthn registration verification failed for user %s: %s",
            user.email,
            e,
        )
        raise errors.validation(f"Registration verification failed: {e}") from e

    # Check if credential ID already exists
    result = await db.execute(
        select(WebAuthnCredential).where(
            WebAuthnCredential.credential_id == verification.credential_id
        )
    )
    if result.scalar_one_or_none():
        raise errors.validation("Credential already registered")

    # Extract transports if available
    transports = None
    if credential.get("response", {}).get("transports"):
        transports = ",".join(credential["response"]["transports"])

    # Store the credential
    webauthn_cred = WebAuthnCredential(
        user_id=user.id,
        credential_id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        transports=transports,
        device_name=request.device_name,
    )
    db.add(webauthn_cred)
    await db.flush()

    logger.info(
        "WebAuthn credential registered successfully for user %s (credential_id=%s)",
        user.email,
        webauthn_cred.id,
    )

    return CredentialResponse(
        id=webauthn_cred.id,
        device_name=webauthn_cred.device_name,
        created_at=webauthn_cred.created_at.isoformat(),
        last_used_at=None,
    )


@router.post("/authenticate/options", response_model=AuthenticateOptionsResponse)
async def get_authentication_options(
    request: AuthenticateOptionsRequest,
    http_request: Request,
    db: DbSession,
) -> AuthenticateOptionsResponse:
    """Generate WebAuthn authentication options.

    Note: To prevent user enumeration, this endpoint always returns a valid
    challenge even if the username doesn't exist or has no passkeys. The
    authentication will fail during verification instead.
    """
    # Rate limit by IP address
    client_ip = http_request.client.host if http_request.client else "unknown"
    webauthn_auth_rate_limiter.check(f"webauthn_auth_options_{client_ip}")

    allow_credentials = None
    user_id_for_challenge = None

    if request.email:
        # Find user and their credentials
        # Note: We always generate options regardless of whether user exists
        # to prevent user enumeration attacks
        result = await db.execute(select(User).where(User.email == request.email))
        user = result.scalar_one_or_none()

        if user:
            user_id_for_challenge = user.id
            result = await db.execute(
                select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
            )
            credentials = result.scalars().all()

            if credentials:
                allow_credentials = []
                for cred in credentials:
                    transports = cred.transports.split(",") if cred.transports else None
                    allow_credentials.append(
                        PublicKeyCredentialDescriptor(
                            id=cred.credential_id,
                            transports=transports,  # type: ignore[arg-type]
                        )
                    )

    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    challenge_id = _store_challenge(options.challenge, user_id=user_id_for_challenge)

    # Convert options to JSON-serializable dict
    # Note: Always return empty allowCredentials array when no credentials found
    # to prevent user enumeration (attacker can't tell if user exists)
    options_dict = {
        "challenge": bytes_to_base64url(options.challenge),
        "timeout": options.timeout,
        "rpId": options.rp_id,
        "allowCredentials": [
            {
                "type": c.type,
                "id": bytes_to_base64url(c.id),
                "transports": c.transports,
            }
            for c in (options.allow_credentials or [])
        ]
        if options.allow_credentials
        else [],
        "userVerification": options.user_verification,
    }

    return AuthenticateOptionsResponse(challenge_id=challenge_id, options=options_dict)


@router.post("/authenticate/verify")
async def verify_authentication(
    request: AuthenticateVerifyRequest,
    http_request: Request,
    response: Response,
    db: DbSession,
) -> AuthenticateVerifyResponse:
    """Verify WebAuthn authentication and create session."""
    # Rate limit by IP address
    client_ip = http_request.client.host if http_request.client else "unknown"
    rate_limit_key = f"webauthn_auth_verify_{client_ip}"
    webauthn_auth_rate_limiter.check(rate_limit_key)

    # Retrieve challenge
    challenge_data = _get_challenge(request.challenge_id)
    if not challenge_data:
        logger.warning(
            "WebAuthn authentication failed: invalid challenge from %s", client_ip
        )
        webauthn_auth_rate_limiter.record(rate_limit_key)
        raise errors.validation("Invalid or expired challenge")

    try:
        # Parse the credential
        credential = request.credential

        # Get credential ID from the response
        raw_id = credential.get("rawId") or credential.get("id")
        if not raw_id:
            raise errors.validation("Missing credential ID")

        # Decode credential ID (handle both URL-safe and standard base64)
        try:
            # Add padding if needed
            padded = raw_id + "=" * (4 - len(raw_id) % 4)
            credential_id = urlsafe_b64decode(padded)
        except Exception as decode_err:
            raise errors.validation("Invalid credential ID encoding") from decode_err

        # Find the credential in database
        result = await db.execute(
            select(WebAuthnCredential).where(
                WebAuthnCredential.credential_id == credential_id
            )
        )
        webauthn_cred = result.scalar_one_or_none()

        if not webauthn_cred:
            logger.warning(
                "WebAuthn authentication failed: unknown credential from %s", client_ip
            )
            webauthn_auth_rate_limiter.record(rate_limit_key)
            raise errors.invalid_credentials()

        # Get the user
        result = await db.execute(select(User).where(User.id == webauthn_cred.user_id))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            logger.warning(
                "WebAuthn authentication failed: inactive user for credential %s",
                webauthn_cred.id,
            )
            webauthn_auth_rate_limiter.record(rate_limit_key)
            raise errors.invalid_credentials()

        # Verify the authentication response
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge_data["challenge"],
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            credential_public_key=webauthn_cred.public_key,
            credential_current_sign_count=webauthn_cred.sign_count,
        )

        # Check for sign count rollback (potential cloned authenticator)
        if (
            webauthn_cred.sign_count > 0
            and verification.new_sign_count <= webauthn_cred.sign_count
        ):
            logger.warning(
                "WebAuthn sign count rollback detected for user %s (credential %s): "
                "stored=%d, received=%d. Possible cloned authenticator.",
                user.email,
                webauthn_cred.id,
                webauthn_cred.sign_count,
                verification.new_sign_count,
            )

        # Update sign count and last used
        webauthn_cred.sign_count = verification.new_sign_count
        webauthn_cred.last_used_at = datetime.now(UTC)

    except ApiError:
        raise
    except Exception as e:
        logger.warning(
            "WebAuthn authentication verification failed from %s: %s", client_ip, e
        )
        webauthn_auth_rate_limiter.record(rate_limit_key)
        raise errors.validation(f"Authentication verification failed: {e}") from e

    # Reset rate limit on success
    webauthn_auth_rate_limiter.reset(rate_limit_key)

    # Create session
    session = Session(
        id=generate_session_id(),
        user_id=user.id,
        expires_at=get_session_expiry(),
    )
    db.add(session)

    # Set cookie
    response.set_cookie(
        key="session",
        value=session.id,
        httponly=True,
        samesite="lax",
        max_age=settings.session_duration_days * 24 * 60 * 60,
        secure=settings.is_production,
    )

    logger.info(
        "WebAuthn authentication successful for user %s (credential_id=%s)",
        user.email,
        webauthn_cred.id,
    )

    return AuthenticateVerifyResponse(
        message="Login successful",
        user={
            "id": user.id,
            "email": user.email,
            "is_admin": user.is_admin,
        },
    )


@router.get("/credentials")
async def list_credentials(
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """List all WebAuthn credentials for the current user."""
    result = await db.execute(
        select(WebAuthnCredential)
        .where(WebAuthnCredential.user_id == user.id)
        .order_by(WebAuthnCredential.created_at.desc())
    )
    credentials = result.scalars().all()

    return {
        "data": [
            {
                "id": cred.id,
                "device_name": cred.device_name,
                "created_at": cred.created_at.isoformat(),
                "last_used_at": cred.last_used_at.isoformat()
                if cred.last_used_at
                else None,
            }
            for cred in credentials
        ],
        "meta": {"count": len(credentials)},
    }


@router.delete("/credentials/{credential_id}")
async def delete_credential(
    credential_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Delete a WebAuthn credential."""
    result = await db.execute(
        select(WebAuthnCredential).where(
            WebAuthnCredential.id == credential_id,
            WebAuthnCredential.user_id == user.id,
        )
    )
    credential = result.scalar_one_or_none()

    if not credential:
        logger.warning(
            "WebAuthn credential deletion failed: credential %s not found for user %s",
            credential_id,
            user.email,
        )
        raise errors.not_found("Credential")

    await db.execute(
        delete(WebAuthnCredential).where(WebAuthnCredential.id == credential_id)
    )

    logger.info(
        "WebAuthn credential deleted for user %s (credential_id=%s)",
        user.email,
        credential_id,
    )

    return {"deleted": True, "id": credential_id}
