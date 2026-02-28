"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import (
    admin_loki,
    api_keys,
    attachments,
    auth,
    categories,
    comments,
    news,
    projects,
    recurring_tasks,
    registration_codes,
    search,
    service_accounts,
    snippets,
    todos,
    trash,
    webauthn,
    wiki,
)
from app.api.oauth import authorize, clients, device, github, token
from app.config import settings
from app.core.csrf import CSRFMiddleware
from app.db.database import init_db
from app.dependencies import get_db
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

# CSRF middleware (must be added before CORS so it runs after CORS in the chain)
app.add_middleware(CSRFMiddleware, allowed_origins=settings.cors_origins)

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
app.include_router(comments.router)
app.include_router(authorize.router)
app.include_router(token.router)
app.include_router(clients.router)
app.include_router(device.router)
app.include_router(api_keys.router)
app.include_router(webauthn.router)
app.include_router(github.router)
app.include_router(admin_loki.router)
app.include_router(service_accounts.router)
app.include_router(snippets.router)
app.include_router(wiki.router)
app.include_router(wiki.todo_wiki_router)


# Static files (self-hosted fonts)
app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)

Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    excluded_handlers=["/health", "/metrics"],
).instrument(app).expose(app, endpoint="/metrics")


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Health check endpoint with per-subsystem status."""
    from app.models.project import Project
    from app.models.snippet import Snippet
    from app.models.todo import Todo
    from app.models.wiki_page import WikiPage

    timestamp = datetime.now(UTC).isoformat()

    # Probe database connectivity
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "subsystems": {},
                "timestamp": timestamp,
            },
        )

    # Probe each subsystem table
    subsystem_models: dict[str, type] = {
        "tasks": Todo,
        "projects": Project,
        "wiki": WikiPage,
        "snippets": Snippet,
    }
    subsystems: dict[str, dict[str, str]] = {}
    all_healthy = True

    for name, model in subsystem_models.items():
        try:
            await db.execute(select(model.id).limit(1))
            subsystems[name] = {"status": "healthy"}
        except Exception:
            await db.rollback()
            subsystems[name] = {"status": "unhealthy"}
            all_healthy = False

    status = "healthy" if all_healthy else "degraded"
    return JSONResponse(
        status_code=200,
        content={
            "status": status,
            "subsystems": subsystems,
            "timestamp": timestamp,
        },
    )
