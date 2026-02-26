"""Wiki page model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.todo import Todo
    from app.models.user import User

# Association table for linking wiki pages to todos (many-to-many)
todo_wiki_links = Table(
    "todo_wiki_links",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "todo_id",
        Integer,
        ForeignKey("todos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "wiki_page_id",
        Integer,
        ForeignKey("wiki_pages.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    UniqueConstraint("todo_id", "wiki_page_id", name="uq_todo_wiki_link"),
)


class WikiPage(Base):
    """Wiki page model for per-user markdown documents."""

    __tablename__ = "wiki_pages"
    __table_args__ = (
        UniqueConstraint("user_id", "slug", name="uq_wiki_page_user_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(500))
    slug: Mapped[str] = mapped_column(String(500), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="wiki_pages")
    linked_todos: Mapped[list[Todo]] = relationship(
        "Todo",
        secondary=todo_wiki_links,
        backref="linked_wiki_pages",
    )
