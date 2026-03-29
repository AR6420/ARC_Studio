"""
Tests for TRIBE v2 and MiroFish HTTP clients.

Uses httpx.MockTransport to simulate downstream service responses without
any network calls. Each test builds a fresh httpx.AsyncClient with a
custom transport handler that returns predetermined responses.
"""

import httpx
import pytest

from orchestrator.clients.tribe_client import TribeClient, TRIBE_SCORE_DIMENSIONS


# ---------------------------------------------------------------------------
# Helpers — mock transport factories
# ---------------------------------------------------------------------------


def _make_tribe_client(handler) -> TribeClient:
    """Build a TribeClient backed by a mock transport handler."""
    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(
        transport=transport, base_url="http://localhost:8001"
    )
    return TribeClient(async_client)


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
        assert len(result) == 7
        # Verify all 7 dimensions present
        for dim in TRIBE_SCORE_DIMENSIONS:
            assert dim in result
            assert isinstance(result[dim], float)
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
