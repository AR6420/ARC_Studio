"""
Tests for DataCompleteness (Landmine 5) schema and campaign_runner computation.

Verifies that the DataCompleteness model is correctly populated from
tribe_scores, mirofish_metrics, and composite_scores produced by
run_single_iteration().
"""

import pytest

from orchestrator.api.schemas import DataCompleteness


# ---------------------------------------------------------------------------
# Helper: replicate the computation logic from campaign_runner._run_single_iteration
# so we can unit-test it without standing up the full pipeline.
# ---------------------------------------------------------------------------

def _compute_data_completeness(
    tribe_scores_list: list[dict | None],
    mirofish_metrics_list: list[dict | None],
    composite_scores_list: list[dict | None],
) -> DataCompleteness:
    """Replicates the DataCompleteness computation in campaign_runner."""
    tribe_real = sum(
        1 for t in tribe_scores_list if t and not t.get("is_pseudo_score")
    )
    tribe_pseudo = sum(
        1 for t in tribe_scores_list if t and t.get("is_pseudo_score")
    )
    mirofish_ok = any(m is not None for m in mirofish_metrics_list)

    missing: set[str] = set()
    for comp in composite_scores_list:
        if comp:
            for key, val in comp.items():
                if val is None:
                    missing.add(key)

    return DataCompleteness(
        tribe_available=any(t is not None for t in tribe_scores_list),
        mirofish_available=mirofish_ok,
        tribe_real_score_count=tribe_real,
        tribe_pseudo_score_count=tribe_pseudo,
        missing_composite_dimensions=sorted(missing),
    )


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _real_tribe_score(**overrides) -> dict:
    base = {
        "attention_capture": 72.0,
        "emotional_resonance": 65.0,
        "memory_encoding": 58.0,
        "reward_response": 70.0,
        "threat_detection": 15.0,
        "cognitive_load": 42.0,
        "social_relevance": 68.0,
        "is_pseudo_score": False,
    }
    base.update(overrides)
    return base


def _pseudo_tribe_score(**overrides) -> dict:
    base = _real_tribe_score()
    base["is_pseudo_score"] = True
    base.update(overrides)
    return base


def _mirofish_metrics(**overrides) -> dict:
    base = {
        "organic_shares": 10,
        "sentiment_trajectory": [0.2, 0.4, 0.5],
        "counter_narrative_count": 2,
        "peak_virality_cycle": 2,
        "sentiment_drift": 0.3,
        "coalition_formation": 2,
        "influence_concentration": 0.35,
        "platform_divergence": 0.2,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_data_completeness_schema_defaults():
    """DataCompleteness can be instantiated with all defaults."""
    dc = DataCompleteness()
    assert dc.tribe_available is True
    assert dc.mirofish_available is True
    assert dc.tribe_real_score_count == 0
    assert dc.tribe_pseudo_score_count == 0
    assert dc.missing_composite_dimensions == []


def test_data_completeness_model_dump():
    """DataCompleteness.model_dump() returns the expected dict structure."""
    dc = DataCompleteness(
        tribe_available=True,
        mirofish_available=False,
        tribe_real_score_count=2,
        tribe_pseudo_score_count=1,
        missing_composite_dimensions=["virality_potential", "backlash_risk"],
    )
    dumped = dc.model_dump()
    assert dumped["tribe_available"] is True
    assert dumped["mirofish_available"] is False
    assert dumped["tribe_real_score_count"] == 2
    assert dumped["tribe_pseudo_score_count"] == 1
    assert dumped["missing_composite_dimensions"] == ["virality_potential", "backlash_risk"]


def test_counts_real_and_pseudo_tribe_scores():
    """
    2 real TRIBE scores + 1 pseudo score are counted correctly.
    MiroFish with 1 None entry still counts as available (any() check).
    """
    tribe_scores = [
        _real_tribe_score(),   # real
        _real_tribe_score(),   # real
        _pseudo_tribe_score(), # pseudo
    ]
    mirofish_metrics = [
        _mirofish_metrics(),   # valid
        None,                  # failed variant
        _mirofish_metrics(),   # valid
    ]
    composite_scores = [
        {"attention_score": 70.0, "virality_potential": 5.0, "backlash_risk": 2.0,
         "memory_durability": 30.0, "conversion_potential": 33.0, "audience_fit": 65.0,
         "polarization_index": 1.0},
        {"attention_score": 65.0, "virality_potential": None, "backlash_risk": None,
         "memory_durability": None, "conversion_potential": 28.0, "audience_fit": 60.0,
         "polarization_index": None},
        {"attention_score": 80.0, "virality_potential": 8.0, "backlash_risk": 3.0,
         "memory_durability": 35.0, "conversion_potential": 40.0, "audience_fit": 72.0,
         "polarization_index": 1.5},
    ]

    dc = _compute_data_completeness(tribe_scores, mirofish_metrics, composite_scores)

    assert dc.tribe_real_score_count == 2
    assert dc.tribe_pseudo_score_count == 1
    assert dc.mirofish_available is True  # at least one non-None


def test_mirofish_available_with_partial_nones():
    """mirofish_available=True when at least one variant's metrics are not None."""
    dc = _compute_data_completeness(
        tribe_scores_list=[_real_tribe_score(), _real_tribe_score()],
        mirofish_metrics_list=[None, _mirofish_metrics()],
        composite_scores_list=[
            {"attention_score": 70.0, "virality_potential": None, "backlash_risk": None,
             "memory_durability": None, "conversion_potential": 30.0, "audience_fit": 60.0,
             "polarization_index": None},
            {"attention_score": 72.0, "virality_potential": 5.0, "backlash_risk": 2.0,
             "memory_durability": 28.0, "conversion_potential": 32.0, "audience_fit": 64.0,
             "polarization_index": 1.0},
        ],
    )
    assert dc.mirofish_available is True


def test_mirofish_unavailable_when_all_none():
    """mirofish_available=False when all variant metrics are None."""
    dc = _compute_data_completeness(
        tribe_scores_list=[_real_tribe_score()],
        mirofish_metrics_list=[None],
        composite_scores_list=[
            {"attention_score": 70.0, "virality_potential": None, "backlash_risk": None,
             "memory_durability": None, "conversion_potential": 30.0, "audience_fit": 60.0,
             "polarization_index": None},
        ],
    )
    assert dc.mirofish_available is False


def test_missing_composite_dimensions_detected():
    """
    When virality_potential is None in any composite score, it appears in
    missing_composite_dimensions.
    """
    composite_scores = [
        {"attention_score": 70.0, "virality_potential": None, "backlash_risk": None,
         "memory_durability": None, "conversion_potential": 30.0, "audience_fit": 60.0,
         "polarization_index": None},
    ]
    dc = _compute_data_completeness(
        tribe_scores_list=[_real_tribe_score()],
        mirofish_metrics_list=[None],
        composite_scores_list=composite_scores,
    )
    assert "virality_potential" in dc.missing_composite_dimensions
    assert "backlash_risk" in dc.missing_composite_dimensions
    assert "memory_durability" in dc.missing_composite_dimensions
    assert "polarization_index" in dc.missing_composite_dimensions
    # Sorted alphabetically
    assert dc.missing_composite_dimensions == sorted(dc.missing_composite_dimensions)


def test_no_missing_dimensions_when_all_present():
    """missing_composite_dimensions is empty when all composite scores are non-None."""
    composite_scores = [
        {"attention_score": 70.0, "virality_potential": 5.0, "backlash_risk": 2.0,
         "memory_durability": 30.0, "conversion_potential": 33.0, "audience_fit": 65.0,
         "polarization_index": 1.0},
    ]
    dc = _compute_data_completeness(
        tribe_scores_list=[_real_tribe_score()],
        mirofish_metrics_list=[_mirofish_metrics()],
        composite_scores_list=composite_scores,
    )
    assert dc.missing_composite_dimensions == []


def test_tribe_unavailable_when_all_none():
    """tribe_available=False when all tribe scores are None."""
    dc = _compute_data_completeness(
        tribe_scores_list=[None, None],
        mirofish_metrics_list=[_mirofish_metrics(), _mirofish_metrics()],
        composite_scores_list=[
            {"attention_score": None, "virality_potential": None, "backlash_risk": None,
             "memory_durability": None, "conversion_potential": None, "audience_fit": None,
             "polarization_index": 1.0},
            {"attention_score": None, "virality_potential": None, "backlash_risk": None,
             "memory_durability": None, "conversion_potential": None, "audience_fit": None,
             "polarization_index": 1.5},
        ],
    )
    assert dc.tribe_available is False
    assert dc.tribe_real_score_count == 0
    assert dc.tribe_pseudo_score_count == 0


def test_full_completeness_scenario():
    """
    Full scenario: 2 real TRIBE scores, 1 pseudo, MiroFish with 1 None,
    one composite has None virality_potential.
    """
    tribe_scores = [
        _real_tribe_score(),
        _real_tribe_score(),
        _pseudo_tribe_score(),
    ]
    mirofish_metrics = [
        _mirofish_metrics(),
        None,
        _mirofish_metrics(),
    ]
    composite_scores = [
        {"attention_score": 70.0, "virality_potential": 5.0, "backlash_risk": 2.0,
         "memory_durability": 30.0, "conversion_potential": 33.0, "audience_fit": 65.0,
         "polarization_index": 1.0},
        # MiroFish was None for this variant -> virality_potential is None
        {"attention_score": 65.0, "virality_potential": None, "backlash_risk": None,
         "memory_durability": None, "conversion_potential": 28.0, "audience_fit": 60.0,
         "polarization_index": None},
        {"attention_score": 80.0, "virality_potential": 8.0, "backlash_risk": 3.0,
         "memory_durability": 35.0, "conversion_potential": 40.0, "audience_fit": 72.0,
         "polarization_index": 1.5},
    ]

    dc = _compute_data_completeness(tribe_scores, mirofish_metrics, composite_scores)

    assert dc.tribe_real_score_count == 2
    assert dc.tribe_pseudo_score_count == 1
    assert dc.mirofish_available is True
    assert dc.tribe_available is True
    assert "virality_potential" in dc.missing_composite_dimensions
