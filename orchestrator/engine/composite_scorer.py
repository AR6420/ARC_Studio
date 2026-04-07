"""
Composite score calculator for A.R.C Studio.

Implements all 7 composite score formulas from Results.md section 3.2,
combining TRIBE v2 neural scores and MiroFish simulation metrics into
unified scores that drive the optimization feedback loop.

Graceful degradation per D-05:
- TRIBE unavailable: attention_score, conversion_potential, audience_fit = None
- MiroFish unavailable: virality_potential, backlash_risk, memory_durability, polarization_index = None
- Both unavailable: all None

All scores normalized to 0-100 range (per Pitfall 5).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Clamp a value to [lo, hi] range."""
    return max(lo, min(hi, value))


def _sentiment_stability(sentiment_trajectory: list[float]) -> float:
    """
    Compute sentiment stability from trajectory.
    Stability = 1 - normalized_variance.
    Returns value in [0, 1] where 1 = perfectly stable.
    """
    if not sentiment_trajectory or len(sentiment_trajectory) < 2:
        return 0.5  # neutral default

    mean = sum(sentiment_trajectory) / len(sentiment_trajectory)
    variance = sum((s - mean) ** 2 for s in sentiment_trajectory) / len(
        sentiment_trajectory
    )

    # Normalize variance relative to the data range.
    # For values in a bounded range, max variance occurs at extremes.
    max_val = max(abs(v) for v in sentiment_trajectory) if sentiment_trajectory else 1.0
    max_possible_variance = max_val**2 if max_val > 0 else 1.0
    normalized_variance = min(variance / max(max_possible_variance, 0.001), 1.0)
    return 1.0 - normalized_variance


def compute_composite_scores(
    tribe: dict[str, float] | None,
    mirofish: dict[str, Any] | None,
    cognitive_weights: dict[str, float],
    agent_count: int,
) -> dict[str, float | None]:
    """
    Compute all 7 composite scores from TRIBE v2 neural scores and MiroFish
    simulation metrics.

    Formulas from Results.md section 3.2:
    1. attention_score = 0.6 * attention_capture + 0.4 * emotional_resonance
       (TRIBE only)
    2. virality_potential = (emotional_resonance * social_relevance)
       / max(cognitive_load, 10) * share_rate_normalized
       (cross-system: TRIBE + MiroFish)
    3. backlash_risk = threat_detection / max(reward_response + social_relevance, 10)
       * counter_narrative_factor
       (cross-system: TRIBE + MiroFish)
    4. memory_durability = memory_encoding * emotional_resonance * sentiment_stability
       (cross-system: TRIBE + MiroFish)
    5. conversion_potential = reward_response * attention_capture
       / max(threat_detection, 10)
       (TRIBE only)
    6. audience_fit = weighted average of TRIBE scores using demographic
       cognitive_weights
       (TRIBE only)
    7. polarization_index = coalition_count * platform_divergence
       * (1 - sentiment_stability)
       (MiroFish only)

    Args:
        tribe: Dict of 7 TRIBE v2 dimension scores (0-100 each), or None
            if unavailable.
        mirofish: Dict of 8 MiroFish metrics, or None if unavailable.
        cognitive_weights: Dict of per-dimension weight multipliers from
            demographic profile.
        agent_count: Number of agents in the simulation (for share rate
            normalization).

    Returns:
        Dict of 7 composite scores, each float (0-100) or None if
        insufficient data.
    """
    scores: dict[str, float | None] = {}

    # Pre-compute MiroFish derived values if available
    share_rate_normalized: float | None = None
    counter_narrative_factor: float | None = None
    sentiment_stability: float | None = None
    coalition_count: int | None = None
    platform_divergence_val: float | None = None

    if mirofish:
        organic_shares = mirofish.get("organic_shares", 0)
        share_rate_normalized = organic_shares / max(agent_count, 1) * 100.0

        counter_narrative_factor = (
            mirofish.get("counter_narrative_count", 0) / max(agent_count, 1) * 100.0
        )

        sentiment_trajectory = mirofish.get("sentiment_trajectory", [])
        sentiment_stability = _sentiment_stability(sentiment_trajectory)

        coalition_count = mirofish.get("coalition_formation", 0)
        platform_divergence_val = mirofish.get("platform_divergence", 0.0)

    # 1. Attention score (TRIBE only)
    if tribe:
        raw = 0.6 * tribe["attention_capture"] + 0.4 * tribe["emotional_resonance"]
        scores["attention_score"] = round(_clamp(raw), 1)
    else:
        scores["attention_score"] = None

    # 2. Virality potential (cross-system: TRIBE + MiroFish)
    if tribe and mirofish and share_rate_normalized is not None:
        raw = (
            (tribe["emotional_resonance"] * tribe["social_relevance"])
            / max(tribe["cognitive_load"], 10)
            * share_rate_normalized
        )
        # Normalize: product of two 0-100 values / 10 * share_rate can be large.
        # Divide by 100 for 0-100 range.
        scores["virality_potential"] = round(_clamp(raw / 100.0), 1)
    else:
        scores["virality_potential"] = None

    # 3. Backlash risk (cross-system: TRIBE + MiroFish)
    if tribe and mirofish and counter_narrative_factor is not None:
        raw = (
            tribe["threat_detection"]
            / max(tribe["reward_response"] + tribe["social_relevance"], 10)
            * counter_narrative_factor
        )
        # Normalize: threat/sum * factor. Factor can be 0-100. Result typically
        # 0-50 range. Scale up.
        scores["backlash_risk"] = round(_clamp(raw * 2.0), 1)
    else:
        scores["backlash_risk"] = None

    # 4. Memory durability (cross-system: TRIBE + MiroFish)
    if tribe and mirofish and sentiment_stability is not None:
        raw = (
            tribe["memory_encoding"]
            * tribe["emotional_resonance"]
            * sentiment_stability
        )
        # Normalize: product of two 0-100 values * stability(0-1) -> max 10000.
        # Divide by 100.
        scores["memory_durability"] = round(_clamp(raw / 100.0), 1)
    else:
        scores["memory_durability"] = None

    # 5. Conversion potential (TRIBE only)
    if tribe:
        raw = (
            tribe["reward_response"]
            * tribe["attention_capture"]
            / max(tribe["threat_detection"], 10)
        )
        # Normalize: product of two 0-100 values / denominator(10-100).
        # Max ~1000. Divide by 10.
        scores["conversion_potential"] = round(_clamp(raw / 10.0), 1)
    else:
        scores["conversion_potential"] = None

    # 6. Audience fit (TRIBE only, uses cognitive_weights)
    if tribe:
        weighted_scores = []
        for dim, score in tribe.items():
            weight = cognitive_weights.get(dim, 1.0)
            weighted_scores.append(score * weight)
        if weighted_scores:
            raw = sum(weighted_scores) / len(weighted_scores)
            scores["audience_fit"] = round(_clamp(raw), 1)
        else:
            scores["audience_fit"] = None
    else:
        scores["audience_fit"] = None

    # 7. Polarization index (MiroFish only)
    if (
        mirofish
        and coalition_count is not None
        and platform_divergence_val is not None
        and sentiment_stability is not None
    ):
        raw = coalition_count * platform_divergence_val * (1 - sentiment_stability)
        # Normalize: coalition_count (typically 2-5) * divergence(0-1)
        # * instability(0-1). Max ~5. Scale by 20.
        scores["polarization_index"] = round(_clamp(raw * 20.0), 1)
    else:
        scores["polarization_index"] = None

    return scores
