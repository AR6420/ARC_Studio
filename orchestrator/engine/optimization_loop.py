"""
Optimization loop helpers for A.R.C Studio.

Pure functions and a TimeEstimator class that support the multi-iteration
optimization loop in CampaignRunner.run_campaign():

- check_thresholds: Compare top variant's composite scores against user targets (D-06, D-07)
- compute_improvement: Average improvement percentage across iterations
- is_converged: Detect <5% improvement for N consecutive iterations (D-05)
- TimeEstimator: Formula-based pre-run and runtime-refined time estimates (D-11)
- find_best_composite: Select best variant by adjusted composite average (D-06)
- build_iteration_feedback: Transform results into variant generation prompt format (D-01, D-04)
"""

from typing import Any

# Scores where lower is better (per D-06).
# backlash_risk: lower means less backlash
# polarization_index: lower means less polarization
INVERTED_SCORES: set[str] = {"backlash_risk", "polarization_index"}


def check_thresholds(
    best_scores: dict[str, float | None],
    thresholds: dict[str, float],
) -> tuple[bool, dict[str, bool]]:
    """
    Check if all user-enabled thresholds are met by the top variant.

    Per D-06: Compare top variant's composite scores against user-defined targets.
    Per D-07: ALL enabled thresholds must be met for all_met=True.

    For metrics in INVERTED_SCORES: actual <= target means met (lower is better).
    For other metrics: actual >= target means met (higher is better).
    If actual is None, that threshold is NOT met.
    If thresholds dict is empty, return (False, {}).

    Args:
        best_scores: Top variant's composite scores (may contain None values).
        thresholds: User-defined target values keyed by metric name.

    Returns:
        Tuple of (all_met, per_threshold_status).
    """
    if not thresholds:
        return False, {}

    status: dict[str, bool] = {}
    for metric, target in thresholds.items():
        actual = best_scores.get(metric)
        if actual is None:
            status[metric] = False
            continue
        if metric in INVERTED_SCORES:
            status[metric] = actual <= target  # lower is better
        else:
            status[metric] = actual >= target  # higher is better

    all_met = all(status.values()) if status else False
    return all_met, status


def compute_improvement(
    current_scores: dict[str, float | None],
    previous_scores: dict[str, float | None],
) -> float:
    """
    Compute average improvement percentage across all non-None composite scores.

    For INVERTED_SCORES, a decrease in value is improvement (inverted comparison).
    If previous score is 0, that metric is skipped to avoid division by zero.
    If no comparable scores exist, returns 0.0.

    Args:
        current_scores: Current iteration's best composite scores.
        previous_scores: Previous iteration's best composite scores.

    Returns:
        Average improvement percentage (e.g., 6.67 means 6.67% improvement).
    """
    improvements: list[float] = []

    for key in current_scores:
        curr = current_scores.get(key)
        prev = previous_scores.get(key)
        if curr is None or prev is None or prev == 0:
            continue
        if key in INVERTED_SCORES:
            # For inverted scores, decrease is improvement
            pct_change = ((prev - curr) / abs(prev)) * 100
        else:
            pct_change = ((curr - prev) / abs(prev)) * 100
        improvements.append(pct_change)

    return sum(improvements) / len(improvements) if improvements else 0.0


def is_converged(
    improvement_history: list[float],
    threshold_pct: float = 5.0,
    consecutive_count: int = 2,
) -> bool:
    """
    Detect convergence based on consecutive low-improvement iterations.

    Per D-05: <5% improvement for 2 consecutive iterations triggers convergence.
    Per Pitfall 6: Need at least `consecutive_count` entries in history.

    Args:
        improvement_history: List of improvement percentages (one per iteration pair).
        threshold_pct: Maximum improvement percentage to consider converged.
        consecutive_count: How many consecutive low-improvement entries needed.

    Returns:
        True if the last `consecutive_count` entries are all below threshold_pct.
    """
    if len(improvement_history) < consecutive_count:
        return False
    recent = improvement_history[-consecutive_count:]
    return all(imp < threshold_pct for imp in recent)


class TimeEstimator:
    """
    Campaign time estimation with formula-based pre-run and runtime-refined
    remaining estimates.

    Per D-11: Formula-based, refined at runtime as actual durations are observed.
    Per Results.md: baseline ~3 minutes per iteration for 40 agents.
    """

    BASELINE_MINUTES_PER_ITERATION = 3.0  # for 40 agents

    def estimate_pre_run(self, agent_count: int, max_iterations: int) -> float:
        """
        Pre-run time estimate using formula from Results.md.

        Formula: estimated_minutes = (agent_count / 40) * max_iterations * 3.0

        Args:
            agent_count: Number of simulation agents.
            max_iterations: Maximum iterations configured.

        Returns:
            Estimated total campaign duration in minutes.
        """
        return (agent_count / 40) * max_iterations * self.BASELINE_MINUTES_PER_ITERATION

    def estimate_remaining(
        self,
        current_iteration: int,
        current_step: int,
        total_steps_per_iteration: int,
        max_iterations: int,
        observed_step_durations: list[float],
    ) -> float:
        """
        Runtime-refined remaining time estimate.

        If observed durations exist, uses moving average of step durations to
        project remaining time. Otherwise falls back to formula-based estimate
        for remaining iterations.

        Args:
            current_iteration: Current iteration number (1-based).
            current_step: Current step within the iteration (1-based).
            total_steps_per_iteration: Total steps per iteration (typically 5).
            max_iterations: Maximum iterations configured.
            observed_step_durations: List of actual step durations in seconds.

        Returns:
            Estimated remaining time in minutes.
        """
        if not observed_step_durations:
            # Fall back to formula-based estimate for remaining iterations
            remaining_iterations = max_iterations - current_iteration
            return remaining_iterations * self.BASELINE_MINUTES_PER_ITERATION

        avg_step_seconds = sum(observed_step_durations) / len(observed_step_durations)
        remaining_steps_this_iter = total_steps_per_iteration - current_step
        remaining_full_iterations = max_iterations - current_iteration
        total_remaining_steps = (
            remaining_steps_this_iter
            + remaining_full_iterations * total_steps_per_iteration
        )
        return (total_remaining_steps * avg_step_seconds) / 60.0


def find_best_composite(
    composite_scores_list: list[dict[str, float | None]],
) -> dict[str, float | None]:
    """
    Find the best variant's composite scores for threshold checking.

    Per D-06: Compare top variant (not average across variants).
    "Best" = highest average of non-None scores, with inverted metrics
    flipped for ranking (100 - value).

    Args:
        composite_scores_list: List of composite score dicts, one per variant.

    Returns:
        The scores dict of the best variant.
    """
    best_idx = 0
    best_avg = -float("inf")

    for i, scores in enumerate(composite_scores_list):
        values: list[float] = []
        for key, val in scores.items():
            if val is None:
                continue
            if key in INVERTED_SCORES:
                values.append(100.0 - val)  # invert for ranking
            else:
                values.append(val)
        avg = sum(values) / len(values) if values else 0.0
        if avg > best_avg:
            best_avg = avg
            best_idx = i

    return composite_scores_list[best_idx]


def build_iteration_feedback(
    result: dict[str, Any],
    analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Transform a single-iteration result into the format expected by
    build_variant_generation_prompt(previous_iteration_results=...).

    Per D-01: Pass full results (scores + analysis).
    Per D-04: Include Opus improvement instructions as iteration_note.

    Each entry contains: variant_id, strategy, composite_scores, tribe_scores,
    mirofish_metrics, iteration_note (Opus assessment + recommendations).

    Args:
        result: Dict from run_single_iteration() with variants, scores, metrics.
        analysis: Dict from result_analyzer with assessments and recommendations.

    Returns:
        List of feedback dicts compatible with variant generation prompt.
    """
    feedback: list[dict[str, Any]] = []
    variants = result["variants"]
    tribe_scores = result["tribe_scores"]
    mirofish_metrics = result["mirofish_metrics"]
    composite_scores = result["composite_scores"]

    # Get Opus recommendations
    recommendations = analysis.get("recommendations_for_next_iteration", [])
    recs_text = " | ".join(recommendations) if recommendations else ""

    # Per-variant assessments from Opus
    assessments: dict[str, str] = {}
    for assessment in analysis.get("per_variant_assessment", []):
        vid = assessment.get("variant_id", "")
        assessments[vid] = assessment.get("composite_assessment", "")

    for i, variant in enumerate(variants):
        vid = variant["id"]
        entry: dict[str, Any] = {
            "variant_id": vid,
            "strategy": variant.get("strategy", ""),
            "composite_scores": composite_scores[i] if i < len(composite_scores) else {},
            "tribe_scores": tribe_scores[i] if i < len(tribe_scores) else {},
            "mirofish_metrics": mirofish_metrics[i] if i < len(mirofish_metrics) else {},
            "iteration_note": f"{assessments.get(vid, '')} Recommendations: {recs_text}",
        }
        feedback.append(entry)

    return feedback
