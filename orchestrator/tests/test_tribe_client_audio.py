"""
Unit tests for ``TribeClient.score_audio`` (Phase 2 A.1).

Mocks the TRIBE v2 scorer via ``httpx.MockTransport`` — no network or GPU
required. Mirrors the style of ``test_clients.py`` for the text path.
"""

from __future__ import annotations

import httpx
import pytest

from orchestrator.clients.tribe_client import (
    SCORE_AUDIO_TIMEOUT,
    TRIBE_SCORE_DIMENSIONS,
    TribeClient,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(handler, *, max_retries: int = 0) -> TribeClient:
    """Build a TribeClient backed by a mock transport.

    ``max_retries=0`` keeps tests fast (no backoff sleeps) unless the test
    explicitly wants to exercise the retry loop.
    """
    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(
        transport=transport, base_url="http://localhost:8001"
    )
    return TribeClient(async_client, max_retries=max_retries, retry_backoff_base=0.0)


_MOCK_AUDIO_RESPONSE = {
    "attention_capture": 72.0,
    "emotional_resonance": 64.0,
    "memory_encoding": 58.0,
    "reward_response": 70.0,
    "threat_detection": 12.0,
    "cognitive_load": 44.0,
    "social_relevance": 66.0,
    "inference_time_ms": 4321.0,
    "duration_seconds": 42.75,
    "is_pseudo_score": False,
}


def _audio_success_handler(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/api/score_audio"
    assert request.method == "POST"
    return httpx.Response(200, json=_MOCK_AUDIO_RESPONSE)


def _audio_pseudo_handler(request: httpx.Request) -> httpx.Response:
    payload = dict(_MOCK_AUDIO_RESPONSE)
    payload["is_pseudo_score"] = True
    payload["pseudo_reason"] = "RuntimeError: CUDA out of memory"
    return httpx.Response(200, json=payload)


def _audio_500_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, json={"detail": "inference crashed"})


def _audio_bad_request_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(400, json={"detail": "audio too long: 75.00s > 60.00s"})


def _audio_short_response_handler(request: httpx.Request) -> httpx.Response:
    # Only 5 of 7 dimensions — client must treat as a parse failure.
    partial = {
        "attention_capture": 50.0,
        "emotional_resonance": 50.0,
        "memory_encoding": 50.0,
        "reward_response": 50.0,
        "threat_detection": 50.0,
        "inference_time_ms": 1000.0,
        "duration_seconds": 30.0,
        "is_pseudo_score": False,
    }
    return httpx.Response(200, json=partial)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_audio_happy_path_returns_seven_dims():
    """200 with full 7 dims → dict with every dimension + is_pseudo_score=False."""
    client = _make_client(_audio_success_handler)
    result = await client.score_audio("/abs/path/to/clip.wav")

    assert result is not None
    for dim in TRIBE_SCORE_DIMENSIONS:
        assert dim in result
        assert isinstance(result[dim], float)
        assert 0.0 <= result[dim] <= 100.0
    assert result["is_pseudo_score"] is False
    # Metadata must NOT leak into the score dict (client filters by dimension list).
    assert "inference_time_ms" not in result
    assert "duration_seconds" not in result


@pytest.mark.asyncio
async def test_score_audio_pseudo_fallback_passes_through():
    """Server-side mid-inference failure surfaces as is_pseudo_score=True."""
    client = _make_client(_audio_pseudo_handler)
    result = await client.score_audio("/abs/path/to/clip.mp3")

    assert result is not None
    assert result["is_pseudo_score"] is True
    # All 7 dims still present — downstream normalizer/composite still runs.
    for dim in TRIBE_SCORE_DIMENSIONS:
        assert dim in result


@pytest.mark.asyncio
async def test_score_audio_500_returns_none():
    """HTTP 5xx after all retries → None (graceful degradation)."""
    client = _make_client(_audio_500_handler, max_retries=1)
    result = await client.score_audio("/abs/path/to/clip.flac")
    assert result is None


@pytest.mark.asyncio
async def test_score_audio_client_error_returns_none():
    """HTTP 400 (e.g., validation failure) → None, no retry needed."""
    client = _make_client(_audio_bad_request_handler, max_retries=2)
    result = await client.score_audio("/abs/too_long.wav")
    assert result is None


@pytest.mark.asyncio
async def test_score_audio_missing_dimensions_returns_none():
    """If the server response lacks any of the 7 dims, client returns None."""
    client = _make_client(_audio_short_response_handler)
    result = await client.score_audio("/abs/path/to/clip.ogg")
    assert result is None


@pytest.mark.asyncio
async def test_score_audio_posts_to_correct_endpoint_with_payload():
    """Request shape: POST /api/score_audio with {audio_path: ...}."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        import json

        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=_MOCK_AUDIO_RESPONSE)

    client = _make_client(handler)
    await client.score_audio("/abs/clip.wav")

    assert captured["method"] == "POST"
    assert captured["path"] == "/api/score_audio"
    assert captured["body"] == {"audio_path": "/abs/clip.wav"}


def test_score_audio_timeout_constant_is_module_level():
    """Contract 2: SCORE_AUDIO_TIMEOUT must exist alongside SCORE_TIMEOUT."""
    from orchestrator.clients import tribe_client as tc

    assert hasattr(tc, "SCORE_AUDIO_TIMEOUT")
    assert hasattr(tc, "SCORE_TIMEOUT")
    assert SCORE_AUDIO_TIMEOUT == 1800.0
