"""OAuth 2.0 authorization endpoint."""

import json
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.config import settings
from app.core.errors import errors
from app.core.security import generate_token, get_token_expiry
from app.dependencies import CurrentUser, DbSession, OptionalUser
from app.models.oauth import AuthorizationCode, OAuthClient

router = APIRouter(prefix="/api/oauth", tags=["oauth"])

# Setup Jinja2 templates
# __file__ is app/api/oauth/authorize.py, so go up 3 levels to get to app/
templates_dir = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/authorize")
async def authorize_get(
    request: Request,
    user: OptionalUser,
    db: DbSession,
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query("read"),
    state: str | None = Query(None),
    code_challenge: str | None = Query(None),
    code_challenge_method: str | None = Query(None),
):
    """Authorization endpoint - shows consent page."""
    # Show login page if not authenticated
    if not user:
        # Build the return_to URL using the public frontend URL
        # to avoid internal Docker service names
        return_path = (
            f"/api/oauth/authorize?{request.url.query}"
            if request.url.query
            else "/api/oauth/authorize"
        )
        return_to = f"{settings.frontend_url}{return_path}"

        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "return_to": return_to,
                "oauth_request": True,
                "error": None,
            },
        )
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
    redirect_uris_list = json.loads(client.redirect_uris)
    if redirect_uri not in redirect_uris_list:
        raise errors.oauth_invalid_redirect()

    # Validate response type
    if response_type != "code":
        params = urlencode({"error": "unsupported_response_type", "state": state or ""})
        return RedirectResponse(f"{redirect_uri}?{params}")

    # Validate requested scopes against client's registered scopes
    requested_scopes = set(scope.split()) if scope else set()
    allowed_scopes = set(json.loads(client.scopes))
    if not requested_scopes.issubset(allowed_scopes):
        raise errors.oauth_invalid_scope()

    # Render consent page with template
    scopes = scope.split()
    return templates.TemplateResponse(
        "oauth_authorize.html",
        {
            "request": request,
            "client": client,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "scopes": scopes,
            "state": state or "",
            "code_challenge": code_challenge or "",
            "code_challenge_method": code_challenge_method or "",
            "user": user,
        },
    )


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
    # Re-validate the client and redirect_uri before issuing any redirect.
    # The form fields are attacker-controlled, so we must not trust redirect_uri
    # without checking it against the client's registered redirect URIs.
    result = await db.execute(
        select(OAuthClient).where(
            OAuthClient.client_id == client_id,
            OAuthClient.is_active.is_(True),
        )
    )
    client = result.scalar_one_or_none()

    if not client:
        raise errors.oauth_invalid_client()

    redirect_uris_list = json.loads(client.redirect_uris)
    if redirect_uri not in redirect_uris_list:
        raise errors.oauth_invalid_redirect()

    # Validate requested scopes against client's registered scopes
    requested_scopes = set(scope.split()) if scope else set()
    allowed_scopes = set(json.loads(client.scopes))
    if not requested_scopes.issubset(allowed_scopes):
        raise errors.oauth_invalid_scope()

    if action == "deny":
        params = urlencode({"error": "access_denied", "state": state})
        # Use 303 to convert POST to GET for OAuth callback
        return RedirectResponse(f"{redirect_uri}?{params}", status_code=303)

    # Generate authorization code
    code = generate_token(32)
    # Convert scope list to JSON string for database storage
    scopes_list = scope.split() if scope else []
    scopes_json = json.dumps(scopes_list)

    auth_code = AuthorizationCode(
        code=code,
        client_id=client_id,
        user_id=user.id,
        redirect_uri=redirect_uri,
        scopes=scopes_json,
        code_challenge=code_challenge or None,
        code_challenge_method=code_challenge_method or None,
        expires_at=get_token_expiry(settings.auth_code_expiry * 60),
    )
    db.add(auth_code)

    params = urlencode({"code": code, "state": state})
    # Use 303 to convert POST to GET for OAuth callback
    return RedirectResponse(f"{redirect_uri}?{params}", status_code=303)
