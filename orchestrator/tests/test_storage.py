"""
Tests for SQLite database layer and campaign store CRUD operations.
"""

import pytest

from orchestrator.api.schemas import CampaignCreateRequest
from orchestrator.storage.campaign_store import CampaignStore
from orchestrator.storage.database import Database


def _make_request(**overrides) -> CampaignCreateRequest:
    """Create a valid CampaignCreateRequest with optional overrides."""
    base = {
        "seed_content": "A" * 150,
        "prediction_question": "How will this content resonate with the target audience?",
        "demographic": "tech_professionals",
    }
    base.update(overrides)
    return CampaignCreateRequest(**base)


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


class TestSchemaInit:
    """Tests for database schema initialization."""

    async def test_schema_init(self, db: Database):
        """All 3 tables (campaigns, iterations, analyses) should exist after connect."""
        cursor = await db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        rows = await cursor.fetchall()
        table_names = sorted([row["name"] for row in rows])
        assert "analyses" in table_names
        assert "campaigns" in table_names
        assert "iterations" in table_names


class TestCampaignCRUD:
    """Tests for campaign create, read, list, delete operations."""

    async def test_create_campaign(self, store: CampaignStore):
        """Creating a campaign returns a CampaignResponse with status='pending' and valid UUID."""
        response = await store.create_campaign(_make_request())
        assert response.status == "pending"
        assert response.id is not None
        assert len(response.id) == 36  # UUID4 format: 8-4-4-4-12
        assert response.seed_content == "A" * 150
        assert response.demographic == "tech_professionals"
        assert response.agent_count == 40
        assert response.max_iterations == 4

    async def test_get_campaign(self, store: CampaignStore):
        """Creating then retrieving a campaign returns matching fields."""
        created = await store.create_campaign(_make_request())
        retrieved = await store.get_campaign(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.status == "pending"
        assert retrieved.seed_content == created.seed_content
        assert retrieved.prediction_question == created.prediction_question
        assert retrieved.demographic == created.demographic
        assert retrieved.agent_count == created.agent_count
        assert retrieved.max_iterations == created.max_iterations

    async def test_get_campaign_not_found(self, store: CampaignStore):
        """Getting a nonexistent campaign returns None."""
        result = await store.get_campaign("nonexistent-id")
        assert result is None

    async def test_list_campaigns(self, store: CampaignStore):
        """Creating 3 campaigns returns a list of 3 ordered by created_at DESC."""
        for i in range(3):
            await store.create_campaign(
                _make_request(seed_content=f"Campaign {i} content " + "x" * 100)
            )

        result = await store.list_campaigns()
        assert result.total == 3
        assert len(result.campaigns) == 3
        # Verify DESC order (most recent first)
        for i in range(len(result.campaigns) - 1):
            assert result.campaigns[i].created_at >= result.campaigns[i + 1].created_at

    async def test_delete_campaign(self, store: CampaignStore):
        """Deleting a campaign removes it; get returns None."""
        created = await store.create_campaign(_make_request())
        deleted = await store.delete_campaign(created.id)
        assert deleted is True

        retrieved = await store.get_campaign(created.id)
        assert retrieved is None

    async def test_delete_nonexistent_campaign(self, store: CampaignStore):
        """Deleting a nonexistent campaign returns False."""
        result = await store.delete_campaign("nonexistent-id")
        assert result is False


class TestCampaignStatusUpdates:
    """Tests for campaign status transition logic."""

    async def test_update_campaign_status_running(self, store: CampaignStore):
        """Setting status to 'running' sets started_at."""
        created = await store.create_campaign(_make_request())
        await store.update_campaign_status(created.id, "running")

        updated = await store.get_campaign(created.id)
        assert updated.status == "running"
        assert updated.started_at is not None
        assert updated.completed_at is None

    async def test_update_campaign_status_completed(self, store: CampaignStore):
        """Setting status to 'completed' sets completed_at."""
        created = await store.create_campaign(_make_request())
        await store.update_campaign_status(created.id, "running")
        await store.update_campaign_status(created.id, "completed")

        updated = await store.get_campaign(created.id)
        assert updated.status == "completed"
        assert updated.started_at is not None
        assert updated.completed_at is not None

    async def test_update_campaign_status_failed_with_error(
        self, store: CampaignStore
    ):
        """Setting status to 'failed' with an error message persists both."""
        created = await store.create_campaign(_make_request())
        await store.update_campaign_status(
            created.id, "failed", error="TRIBE v2 timeout"
        )

        updated = await store.get_campaign(created.id)
        assert updated.status == "failed"
        assert updated.error == "TRIBE v2 timeout"
        assert updated.completed_at is not None


class TestIterationOperations:
    """Tests for iteration save and retrieval with JSON roundtrip."""

    async def test_save_iteration(self, store: CampaignStore):
        """Saving an iteration with TRIBE scores and MiroFish metrics roundtrips correctly."""
        campaign = await store.create_campaign(_make_request())

        tribe_data = {
            "attention_capture": 0.85,
            "emotional_resonance": 0.72,
            "memory_encoding": 0.68,
            "reward_response": 0.91,
            "threat_detection": 0.45,
            "cognitive_load": 0.33,
            "social_relevance": 0.77,
        }
        mirofish_data = {
            "organic_shares": 150,
            "sentiment_trajectory": [0.5, 0.6, 0.55, 0.7],
            "counter_narrative_count": 3,
            "peak_virality_cycle": 4,
            "sentiment_drift": 0.15,
            "coalition_formation": 2,
            "influence_concentration": 0.45,
            "platform_divergence": 0.22,
        }
        composite_data = {
            "attention_score": 0.8,
            "virality_potential": 0.6,
        }

        iteration_id = await store.save_iteration(
            campaign_id=campaign.id,
            iteration_number=1,
            variant_id="v1",
            variant_content="Test variant content for persistence verification.",
            variant_strategy="direct_appeal",
            tribe_scores=tribe_data,
            mirofish_metrics=mirofish_data,
            composite_scores=composite_data,
        )

        assert iteration_id is not None
        assert len(iteration_id) == 36  # UUID4

        # Retrieve and verify JSON roundtrip
        iterations = await store.get_iterations(campaign.id)
        assert len(iterations) == 1

        it = iterations[0]
        assert it.id == iteration_id
        assert it.campaign_id == campaign.id
        assert it.iteration_number == 1
        assert it.variant_id == "v1"
        assert it.variant_content == "Test variant content for persistence verification."
        assert it.variant_strategy == "direct_appeal"

        # Verify TRIBE scores deserialized correctly
        assert it.tribe_scores is not None
        assert it.tribe_scores.attention_capture == 0.85
        assert it.tribe_scores.social_relevance == 0.77

        # Verify MiroFish metrics deserialized correctly
        assert it.mirofish_metrics is not None
        assert it.mirofish_metrics.organic_shares == 150
        assert it.mirofish_metrics.sentiment_trajectory == [0.5, 0.6, 0.55, 0.7]
        assert it.mirofish_metrics.coalition_formation == 2

        # Verify composite scores deserialized correctly
        assert it.composite_scores is not None
        assert it.composite_scores.attention_score == 0.8
        assert it.composite_scores.virality_potential == 0.6
        assert it.composite_scores.backlash_risk is None  # Not set

    async def test_get_iterations_by_number(self, store: CampaignStore):
        """Filtering iterations by iteration_number returns only matching records."""
        campaign = await store.create_campaign(_make_request())

        # Save iterations for two different iteration numbers
        await store.save_iteration(
            campaign.id, 1, "v1", "Iter 1 variant 1", None, None, None, None
        )
        await store.save_iteration(
            campaign.id, 1, "v2", "Iter 1 variant 2", None, None, None, None
        )
        await store.save_iteration(
            campaign.id, 2, "v1", "Iter 2 variant 1", None, None, None, None
        )

        iter_1 = await store.get_iterations(campaign.id, iteration_number=1)
        assert len(iter_1) == 2

        iter_2 = await store.get_iterations(campaign.id, iteration_number=2)
        assert len(iter_2) == 1
        assert iter_2[0].variant_content == "Iter 2 variant 1"


class TestAnalysisOperations:
    """Tests for analysis save and retrieval with JSON roundtrip."""

    async def test_save_analysis(self, store: CampaignStore):
        """Saving an analysis with analysis_json dict roundtrips correctly."""
        campaign = await store.create_campaign(_make_request())

        analysis_data = {
            "summary": "Cross-system analysis shows strong attention but moderate backlash risk.",
            "recommendations": [
                "Soften threat language in paragraph 2",
                "Add social proof elements",
            ],
            "confidence": 0.85,
        }
        availability = {"tribe_available": True, "mirofish_available": True}

        analysis_id = await store.save_analysis(
            campaign_id=campaign.id,
            iteration_number=1,
            analysis_json=analysis_data,
            system_availability=availability,
        )

        assert analysis_id is not None
        assert len(analysis_id) == 36  # UUID4

        # Retrieve through get_campaign which nests analyses
        retrieved = await store.get_campaign(campaign.id)
        assert retrieved.analyses is not None
        assert len(retrieved.analyses) == 1

        analysis = retrieved.analyses[0]
        assert analysis.id == analysis_id
        assert analysis.campaign_id == campaign.id
        assert analysis.iteration_number == 1
        assert analysis.analysis_json["summary"].startswith("Cross-system analysis")
        assert len(analysis.analysis_json["recommendations"]) == 2
        assert analysis.analysis_json["confidence"] == 0.85
        assert analysis.system_availability == {
            "tribe_available": True,
            "mirofish_available": True,
        }


class TestCascadeDelete:
    """Tests for CASCADE delete behavior."""

    async def test_cascade_delete(self, store: CampaignStore, db: Database):
        """Deleting a campaign also deletes its iterations and analyses."""
        campaign = await store.create_campaign(_make_request())

        # Add iterations
        await store.save_iteration(
            campaign.id, 1, "v1", "Variant 1", "strategy_a", None, None, None
        )
        await store.save_iteration(
            campaign.id, 1, "v2", "Variant 2", "strategy_b", None, None, None
        )

        # Add analysis
        await store.save_analysis(
            campaign.id, 1, {"summary": "Test analysis"}, None
        )

        # Verify data exists
        iterations = await store.get_iterations(campaign.id)
        assert len(iterations) == 2

        # Delete campaign
        deleted = await store.delete_campaign(campaign.id)
        assert deleted is True

        # Verify cascade: iterations and analyses should be gone
        cursor = await db.conn.execute(
            "SELECT COUNT(*) as cnt FROM iterations WHERE campaign_id = ?",
            (campaign.id,),
        )
        row = await cursor.fetchone()
        assert row["cnt"] == 0

        cursor = await db.conn.execute(
            "SELECT COUNT(*) as cnt FROM analyses WHERE campaign_id = ?",
            (campaign.id,),
        )
        row = await cursor.fetchone()
        assert row["cnt"] == 0
