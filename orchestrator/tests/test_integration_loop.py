"""
Integration tests for the optimization loop wiring (Plan 06-03).

Verifies:
1. CLI calls run_campaign() (multi-iteration) instead of run_single_iteration()
2. API auto_start creates a background asyncio task with queue
3. Progress router is mounted on the app at /api prefix
"""

import asyncio
import argparse
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from orchestrator.api.schemas import CampaignResponse


# ── Helpers ──────────────────────────────────────────────────────────────────

VALID_SEED_CONTENT = (
    "This is a comprehensive product launch announcement for our new AI-powered "
    "content optimization platform that helps marketing teams create better content. "
    "It uses neural response prediction and social simulation to iteratively improve messaging."
)


def _make_campaign_response(campaign_id: str = "campaign-int-001") -> CampaignResponse:
    """Create a realistic mock campaign response."""
    return CampaignResponse(
        id=campaign_id,
        status="pending",
        seed_content=VALID_SEED_CONTENT,
        prediction_question="How will tech professionals respond to this product launch?",
        demographic="tech_professionals",
        demographic_custom=None,
        agent_count=40,
        max_iterations=4,
        thresholds={"attention_score": 70.0},
        constraints=None,
        created_at="2026-03-29T00:00:00Z",
    )


def _make_run_campaign_result(campaign_id: str = "campaign-int-001") -> dict:
    """Create a multi-iteration result dict matching run_campaign() output."""
    return {
        "campaign_id": campaign_id,
        "iterations": [
            {
                "campaign_id": campaign_id,
                "iteration_number": 1,
                "variants": [{"id": "v1", "content": "Variant 1", "strategy": "direct"}],
                "tribe_scores": [{"attention_capture": 75.0}],
                "mirofish_metrics": [{"organic_shares": 12}],
                "composite_scores": [{"attention_score": 72.0}],
                "analysis": {"ranking": ["v1"], "cross_system_insights": []},
                "system_availability": {"tribe_available": True, "mirofish_available": True},
                "warnings": [],
            },
            {
                "campaign_id": campaign_id,
                "iteration_number": 2,
                "variants": [{"id": "v1b", "content": "Variant 1b", "strategy": "refined"}],
                "tribe_scores": [{"attention_capture": 82.0}],
                "mirofish_metrics": [{"organic_shares": 18}],
                "composite_scores": [{"attention_score": 80.0}],
                "analysis": {"ranking": ["v1b"], "cross_system_insights": ["Improved"]},
                "system_availability": {"tribe_available": True, "mirofish_available": True},
                "warnings": [],
            },
        ],
        "stop_reason": "converged",
        "iterations_completed": 2,
        "best_scores_history": [
            {"attention_score": 72.0},
            {"attention_score": 80.0},
        ],
        "improvement_history": [11.1],
    }


# ── Test 1: CLI uses run_campaign (multi-iteration) ─────────────────────────


class TestCLIMultiIteration:
    """Verify CLI calls run_campaign() instead of run_single_iteration()."""

    @pytest.mark.asyncio
    async def test_cli_run_campaign_multi_iteration(self, tmp_path):
        """
        Mock all external deps and verify that the CLI function calls
        runner.run_campaign() (not run_single_iteration()).
        """
        from orchestrator.cli import run_campaign

        args = argparse.Namespace(
            seed_content=VALID_SEED_CONTENT,
            seed_file=None,
            prediction_question="How will tech professionals respond?",
            demographic="tech_professionals",
            demographic_custom=None,
            agent_count=40,
            max_iterations=2,
            thresholds=None,
            constraints=None,
            output=None,
            verbose=False,
        )

        mock_db = AsyncMock()
        mock_store = AsyncMock()
        mock_store.create_campaign.return_value = MagicMock(id="cli-test-001")

        mock_runner = AsyncMock()
        mock_runner.run_campaign.return_value = _make_run_campaign_result("cli-test-001")

        with patch("orchestrator.cli.Database", return_value=mock_db), \
             patch("orchestrator.cli.CampaignStore", return_value=mock_store), \
             patch("orchestrator.cli.ClaudeClient"), \
             patch("orchestrator.cli.TribeClient"), \
             patch("orchestrator.cli.MirofishClient"), \
             patch("orchestrator.cli.VariantGenerator"), \
             patch("orchestrator.cli.TribeScoringPipeline"), \
             patch("orchestrator.cli.MirofishRunner"), \
             patch("orchestrator.cli.ResultAnalyzer"), \
             patch("orchestrator.cli.CampaignRunner", return_value=mock_runner), \
             patch("orchestrator.cli.settings") as mock_settings, \
             patch("orchestrator.cli.httpx.AsyncClient", return_value=AsyncMock()):

            mock_settings.database_path_absolute = tmp_path / "test.db"
            mock_settings.tribe_scorer_url = "http://localhost:8001"
            mock_settings.mirofish_url = "http://localhost:5000"

            result = await run_campaign(args)

        # CRITICAL: run_campaign must be called, NOT run_single_iteration
        mock_runner.run_campaign.assert_awaited_once()
        mock_runner.run_single_iteration.assert_not_awaited()

        # Verify result has multi-iteration structure
        assert result["iterations_completed"] == 2
        assert result["stop_reason"] == "converged"

        # Verify campaign request had max_iterations
        create_call = mock_store.create_campaign.call_args[0][0]
        assert create_call.max_iterations == 2


# ── Test 2: API auto_start creates background task ──────────────────────────


class TestAPIAutoStart:
    """Verify POST /api/campaigns with auto_start creates background task."""

    @pytest.mark.asyncio
    async def test_api_auto_start_creates_background_task(self, tmp_path):
        """
        Create a test app with mocked state, POST with auto_start=True,
        and verify a task was created in running_tasks and a queue exists.
        """
        from orchestrator.api.campaigns import router as campaigns_router

        app = FastAPI()
        app.include_router(campaigns_router, prefix="/api")

        # Set up app.state manually (lifespan not triggered by ASGITransport)
        from orchestrator.storage.database import Database
        from orchestrator.storage.campaign_store import CampaignStore

        db = Database(str(tmp_path / "test_auto_start.db"))
        await db.connect()

        app.state.db = db
        app.state.campaign_store = CampaignStore(db)
        app.state.running_tasks = {}
        app.state.progress_queues = {}

        # Mock campaign_runner so background task doesn't actually run the pipeline
        mock_campaign_runner = AsyncMock()
        mock_campaign_runner.run_campaign = AsyncMock(return_value=_make_run_campaign_result())
        app.state.campaign_runner = mock_campaign_runner

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            body = {
                "seed_content": VALID_SEED_CONTENT,
                "prediction_question": "How will tech professionals respond?",
                "demographic": "tech_professionals",
                "agent_count": 40,
                "max_iterations": 4,
                "auto_start": True,
            }
            response = await client.post("/api/campaigns", json=body)

        assert response.status_code == 201
        campaign_id = response.json()["id"]

        # A queue should have been created for this campaign
        assert campaign_id in app.state.progress_queues

        # A running task should have been created
        assert campaign_id in app.state.running_tasks
        task = app.state.running_tasks[campaign_id]
        assert isinstance(task, asyncio.Task)

        # Wait briefly for the background task to start/complete
        await asyncio.sleep(0.1)

        # Cleanup
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        await db.close()


# ── Test 3: Progress router is mounted ───────────────────────────────────────


class TestProgressRouterMounted:
    """Verify progress router is mounted on the app from create_app()."""

    def test_progress_router_mounted(self):
        """
        create_app() should produce an app with routes matching
        /api/campaigns/{campaign_id}/progress and /api/estimate.
        """
        from orchestrator.api import create_app

        app = create_app()
        routes = [r.path for r in app.routes]

        # Check progress SSE endpoint
        assert "/api/campaigns/{campaign_id}/progress" in routes, (
            f"Progress SSE route not found. Available routes: {routes}"
        )

        # Check estimate endpoint
        assert "/api/estimate" in routes, (
            f"Estimate route not found. Available routes: {routes}"
        )
