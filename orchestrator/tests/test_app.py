"""
Tests for the FastAPI application factory, CORS, and OpenAPI configuration.

Uses httpx AsyncClient with ASGITransport to test the app with a temporary
database, avoiding external service dependencies.
"""

import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from orchestrator.storage.database import Database
from orchestrator.storage.campaign_store import CampaignStore
from orchestrator.clients.tribe_client import TribeClient
from orchestrator.clients.mirofish_client import MirofishClient


def _create_test_app(tmp_db_path: str) -> FastAPI:
    """
    Create a FastAPI test app with a temporary database and mock external clients.
    Uses a custom lifespan that avoids connecting to real services.
    """

    @asynccontextmanager
    async def test_lifespan(app: FastAPI):
        db = Database(tmp_db_path)
        await db.connect()

        # Use mock HTTP clients -- we don't want real connections in tests
        tribe_http = httpx.AsyncClient(base_url="http://localhost:8001")
        mirofish_http = httpx.AsyncClient(base_url="http://localhost:5000")

        app.state.db = db
        app.state.campaign_store = CampaignStore(db)
        app.state.tribe_client = TribeClient(tribe_http)
        app.state.mirofish_client = MirofishClient(mirofish_http)
        app.state.claude_client = MagicMock()
        app.state.tribe_http = tribe_http
        app.state.mirofish_http = mirofish_http

        yield

        await tribe_http.aclose()
        await mirofish_http.aclose()
        await db.close()

    from orchestrator.api.campaigns import router as campaigns_router
    from orchestrator.api.health import router as health_router

    application = FastAPI(
        title="A.R.C Studio Orchestrator",
        description="Content optimization pipeline orchestrating TRIBE v2, MiroFish, and Claude",
        version="0.1.0",
        lifespan=test_lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(campaigns_router, prefix="/api")
    application.include_router(health_router, prefix="/api")

    return application


@pytest.fixture
async def test_client(tmp_path: Path):
    """Provide an async test client connected to a test app with temp DB."""
    db_path = str(tmp_path / "test_app.db")
    app = _create_test_app(db_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_app_cors_headers(test_client: AsyncClient):
    """CORS headers should be set for the Vite dev server origin."""
    response = await test_client.options(
        "/api/campaigns",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert "http://localhost:5173" in response.headers.get(
        "access-control-allow-origin", ""
    )


@pytest.mark.asyncio
async def test_app_openapi_docs(test_client: AsyncClient):
    """OpenAPI docs endpoint should be accessible."""
    response = await test_client.get("/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_app_title(test_client: AsyncClient):
    """OpenAPI schema should have the correct app title."""
    response = await test_client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "A.R.C Studio Orchestrator"
    assert data["info"]["version"] == "0.1.0"
