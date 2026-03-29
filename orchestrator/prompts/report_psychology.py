"""
Prompt templates for Layer 4 of the final report: Mass Psychology.

Two modes as defined in Results.md:

General mode:
  "Narrative prose (200-600 words), accessible to any literate adult.
   Must reference specific simulation cycles. No jargon."

Technical mode:
  "References established theories (Granovetter, Noelle-Neumann, Cialdini,
   emotional contagion). Includes quantitative metrics. Quality standard: a
   behavioral scientist should be able to use this in a research context."
"""

from typing import Any


# ── System prompts ────────────────────────────────────────────────────────────

MASS_PSYCHOLOGY_GENERAL_SYSTEM = """\
You are a science communicator explaining complex social dynamics to an \
educated but non-specialist audience. Your task is to write Layer 4 \
(General mode) of the Nexus Sim final report: a narrative account of how \
opinion formed, spread, and stabilized in the simulation.

## Writing standards

- Narrative prose ONLY. No bullet points, no headers, no tables.
- Length: 200–600 words.
- Language: accessible to any literate adult. Define any term that a typical \
  newspaper reader would not know.
- Tell a story with a beginning, middle, and end — how did opinion start, what \
  turned the tide, where did things settle?
- Reference specific simulation cycles by number (e.g., "by cycle 14, the \
  mood had shifted noticeably").
- Identify key moments: tipping points, surges, reversals, surprising outcomes.
- Do NOT use technical terms like "coalition formation index," "influence \
  concentration," "sentiment drift metric," etc. Translate them into human \
  language.
- Do NOT mention TRIBE v2, MiroFish, neural scoring, or the simulation \
  infrastructure by name. Refer to "the community," "participants," "people \
  in our test group," "the conversation," etc.
"""

MASS_PSYCHOLOGY_TECHNICAL_SYSTEM = """\
You are a behavioral scientist writing a technical analysis of collective \
psychology dynamics for a research audience. Your task is to write Layer 4 \
(Technical mode) of the Nexus Sim final report.

## Scientific framing

Ground your analysis in established social psychology and behavioral science \
theories. You MUST reference at least 2 of the following frameworks, using \
their proper terminology and citing the mechanisms at work:

- **Granovetter's threshold model** — cascade dynamics, threshold activation, \
  critical mass
- **Noelle-Neumann's spiral of silence** — opinion climate perception, \
  willingness to speak, dominant vs. minority opinion suppression
- **Cialdini's influence principles** — social proof, authority, scarcity, \
  liking, reciprocity, commitment/consistency
- **Emotional contagion theory** (Hatfield, Cacioppo, Rapson) — affective \
  transmission, emotional synchrony, valence spreading
- **Overton window dynamics** — shifting the range of acceptable discourse, \
  normalization of positions

## Quantitative requirements

Include the following metrics in your analysis (they will be provided):
- Social proof cascade rates (derived from organic share velocity)
- In-group/out-group formation indices (derived from coalition formation data)
- Cognitive dissonance resolution patterns (derived from sentiment trajectory)
- Opinion leader influence ratios (derived from influence concentration)

## Format

- Structured prose with clear paragraph breaks.
- Length: 300–700 words.
- Tone: academic but readable — suitable for a conference presentation or \
  research brief.
- You MAY use bullet points or a table for quantitative data only. Prose \
  for all qualitative analysis.
"""


# ── User prompt templates ─────────────────────────────────────────────────────

def build_mass_psychology_general_prompt(
    campaign_brief: str,
    demographic_description: str,
    winning_variant: dict[str, Any],
    all_variants: list[dict[str, Any]],
    simulation_summary: dict[str, Any],
) -> str:
    """
    Build the user-turn prompt for the general-audience mass psychology narrative.

    Args:
        campaign_brief: Original seed content / campaign description.
        demographic_description: Human-readable description of the target audience.
        winning_variant: The top-scoring variant with scores and metrics.
        all_variants: All final-iteration variants (for comparison context).
        simulation_summary: Aggregated MiroFish metrics for the winning variant,
            expected keys: organic_shares, sentiment_trajectory (list),
            counter_narrative_count, peak_virality_cycle, sentiment_drift,
            coalition_formation, influence_concentration, platform_divergence.

    Returns:
        Formatted user-turn prompt string.
    """
    lines: list[str] = []

    lines.append("## What was being tested")
    lines.append(campaign_brief.strip()[:500])
    lines.append("")

    lines.append("## Who was in the simulation")
    lines.append(demographic_description.strip())
    lines.append("")

    lines.append("## What happened in the simulation (raw data)")

    traj = simulation_summary.get("sentiment_trajectory", [])
    if traj:
        lines.append(
            f"Sentiment over {len(traj)} simulation cycles: "
            f"started at {traj[0]:.2f}, "
            f"peaked at {max(traj):.2f} (cycle {traj.index(max(traj)) + 1}), "
            f"ended at {traj[-1]:.2f}"
        )

    shares = simulation_summary.get("organic_shares")
    if shares is not None:
        lines.append(f"Voluntary shares by the end: {shares}")

    peak = simulation_summary.get("peak_virality_cycle")
    if peak is not None:
        lines.append(f"Sharing peaked at cycle: {peak}")

    drift = simulation_summary.get("sentiment_drift")
    if drift is not None:
        direction = "positive" if drift > 0 else "negative" if drift < 0 else "neutral"
        lines.append(f"Net sentiment change: {drift:+.1f} ({direction} shift)")

    counter = simulation_summary.get("counter_narrative_count")
    if counter is not None:
        lines.append(f"Opposing narratives that emerged: {counter}")

    coalition = simulation_summary.get("coalition_formation", {})
    if coalition and isinstance(coalition, dict):
        groups = coalition.get("groups", [])
        if groups:
            group_desc = "; ".join(
                f"{g.get('name', 'unnamed')} (size {g.get('size', '?')}, "
                f"stability {g.get('stability', '?')})"
                for g in groups
            )
            lines.append(f"Opinion groups that formed: {group_desc}")

    influence = simulation_summary.get("influence_concentration")
    if influence is not None:
        if influence < 30:
            influence_label = "spread evenly across many participants"
        elif influence < 60:
            influence_label = "moderately concentrated in key individuals"
        else:
            influence_label = "highly concentrated in a small number of influencers"
        lines.append(f"Influence distribution: {influence:.0f}/100 ({influence_label})")

    divergence = simulation_summary.get("platform_divergence")
    if divergence is not None:
        lines.append(f"Platform divergence (Twitter-like vs. Reddit-like): {divergence:.0f}/100")

    lines.append("")

    lines.append("## Comparison: how other variants performed socially")
    for v in all_variants:
        vid = v.get("variant_id", "unknown")
        if vid == winning_variant.get("variant_id"):
            lines.append(f"[Winner] {vid}: see above")
            continue
        vmf = v.get("mirofish_metrics", {})
        if vmf:
            shares_v = vmf.get("organic_shares", "N/A")
            drift_v = vmf.get("sentiment_drift", "N/A")
            counter_v = vmf.get("counter_narrative_count", "N/A")
            lines.append(
                f"{vid}: shares={shares_v}, sentiment drift={drift_v}, "
                f"counter-narratives={counter_v}"
            )
    lines.append("")

    lines.append("## Your task")
    lines.append(
        "Write a narrative (200-600 words, plain English, no jargon) telling the "
        "story of how public opinion formed, spread, and settled in this simulation. "
        "Reference specific cycle numbers. Identify the key turning point. "
        "Explain what drove sharing and what caused any resistance. "
        "Make it compelling and accessible to any literate adult."
    )

    return "\n".join(lines)


def build_mass_psychology_technical_prompt(
    campaign_brief: str,
    demographic_description: str,
    winning_variant: dict[str, Any],
    all_variants: list[dict[str, Any]],
    simulation_summary: dict[str, Any],
    tribe_scores: dict[str, float] | None = None,
) -> str:
    """
    Build the user-turn prompt for the technical-audience mass psychology analysis.

    Args:
        campaign_brief: Original seed content / campaign description.
        demographic_description: Human-readable description of the target audience.
        winning_variant: The top-scoring variant with all scores.
        all_variants: All final-iteration variants.
        simulation_summary: MiroFish metrics dict for the winning variant.
        tribe_scores: TRIBE v2 neural dimension scores for the winning variant
            (optional but strongly recommended for technical analysis).

    Returns:
        Formatted user-turn prompt string.
    """
    lines: list[str] = []

    lines.append("## Research context")
    lines.append(f"Content type: {campaign_brief.strip()[:300]}")
    lines.append(f"Population: {demographic_description.strip()}")
    lines.append("")

    lines.append("## Neurological substrate (TRIBE v2 scores, 0-100 normalized)")
    if tribe_scores:
        for dim, score in tribe_scores.items():
            lines.append(f"  {dim}: {score}")
    else:
        lines.append("  (neural scores unavailable)")
    lines.append("")

    lines.append("## Social dynamics dataset (MiroFish simulation metrics)")

    traj = simulation_summary.get("sentiment_trajectory", [])
    if traj:
        # Compute velocity at each step for cascade rate analysis
        velocities = [
            round(traj[i] - traj[i - 1], 4) for i in range(1, len(traj))
        ]
        max_velocity = max(velocities) if velocities else 0.0
        max_velocity_cycle = velocities.index(max_velocity) + 2 if velocities else 0
        lines.append(f"  Sentiment trajectory: {len(traj)} cycles")
        lines.append(f"  Initial sentiment: {traj[0]:.4f}")
        lines.append(f"  Terminal sentiment: {traj[-1]:.4f}")
        lines.append(f"  Peak sentiment: {max(traj):.4f} at cycle {traj.index(max(traj)) + 1}")
        lines.append(f"  Max cascade velocity: {max_velocity:.4f} at cycle {max_velocity_cycle}")

    shares = simulation_summary.get("organic_shares")
    if shares is not None:
        lines.append(f"  Organic share count: {shares}")

    peak = simulation_summary.get("peak_virality_cycle")
    if peak is not None:
        lines.append(f"  Peak virality cycle: {peak}")

    drift = simulation_summary.get("sentiment_drift")
    if drift is not None:
        lines.append(f"  Sentiment drift (net): {drift:+.2f}")

    counter = simulation_summary.get("counter_narrative_count")
    if counter is not None:
        lines.append(f"  Counter-narrative count: {counter}")

    influence = simulation_summary.get("influence_concentration")
    if influence is not None:
        lines.append(f"  Influence concentration index: {influence:.1f}/100")

    divergence = simulation_summary.get("platform_divergence")
    if divergence is not None:
        lines.append(f"  Platform divergence coefficient: {divergence:.1f}/100")

    coalition = simulation_summary.get("coalition_formation", {})
    if coalition and isinstance(coalition, dict):
        groups = coalition.get("groups", [])
        if groups:
            lines.append(f"  Coalition count: {len(groups)}")
            for g in groups:
                lines.append(
                    f"    - {g.get('name', 'unnamed')}: n={g.get('size', '?')}, "
                    f"stability={g.get('stability', '?')}"
                )
    lines.append("")

    # Cross-variant comparison for in-group/out-group analysis
    if len(all_variants) > 1:
        lines.append("## Cross-variant comparison (for theoretical grounding)")
        for v in all_variants:
            vid = v.get("variant_id", "unknown")
            vtribe = v.get("tribe_scores", {})
            vmf = v.get("mirofish_metrics", {})
            if vtribe or vmf:
                social_rel = vtribe.get("social_relevance", "N/A")
                threat = vtribe.get("threat_detection", "N/A")
                vshares = vmf.get("organic_shares", "N/A")
                vcounter = vmf.get("counter_narrative_count", "N/A")
                vdrift = vmf.get("sentiment_drift", "N/A")
                lines.append(
                    f"  {vid}: social_relevance={social_rel}, "
                    f"threat_detection={threat}, shares={vshares}, "
                    f"counter_narratives={vcounter}, drift={vdrift}"
                )
        lines.append("")

    lines.append("## Analytical task")
    lines.append(
        "Write a technical mass psychology analysis (300-700 words). "
        "You MUST reference at least 2 of the following frameworks explicitly by name: "
        "Granovetter threshold model, Noelle-Neumann spiral of silence, "
        "Cialdini's influence principles, emotional contagion theory (Hatfield et al.), "
        "Overton window dynamics. "
        "Ground every theoretical claim in the quantitative data above. "
        "Include computed metrics where they support the analysis: "
        "social proof cascade rates, in-group/out-group formation indices, "
        "cognitive dissonance resolution patterns, opinion leader influence ratios. "
        "The output should be suitable for use in a research brief or conference presentation."
    )

    return "\n".join(lines)
