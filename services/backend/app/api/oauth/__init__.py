"""OAuth 2.0 API routes."""

from app.api.oauth import authorize, clients, device, token

__all__ = ["authorize", "token", "clients", "device"]
