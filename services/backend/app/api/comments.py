"""Comment API routes for task comments."""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.errors import errors
from app.db.queries import get_resource_for_user
from app.dependencies import CurrentUserFlexible, DbSession
from app.models.comment import Comment
from app.models.todo import Todo
from app.schemas import DataResponse, ListResponse

router = APIRouter(prefix="/api/todos", tags=["comments"])


class CommentCreate(BaseModel):
    """Comment creation schema."""

    content: str = Field(..., min_length=1, max_length=10000)


class CommentUpdate(BaseModel):
    """Comment update schema."""

    content: str = Field(..., min_length=1, max_length=10000)


class CommentResponse(BaseModel):
    """Comment response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    todo_id: int
    user_id: int
    content: str
    created_at: datetime
    updated_at: datetime | None


async def _get_todo_for_user(db: DbSession, todo_id: int, user_id: int) -> Todo:
    """Get a todo by ID, ensuring it belongs to the user."""
    return await get_resource_for_user(
        db, Todo, todo_id, user_id, errors.todo_not_found
    )


async def _get_comment_for_user(
    db: DbSession, comment_id: int, todo_id: int, user_id: int
) -> Comment:
    """Get a comment by ID, ensuring it belongs to the user's todo."""
    result = await db.execute(
        select(Comment).where(
            Comment.id == comment_id,
            Comment.todo_id == todo_id,
            Comment.user_id == user_id,
            Comment.deleted_at.is_(None),
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise errors.comment_not_found()
    return comment


@router.get("/{todo_id}/comments")
async def list_comments(
    todo_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> ListResponse[CommentResponse]:
    """List all comments for a todo."""
    await _get_todo_for_user(db, todo_id, user.id)

    result = await db.execute(
        select(Comment)
        .where(
            Comment.todo_id == todo_id,
            Comment.user_id == user.id,
            Comment.deleted_at.is_(None),
        )
        .order_by(Comment.created_at.asc())
    )
    comments = result.scalars().all()

    return ListResponse(
        data=[CommentResponse.model_validate(c) for c in comments],
        meta={"count": len(comments)},
    )


@router.post("/{todo_id}/comments", status_code=201)
async def create_comment(
    todo_id: int,
    body: CommentCreate,
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[CommentResponse]:
    """Create a comment on a todo."""
    await _get_todo_for_user(db, todo_id, user.id)

    comment = Comment(
        todo_id=todo_id,
        user_id=user.id,
        content=body.content,
    )
    db.add(comment)
    await db.flush()
    await db.refresh(comment)

    return DataResponse(data=CommentResponse.model_validate(comment))


@router.put("/{todo_id}/comments/{comment_id}")
async def update_comment(
    todo_id: int,
    comment_id: int,
    body: CommentUpdate,
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[CommentResponse]:
    """Update a comment's content."""
    await _get_todo_for_user(db, todo_id, user.id)
    comment = await _get_comment_for_user(db, comment_id, todo_id, user.id)

    comment.content = body.content
    await db.flush()
    await db.refresh(comment)

    return DataResponse(data=CommentResponse.model_validate(comment))


@router.delete("/{todo_id}/comments/{comment_id}")
async def delete_comment(
    todo_id: int,
    comment_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Soft-delete a comment."""
    await _get_todo_for_user(db, todo_id, user.id)
    comment = await _get_comment_for_user(db, comment_id, todo_id, user.id)

    comment.deleted_at = datetime.now(UTC)

    return {"data": {"deleted": True, "id": comment_id}}
