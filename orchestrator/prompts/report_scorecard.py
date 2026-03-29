"""
Prompt templates for Layer 2 of the final report: The Scorecard.

The scorecard is primarily computed programmatically (variant ranking,
composite scores, color coding, iteration trajectory). Claude Opus is used
only for generating a 2-3 sentence summary and ranking rationale to
complement the structured data.

Per Open Question #2 in RESEARCH.md: the scorecard data is assembled from DB
data; Opus adds only the narrative summary.
"""

import json
from typing import Any


# -- System prompt ---------------------------------------------------------

REPORT_SCORECARD_SYSTEM = """\
You are a data analyst summarizing the results of a content optimization \
campaign. Your task is to write a concise summary and ranking rationale for \
the scorecard section of the final report.

## What you receive

You will receive:
- The winning variant and its scores
- All variants ranked by performance
- Iteration trajectory showing how scores improved
- Threshold status (whether targets were met)

## What you produce

Return a JSON object with exactly two fields:
- "summary": A 2-3 sentence overview of the results. Who won, by how much, \
  and what drove the ranking.
- "ranking_rationale": A 1-2 sentence explanation of WHY the winning variant \
  outperformed the others. Reference specific score differences.

Keep it tight. No prose, no hedging. Just the facts.
"""


# -- User prompt template --------------------------------------------------

def build_report_scorecard_prompt(
    winning_variant: dict[str, Any],
    all_variants: list[dict[str, Any]],
    iteration_trajectory: list[dict[str, Any]],
    thresholds_status: dict[str, Any],
) -> str:
    """
    Build the user-turn prompt for the scorecard summary.

    Args:
        winning_variant: The top-ranked variant dict with composite_scores.
        all_variants: All variants ranked by performance.
        iteration_trajectory: List of per-iteration best score snapshots.
        thresholds_status: Dict with all_met and per_threshold booleans.

    Returns:
        Formatted user-turn prompt string asking for summary + ranking_rationale.
    """
    lines: list[str] = []

    lines.append("## Winning variant")
    lines.append(json.dumps(winning_variant, indent=2, default=str))
    lines.append("")

    lines.append("## All variants (ranked)")
    for v in all_variants:
        lines.append(f"Rank {v.get('rank', '?')}: {v.get('variant_id', '?')} "
                      f"(strategy: {v.get('strategy', '?')})")
        scores = v.get("composite_scores", {})
        if scores:
            score_str = ", ".join(f"{k}: {val}" for k, val in scores.items())
            lines.append(f"  Scores: {score_str}")
    lines.append("")

    lines.append("## Iteration trajectory")
    for t in iteration_trajectory:
        lines.append(f"Iteration {t.get('iteration', '?')}: "
                      f"{json.dumps(t.get('best_scores', {}), default=str)}")
    lines.append("")

    lines.append("## Thresholds")
    lines.append(json.dumps(thresholds_status, indent=2, default=str))
    lines.append("")

    lines.append("## Your task")
    lines.append(
        'Return a JSON object with exactly two fields: "summary" (2-3 sentences) '
        'and "ranking_rationale" (1-2 sentences). No other fields.'
    )

    return "\n".join(lines)
