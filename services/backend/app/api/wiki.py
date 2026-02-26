"""Wiki page API routes."""

import re
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.core.errors import errors
from app.db.queries import get_resource_for_user
from app.dependencies import CurrentUserFlexible, DbSession
from app.models.todo import Todo
from app.models.wiki_page import WikiPage, todo_wiki_links
from app.schemas import DataResponse, ListResponse

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

RESERVED_SLUGS = {"new", "resolve"}


class WikiPageCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = ""
    slug: str | None = Field(None, max_length=500)


class WikiPageUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    content: str | None = None
    slug: str | None = Field(None, max_length=500)


class WikiPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    content: str
    created_at: datetime
    updated_at: datetime | None


class WikiPageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    created_at: datetime
    updated_at: datetime | None


class LinkedTodoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    priority: str
    due_date: str | None = None


class LinkTaskRequest(BaseModel):
    todo_id: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def generate_slug(title: str) -> str:
    """Convert title to URL-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug or "untitled"


async def ensure_unique_slug(
    db: DbSession,
    user_id: int,
    slug: str,
    exclude_id: int | None = None,
) -> str:
    """Append -2, -3, etc. if slug already taken by this user."""
    candidate = slug
    suffix = 1
    while True:
        query = select(WikiPage.id).where(
            WikiPage.user_id == user_id,
            WikiPage.slug == candidate,
        )
        if exclude_id is not None:
            query = query.where(WikiPage.id != exclude_id)
        result = await db.execute(query)
        if result.scalar_one_or_none() is None:
            return candidate
        suffix += 1
        candidate = f"{slug}-{suffix}"


# ---------------------------------------------------------------------------
# Wiki router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/wiki", tags=["wiki"])


@router.get("")
async def list_wiki_pages(
    user: CurrentUserFlexible,
    db: DbSession,
    q: str | None = Query(None, description="Search query"),
) -> ListResponse[WikiPageSummary]:
    """List wiki pages for the current user, optionally filtered by search."""
    query = select(WikiPage).where(WikiPage.user_id == user.id)
    if q:
        query = query.where(
            WikiPage.title.ilike(f"%{q}%") | WikiPage.content.ilike(f"%{q}%")
        )
    query = query.order_by(WikiPage.updated_at.desc().nullslast())
    result = await db.execute(query)
    pages = result.scalars().all()
    return ListResponse(
        data=[WikiPageSummary.model_validate(p) for p in pages],
        meta={"count": len(pages)},
    )


@router.post("", status_code=201)
async def create_wiki_page(
    body: WikiPageCreate,
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[WikiPageResponse]:
    """Create a new wiki page."""
    slug = body.slug if body.slug else generate_slug(body.title)
    if slug in RESERVED_SLUGS:
        raise errors.validation(f"Slug '{slug}' is reserved")
    slug = await ensure_unique_slug(db, user.id, slug)

    page = WikiPage(
        user_id=user.id,
        title=body.title,
        slug=slug,
        content=body.content,
    )
    db.add(page)
    await db.flush()
    await db.refresh(page)

    return DataResponse(data=WikiPageResponse.model_validate(page))


@router.get("/resolve")
async def resolve_wiki_links(
    user: CurrentUserFlexible,
    db: DbSession,
    titles: str = Query(..., description="Comma-separated page titles"),
) -> DataResponse[dict[str, str | None]]:
    """Batch resolve page titles to slugs. Returns {title: slug | null}."""
    title_list = [t.strip() for t in titles.split(",") if t.strip()]
    result_map: dict[str, str | None] = {}
    if title_list:
        result = await db.execute(
            select(WikiPage.title, WikiPage.slug).where(
                WikiPage.user_id == user.id,
                WikiPage.title.in_(title_list),
            )
        )
        found = {row.title: row.slug for row in result.all()}
        for title in title_list:
            result_map[title] = found.get(title)
    return DataResponse(data=result_map)


@router.get("/{slug_or_id}")
async def get_wiki_page(
    slug_or_id: str,
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[WikiPageResponse]:
    """Get a wiki page by slug or numeric ID."""
    page = await _resolve_page(db, user.id, slug_or_id)
    return DataResponse(data=WikiPageResponse.model_validate(page))


@router.put("/{page_id}")
async def update_wiki_page(
    page_id: int,
    body: WikiPageUpdate,
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[WikiPageResponse]:
    """Update an existing wiki page."""
    page = await get_resource_for_user(
        db, WikiPage, page_id, user.id, errors.wiki_page_not_found, check_deleted=False
    )

    if body.title is not None:
        page.title = body.title
        # Re-slug if title changed and no explicit slug provided
        if body.slug is None:
            new_slug = generate_slug(body.title)
            if new_slug in RESERVED_SLUGS:
                raise errors.validation(f"Slug '{new_slug}' is reserved")
            page.slug = await ensure_unique_slug(
                db, user.id, new_slug, exclude_id=page.id
            )

    if body.slug is not None:
        if body.slug in RESERVED_SLUGS:
            raise errors.validation(f"Slug '{body.slug}' is reserved")
        page.slug = await ensure_unique_slug(db, user.id, body.slug, exclude_id=page.id)

    if body.content is not None:
        page.content = body.content

    await db.flush()
    await db.refresh(page)

    return DataResponse(data=WikiPageResponse.model_validate(page))


@router.delete("/{page_id}")
async def delete_wiki_page(
    page_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Hard-delete a wiki page."""
    page = await get_resource_for_user(
        db, WikiPage, page_id, user.id, errors.wiki_page_not_found, check_deleted=False
    )
    await db.delete(page)
    return {"data": {"deleted": True, "id": page_id}}


# ---------------------------------------------------------------------------
# Task linking endpoints
# ---------------------------------------------------------------------------


@router.post("/{page_id}/link-task", status_code=201)
async def link_task(
    page_id: int,
    body: LinkTaskRequest,
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[LinkedTodoResponse]:
    """Link a wiki page to a task."""
    page = await get_resource_for_user(
        db, WikiPage, page_id, user.id, errors.wiki_page_not_found, check_deleted=False
    )
    todo = await get_resource_for_user(
        db, Todo, body.todo_id, user.id, errors.todo_not_found
    )

    # Check for existing link
    existing = await db.execute(
        select(todo_wiki_links).where(
            todo_wiki_links.c.todo_id == todo.id,
            todo_wiki_links.c.wiki_page_id == page.id,
        )
    )
    if existing.first():
        raise errors.wiki_link_exists()

    await db.execute(
        todo_wiki_links.insert().values(todo_id=todo.id, wiki_page_id=page.id)
    )

    return DataResponse(data=LinkedTodoResponse.model_validate(todo))


@router.delete("/{page_id}/link-task/{todo_id}")
async def unlink_task(
    page_id: int,
    todo_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Unlink a wiki page from a task."""
    await get_resource_for_user(
        db, WikiPage, page_id, user.id, errors.wiki_page_not_found, check_deleted=False
    )
    await get_resource_for_user(
        db, Todo, todo_id, user.id, errors.todo_not_found
    )

    result = await db.execute(
        delete(todo_wiki_links).where(
            todo_wiki_links.c.todo_id == todo_id,
            todo_wiki_links.c.wiki_page_id == page_id,
        )
    )
    if result.rowcount == 0:
        raise errors.not_found("Wiki-task link")

    return {"data": {"deleted": True, "page_id": page_id, "todo_id": todo_id}}


@router.get("/{page_id}/linked-tasks")
async def get_linked_tasks(
    page_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> ListResponse[LinkedTodoResponse]:
    """List tasks linked to a wiki page."""
    page = await get_resource_for_user(
        db, WikiPage, page_id, user.id, errors.wiki_page_not_found, check_deleted=False
    )

    result = await db.execute(
        select(WikiPage)
        .where(WikiPage.id == page.id)
        .options(selectinload(WikiPage.linked_todos))
    )
    page_with_todos = result.scalar_one()

    todos = [
        LinkedTodoResponse.model_validate(t)
        for t in page_with_todos.linked_todos
        if t.deleted_at is None
    ]
    return ListResponse(data=todos, meta={"count": len(todos)})


# ---------------------------------------------------------------------------
# Todo → wiki pages router
# ---------------------------------------------------------------------------

todo_wiki_router = APIRouter(prefix="/api/todos", tags=["wiki"])


@todo_wiki_router.get("/{todo_id}/wiki-pages")
async def get_todo_wiki_pages(
    todo_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> ListResponse[WikiPageSummary]:
    """List wiki pages linked to a task."""
    await get_resource_for_user(
        db, Todo, todo_id, user.id, errors.todo_not_found
    )

    result = await db.execute(
        select(WikiPage)
        .join(todo_wiki_links, todo_wiki_links.c.wiki_page_id == WikiPage.id)
        .where(todo_wiki_links.c.todo_id == todo_id)
        .order_by(WikiPage.title)
    )
    pages = result.scalars().all()

    return ListResponse(
        data=[WikiPageSummary.model_validate(p) for p in pages],
        meta={"count": len(pages)},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _resolve_page(db: DbSession, user_id: int, slug_or_id: str) -> WikiPage:
    """Resolve a wiki page by slug or numeric ID."""
    # Try numeric ID first
    if slug_or_id.isdigit():
        page_id = int(slug_or_id)
        result = await db.execute(
            select(WikiPage).where(
                WikiPage.id == page_id,
                WikiPage.user_id == user_id,
            )
        )
        page = result.scalar_one_or_none()
        if page:
            return page

    # Fall back to slug lookup
    result = await db.execute(
        select(WikiPage).where(
            WikiPage.slug == slug_or_id,
            WikiPage.user_id == user_id,
        )
    )
    page = result.scalar_one_or_none()
    if not page:
        raise errors.wiki_page_not_found()
    return page
