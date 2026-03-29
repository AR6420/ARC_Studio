"""
Tests for orchestrator Pydantic schemas.
"""

import pytest
from pydantic import ValidationError

from orchestrator.api.schemas import (
    CampaignCreateRequest,
    CampaignResponse,
    CompositeScores,
    IterationRecord,
    MirofishMetrics,
    TribeScores,
)


class TestCampaignCreateRequest:
    """Tests for CampaignCreateRequest validation."""

    def _valid_payload(self, **overrides) -> dict:
        """Return a valid payload, with optional overrides."""
        base = {
            "seed_content": "A" * 150,  # well above min_length=100
            "prediction_question": "How will this resonate?",
            "demographic": "tech_professionals",
        }
        base.update(overrides)
        return base

    def test_valid_request_with_defaults(self):
        """Accepts valid input and fills in defaults."""
        req = CampaignCreateRequest(**self._valid_payload())
        assert req.agent_count == 40
        assert req.max_iterations == 4
        assert req.auto_start is True
        assert req.thresholds is None
        assert req.constraints is None
        assert req.demographic_custom is None

    def test_rejects_short_seed_content(self):
        """seed_content shorter than 100 characters must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CampaignCreateRequest(**self._valid_payload(seed_content="too short"))
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("seed_content",) for e in errors)

    def test_validates_seed_content_min_length(self):
        """seed_content of exactly 100 characters should be accepted."""
        req = CampaignCreateRequest(**self._valid_payload(seed_content="X" * 100))
        assert len(req.seed_content) == 100

    def test_rejects_short_prediction_question(self):
        """prediction_question shorter than 10 chars must be rejected."""
        with pytest.raises(ValidationError):
            CampaignCreateRequest(**self._valid_payload(prediction_question="short"))

    def test_defaults_are_correct(self):
        """agent_count=40, max_iterations=4, auto_start=True."""
        req = CampaignCreateRequest(**self._valid_payload())
        assert req.agent_count == 40
        assert req.max_iterations == 4
        assert req.auto_start is True

    def test_agent_count_bounds(self):
        """agent_count must be between 20 and 200."""
        with pytest.raises(ValidationError):
            CampaignCreateRequest(**self._valid_payload(agent_count=10))
        with pytest.raises(ValidationError):
            CampaignCreateRequest(**self._valid_payload(agent_count=300))
        # Boundary values should succeed
        req_low = CampaignCreateRequest(**self._valid_payload(agent_count=20))
        assert req_low.agent_count == 20
        req_high = CampaignCreateRequest(**self._valid_payload(agent_count=200))
        assert req_high.agent_count == 200

    def test_max_iterations_bounds(self):
        """max_iterations must be between 1 and 10."""
        with pytest.raises(ValidationError):
            CampaignCreateRequest(**self._valid_payload(max_iterations=0))
        with pytest.raises(ValidationError):
            CampaignCreateRequest(**self._valid_payload(max_iterations=15))

    def test_optional_fields(self):
        """Optional fields can be set."""
        req = CampaignCreateRequest(
            **self._valid_payload(
                demographic_custom="Custom demo description",
                thresholds={"attention": 0.8, "virality": 0.6},
                constraints="Keep under 500 words",
                auto_start=False,
            )
        )
        assert req.demographic_custom == "Custom demo description"
        assert req.thresholds == {"attention": 0.8, "virality": 0.6}
        assert req.constraints == "Keep under 500 words"
        assert req.auto_start is False


class TestTribeScores:
    """Tests for TribeScores model."""

    def test_accepts_seven_float_fields(self):
        """All 7 TRIBE dimensions should be accepted as floats."""
        scores = TribeScores(
            attention_capture=0.85,
            emotional_resonance=0.72,
            memory_encoding=0.68,
            reward_response=0.91,
            threat_detection=0.45,
            cognitive_load=0.33,
            social_relevance=0.77,
        )
        assert scores.attention_capture == 0.85
        assert scores.social_relevance == 0.77

    def test_rejects_missing_fields(self):
        """All 7 fields are required."""
        with pytest.raises(ValidationError):
            TribeScores(attention_capture=0.5)  # Missing 6 fields


class TestCompositeScores:
    """Tests for CompositeScores model."""

    def test_all_fields_default_to_none(self):
        """All 7 composite scores default to None (graceful degradation)."""
        scores = CompositeScores()
        assert scores.attention_score is None
        assert scores.virality_potential is None
        assert scores.backlash_risk is None
        assert scores.memory_durability is None
        assert scores.conversion_potential is None
        assert scores.audience_fit is None
        assert scores.polarization_index is None

    def test_partial_scores(self):
        """Can set some scores while leaving others as None."""
        scores = CompositeScores(attention_score=0.8, backlash_risk=0.3)
        assert scores.attention_score == 0.8
        assert scores.backlash_risk == 0.3
        assert scores.virality_potential is None


class TestMirofishMetrics:
    """Tests for MirofishMetrics model."""

    def test_accepts_all_eight_fields(self):
        """All 8 MiroFish metrics including list[float] for sentiment_trajectory."""
        metrics = MirofishMetrics(
            organic_shares=150,
            sentiment_trajectory=[0.5, 0.6, 0.55, 0.7, 0.65],
            counter_narrative_count=3,
            peak_virality_cycle=4,
            sentiment_drift=0.15,
            coalition_formation=2,
            influence_concentration=0.45,
            platform_divergence=0.22,
        )
        assert metrics.organic_shares == 150
        assert len(metrics.sentiment_trajectory) == 5
        assert metrics.sentiment_trajectory[3] == 0.7
        assert metrics.coalition_formation == 2
        assert metrics.influence_concentration == 0.45

    def test_rejects_missing_fields(self):
        """All 8 fields are required."""
        with pytest.raises(ValidationError):
            MirofishMetrics(organic_shares=100)


class TestCampaignResponse:
    """Tests for CampaignResponse serialization with nested records."""

    def test_serialization_with_nested_iterations(self):
        """CampaignResponse should serialize correctly with nested IterationRecords."""
        iteration = IterationRecord(
            id="iter-001",
            campaign_id="camp-001",
            iteration_number=1,
            variant_id="v1",
            variant_content="Test variant content for serialization.",
            variant_strategy="direct_appeal",
            tribe_scores=TribeScores(
                attention_capture=0.85,
                emotional_resonance=0.72,
                memory_encoding=0.68,
                reward_response=0.91,
                threat_detection=0.45,
                cognitive_load=0.33,
                social_relevance=0.77,
            ),
            mirofish_metrics=MirofishMetrics(
                organic_shares=150,
                sentiment_trajectory=[0.5, 0.6, 0.55],
                counter_narrative_count=3,
                peak_virality_cycle=4,
                sentiment_drift=0.15,
                coalition_formation=2,
                influence_concentration=0.45,
                platform_divergence=0.22,
            ),
            composite_scores=CompositeScores(
                attention_score=0.8, virality_potential=0.6
            ),
            created_at="2026-03-29T10:00:00",
        )

        campaign = CampaignResponse(
            id="camp-001",
            status="running",
            seed_content="A" * 150,
            prediction_question="How will this resonate?",
            demographic="tech_professionals",
            agent_count=40,
            max_iterations=4,
            created_at="2026-03-29T09:00:00",
            started_at="2026-03-29T09:01:00",
            iterations=[iteration],
        )

        # Verify serialization roundtrip
        data = campaign.model_dump()
        assert data["id"] == "camp-001"
        assert data["status"] == "running"
        assert len(data["iterations"]) == 1
        assert data["iterations"][0]["tribe_scores"]["attention_capture"] == 0.85
        assert data["iterations"][0]["mirofish_metrics"]["organic_shares"] == 150
        assert data["iterations"][0]["composite_scores"]["attention_score"] == 0.8

        # Verify JSON serialization
        json_str = campaign.model_dump_json()
        reconstructed = CampaignResponse.model_validate_json(json_str)
        assert reconstructed.iterations[0].tribe_scores.attention_capture == 0.85
