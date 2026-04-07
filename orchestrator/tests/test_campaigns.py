"""
Tests for campaign CRUD API endpoints.

Uses httpx AsyncClient with ASGITransport against a test app with temp DB.
The lifespan is managed manually since httpx ASGITransport does not trigger
ASGI lifespan events.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import httpx
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from orchestrator.storage.database import Database
from orchestrator.storage.campaign_store import CampaignStore
from orchestrator.clients.tribe_client import TribeClient
from orchestrator.clients.mirofish_client import MirofishClient


# Valid seed content (>= 100 chars)
VALID_SEED_CONTENT = (
    "This is a comprehensive product launch announcement for our new AI-powered "
    "content optimization platform that helps marketing teams create better content. "
    "It uses neural response prediction and social simulation to iteratively improve messaging."
)

VALID_CAMPAIGN_BODY = {
    "seed_content": VALID_SEED_CONTENT,
    "prediction_question": "How will tech professionals respond to this product launch?",
    "demographic": "tech_professionals",
    "agent_count": 40,
    "max_iterations": 4,
    "auto_start": False,
}


def _create_test_app() -> FastAPI:
    """Create a test app without lifespan (state set up manually by fixture)."""
    from orchestrator.api.campaigns import router as campaigns_router
    from orchestrator.api.health import router as health_router

    application = FastAPI(
        title="A.R.C Studio Orchestrator",
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


@pytest.fixture
async def client(tmp_path: Path):
    """Provide an async test client with manually initialized app state."""
    db_path = str(tmp_path / "test_campaigns.db")

    app = _create_test_app()

    # Manually set up app state (equivalent to lifespan startup)
    db = Database(db_path)
    await db.connect()

    tribe_http = httpx.AsyncClient(base_url="http://localhost:8001")
    mirofish_http = httpx.AsyncClient(base_url="http://localhost:5000")

    app.state.db = db
    app.state.campaign_store = CampaignStore(db)
    app.state.tribe_client = TribeClient(tribe_http)
    app.state.mirofish_client = MirofishClient(mirofish_http)
    app.state.claude_client = MagicMock()
    app.state.tribe_http = tribe_http
    app.state.mirofish_http = mirofish_http

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c

    # Teardown
    await tribe_http.aclose()
    await mirofish_http.aclose()
    await db.close()


@pytest.mark.asyncio
async def test_create_campaign(client: AsyncClient):
    """POST /api/campaigns with valid body should return 201 with id and status=pending."""
    response = await client.post("/api/campaigns", json=VALID_CAMPAIGN_BODY)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["status"] == "pending"
    assert data["seed_content"] == VALID_SEED_CONTENT
    assert data["prediction_question"] == VALID_CAMPAIGN_BODY["prediction_question"]
    assert data["demographic"] == "tech_professionals"
    assert data["agent_count"] == 40
    assert data["max_iterations"] == 4


@pytest.mark.asyncio
async def test_create_campaign_validation(client: AsyncClient):
    """POST with seed_content too short (<100 chars) should return 422."""
    body = {**VALID_CAMPAIGN_BODY, "seed_content": "Too short content"}
    response = await client.post("/api/campaigns", json=body)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_campaign(client: AsyncClient):
    """POST then GET /api/campaigns/{id} should return matching campaign."""
    # Create
    create_resp = await client.post("/api/campaigns", json=VALID_CAMPAIGN_BODY)
    assert create_resp.status_code == 201
    campaign_id = create_resp.json()["id"]

    # Get
    get_resp = await client.get(f"/api/campaigns/{campaign_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == campaign_id
    assert data["status"] == "pending"
    assert data["seed_content"] == VALID_SEED_CONTENT
    assert data["demographic"] == "tech_professionals"


@pytest.mark.asyncio
async def test_get_campaign_not_found(client: AsyncClient):
    """GET /api/campaigns/nonexistent should return 404."""
    response = await client.get("/api/campaigns/nonexistent-id-12345")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_campaigns(client: AsyncClient):
    """POST 2 campaigns, GET /api/campaigns should return total=2."""
    # Create two campaigns
    resp1 = await client.post("/api/campaigns", json=VALID_CAMPAIGN_BODY)
    assert resp1.status_code == 201

    body2 = {
        **VALID_CAMPAIGN_BODY,
        "prediction_question": "How will enterprise leaders respond to this launch?",
        "demographic": "enterprise_decision_makers",
    }
    resp2 = await client.post("/api/campaigns", json=body2)
    assert resp2.status_code == 201

    # List
    list_resp = await client.get("/api/campaigns")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 2
    assert len(data["campaigns"]) == 2


@pytest.mark.asyncio
async def test_delete_campaign(client: AsyncClient):
    """POST then DELETE should return 204, then GET should return 404."""
    # Create
    create_resp = await client.post("/api/campaigns", json=VALID_CAMPAIGN_BODY)
    assert create_resp.status_code == 201
    campaign_id = create_resp.json()["id"]

    # Delete
    delete_resp = await client.delete(f"/api/campaigns/{campaign_id}")
    assert delete_resp.status_code == 204

    # Verify deleted
    get_resp = await client.get(f"/api/campaigns/{campaign_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_campaign_not_found(client: AsyncClient):
    """DELETE /api/campaigns/nonexistent should return 404."""
    response = await client.delete("/api/campaigns/nonexistent-id-12345")
    assert response.status_code == 404
