"""OAuth 2.0 token endpoint."""

import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Form, Request
from sqlalchemy import select

from app.config import settings
from app.core.errors import errors
from app.core.security import generate_token, get_token_expiry, verify_password
from app.dependencies import DbSession
from app.models.oauth import AccessToken, AuthorizationCode, DeviceCode, OAuthClient
from app.models.user import User

router = APIRouter(prefix="/api/oauth", tags=["oauth"])


def verify_pkce(code_verifier: str, code_challenge: str, method: str) -> bool:
    """Verify PKCE code challenge with constant-time comparison."""
    if method == "plain":
        return secrets.compare_digest(
            code_verifier.encode("utf-8"), code_challenge.encode("utf-8")
        )
    elif method == "S256":
        digest = hashlib.sha256(code_verifier.encode()).digest()
        computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return secrets.compare_digest(
            computed.encode("utf-8"), code_challenge.encode("utf-8")
        )
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
            AuthorizationCode.code == code,  # SQL filter (OK for performance)
            AuthorizationCode.client_id == client.client_id,
            AuthorizationCode.expires_at > datetime.now(UTC),
        )
    )
    auth_code = result.scalar_one_or_none()

    # Add constant-time verification to prevent timing attacks
    if not auth_code or not secrets.compare_digest(
        auth_code.code.encode("utf-8"), code.encode("utf-8")
    ):
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
        refresh_token_expires_at=get_token_expiry(settings.refresh_token_expiry),
    )
    db.add(access_token)
    # Commit now so the token is visible to immediate follow-up requests
    # (e.g. MCP auth server verifying the token right after exchange)
    await db.commit()

    # Deserialize scopes from JSON for response
    scopes_list = json.loads(auth_code.scopes)
    return {
        "access_token": access_token.token,
        "token_type": "Bearer",
        "expires_in": settings.access_token_expiry,
        "refresh_token": access_token.refresh_token,
        "scope": " ".join(scopes_list),
    }


async def _handle_refresh_token(
    db, client: OAuthClient, refresh_token: str | None
) -> dict:
    """Handle refresh token grant."""
    if not refresh_token:
        raise errors.oauth_invalid_grant()

    result = await db.execute(
        select(AccessToken).where(
            AccessToken.refresh_token
            == refresh_token,  # SQL filter (OK for performance)
            AccessToken.client_id == client.client_id,
            AccessToken.refresh_token_expires_at > datetime.now(UTC),
            AccessToken.revoked.is_(False),
        )
    )
    old_token = result.scalar_one_or_none()

    # Add constant-time verification to prevent timing attacks
    if not old_token or not secrets.compare_digest(
        old_token.refresh_token.encode("utf-8"), refresh_token.encode("utf-8")
    ):
        raise errors.oauth_invalid_grant()

    # Create new access token
    new_token = AccessToken(
        token=generate_token(32),
        client_id=client.client_id,
        user_id=old_token.user_id,
        scopes=old_token.scopes,
        expires_at=get_token_expiry(settings.access_token_expiry),
        refresh_token=generate_token(32),
        refresh_token_expires_at=get_token_expiry(settings.refresh_token_expiry),
    )
    db.add(new_token)

    # Delete old token
    await db.delete(old_token)
    await db.commit()

    # Deserialize scopes from JSON for response
    scopes_list = json.loads(old_token.scopes)
    return {
        "access_token": new_token.token,
        "token_type": "Bearer",
        "expires_in": settings.access_token_expiry,
        "refresh_token": new_token.refresh_token,
        "scope": " ".join(scopes_list),
    }


async def _handle_client_credentials(
    db, client: OAuthClient, scope: str | None
) -> dict:
    """Handle client credentials grant.

    If the OAuthClient is linked to a service account (user_id is set),
    the issued token carries that user_id so all downstream queries
    attribute actions to the service account.
    """
    if "client_credentials" not in client.grant_types:
        raise errors.oauth_unsupported_grant_type()

    # Resolve the token's user_id from the linked service account (if any)
    token_user_id: int | None = None
    if client.user_id is not None:
        result = await db.execute(select(User).where(User.id == client.user_id))
        linked_user = result.scalar_one_or_none()

        # Reject if the linked user doesn't exist, is inactive,
        # or is not a service account
        if not linked_user or not linked_user.is_active:
            raise errors.oauth_invalid_client()
        if not linked_user.is_service_account:
            raise errors.oauth_invalid_client()

        token_user_id = linked_user.id

    # Convert scope string to JSON for storage, or use client's default scopes.
    # Requested scopes must be a subset of what the client is allowed.
    if scope:
        requested_scopes = set(scope.split())
        allowed_scopes = set(json.loads(client.scopes))
        if not requested_scopes.issubset(allowed_scopes):
            raise errors.oauth_invalid_scope()
        scopes_list = scope.split()
        scopes_json = json.dumps(scopes_list)
    else:
        scopes_json = client.scopes
        scopes_list = json.loads(client.scopes)

    access_token = AccessToken(
        token=generate_token(32),
        client_id=client.client_id,
        user_id=token_user_id,
        scopes=scopes_json,
        expires_at=get_token_expiry(settings.access_token_expiry),
    )
    db.add(access_token)
    await db.commit()

    return {
        "access_token": access_token.token,
        "token_type": "Bearer",
        "expires_in": settings.access_token_expiry,
        "scope": " ".join(scopes_list),
    }


async def _handle_device_code(db, client: OAuthClient, device_code: str | None) -> dict:
    """Handle device code grant (RFC 8628)."""
    if not device_code:
        raise errors.oauth_invalid_grant()

    # First, check if the device code exists at all
    result = await db.execute(
        select(DeviceCode).where(
            DeviceCode.device_code == device_code
        )  # SQL filter (OK for performance)
    )
    dc = result.scalar_one_or_none()

    # Add constant-time verification to prevent timing attacks
    if not dc or not secrets.compare_digest(
        dc.device_code.encode("utf-8"), device_code.encode("utf-8")
    ):
        # Device code not found - either invalid or expired and cleaned up
        raise errors.oauth_invalid_grant()

    # Verify the device code belongs to this client
    if dc.client_id != client.client_id:
        # Wrong client - this shouldn't happen in normal flow
        raise errors.oauth_invalid_grant()

    # Check expiry - ensure timezone-aware comparison
    now = datetime.now(UTC)
    expires_at = (
        dc.expires_at.replace(tzinfo=UTC)
        if dc.expires_at.tzinfo is None
        else dc.expires_at
    )
    if expires_at < now:
        raise errors.oauth_expired_token()

    # Check polling rate
    if dc.last_poll_at:
        last_poll = (
            dc.last_poll_at.replace(tzinfo=UTC)
            if dc.last_poll_at.tzinfo is None
            else dc.last_poll_at
        )
        elapsed = (now - last_poll).total_seconds()
        if elapsed < dc.interval:
            raise errors.oauth_slow_down()

    # Update last poll time
    # Note: This will only be saved if the request succeeds (status="approved")
    # Rate limiting for pending/denied states is handled by the MCP auth server
    dc.last_poll_at = datetime.now(UTC)

    # Check status and handle accordingly
    if dc.status == "pending":
        # RFC 8628: Return authorization_pending when user hasn't authorized yet
        raise errors.oauth_authorization_pending()
    elif dc.status == "denied":
        # RFC 8628: Return access_denied when user denied the request
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
        refresh_token_expires_at=get_token_expiry(settings.refresh_token_expiry),
    )
    db.add(access_token)

    # Delete device code
    await db.delete(dc)
    await db.commit()

    # Deserialize scopes from JSON for response
    scopes_list = json.loads(dc.scopes)
    return {
        "access_token": access_token.token,
        "token_type": "Bearer",
        "expires_in": settings.access_token_expiry,
        "refresh_token": access_token.refresh_token,
        "scope": " ".join(scopes_list),
    }


@router.post("/revoke")
async def revoke_endpoint(
    db: DbSession,
    token: str = Form(...),
    client_id: str = Form(...),
    client_secret: str | None = Form(None),
    token_type_hint: str | None = Form(None),
) -> dict:
    """Token revocation endpoint (RFC 7009).

    Revokes an access token or refresh token. Per RFC 7009, always returns
    200 OK regardless of whether the token was found, already revoked, or
    belongs to a different client — this prevents token existence disclosure.
    """
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

    # Lookup token — search order depends on token_type_hint
    access_token_record = None
    if token_type_hint == "refresh_token":
        # Hint says refresh token: search refresh_token first, fall back to token
        result = await db.execute(
            select(AccessToken).where(
                AccessToken.refresh_token == token,
                AccessToken.client_id == client.client_id,
            )
        )
        access_token_record = result.scalar_one_or_none()
        if not access_token_record:
            result = await db.execute(
                select(AccessToken).where(
                    AccessToken.token == token,
                    AccessToken.client_id == client.client_id,
                )
            )
            access_token_record = result.scalar_one_or_none()
    else:
        # No hint or access_token hint: search token first, fall back to refresh_token
        result = await db.execute(
            select(AccessToken).where(
                AccessToken.token == token,
                AccessToken.client_id == client.client_id,
            )
        )
        access_token_record = result.scalar_one_or_none()
        if not access_token_record:
            result = await db.execute(
                select(AccessToken).where(
                    AccessToken.refresh_token == token,
                    AccessToken.client_id == client.client_id,
                )
            )
            access_token_record = result.scalar_one_or_none()

    # If found, revoke it. Per RFC 7009: always return 200 OK.
    if access_token_record:
        access_token_record.revoked = True
        await db.commit()

    return {}


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
        .where(AccessToken.token == token)  # SQL filter (OK for performance)
        .where(AccessToken.revoked.is_(False))
    )
    access_token = result.scalar_one_or_none()

    # Add constant-time verification to prevent timing attacks
    if not access_token or not secrets.compare_digest(
        access_token.token.encode("utf-8"), token.encode("utf-8")
    ):
        raise errors.invalid_token()

    # Check if token is expired
    now = datetime.now(UTC)
    # Convert expires_at to UTC if it's naive (database may not store timezone)
    token_expires = (
        access_token.expires_at.replace(tzinfo=UTC)
        if access_token.expires_at.tzinfo is None
        else access_token.expires_at
    )
    if token_expires <= now:
        raise errors.invalid_token()

    # Calculate seconds until expiration
    expires_in = int((token_expires - now).total_seconds())

    return {
        "valid": True,
        "client_id": access_token.client_id,
        "user_id": access_token.user_id,
        "scopes": access_token.scopes,
        "expires_in": expires_in,
        "token_type": "Bearer",
    }
