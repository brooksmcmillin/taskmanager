"""Wiki page API routes."""

import re
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy import func as sa_func

from app.core.errors import errors
from app.db.queries import get_resource_for_user
from app.dependencies import CurrentUserFlexible, DbSession
from app.models.todo import Todo
from app.models.wiki_page import WikiPage, WikiPageRevision, todo_wiki_links
from app.schemas import DataResponse, ListResponse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESERVED_SLUGS = {"new", "resolve", "tree"}
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SLUG_DEDUP = 100
MAX_RESOLVE_TITLES = 50
MAX_BATCH_LINK_TASKS = 100
MAX_CONTENT_LENGTH = 500_000
MAX_WIKI_DEPTH = 3
MAX_TAGS = 20
MAX_TAG_LENGTH = 50

Tag = Annotated[str, Field(min_length=1, max_length=MAX_TAG_LENGTH)]

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class WikiPageCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field("", max_length=MAX_CONTENT_LENGTH)
    slug: str | None = Field(None, max_length=500)
    parent_id: int | None = None
    tags: list[Tag] = Field(default_factory=list, max_length=MAX_TAGS)


class WikiPageUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    content: str | None = Field(None, max_length=MAX_CONTENT_LENGTH)
    slug: str | None = Field(None, max_length=500)
    append: bool = False
    parent_id: int | None = None
    remove_parent: bool = False
    tags: list[Tag] | None = Field(None, max_length=MAX_TAGS)


class WikiPageAncestor(BaseModel):
    id: int
    title: str
    slug: str


class WikiPageChildSummary(BaseModel):
    id: int
    title: str
    slug: str
    child_count: int = 0


class WikiPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    content: str
    parent_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    revision_number: int = 1
    created_at: datetime
    updated_at: datetime | None
    slug_modified: bool = False
    requested_slug: str | None = None
    ancestors: list[WikiPageAncestor] = Field(default_factory=list)
    children: list[WikiPageChildSummary] = Field(default_factory=list)


class WikiPageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    parent_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None


class WikiPageSearchResult(WikiPageSummary):
    content_snippet: str | None = None


class WikiTreeNode(BaseModel):
    id: int
    title: str
    slug: str
    tags: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None
    children: list["WikiTreeNode"] = Field(default_factory=list)


class LinkedTodoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    priority: str
    due_date: date | None = None


class LinkTaskRequest(BaseModel):
    todo_id: int


class BatchLinkTasksRequest(BaseModel):
    todo_ids: list[int] = Field(..., max_length=MAX_BATCH_LINK_TASKS)


class BatchLinkTasksResponse(BaseModel):
    linked: list[int]
    already_linked: list[int]
    not_found: list[int]


class WikiPageRevisionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wiki_page_id: int
    title: str
    slug: str
    revision_number: int
    created_at: datetime


class WikiPageRevisionResponse(WikiPageRevisionSummary):
    content: str


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


async def _get_ancestors(db: DbSession, page: WikiPage) -> list[WikiPageAncestor]:
    """Walk parent chain and return root-first ancestor list."""
    ancestors: list[WikiPageAncestor] = []
    current = page
    seen: set[int] = {page.id}
    while current.parent_id is not None:
        result = await db.execute(
            select(WikiPage).where(
                WikiPage.id == current.parent_id,
                WikiPage.deleted_at.is_(None),
            )
        )
        parent = result.scalar_one_or_none()
        if parent is None or parent.id in seen:
            break
        seen.add(parent.id)
        ancestors.append(
            WikiPageAncestor(id=parent.id, title=parent.title, slug=parent.slug)
        )
        current = parent
    ancestors.reverse()
    return ancestors


async def _get_children_with_counts(
    db: DbSession, page_id: int, user_id: int
) -> list[WikiPageChildSummary]:
    """Get direct children of a page with their own child counts."""
    # Subquery to count grandchildren per child
    grandchild_count = (
        select(
            WikiPage.parent_id,
            sa_func.count(WikiPage.id).label("cnt"),
        )
        .where(WikiPage.deleted_at.is_(None))
        .group_by(WikiPage.parent_id)
        .subquery()
    )

    stmt = (
        select(
            WikiPage.id,
            WikiPage.title,
            WikiPage.slug,
            sa_func.coalesce(grandchild_count.c.cnt, 0).label("child_count"),
        )
        .outerjoin(grandchild_count, grandchild_count.c.parent_id == WikiPage.id)
        .where(
            WikiPage.parent_id == page_id,
            WikiPage.user_id == user_id,
            WikiPage.deleted_at.is_(None),
        )
        .order_by(WikiPage.title)
    )
    result = await db.execute(stmt)
    return [
        WikiPageChildSummary(
            id=row.id,
            title=row.title,
            slug=row.slug,
            child_count=row.child_count,
        )
        for row in result.all()
    ]


async def _validate_parent(
    db: DbSession,
    user_id: int,
    parent_id: int,
    exclude_id: int | None = None,
) -> None:
    """Validate parent_id: exists, owned by user, not circular, depth OK."""
    # Check existence and ownership
    result = await db.execute(
        select(WikiPage).where(
            WikiPage.id == parent_id,
            WikiPage.user_id == user_id,
            WikiPage.deleted_at.is_(None),
        )
    )
    parent = result.scalar_one_or_none()
    if parent is None:
        raise errors.validation("Parent page not found")

    # Cannot be self
    if exclude_id is not None and parent_id == exclude_id:
        raise errors.validation("A page cannot be its own parent")

    # Check depth: walk up from parent, counting levels
    depth = 1  # parent is at least depth 1
    current = parent
    seen: set[int] = {parent_id}
    if exclude_id is not None:
        seen.add(exclude_id)
    while current.parent_id is not None:
        if current.parent_id in seen:
            raise errors.validation("Circular parent reference detected")
        seen.add(current.parent_id)
        r = await db.execute(
            select(WikiPage).where(
                WikiPage.id == current.parent_id,
                WikiPage.deleted_at.is_(None),
            )
        )
        current = r.scalar_one_or_none()
        if current is None:
            break
        depth += 1

    # page_depth = depth of the moved/new page under the new parent
    page_depth = depth + 1

    # When reparenting, also account for the subtree depth below the moved page
    subtree_depth = 0
    if exclude_id is not None:
        subtree_depth = await _get_subtree_depth(db, exclude_id)

    if page_depth + subtree_depth > MAX_WIKI_DEPTH:
        raise errors.validation(f"Maximum nesting depth of {MAX_WIKI_DEPTH} exceeded")


async def _get_subtree_depth(db: DbSession, page_id: int) -> int:
    """Return the maximum depth of descendants below page_id (0 if leaf)."""
    max_depth = 0
    # BFS with depth tracking
    to_visit: list[tuple[int, int]] = [(page_id, 0)]
    visited: set[int] = set()
    while to_visit:
        current_id, current_depth = to_visit.pop()
        if current_id in visited:
            continue
        visited.add(current_id)
        result = await db.execute(
            select(WikiPage.id).where(
                WikiPage.parent_id == current_id,
                WikiPage.deleted_at.is_(None),
            )
        )
        for row in result.all():
            child_depth = current_depth + 1
            if child_depth > max_depth:
                max_depth = child_depth
            to_visit.append((row.id, child_depth))
    return max_depth


async def _soft_delete_descendants(db: DbSession, page_id: int) -> None:
    """Recursively soft-delete all descendants of a page."""
    result = await db.execute(
        select(WikiPage).where(
            WikiPage.parent_id == page_id,
            WikiPage.deleted_at.is_(None),
        )
    )
    children = result.scalars().all()
    for child in children:
        child.deleted_at = datetime.now(UTC)
        await _soft_delete_descendants(db, child.id)


# ---------------------------------------------------------------------------
# Wiki router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/wiki", tags=["wiki"])


@router.get("")
async def list_wiki_pages(
    user: CurrentUserFlexible,
    db: DbSession,
    q: str | None = Query(None, description="Search query"),
    tag: str | None = Query(None, description="Filter by tag"),
    parent_id: int | None = Query(None, description="Filter by parent (0=root only)"),
) -> ListResponse[WikiPageSearchResult]:
    """List wiki pages for the current user, optionally filtered by search."""
    query = select(WikiPage).where(
        WikiPage.user_id == user.id,
        WikiPage.deleted_at.is_(None),
    )
    if q:
        query = query.where(
            WikiPage.title.ilike(f"%{q}%") | WikiPage.content.ilike(f"%{q}%")
        )
    if tag:
        query = query.where(WikiPage.tags.op("@>")(sa_func.jsonb_build_array(tag)))
    if parent_id is not None:
        if parent_id == 0:
            query = query.where(WikiPage.parent_id.is_(None))
        else:
            query = query.where(WikiPage.parent_id == parent_id)
    query = query.order_by(WikiPage.updated_at.desc().nullslast())
    result = await db.execute(query)
    pages = result.scalars().all()

    data = []
    for p in pages:
        item = WikiPageSearchResult.model_validate(p)
        if q:
            item.content_snippet = extract_snippet(p.content, q)
        data.append(item)
    return ListResponse(data=data, meta={"count": len(data)})


@router.post("", status_code=201)
async def create_wiki_page(
    body: WikiPageCreate,
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[WikiPageResponse]:
    """Create a new wiki page."""
    # Validate parent
    if body.parent_id is not None:
        await _validate_parent(db, user.id, body.parent_id)

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
        parent_id=body.parent_id,
        tags=body.tags,
    )
    db.add(page)
    await db.flush()
    await db.refresh(page)

    ancestors = await _get_ancestors(db, page)
    children = await _get_children_with_counts(db, page.id, user.id)

    resp = WikiPageResponse(
        id=page.id,
        title=page.title,
        slug=page.slug,
        content=page.content,
        parent_id=page.parent_id,
        tags=page.tags or [],
        revision_number=page.revision_number,
        created_at=page.created_at,
        updated_at=page.updated_at,
        ancestors=ancestors,
        children=children,
    )
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


@router.get("/tree")
async def get_wiki_tree(
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[list[WikiTreeNode]]:
    """Get full nested tree of wiki pages."""
    result = await db.execute(
        select(WikiPage)
        .where(
            WikiPage.user_id == user.id,
            WikiPage.deleted_at.is_(None),
        )
        .order_by(WikiPage.title)
    )
    pages = result.scalars().all()

    # Build lookup maps
    children_map: dict[int | None, list[WikiPage]] = {}
    for p in pages:
        children_map.setdefault(p.parent_id, []).append(p)

    def build_tree(parent_id: int | None) -> list[WikiTreeNode]:
        nodes: list[WikiTreeNode] = []
        for p in children_map.get(parent_id, []):
            nodes.append(
                WikiTreeNode(
                    id=p.id,
                    title=p.title,
                    slug=p.slug,
                    tags=p.tags or [],
                    updated_at=p.updated_at,
                    children=build_tree(p.id),
                )
            )
        return nodes

    tree = build_tree(None)
    return DataResponse(data=tree)


@router.get("/{slug_or_id}")
async def get_wiki_page(
    slug_or_id: str,
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[WikiPageResponse]:
    """Get a wiki page by slug or numeric ID."""
    page = await _resolve_page(db, user.id, slug_or_id)
    ancestors = await _get_ancestors(db, page)
    children = await _get_children_with_counts(db, page.id, user.id)
    resp = WikiPageResponse(
        id=page.id,
        title=page.title,
        slug=page.slug,
        content=page.content,
        parent_id=page.parent_id,
        tags=page.tags or [],
        revision_number=page.revision_number,
        created_at=page.created_at,
        updated_at=page.updated_at,
        ancestors=ancestors,
        children=children,
    )
    return DataResponse(data=resp)


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

    # Atomically increment revision_number at the SQL level
    await db.execute(
        update(WikiPage)
        .where(WikiPage.id == page.id)
        .values(revision_number=WikiPage.revision_number + 1)
    )

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
            if page.content:
                new_content = page.content + "\n" + body.content
            else:
                new_content = body.content
            if len(new_content) > MAX_CONTENT_LENGTH:
                raise errors.validation(
                    f"Total content exceeds maximum of {MAX_CONTENT_LENGTH} characters"
                )
            page.content = new_content
        else:
            page.content = body.content

    # Handle parent changes
    if body.remove_parent:
        page.parent_id = None
    elif body.parent_id is not None:
        await _validate_parent(db, user.id, body.parent_id, exclude_id=page.id)
        page.parent_id = body.parent_id

    # Handle tags
    if body.tags is not None:
        page.tags = body.tags

    await db.flush()
    await db.refresh(page)

    ancestors = await _get_ancestors(db, page)
    children = await _get_children_with_counts(db, page.id, user.id)

    resp = WikiPageResponse(
        id=page.id,
        title=page.title,
        slug=page.slug,
        content=page.content,
        parent_id=page.parent_id,
        tags=page.tags or [],
        revision_number=page.revision_number,
        created_at=page.created_at,
        updated_at=page.updated_at,
        ancestors=ancestors,
        children=children,
    )
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
    """Soft-delete a wiki page and all descendants."""
    page = await get_resource_for_user(
        db, WikiPage, page_id, user.id, errors.wiki_page_not_found
    )
    page.deleted_at = datetime.now(UTC)
    await _soft_delete_descendants(db, page.id)
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
) -> ListResponse[WikiPageRevisionSummary]:
    """List revisions for a wiki page (without content)."""
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
        data=[WikiPageRevisionSummary.model_validate(r) for r in revisions],
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

    # Deduplicate IDs while preserving order
    seen: set[int] = set()
    unique_ids: list[int] = []
    for tid in body.todo_ids:
        if tid not in seen:
            seen.add(tid)
            unique_ids.append(tid)

    # Batch-fetch all matching todos in one query
    result = await db.execute(
        select(Todo).where(
            Todo.id.in_(unique_ids),
            Todo.user_id == user.id,
            Todo.deleted_at.is_(None),
        )
    )
    found_todos = {t.id for t in result.scalars().all()}

    # Batch-fetch existing links in one query
    existing_result = await db.execute(
        select(todo_wiki_links.c.todo_id).where(
            todo_wiki_links.c.wiki_page_id == page.id,
            todo_wiki_links.c.todo_id.in_(unique_ids),
        )
    )
    existing_links = {row.todo_id for row in existing_result.all()}

    linked: list[int] = []
    already_linked: list[int] = []
    not_found: list[int] = []

    for todo_id in unique_ids:
        if todo_id not in found_todos:
            not_found.append(todo_id)
        elif todo_id in existing_links:
            already_linked.append(todo_id)
        else:
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
    await get_resource_for_user(db, Todo, todo_id, user.id, errors.todo_not_found)

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
    await get_resource_for_user(db, Todo, todo_id, user.id, errors.todo_not_found)

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
