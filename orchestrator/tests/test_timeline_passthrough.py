"""
Phase 5 (AMD hackathon): timeline data must flow TRIBE → tribe_client →
TribeScores schema → storage → API response without loss.

Covers the four hops independently so a regression at any layer is caught
in isolation.
"""

import json

import pytest

from orchestrator.api.schemas import CampaignCreateRequest, TribeScores
from orchestrator.clients.tribe_client import _extract_scores
from orchestrator.storage.campaign_store import CampaignStore
from orchestrator.storage.database import Database


SAMPLE_TIMELINE = {
    "attention_capture":   [0.041, 0.067, 0.052, 0.071, 0.063],
    "emotional_resonance": [0.013, 0.022, 0.019, 0.028, 0.024],
    "memory_encoding":     [0.028, 0.031, 0.027, 0.034, 0.030],
    "reward_response":     [0.011, 0.015, 0.018, 0.021, 0.019],
    "threat_detection":    [0.005, 0.009, 0.012, 0.011, 0.008],
    "cognitive_load":      [0.034, 0.041, 0.038, 0.044, 0.040],
    "social_relevance":    [0.029, 0.033, 0.035, 0.038, 0.034],
}


def _make_tribe_response(*, with_timeline: bool) -> dict:
    payload = {
        "attention_capture": 73.4,
        "emotional_resonance": 56.1,
        "memory_encoding": 61.8,
        "reward_response": 49.2,
        "threat_detection": 38.5,
        "cognitive_load": 65.0,
        "social_relevance": 71.7,
        "is_pseudo_score": False,
        "inference_time_ms": 1842.3,
    }
    if with_timeline:
        payload["timeline"] = SAMPLE_TIMELINE
        payload["tr_seconds"] = 1.49
    return payload


# ── Hop 1: tribe_client._extract_scores ─────────────────────────────────────


def test_extract_scores_includes_timeline_when_present():
    out = _extract_scores(_make_tribe_response(with_timeline=True))
    assert out is not None
    assert out["timeline"] == SAMPLE_TIMELINE
    assert out["tr_seconds"] == 1.49


def test_extract_scores_omits_timeline_when_absent():
    out = _extract_scores(_make_tribe_response(with_timeline=False))
    assert out is not None
    assert "timeline" not in out
    assert "tr_seconds" not in out


# ── Hop 2: TribeScores Pydantic schema ──────────────────────────────────────


def test_tribe_scores_schema_accepts_timeline():
    extracted = _extract_scores(_make_tribe_response(with_timeline=True))
    model = TribeScores(**extracted)
    assert model.timeline == SAMPLE_TIMELINE
    assert model.tr_seconds == 1.49


def test_tribe_scores_schema_defaults_timeline_to_none():
    extracted = _extract_scores(_make_tribe_response(with_timeline=False))
    model = TribeScores(**extracted)
    assert model.timeline is None
    assert model.tr_seconds is None


def test_tribe_scores_serialises_timeline_to_json_dict():
    """API responses go through model_dump → JSON. Timeline must round-trip."""
    extracted = _extract_scores(_make_tribe_response(with_timeline=True))
    model = TribeScores(**extracted)
    dumped = model.model_dump()
    assert dumped["timeline"] == SAMPLE_TIMELINE
    assert dumped["tr_seconds"] == 1.49
    # JSON-serialisable
    re_loaded = json.loads(json.dumps(dumped))
    assert re_loaded["timeline"]["attention_capture"][0] == pytest.approx(0.041)


# ── Hop 3: SQLite storage round-trip ────────────────────────────────────────


async def test_storage_roundtrip_preserves_timeline(tmp_db_path: str):
    """save_iteration → get_iterations preserves timeline through the
    JSON column. Catches regressions where storage drops the field."""
    db = Database(tmp_db_path)
    await db.connect()
    try:
        store = CampaignStore(db)
        campaign = await store.create_campaign(
            CampaignCreateRequest(
                seed_content="A" * 150,
                prediction_question="Will the timeline survive storage?",
                demographic="tech_professionals",
            )
        )

        tribe_dict = _extract_scores(_make_tribe_response(with_timeline=True))
        await store.save_iteration(
            campaign_id=campaign.id,
            iteration_number=1,
            variant_id="v1",
            variant_content="hello",
            variant_strategy=None,
            tribe_scores=tribe_dict,
            mirofish_metrics=None,
            composite_scores=None,
        )

        iterations = await store.get_iterations(campaign.id)
        assert len(iterations) == 1
        recovered = iterations[0].tribe_scores
        assert recovered is not None
        assert recovered.timeline == SAMPLE_TIMELINE
        assert recovered.tr_seconds == 1.49
    finally:
        await db.close()
