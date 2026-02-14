"""News feed API routes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import errors
from app.dependencies import AdminUser, CurrentUser, DbSession
from app.models.article import Article
from app.models.article_interaction import ArticleInteraction, ArticleRating
from app.models.feed_source import FeedSource, FeedType
from app.schemas import ListResponse

router = APIRouter(prefix="/api/news", tags=["news"])


# Schemas
class ArticleResponse(BaseModel):
    """Article response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    url: str
    summary: str | None
    author: str | None
    published_at: datetime | None
    keywords: list[str]
    feed_source_name: str
    is_read: bool = False
    rating: ArticleRating | None = None
    read_at: datetime | None = None


class MarkReadRequest(BaseModel):
    """Mark article as read request."""

    is_read: bool = True


class RateArticleRequest(BaseModel):
    """Rate article request."""

    rating: ArticleRating


class FeedSourceResponse(BaseModel):
    """Feed source response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    description: str | None
    type: FeedType
    is_active: bool
    is_featured: bool
    fetch_interval_hours: int
    last_fetched_at: datetime | None
    quality_score: float
    created_at: datetime


class ToggleFeedSourceRequest(BaseModel):
    """Toggle feed source active status."""

    is_active: bool


class FeedSourceCreate(BaseModel):
    """Create a new feed source."""

    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    type: FeedType = FeedType.article
    is_active: bool = True
    is_featured: bool = False
    fetch_interval_hours: int = Field(default=6, ge=1, le=168)


class FeedSourceUpdate(BaseModel):
    """Update a feed source (partial)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    url: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    type: FeedType | None = None
    is_active: bool | None = None
    is_featured: bool | None = None
    fetch_interval_hours: int | None = Field(default=None, ge=1, le=168)


def _raise_duplicate_error(exc: IntegrityError) -> None:
    """Raise a user-friendly validation error from an IntegrityError.

    Uses the database constraint name for reliable field identification
    instead of parsing the full error message string.
    """
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if not constraint and exc.orig:
        constraint = str(exc.orig)
    if "name" in constraint:
        raise errors.validation("A feed source with this name already exists") from None
    if "url" in constraint:
        raise errors.validation("A feed source with this URL already exists") from None
    raise exc


# Feed Source Management (must be before /{article_id} routes)


@router.get("/sources")
async def list_feed_sources(
    user: CurrentUser,
    db: DbSession,
    featured: bool | None = Query(None),
) -> ListResponse[FeedSourceResponse]:
    """List all feed sources, optionally filtered by featured status."""
    stmt = select(FeedSource).order_by(FeedSource.name)
    if featured is not None:
        stmt = stmt.where(FeedSource.is_featured == featured)
    result = await db.execute(stmt)
    sources = result.scalars().all()

    response_data = [FeedSourceResponse.model_validate(source) for source in sources]
    return ListResponse(data=response_data, meta={})


@router.post("/sources/{source_id}/toggle")
async def toggle_feed_source(
    source_id: int,
    request: ToggleFeedSourceRequest,
    user: AdminUser,
    db: DbSession,
) -> dict:
    """Toggle a feed source active status (admin only)."""
    source = await db.get(FeedSource, source_id)
    if not source:
        raise errors.not_found("Feed source")

    source.is_active = request.is_active
    await db.commit()

    return {"data": {"id": source_id, "is_active": request.is_active}}


@router.post("/sources", status_code=201, response_model=dict[str, FeedSourceResponse])
async def create_feed_source(
    source: FeedSourceCreate,
    user: AdminUser,
    db: DbSession,
) -> dict[str, FeedSourceResponse]:
    """Create a new feed source (admin only)."""
    feed_source = FeedSource(**source.model_dump())
    db.add(feed_source)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        _raise_duplicate_error(e)
    await db.commit()
    await db.refresh(feed_source)

    return {"data": FeedSourceResponse.model_validate(feed_source)}


@router.put("/sources/{source_id}", response_model=dict[str, FeedSourceResponse])
async def update_feed_source(
    source_id: int,
    source: FeedSourceUpdate,
    user: AdminUser,
    db: DbSession,
) -> dict[str, FeedSourceResponse]:
    """Update a feed source (admin only, partial update)."""
    result = await db.execute(
        select(FeedSource).where(FeedSource.id == source_id).with_for_update()
    )
    feed_source = result.scalar_one_or_none()
    if not feed_source:
        raise errors.not_found("Feed source")

    update_data = source.model_dump(exclude_unset=True)

    # Check for duplicate name if name is being changed
    if "name" in update_data and update_data["name"] != feed_source.name:
        existing = await db.execute(
            select(FeedSource).where(
                FeedSource.name == update_data["name"],
                FeedSource.id != source_id,
            )
        )
        if existing.scalar_one_or_none():
            raise errors.validation("A feed source with this name already exists")

    # Check for duplicate URL if URL is being changed
    if "url" in update_data and update_data["url"] != feed_source.url:
        existing = await db.execute(
            select(FeedSource).where(
                FeedSource.url == update_data["url"],
                FeedSource.id != source_id,
            )
        )
        if existing.scalar_one_or_none():
            raise errors.validation("A feed source with this URL already exists")

    for key, value in update_data.items():
        setattr(feed_source, key, value)

    await db.commit()
    await db.refresh(feed_source)

    return {"data": FeedSourceResponse.model_validate(feed_source)}


@router.delete("/sources/{source_id}", response_model=dict[str, dict])
async def delete_feed_source(
    source_id: int,
    user: AdminUser,
    db: DbSession,
) -> dict[str, dict]:
    """Delete a feed source and its articles (admin only)."""
    feed_source = await db.get(FeedSource, source_id)
    if not feed_source:
        raise errors.not_found("Feed source")

    await db.delete(feed_source)
    await db.commit()

    return {"data": {"deleted": True, "id": source_id}}


# Article endpoints


@router.get("")
async def list_articles(
    user: CurrentUser,
    db: DbSession,
    unread_only: bool = Query(False),
    search: str | None = Query(None),
    feed_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ListResponse[ArticleResponse]:
    """List news articles with optional filters."""
    # Base query with feed source
    query = (
        select(
            Article,
            FeedSource.name.label("feed_source_name"),
            ArticleInteraction.is_read,
            ArticleInteraction.rating,
            ArticleInteraction.read_at,
        )
        .join(FeedSource, Article.feed_source_id == FeedSource.id)
        .outerjoin(
            ArticleInteraction,
            and_(
                ArticleInteraction.article_id == Article.id,
                ArticleInteraction.user_id == user.id,
            ),
        )
    )

    # Filter by feed type
    if feed_type and feed_type in ["paper", "article"]:
        query = query.where(FeedSource.type == feed_type)

    # Filter by unread
    if unread_only:
        query = query.where(
            or_(
                ArticleInteraction.is_read.is_(None),
                ArticleInteraction.is_read == False,  # noqa: E712
            )
        )

    # Filter by search
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                Article.title.ilike(search_pattern),
                Article.summary.ilike(search_pattern),
            )
        )

    # Order by published date (newest first)
    query = query.order_by(Article.published_at.desc().nulls_last(), Article.id.desc())

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    rows = result.all()

    articles = []
    for row in rows:
        article = row[0]
        articles.append(
            ArticleResponse(
                id=article.id,
                title=article.title,
                url=article.url,
                summary=article.summary,
                author=article.author,
                published_at=article.published_at,
                keywords=article.keywords,
                feed_source_name=row.feed_source_name,
                is_read=row.is_read or False,
                rating=row.rating,
                read_at=row.read_at,
            )
        )

    return ListResponse(
        data=articles,
        meta={"total": total, "limit": limit, "offset": offset},
    )


@router.get("/{article_id}")
async def get_article(
    article_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Get a single article by ID."""
    query = (
        select(
            Article,
            FeedSource.name.label("feed_source_name"),
            ArticleInteraction.is_read,
            ArticleInteraction.rating,
            ArticleInteraction.read_at,
        )
        .join(FeedSource, Article.feed_source_id == FeedSource.id)
        .outerjoin(
            ArticleInteraction,
            and_(
                ArticleInteraction.article_id == Article.id,
                ArticleInteraction.user_id == user.id,
            ),
        )
        .where(Article.id == article_id)
    )

    result = await db.execute(query)
    row = result.one_or_none()

    if not row:
        raise errors.not_found("Article")

    article = row[0]
    return {
        "data": ArticleResponse(
            id=article.id,
            title=article.title,
            url=article.url,
            summary=article.summary,
            author=article.author,
            published_at=article.published_at,
            keywords=article.keywords,
            feed_source_name=row.feed_source_name,
            is_read=row.is_read or False,
            rating=row.rating,
            read_at=row.read_at,
        )
    }


@router.post("/{article_id}/read")
async def mark_article_read(
    article_id: int,
    request: MarkReadRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Mark an article as read or unread."""
    # Check if article exists
    article = await db.get(Article, article_id)
    if not article:
        raise errors.not_found("Article")

    # Check if interaction already exists
    stmt = select(ArticleInteraction).where(
        ArticleInteraction.user_id == user.id,
        ArticleInteraction.article_id == article_id,
    )
    result = await db.execute(stmt)
    interaction = result.scalar_one_or_none()

    if interaction:
        # Update existing interaction
        interaction.is_read = request.is_read
        interaction.read_at = datetime.now(UTC) if request.is_read else None
    else:
        # Create new interaction
        interaction = ArticleInteraction(
            user_id=user.id,
            article_id=article_id,
            is_read=request.is_read,
            read_at=datetime.now(UTC) if request.is_read else None,
        )
        db.add(interaction)

    await db.commit()

    return {"data": {"is_read": request.is_read, "article_id": article_id}}


@router.post("/{article_id}/rate")
async def rate_article(
    article_id: int,
    request: RateArticleRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Rate an article (good/bad/not_interested)."""
    # Check if article exists
    article = await db.get(Article, article_id)
    if not article:
        raise errors.not_found("Article")

    # Check if interaction already exists
    stmt = select(ArticleInteraction).where(
        ArticleInteraction.user_id == user.id,
        ArticleInteraction.article_id == article_id,
    )
    result = await db.execute(stmt)
    interaction = result.scalar_one_or_none()

    if interaction:
        # Update existing interaction
        interaction.rating = request.rating
        interaction.rated_at = datetime.now(UTC)
    else:
        # Create new interaction
        interaction = ArticleInteraction(
            user_id=user.id,
            article_id=article_id,
            rating=request.rating,
            rated_at=datetime.now(UTC),
        )
        db.add(interaction)

    await db.commit()

    # Update feed source quality score based on rating
    # Good ratings increase score, bad/not_interested decrease it
    feed_source = await db.get(FeedSource, article.feed_source_id)
    if feed_source:
        if request.rating == ArticleRating.good:
            feed_source.quality_score = min(2.0, feed_source.quality_score + 0.1)
        elif request.rating == ArticleRating.bad:
            feed_source.quality_score = max(0.0, feed_source.quality_score - 0.1)
        elif request.rating == ArticleRating.not_interested:
            feed_source.quality_score = max(0.0, feed_source.quality_score - 0.05)
        await db.commit()

    return {"data": {"rating": request.rating, "article_id": article_id}}
