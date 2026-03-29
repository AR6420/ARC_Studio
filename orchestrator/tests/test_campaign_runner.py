"""
Tests for the campaign runner (main orchestration pipeline).

Verifies that CampaignRunner correctly:
- Wires all 5 pipeline steps into a single iteration flow
- Updates campaign status at each lifecycle point (running/completed/failed)
- Degrades gracefully when TRIBE or MiroFish is unavailable
- Persists iterations and analysis to the campaign store
"""

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from orchestrator.api.schemas import CampaignResponse
from orchestrator.engine.campaign_runner import CampaignRunner


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_campaign_response() -> CampaignResponse:
    """Create a realistic mock campaign response."""
    return CampaignResponse(
        id="campaign-001",
        status="pending",
        seed_content="A" * 150,  # meets min_length=100
        prediction_question="How will tech professionals respond to this product launch?",
        demographic="tech_professionals",
        demographic_custom=None,
        agent_count=40,
        max_iterations=4,
        thresholds={"attention_score": 70.0},
        constraints=None,
        created_at="2026-03-29T00:00:00Z",
    )


def _make_variants() -> list[dict]:
    """Create 3 sample variant dicts."""
    return [
        {"id": "v1", "content": "Variant 1 content about AI product launch.", "strategy": "direct_appeal"},
        {"id": "v2", "content": "Variant 2 content using social proof approach.", "strategy": "social_proof"},
        {"id": "v3", "content": "Variant 3 content with urgency framing.", "strategy": "urgency"},
    ]


def _make_tribe_scores() -> list[dict]:
    """Create 3 sample TRIBE score dicts."""
    return [
        {
            "attention_capture": 82.0, "emotional_resonance": 75.0, "memory_encoding": 68.0,
            "reward_response": 71.0, "threat_detection": 15.0, "cognitive_load": 42.0, "social_relevance": 78.0,
        },
        {
            "attention_capture": 70.0, "emotional_resonance": 80.0, "memory_encoding": 72.0,
            "reward_response": 65.0, "threat_detection": 20.0, "cognitive_load": 38.0, "social_relevance": 69.0,
        },
        {
            "attention_capture": 90.0, "emotional_resonance": 60.0, "memory_encoding": 55.0,
            "reward_response": 85.0, "threat_detection": 45.0, "cognitive_load": 55.0, "social_relevance": 72.0,
        },
    ]


def _make_mirofish_metrics() -> list[dict]:
    """Create 3 sample MiroFish metric dicts."""
    return [
        {
            "organic_shares": 12, "sentiment_trajectory": [0.2, 0.4, 0.5],
            "counter_narrative_count": 0, "peak_virality_cycle": 3,
            "sentiment_drift": 0.3, "coalition_formation": 1,
            "influence_concentration": 0.35, "platform_divergence": 0.1,
        },
        {
            "organic_shares": 8, "sentiment_trajectory": [0.1, 0.2, 0.3],
            "counter_narrative_count": 2, "peak_virality_cycle": 5,
            "sentiment_drift": 0.2, "coalition_formation": 2,
            "influence_concentration": 0.45, "platform_divergence": 0.3,
        },
        {
            "organic_shares": 20, "sentiment_trajectory": [0.5, 0.3, 0.1],
            "counter_narrative_count": 5, "peak_virality_cycle": 1,
            "sentiment_drift": -0.4, "coalition_formation": 3,
            "influence_concentration": 0.6, "platform_divergence": 0.5,
        },
    ]


def _make_analysis() -> dict:
    """Create a sample analysis result dict."""
    return {
        "iteration_number": 1,
        "per_variant_assessment": [
            {"variant_id": "v1", "composite_assessment": "Strong performer."},
        ],
        "ranking": ["v1", "v3", "v2"],
        "cross_system_insights": [
            "High attention drove sharing.",
            "Threat detection correlated with counter-narratives.",
        ],
        "recommendations_for_next_iteration": ["Reduce cognitive load."],
        "thresholds_assessment": {"met": False, "notes": "Below target."},
    }


def _build_runner(
    tribe_available: bool = True,
    mirofish_available: bool = True,
    variant_gen_error: bool = False,
) -> tuple[CampaignRunner, dict[str, AsyncMock]]:
    """
    Build a CampaignRunner with all mocked dependencies.
    Returns (runner, dict of named mocks).
    """
    mock_variant_gen = AsyncMock()
    if variant_gen_error:
        mock_variant_gen.generate_variants.side_effect = RuntimeError("Haiku API error")
    else:
        mock_variant_gen.generate_variants.return_value = _make_variants()

    mock_tribe_scoring = AsyncMock()
    mock_tribe_scoring.score_variants.return_value = _make_tribe_scores()

    mock_mirofish_runner = AsyncMock()
    mock_mirofish_runner.simulate_variants.return_value = _make_mirofish_metrics()

    mock_result_analyzer = AsyncMock()
    mock_result_analyzer.analyze_iteration.return_value = _make_analysis()

    mock_store = AsyncMock()
    mock_store.get_campaign.return_value = _make_campaign_response()
    mock_store.save_iteration.return_value = "iter-id-001"
    mock_store.save_analysis.return_value = "analysis-id-001"

    mock_tribe_client = AsyncMock()
    mock_tribe_client.health_check.return_value = tribe_available

    mock_mirofish_client = AsyncMock()
    mock_mirofish_client.health_check.return_value = mirofish_available

    runner = CampaignRunner(
        variant_generator=mock_variant_gen,
        tribe_scoring=mock_tribe_scoring,
        mirofish_runner=mock_mirofish_runner,
        result_analyzer=mock_result_analyzer,
        campaign_store=mock_store,
        tribe_client=mock_tribe_client,
        mirofish_client=mock_mirofish_client,
    )

    mocks = {
        "variant_gen": mock_variant_gen,
        "tribe_scoring": mock_tribe_scoring,
        "mirofish_runner": mock_mirofish_runner,
        "result_analyzer": mock_result_analyzer,
        "store": mock_store,
        "tribe_client": mock_tribe_client,
        "mirofish_client": mock_mirofish_client,
    }

    return runner, mocks


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_full_pipeline_success():
    """Full pipeline with all systems available -- verify all steps execute."""
    runner, mocks = _build_runner(tribe_available=True, mirofish_available=True)

    result = await runner.run_single_iteration(campaign_id="campaign-001")

    # Verify status updates: running then completed
    status_calls = mocks["store"].update_campaign_status.call_args_list
    assert status_calls[0] == call("campaign-001", "running")
    assert status_calls[1] == call("campaign-001", "completed")

    # Verify generate_variants called once
    mocks["variant_gen"].generate_variants.assert_called_once()

    # Verify score_variants called once
    mocks["tribe_scoring"].score_variants.assert_called_once()

    # Verify simulate_variants called once
    mocks["mirofish_runner"].simulate_variants.assert_called_once()

    # Verify save_iteration called 3 times (once per variant)
    assert mocks["store"].save_iteration.call_count == 3

    # Verify save_analysis called once
    mocks["store"].save_analysis.assert_called_once()

    # Verify result structure
    assert "variants" in result
    assert "tribe_scores" in result
    assert "mirofish_metrics" in result
    assert "composite_scores" in result
    assert "analysis" in result
    assert len(result["variants"]) == 3
    assert len(result["tribe_scores"]) == 3
    assert len(result["mirofish_metrics"]) == 3
    assert len(result["composite_scores"]) == 3
    assert result["system_availability"]["tribe_available"] is True
    assert result["system_availability"]["mirofish_available"] is True


@pytest.mark.asyncio
async def test_run_tribe_unavailable():
    """TRIBE unavailable -- pipeline skips scoring, composite scores reflect gaps."""
    runner, mocks = _build_runner(tribe_available=False, mirofish_available=True)

    result = await runner.run_single_iteration(campaign_id="campaign-001")

    # score_variants should NOT be called
    mocks["tribe_scoring"].score_variants.assert_not_called()

    # tribe_scores should all be None
    assert all(ts is None for ts in result["tribe_scores"])

    # composite_scores should have TRIBE-only fields as None
    for composite in result["composite_scores"]:
        assert composite["attention_score"] is None
        assert composite["conversion_potential"] is None

    # Pipeline should still complete
    status_calls = mocks["store"].update_campaign_status.call_args_list
    assert status_calls[-1] == call("campaign-001", "completed")


@pytest.mark.asyncio
async def test_run_mirofish_unavailable():
    """MiroFish unavailable -- pipeline skips simulation, composite scores reflect gaps."""
    runner, mocks = _build_runner(tribe_available=True, mirofish_available=False)

    result = await runner.run_single_iteration(campaign_id="campaign-001")

    # simulate_variants should NOT be called
    mocks["mirofish_runner"].simulate_variants.assert_not_called()

    # mirofish_metrics should all be None
    assert all(mm is None for mm in result["mirofish_metrics"])

    # composite_scores should have MiroFish-only fields as None
    for composite in result["composite_scores"]:
        assert composite["virality_potential"] is None
        assert composite["polarization_index"] is None

    # Pipeline should still complete
    status_calls = mocks["store"].update_campaign_status.call_args_list
    assert status_calls[-1] == call("campaign-001", "completed")


@pytest.mark.asyncio
async def test_run_both_unavailable():
    """Both TRIBE and MiroFish unavailable -- pipeline still completes with warnings."""
    runner, mocks = _build_runner(tribe_available=False, mirofish_available=False)

    result = await runner.run_single_iteration(campaign_id="campaign-001")

    # Neither scoring nor simulation should be called
    mocks["tribe_scoring"].score_variants.assert_not_called()
    mocks["mirofish_runner"].simulate_variants.assert_not_called()

    # Warnings should contain 2 entries
    assert len(result["warnings"]) == 2

    # variant generation and analysis still run
    mocks["variant_gen"].generate_variants.assert_called_once()
    mocks["result_analyzer"].analyze_iteration.assert_called_once()

    # Pipeline should still complete
    status_calls = mocks["store"].update_campaign_status.call_args_list
    assert status_calls[-1] == call("campaign-001", "completed")


@pytest.mark.asyncio
async def test_run_pipeline_failure_sets_failed_status():
    """Exception during pipeline sets status to 'failed' and propagates."""
    runner, mocks = _build_runner(variant_gen_error=True)

    with pytest.raises(RuntimeError, match="Haiku API error"):
        await runner.run_single_iteration(campaign_id="campaign-001")

    # Verify status was set to running, then to failed with error message
    status_calls = mocks["store"].update_campaign_status.call_args_list
    assert status_calls[0] == call("campaign-001", "running")
    assert status_calls[1] == call("campaign-001", "failed", error="Haiku API error")
