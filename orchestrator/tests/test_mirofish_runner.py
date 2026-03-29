"""
Tests for the MiroFish simulation runner and metric computation.

Verifies simulation orchestration, metric computation from raw data,
partial failure handling, and edge cases for all 8 metrics.
"""

import pytest
from unittest.mock import AsyncMock

from orchestrator.engine.mirofish_runner import (
    MirofishRunner,
    compute_metrics,
    _count_shares,
    _compute_sentiment_trajectory,
    _count_counter_narratives,
    _find_peak_virality,
    _compute_sentiment_drift,
    _count_coalitions,
    _compute_influence_gini,
    _compute_platform_divergence,
)


def _make_raw_simulation_data() -> dict:
    """Create sample raw MiroFish simulation output with all data types."""
    return {
        "simulation_id": "sim_test_001",
        "posts": [
            {"id": "p1", "agent_id": "a1", "content": "I support this!", "platform": "twitter", "round": 1},
            {"id": "p2", "agent_id": "a2", "content": "This is concerning.", "platform": "reddit", "stance": "against", "round": 2},
            {"id": "p3", "agent_id": "a3", "content": "Sharing with friends.", "platform": "twitter", "round": 3},
        ],
        "actions": [
            {"agent_id": "a1", "action_type": "SHARE", "round": 1, "platform": "twitter"},
            {"agent_id": "a2", "action_type": "SHARE", "round": 1, "platform": "twitter"},
            {"agent_id": "a3", "action_type": "COUNTER_NARRATIVE", "round": 2, "platform": "reddit"},
            {"agent_id": "a1", "action_type": "REPOST", "round": 2, "platform": "twitter"},
            {"agent_id": "a4", "action_type": "SHARE", "round": 3, "platform": "reddit"},
            {"agent_id": "a1", "action_type": "SHARE", "round": 3, "platform": "twitter"},
        ],
        "timeline": [
            {"round": 1, "sentiment": 0.3, "shares": 2, "total_actions": 2},
            {"round": 2, "sentiment": 0.1, "shares": 1, "total_actions": 2},
            {"round": 3, "sentiment": 0.5, "shares": 2, "total_actions": 2},
        ],
        "agent_stats": [
            {"agent_id": "a1", "stance": "pro", "action_count": 3},
            {"agent_id": "a2", "stance": "pro", "action_count": 1},
            {"agent_id": "a3", "stance": "anti", "action_count": 1},
            {"agent_id": "a4", "stance": "pro", "action_count": 1},
        ],
    }


def _make_variant(variant_id: str, content: str = "Sample variant content") -> dict:
    """Create a sample variant dict."""
    return {"id": variant_id, "content": content}


@pytest.fixture
def mock_mirofish_client() -> AsyncMock:
    """Create a mock MirofishClient with run_simulation as AsyncMock."""
    client = AsyncMock()
    client.run_simulation = AsyncMock(return_value=_make_raw_simulation_data())
    return client


# -- Integration tests for MirofishRunner --


@pytest.mark.asyncio
async def test_simulate_variants_success(mock_mirofish_client: AsyncMock):
    """All variants simulated successfully -- returns metrics dicts with all 8 keys."""
    runner = MirofishRunner(mock_mirofish_client)

    variants = [
        _make_variant("v1", "First variant content for simulation"),
        _make_variant("v2", "Second variant content for simulation"),
    ]

    results = await runner.simulate_variants(
        variants=variants,
        prediction_question="Will this campaign go viral?",
        campaign_id="camp_001",
        agent_count=40,
        max_rounds=30,
    )

    assert len(results) == 2
    assert all(r is not None for r in results)

    expected_keys = {
        "organic_shares", "sentiment_trajectory", "counter_narrative_count",
        "peak_virality_cycle", "sentiment_drift", "coalition_formation",
        "influence_concentration", "platform_divergence",
    }
    for r in results:
        assert set(r.keys()) == expected_keys

    assert mock_mirofish_client.run_simulation.call_count == 2


@pytest.mark.asyncio
async def test_simulate_variants_partial_failure(mock_mirofish_client: AsyncMock):
    """Second variant fails -- returns [metrics, None, metrics] pattern."""
    raw_1 = _make_raw_simulation_data()
    raw_3 = _make_raw_simulation_data()

    mock_mirofish_client.run_simulation = AsyncMock(
        side_effect=[raw_1, None, raw_3]
    )

    runner = MirofishRunner(mock_mirofish_client)

    variants = [
        _make_variant("v1", "First variant"),
        _make_variant("v2", "Second variant"),
        _make_variant("v3", "Third variant"),
    ]

    results = await runner.simulate_variants(
        variants=variants,
        prediction_question="Test question",
        campaign_id="camp_002",
    )

    assert len(results) == 3
    assert results[0] is not None
    assert results[1] is None
    assert results[2] is not None


@pytest.mark.asyncio
async def test_simulate_variants_empty_content(mock_mirofish_client: AsyncMock):
    """Empty content variants are skipped without calling run_simulation."""
    runner = MirofishRunner(mock_mirofish_client)

    variants = [
        _make_variant("v1", "Valid content"),
        _make_variant("v2", ""),
        _make_variant("v3", "   "),
    ]

    results = await runner.simulate_variants(
        variants=variants,
        prediction_question="Test",
        campaign_id="camp_003",
    )

    assert len(results) == 3
    assert results[0] is not None
    assert results[1] is None
    assert results[2] is None
    assert mock_mirofish_client.run_simulation.call_count == 1


# -- Unit tests for individual metric computations --


def test_compute_metrics_organic_shares():
    """Raw data with 5 SHARE actions returns organic_shares=5."""
    raw = {
        "posts": [],
        "actions": [
            {"agent_id": "a1", "action_type": "SHARE", "round": 1},
            {"agent_id": "a2", "action_type": "SHARE", "round": 1},
            {"agent_id": "a3", "action_type": "REPOST", "round": 2},
            {"agent_id": "a4", "action_type": "SHARE", "round": 2},
            {"agent_id": "a5", "action_type": "RETWEET", "round": 3},
        ],
        "timeline": [],
        "agent_stats": [],
    }
    assert _count_shares(raw["actions"], raw["posts"]) == 5


def test_compute_metrics_organic_shares_fallback_to_posts():
    """When no share actions exist, falls back to post count."""
    raw = {
        "posts": [{"id": "p1"}, {"id": "p2"}, {"id": "p3"}],
        "actions": [
            {"agent_id": "a1", "action_type": "COMMENT", "round": 1},
        ],
        "timeline": [],
        "agent_stats": [],
    }
    assert _count_shares(raw["actions"], raw["posts"]) == 3


def test_compute_metrics_sentiment_trajectory():
    """Timeline with sentiment values extracts trajectory correctly."""
    timeline = [
        {"round": 1, "sentiment": 0.2},
        {"round": 2, "sentiment": 0.4},
        {"round": 3, "sentiment": 0.6},
    ]
    trajectory = _compute_sentiment_trajectory(timeline, [])
    assert trajectory == [0.2, 0.4, 0.6]


def test_compute_metrics_sentiment_trajectory_from_actions():
    """When timeline is empty, derives sentiment from action types."""
    actions = [
        {"agent_id": "a1", "action_type": "share", "round": 1},
        {"agent_id": "a2", "action_type": "share", "round": 1},
        {"agent_id": "a3", "action_type": "counter", "round": 2},
        {"agent_id": "a4", "action_type": "share", "round": 2},
    ]
    trajectory = _compute_sentiment_trajectory([], actions)
    assert len(trajectory) == 2
    # Round 1: 2 shares -> avg 0.5
    assert trajectory[0] == pytest.approx(0.5)
    # Round 2: 1 counter (-0.5) + 1 share (0.5) -> avg 0.0
    assert trajectory[1] == pytest.approx(0.0)


def test_compute_metrics_counter_narratives():
    """Actions with COUNTER_NARRATIVE types are counted."""
    actions = [
        {"agent_id": "a1", "action_type": "COUNTER_NARRATIVE", "round": 1},
        {"agent_id": "a2", "action_type": "SHARE", "round": 1},
        {"agent_id": "a3", "action_type": "OPPOSE", "round": 2},
    ]
    posts = [
        {"id": "p1", "stance": "against"},
        {"id": "p2", "stance": "supporting"},
    ]
    count = _count_counter_narratives(actions, posts)
    # 2 from actions (COUNTER_NARRATIVE, OPPOSE) + 1 from posts (stance=against)
    assert count == 3


def test_compute_metrics_peak_virality():
    """Timeline with varying activity returns correct peak round."""
    timeline = [
        {"round": 1, "shares": 5, "total_actions": 10},
        {"round": 2, "shares": 12, "total_actions": 20},
        {"round": 3, "shares": 8, "total_actions": 15},
    ]
    peak = _find_peak_virality(timeline, [])
    assert peak == 2  # Round 2 has most shares (12)


def test_compute_metrics_peak_virality_from_actions():
    """When timeline is empty, derives peak from action counts per round."""
    actions = [
        {"agent_id": "a1", "round": 1},
        {"agent_id": "a2", "round": 2},
        {"agent_id": "a3", "round": 2},
        {"agent_id": "a4", "round": 2},
        {"agent_id": "a5", "round": 3},
    ]
    peak = _find_peak_virality([], actions)
    assert peak == 2  # Round 2 has most actions (3)


def test_compute_metrics_sentiment_drift():
    """Sentiment drift is last minus first value."""
    trajectory = [0.2, 0.3, 0.5]
    drift = _compute_sentiment_drift(trajectory)
    assert drift == pytest.approx(0.3)


def test_compute_metrics_sentiment_drift_negative():
    """Negative drift when sentiment decreases."""
    trajectory = [0.5, 0.3, 0.1]
    drift = _compute_sentiment_drift(trajectory)
    assert drift == pytest.approx(-0.4)


def test_compute_metrics_sentiment_drift_single_value():
    """Single value trajectory returns 0.0 drift."""
    assert _compute_sentiment_drift([0.5]) == 0.0
    assert _compute_sentiment_drift([]) == 0.0


def test_compute_metrics_gini_equal():
    """All agents with same action count -- gini near 0."""
    actions = [
        {"agent_id": "a1", "round": 1},
        {"agent_id": "a2", "round": 1},
        {"agent_id": "a3", "round": 1},
        {"agent_id": "a4", "round": 1},
    ]
    gini = _compute_influence_gini([], actions, agent_count=4)
    assert gini == pytest.approx(0.0, abs=0.01)


def test_compute_metrics_gini_concentrated():
    """One agent has all actions -- gini near 1."""
    actions = [
        {"agent_id": "a1", "round": i} for i in range(40)
    ]
    gini = _compute_influence_gini([], actions, agent_count=40)
    # With 1 agent having 40 actions and 39 with 0, gini should be high
    assert gini > 0.9


def test_compute_metrics_gini_moderate():
    """Mixed distribution -- gini between 0 and 1."""
    actions = [
        {"agent_id": "a1", "round": 1},
        {"agent_id": "a1", "round": 2},
        {"agent_id": "a1", "round": 3},
        {"agent_id": "a2", "round": 1},
        {"agent_id": "a3", "round": 1},
    ]
    gini = _compute_influence_gini([], actions, agent_count=5)
    assert 0.0 < gini < 1.0


def test_compute_metrics_platform_divergence():
    """80% twitter, 20% reddit -- divergence = 0.6."""
    actions = [
        {"agent_id": "a1", "platform": "twitter"},
        {"agent_id": "a2", "platform": "twitter"},
        {"agent_id": "a3", "platform": "twitter"},
        {"agent_id": "a4", "platform": "twitter"},
    ]
    posts = [
        {"id": "p1", "platform": "reddit"},
    ]
    divergence = _compute_platform_divergence(actions, posts)
    # 4 twitter, 1 reddit = 80%/20% => divergence = |0.8 - 0.2| = 0.6
    assert divergence == pytest.approx(0.6)


def test_compute_metrics_platform_divergence_equal():
    """Equal twitter and reddit -- divergence = 0."""
    items = [
        {"platform": "twitter"},
        {"platform": "reddit"},
    ]
    divergence = _compute_platform_divergence(items, [])
    assert divergence == pytest.approx(0.0)


def test_compute_metrics_empty_data():
    """Empty raw data returns valid dict with safe defaults."""
    raw = {
        "posts": [],
        "actions": [],
        "timeline": [],
        "agent_stats": [],
    }
    metrics = compute_metrics(raw, agent_count=40)

    expected_keys = {
        "organic_shares", "sentiment_trajectory", "counter_narrative_count",
        "peak_virality_cycle", "sentiment_drift", "coalition_formation",
        "influence_concentration", "platform_divergence",
    }
    assert set(metrics.keys()) == expected_keys
    assert metrics["organic_shares"] == 0
    assert metrics["sentiment_trajectory"] == [0.0]
    assert metrics["counter_narrative_count"] == 0
    assert metrics["peak_virality_cycle"] == 1
    assert metrics["sentiment_drift"] == 0.0
    assert metrics["coalition_formation"] == 1  # at least 1
    assert metrics["influence_concentration"] == 0.0
    assert metrics["platform_divergence"] == 0.0


def test_compute_metrics_full_integration():
    """Full metric computation from realistic raw data."""
    raw = _make_raw_simulation_data()
    metrics = compute_metrics(raw, agent_count=40)

    assert isinstance(metrics["organic_shares"], int)
    assert metrics["organic_shares"] > 0
    assert isinstance(metrics["sentiment_trajectory"], list)
    assert len(metrics["sentiment_trajectory"]) == 3
    assert isinstance(metrics["counter_narrative_count"], int)
    assert isinstance(metrics["peak_virality_cycle"], int)
    assert metrics["peak_virality_cycle"] >= 1
    assert isinstance(metrics["sentiment_drift"], float)
    assert isinstance(metrics["coalition_formation"], int)
    assert metrics["coalition_formation"] >= 1
    assert 0.0 <= metrics["influence_concentration"] <= 1.0
    assert 0.0 <= metrics["platform_divergence"] <= 1.0


def test_compute_metrics_coalitions_pro_and_anti():
    """Both pro and anti coalitions detected from actions."""
    actions = [
        {"agent_id": "a1", "action_type": "share", "round": 1},
        {"agent_id": "a2", "action_type": "counter", "round": 1},
    ]
    agent_stats = [
        {"agent_id": "a1"},
        {"agent_id": "a2"},
        {"agent_id": "a3"},  # neutral
    ]
    coalitions = _count_coalitions(agent_stats, actions)
    # pro (a1), anti (a2), neutral (a3) = 3 coalitions
    assert coalitions == 3


def test_compute_metrics_coalitions_from_agent_stats():
    """Coalitions detected from agent_stats stance field."""
    actions = []
    agent_stats = [
        {"agent_id": "a1", "stance": "pro"},
        {"agent_id": "a2", "stance": "anti"},
        {"agent_id": "a3", "stance": "pro"},
    ]
    coalitions = _count_coalitions(agent_stats, actions)
    assert coalitions == 2  # pro and anti
