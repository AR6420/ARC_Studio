"""
Tests for health check and demographics API endpoints.

Uses httpx AsyncClient with ASGITransport against a test app with manually
initialized state. Mocks tribe_client and mirofish_client health_check methods
to simulate upstream service availability states.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import httpx
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from orchestrator.storage.database import Database
from orchestrator.storage.campaign_store import CampaignStore
from orchestrator.clients.tribe_client import TribeClient
from orchestrator.clients.mirofish_client import MirofishClient


def _create_test_app() -> FastAPI:
    """Create a test app without lifespan (state set up manually by fixture)."""
    from orchestrator.api.campaigns import router as campaigns_router
    from orchestrator.api.health import router as health_router

    application = FastAPI(
        title="Nexus Sim Orchestrator",
        version="0.1.0",
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


async def _make_client(
    tmp_path: Path,
    tribe_healthy: bool = True,
    mirofish_healthy: bool = True,
):
    """
    Create an async client with manually initialized state and
    configurable health check mocks.
    Returns (client, cleanup_fn) tuple -- caller must call cleanup.
    """
    db_path = str(tmp_path / "test_health.db")
    app = _create_test_app()

    db = Database(db_path)
    await db.connect()

    tribe_http = httpx.AsyncClient(base_url="http://localhost:8001")
    mirofish_http = httpx.AsyncClient(base_url="http://localhost:5000")

    tribe_client = TribeClient(tribe_http)
    mirofish_client = MirofishClient(mirofish_http)

    # Mock health_check methods
    tribe_client.health_check = AsyncMock(return_value=tribe_healthy)
    mirofish_client.health_check = AsyncMock(return_value=mirofish_healthy)

    app.state.db = db
    app.state.campaign_store = CampaignStore(db)
    app.state.tribe_client = tribe_client
    app.state.mirofish_client = mirofish_client
    app.state.claude_client = MagicMock()
    app.state.tribe_http = tribe_http
    app.state.mirofish_http = mirofish_http

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")

    async def cleanup():
        await client.aclose()
        await tribe_http.aclose()
        await mirofish_http.aclose()
        await db.close()

    return client, cleanup


@pytest.mark.asyncio
async def test_health_all_ok(tmp_path: Path):
    """When all services are healthy, response should show ok for everything."""
    client, cleanup = await _make_client(tmp_path, tribe_healthy=True, mirofish_healthy=True)
    try:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["orchestrator"] == "ok"
        assert data["tribe_scorer"]["status"] == "ok"
        assert data["mirofish"]["status"] == "ok"
        assert data["database"]["status"] == "ok"
        # Latency should be present for healthy services
        assert data["tribe_scorer"]["latency_ms"] is not None
        assert data["mirofish"]["latency_ms"] is not None
        assert data["database"]["latency_ms"] is not None
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_health_tribe_down(tmp_path: Path):
    """When TRIBE is down, tribe_scorer.status should be 'unavailable'."""
    client, cleanup = await _make_client(tmp_path, tribe_healthy=False, mirofish_healthy=True)
    try:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["orchestrator"] == "ok"
        assert data["tribe_scorer"]["status"] == "unavailable"
        assert data["tribe_scorer"]["latency_ms"] is None
        assert data["mirofish"]["status"] == "ok"
        assert data["database"]["status"] == "ok"
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_health_mirofish_down(tmp_path: Path):
    """When MiroFish is down, mirofish.status should be 'unavailable'."""
    client, cleanup = await _make_client(tmp_path, tribe_healthy=True, mirofish_healthy=False)
    try:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["orchestrator"] == "ok"
        assert data["tribe_scorer"]["status"] == "ok"
        assert data["mirofish"]["status"] == "unavailable"
        assert data["mirofish"]["latency_ms"] is None
        assert data["database"]["status"] == "ok"
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_demographics(tmp_path: Path):
    """GET /api/demographics should return 6 presets with key/label/description."""
    client, cleanup = await _make_client(tmp_path)
    try:
        response = await client.get("/api/demographics")
        assert response.status_code == 200
        data = response.json()
        assert data["supports_custom"] is True
        assert len(data["presets"]) == 6
        for preset in data["presets"]:
            assert "key" in preset
            assert "label" in preset
            assert "description" in preset
            assert len(preset["description"]) > 0
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_demographics_keys(tmp_path: Path):
    """Demographics should include all 6 expected preset keys."""
    client, cleanup = await _make_client(tmp_path)
    try:
        response = await client.get("/api/demographics")
        data = response.json()
        keys = {p["key"] for p in data["presets"]}
        expected_keys = {
            "tech_professionals",
            "enterprise_decision_makers",
            "general_consumer_us",
            "policy_aware_public",
            "healthcare_professionals",
            "gen_z_digital_natives",
        }
        assert keys == expected_keys
    finally:
        await cleanup()
