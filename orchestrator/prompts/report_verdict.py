"""
Prompt templates for Layer 1 of the final report: The Verdict.

Quality standard from Results.md:
  "Must be understandable by a non-technical adult. No jargon. Must contain a
   clear recommendation. Must be 100-400 words."

The verdict is written by Claude Opus in plain English. It should read like a
clear, confident recommendation from a trusted advisor — not a data dump.
"""

from typing import Any


# ── System prompt ─────────────────────────────────────────────────────────────

REPORT_VERDICT_SYSTEM = """\
You are a trusted advisor helping a non-technical decision-maker understand \
the results of a content optimization analysis. Your job is to write Layer 1 \
of the final report: The Verdict.

## Audience and tone

Write for someone who has NO technical background. They have never heard of \
"TRIBE v2," "fMRI," "neural scoring," or "multi-agent simulation." They want \
to know one thing: what should they do?

- Use plain English. No jargon. No acronyms without explanation.
- Write in an authoritative but accessible tone — like a trusted expert friend.
- Be specific and concrete. Vague guidance is useless.
- Lead with the recommendation. Don't bury it.
- Mention surprising findings — things the user wouldn't have guessed.
- Be honest about limitations or caveats.

## Format requirements

- Plain prose only. No bullet points. No headers. No markdown.
- Length: 100–400 words. Tight and punchy beats long and rambling.
- Structure: recommendation → key reason → what to avoid → surprising finding \
(if any) → one-sentence close.

## What NOT to do

- Do not mention TRIBE v2, MiroFish, neural scores, fMRI, or simulation by name.
  Refer to them as "our analysis," "the research found," "testing showed," etc.
- Do not list numbers unless they are essential to the recommendation and \
  understandable without context.
- Do not hedge everything — give a clear verdict even if the margin is close.
"""


# ── User prompt template ──────────────────────────────────────────────────────

def build_report_verdict_prompt(
    prediction_question: str,
    winning_variant: dict[str, Any],
    all_variants: list[dict[str, Any]],
    simulation_results: dict[str, Any] | None = None,
    thresholds_met: bool | None = None,
    iterations_run: int = 1,
) -> str:
    """
    Build the user-turn prompt for the verdict (Layer 1).

    Args:
        prediction_question: The user's original question about audience response.
        winning_variant: The top-scoring variant dict, including:
            - variant_id, content, strategy, composite_scores, tribe_scores,
              mirofish_metrics
        all_variants: All variants from the final iteration (for comparison context).
        simulation_results: Optional summary of simulation outcomes.
        thresholds_met: Whether the user's threshold targets were achieved.
        iterations_run: How many optimization iterations were completed.

    Returns:
        Formatted user-turn prompt string.
    """
    lines: list[str] = []

    lines.append("## The question this analysis was designed to answer")
    lines.append(prediction_question.strip())
    lines.append("")

    lines.append("## What we tested")
    lines.append(
        f"We tested {len(all_variants)} content variant(s) across "
        f"{iterations_run} optimization iteration(s)."
    )
    lines.append("")

    # Winning variant
    wid = winning_variant.get("variant_id", "unknown")
    wstrategy = winning_variant.get("strategy", "")
    wcontent = winning_variant.get("content", "")
    wcomposite = winning_variant.get("composite_scores", {})
    wtribe = winning_variant.get("tribe_scores", {})
    wmirofish = winning_variant.get("mirofish_metrics", {})

    lines.append(f"## The winning approach: {wid}")
    if wstrategy:
        lines.append(f"Strategic approach: {wstrategy}")
    if wcontent:
        preview = wcontent[:400] + ("..." if len(wcontent) > 400 else "")
        lines.append(f"Content: {preview}")
    lines.append("")

    if wcomposite:
        lines.append("Winning variant scores:")
        for score_name, score_value in wcomposite.items():
            lines.append(f"  {score_name}: {score_value}")
        lines.append("")

    if wtribe:
        lines.append("Neural response highlights (TRIBE v2):")
        # Highlight the most meaningful scores for verdict context
        highlights = {
            "attention_capture": "attention",
            "emotional_resonance": "emotional impact",
            "threat_detection": "defensiveness risk",
            "reward_response": "positive engagement",
            "social_relevance": "shareability",
        }
        for key, label in highlights.items():
            if key in wtribe:
                lines.append(f"  {label}: {wtribe[key]}")
        lines.append("")

    if wmirofish:
        lines.append("Social simulation highlights (MiroFish):")
        mf_highlights = {
            "organic_shares": "voluntary shares",
            "sentiment_drift": "net sentiment change",
            "counter_narrative_count": "opposing narratives generated",
            "peak_virality_cycle": "when sharing peaked (cycle)",
        }
        for key, label in mf_highlights.items():
            if key in wmirofish:
                lines.append(f"  {label}: {wmirofish[key]}")
        lines.append("")

    # Other variants for comparison
    if len(all_variants) > 1:
        lines.append("## Other tested variants (for contrast)")
        for v in all_variants:
            vid = v.get("variant_id", "unknown")
            if vid == wid:
                continue
            vstrategy = v.get("strategy", "")
            vcomposite = v.get("composite_scores", {})
            vtribe = v.get("tribe_scores", {})
            vmirofish = v.get("mirofish_metrics", {})

            lines.append(f"Variant {vid}:")
            if vstrategy:
                lines.append(f"  Strategy: {vstrategy}")
            if vcomposite:
                comp_str = ", ".join(f"{k}: {val}" for k, val in vcomposite.items())
                lines.append(f"  Composite scores: {comp_str}")
            if vtribe.get("threat_detection") is not None:
                lines.append(f"  Defensiveness risk: {vtribe['threat_detection']}")
            if vmirofish.get("counter_narrative_count") is not None:
                lines.append(f"  Opposing narratives: {vmirofish['counter_narrative_count']}")
        lines.append("")

    if thresholds_met is not None:
        if thresholds_met:
            lines.append(
                "Threshold targets: ALL user-defined threshold targets were met."
            )
        else:
            lines.append(
                "Threshold targets: Some user-defined threshold targets were NOT met "
                "within the configured iteration limit. The winning variant represents "
                "the best achievable result given the constraints."
            )
        lines.append("")

    lines.append("## Your task")
    lines.append(
        "Write a verdict in plain English (100-400 words, no jargon, no bullet points). "
        "Lead with a clear recommendation. Explain why the winning approach works in "
        "terms a non-technical reader understands. Warn about the worst-performing "
        "variant if it is a risk. Include one surprising finding if the data supports it. "
        "Close with a single confident sentence."
    )

    return "\n".join(lines)
