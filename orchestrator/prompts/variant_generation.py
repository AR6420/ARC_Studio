"""
Prompt templates for content variant generation.

Used by engine/variant_generator.py to call Claude Haiku and generate
N content variants from a campaign brief.

Each variant must take a meaningfully different strategic approach so that
the TRIBE v2 + MiroFish scoring can distinguish them and the feedback loop
can converge toward an optimal strategy.
"""

from typing import Any


# ── System prompt ────────────────────────────────────────────────────────────

VARIANT_GENERATION_SYSTEM = """\
You are a world-class content strategist specializing in audience psychology and \
persuasive communication. Your task is to generate distinct content variants from a \
campaign brief, each embodying a different strategic approach to reach the target audience.

You have deep knowledge of:
- Cognitive psychology: how framing, priming, and emotional triggers affect processing
- Social dynamics: what drives sharing, discussion, and behavioral change
- Demographic nuance: how different audiences process and respond to messages differently
- Narrative structure: story arcs, tension, resolution, and their psychological effects

## Output requirements

You MUST respond with valid JSON only. No prose, no markdown, no code fences.

The JSON must conform to this schema:
{
  "variants": [
    {
      "id": "v{N}_{short_strategy_slug}",
      "content": "<the full content text>",
      "strategy": "<1-2 sentence description of the strategic approach>",
      "key_psychological_mechanisms": ["<mechanism 1>", "<mechanism 2>"],
      "expected_strengths": ["<strength 1>", "<strength 2>"],
      "potential_risks": ["<risk 1>"]
    }
  ]
}

Rules:
- Each variant must have a DISTINCT strategic approach. Do not produce minor variations \
of the same theme.
- Variants should explore different psychological mechanisms: one might lead with social \
proof, another with fear reduction, another with reward framing, etc.
- All variants must satisfy any stated constraints exactly.
- Content must be complete and polished — not a draft or outline.
- Each variant's content MUST be between 80 and 150 words. This is a hard limit. Do not \
exceed 150 words per variant. Shorter, punchier variants score better on neural response.
- Variant IDs use the format: v1_strategy_name, v2_strategy_name, etc.
"""


# ── User prompt template ─────────────────────────────────────────────────────

def build_variant_generation_prompt(
    campaign_brief: str,
    demographic_description: str,
    num_variants: int,
    constraints: str | None = None,
    previous_iteration_results: list[dict[str, Any]] | None = None,
) -> str:
    """
    Build the user-turn prompt for variant generation.

    Args:
        campaign_brief: The seed content / campaign description from the user.
        demographic_description: Human-readable description of the target audience
            (from a preset or custom free-text input).
        num_variants: How many distinct variants to generate.
        constraints: Optional brand guidelines or content rules the variants must follow.
        previous_iteration_results: If this is iteration N > 1, pass the analysis and
            scores from the previous iteration so Haiku can build on what worked.

    Returns:
        The fully formatted user-turn prompt string.
    """
    lines: list[str] = []

    lines.append("## Campaign brief")
    lines.append(campaign_brief.strip())
    lines.append("")

    lines.append("## Target demographic")
    lines.append(demographic_description.strip())
    lines.append("")

    if constraints:
        lines.append("## Constraints (MUST be followed in every variant)")
        lines.append(constraints.strip())
        lines.append("")

    lines.append(f"## Task")
    lines.append(
        f"Generate exactly {num_variants} content variants. "
        "Each variant must take a fundamentally different strategic approach. "
        "Think carefully about which psychological mechanisms each approach activates."
    )
    lines.append("")

    if previous_iteration_results:
        lines.append("## Previous iteration results (use to improve this iteration)")
        lines.append(
            "The following variants were tested in the previous iteration. "
            "Use the scores and analysis to understand what worked and what did not. "
            "Build on the strongest signals and avoid repeating weak strategies."
        )
        lines.append("")
        for result in previous_iteration_results:
            variant_id = result.get("variant_id", "unknown")
            strategy = result.get("strategy", "")
            composite = result.get("composite_scores", {})
            tribe = result.get("tribe_scores", {})
            mirofish = result.get("mirofish_metrics", {})
            opus_note = result.get("iteration_note", "")

            lines.append(f"### Variant: {variant_id}")
            if strategy:
                lines.append(f"Strategy: {strategy}")
            if composite:
                scores_str = ", ".join(
                    f"{k}: {v}" for k, v in composite.items()
                )
                lines.append(f"Composite scores: {scores_str}")
            if tribe:
                tribe_str = ", ".join(f"{k}: {v}" for k, v in tribe.items() if k != "is_pseudo_score")
                lines.append(f"Neural scores (TRIBE v2): {tribe_str}")
            if mirofish:
                mf_str = ", ".join(
                    f"{k}: {v}"
                    for k, v in mirofish.items()
                    if not isinstance(v, (list, dict))
                )
                lines.append(f"Simulation metrics: {mf_str}")
            if opus_note:
                lines.append(f"Analysis note: {opus_note}")
            lines.append("")

        lines.append(
            "Improvement directive: Generate variants that address the weaknesses "
            "identified above while amplifying what worked. Each new variant should "
            "represent a meaningful strategic evolution, not cosmetic text changes."
        )
        lines.append("")

    lines.append(
        f"Return the JSON object with exactly {num_variants} variants in the "
        '"variants" array.'
    )

    return "\n".join(lines)
