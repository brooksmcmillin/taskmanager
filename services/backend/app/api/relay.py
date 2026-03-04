"""MCP Relay debug API proxy for admin users."""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.dependencies import AdminUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/relay", tags=["admin-relay"])

RELAY_TIMEOUT = 10.0

_ERROR_MESSAGES: dict[type[Exception], str] = {
    httpx.ConnectError: "Unable to connect to MCP Relay",
    httpx.TimeoutException: "MCP Relay request timed out",
}


class MessageSend(BaseModel):
    content: str = Field(..., min_length=1, max_length=65536)
    sender: str = Field(default="admin-ui", max_length=128)


def _auth_headers() -> dict[str, str]:
    """Build auth headers for the relay debug API."""
    if settings.mcp_relay_debug_token:
        return {"Authorization": f"Bearer {settings.mcp_relay_debug_token}"}
    return {}


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
        message = _ERROR_MESSAGES.get(type(exc), "Relay request failed")
        return {"channels": [], "error": message}
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
        message = _ERROR_MESSAGES.get(type(exc), "Relay request failed")
        return {"channel": channel, "messages": [], "count": 0, "error": message}
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
) -> dict[str, Any]:
    """Send a message to a relay channel."""
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
        message = _ERROR_MESSAGES.get(type(exc), "Relay request failed")
        return {"error": message}
    except httpx.HTTPStatusError as exc:
        logger.warning("Relay returned HTTP %s: %s", exc.response.status_code, exc)
        return {"error": f"Relay returned HTTP {exc.response.status_code}"}


@router.post("/channels/{channel}/clear")
async def clear_channel(
    channel: str,
    _admin: AdminUser,
) -> dict[str, Any]:
    """Clear all messages in a relay channel."""
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
        message = _ERROR_MESSAGES.get(type(exc), "Relay request failed")
        return {"error": message}
    except httpx.HTTPStatusError as exc:
        logger.warning("Relay returned HTTP %s: %s", exc.response.status_code, exc)
        return {"error": f"Relay returned HTTP {exc.response.status_code}"}
