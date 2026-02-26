"""Wiki page API routes."""

import re
from datetime import UTC, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import CursorResult, delete, select

from app.core.errors import errors
from app.db.queries import get_resource_for_user
from app.dependencies import CurrentUserFlexible, DbSession
from app.models.todo import Todo
from app.models.wiki_page import WikiPage, WikiPageRevision, todo_wiki_links
from app.schemas import DataResponse, ListResponse

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

RESERVED_SLUGS = {"new", "resolve"}
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SLUG_DEDUP = 100
MAX_RESOLVE_TITLES = 50


class WikiPageCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = ""
    slug: str | None = Field(None, max_length=500)


class WikiPageUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    content: str | None = None
    slug: str | None = Field(None, max_length=500)
    append: bool = False


class WikiPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    content: str
    revision_number: int = 1
    created_at: datetime
    updated_at: datetime | None
    slug_modified: bool = False
    requested_slug: str | None = None


class WikiPageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    created_at: datetime
    updated_at: datetime | None


class WikiPageSearchResult(WikiPageSummary):
    content_snippet: str | None = None


class LinkedTodoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    priority: str
    due_date: str | None = None


class LinkTaskRequest(BaseModel):
    todo_id: int


class BatchLinkTasksRequest(BaseModel):
    todo_ids: list[int]


class BatchLinkTasksResponse(BaseModel):
    linked: list[int]
    already_linked: list[int]
    not_found: list[int]


class WikiPageRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wiki_page_id: int
    title: str
    slug: str
    content: str
    revision_number: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def validate_slug(slug: str) -> None:
    """Validate a user-supplied slug."""
    if len(slug) > 200:
        raise errors.validation("Slug must be 200 characters or fewer")
    if not SLUG_PATTERN.match(slug):
        raise errors.validation(
            "Slug must contain only lowercase letters, numbers, and hyphens"
        )
    if slug.isdigit():
        raise errors.validation("Slug cannot be purely numeric")


def generate_slug(title: str) -> str:
    """Convert title to URL-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug or "untitled"


def extract_snippet(content: str, query: str, max_len: int = 200) -> str | None:
    """Extract a snippet of content around the first match of query."""
    idx = content.lower().find(query.lower())
    if idx == -1:
        return None
    start = max(0, idx - 80)
    end = min(len(content), idx + len(query) + 80)
    snippet = content[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."
    return snippet


async def ensure_unique_slug(
    db: DbSession,
    user_id: int,
    slug: str,
    exclude_id: int | None = None,
) -> tuple[str, bool]:
    """Append -2, -3, etc. if slug already taken by this user.

    Returns (final_slug, was_modified) tuple.
    """
    candidate = slug
    suffix = 1
    while suffix <= MAX_SLUG_DEDUP:
        query = select(WikiPage.id).where(
            WikiPage.user_id == user_id,
            WikiPage.slug == candidate,
            WikiPage.deleted_at.is_(None),
        )
        if exclude_id is not None:
            query = query.where(WikiPage.id != exclude_id)
        result = await db.execute(query)
        if result.scalar_one_or_none() is None:
            was_modified = candidate != slug
            return candidate, was_modified
        suffix += 1
        candidate = f"{slug}-{suffix}"
    raise errors.validation("Too many pages with similar slugs; provide a unique slug")


async def _save_revision(db: DbSession, page: WikiPage) -> None:
    """Save the current page state as a revision before updating."""
    revision = WikiPageRevision(
        wiki_page_id=page.id,
        user_id=page.user_id,
        title=page.title,
        slug=page.slug,
        content=page.content,
        revision_number=page.revision_number,
    )
    db.add(revision)


# ---------------------------------------------------------------------------
# Wiki router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/wiki", tags=["wiki"])


@router.get("")
async def list_wiki_pages(
    user: CurrentUserFlexible,
    db: DbSession,
    q: str | None = Query(None, description="Search query"),
) -> ListResponse[WikiPageSearchResult] | ListResponse[WikiPageSummary]:
    """List wiki pages for the current user, optionally filtered by search."""
    query = select(WikiPage).where(
        WikiPage.user_id == user.id,
        WikiPage.deleted_at.is_(None),
    )
    if q:
        query = query.where(
            WikiPage.title.ilike(f"%{q}%") | WikiPage.content.ilike(f"%{q}%")
        )
    query = query.order_by(WikiPage.updated_at.desc().nullslast())
    result = await db.execute(query)
    pages = result.scalars().all()

    if q:
        data = []
        for p in pages:
            item = WikiPageSearchResult.model_validate(p)
            item.content_snippet = extract_snippet(p.content, q)
            data.append(item)
        return ListResponse(data=data, meta={"count": len(data)})

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
    requested_slug = body.slug
    if body.slug:
        validate_slug(body.slug)
    slug = body.slug if body.slug else generate_slug(body.title)
    if slug in RESERVED_SLUGS:
        raise errors.validation(f"Slug '{slug}' is reserved")
    final_slug, was_modified = await ensure_unique_slug(db, user.id, slug)

    page = WikiPage(
        user_id=user.id,
        title=body.title,
        slug=final_slug,
        content=body.content,
    )
    db.add(page)
    await db.flush()
    await db.refresh(page)

    resp = WikiPageResponse.model_validate(page)
    if was_modified:
        resp.slug_modified = True
        resp.requested_slug = requested_slug or slug
    return DataResponse(data=resp)


@router.get("/resolve")
async def resolve_wiki_links(
    user: CurrentUserFlexible,
    db: DbSession,
    titles: str = Query(..., description="Comma-separated page titles"),
) -> DataResponse[dict[str, str | None]]:
    """Batch resolve page titles to slugs. Returns {title: slug | null}."""
    all_titles = [t.strip() for t in titles.split(",") if t.strip()]
    if len(all_titles) > MAX_RESOLVE_TITLES:
        raise errors.validation(
            f"Too many titles ({len(all_titles)}). Maximum is {MAX_RESOLVE_TITLES}"
        )
    title_list = all_titles
    result_map: dict[str, str | None] = {}
    if title_list:
        result = await db.execute(
            select(WikiPage.title, WikiPage.slug).where(
                WikiPage.user_id == user.id,
                WikiPage.deleted_at.is_(None),
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
        db, WikiPage, page_id, user.id, errors.wiki_page_not_found
    )

    # Save current state as revision before making changes
    await _save_revision(db, page)
    page.revision_number += 1

    slug_modified = False
    requested_slug: str | None = None

    if body.title is not None:
        page.title = body.title
        # Re-slug if title changed and no explicit slug provided
        if body.slug is None:
            new_slug = generate_slug(body.title)
            if new_slug in RESERVED_SLUGS:
                raise errors.validation(f"Slug '{new_slug}' is reserved")
            final_slug, was_modified = await ensure_unique_slug(
                db, user.id, new_slug, exclude_id=page.id
            )
            page.slug = final_slug
            if was_modified:
                slug_modified = True
                requested_slug = new_slug

    if body.slug is not None:
        validate_slug(body.slug)
        if body.slug in RESERVED_SLUGS:
            raise errors.validation(f"Slug '{body.slug}' is reserved")
        requested_slug_val = body.slug
        final_slug, was_modified = await ensure_unique_slug(
            db, user.id, body.slug, exclude_id=page.id
        )
        page.slug = final_slug
        if was_modified:
            slug_modified = True
            requested_slug = requested_slug_val

    if body.content is not None:
        if body.append:
            page.content = page.content + "\n" + body.content
        else:
            page.content = body.content

    await db.flush()
    await db.refresh(page)

    resp = WikiPageResponse.model_validate(page)
    if slug_modified:
        resp.slug_modified = True
        resp.requested_slug = requested_slug
    return DataResponse(data=resp)


@router.delete("/{page_id}")
async def delete_wiki_page(
    page_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Soft-delete a wiki page."""
    page = await get_resource_for_user(
        db, WikiPage, page_id, user.id, errors.wiki_page_not_found
    )
    page.deleted_at = datetime.now(UTC)
    await db.flush()
    return {"data": {"deleted": True, "id": page_id}}


# ---------------------------------------------------------------------------
# Revision endpoints
# ---------------------------------------------------------------------------


@router.get("/{page_id}/revisions")
async def list_revisions(
    page_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> ListResponse[WikiPageRevisionResponse]:
    """List revisions for a wiki page."""
    await get_resource_for_user(
        db, WikiPage, page_id, user.id, errors.wiki_page_not_found
    )
    result = await db.execute(
        select(WikiPageRevision)
        .where(WikiPageRevision.wiki_page_id == page_id)
        .order_by(WikiPageRevision.revision_number.desc())
    )
    revisions = result.scalars().all()
    return ListResponse(
        data=[WikiPageRevisionResponse.model_validate(r) for r in revisions],
        meta={"count": len(revisions)},
    )


@router.get("/{page_id}/revisions/{revision_number}")
async def get_revision(
    page_id: int,
    revision_number: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[WikiPageRevisionResponse]:
    """Get a specific revision of a wiki page."""
    await get_resource_for_user(
        db, WikiPage, page_id, user.id, errors.wiki_page_not_found
    )
    result = await db.execute(
        select(WikiPageRevision).where(
            WikiPageRevision.wiki_page_id == page_id,
            WikiPageRevision.revision_number == revision_number,
        )
    )
    revision = result.scalar_one_or_none()
    if not revision:
        raise errors.not_found("Revision")
    return DataResponse(data=WikiPageRevisionResponse.model_validate(revision))


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
        db, WikiPage, page_id, user.id, errors.wiki_page_not_found
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


@router.post("/{page_id}/link-tasks", status_code=200)
async def batch_link_tasks(
    page_id: int,
    body: BatchLinkTasksRequest,
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[BatchLinkTasksResponse]:
    """Batch link multiple tasks to a wiki page."""
    page = await get_resource_for_user(
        db, WikiPage, page_id, user.id, errors.wiki_page_not_found
    )

    linked: list[int] = []
    already_linked: list[int] = []
    not_found: list[int] = []

    for todo_id in body.todo_ids:
        # Check task exists and belongs to user
        result = await db.execute(
            select(Todo).where(
                Todo.id == todo_id,
                Todo.user_id == user.id,
                Todo.deleted_at.is_(None),
            )
        )
        todo = result.scalar_one_or_none()
        if not todo:
            not_found.append(todo_id)
            continue

        # Check for existing link
        existing = await db.execute(
            select(todo_wiki_links).where(
                todo_wiki_links.c.todo_id == todo_id,
                todo_wiki_links.c.wiki_page_id == page.id,
            )
        )
        if existing.first():
            already_linked.append(todo_id)
            continue

        await db.execute(
            todo_wiki_links.insert().values(todo_id=todo_id, wiki_page_id=page.id)
        )
        linked.append(todo_id)

    return DataResponse(
        data=BatchLinkTasksResponse(
            linked=linked,
            already_linked=already_linked,
            not_found=not_found,
        )
    )


@router.delete("/{page_id}/link-task/{todo_id}")
async def unlink_task(
    page_id: int,
    todo_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Unlink a wiki page from a task."""
    await get_resource_for_user(
        db, WikiPage, page_id, user.id, errors.wiki_page_not_found
    )
    await get_resource_for_user(
        db, Todo, todo_id, user.id, errors.todo_not_found
    )

    cursor: CursorResult = await db.execute(  # type: ignore[assignment]
        delete(todo_wiki_links).where(
            todo_wiki_links.c.todo_id == todo_id,
            todo_wiki_links.c.wiki_page_id == page_id,
        )
    )
    if cursor.rowcount == 0:
        raise errors.not_found("Wiki-task link")

    return {"data": {"deleted": True, "page_id": page_id, "todo_id": todo_id}}


@router.get("/{page_id}/linked-tasks")
async def get_linked_tasks(
    page_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> ListResponse[LinkedTodoResponse]:
    """List tasks linked to a wiki page."""
    await get_resource_for_user(
        db, WikiPage, page_id, user.id, errors.wiki_page_not_found
    )

    result = await db.execute(
        select(Todo)
        .join(todo_wiki_links, todo_wiki_links.c.todo_id == Todo.id)
        .where(
            todo_wiki_links.c.wiki_page_id == page_id,
            Todo.deleted_at.is_(None),
        )
    )
    todos = [LinkedTodoResponse.model_validate(t) for t in result.scalars().all()]
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
        .where(
            todo_wiki_links.c.todo_id == todo_id,
            WikiPage.deleted_at.is_(None),
        )
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
                WikiPage.deleted_at.is_(None),
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
            WikiPage.deleted_at.is_(None),
        )
    )
    page = result.scalar_one_or_none()
    if not page:
        raise errors.wiki_page_not_found()
    return page
