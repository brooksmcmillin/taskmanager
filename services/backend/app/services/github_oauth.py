"""GitHub OAuth service for handling GitHub authentication."""

import secrets
from dataclasses import dataclass

import httpx

from app.config import settings

# Timeout for GitHub API requests.  Read timeout is lower than RSS feeds
# (10s vs 15s) because GitHub API responses are small JSON payloads.
GITHUB_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=10.0)

# GitHub OAuth endpoints
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_USER_EMAILS_URL = "https://api.github.com/user/emails"


@dataclass
class GitHubUser:
    """GitHub user information."""

    id: str
    login: str
    email: str | None
    avatar_url: str | None
    name: str | None


class GitHubOAuthError(Exception):
    """Exception raised for GitHub OAuth errors."""

    def __init__(self, message: str, error_code: str | None = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


def generate_state() -> str:
    """Generate a cryptographically secure state parameter."""
    return secrets.token_urlsafe(32)


def get_redirect_uri() -> str:
    """Get the OAuth redirect URI."""
    if settings.github_oauth_redirect_uri:
        return settings.github_oauth_redirect_uri
    return f"{settings.frontend_url}/oauth/github/callback"


def get_authorization_url(state: str) -> str:
    """Generate the GitHub OAuth authorization URL.

    Args:
        state: CSRF protection state parameter

    Returns:
        The full authorization URL to redirect the user to
    """
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": get_redirect_uri(),
        "scope": "read:user user:email",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GITHUB_AUTHORIZE_URL}?{query}"


async def exchange_code_for_token(code: str) -> str:
    """Exchange an authorization code for an access token.

    Args:
        code: The authorization code from GitHub

    Returns:
        The access token

    Raises:
        GitHubOAuthError: If the token exchange fails
    """
    async with httpx.AsyncClient(timeout=GITHUB_TIMEOUT) as client:
        response = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": get_redirect_uri(),
            },
            headers={"Accept": "application/json"},
        )

        if response.status_code != 200:
            raise GitHubOAuthError(
                f"Failed to exchange code for token: {response.text}",
                error_code="token_exchange_failed",
            )

        data = response.json()

        if "error" in data:
            raise GitHubOAuthError(
                data.get("error_description", data["error"]),
                error_code=data["error"],
            )

        return data["access_token"]


async def get_user_info(access_token: str) -> GitHubUser:
    """Fetch user information from GitHub API.

    Args:
        access_token: The GitHub access token

    Returns:
        GitHubUser with the user's information

    Raises:
        GitHubOAuthError: If fetching user info fails
    """
    async with httpx.AsyncClient(timeout=GITHUB_TIMEOUT) as client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        # Fetch basic user info
        response = await client.get(GITHUB_USER_URL, headers=headers)

        if response.status_code != 200:
            raise GitHubOAuthError(
                f"Failed to fetch user info: {response.text}",
                error_code="user_info_failed",
            )

        user_data = response.json()

        # Fetch user emails if primary email not in profile
        email = user_data.get("email")
        if not email:
            email_response = await client.get(GITHUB_USER_EMAILS_URL, headers=headers)
            if email_response.status_code == 200:
                emails = email_response.json()
                # Find primary email or first verified email
                for e in emails:
                    if e.get("primary") and e.get("verified"):
                        email = e["email"]
                        break
                if not email:
                    for e in emails:
                        if e.get("verified"):
                            email = e["email"]
                            break

        return GitHubUser(
            id=str(user_data["id"]),
            login=user_data["login"],
            email=email,
            avatar_url=user_data.get("avatar_url"),
            name=user_data.get("name"),
        )


def is_github_configured() -> bool:
    """Check if GitHub OAuth is properly configured."""
    return bool(settings.github_client_id and settings.github_client_secret)
