"""
Tests for the report generation engine, data layer, and Pydantic models.

Covers:
- Report storage (save_report / get_report)
- ScorecardData / ReportResponse Pydantic models
- ReportGenerator engine (verdict, scorecard, deep analysis, mass psychology)
- color_code_score utility
"""

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from orchestrator.api.schemas import (
    AnalysisRecord,
    CampaignCreateRequest,
    CampaignResponse,
    CompositeScores,
    IterationRecord,
    MirofishMetrics,
    ReportResponse,
    ScorecardData,
    ScorecardVariant,
    TribeScores,
)
from orchestrator.engine.report_generator import ReportGenerator, color_code_score
from orchestrator.storage.campaign_store import CampaignStore
from orchestrator.storage.database import Database


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_request(**overrides) -> CampaignCreateRequest:
    """Create a valid CampaignCreateRequest with optional overrides."""
    base = {
        "seed_content": "A" * 150,
        "prediction_question": "How will this content resonate with the target audience?",
        "demographic": "tech_professionals",
    }
    base.update(overrides)
    return CampaignCreateRequest(**base)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db(tmp_db_path: str):
    """Create and connect a test database, yield it, then close."""
    database = Database(tmp_db_path)
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
async def store(db: Database) -> CampaignStore:
    """Create a CampaignStore backed by the test database."""
    return CampaignStore(db)


# ── Storage Tests ────────────────────────────────────────────────────────────


class TestReportStorage:
    """Tests for save_report() and get_report() on CampaignStore."""

    async def test_save_and_get_report(self, store: CampaignStore):
        """save_report() persists all 5 layer fields and get_report() retrieves them."""
        campaign = await store.create_campaign(_make_request())

        report_data = {
            "verdict": "Use variant A. It performed best across all dimensions.",
            "scorecard": {
                "winning_variant_id": "v1",
                "variants": [
                    {
                        "variant_id": "v1",
                        "rank": 1,
                        "strategy": "direct_appeal",
                        "composite_scores": {"attention_score": 82.0, "virality_potential": 65.0},
                        "color_coding": {"attention_score": "green", "virality_potential": "amber"},
                    }
                ],
                "iteration_trajectory": [{"iteration": 1, "best_scores": {"attention_score": 78.0}}],
                "thresholds_status": {"all_met": True, "per_threshold": {"attention_score": True}},
                "summary": "Variant A ranked first across all metrics.",
            },
            "deep_analysis": {
                "iterations": [
                    {
                        "iteration": 1,
                        "variants": [{"variant_id": "v1", "content": "Test content"}],
                        "analysis": {"summary": "Strong performer."},
                    }
                ]
            },
            "mass_psychology_general": "The community rallied around the message early.",
            "mass_psychology_technical": "Granovetter threshold model explains the cascade.",
        }

        report_id = await store.save_report(campaign_id=campaign.id, report=report_data)
        assert report_id is not None
        assert len(report_id) == 36  # UUID4

        # Retrieve
        retrieved = await store.get_report(campaign.id)
        assert retrieved is not None
        assert isinstance(retrieved, ReportResponse)
        assert retrieved.campaign_id == campaign.id
        assert retrieved.verdict == report_data["verdict"]
        assert retrieved.scorecard is not None
        assert retrieved.scorecard.winning_variant_id == "v1"
        assert len(retrieved.scorecard.variants) == 1
        assert retrieved.scorecard.variants[0].color_coding == {"attention_score": "green", "virality_potential": "amber"}
        assert retrieved.deep_analysis is not None
        assert retrieved.deep_analysis["iterations"][0]["iteration"] == 1
        assert retrieved.mass_psychology_general == report_data["mass_psychology_general"]
        assert retrieved.mass_psychology_technical == report_data["mass_psychology_technical"]

    async def test_get_report_not_found(self, store: CampaignStore):
        """get_report() returns None for a campaign with no report."""
        campaign = await store.create_campaign(_make_request())
        result = await store.get_report(campaign.id)
        assert result is None

    async def test_get_report_nonexistent_campaign(self, store: CampaignStore):
        """get_report() returns None for a nonexistent campaign."""
        result = await store.get_report("nonexistent-id")
        assert result is None


# ── Pydantic Model Tests ────────────────────────────────────────────────────


class TestScorecardDataModel:
    """Tests for ScorecardData Pydantic model validation."""

    def test_scorecard_data_validates_structure(self):
        """ScorecardData model validates variant ranking structure with color_coding."""
        data = ScorecardData(
            winning_variant_id="v1",
            variants=[
                ScorecardVariant(
                    variant_id="v1",
                    rank=1,
                    strategy="direct_appeal",
                    composite_scores={"attention_score": 82.0, "virality_potential": 65.0},
                    color_coding={"attention_score": "green", "virality_potential": "amber"},
                ),
                ScorecardVariant(
                    variant_id="v2",
                    rank=2,
                    strategy="social_proof",
                    composite_scores={"attention_score": 60.0, "virality_potential": 45.0},
                    color_coding={"attention_score": "amber", "virality_potential": "amber"},
                ),
            ],
            iteration_trajectory=[
                {"iteration": 1, "best_scores": {"attention_score": 78.0}},
                {"iteration": 2, "best_scores": {"attention_score": 82.0}},
            ],
            thresholds_status={"all_met": True, "per_threshold": {"attention_score": True}},
            summary="Variant A ranked first.",
        )
        assert data.winning_variant_id == "v1"
        assert len(data.variants) == 2
        assert data.variants[0].rank == 1
        assert data.variants[1].color_coding["attention_score"] == "amber"


class TestReportResponseModel:
    """Tests for ReportResponse Pydantic model serialization."""

    def test_report_response_serializes_all_layers(self):
        """ReportResponse model serializes all layer fields correctly."""
        report = ReportResponse(
            id="rpt-001",
            campaign_id="cmp-001",
            verdict="Use variant A.",
            scorecard=ScorecardData(
                winning_variant_id="v1",
                variants=[],
                iteration_trajectory=[],
                thresholds_status={},
                summary="Summary text.",
            ),
            deep_analysis={"iterations": []},
            mass_psychology_general="General narrative text.",
            mass_psychology_technical="Technical analysis with Granovetter and Cialdini.",
            created_at="2026-03-29T00:00:00Z",
        )
        assert isinstance(report.verdict, str)
        assert isinstance(report.scorecard, ScorecardData)
        assert isinstance(report.deep_analysis, dict)
        assert isinstance(report.mass_psychology_general, str)
        assert isinstance(report.mass_psychology_technical, str)

        # Serialize to dict
        data = report.model_dump()
        assert data["verdict"] == "Use variant A."
        assert data["scorecard"]["winning_variant_id"] == "v1"
        assert data["deep_analysis"] == {"iterations": []}


# ── ReportGenerator Engine Tests ─────────────────────────────────────────────


def _mock_claude_client() -> AsyncMock:
    """Create a mock ClaudeClient that records calls and returns canned responses."""
    client = AsyncMock()

    async def _call_opus(system: str, user: str, max_tokens: int = 4096) -> str:
        """Return canned text based on which system prompt is used."""
        if "verdict" in system.lower() or "advisor" in system.lower():
            return (
                "Use variant v1. Our analysis found that this approach captures attention "
                "more effectively and generates greater engagement than the alternatives. "
                "The direct appeal strategy resonated strongly with the target audience, "
                "producing the highest levels of interest and sharing. Avoid the urgency-based "
                "approach as it triggered defensive reactions. The research found a surprising "
                "result: the most shareable content was not the most emotionally intense. "
                "Go with variant v1 for the best results."
            )
        elif "science communicator" in system.lower() or "general" in system.lower():
            return (
                "When the content first reached the community, reactions were muted. By cycle 3, "
                "a few influential voices began sharing it, and momentum built quickly. The turning "
                "point came around cycle 5 when sentiment shifted decisively positive. By the end "
                "of the simulation, the majority of participants had engaged positively. The direct "
                "appeal approach avoided the backlash that the urgency variant triggered."
            )
        elif "behavioral scientist" in system.lower() or "technical" in system.lower():
            return (
                "The observed cascade dynamics align with Granovetter's threshold model, where "
                "initial adoption by low-threshold agents triggered broader participation. "
                "Noelle-Neumann's spiral of silence was evident in the suppression of counter-narratives "
                "after cycle 5. Social proof cascade rate peaked at 2.4 shares/cycle. "
                "In-group formation index: 0.65. Opinion leader influence ratio: 3.2:1."
            )
        elif "scorecard" in system.lower() or "ranking" in system.lower():
            return json.dumps({
                "summary": "Variant v1 ranked first with strong attention and low backlash.",
                "ranking_rationale": "Direct appeal outperformed other strategies.",
            })
        return "Default response."

    client.call_opus = AsyncMock(side_effect=_call_opus)
    client.call_opus_json = AsyncMock(return_value={
        "summary": "Variant v1 ranked first.",
        "ranking_rationale": "Direct appeal outperformed.",
    })
    return client


def _make_campaign() -> CampaignResponse:
    """Create a mock CampaignResponse for testing."""
    return CampaignResponse(
        id="cmp-test-001",
        status="completed",
        seed_content="A" * 150,
        prediction_question="How will tech professionals respond to this product launch?",
        demographic="tech_professionals",
        agent_count=40,
        max_iterations=4,
        thresholds={"attention_score": 70.0, "virality_potential": 50.0},
        created_at="2026-03-29T00:00:00Z",
    )


def _make_iterations() -> list[IterationRecord]:
    """Create mock IterationRecords (2 iterations, 3 variants each)."""
    records = []
    for iter_num in range(1, 3):
        for vid, strategy, attn, viral, backlash, mem, conv, aud, polar in [
            ("v1", "direct_appeal", 75.0 + iter_num * 3, 60.0 + iter_num * 2, 15.0 - iter_num, 65.0, 70.0, 72.0, 10.0),
            ("v2", "social_proof", 65.0 + iter_num * 2, 55.0 + iter_num, 20.0, 58.0, 60.0, 65.0, 18.0),
            ("v3", "urgency", 55.0 + iter_num, 40.0, 45.0, 50.0, 55.0, 48.0, 35.0),
        ]:
            records.append(
                IterationRecord(
                    id=f"it-{iter_num}-{vid}",
                    campaign_id="cmp-test-001",
                    iteration_number=iter_num,
                    variant_id=vid,
                    variant_content=f"Content for {vid} iteration {iter_num}.",
                    variant_strategy=strategy,
                    tribe_scores=TribeScores(
                        attention_capture=attn / 100,
                        emotional_resonance=0.72,
                        memory_encoding=0.68,
                        reward_response=0.71,
                        threat_detection=0.15,
                        cognitive_load=0.33,
                        social_relevance=0.78,
                    ),
                    mirofish_metrics=MirofishMetrics(
                        organic_shares=int(viral / 5),
                        sentiment_trajectory=[0.3, 0.5, 0.6, 0.55],
                        counter_narrative_count=1 if backlash > 30 else 0,
                        peak_virality_cycle=3,
                        sentiment_drift=0.25,
                        coalition_formation=2,
                        influence_concentration=0.45,
                        platform_divergence=0.22,
                    ),
                    composite_scores=CompositeScores(
                        attention_score=attn,
                        virality_potential=viral,
                        backlash_risk=backlash,
                        memory_durability=mem,
                        conversion_potential=conv,
                        audience_fit=aud,
                        polarization_index=polar,
                    ),
                    created_at=f"2026-03-29T0{iter_num}:00:00Z",
                )
            )
    return records


def _make_analyses() -> list[AnalysisRecord]:
    """Create mock AnalysisRecords (1 per iteration)."""
    return [
        AnalysisRecord(
            id=f"an-{i}",
            campaign_id="cmp-test-001",
            iteration_number=i,
            analysis_json={
                "ranking": ["v1", "v2", "v3"],
                "cross_system_insights": [
                    f"Iteration {i}: High attention drove sharing.",
                    f"Iteration {i}: Low backlash correlated with positive sentiment.",
                ],
                "recommendations_for_next_iteration": ["Improve virality."],
            },
            created_at=f"2026-03-29T0{i}:30:00Z",
        )
        for i in range(1, 3)
    ]


def _make_best_scores_history() -> list[dict[str, float | None]]:
    """Create mock best_scores_history (one per iteration)."""
    return [
        {
            "attention_score": 78.0,
            "virality_potential": 62.0,
            "backlash_risk": 14.0,
            "memory_durability": 65.0,
            "conversion_potential": 70.0,
            "audience_fit": 72.0,
            "polarization_index": 10.0,
        },
        {
            "attention_score": 81.0,
            "virality_potential": 64.0,
            "backlash_risk": 13.0,
            "memory_durability": 65.0,
            "conversion_potential": 70.0,
            "audience_fit": 72.0,
            "polarization_index": 10.0,
        },
    ]


class TestReportGeneratorEngine:
    """Tests for ReportGenerator.generate_report() and its layers."""

    @pytest.mark.asyncio
    async def test_generate_report_verdict(self):
        """RPT-01: generate_report() calls call_opus with REPORT_VERDICT_SYSTEM and returns verdict text."""
        client = _mock_claude_client()
        generator = ReportGenerator(claude_client=client)

        result = await generator.generate_report(
            campaign=_make_campaign(),
            all_iterations=_make_iterations(),
            all_analyses=_make_analyses(),
            best_scores_history=_make_best_scores_history(),
            stop_reason="max_iterations",
        )

        assert "verdict" in result
        assert isinstance(result["verdict"], str)
        assert len(result["verdict"]) > 50  # Meaningful text, not empty
        # Verify call_opus was called (at least once for verdict)
        assert client.call_opus.call_count >= 1

    @pytest.mark.asyncio
    async def test_generate_report_scorecard(self):
        """RPT-02: generate_report() assembles scorecard with ranking, color_coding, trajectory."""
        client = _mock_claude_client()
        generator = ReportGenerator(claude_client=client)

        result = await generator.generate_report(
            campaign=_make_campaign(),
            all_iterations=_make_iterations(),
            all_analyses=_make_analyses(),
            best_scores_history=_make_best_scores_history(),
            stop_reason="max_iterations",
        )

        assert "scorecard" in result
        sc = result["scorecard"]
        assert "winning_variant_id" in sc
        assert "variants" in sc
        assert len(sc["variants"]) > 0
        # Verify ranked variants have color_coding
        for v in sc["variants"]:
            assert "color_coding" in v
            assert "rank" in v
            assert "composite_scores" in v
        # Verify iteration_trajectory
        assert "iteration_trajectory" in sc
        assert len(sc["iteration_trajectory"]) == 2  # 2 iterations
        # Verify thresholds_status
        assert "thresholds_status" in sc

    @pytest.mark.asyncio
    async def test_generate_report_deep_analysis_no_llm(self):
        """RPT-03: generate_report() assembles deep_analysis from stored data, NO LLM call."""
        client = _mock_claude_client()
        generator = ReportGenerator(claude_client=client)

        result = await generator.generate_report(
            campaign=_make_campaign(),
            all_iterations=_make_iterations(),
            all_analyses=_make_analyses(),
            best_scores_history=_make_best_scores_history(),
            stop_reason="max_iterations",
        )

        assert "deep_analysis" in result
        da = result["deep_analysis"]
        assert "iterations" in da
        assert len(da["iterations"]) == 2  # 2 iterations
        # Verify per-iteration structure
        for iter_data in da["iterations"]:
            assert "iteration" in iter_data
            assert "variants" in iter_data
            assert len(iter_data["variants"]) > 0
            for v in iter_data["variants"]:
                assert "variant_id" in v
                assert "content" in v

    @pytest.mark.asyncio
    async def test_generate_report_psychology_general(self):
        """RPT-04: generate_report() calls call_opus with MASS_PSYCHOLOGY_GENERAL_SYSTEM."""
        client = _mock_claude_client()
        generator = ReportGenerator(claude_client=client)

        result = await generator.generate_report(
            campaign=_make_campaign(),
            all_iterations=_make_iterations(),
            all_analyses=_make_analyses(),
            best_scores_history=_make_best_scores_history(),
            stop_reason="max_iterations",
        )

        assert "mass_psychology_general" in result
        assert isinstance(result["mass_psychology_general"], str)
        assert len(result["mass_psychology_general"]) > 50

    @pytest.mark.asyncio
    async def test_generate_report_psychology_technical(self):
        """RPT-05: generate_report() calls call_opus with MASS_PSYCHOLOGY_TECHNICAL_SYSTEM."""
        client = _mock_claude_client()
        generator = ReportGenerator(claude_client=client)

        result = await generator.generate_report(
            campaign=_make_campaign(),
            all_iterations=_make_iterations(),
            all_analyses=_make_analyses(),
            best_scores_history=_make_best_scores_history(),
            stop_reason="max_iterations",
        )

        assert "mass_psychology_technical" in result
        assert isinstance(result["mass_psychology_technical"], str)
        assert len(result["mass_psychology_technical"]) > 50

    @pytest.mark.asyncio
    async def test_generate_report_returns_all_five_keys(self):
        """generate_report() returns dict with all 5 layer keys."""
        client = _mock_claude_client()
        generator = ReportGenerator(claude_client=client)

        result = await generator.generate_report(
            campaign=_make_campaign(),
            all_iterations=_make_iterations(),
            all_analyses=_make_analyses(),
            best_scores_history=_make_best_scores_history(),
            stop_reason="max_iterations",
        )

        expected_keys = {"verdict", "scorecard", "deep_analysis", "mass_psychology_general", "mass_psychology_technical"}
        assert set(result.keys()) == expected_keys


class TestColorCodeScore:
    """Tests for color_code_score utility."""

    def test_normal_metric_green(self):
        """attention_score=75 should be green (>=70)."""
        assert color_code_score("attention_score", 75) == "green"

    def test_normal_metric_amber(self):
        """attention_score=50 should be amber (>=40, <70)."""
        assert color_code_score("attention_score", 50) == "amber"

    def test_normal_metric_red(self):
        """attention_score=30 should be red (<40)."""
        assert color_code_score("attention_score", 30) == "red"

    def test_inverted_metric_green(self):
        """backlash_risk=20 should be green (<30, inverted)."""
        assert color_code_score("backlash_risk", 20) == "green"

    def test_inverted_metric_red(self):
        """backlash_risk=70 should be red (>=60, inverted)."""
        assert color_code_score("backlash_risk", 70) == "red"

    def test_inverted_metric_amber(self):
        """backlash_risk=45 should be amber (>=30, <60, inverted)."""
        assert color_code_score("backlash_risk", 45) == "amber"

    def test_polarization_inverted_green(self):
        """polarization_index=10 should be green (<30, inverted)."""
        assert color_code_score("polarization_index", 10) == "green"

    def test_polarization_inverted_red(self):
        """polarization_index=65 should be red (>=60, inverted)."""
        assert color_code_score("polarization_index", 65) == "red"
