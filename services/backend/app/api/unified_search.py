"""Unified search API route across tasks, wiki, snippets, and articles."""

import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.wiki import extract_snippet
from app.dependencies import CurrentUserFlexible, DbSession
from app.models.article import Article
from app.models.feed_source import FeedSource
from app.models.project import Project
from app.models.snippet import Snippet
from app.models.todo import Todo
from app.models.wiki_page import WikiPage
from app.schemas import DataResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])

VALID_TYPES = {"task", "wiki", "snippet", "article"}

TYPE_ORDER = ["task", "wiki", "snippet", "article"]


class UnifiedSearchItem(BaseModel):
    type: str
    id: int
    title: str
    subtitle: str | None = None
    url: str
    metadata: dict = {}


def _escape_ilike(value: str) -> str:
    """Escape ILIKE special characters."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def _search_tasks(
    db: AsyncSession, user_id: int, query: str, limit: int
) -> list[UnifiedSearchItem]:
    """Search tasks using full-text search."""
    search_vector = func.to_tsvector(
        "english",
        func.concat(Todo.title, " ", func.coalesce(Todo.description, "")),
    )
    search_query = func.plainto_tsquery("english", query)

    stmt = (
        select(
            Todo.id,
            Todo.title,
            Todo.status,
            Todo.priority,
            Project.name.label("project_name"),
        )
        .outerjoin(Project, Todo.project_id == Project.id)
        .where(
            Todo.user_id == user_id,
            Todo.deleted_at.is_(None),
            search_vector.bool_op("@@")(search_query),
        )
        .order_by(Todo.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    return [
        UnifiedSearchItem(
            type="task",
            id=row.id,
            title=row.title,
            subtitle=row.project_name or row.status,
            url=f"/task/{row.id}",
            metadata={"status": row.status, "priority": row.priority},
        )
        for row in result.all()
    ]


async def _search_wiki(
    db: AsyncSession, user_id: int, query: str, limit: int
) -> list[UnifiedSearchItem]:
    """Search wiki pages using ILIKE."""
    pattern = f"%{query}%"
    stmt = (
        select(WikiPage.id, WikiPage.title, WikiPage.slug, WikiPage.content)
        .where(
            WikiPage.user_id == user_id,
            WikiPage.deleted_at.is_(None),
            or_(
                WikiPage.title.ilike(pattern),
                WikiPage.content.ilike(pattern),
            ),
        )
        .order_by(WikiPage.updated_at.desc().nullslast())
        .limit(limit)
    )

    result = await db.execute(stmt)
    return [
        UnifiedSearchItem(
            type="wiki",
            id=row.id,
            title=row.title,
            subtitle=extract_snippet(row.content, query) if row.content else None,
            url=f"/wiki/{row.slug}",
        )
        for row in result.all()
    ]


async def _search_snippets(
    db: AsyncSession, user_id: int, query: str, limit: int
) -> list[UnifiedSearchItem]:
    """Search snippets using ILIKE."""
    pattern = f"%{query}%"
    stmt = (
        select(Snippet.id, Snippet.title, Snippet.category, Snippet.snippet_date)
        .where(
            Snippet.user_id == user_id,
            Snippet.deleted_at.is_(None),
            or_(
                Snippet.title.ilike(pattern),
                Snippet.content.ilike(pattern),
                Snippet.category.ilike(pattern),
            ),
        )
        .order_by(Snippet.snippet_date.desc(), Snippet.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    return [
        UnifiedSearchItem(
            type="snippet",
            id=row.id,
            title=row.title,
            subtitle=f"{row.category} \u2022 {row.snippet_date.isoformat()}",
            url=f"/snippets/{row.id}",
        )
        for row in result.all()
    ]


async def _search_articles(
    db: AsyncSession, query: str, limit: int
) -> list[UnifiedSearchItem]:
    """Search articles using ILIKE with escaping (global, not user-scoped)."""
    escaped = _escape_ilike(query)
    pattern = f"%{escaped}%"
    stmt = (
        select(
            Article.id,
            Article.title,
            Article.url,
            Article.summary,
            FeedSource.name.label("feed_source_name"),
        )
        .join(FeedSource, Article.feed_source_id == FeedSource.id)
        .where(
            or_(
                Article.title.ilike(pattern, escape="\\"),
                Article.summary.ilike(pattern, escape="\\"),
            ),
        )
        .order_by(Article.published_at.desc().nulls_last())
        .limit(limit)
    )

    result = await db.execute(stmt)
    return [
        UnifiedSearchItem(
            type="article",
            id=row.id,
            title=row.title,
            subtitle=row.feed_source_name,
            url=row.url,
            metadata={"external": True},
        )
        for row in result.all()
    ]


@router.get("/search")
async def unified_search(
    user: CurrentUserFlexible,
    db: DbSession,
    q: str = Query(..., min_length=1, max_length=200),
    types: str | None = Query(None),
    limit: int = Query(5, ge=1, le=20),
) -> DataResponse[dict]:
    """Search across tasks, wiki pages, snippets, and articles."""
    if types:
        requested = {t.strip() for t in types.split(",") if t.strip()}
        requested &= VALID_TYPES
    else:
        requested = VALID_TYPES

    results: dict[str, list[dict]] = {}
    total = 0

    searchers: list[tuple[str, list[UnifiedSearchItem]]] = []

    for content_type in TYPE_ORDER:
        if content_type not in requested:
            continue
        try:
            if content_type == "task":
                items = await _search_tasks(db, user.id, q, limit)
            elif content_type == "wiki":
                items = await _search_wiki(db, user.id, q, limit)
            elif content_type == "snippet":
                items = await _search_snippets(db, user.id, q, limit)
            else:
                items = await _search_articles(db, q, limit)
            searchers.append((content_type, items))
        except Exception:
            logger.warning("Unified search failed for %s", content_type, exc_info=True)
            searchers.append((content_type, []))

    for key, items in searchers:
        results[key] = [item.model_dump() for item in items]
        total += len(items)

    return DataResponse(
        data={
            "results": results,
            "meta": {"total": total, "query": q, "types": list(results.keys())},
        }
    )
