"""MCP Relay debug API proxy for admin users."""

import logging
import re
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.config import settings
from app.dependencies import AdminUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/relay", tags=["admin-relay"])

RELAY_TIMEOUT = 10.0
_CHANNEL_RE = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


class MessageSend(BaseModel):
    content: str = Field(..., min_length=1, max_length=65536)
    sender: str = Field(default="admin-ui", max_length=128)


def _auth_headers() -> dict[str, str]:
    """Build auth headers for the relay debug API."""
    if settings.mcp_relay_debug_token:
        return {"Authorization": f"Bearer {settings.mcp_relay_debug_token}"}
    return {}


def _error_message(exc: Exception) -> str:
    """Return a user-facing error message for relay connection failures."""
    if isinstance(exc, httpx.ConnectError):
        return "Unable to connect to MCP Relay"
    return "MCP Relay request timed out"


def _validate_channel(channel: str) -> None:
    """Validate channel name to prevent path traversal."""
    if not _CHANNEL_RE.match(channel):
        raise HTTPException(
            status_code=400,
            detail="Invalid channel name",
        )


@router.get("/channels")
async def list_channels(_admin: AdminUser) -> dict[str, Any]:
    """List all relay channels with message counts."""
    base_url = settings.mcp_relay_url
    try:
        async with httpx.AsyncClient(timeout=RELAY_TIMEOUT) as client:
            resp = await client.get(
                f"{base_url}/debug/api/channels",
                headers=_auth_headers(),
            )
            resp.raise_for_status()
            return resp.json()
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.warning("Relay request failed: %s", exc)
        return {"channels": [], "error": _error_message(exc)}
    except httpx.HTTPStatusError as exc:
        logger.warning("Relay returned HTTP %s: %s", exc.response.status_code, exc)
        status = exc.response.status_code
        return {"channels": [], "error": f"Relay returned HTTP {status}"}


@router.get("/channels/{channel}/messages")
async def get_messages(
    channel: str,
    _admin: AdminUser,
    since: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    """Get messages for a specific relay channel."""
    _validate_channel(channel)
    base_url = settings.mcp_relay_url
    params: dict[str, str | int] = {"limit": limit}
    if since:
        params["since"] = since
    try:
        async with httpx.AsyncClient(timeout=RELAY_TIMEOUT) as client:
            resp = await client.get(
                f"{base_url}/debug/api/channels/{channel}/messages",
                headers=_auth_headers(),
                params=params,
            )
            resp.raise_for_status()
            return resp.json()
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.warning("Relay request failed: %s", exc)
        return {
            "channel": channel,
            "messages": [],
            "count": 0,
            "error": _error_message(exc),
        }
    except httpx.HTTPStatusError as exc:
        logger.warning("Relay returned HTTP %s: %s", exc.response.status_code, exc)
        return {
            "channel": channel,
            "messages": [],
            "count": 0,
            "error": f"Relay returned HTTP {exc.response.status_code}",
        }


@router.post("/channels/{channel}/messages", status_code=201)
async def send_message(
    channel: str,
    body: MessageSend,
    _admin: AdminUser,
    response: Response,
) -> dict[str, Any]:
    """Send a message to a relay channel."""
    _validate_channel(channel)
    base_url = settings.mcp_relay_url
    try:
        async with httpx.AsyncClient(timeout=RELAY_TIMEOUT) as client:
            resp = await client.post(
                f"{base_url}/debug/api/channels/{channel}/messages",
                headers=_auth_headers(),
                json={"content": body.content, "sender": body.sender},
            )
            resp.raise_for_status()
            return resp.json()
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.warning("Relay request failed: %s", exc)
        response.status_code = 502
        return {"error": _error_message(exc)}
    except httpx.HTTPStatusError as exc:
        logger.warning("Relay returned HTTP %s: %s", exc.response.status_code, exc)
        response.status_code = 502
        return {"error": f"Relay returned HTTP {exc.response.status_code}"}


@router.post("/channels/{channel}/clear")
async def clear_channel(
    channel: str,
    _admin: AdminUser,
) -> dict[str, Any]:
    """Clear all messages in a relay channel."""
    _validate_channel(channel)
    base_url = settings.mcp_relay_url
    try:
        async with httpx.AsyncClient(timeout=RELAY_TIMEOUT) as client:
            resp = await client.post(
                f"{base_url}/debug/api/channels/{channel}/clear",
                headers=_auth_headers(),
            )
            resp.raise_for_status()
            return resp.json()
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.warning("Relay request failed: %s", exc)
        return {"error": _error_message(exc)}
    except httpx.HTTPStatusError as exc:
        logger.warning("Relay returned HTTP %s: %s", exc.response.status_code, exc)
        return {"error": f"Relay returned HTTP {exc.response.status_code}"}
