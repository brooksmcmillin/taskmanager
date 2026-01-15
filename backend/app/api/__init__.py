"""API routes."""

from app.api import auth, todos, projects, categories, search

__all__ = ["auth", "todos", "projects", "categories", "search"]
