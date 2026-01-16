"""OAuth 2.0 authorization endpoint."""

from urllib.parse import urlencode

from fastapi import APIRouter, Form, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.config import settings
from app.core.errors import errors
from app.core.security import generate_token, get_token_expiry
from app.dependencies import CurrentUser, DbSession
from app.models.oauth import AuthorizationCode, OAuthClient

router = APIRouter(prefix="/api/oauth", tags=["oauth"])


@router.get("/authorize")
async def authorize_get(
    db: DbSession,
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query("read"),
    state: str | None = Query(None),
    code_challenge: str | None = Query(None),
    code_challenge_method: str | None = Query(None),
) -> RedirectResponse:
    """Authorization endpoint - redirects to consent page or login."""
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

    # Validate redirect URI
    if redirect_uri not in client.redirect_uris:
        raise errors.oauth_invalid_redirect()

    # Validate response type
    if response_type != "code":
        params = urlencode({"error": "unsupported_response_type", "state": state or ""})
        return RedirectResponse(f"{redirect_uri}?{params}")

    # Redirect to consent page with parameters
    consent_params = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state or "",
            "code_challenge": code_challenge or "",
            "code_challenge_method": code_challenge_method or "",
        }
    )
    return RedirectResponse(f"/oauth/authorize?{consent_params}")


@router.post("/authorize")
async def authorize_post(
    user: CurrentUser,
    db: DbSession,
    action: str = Form(...),
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    scope: str = Form("read"),
    state: str = Form(""),
    code_challenge: str = Form(""),
    code_challenge_method: str = Form(""),
) -> RedirectResponse:
    """Process authorization consent."""
    if action == "deny":
        params = urlencode({"error": "access_denied", "state": state})
        return RedirectResponse(f"{redirect_uri}?{params}")

    # Generate authorization code
    code = generate_token(32)
    auth_code = AuthorizationCode(
        code=code,
        client_id=client_id,
        user_id=user.id,
        redirect_uri=redirect_uri,
        scopes=scope.split(),
        code_challenge=code_challenge or None,
        code_challenge_method=code_challenge_method or None,
        expires_at=get_token_expiry(settings.auth_code_expiry * 60),
    )
    db.add(auth_code)

    params = urlencode({"code": code, "state": state})
    return RedirectResponse(f"{redirect_uri}?{params}")
