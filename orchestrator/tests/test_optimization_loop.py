"""
Tests for the optimization loop helpers: threshold checking, convergence
detection, time estimation, best variant finder, and iteration feedback builder.

Covers:
- check_thresholds: normal, inverted (backlash_risk, polarization_index), None, empty
- compute_improvement: positive, negative, None scores, zero previous
- is_converged: off-by-one safe (needs consecutive_count entries)
- TimeEstimator: formula-based pre-run, runtime-refined remaining
- find_best_composite: selects variant with highest adjusted average
- build_iteration_feedback: transforms result + analysis into prompt format
"""

import pytest

from orchestrator.engine.optimization_loop import (
    INVERTED_SCORES,
    TimeEstimator,
    build_iteration_feedback,
    check_thresholds,
    compute_improvement,
    find_best_composite,
    is_converged,
)


# ── check_thresholds ────────────────────────────────────────────────────────


class TestCheckThresholds:
    def test_higher_is_better_met(self):
        """Actual >= target for standard metrics means met."""
        all_met, status = check_thresholds(
            {"attention_score": 80.0, "backlash_risk": 10.0},
            {"attention_score": 70.0},
        )
        assert all_met is True
        assert status == {"attention_score": True}

    def test_higher_is_better_not_met(self):
        """Actual < target for standard metrics means not met."""
        all_met, status = check_thresholds(
            {"attention_score": 60.0},
            {"attention_score": 70.0},
        )
        assert all_met is False
        assert status == {"attention_score": False}

    def test_inverted_met(self):
        """For inverted scores (backlash_risk), actual <= target means met."""
        all_met, status = check_thresholds(
            {"backlash_risk": 20.0},
            {"backlash_risk": 30.0},
        )
        assert all_met is True
        assert status == {"backlash_risk": True}

    def test_inverted_not_met(self):
        """For inverted scores (backlash_risk), actual > target means not met."""
        all_met, status = check_thresholds(
            {"backlash_risk": 40.0},
            {"backlash_risk": 30.0},
        )
        assert all_met is False
        assert status == {"backlash_risk": False}

    def test_none_score_never_meets(self):
        """None actual score never meets threshold."""
        all_met, status = check_thresholds(
            {"attention_score": None},
            {"attention_score": 70.0},
        )
        assert all_met is False
        assert status == {"attention_score": False}

    def test_multiple_thresholds_all_met(self):
        """all_met=True only when ALL thresholds pass (per D-07)."""
        all_met, status = check_thresholds(
            {"attention_score": 80.0, "backlash_risk": 10.0, "virality_potential": 60.0},
            {"attention_score": 70.0, "backlash_risk": 30.0, "virality_potential": 50.0},
        )
        assert all_met is True
        assert status == {
            "attention_score": True,
            "backlash_risk": True,
            "virality_potential": True,
        }

    def test_multiple_thresholds_one_fails(self):
        """all_met=False when any threshold fails."""
        all_met, status = check_thresholds(
            {"attention_score": 80.0, "backlash_risk": 40.0},
            {"attention_score": 70.0, "backlash_risk": 30.0},
        )
        assert all_met is False
        assert status["attention_score"] is True
        assert status["backlash_risk"] is False

    def test_empty_thresholds(self):
        """Empty thresholds dict returns (False, {})."""
        all_met, status = check_thresholds(
            {"attention_score": 80.0},
            {},
        )
        assert all_met is False
        assert status == {}


# ── compute_improvement ─────────────────────────────────────────────────────


class TestComputeImprovement:
    def test_positive_improvement(self):
        """Improvement from 75 to 80 is ~6.67%."""
        result = compute_improvement(
            {"attention_score": 80.0},
            {"attention_score": 75.0},
        )
        assert abs(result - 6.67) < 0.1

    def test_all_none_returns_zero(self):
        """All None scores yields 0.0 improvement."""
        result = compute_improvement(
            {"attention_score": None, "virality_potential": None},
            {"attention_score": None, "virality_potential": None},
        )
        assert result == 0.0

    def test_inverted_score_improvement(self):
        """For backlash_risk, decrease is improvement (positive %)."""
        result = compute_improvement(
            {"backlash_risk": 20.0},
            {"backlash_risk": 30.0},
        )
        # Decrease from 30 to 20 is improvement for inverted: ((30-20)/30)*100 = 33.3%
        assert result > 0.0

    def test_zero_previous_skipped(self):
        """Zero previous score is skipped to avoid division by zero."""
        result = compute_improvement(
            {"attention_score": 50.0, "virality_potential": 60.0},
            {"attention_score": 0.0, "virality_potential": 50.0},
        )
        # Only virality counted: (60-50)/50 * 100 = 20%
        assert abs(result - 20.0) < 0.1

    def test_mixed_none_and_values(self):
        """Only non-None pairs contribute to improvement calculation."""
        result = compute_improvement(
            {"attention_score": 90.0, "virality_potential": None},
            {"attention_score": 80.0, "virality_potential": 60.0},
        )
        # Only attention: (90-80)/80 * 100 = 12.5%
        assert abs(result - 12.5) < 0.1


# ── is_converged ────────────────────────────────────────────────────────────


class TestIsConverged:
    def test_converged_two_below_threshold(self):
        """Two consecutive values below 5% -> converged."""
        assert is_converged([3.0, 4.0], threshold_pct=5.0, consecutive_count=2) is True

    def test_not_converged_only_one(self):
        """Only 1 data point, need 2 -> not converged."""
        assert is_converged([3.0], threshold_pct=5.0, consecutive_count=2) is False

    def test_not_converged_second_above(self):
        """Second value >= threshold -> not converged."""
        assert is_converged([3.0, 8.0], threshold_pct=5.0, consecutive_count=2) is False

    def test_empty_history(self):
        """Empty history -> not converged."""
        assert is_converged([], threshold_pct=5.0, consecutive_count=2) is False

    def test_converged_with_earlier_high(self):
        """Earlier high value doesn't matter if last 2 are below threshold."""
        assert is_converged([15.0, 3.0, 4.0], threshold_pct=5.0, consecutive_count=2) is True


# ── TimeEstimator ───────────────────────────────────────────────────────────


class TestTimeEstimator:
    def test_pre_run_40_agents_4_iterations(self):
        """40 agents, 4 iterations: (40/40) * 4 * 3.0 = 12.0 minutes."""
        estimator = TimeEstimator()
        assert estimator.estimate_pre_run(agent_count=40, max_iterations=4) == 12.0

    def test_pre_run_80_agents_2_iterations(self):
        """80 agents, 2 iterations: (80/40) * 2 * 3.0 = 12.0 minutes."""
        estimator = TimeEstimator()
        assert estimator.estimate_pre_run(agent_count=80, max_iterations=2) == 12.0

    def test_remaining_with_observed_durations(self):
        """With observed step durations, uses moving average for projection."""
        estimator = TimeEstimator()
        # Observed 3 steps at 30s each, currently on iteration 1 step 3,
        # total 5 steps/iter, max 4 iterations.
        result = estimator.estimate_remaining(
            current_iteration=1,
            current_step=3,
            total_steps_per_iteration=5,
            max_iterations=4,
            observed_step_durations=[30.0, 30.0, 30.0],
        )
        # Remaining: 2 steps this iter + 3*5=15 steps remaining iters = 17 steps
        # 17 * 30s / 60 = 8.5 minutes
        assert abs(result - 8.5) < 0.01

    def test_remaining_without_observed_durations(self):
        """Without observed durations, falls back to formula."""
        estimator = TimeEstimator()
        result = estimator.estimate_remaining(
            current_iteration=2,
            current_step=1,
            total_steps_per_iteration=5,
            max_iterations=4,
            observed_step_durations=[],
        )
        # Fallback: remaining iterations = 4-2 = 2, 2 * 3.0 = 6.0 minutes
        assert result == 6.0


# ── find_best_composite ─────────────────────────────────────────────────────


class TestFindBestComposite:
    def test_selects_best_by_adjusted_average(self):
        """Returns the scores dict with the highest adjusted average."""
        scores_a = {"attention_score": 80.0, "backlash_risk": 10.0, "virality_potential": 60.0}
        scores_b = {"attention_score": 70.0, "backlash_risk": 40.0, "virality_potential": 50.0}
        # a: (80 + (100-10) + 60) / 3 = (80+90+60)/3 = 76.67
        # b: (70 + (100-40) + 50) / 3 = (70+60+50)/3 = 60.0
        result = find_best_composite([scores_a, scores_b])
        assert result is scores_a

    def test_handles_none_values(self):
        """None values are skipped in average calculation."""
        scores_a = {"attention_score": 70.0, "virality_potential": None}
        scores_b = {"attention_score": 80.0, "virality_potential": None}
        result = find_best_composite([scores_a, scores_b])
        assert result is scores_b

    def test_single_entry(self):
        """Single entry returns that entry."""
        scores = {"attention_score": 50.0}
        result = find_best_composite([scores])
        assert result is scores


# ── build_iteration_feedback ────────────────────────────────────────────────


class TestBuildIterationFeedback:
    def test_builds_feedback_list(self):
        """Transforms result + analysis into prompt-compatible format."""
        result = {
            "variants": [
                {"id": "v1", "content": "content1", "strategy": "direct"},
                {"id": "v2", "content": "content2", "strategy": "social_proof"},
            ],
            "tribe_scores": [
                {"attention_capture": 80.0},
                {"attention_capture": 70.0},
            ],
            "mirofish_metrics": [
                {"organic_shares": 12},
                {"organic_shares": 8},
            ],
            "composite_scores": [
                {"attention_score": 75.0},
                {"attention_score": 65.0},
            ],
        }
        analysis = {
            "per_variant_assessment": [
                {"variant_id": "v1", "composite_assessment": "Strong performer."},
                {"variant_id": "v2", "composite_assessment": "Needs work."},
            ],
            "recommendations_for_next_iteration": [
                "Reduce cognitive load.",
                "Increase emotional resonance.",
            ],
        }

        feedback = build_iteration_feedback(result, analysis)

        assert len(feedback) == 2
        assert feedback[0]["variant_id"] == "v1"
        assert feedback[0]["strategy"] == "direct"
        assert feedback[0]["composite_scores"] == {"attention_score": 75.0}
        assert feedback[0]["tribe_scores"] == {"attention_capture": 80.0}
        assert feedback[0]["mirofish_metrics"] == {"organic_shares": 12}
        assert "Strong performer." in feedback[0]["iteration_note"]
        assert "Reduce cognitive load." in feedback[0]["iteration_note"]
        assert "Increase emotional resonance." in feedback[0]["iteration_note"]

    def test_empty_analysis(self):
        """Handles empty analysis gracefully."""
        result = {
            "variants": [{"id": "v1", "content": "c1", "strategy": "s1"}],
            "tribe_scores": [{}],
            "mirofish_metrics": [{}],
            "composite_scores": [{}],
        }
        analysis = {}

        feedback = build_iteration_feedback(result, analysis)

        assert len(feedback) == 1
        assert feedback[0]["variant_id"] == "v1"
        assert "Recommendations:" in feedback[0]["iteration_note"]


# ── INVERTED_SCORES constant ───────────────────────────────────────────────


class TestInvertedScores:
    def test_contains_backlash_and_polarization(self):
        """INVERTED_SCORES contains both inverted metrics."""
        assert "backlash_risk" in INVERTED_SCORES
        assert "polarization_index" in INVERTED_SCORES

    def test_is_set(self):
        """INVERTED_SCORES is a set for O(1) lookup."""
        assert isinstance(INVERTED_SCORES, (set, frozenset))
