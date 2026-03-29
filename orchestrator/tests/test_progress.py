"""
Tests for the progress SSE endpoint, estimate endpoint, and queue management helpers.

Tests cover:
- POST /api/estimate: default and custom configurations, validation
- GET /api/campaigns/{id}/progress: 404 on missing queue, SSE event delivery
- get_or_create_queue: idempotent queue creation
- cleanup_queue: queue removal from app.state
"""

import asyncio
import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from orchestrator.api.progress import (
    router,
    get_or_create_queue,
    cleanup_queue,
)


def _create_progress_test_app() -> FastAPI:
    """Create a minimal FastAPI app with just the progress router for testing."""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.progress_queues = {}
    return app


@pytest.fixture
def progress_app() -> FastAPI:
    """Provide a fresh test app for each test."""
    return _create_progress_test_app()


@pytest.fixture
async def progress_client(progress_app: FastAPI):
    """Provide an async HTTP client connected to the progress test app."""
    transport = ASGITransport(app=progress_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# ── Estimate endpoint tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_estimate_endpoint_default(progress_client: AsyncClient):
    """POST /api/estimate with default 40 agents, 4 iterations -> 12.0 minutes."""
    response = await progress_client.post(
        "/api/estimate",
        json={"agent_count": 40, "max_iterations": 4},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["estimated_minutes"] == 12.0
    assert data["agent_count"] == 40
    assert data["max_iterations"] == 4
    assert "formula" in data


@pytest.mark.asyncio
async def test_estimate_endpoint_custom(progress_client: AsyncClient):
    """POST /api/estimate with 80 agents, 2 iterations -> 12.0 minutes."""
    response = await progress_client.post(
        "/api/estimate",
        json={"agent_count": 80, "max_iterations": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["estimated_minutes"] == 12.0
    assert data["agent_count"] == 80
    assert data["max_iterations"] == 2


@pytest.mark.asyncio
async def test_estimate_endpoint_validation(progress_client: AsyncClient):
    """POST /api/estimate with agent_count=10 -> 422 validation error."""
    response = await progress_client.post(
        "/api/estimate",
        json={"agent_count": 10, "max_iterations": 4},
    )
    assert response.status_code == 422


# ── SSE endpoint tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sse_no_active_queue(progress_client: AsyncClient):
    """GET /api/campaigns/nonexistent/progress -> 404."""
    response = await progress_client.get("/api/campaigns/nonexistent/progress")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sse_delivers_events(progress_app: FastAPI):
    """SSE endpoint delivers events from queue and closes on campaign_complete."""
    campaign_id = "test-campaign-001"

    # Pre-create queue and push events
    queue = get_or_create_queue(progress_app, campaign_id)
    await queue.put({
        "event": "iteration_start",
        "campaign_id": campaign_id,
        "iteration": 1,
        "max_iterations": 4,
    })
    await queue.put({
        "event": "campaign_complete",
        "campaign_id": campaign_id,
        "iteration": 1,
        "max_iterations": 4,
    })

    transport = ASGITransport(app=progress_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Use stream to read SSE events
        async with client.stream(
            "GET", f"/api/campaigns/{campaign_id}/progress"
        ) as response:
            assert response.status_code == 200
            body = ""
            async for chunk in response.aiter_text():
                body += chunk
                # Stop reading after we get campaign_complete
                if "campaign_complete" in body:
                    break

    # Verify we received both events in the SSE stream
    assert "iteration_start" in body
    assert "campaign_complete" in body


# ── Queue management tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_or_create_queue(progress_app: FastAPI):
    """get_or_create_queue returns the same queue on repeated calls."""
    queue1 = get_or_create_queue(progress_app, "camp-1")
    queue2 = get_or_create_queue(progress_app, "camp-1")
    assert queue1 is queue2


@pytest.mark.asyncio
async def test_cleanup_queue(progress_app: FastAPI):
    """cleanup_queue removes the queue from app.state."""
    get_or_create_queue(progress_app, "camp-1")
    assert "camp-1" in progress_app.state.progress_queues
    cleanup_queue(progress_app, "camp-1")
    assert "camp-1" not in progress_app.state.progress_queues
