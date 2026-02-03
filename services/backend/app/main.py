"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    api_keys,
    attachments,
    auth,
    categories,
    news,
    projects,
    recurring_tasks,
    registration_codes,
    search,
    todos,
    trash,
    webauthn,
)
from app.api.oauth import authorize, clients, device, token
from app.config import settings
from app.db.database import init_db
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    await init_db()
    # Ensure upload directory exists
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="TaskManager API",
    description="Task management API with OAuth 2.0 support",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(todos.router)
app.include_router(projects.router)
app.include_router(categories.router)
app.include_router(search.router)
app.include_router(trash.router)
app.include_router(recurring_tasks.router)
app.include_router(registration_codes.router)
app.include_router(news.router)
app.include_router(attachments.router)
app.include_router(authorize.router)
app.include_router(token.router)
app.include_router(clients.router)
app.include_router(device.router)
app.include_router(api_keys.router)
app.include_router(webauthn.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
