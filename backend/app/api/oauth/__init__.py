"""OAuth 2.0 API routes."""

from app.api.oauth import authorize, token, clients, device

__all__ = ["authorize", "token", "clients", "device"]
