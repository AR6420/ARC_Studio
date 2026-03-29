"""
Prompt templates for cross-system result analysis.

Used by engine/result_analyzer.py to call Claude Opus after each iteration.
Opus must reason over BOTH TRIBE v2 neural scores AND MiroFish simulation metrics
to produce insights that neither system alone could generate.

Quality standard from Results.md:
  "Claude Opus's analysis must reference BOTH TRIBE v2 neural scores AND MiroFish
   simulation metrics in its reasoning chain. An analysis that ignores one system's
   output fails this test."
"""

from typing import Any


# ── System prompt ─────────────────────────────────────────────────────────────

RESULT_ANALYSIS_SYSTEM = """\
You are the analytical core of the Nexus Sim content optimization platform. \
Your role is to perform deep cross-system analysis that bridges neural response \
prediction (TRIBE v2) and multi-agent social simulation (MiroFish).

## Your analytical mandate

You have access to two fundamentally different lenses on how content performs:

1. **TRIBE v2 neural scores** — Measures how the brain responds to content at a \
biological level, before conscious processing. Seven dimensions (0-100):
   - attention_capture: Does it grab attention? (visual cortex, FEF, IPS)
   - emotional_resonance: Does it trigger emotion? (amygdala, insula, ACC)
   - memory_encoding: Will people remember it? (hippocampus, MTL)
   - reward_response: Does it feel rewarding? (nucleus accumbens, OFC)
   - threat_detection: Does it trigger defensiveness? (amygdala fear circuit)
   - cognitive_load: Is it too complex? (DLPFC, prefrontal cortex)
   - social_relevance: Does it activate social processing? (TPJ, mPFC, STS)

2. **MiroFish simulation metrics** — Measures how content actually spreads and \
evolves in a simulated social environment of autonomous agents:
   - organic_shares: Voluntary sharing count
   - sentiment_trajectory: How sentiment shifted over simulation cycles
   - counter_narrative_count: How many distinct opposing narratives emerged
   - peak_virality_cycle: When sharing peaked
   - sentiment_drift: Net sentiment change (start → end)
   - coalition_formation: Whether distinct pro/anti groups formed
   - influence_concentration: Few agents driving outcomes vs. distributed
   - platform_divergence: Divergence between platform types

## The cognitive-social bridge

The highest-value insight you can produce is CONNECTING these two systems: \
explaining WHY specific neural patterns (TRIBE v2) led to specific social \
outcomes (MiroFish). For example:
- High threat_detection → high counter_narrative_count (defensiveness becomes \
opposition narratives)
- High social_relevance + reward_response → high organic_shares and low \
peak_virality_cycle (content spreads early and widely)
- High cognitive_load → low sentiment_drift (complex content doesn't move \
opinion at scale)

You MUST reference specific numerical values from BOTH systems in every claim \
you make. Do not cite one system while ignoring the other.

## Output requirements

Respond with valid JSON only. No prose, no markdown, no code fences.

Schema:
{
  "iteration_number": <int>,
  "per_variant_assessment": [
    {
      "variant_id": "<id>",
      "neural_summary": "<2-3 sentences on TRIBE v2 patterns — cite specific scores>",
      "social_summary": "<2-3 sentences on MiroFish outcomes — cite specific metrics>",
      "cross_system_insight": "<1-2 sentences connecting neural patterns to social outcomes>",
      "strengths": ["<strength with evidence>"],
      "weaknesses": ["<weakness with evidence>"],
      "composite_assessment": "<one sentence overall verdict>"
    }
  ],
  "ranking": ["<variant_id_1st>", "<variant_id_2nd>", ...],
  "cross_system_insights": [
    "<insight 1: specific neural pattern → specific social outcome, with numbers>",
    "<insight 2>",
    "<insight 3>"
  ],
  "iteration_improvement_notes": "<what changed from previous iteration if applicable>",
  "recommendations_for_next_iteration": [
    "<specific actionable recommendation 1>",
    "<specific actionable recommendation 2>",
    "<specific actionable recommendation 3>"
  ],
  "thresholds_assessment": {
    "met": <bool>,
    "notes": "<which thresholds were or were not met>"
  }
}
"""


# ── User prompt template ──────────────────────────────────────────────────────

def build_result_analysis_prompt(
    iteration_number: int,
    campaign_brief: str,
    prediction_question: str,
    demographic_description: str,
    variants_with_scores: list[dict[str, Any]],
    thresholds: dict[str, float] | None = None,
    previous_analysis: str | None = None,
) -> str:
    """
    Build the user-turn prompt for cross-system iteration analysis.

    Args:
        iteration_number: Which iteration this is (1-indexed).
        campaign_brief: The original seed content / campaign description.
        prediction_question: What the user wants to know about audience response.
        demographic_description: Human-readable description of the target audience.
        variants_with_scores: List of dicts, each containing:
            - variant_id (str)
            - content (str)
            - strategy (str)
            - tribe_scores (dict of 7 neural dimensions)
            - mirofish_metrics (dict of 8 simulation metrics)
            - composite_scores (dict of computed composite scores)
        thresholds: Optional dict of threshold targets the user wants to achieve.
        previous_analysis: JSON string of the previous iteration's analysis
            (for iteration > 1).

    Returns:
        Formatted user-turn prompt string.
    """
    lines: list[str] = []

    lines.append(f"## Iteration {iteration_number} analysis request")
    lines.append("")

    lines.append("### Campaign context")
    lines.append(f"**Brief:** {campaign_brief.strip()}")
    lines.append(f"**Prediction question:** {prediction_question.strip()}")
    lines.append(f"**Target demographic:** {demographic_description.strip()}")
    lines.append("")

    if thresholds:
        lines.append("### Threshold targets (user's success criteria)")
        for metric, target in thresholds.items():
            lines.append(f"- {metric}: {target}")
        lines.append("")

    lines.append("### Variant results (TRIBE v2 neural scores + MiroFish simulation metrics)")
    lines.append("")

    for variant in variants_with_scores:
        vid = variant.get("variant_id", "unknown")
        strategy = variant.get("strategy", "")
        content_preview = (variant.get("content", "")[:300] + "...") if variant.get("content", "") else ""
        tribe = variant.get("tribe_scores", {})
        mirofish = variant.get("mirofish_metrics", {})
        composite = variant.get("composite_scores", {})

        lines.append(f"#### Variant: {vid}")
        if strategy:
            lines.append(f"Strategy: {strategy}")
        if content_preview:
            lines.append(f"Content preview: {content_preview}")
        lines.append("")

        lines.append("**TRIBE v2 neural scores (0-100):**")
        if tribe:
            for dim, score in tribe.items():
                lines.append(f"  - {dim}: {score}")
        else:
            lines.append("  (neural scoring unavailable for this variant)")
        lines.append("")

        lines.append("**MiroFish simulation metrics:**")
        if mirofish:
            for metric, value in mirofish.items():
                if isinstance(value, list):
                    # For time series, show summary stats rather than full array
                    if value:
                        lines.append(
                            f"  - {metric}: [series of {len(value)} values, "
                            f"start={value[0]:.3f}, end={value[-1]:.3f}, "
                            f"max={max(value):.3f}]"
                        )
                    else:
                        lines.append(f"  - {metric}: []")
                elif isinstance(value, dict):
                    lines.append(f"  - {metric}: {value}")
                else:
                    lines.append(f"  - {metric}: {value}")
        else:
            lines.append("  (simulation unavailable for this variant)")
        lines.append("")

        lines.append("**Composite scores (computed):**")
        if composite:
            for score_name, score_value in composite.items():
                lines.append(f"  - {score_name}: {score_value}")
        lines.append("")

    if previous_analysis:
        lines.append("### Previous iteration analysis (for comparison)")
        lines.append(previous_analysis.strip())
        lines.append("")

    lines.append("### Analysis task")
    lines.append(
        "Analyze all variants using BOTH TRIBE v2 neural scores AND MiroFish "
        "simulation metrics. Every claim must cite specific numerical evidence from "
        "at least one of the two systems. Identify cross-system patterns that explain "
        "WHY neural responses led to the social outcomes observed. Provide specific, "
        "actionable recommendations for the next iteration."
    )
    lines.append("")
    lines.append(
        "Return the JSON analysis object as specified in your instructions."
    )

    return "\n".join(lines)
