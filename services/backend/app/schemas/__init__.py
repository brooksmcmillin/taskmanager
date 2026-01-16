"""Pydantic schemas for request/response validation.

Note: Most schemas are defined inline in their API modules for simplicity.
This module contains shared schemas used across multiple endpoints.
"""

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


class DeleteResponse(BaseModel):
    """Delete operation response."""

    deleted: bool


class ErrorDetail(BaseModel):
    """Error detail structure."""

    code: str
    message: str
    details: dict | None = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail
