"""Attachment API routes for todo image uploads."""

import io
import logging
import re
from datetime import datetime

import filetype
from fastapi import APIRouter, UploadFile
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.config import settings
from app.core.errors import ApiError, errors
from app.dependencies import CurrentUser, DbSession
from app.models.attachment import Attachment
from app.models.todo import Todo
from app.schemas import ListResponse
from app.services.storage import storage_service

logger = logging.getLogger(__name__)

# Maximum image dimensions to prevent image bombs
MAX_IMAGE_DIMENSION = 10000


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent header injection attacks.

    Removes or replaces characters that could be used for HTTP header injection,
    path traversal, or other attacks.

    Args:
        filename: The original filename

    Returns:
        A safe filename suitable for use in Content-Disposition headers
    """
    # Remove any path components
    filename = filename.replace("/", "_").replace("\\", "_")
    # Keep only safe characters: alphanumeric, spaces, dots, hyphens, underscores
    safe_filename = re.sub(r"[^\w\s.\-]", "", filename)
    # Collapse multiple spaces/underscores
    safe_filename = re.sub(r"[\s_]+", "_", safe_filename)
    # Ensure it's not empty
    return safe_filename.strip("._") or "attachment"


def _validate_image_content(content: bytes) -> str:
    """Validate that content is actually an allowed image type using magic bytes.

    Args:
        content: The file content

    Returns:
        The detected MIME type

    Raises:
        errors.invalid_file_type: If content is not a valid allowed image type
    """
    kind = filetype.guess(content)
    if kind is None or kind.mime not in settings.allowed_image_types_list:
        raise errors.invalid_file_type(settings.allowed_image_types_list)
    return kind.mime


def _validate_image_dimensions(content: bytes) -> None:
    """Validate image dimensions to prevent image bomb attacks.

    Args:
        content: The image file content

    Raises:
        errors.invalid_file_type: If image has invalid dimensions or is corrupted
    """
    try:
        # Use PIL to verify the image and check dimensions
        img = Image.open(io.BytesIO(content))
        img.verify()  # Verify image integrity

        # Re-open after verify (verify() closes the file)
        img = Image.open(io.BytesIO(content))
        width, height = img.size

        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            raise errors.invalid_file_type(
                [f"images up to {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION} pixels"]
            )
    except ApiError:
        # Re-raise our own errors
        raise
    except Exception as e:
        logger.warning("Image validation failed: %s", e)
        raise errors.invalid_file_type(settings.allowed_image_types_list) from e


router = APIRouter(prefix="/api/todos", tags=["attachments"])


class AttachmentResponse(BaseModel):
    """Attachment response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    todo_id: int
    filename: str
    content_type: str
    file_size: int
    created_at: datetime


async def _get_todo_for_user(db: DbSession, todo_id: int, user_id: int) -> Todo:
    """Get a todo by ID, ensuring it belongs to the user.

    Args:
        db: Database session
        todo_id: Todo ID to fetch
        user_id: User ID to verify ownership

    Returns:
        Todo model instance

    Raises:
        errors.todo_not_found: If todo doesn't exist or belongs to another user
    """
    result = await db.execute(
        select(Todo).where(
            Todo.id == todo_id,
            Todo.user_id == user_id,
            Todo.deleted_at.is_(None),
        )
    )
    todo = result.scalar_one_or_none()
    if not todo:
        raise errors.todo_not_found()
    return todo


async def _get_attachment_for_user(
    db: DbSession, attachment_id: int, todo_id: int, user_id: int
) -> Attachment:
    """Get an attachment by ID, ensuring it belongs to the user's todo.

    Args:
        db: Database session
        attachment_id: Attachment ID to fetch
        todo_id: Todo ID to verify parent relationship
        user_id: User ID to verify ownership

    Returns:
        Attachment model instance

    Raises:
        errors.attachment_not_found: If attachment doesn't exist or is unauthorized
    """
    result = await db.execute(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.todo_id == todo_id,
            Attachment.user_id == user_id,
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise errors.attachment_not_found()
    return attachment


@router.get("/{todo_id}/attachments")
async def list_attachments(
    todo_id: int,
    user: CurrentUser,
    db: DbSession,
) -> ListResponse[AttachmentResponse]:
    """List all attachments for a todo."""
    # Verify todo exists and belongs to user
    await _get_todo_for_user(db, todo_id, user.id)

    result = await db.execute(
        select(Attachment)
        .where(Attachment.todo_id == todo_id, Attachment.user_id == user.id)
        .order_by(Attachment.created_at.asc())
    )
    attachments = result.scalars().all()

    return ListResponse(
        data=[AttachmentResponse.model_validate(a) for a in attachments],
        meta={"count": len(attachments)},
    )


@router.post("/{todo_id}/attachments", status_code=201)
async def upload_attachment(
    todo_id: int,
    file: UploadFile,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Upload an image attachment to a todo.

    Accepts multipart/form-data with a file field.
    Only image files (JPEG, PNG, GIF, WebP) are allowed.
    Maximum file size is configurable (default 10MB).
    Images are validated using magic bytes (not just Content-Type header).
    """
    # Verify todo exists and belongs to user
    await _get_todo_for_user(db, todo_id, user.id)

    # Read file content
    content = await file.read()

    # Validate file size first (before expensive operations)
    if len(content) > settings.max_upload_size_bytes:
        raise errors.file_too_large(settings.max_upload_size_mb)

    # Validate actual file content using magic bytes (not client-provided Content-Type)
    detected_content_type = _validate_image_content(content)

    # Validate image dimensions to prevent image bombs
    _validate_image_dimensions(content)

    # Sanitize filename for safe storage and display
    safe_filename = _sanitize_filename(file.filename or "upload")

    # Save file to storage
    storage_path: str | None = None
    try:
        storage_path, file_size = await storage_service.save_file(
            content, safe_filename, detected_content_type
        )
    except Exception as e:
        logger.exception("Failed to save file to storage")
        raise errors.upload_failed() from e

    # Create attachment record - clean up file on failure
    try:
        attachment = Attachment(
            todo_id=todo_id,
            user_id=user.id,
            filename=safe_filename,
            storage_path=storage_path,
            content_type=detected_content_type,
            file_size=file_size,
        )
        db.add(attachment)
        await db.flush()
        await db.refresh(attachment)
    except Exception:
        # Clean up orphaned file on database failure
        if storage_path:
            try:
                await storage_service.delete_file(storage_path)
            except Exception:
                logger.warning("Failed to clean up orphaned file: %s", storage_path)
        logger.exception("Failed to create attachment record")
        raise

    return {"data": AttachmentResponse.model_validate(attachment)}


@router.get("/{todo_id}/attachments/{attachment_id}")
async def get_attachment(
    todo_id: int,
    attachment_id: int,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    """Download/view an attachment.

    Returns the raw file content with appropriate content type.
    """
    # Verify todo exists and belongs to user
    await _get_todo_for_user(db, todo_id, user.id)

    # Get attachment
    attachment = await _get_attachment_for_user(db, attachment_id, todo_id, user.id)

    # Read file from storage
    try:
        content = await storage_service.read_file(attachment.storage_path)
    except FileNotFoundError as e:
        raise errors.attachment_not_found() from e

    # Sanitize filename for Content-Disposition header to prevent header injection
    safe_filename = _sanitize_filename(attachment.filename)

    return Response(
        content=content,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}"',
            "Cache-Control": "private, max-age=86400",
        },
    )


@router.delete("/{todo_id}/attachments/{attachment_id}")
async def delete_attachment(
    todo_id: int,
    attachment_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Delete an attachment."""
    # Verify todo exists and belongs to user
    await _get_todo_for_user(db, todo_id, user.id)

    # Get attachment
    attachment = await _get_attachment_for_user(db, attachment_id, todo_id, user.id)

    # Delete file from storage (ignore if already deleted)
    await storage_service.delete_file(attachment.storage_path)

    # Delete attachment record
    await db.delete(attachment)

    return {"data": {"deleted": True, "id": attachment_id}}
