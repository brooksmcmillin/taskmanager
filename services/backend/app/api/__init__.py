"""API routes."""

from app.api import auth, categories, projects, search, todos

__all__ = ["auth", "todos", "projects", "categories", "search"]
