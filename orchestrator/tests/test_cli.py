"""
Smoke tests for the CLI entry point (orchestrator/cli.py).

All external dependencies (Claude, TRIBE, MiroFish, Database) are mocked
so tests run entirely offline. Verifies argument parsing, wiring, and
the full run_campaign flow.
"""

import argparse
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.cli import parse_args, run_campaign, main, _print_summary


# ---------------------------------------------------------------------------
# parse_args tests
# ---------------------------------------------------------------------------

class TestParseArgs:
    """Verify argparse configuration for the CLI."""

    def test_parse_args_basic(self):
        """Basic required flags are parsed correctly."""
        args = parse_args([
            "--seed-content", "A test seed content that is long enough to pass validation " * 5,
            "--prediction-question", "How will users react?",
            "--demographic", "tech_professionals",
        ])
        assert "test seed content" in args.seed_content
        assert args.prediction_question == "How will users react?"
        assert args.demographic == "tech_professionals"
        assert args.agent_count == 40  # default
        assert args.verbose is False
        assert args.output is None

    def test_parse_args_seed_file(self):
        """--seed-file flag is parsed correctly."""
        args = parse_args([
            "--seed-file", "content.txt",
            "--prediction-question", "Will this go viral?",
            "--demographic", "gen_z_consumers",
        ])
        assert args.seed_file == "content.txt"
        assert args.seed_content is None

    def test_parse_args_all_optional_flags(self):
        """All optional flags are parsed."""
        args = parse_args([
            "--seed-content", "Some content " * 20,
            "--prediction-question", "Test question?",
            "--demographic", "custom",
            "--demographic-custom", "Ages 25-35 urban professionals",
            "--agent-count", "80",
            "--constraints", "Must be professional tone",
            "--output", "results.json",
            "--verbose",
        ])
        assert args.demographic_custom == "Ages 25-35 urban professionals"
        assert args.agent_count == 80
        assert args.constraints == "Must be professional tone"
        assert args.output == "results.json"
        assert args.verbose is True

    def test_parse_args_missing_required(self):
        """argparse exits when required args are missing."""
        with pytest.raises(SystemExit):
            parse_args([])

    def test_parse_args_missing_demographic(self):
        """argparse exits when --demographic is missing."""
        with pytest.raises(SystemExit):
            parse_args([
                "--seed-content", "Some content",
                "--prediction-question", "Test?",
            ])

    def test_parse_args_mutually_exclusive(self):
        """Cannot use both --seed-content and --seed-file."""
        with pytest.raises(SystemExit):
            parse_args([
                "--seed-content", "Some content",
                "--seed-file", "file.txt",
                "--prediction-question", "Test?",
                "--demographic", "tech_professionals",
            ])


# ---------------------------------------------------------------------------
# run_campaign integration test (fully mocked)
# ---------------------------------------------------------------------------

class TestRunCampaignMocked:
    """Verify the full wiring of run_campaign with all dependencies mocked."""

    @pytest.mark.asyncio
    async def test_run_campaign_mocked(self, tmp_path):
        """
        Mock all external dependencies and verify run_campaign completes,
        returning a dict with the expected top-level keys.
        """
        seed = "A comprehensive test seed content for the campaign " * 5

        args = argparse.Namespace(
            seed_content=seed,
            seed_file=None,
            prediction_question="How will tech professionals respond?",
            demographic="tech_professionals",
            demographic_custom=None,
            agent_count=40,
            constraints=None,
            output=None,
            verbose=False,
        )

        # Canned data for mock returns
        fake_campaign_id = "test-campaign-001"
        fake_variants = [
            {"id": "v1", "content": "Variant one content", "strategy": "direct_appeal"},
            {"id": "v2", "content": "Variant two content", "strategy": "social_proof"},
            {"id": "v3", "content": "Variant three content", "strategy": "urgency"},
        ]
        fake_tribe_scores = {
            "attention_capture": 75.0,
            "emotional_resonance": 68.0,
            "memory_encoding": 72.0,
            "reward_response": 65.0,
            "threat_detection": 20.0,
            "cognitive_load": 45.0,
            "social_relevance": 80.0,
        }
        fake_analysis = {
            "per_variant_assessment": [],
            "ranking": ["v1", "v3", "v2"],
            "cross_system_insights": ["Neural attention correlates with social sharing"],
            "recommendations_for_next_iteration": ["Increase emotional hooks"],
        }
        fake_result = {
            "campaign_id": fake_campaign_id,
            "iteration_number": 1,
            "variants": fake_variants,
            "tribe_scores": [fake_tribe_scores, None, fake_tribe_scores],
            "mirofish_metrics": [None, None, None],
            "composite_scores": [
                {"attention_score": 72.2, "virality_potential": None,
                 "backlash_risk": None, "memory_durability": None,
                 "conversion_potential": 51.9, "audience_fit": 65.0,
                 "polarization_index": None},
            ] * 3,
            "analysis": fake_analysis,
            "system_availability": {"tribe_available": True, "mirofish_available": False},
            "warnings": ["MiroFish simulator unavailable -- simulation metrics will be skipped"],
        }

        # Mock all the components
        mock_db = AsyncMock()
        mock_store = AsyncMock()
        mock_store.create_campaign.return_value = MagicMock(id=fake_campaign_id)

        mock_runner = AsyncMock()
        mock_runner.run_single_iteration.return_value = fake_result

        db_path = str(tmp_path / "test.db")

        with patch("orchestrator.cli.Database", return_value=mock_db) as mock_db_cls, \
             patch("orchestrator.cli.CampaignStore", return_value=mock_store), \
             patch("orchestrator.cli.ClaudeClient") as mock_claude_cls, \
             patch("orchestrator.cli.TribeClient") as mock_tribe_cls, \
             patch("orchestrator.cli.MirofishClient") as mock_mirofish_cls, \
             patch("orchestrator.cli.VariantGenerator") as mock_vargen_cls, \
             patch("orchestrator.cli.TribeScoringPipeline") as mock_tribe_pipe_cls, \
             patch("orchestrator.cli.MirofishRunner") as mock_miro_runner_cls, \
             patch("orchestrator.cli.ResultAnalyzer") as mock_analyzer_cls, \
             patch("orchestrator.cli.CampaignRunner", return_value=mock_runner), \
             patch("orchestrator.cli.settings") as mock_settings, \
             patch("orchestrator.cli.httpx.AsyncClient") as mock_http:

            mock_settings.database_path_absolute = tmp_path / "test.db"
            mock_settings.tribe_scorer_url = "http://localhost:8001"
            mock_settings.mirofish_url = "http://localhost:5000"

            # Make httpx.AsyncClient return an AsyncMock with aclose
            mock_http_instance = AsyncMock()
            mock_http.return_value = mock_http_instance

            result = await run_campaign(args)

        # Verify result structure
        assert isinstance(result, dict)
        assert "campaign_id" in result
        assert "variants" in result
        assert "tribe_scores" in result
        assert "mirofish_metrics" in result
        assert "composite_scores" in result
        assert "analysis" in result
        assert "system_availability" in result
        assert "warnings" in result

        # Verify the pipeline was invoked
        mock_db.connect.assert_awaited_once()
        mock_store.create_campaign.assert_awaited_once()
        mock_runner.run_single_iteration.assert_awaited_once()
        mock_db.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_campaign_with_seed_file(self, tmp_path):
        """Verify that --seed-file reads content from file."""
        seed_content = "A test content from file that is sufficiently long " * 5
        seed_file = tmp_path / "seed.txt"
        seed_file.write_text(seed_content, encoding="utf-8")

        args = argparse.Namespace(
            seed_content=None,
            seed_file=str(seed_file),
            prediction_question="Test question for file-based seed?",
            demographic="tech_professionals",
            demographic_custom=None,
            agent_count=40,
            constraints=None,
            output=None,
            verbose=False,
        )

        fake_result = {
            "campaign_id": "test-002",
            "iteration_number": 1,
            "variants": [],
            "tribe_scores": [],
            "mirofish_metrics": [],
            "composite_scores": [],
            "analysis": {},
            "system_availability": {"tribe_available": False, "mirofish_available": False},
            "warnings": [],
        }

        mock_db = AsyncMock()
        mock_store = AsyncMock()
        mock_store.create_campaign.return_value = MagicMock(id="test-002")
        mock_runner = AsyncMock()
        mock_runner.run_single_iteration.return_value = fake_result

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

        # Verify the seed content from file was used (campaign was created)
        create_call = mock_store.create_campaign.call_args
        request_arg = create_call[0][0]
        assert seed_content.strip() in request_arg.seed_content


# ---------------------------------------------------------------------------
# _print_summary test
# ---------------------------------------------------------------------------

class TestPrintSummary:
    """Verify the summary printer handles various result shapes."""

    def test_print_summary_full_result(self, capsys):
        """Print a full result with all fields populated."""
        result = {
            "system_availability": {"tribe_available": True, "mirofish_available": True},
            "warnings": [],
            "variants": [
                {"id": "v1", "content": "Content for variant one", "strategy": "direct_appeal"},
            ],
            "tribe_scores": [
                {"attention_capture": 75.0, "emotional_resonance": 68.0},
            ],
            "mirofish_metrics": [
                {"organic_shares": 15, "sentiment_drift": 0.12, "sentiment_trajectory": [0.1, 0.2]},
            ],
            "composite_scores": [
                {"attention_score": 72.2, "virality_potential": 45.1},
            ],
            "analysis": {
                "ranking": ["v1"],
                "cross_system_insights": ["High attention maps to sharing behavior"],
                "recommendations_for_next_iteration": ["Try more emotional hooks"],
            },
        }
        _print_summary(result)
        captured = capsys.readouterr()
        assert "CAMPAIGN RESULTS" in captured.out
        assert "TRIBE v2: Available" in captured.out
        assert "MiroFish: Available" in captured.out
        assert "v1" in captured.out
        assert "RANKING: v1" in captured.out
        assert "CROSS-SYSTEM INSIGHTS:" in captured.out

    def test_print_summary_empty_result(self, capsys):
        """Handle empty/minimal result without crashing."""
        result = {
            "system_availability": {},
            "warnings": ["TRIBE unavailable"],
            "variants": [],
            "tribe_scores": [],
            "mirofish_metrics": [],
            "composite_scores": [],
            "analysis": {},
        }
        _print_summary(result)
        captured = capsys.readouterr()
        assert "CAMPAIGN RESULTS" in captured.out
        assert "WARNING: TRIBE unavailable" in captured.out
