"""OAuth 2.0 device authorization flow (RFC 8628)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.dependencies import DbSession, CurrentUser
from app.core.errors import errors
from app.core.security import generate_token, generate_user_code, get_token_expiry
from app.models.oauth import OAuthClient, DeviceCode
from app.config import settings

router = APIRouter(prefix="/api/oauth/device", tags=["oauth"])


@router.post("/code")
async def device_authorization(
    client_id: str = Form(...),
    scope: str = Form("read"),
    db: DbSession = None,
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
    dc = DeviceCode(
        device_code=device_code,
        user_code=user_code,
        client_id=client_id,
        scopes=scope.split(),
        interval=settings.device_poll_interval,
        expires_at=get_token_expiry(settings.device_code_expiry),
    )
    db.add(dc)

    # Build verification URI
    base_url = "https://todo.brooksmcmillin.com"  # TODO: Get from settings
    verification_uri = f"{base_url}/oauth/device"

    return {
        "device_code": device_code,
        "user_code": user_code,
        "verification_uri": verification_uri,
        "verification_uri_complete": f"{verification_uri}?code={user_code}",
        "expires_in": settings.device_code_expiry,
        "interval": settings.device_poll_interval,
    }


@router.post("/authorize")
async def authorize_device(
    user_code: str = Form(...),
    action: str = Form(...),
    user: CurrentUser = None,
    db: DbSession = None,
) -> RedirectResponse:
    """Authorize or deny device.

    Called when user submits the device authorization form.
    """
    result = await db.execute(
        select(DeviceCode).where(
            DeviceCode.user_code == user_code.upper().replace(" ", "-"),
            DeviceCode.expires_at > datetime.now(timezone.utc),
            DeviceCode.status == "pending",
        )
    )
    dc = result.scalar_one_or_none()

    if not dc:
        return RedirectResponse("/oauth/device?error=invalid_code")

    if action == "approve":
        dc.status = "approved"
        dc.user_id = user.id
        return RedirectResponse("/oauth/device/success")
    else:
        dc.status = "denied"
        return RedirectResponse("/oauth/device/denied")
