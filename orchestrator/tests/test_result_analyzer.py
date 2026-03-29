"""
Tests for the cross-system result analyzer (Claude Opus analysis).

Verifies that ResultAnalyzer correctly:
- Calls Claude Opus via call_opus_json with the result analysis prompt
- Handles custom demographics
- Passes thresholds to the prompt builder
- Serializes previous_analysis as JSON string for the prompt
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from orchestrator.engine.result_analyzer import ResultAnalyzer


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_mock_claude_client(analysis_response: dict | None = None) -> AsyncMock:
    """Create a mock ClaudeClient with call_opus_json pre-configured."""
    client = AsyncMock()
    client.call_opus_json.return_value = analysis_response or {
        "iteration_number": 1,
        "per_variant_assessment": [
            {
                "variant_id": "v1",
                "neural_summary": "High attention (82) and emotional resonance (75).",
                "social_summary": "12 organic shares, peak virality at cycle 3.",
                "cross_system_insight": "High attention drove early sharing.",
                "strengths": ["Strong attention capture"],
                "weaknesses": ["Moderate cognitive load"],
                "composite_assessment": "Strong performer overall.",
            }
        ],
        "ranking": ["v1", "v2", "v3"],
        "cross_system_insights": [
            "High attention_capture (82) correlated with 12 organic shares.",
            "Low threat_detection (15) aligned with zero counter-narratives.",
            "Emotional resonance (75) drove peak virality at cycle 3.",
        ],
        "iteration_improvement_notes": "First iteration -- no comparison available.",
        "recommendations_for_next_iteration": [
            "Try reducing cognitive load to improve sharing velocity.",
            "Increase social relevance cues for broader coalition formation.",
            "Test a fear-appeal variant to explore backlash dynamics.",
        ],
        "thresholds_assessment": {
            "met": False,
            "notes": "Attention score 74 below target 80.",
        },
    }
    return client


def _sample_variants_with_scores() -> list[dict]:
    """Return sample variants with TRIBE + MiroFish scores for testing."""
    return [
        {
            "variant_id": "v1",
            "content": "Sample content variant 1 for testing.",
            "strategy": "direct_appeal",
            "tribe_scores": {
                "attention_capture": 82.0,
                "emotional_resonance": 75.0,
                "memory_encoding": 68.0,
                "reward_response": 71.0,
                "threat_detection": 15.0,
                "cognitive_load": 42.0,
                "social_relevance": 78.0,
            },
            "mirofish_metrics": {
                "organic_shares": 12,
                "sentiment_trajectory": [0.2, 0.4, 0.5, 0.45],
                "counter_narrative_count": 0,
                "peak_virality_cycle": 3,
                "sentiment_drift": 0.25,
                "coalition_formation": 1,
                "influence_concentration": 0.35,
                "platform_divergence": 0.1,
            },
            "composite_scores": {
                "attention_score": 79.2,
                "virality_potential": 45.3,
                "backlash_risk": 2.1,
                "memory_durability": 38.5,
                "conversion_potential": 64.7,
                "audience_fit": 72.0,
                "polarization_index": 1.2,
            },
        },
    ]


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_iteration_success():
    """Verify a successful analysis call returns expected structure."""
    mock_client = _make_mock_claude_client()
    analyzer = ResultAnalyzer(claude_client=mock_client)

    result = await analyzer.analyze_iteration(
        iteration_number=1,
        campaign_brief="Test product launch for a new SaaS tool.",
        prediction_question="How will tech professionals respond?",
        demographic="tech_professionals",
        demographic_custom=None,
        variants_with_scores=_sample_variants_with_scores(),
    )

    # Verify result has expected keys
    assert "per_variant_assessment" in result
    assert "ranking" in result
    assert "cross_system_insights" in result
    assert result["ranking"] == ["v1", "v2", "v3"]
    assert len(result["cross_system_insights"]) == 3

    # Verify call_opus_json was called once with correct params
    mock_client.call_opus_json.assert_called_once()
    call_kwargs = mock_client.call_opus_json.call_args
    assert call_kwargs.kwargs["max_tokens"] == 8192


@pytest.mark.asyncio
async def test_analyze_iteration_with_previous():
    """Verify previous_analysis is serialized as JSON and passed to the prompt."""
    mock_client = _make_mock_claude_client()
    analyzer = ResultAnalyzer(claude_client=mock_client)

    previous = {
        "ranking": ["v2", "v1"],
        "cross_system_insights": ["Insight from prior iteration."],
    }

    with patch(
        "orchestrator.engine.result_analyzer.build_result_analysis_prompt"
    ) as mock_build:
        mock_build.return_value = "mocked prompt"

        await analyzer.analyze_iteration(
            iteration_number=2,
            campaign_brief="Test campaign brief.",
            prediction_question="How will people respond?",
            demographic="tech_professionals",
            demographic_custom=None,
            variants_with_scores=_sample_variants_with_scores(),
            previous_analysis=previous,
        )

        # Verify the prompt builder received previous_analysis as JSON string
        mock_build.assert_called_once()
        call_kwargs = mock_build.call_args.kwargs
        assert call_kwargs["previous_analysis"] is not None
        # Verify it's a valid JSON string
        parsed = json.loads(call_kwargs["previous_analysis"])
        assert parsed["ranking"] == ["v2", "v1"]


@pytest.mark.asyncio
async def test_analyze_iteration_custom_demographic():
    """Verify custom demographic passes the custom description, not a preset."""
    mock_client = _make_mock_claude_client()
    analyzer = ResultAnalyzer(claude_client=mock_client)

    with patch(
        "orchestrator.engine.result_analyzer.build_result_analysis_prompt"
    ) as mock_build:
        mock_build.return_value = "mocked prompt"

        await analyzer.analyze_iteration(
            iteration_number=1,
            campaign_brief="Test campaign.",
            prediction_question="Response prediction?",
            demographic="custom",
            demographic_custom="Left-handed underwater basket weavers aged 30-40",
            variants_with_scores=_sample_variants_with_scores(),
        )

        call_kwargs = mock_build.call_args.kwargs
        assert call_kwargs["demographic_description"] == "Left-handed underwater basket weavers aged 30-40"


@pytest.mark.asyncio
async def test_analyze_iteration_with_thresholds():
    """Verify thresholds are forwarded to the prompt builder."""
    mock_client = _make_mock_claude_client()
    analyzer = ResultAnalyzer(claude_client=mock_client)

    thresholds = {"attention_score": 70.0, "virality_potential": 50.0}

    with patch(
        "orchestrator.engine.result_analyzer.build_result_analysis_prompt"
    ) as mock_build:
        mock_build.return_value = "mocked prompt"

        await analyzer.analyze_iteration(
            iteration_number=1,
            campaign_brief="Test campaign.",
            prediction_question="Response prediction?",
            demographic="general_consumer_us",
            demographic_custom=None,
            variants_with_scores=_sample_variants_with_scores(),
            thresholds=thresholds,
        )

        call_kwargs = mock_build.call_args.kwargs
        assert call_kwargs["thresholds"] == {"attention_score": 70.0, "virality_potential": 50.0}
