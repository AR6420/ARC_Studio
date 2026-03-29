"""
FastAPI application factory for the Nexus Sim Orchestrator.

Creates the app with lifespan resource management (database, HTTP clients),
CORS middleware for the Vite dev server, and router mounting.

Usage:
    # Via uvicorn (uses module-level app instance):
    uvicorn orchestrator.api:app --port 8000

    # Programmatic:
    from orchestrator.api import create_app
    app = create_app()
"""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from orchestrator.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage shared resources: database, HTTP clients, Claude client.
    Per FastAPI best practices: use lifespan instead of deprecated on_event.

    Imports are deferred to avoid circular imports (campaign_store -> schemas
    -> orchestrator.api package).
    """
    # Deferred imports to break circular dependency
    from orchestrator.storage.database import Database
    from orchestrator.storage.campaign_store import CampaignStore
    from orchestrator.clients.tribe_client import TribeClient
    from orchestrator.clients.mirofish_client import MirofishClient
    from orchestrator.clients.claude_client import ClaudeClient

    # Startup
    db = Database(str(settings.database_path_absolute))
    await db.connect()

    tribe_http = httpx.AsyncClient(base_url=settings.tribe_scorer_url, timeout=120.0)
    mirofish_http = httpx.AsyncClient(base_url=settings.mirofish_url, timeout=300.0)

    app.state.db = db
    app.state.campaign_store = CampaignStore(db)
    app.state.tribe_client = TribeClient(tribe_http)
    app.state.mirofish_client = MirofishClient(mirofish_http)
    app.state.claude_client = ClaudeClient()
    app.state.tribe_http = tribe_http
    app.state.mirofish_http = mirofish_http

    logger.info(
        "Orchestrator started — DB at %s, TRIBE at %s, MiroFish at %s",
        settings.database_path_absolute,
        settings.tribe_scorer_url,
        settings.mirofish_url,
    )

    yield

    # Shutdown
    await tribe_http.aclose()
    await mirofish_http.aclose()
    await db.close()
    logger.info("Orchestrator shutdown complete")


def create_app() -> FastAPI:
    """Factory function to create the FastAPI app."""
    from orchestrator.api.campaigns import router as campaigns_router
    from orchestrator.api.health import router as health_router

    application = FastAPI(
        title="Nexus Sim Orchestrator",
        description="Content optimization pipeline orchestrating TRIBE v2, MiroFish, and Claude",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS for Vite dev server (per ORCH-01)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routers
    application.include_router(campaigns_router, prefix="/api")
    application.include_router(health_router, prefix="/api")

    return application


# Module-level app instance for uvicorn
app = create_app()
