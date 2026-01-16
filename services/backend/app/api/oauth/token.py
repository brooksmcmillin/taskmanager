"""OAuth 2.0 token endpoint."""

import base64
import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Form, Request
from sqlalchemy import select

from app.config import settings
from app.core.errors import errors
from app.core.security import generate_token, get_token_expiry, verify_password
from app.dependencies import DbSession
from app.models.oauth import AccessToken, AuthorizationCode, DeviceCode, OAuthClient

router = APIRouter(prefix="/api/oauth", tags=["oauth"])


def verify_pkce(code_verifier: str, code_challenge: str, method: str) -> bool:
    """Verify PKCE code challenge."""
    if method == "plain":
        return code_verifier == code_challenge
    elif method == "S256":
        digest = hashlib.sha256(code_verifier.encode()).digest()
        computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return computed == code_challenge
    return False


@router.post("/token")
async def token_endpoint(
    db: DbSession,
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str | None = Form(None),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    code_verifier: str | None = Form(None),
    refresh_token: str | None = Form(None),
    device_code: str | None = Form(None),
    scope: str | None = Form(None),
) -> dict:
    """Token endpoint for all grant types."""
    # Validate client
    result = await db.execute(
        select(OAuthClient).where(
            OAuthClient.client_id == client_id,
            OAuthClient.is_active.is_(True),
        )
    )
    client = result.scalar_one_or_none()

    if not client:
        raise errors.oauth_invalid_client()

    # Verify client secret for confidential clients
    if (
        not client.is_public
        and client.client_secret_hash
        and (
            not client_secret
            or not verify_password(client_secret, client.client_secret_hash)
        )
    ):
        raise errors.oauth_invalid_client()

    # Handle different grant types
    if grant_type == "authorization_code":
        return await _handle_authorization_code(
            db, client, code, redirect_uri, code_verifier
        )
    elif grant_type == "refresh_token":
        return await _handle_refresh_token(db, client, refresh_token)
    elif grant_type == "client_credentials":
        return await _handle_client_credentials(db, client, scope)
    elif grant_type == "urn:ietf:params:oauth:grant-type:device_code":
        return await _handle_device_code(db, client, device_code)
    else:
        raise errors.oauth_unsupported_grant_type()


async def _handle_authorization_code(
    db,
    client: OAuthClient,
    code: str | None,
    redirect_uri: str | None,
    code_verifier: str | None,
) -> dict:
    """Handle authorization code grant."""
    if not code:
        raise errors.oauth_invalid_grant()

    result = await db.execute(
        select(AuthorizationCode).where(
            AuthorizationCode.code == code,
            AuthorizationCode.client_id == client.client_id,
            AuthorizationCode.expires_at > datetime.now(UTC),
        )
    )
    auth_code = result.scalar_one_or_none()

    if not auth_code:
        raise errors.oauth_invalid_grant()

    # Verify redirect URI
    if auth_code.redirect_uri != redirect_uri:
        raise errors.oauth_invalid_redirect()

    # Verify PKCE
    if auth_code.code_challenge:
        if not code_verifier:
            raise errors.oauth_invalid_grant()
        if not verify_pkce(
            code_verifier,
            auth_code.code_challenge,
            auth_code.code_challenge_method or "plain",
        ):
            raise errors.oauth_invalid_grant()

    # Delete authorization code (single use)
    await db.delete(auth_code)

    # Create access token
    access_token = AccessToken(
        token=generate_token(32),
        client_id=client.client_id,
        user_id=auth_code.user_id,
        scopes=auth_code.scopes,
        expires_at=get_token_expiry(settings.access_token_expiry),
        refresh_token=generate_token(32),
        refresh_token_expires_at=get_token_expiry(settings.access_token_expiry * 24),
    )
    db.add(access_token)

    return {
        "access_token": access_token.token,
        "token_type": "Bearer",
        "expires_in": settings.access_token_expiry,
        "refresh_token": access_token.refresh_token,
        "scope": " ".join(auth_code.scopes),
    }


async def _handle_refresh_token(
    db, client: OAuthClient, refresh_token: str | None
) -> dict:
    """Handle refresh token grant."""
    if not refresh_token:
        raise errors.oauth_invalid_grant()

    result = await db.execute(
        select(AccessToken).where(
            AccessToken.refresh_token == refresh_token,
            AccessToken.client_id == client.client_id,
            AccessToken.refresh_token_expires_at > datetime.now(UTC),
        )
    )
    old_token = result.scalar_one_or_none()

    if not old_token:
        raise errors.oauth_invalid_grant()

    # Create new access token
    new_token = AccessToken(
        token=generate_token(32),
        client_id=client.client_id,
        user_id=old_token.user_id,
        scopes=old_token.scopes,
        expires_at=get_token_expiry(settings.access_token_expiry),
        refresh_token=generate_token(32),
        refresh_token_expires_at=get_token_expiry(settings.access_token_expiry * 24),
    )
    db.add(new_token)

    # Delete old token
    await db.delete(old_token)

    return {
        "access_token": new_token.token,
        "token_type": "Bearer",
        "expires_in": settings.access_token_expiry,
        "refresh_token": new_token.refresh_token,
        "scope": " ".join(old_token.scopes),
    }


async def _handle_client_credentials(
    db, client: OAuthClient, scope: str | None
) -> dict:
    """Handle client credentials grant."""
    if "client_credentials" not in client.grant_types:
        raise errors.oauth_unsupported_grant_type()

    scopes = scope.split() if scope else client.scopes

    access_token = AccessToken(
        token=generate_token(32),
        client_id=client.client_id,
        user_id=None,  # No user for client credentials
        scopes=scopes,
        expires_at=get_token_expiry(settings.access_token_expiry),
    )
    db.add(access_token)

    return {
        "access_token": access_token.token,
        "token_type": "Bearer",
        "expires_in": settings.access_token_expiry,
        "scope": " ".join(scopes),
    }


async def _handle_device_code(db, client: OAuthClient, device_code: str | None) -> dict:
    """Handle device code grant."""
    if not device_code:
        raise errors.oauth_invalid_grant()

    result = await db.execute(
        select(DeviceCode).where(
            DeviceCode.device_code == device_code,
            DeviceCode.client_id == client.client_id,
        )
    )
    dc = result.scalar_one_or_none()

    if not dc:
        raise errors.oauth_invalid_grant()

    # Check expiry
    if dc.expires_at < datetime.now(UTC):
        raise errors.oauth_expired_token()

    # Check polling rate
    if dc.last_poll:
        elapsed = (datetime.now(UTC) - dc.last_poll).total_seconds()
        if elapsed < dc.interval:
            raise errors.oauth_slow_down()

    dc.last_poll = datetime.now(UTC)

    # Check status
    if dc.status == "pending":
        raise errors.oauth_authorization_pending()
    elif dc.status == "denied":
        await db.delete(dc)
        raise errors.oauth_access_denied()
    elif dc.status != "approved":
        raise errors.oauth_invalid_grant()

    # Create access token
    access_token = AccessToken(
        token=generate_token(32),
        client_id=client.client_id,
        user_id=dc.user_id,
        scopes=dc.scopes,
        expires_at=get_token_expiry(settings.access_token_expiry),
        refresh_token=generate_token(32),
        refresh_token_expires_at=get_token_expiry(settings.access_token_expiry * 24),
    )
    db.add(access_token)

    # Delete device code
    await db.delete(dc)

    return {
        "access_token": access_token.token,
        "token_type": "Bearer",
        "expires_in": settings.access_token_expiry,
        "refresh_token": access_token.refresh_token,
        "scope": " ".join(dc.scopes),
    }


@router.get("/verify")
async def verify_token(
    request: Request,
    db: DbSession,
) -> dict:
    """
    Verify OAuth access token.

    Works for both user tokens and client credentials tokens.
    Returns token information without requiring a user context.
    Useful for health checks and token validation.
    """
    # Extract Bearer token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise errors.auth_required()

    token = auth_header.replace("Bearer ", "")

    # Validate access token
    result = await db.execute(
        select(AccessToken)
        .where(AccessToken.token == token)
        .where(AccessToken.revoked.is_(False))
    )
    access_token = result.scalar_one_or_none()

    if not access_token:
        raise errors.invalid_token()

    # Check if token is expired
    now = datetime.now(UTC)
    if access_token.expires_at <= now:
        raise errors.invalid_token()

    # Calculate seconds until expiration
    expires_in = int((access_token.expires_at - now).total_seconds())

    return {
        "valid": True,
        "client_id": access_token.client_id,
        "user_id": access_token.user_id,
        "scopes": access_token.scopes,
        "expires_in": expires_in,
        "token_type": "Bearer",
    }
