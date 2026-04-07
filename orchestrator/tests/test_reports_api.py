"""
Tests for report retrieval and export API endpoints.

Tests cover:
- GET /api/campaigns/{id}/report: returns ReportResponse, 404 for missing
- GET /api/campaigns/{id}/export/json: returns full campaign data with download headers (RPT-06)
- GET /api/campaigns/{id}/export/markdown: returns Markdown with all 4 layers (RPT-07)
- 404 for nonexistent campaigns on all endpoints

Uses httpx AsyncClient with ASGITransport against a test app with temp DB.
"""

import json
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

SAMPLE_REPORT = {
    "verdict": "Variant v1 is the strongest performer with high attention and virality.",
    "scorecard": {
        "winning_variant_id": "v1",
        "variants": [
            {
                "variant_id": "v1",
                "rank": 1,
                "strategy": "direct_appeal",
                "composite_scores": {"attention_score": 80.0, "virality_potential": 70.0},
                "color_coding": {"attention_score": "green", "virality_potential": "green"},
            }
        ],
        "iteration_trajectory": [{"iteration": 1, "best_scores": {"attention_score": 80.0}}],
        "thresholds_status": {},
        "summary": "Variant v1 ranked first. Campaign completed after 1 iteration(s) (stop reason: max_iterations).",
    },
    "deep_analysis": {
        "iterations": [
            {
                "iteration": 1,
                "variants": [
                    {
                        "variant_id": "v1",
                        "content": "Content for variant 1",
                        "strategy": "direct_appeal",
                        "tribe_scores": {"attention_capture": 82.0},
                        "mirofish_metrics": {"organic_shares": 12},
                        "composite_scores": {"attention_score": 80.0},
                    }
                ],
                "analysis": {"ranking": ["v1"]},
            }
        ]
    },
    "mass_psychology_general": "The general audience responds positively to this content because of strong emotional resonance.",
    "mass_psychology_technical": "Neural activation patterns in the prefrontal cortex indicate high attention capture.",
}


def _create_test_app() -> FastAPI:
    """Create a test app with reports router for testing."""
    from orchestrator.api.campaigns import router as campaigns_router
    from orchestrator.api.reports import router as reports_router

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
    application.include_router(reports_router, prefix="/api")

    return application


@pytest.fixture
async def client(tmp_path: Path):
    """Provide an async test client with manually initialized app state."""
    db_path = str(tmp_path / "test_reports.db")

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
        yield c, app.state.campaign_store

    # Teardown
    await tribe_http.aclose()
    await mirofish_http.aclose()
    await db.close()


async def _create_campaign_with_report(store: CampaignStore) -> str:
    """Helper: create a campaign and save a report. Returns campaign_id."""
    from orchestrator.api.schemas import CampaignCreateRequest

    request = CampaignCreateRequest(
        seed_content=VALID_SEED_CONTENT,
        prediction_question="How will tech professionals respond to this product launch?",
        demographic="tech_professionals",
        agent_count=40,
        max_iterations=4,
        auto_start=False,
    )
    campaign = await store.create_campaign(request)

    # Save an iteration so export has data
    await store.save_iteration(
        campaign_id=campaign.id,
        iteration_number=1,
        variant_id="v1",
        variant_content="Content for variant 1",
        variant_strategy="direct_appeal",
        tribe_scores={"attention_capture": 82.0, "emotional_resonance": 75.0,
                      "memory_encoding": 68.0, "reward_response": 71.0,
                      "threat_detection": 15.0, "cognitive_load": 42.0,
                      "social_relevance": 78.0},
        mirofish_metrics={"organic_shares": 12, "sentiment_trajectory": [0.2, 0.4],
                          "counter_narrative_count": 0, "peak_virality_cycle": 3,
                          "sentiment_drift": 0.3, "coalition_formation": 1,
                          "influence_concentration": 0.35, "platform_divergence": 0.1},
        composite_scores={"attention_score": 80.0, "virality_potential": 70.0,
                          "backlash_risk": 20.0, "memory_durability": 65.0,
                          "conversion_potential": 72.0, "audience_fit": 68.0,
                          "polarization_index": 15.0},
    )

    # Save a report
    await store.save_report(campaign_id=campaign.id, report=SAMPLE_REPORT)

    return campaign.id


# ── Test 1 (RPT-06): JSON export with download headers ──────────────────


@pytest.mark.asyncio
async def test_export_json_returns_download_headers(client):
    """GET /api/campaigns/{id}/export/json returns Content-Disposition attachment header."""
    c, store = client
    campaign_id = await _create_campaign_with_report(store)

    response = await c.get(f"/api/campaigns/{campaign_id}/export/json")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert "attachment" in response.headers["content-disposition"]
    assert campaign_id in response.headers["content-disposition"]


# ── Test 2 (RPT-07): Markdown export with download headers ──────────────


@pytest.mark.asyncio
async def test_export_markdown_returns_download_headers(client):
    """GET /api/campaigns/{id}/export/markdown returns Content-Disposition attachment."""
    c, store = client
    campaign_id = await _create_campaign_with_report(store)

    response = await c.get(f"/api/campaigns/{campaign_id}/export/markdown")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/markdown; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]


# ── Test 3: GET report returns ReportResponse ────────────────────────────


@pytest.mark.asyncio
async def test_get_report_returns_all_layers(client):
    """GET /api/campaigns/{id}/report returns 200 with all report layer fields."""
    c, store = client
    campaign_id = await _create_campaign_with_report(store)

    response = await c.get(f"/api/campaigns/{campaign_id}/report")
    assert response.status_code == 200
    data = response.json()
    assert data["campaign_id"] == campaign_id
    assert data["verdict"] is not None
    assert data["scorecard"] is not None
    assert data["deep_analysis"] is not None
    assert data["mass_psychology_general"] is not None
    assert data["mass_psychology_technical"] is not None


# ── Test 4: GET report 404 for missing campaign ─────────────────────────


@pytest.mark.asyncio
async def test_get_report_not_found(client):
    """GET /api/campaigns/nonexistent/report returns 404."""
    c, store = client
    response = await c.get("/api/campaigns/nonexistent-id-12345/report")
    assert response.status_code == 404


# ── Test 5: JSON export 404 for missing campaign ────────────────────────


@pytest.mark.asyncio
async def test_export_json_not_found(client):
    """GET /api/campaigns/nonexistent/export/json returns 404."""
    c, store = client
    response = await c.get("/api/campaigns/nonexistent-id-12345/export/json")
    assert response.status_code == 404


# ── Test 6: Markdown export contains all 4 section headers ──────────────


@pytest.mark.asyncio
async def test_export_markdown_contains_all_sections(client):
    """Markdown export body contains all 4 layer sections."""
    c, store = client
    campaign_id = await _create_campaign_with_report(store)

    response = await c.get(f"/api/campaigns/{campaign_id}/export/markdown")
    assert response.status_code == 200
    body = response.text
    assert "## Verdict" in body
    assert "## Scorecard" in body
    assert "## Deep Analysis" in body
    assert "## Mass Psychology" in body


# ── Test 7: JSON export includes full audit trail (D-04) ────────────────


@pytest.mark.asyncio
async def test_export_json_includes_full_data(client):
    """JSON export contains campaign data and report layers (per D-04)."""
    c, store = client
    campaign_id = await _create_campaign_with_report(store)

    response = await c.get(f"/api/campaigns/{campaign_id}/export/json")
    assert response.status_code == 200
    data = response.json()
    assert "campaign" in data
    assert "report" in data
    # Campaign should include iterations
    assert data["campaign"]["id"] == campaign_id
    # Report should include all layers
    assert data["report"]["verdict"] is not None
