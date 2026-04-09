"""
Tests for TRIBE v2 and MiroFish HTTP clients.

Uses httpx.MockTransport to simulate downstream service responses without
any network calls. Each test builds a fresh httpx.AsyncClient with a
custom transport handler that returns predetermined responses.
"""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from orchestrator.clients.mirofish_client import (
    MirofishClient,
    POLL_INITIAL_INTERVAL,
)
from orchestrator.clients.tribe_client import TribeClient, TRIBE_SCORE_DIMENSIONS


# ---------------------------------------------------------------------------
# Helpers — mock transport factories
# ---------------------------------------------------------------------------


def _make_tribe_client(handler, *, max_retries: int = 0) -> TribeClient:
    """Build a TribeClient backed by a mock transport handler.

    max_retries defaults to 0 for fast tests (no retry backoff delays).
    """
    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(
        transport=transport, base_url="http://localhost:8001"
    )
    return TribeClient(async_client, max_retries=max_retries, retry_backoff_base=0.0)


def _tribe_health_ok_handler(request: httpx.Request) -> httpx.Response:
    """Respond to /api/health with a healthy status."""
    return httpx.Response(
        200,
        json={
            "status": "ok",
            "model_loaded": True,
            "gpu_available": True,
            "model_name": "meta-llama/Llama-3.2-3B",
        },
    )


def _tribe_health_degraded_handler(request: httpx.Request) -> httpx.Response:
    """Respond to /api/health with a degraded status."""
    return httpx.Response(200, json={"status": "degraded", "model_loaded": False})


MOCK_TRIBE_SCORES = {
    "attention_capture": 72.0,
    "emotional_resonance": 65.0,
    "memory_encoding": 58.0,
    "reward_response": 70.0,
    "threat_detection": 15.0,
    "cognitive_load": 42.0,
    "social_relevance": 68.0,
    "inference_time_ms": 1234.56,  # metadata — should be excluded
}


def _tribe_score_success_handler(request: httpx.Request) -> httpx.Response:
    """Respond to /api/score with a full set of scores + metadata."""
    return httpx.Response(200, json=MOCK_TRIBE_SCORES)


def _tribe_score_timeout_handler(request: httpx.Request) -> httpx.Response:
    """Simulate a timeout on /api/score."""
    raise httpx.TimeoutException("Connection timed out")


def _tribe_score_server_error_handler(request: httpx.Request) -> httpx.Response:
    """Simulate a 500 Internal Server Error on /api/score."""
    return httpx.Response(500, text="Internal Server Error")


def _tribe_connection_error_handler(request: httpx.Request) -> httpx.Response:
    """Simulate a connection error (service down)."""
    raise httpx.ConnectError("Connection refused")


# ---------------------------------------------------------------------------
# TRIBE client tests
# ---------------------------------------------------------------------------


class TestTribeHealthCheck:
    @pytest.mark.asyncio
    async def test_tribe_health_check_ok(self):
        """Health check returns True when TRIBE reports status 'ok'."""
        client = _make_tribe_client(_tribe_health_ok_handler)
        result = await client.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_tribe_health_check_degraded(self):
        """Health check returns False when TRIBE reports status 'degraded'."""
        client = _make_tribe_client(_tribe_health_degraded_handler)
        result = await client.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_tribe_health_check_down(self):
        """Health check returns False when TRIBE is unreachable."""
        client = _make_tribe_client(_tribe_connection_error_handler)
        result = await client.health_check()
        assert result is False


class TestTribeScoreText:
    @pytest.mark.asyncio
    async def test_tribe_score_text_success(self):
        """Score returns dict with exactly 7 dimensions (no inference_time_ms)."""
        client = _make_tribe_client(_tribe_score_success_handler)
        result = await client.score_text("Test content for scoring")

        assert result is not None
        assert isinstance(result, dict)
        assert len(result) == 8  # 7 dimensions + is_pseudo_score
        # Verify all 7 dimensions present
        for dim in TRIBE_SCORE_DIMENSIONS:
            assert dim in result
            assert isinstance(result[dim], float)
        # Verify is_pseudo_score flag present
        assert "is_pseudo_score" in result
        assert isinstance(result["is_pseudo_score"], bool)
        # Verify metadata excluded
        assert "inference_time_ms" not in result
        # Verify specific values
        assert result["attention_capture"] == 72.0
        assert result["social_relevance"] == 68.0

    @pytest.mark.asyncio
    async def test_tribe_score_text_timeout(self):
        """Score returns None when request times out."""
        client = _make_tribe_client(_tribe_score_timeout_handler)
        result = await client.score_text("Test content")
        assert result is None

    @pytest.mark.asyncio
    async def test_tribe_score_text_server_error(self):
        """Score returns None when TRIBE returns 500."""
        client = _make_tribe_client(_tribe_score_server_error_handler)
        result = await client.score_text("Test content")
        assert result is None

    @pytest.mark.asyncio
    async def test_tribe_score_text_connection_error(self):
        """Score returns None when TRIBE is unreachable."""
        client = _make_tribe_client(_tribe_connection_error_handler)
        result = await client.score_text("Test content")
        assert result is None

    @pytest.mark.asyncio
    async def test_tribe_score_text_missing_dimensions(self):
        """Score returns None when TRIBE response has fewer than 7 dimensions."""

        def handler(request: httpx.Request) -> httpx.Response:
            # Only 3 dimensions instead of 7
            return httpx.Response(
                200,
                json={
                    "attention_capture": 72.0,
                    "emotional_resonance": 65.0,
                    "memory_encoding": 58.0,
                },
            )

        client = _make_tribe_client(handler)
        result = await client.score_text("Test content")
        assert result is None


# ---------------------------------------------------------------------------
# MiroFish client helpers
# ---------------------------------------------------------------------------

MOCK_PROJECT_ID = "proj-abc123"
MOCK_TASK_ID = "task-def456"
MOCK_SIM_ID = "sim-ghi789"
MOCK_PREPARE_TASK_ID = "prep-jkl012"


def _make_mirofish_client(handler) -> MirofishClient:
    """Build a MirofishClient backed by a mock transport handler."""
    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(
        transport=transport, base_url="http://localhost:5000"
    )
    return MirofishClient(async_client)


def _mirofish_health_ok_handler(request: httpx.Request) -> httpx.Response:
    """Respond to /health with 200 OK."""
    return httpx.Response(200, text="OK")


def _mirofish_connection_error_handler(request: httpx.Request) -> httpx.Response:
    """Simulate a connection error (service down)."""
    raise httpx.ConnectError("Connection refused")


def _mirofish_full_workflow_handler(request: httpx.Request) -> httpx.Response:
    """
    Route-based mock handler that simulates the entire MiroFish workflow.
    All endpoints return successful responses immediately.
    """
    url = str(request.url)
    method = request.method

    # Step 1: Ontology generation
    if "/api/graph/ontology/generate" in url and method == "POST":
        # Verify multipart form data
        content_type = request.headers.get("content-type", "")
        assert "multipart/form-data" in content_type, (
            f"Expected multipart/form-data, got {content_type}"
        )
        return httpx.Response(
            200,
            json={"project_id": MOCK_PROJECT_ID, "ontology": {"nodes": [], "edges": []}},
        )

    # Step 2: Graph build
    if "/api/graph/build" in url and method == "POST":
        return httpx.Response(200, json={"task_id": MOCK_TASK_ID})

    # Step 2b: Graph build poll
    if f"/api/graph/task/{MOCK_TASK_ID}" in url and method == "GET":
        return httpx.Response(200, json={"status": "completed", "progress": 100})

    # Step 3: Create simulation
    if "/api/simulation/create" in url and method == "POST":
        return httpx.Response(200, json={"simulation_id": MOCK_SIM_ID})

    # Step 4: Prepare simulation
    if "/api/simulation/prepare/status" in url and method == "POST":
        return httpx.Response(200, json={"status": "completed", "ready": True})

    if "/api/simulation/prepare" in url and method == "POST":
        return httpx.Response(200, json={"task_id": MOCK_PREPARE_TASK_ID})

    # Step 5: Start simulation
    if "/api/simulation/start" in url and method == "POST":
        return httpx.Response(200, json={"runner_status": "running"})

    # Step 5b: Run status poll
    if f"/api/simulation/{MOCK_SIM_ID}/run-status" in url and method == "GET":
        return httpx.Response(
            200,
            json={
                "runner_status": "completed",
                "current_round": 30,
                "total_rounds": 30,
                "progress_percent": 100,
            },
        )

    # Step 6: Extract results
    if f"/api/simulation/{MOCK_SIM_ID}/posts" in url:
        return httpx.Response(200, json=[{"id": 1, "content": "test post"}])
    if f"/api/simulation/{MOCK_SIM_ID}/actions" in url:
        return httpx.Response(200, json=[{"id": 1, "type": "share"}])
    if f"/api/simulation/{MOCK_SIM_ID}/timeline" in url:
        return httpx.Response(200, json=[{"round": 1, "events": 5}])
    if f"/api/simulation/{MOCK_SIM_ID}/agent-stats" in url:
        return httpx.Response(200, json=[{"agent_id": "a1", "posts": 3}])

    # Fallback
    return httpx.Response(404, text="Not Found")


def _mirofish_graph_build_fails_handler(request: httpx.Request) -> httpx.Response:
    """
    Mock handler where ontology succeeds but graph build task fails.
    """
    url = str(request.url)
    method = request.method

    if "/api/graph/ontology/generate" in url and method == "POST":
        return httpx.Response(200, json={"project_id": MOCK_PROJECT_ID})

    if "/api/graph/build" in url and method == "POST":
        return httpx.Response(200, json={"task_id": MOCK_TASK_ID})

    if f"/api/graph/task/{MOCK_TASK_ID}" in url and method == "GET":
        return httpx.Response(
            200, json={"status": "failed", "error": "Graph construction error"}
        )

    return httpx.Response(404, text="Not Found")


def _mirofish_poll_never_completes_handler(request: httpx.Request) -> httpx.Response:
    """
    Mock handler where ontology succeeds but graph build task never completes.
    Always returns 'processing' status.
    """
    url = str(request.url)
    method = request.method

    if "/api/graph/ontology/generate" in url and method == "POST":
        return httpx.Response(200, json={"project_id": MOCK_PROJECT_ID})

    if "/api/graph/build" in url and method == "POST":
        return httpx.Response(200, json={"task_id": MOCK_TASK_ID})

    if f"/api/graph/task/{MOCK_TASK_ID}" in url and method == "GET":
        return httpx.Response(
            200, json={"status": "processing", "progress": 42}
        )

    return httpx.Response(404, text="Not Found")


# ---------------------------------------------------------------------------
# MiroFish client tests
# ---------------------------------------------------------------------------


class TestMirofishHealthCheck:
    @pytest.mark.asyncio
    async def test_mirofish_health_check_ok(self):
        """Health check returns True when MiroFish and LiteLLM are healthy."""
        client = _make_mirofish_client(_mirofish_health_ok_handler)

        # Mock the LiteLLM check (uses a separate httpx.AsyncClient internally)
        mock_llm_response = httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hi"}}]},
        )
        with patch("orchestrator.clients.mirofish_client.httpx.AsyncClient") as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.post = AsyncMock(return_value=mock_llm_response)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await client.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_mirofish_health_check_down(self):
        """Health check returns False when MiroFish is unreachable."""
        client = _make_mirofish_client(_mirofish_connection_error_handler)
        result = await client.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_mirofish_health_check_llm_401(self):
        """Health check returns False when LiteLLM returns 401 (expired key)."""
        client = _make_mirofish_client(_mirofish_health_ok_handler)

        mock_llm_response = httpx.Response(401, json={"error": "unauthorized"})
        with patch("orchestrator.clients.mirofish_client.httpx.AsyncClient") as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.post = AsyncMock(return_value=mock_llm_response)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await client.health_check()
        assert result is False


class TestMirofishOntologyGeneration:
    @pytest.mark.asyncio
    async def test_mirofish_generate_ontology(self):
        """Ontology generation sends multipart/form-data with files key."""

        captured_request = {}

        def capture_handler(request: httpx.Request) -> httpx.Response:
            captured_request["content_type"] = request.headers.get("content-type", "")
            captured_request["method"] = request.method
            captured_request["url"] = str(request.url)
            return httpx.Response(
                200, json={"project_id": MOCK_PROJECT_ID, "ontology": {}}
            )

        client = _make_mirofish_client(capture_handler)
        project_id = await client._generate_ontology(
            content="Test content for ontology",
            requirement="Simulate social reaction to product launch",
            project_name="test-project",
        )

        assert project_id == MOCK_PROJECT_ID
        assert "multipart/form-data" in captured_request["content_type"]
        assert captured_request["method"] == "POST"


class TestMirofishRunSimulation:
    @pytest.mark.asyncio
    async def test_mirofish_run_simulation_success(self):
        """Full workflow returns dict with posts, actions, timeline, agent_stats."""
        client = _make_mirofish_client(_mirofish_full_workflow_handler)
        result = await client.run_simulation(
            content="Test product launch announcement",
            simulation_requirement="Simulate social reaction to new product",
            project_name="test-campaign",
            max_rounds=30,
        )

        assert result is not None
        assert isinstance(result, dict)
        assert result["simulation_id"] == MOCK_SIM_ID
        assert "posts" in result
        assert "actions" in result
        assert "timeline" in result
        assert "agent_stats" in result
        # Verify actual data came through
        assert len(result["posts"]) > 0
        assert len(result["actions"]) > 0

    @pytest.mark.asyncio
    async def test_mirofish_run_simulation_graph_build_fails(self):
        """Returns None when graph build task reports failure."""
        client = _make_mirofish_client(_mirofish_graph_build_fails_handler)
        result = await client.run_simulation(
            content="Test content",
            simulation_requirement="Test requirement",
            project_name="test",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_mirofish_poll_timeout(self):
        """Returns None when task polling times out (never reaches 'completed')."""
        import orchestrator.clients.mirofish_client as mf_mod

        # Temporarily override timeout to make test fast
        original_timeout = mf_mod.GRAPH_BUILD_TIMEOUT
        original_interval = mf_mod.POLL_INITIAL_INTERVAL
        mf_mod.GRAPH_BUILD_TIMEOUT = 0.5  # half second
        mf_mod.POLL_INITIAL_INTERVAL = 0.1  # 100ms

        try:
            client = _make_mirofish_client(_mirofish_poll_never_completes_handler)
            result = await client.run_simulation(
                content="Test content",
                simulation_requirement="Test requirement",
                project_name="test",
            )
            assert result is None
        finally:
            # Restore original values
            mf_mod.GRAPH_BUILD_TIMEOUT = original_timeout
            mf_mod.POLL_INITIAL_INTERVAL = original_interval

    @pytest.mark.asyncio
    async def test_mirofish_run_simulation_connection_error(self):
        """Returns None when MiroFish is unreachable."""
        client = _make_mirofish_client(_mirofish_connection_error_handler)
        result = await client.run_simulation(
            content="Test content",
            simulation_requirement="Test requirement",
            project_name="test",
        )
        assert result is None
