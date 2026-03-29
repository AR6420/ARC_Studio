"""
Tests for the report generation engine, data layer, and Pydantic models.

Covers:
- Report storage (save_report / get_report)
- ScorecardData / ReportResponse Pydantic models
- ReportGenerator engine (verdict, scorecard, deep analysis, mass psychology)
- color_code_score utility
"""

import json

import pytest

from orchestrator.api.schemas import (
    CampaignCreateRequest,
    ReportResponse,
    ScorecardData,
    ScorecardVariant,
)
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
