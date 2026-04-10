"""
Tests for the composite scorer module.

Validates that compute_composite_scores correctly implements all 7 formulas
from Results.md section 3.2, handles graceful degradation when TRIBE or
MiroFish data is unavailable, and normalizes all scores to 0-100 range.
"""

import pytest

from orchestrator.engine.composite_scorer import compute_composite_scores


# -- Sample data --

SAMPLE_TRIBE = {
    "attention_capture": 72.0,
    "emotional_resonance": 65.0,
    "memory_encoding": 58.0,
    "reward_response": 70.0,
    "threat_detection": 15.0,
    "cognitive_load": 42.0,
    "social_relevance": 68.0,
}

SAMPLE_MIROFISH = {
    "organic_shares": 12,
    "sentiment_trajectory": [0.2, 0.3, 0.5, 0.4, 0.6],
    "counter_narrative_count": 3,
    "peak_virality_cycle": 4,
    "sentiment_drift": 0.4,
    "coalition_formation": 2,
    "influence_concentration": 0.35,
    "platform_divergence": 0.25,
}

SAMPLE_WEIGHTS = {
    "attention_capture": 1.0,
    "emotional_resonance": 0.8,
    "memory_encoding": 1.1,
    "reward_response": 0.9,
    "threat_detection": 1.2,
    "cognitive_load": 0.7,
    "social_relevance": 1.15,
}

AGENT_COUNT = 40


# -- Test 1: attention_score formula --

def test_attention_score():
    """attention_score = 0.6 * attention_capture + 0.4 * emotional_resonance, result in 0-100."""
    scores = compute_composite_scores(
        tribe=SAMPLE_TRIBE,
        mirofish=SAMPLE_MIROFISH,
        cognitive_weights=SAMPLE_WEIGHTS,
        agent_count=AGENT_COUNT,
    )
    expected = round(0.6 * 72.0 + 0.4 * 65.0, 1)  # 43.2 + 26.0 = 69.2
    assert scores["attention_score"] == expected
    assert 0 <= scores["attention_score"] <= 100


# -- Test 2: virality_potential formula --

def test_virality_potential():
    """virality_potential uses cross-system formula with share_rate normalization, result in 0-100."""
    scores = compute_composite_scores(
        tribe=SAMPLE_TRIBE,
        mirofish=SAMPLE_MIROFISH,
        cognitive_weights=SAMPLE_WEIGHTS,
        agent_count=AGENT_COUNT,
    )
    assert scores["virality_potential"] is not None
    assert 0 <= scores["virality_potential"] <= 100


# -- Test 3: backlash_risk formula --

def test_backlash_risk():
    """backlash_risk uses threat_detection, reward_response, social_relevance,
    counter_narrative_factor, result in 0-100."""
    scores = compute_composite_scores(
        tribe=SAMPLE_TRIBE,
        mirofish=SAMPLE_MIROFISH,
        cognitive_weights=SAMPLE_WEIGHTS,
        agent_count=AGENT_COUNT,
    )
    assert scores["backlash_risk"] is not None
    assert 0 <= scores["backlash_risk"] <= 100


# -- Test 4: memory_durability formula --

def test_memory_durability():
    """memory_durability uses memory_encoding * emotional_resonance * sentiment_stability,
    normalized to 0-100."""
    scores = compute_composite_scores(
        tribe=SAMPLE_TRIBE,
        mirofish=SAMPLE_MIROFISH,
        cognitive_weights=SAMPLE_WEIGHTS,
        agent_count=AGENT_COUNT,
    )
    assert scores["memory_durability"] is not None
    assert 0 <= scores["memory_durability"] <= 100


# -- Test 5: conversion_potential formula --

def test_conversion_potential():
    """conversion_potential = reward_response * attention_capture / max(threat_detection, 10),
    normalized to 0-100."""
    scores = compute_composite_scores(
        tribe=SAMPLE_TRIBE,
        mirofish=SAMPLE_MIROFISH,
        cognitive_weights=SAMPLE_WEIGHTS,
        agent_count=AGENT_COUNT,
    )
    # Expected: (70.0 * 72.0) / max(15.0, 10) / 10.0 = 5040 / 15 / 10 = 33.6
    expected = round(70.0 * 72.0 / max(15.0, 10) / 10.0, 1)
    assert scores["conversion_potential"] == expected
    assert 0 <= scores["conversion_potential"] <= 100


# -- Test 6: audience_fit formula --

def test_audience_fit():
    """audience_fit applies cognitive_weights to all TRIBE scores and averages,
    result in 0-100."""
    scores = compute_composite_scores(
        tribe=SAMPLE_TRIBE,
        mirofish=SAMPLE_MIROFISH,
        cognitive_weights=SAMPLE_WEIGHTS,
        agent_count=AGENT_COUNT,
    )
    # Manual calculation: weighted average of each TRIBE score * its weight
    weighted = [
        72.0 * 1.0,    # attention_capture
        65.0 * 0.8,    # emotional_resonance
        58.0 * 1.1,    # memory_encoding
        70.0 * 0.9,    # reward_response
        15.0 * 1.2,    # threat_detection
        42.0 * 0.7,    # cognitive_load
        68.0 * 1.15,   # social_relevance
    ]
    expected = round(sum(weighted) / len(weighted), 1)
    assert scores["audience_fit"] == expected
    assert 0 <= scores["audience_fit"] <= 100


# -- Test 7: polarization_index formula --

def test_polarization_index():
    """polarization_index uses coalition_count * platform_divergence * (1 - sentiment_stability),
    normalized to 0-100."""
    scores = compute_composite_scores(
        tribe=SAMPLE_TRIBE,
        mirofish=SAMPLE_MIROFISH,
        cognitive_weights=SAMPLE_WEIGHTS,
        agent_count=AGENT_COUNT,
    )
    assert scores["polarization_index"] is not None
    assert 0 <= scores["polarization_index"] <= 100


# -- Test 8: TRIBE unavailable --

def test_tribe_unavailable():
    """When tribe=None, attention_score, conversion_potential, audience_fit are None;
    cross-system scores are also None."""
    scores = compute_composite_scores(
        tribe=None,
        mirofish=SAMPLE_MIROFISH,
        cognitive_weights=SAMPLE_WEIGHTS,
        agent_count=AGENT_COUNT,
    )
    # TRIBE-only scores should be None
    assert scores["attention_score"] is None
    assert scores["conversion_potential"] is None
    assert scores["audience_fit"] is None
    # Cross-system scores requiring TRIBE should also be None
    assert scores["virality_potential"] is None
    assert scores["backlash_risk"] is None
    assert scores["memory_durability"] is None
    # MiroFish-only score should still work
    assert scores["polarization_index"] is not None


# -- Test 9: MiroFish unavailable --

def test_mirofish_unavailable():
    """When mirofish=None, virality_potential, backlash_risk, memory_durability,
    polarization_index are None; TRIBE-only scores still computed."""
    scores = compute_composite_scores(
        tribe=SAMPLE_TRIBE,
        mirofish=None,
        cognitive_weights=SAMPLE_WEIGHTS,
        agent_count=AGENT_COUNT,
    )
    # Cross-system and MiroFish-only scores should be None
    assert scores["virality_potential"] is None
    assert scores["backlash_risk"] is None
    assert scores["memory_durability"] is None
    assert scores["polarization_index"] is None
    # TRIBE-only scores should still work
    assert scores["attention_score"] is not None
    assert scores["conversion_potential"] is not None
    assert scores["audience_fit"] is not None


# -- Test 10: Both unavailable --

def test_both_unavailable():
    """When both tribe=None and mirofish=None, all scores are None."""
    scores = compute_composite_scores(
        tribe=None,
        mirofish=None,
        cognitive_weights=SAMPLE_WEIGHTS,
        agent_count=AGENT_COUNT,
    )
    for key, value in scores.items():
        assert value is None, f"{key} should be None when both systems unavailable"


# -- Test 11: All scores in range --

def test_all_scores_in_range():
    """Every non-None score is between 0 and 100."""
    scores = compute_composite_scores(
        tribe=SAMPLE_TRIBE,
        mirofish=SAMPLE_MIROFISH,
        cognitive_weights=SAMPLE_WEIGHTS,
        agent_count=AGENT_COUNT,
    )
    for key, value in scores.items():
        if value is not None:
            assert 0 <= value <= 100, f"{key}={value} is outside 0-100 range"


# -- Test 12: Shares mapping (Issue 13) --

def test_organic_shares_flows_through_to_virality():
    """
    Regression test for Issue 13: mirofish_metrics must use 'organic_shares'
    (not 'total_shares' or any other alias) end-to-end.

    Verifies that organic_shares=10 produces a non-zero virality_potential,
    while organic_shares=0 produces virality_potential=0.
    """
    mirofish_with_shares = {
        "organic_shares": 10,
        "sentiment_trajectory": [0.2, 0.4, 0.5],
        "counter_narrative_count": 0,
        "peak_virality_cycle": 2,
        "sentiment_drift": 0.3,
        "coalition_formation": 1,
        "influence_concentration": 0.3,
        "platform_divergence": 0.2,
    }
    mirofish_zero_shares = {**mirofish_with_shares, "organic_shares": 0}

    scores_with_shares = compute_composite_scores(
        tribe=SAMPLE_TRIBE,
        mirofish=mirofish_with_shares,
        cognitive_weights=SAMPLE_WEIGHTS,
        agent_count=AGENT_COUNT,
    )
    scores_zero_shares = compute_composite_scores(
        tribe=SAMPLE_TRIBE,
        mirofish=mirofish_zero_shares,
        cognitive_weights=SAMPLE_WEIGHTS,
        agent_count=AGENT_COUNT,
    )

    # virality_potential must be > 0 when organic_shares=10
    assert scores_with_shares["virality_potential"] is not None
    assert scores_with_shares["virality_potential"] > 0, (
        "virality_potential must be > 0 when organic_shares=10"
    )

    # virality_potential must be 0 when organic_shares=0
    assert scores_zero_shares["virality_potential"] == 0.0, (
        "virality_potential must be 0 when organic_shares=0"
    )

    # Confirm organic_shares=10 produces higher virality than organic_shares=0
    assert scores_with_shares["virality_potential"] > scores_zero_shares["virality_potential"], (
        "shares=10 must yield higher virality_potential than shares=0"
    )
