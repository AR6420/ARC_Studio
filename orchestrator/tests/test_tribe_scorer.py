"""
Tests for the TRIBE v2 scoring pipeline.

Verifies sequential scoring, partial failure handling, empty content skipping,
and correct ordering of results.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from orchestrator.engine.tribe_scorer import TribeScoringPipeline


def _make_scores(multiplier: float = 1.0) -> dict[str, float]:
    """Create a sample 7-dimension TRIBE scores dict."""
    return {
        "attention_capture": 72.0 * multiplier,
        "emotional_resonance": 65.0 * multiplier,
        "memory_encoding": 58.0 * multiplier,
        "reward_response": 70.0 * multiplier,
        "threat_detection": 30.0 * multiplier,
        "cognitive_load": 45.0 * multiplier,
        "social_relevance": 80.0 * multiplier,
    }


def _make_variant(variant_id: str, content: str = "Sample content for testing") -> dict:
    """Create a sample variant dict."""
    return {"id": variant_id, "content": content}


@pytest.fixture
def mock_tribe_client() -> AsyncMock:
    """Create a mock TribeClient with score_text as AsyncMock."""
    client = AsyncMock()
    client.score_text = AsyncMock(return_value=_make_scores())
    return client


@pytest.mark.asyncio
async def test_score_variants_all_success(mock_tribe_client: AsyncMock):
    """All 3 variants scored successfully -- returns 3 non-None results."""
    pipeline = TribeScoringPipeline(mock_tribe_client)

    variants = [
        _make_variant("v1", "First variant content for neural scoring"),
        _make_variant("v2", "Second variant content for neural scoring"),
        _make_variant("v3", "Third variant content for neural scoring"),
    ]

    results = await pipeline.score_variants(variants)

    assert len(results) == 3
    assert all(r is not None for r in results)
    assert all(isinstance(r, dict) for r in results)
    assert all("attention_capture" in r for r in results)
    assert mock_tribe_client.score_text.call_count == 3


@pytest.mark.asyncio
async def test_score_variants_partial_failure(mock_tribe_client: AsyncMock):
    """Second variant fails -- returns [scores, None, scores] pattern."""
    scores_1 = _make_scores(1.0)
    scores_3 = _make_scores(0.8)

    mock_tribe_client.score_text = AsyncMock(
        side_effect=[scores_1, None, scores_3]
    )

    pipeline = TribeScoringPipeline(mock_tribe_client)

    variants = [
        _make_variant("v1", "First variant"),
        _make_variant("v2", "Second variant"),
        _make_variant("v3", "Third variant"),
    ]

    results = await pipeline.score_variants(variants)

    assert len(results) == 3
    assert results[0] is not None
    assert results[1] is None
    assert results[2] is not None
    assert results[0]["attention_capture"] == 72.0
    assert results[2]["attention_capture"] == pytest.approx(57.6)


@pytest.mark.asyncio
async def test_score_variants_empty_content(mock_tribe_client: AsyncMock):
    """Variant with empty content returns None without calling score_text."""
    pipeline = TribeScoringPipeline(mock_tribe_client)

    variants = [
        _make_variant("v1", "Valid content here"),
        _make_variant("v2", ""),
        _make_variant("v3", "   "),  # whitespace-only also empty
    ]

    results = await pipeline.score_variants(variants)

    assert len(results) == 3
    assert results[0] is not None
    assert results[1] is None
    assert results[2] is None
    # score_text should only be called once (for v1)
    assert mock_tribe_client.score_text.call_count == 1


@pytest.mark.asyncio
async def test_score_variants_sequential_order(mock_tribe_client: AsyncMock):
    """Variants are scored in order (not parallel) -- verified via side_effect list."""
    call_order = []

    async def track_calls(text: str):
        call_order.append(text)
        return _make_scores()

    mock_tribe_client.score_text = AsyncMock(side_effect=track_calls)

    pipeline = TribeScoringPipeline(mock_tribe_client)

    variants = [
        _make_variant("v1", "First"),
        _make_variant("v2", "Second"),
        _make_variant("v3", "Third"),
    ]

    results = await pipeline.score_variants(variants)

    assert len(results) == 3
    assert call_order == ["First", "Second", "Third"]


@pytest.mark.asyncio
async def test_score_variants_empty_list(mock_tribe_client: AsyncMock):
    """Empty variant list returns empty results."""
    pipeline = TribeScoringPipeline(mock_tribe_client)
    results = await pipeline.score_variants([])
    assert results == []
    assert mock_tribe_client.score_text.call_count == 0


@pytest.mark.asyncio
async def test_score_variants_default_variant_id(mock_tribe_client: AsyncMock):
    """Variant without 'id' key gets a default variant_X id (no crash)."""
    pipeline = TribeScoringPipeline(mock_tribe_client)

    variants = [{"content": "Content without explicit id"}]

    results = await pipeline.score_variants(variants)

    assert len(results) == 1
    assert results[0] is not None
