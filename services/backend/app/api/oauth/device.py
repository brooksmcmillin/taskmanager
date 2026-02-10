"""OAuth 2.0 device authorization flow (RFC 8628)."""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.config import settings
from app.core.errors import errors
from app.core.security import generate_token, generate_user_code, get_token_expiry
from app.dependencies import CurrentUser, DbSession
from app.models.oauth import DeviceCode, OAuthClient

router = APIRouter(prefix="/api/oauth/device", tags=["oauth"])


@router.post("/code")
async def device_authorization(
    db: DbSession,
    client_id: str = Form(...),
    scope: str = Form("read"),
) -> dict:
    """Device authorization endpoint.

    Returns device code and user code for device flow.
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

    # Check if device_code grant type is allowed
    if "device_code" not in client.grant_types:
        raise errors.oauth_unsupported_grant_type()

    # Generate codes
    device_code = generate_token(32)
    user_code = generate_user_code()

    # Store device authorization
    # Serialize scopes list to JSON for database storage
    scopes_list = scope.split() if scope else []
    scopes_json = json.dumps(scopes_list)

    dc = DeviceCode(
        device_code=device_code,
        user_code=user_code,
        client_id=client_id,
        scopes=scopes_json,
        interval=settings.device_poll_interval,
        expires_at=get_token_expiry(settings.device_code_expiry),
    )
    db.add(dc)
    # Commit immediately so the device code is available for polling
    # The client will start polling right after receiving this response
    await db.commit()

    # Build verification URI
    base_url = settings.frontend_url
    verification_uri = f"{base_url}/oauth/device"

    return {
        "device_code": device_code,
        "user_code": user_code,
        "verification_uri": verification_uri,
        "verification_uri_complete": f"{verification_uri}?code={user_code}",
        "expires_in": settings.device_code_expiry,
        "interval": settings.device_poll_interval,
    }


@router.get("/lookup")
async def lookup_device_code(
    user: CurrentUser,
    db: DbSession,
    user_code: str = Query(...),
) -> dict:
    """Look up device authorization by user code.

    Returns device authorization details for display to the user.
    Requires authentication.
    """
    # Normalize user code (uppercase, with dash)
    normalized_code = user_code.upper().replace(" ", "-")

    # Look up device code
    result = await db.execute(
        select(DeviceCode, OAuthClient)
        .join(OAuthClient, DeviceCode.client_id == OAuthClient.client_id)
        .where(
            DeviceCode.user_code == normalized_code,
            DeviceCode.status == "pending",
        )
    )
    row = result.first()

    if not row:
        raise errors.not_found("Device authorization")

    dc, client = row

    # Check expiry with timezone handling
    now = datetime.now(UTC)
    expires_at = (
        dc.expires_at.replace(tzinfo=UTC)
        if dc.expires_at.tzinfo is None
        else dc.expires_at
    )
    if expires_at < now:
        raise errors.not_found("Device authorization")

    return {
        "user_code": dc.user_code,
        "client_id": dc.client_id,
        "client_name": client.name,
        "scopes": dc.scopes,
        "expires_at": dc.expires_at.isoformat(),
    }


@router.post("/authorize", response_model=None)
async def authorize_device(
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Authorize or deny device.

    Supports both JSON (for API clients) and form data (for web forms).
    """
    # Determine content type and parse accordingly
    content_type = request.headers.get("content-type", "")

    user_code: str
    action: str

    if "application/json" in content_type:
        # JSON request
        body = await request.json()
        user_code = str(body.get("user_code", ""))
        action = str(body.get("action", ""))
    elif (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    ):
        # Form request
        form = await request.form()
        user_code = str(form.get("user_code", ""))
        action = str(form.get("action", ""))
    else:
        raise errors.validation("Invalid content type")

    if not user_code or not action:
        raise errors.validation("user_code and action are required")

    # Normalize user code
    normalized_code = user_code.upper().replace(" ", "-")

    # Look up device code
    result = await db.execute(
        select(DeviceCode).where(
            DeviceCode.user_code == normalized_code,
            DeviceCode.status == "pending",
        )
    )
    dc = result.scalar_one_or_none()

    if not dc:
        # For JSON requests, raise error; for form requests, redirect
        if "application/json" in content_type:
            raise errors.not_found("Device authorization")
        return RedirectResponse("/oauth/device?error=invalid_code")

    # Check expiry with timezone handling
    now = datetime.now(UTC)
    expires_at = (
        dc.expires_at.replace(tzinfo=UTC)
        if dc.expires_at.tzinfo is None
        else dc.expires_at
    )
    if expires_at < now:
        # For JSON requests, raise error; for form requests, redirect
        if "application/json" in content_type:
            raise errors.not_found("Device authorization")
        return RedirectResponse("/oauth/device?error=invalid_code")

    # Update device code status
    if action == "allow":
        dc.status = "approved"
        dc.user_id = user.id
        redirect_path = "/oauth/device/success"
        message = "Device authorized successfully"
    else:
        dc.status = "denied"
        redirect_path = "/oauth/device/denied"
        message = "Device authorization denied"

    # For JSON requests, return JSON; for form requests, redirect
    if "application/json" in content_type:
        return {"message": message, "status": dc.status}
    return RedirectResponse(redirect_path)
