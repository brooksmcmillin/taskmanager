"""Pydantic schemas for request/response validation.

Note: Most schemas are defined inline in their API modules for simplicity.
This module contains shared schemas used across multiple endpoints.
"""

from typing import TypeVar

from pydantic import BaseModel

# Generic type variable for response data
T = TypeVar("T")


class ListResponse[T](BaseModel):
    """Generic list response with data and metadata.

    Use this for any endpoint that returns a list of items with metadata.

    Example:
        @router.get("")
        async def list_items(...) -> ListResponse[ItemResponse]:
            return ListResponse(data=items, meta={"count": len(items)})
    """

    data: list[T]
    meta: dict


class DataResponse[T](BaseModel):
    """Generic single item response.

    Use this for any endpoint that returns a single item wrapped in a data field.

    Example:
        @router.post("")
        async def create_item(...) -> DataResponse[ItemResponse]:
            return DataResponse(data=item)
    """

    data: T


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
