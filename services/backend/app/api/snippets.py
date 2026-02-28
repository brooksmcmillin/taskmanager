"""Snippet API routes for quick dated log entries."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.core.errors import errors
from app.dependencies import CurrentUserFlexible, DbSession
from app.models.snippet import Snippet
from app.schemas import DataResponse, ListResponse

router = APIRouter(prefix="/api/snippets", tags=["snippets"])

MAX_TAGS = 20
MAX_CONTENT_LENGTH = 50_000

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

Tag = str


class SnippetCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field("", max_length=MAX_CONTENT_LENGTH)
    snippet_date: date | None = None
    tags: list[Tag] = Field(default_factory=list, max_length=MAX_TAGS)


class SnippetUpdate(BaseModel):
    category: str | None = Field(None, min_length=1, max_length=255)
    title: str | None = Field(None, min_length=1, max_length=500)
    content: str | None = Field(None, max_length=MAX_CONTENT_LENGTH)
    snippet_date: date | None = None
    tags: list[Tag] | None = Field(None, max_length=MAX_TAGS)


class SnippetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    title: str
    content: str
    snippet_date: date
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None


class SnippetSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    title: str
    snippet_date: date
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None


class CategoryCount(BaseModel):
    category: str
    count: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
async def list_snippets(
    user: CurrentUserFlexible,
    db: DbSession,
    q: str | None = Query(None, max_length=200),
    category: str | None = Query(None, max_length=255),
    tag: str | None = Query(None, max_length=100),
    date_from: date | None = None,
    date_to: date | None = None,
) -> ListResponse[SnippetSummary]:
    """List snippets with optional search, category, tag, and date filters."""
    stmt = (
        select(Snippet)
        .where(Snippet.user_id == user.id, Snippet.deleted_at.is_(None))
        .order_by(Snippet.snippet_date.desc(), Snippet.created_at.desc())
    )

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            (Snippet.title.ilike(pattern))
            | (Snippet.content.ilike(pattern))
            | (Snippet.category.ilike(pattern))
        )

    if category:
        stmt = stmt.where(Snippet.category == category)

    if tag:
        stmt = stmt.where(Snippet.tags.op("@>")(f'["{tag}"]'))

    if date_from:
        stmt = stmt.where(Snippet.snippet_date >= date_from)

    if date_to:
        stmt = stmt.where(Snippet.snippet_date <= date_to)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    return ListResponse(
        data=[SnippetSummary.model_validate(r) for r in rows],
        meta={"count": len(rows)},
    )


@router.get("/categories")
async def list_categories(
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[list[CategoryCount]]:
    """Return distinct categories with counts for the current user."""
    stmt = (
        select(Snippet.category, func.count(Snippet.id).label("count"))
        .where(Snippet.user_id == user.id, Snippet.deleted_at.is_(None))
        .group_by(Snippet.category)
        .order_by(Snippet.category)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return DataResponse(
        data=[CategoryCount(category=row[0], count=row[1]) for row in rows]
    )


@router.post("", status_code=201)
async def create_snippet(
    body: SnippetCreate,
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[SnippetResponse]:
    """Create a new snippet."""
    snippet = Snippet(
        user_id=user.id,
        category=body.category.strip(),
        title=body.title.strip(),
        content=body.content,
        snippet_date=body.snippet_date or datetime.now(tz=UTC).date(),
        tags=[t.strip() for t in body.tags if t.strip()],
    )
    db.add(snippet)
    await db.flush()
    await db.refresh(snippet)

    return DataResponse(data=SnippetResponse.model_validate(snippet))


@router.get("/{snippet_id}")
async def get_snippet(
    snippet_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[SnippetResponse]:
    """Get a single snippet by ID."""
    stmt = select(Snippet).where(
        Snippet.id == snippet_id,
        Snippet.user_id == user.id,
        Snippet.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    snippet = result.scalar_one_or_none()
    if not snippet:
        raise errors.snippet_not_found()

    return DataResponse(data=SnippetResponse.model_validate(snippet))


@router.put("/{snippet_id}")
async def update_snippet(
    snippet_id: int,
    body: SnippetUpdate,
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[SnippetResponse]:
    """Update a snippet."""
    stmt = select(Snippet).where(
        Snippet.id == snippet_id,
        Snippet.user_id == user.id,
        Snippet.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    snippet = result.scalar_one_or_none()
    if not snippet:
        raise errors.snippet_not_found()

    if body.category is not None:
        snippet.category = body.category.strip()
    if body.title is not None:
        snippet.title = body.title.strip()
    if body.content is not None:
        snippet.content = body.content
    if body.snippet_date is not None:
        snippet.snippet_date = body.snippet_date
    if body.tags is not None:
        snippet.tags = [t.strip() for t in body.tags if t.strip()]

    await db.flush()
    await db.refresh(snippet)

    return DataResponse(data=SnippetResponse.model_validate(snippet))


@router.delete("/{snippet_id}")
async def delete_snippet(
    snippet_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[dict]:
    """Soft-delete a snippet."""
    stmt = select(Snippet).where(
        Snippet.id == snippet_id,
        Snippet.user_id == user.id,
        Snippet.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    snippet = result.scalar_one_or_none()
    if not snippet:
        raise errors.snippet_not_found()

    snippet.deleted_at = datetime.now(UTC)
    await db.flush()

    return DataResponse(data={"deleted": True, "id": snippet_id})
