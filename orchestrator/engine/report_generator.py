"""
Report generation engine for A.R.C Studio.

Produces all 4 report layers after the final campaign iteration:
  Layer 1: Verdict (plain English via Claude Opus)
  Layer 2: Scorecard (programmatic ranking + Opus summary)
  Layer 3: Deep analysis (pure data aggregation, NO LLM call)
  Layer 4: Mass psychology, general + technical (via Claude Opus)

Per D-02: Generated after the final iteration completes.
Per D-03: Both psychology modes stored in the same report record.
Per research guidance: Layer 3 is raw data assembly, not LLM-generated.
"""

import logging
from typing import Any

from orchestrator.api.schemas import (
    AnalysisRecord,
    CampaignResponse,
    IterationRecord,
)
from orchestrator.clients.claude_client import ClaudeClient
from orchestrator.engine.optimization_loop import (
    INVERTED_SCORES,
    check_thresholds,
    find_best_composite,
)
from orchestrator.prompts.demographic_profiles import get_profile
from orchestrator.prompts.report_psychology import (
    MASS_PSYCHOLOGY_GENERAL_SYSTEM,
    MASS_PSYCHOLOGY_TECHNICAL_SYSTEM,
    build_mass_psychology_general_prompt,
    build_mass_psychology_technical_prompt,
)
from orchestrator.prompts.report_scorecard import (
    REPORT_SCORECARD_SYSTEM,
    build_report_scorecard_prompt,
)
from orchestrator.prompts.report_verdict import (
    REPORT_VERDICT_SYSTEM,
    build_report_verdict_prompt,
)

logger = logging.getLogger(__name__)


# -- Utility ---------------------------------------------------------------


def color_code_score(metric_name: str, value: float) -> str:
    """
    Return a traffic-light color for a composite score value.

    For metrics in INVERTED_SCORES (backlash_risk, polarization_index):
        <30 green, <60 amber, >=60 red  (lower is better)
    For other metrics:
        >=70 green, >=40 amber, <40 red  (higher is better)
    """
    if metric_name in INVERTED_SCORES:
        if value < 30:
            return "green"
        elif value < 60:
            return "amber"
        else:
            return "red"
    else:
        if value >= 70:
            return "green"
        elif value >= 40:
            return "amber"
        else:
            return "red"


# -- ReportGenerator -------------------------------------------------------


class ReportGenerator:
    """
    Generates all 4 report layers from campaign results.

    Follows the ResultAnalyzer pattern: ClaudeClient injected via constructor.
    """

    def __init__(self, claude_client: ClaudeClient):
        self._claude = claude_client

    async def generate_report(
        self,
        campaign: CampaignResponse,
        all_iterations: list[IterationRecord],
        all_analyses: list[AnalysisRecord],
        best_scores_history: list[dict],
        stop_reason: str,
    ) -> dict[str, Any]:
        """
        Orchestrate all 4 report layers.

        Each layer is attempted independently so that failures in LLM-dependent
        layers (verdict, psychology) don't prevent programmatic layers (scorecard,
        deep analysis) from being generated.  A partial report with scorecard and
        deep analysis is far more useful than no report at all.

        Returns dict with keys: verdict, scorecard, deep_analysis,
        mass_psychology_general, mass_psychology_technical.
        """
        # Identify final iteration number
        max_iter = max(it.iteration_number for it in all_iterations)
        final_iterations = [
            it for it in all_iterations if it.iteration_number == max_iter
        ]
        iterations_run = max_iter

        # Build final variants with scores for verdict/psychology
        final_variants_with_scores = self._build_variants_with_scores(
            final_iterations
        )

        # Determine winner using find_best_composite on final iteration
        composite_scores_list = [
            v["composite_scores"] for v in final_variants_with_scores
        ]
        best_scores = find_best_composite(composite_scores_list)

        # Find the winning variant dict
        winning_variant = final_variants_with_scores[0]  # fallback
        for v in final_variants_with_scores:
            if v["composite_scores"] == best_scores:
                winning_variant = v
                break

        # Check thresholds
        thresholds_met = None
        if campaign.thresholds:
            all_met, _ = check_thresholds(best_scores, campaign.thresholds)
            thresholds_met = all_met

        # Layer 1: Verdict (Opus call -- may fail if LLM unavailable)
        verdict: str | None = None
        try:
            logger.info("Generating Layer 1: Verdict")
            verdict = await self._generate_verdict(
                campaign=campaign,
                final_variants_with_scores=final_variants_with_scores,
                winning_variant=winning_variant,
                thresholds_met=thresholds_met,
                iterations_run=iterations_run,
            )
        except Exception as e:
            logger.error("Layer 1 (Verdict) failed: %s", e)

        # Layer 2: Scorecard (programmatic -- should always succeed)
        scorecard = None
        try:
            logger.info("Generating Layer 2: Scorecard")
            scorecard = self._assemble_scorecard(
                campaign=campaign,
                all_iterations=all_iterations,
                best_scores_history=best_scores_history,
                stop_reason=stop_reason,
                thresholds_met=thresholds_met,
                final_variants_with_scores=final_variants_with_scores,
                winning_variant=winning_variant,
            )
        except Exception as e:
            logger.error("Layer 2 (Scorecard) failed: %s", e)

        # Layer 3: Deep analysis (pure data, no LLM -- should always succeed)
        deep_analysis = None
        try:
            logger.info("Generating Layer 3: Deep Analysis")
            deep_analysis = self._assemble_deep_analysis(
                all_iterations=all_iterations,
                all_analyses=all_analyses,
            )
        except Exception as e:
            logger.error("Layer 3 (Deep Analysis) failed: %s", e)

        # Layer 4: Mass psychology (2 Opus calls -- may fail if LLM unavailable)
        psych_general: str | None = None
        psych_technical: str | None = None
        try:
            logger.info("Generating Layer 4: Mass Psychology")
            psych_general, psych_technical = await self._generate_psychology(
                campaign=campaign,
                final_variants_with_scores=final_variants_with_scores,
                winning_variant=winning_variant,
            )
        except Exception as e:
            logger.error("Layer 4 (Mass Psychology) failed: %s", e)

        layers_generated = sum(1 for x in [verdict, scorecard, deep_analysis, psych_general] if x is not None)
        logger.info("Report assembled: %d/4 layers generated", layers_generated)

        return {
            "verdict": verdict,
            "scorecard": scorecard,
            "deep_analysis": deep_analysis,
            "mass_psychology_general": psych_general,
            "mass_psychology_technical": psych_technical,
        }

    # -- Private layer methods -----------------------------------------------

    async def _generate_verdict(
        self,
        campaign: CampaignResponse,
        final_variants_with_scores: list[dict[str, Any]],
        winning_variant: dict[str, Any],
        thresholds_met: bool | None,
        iterations_run: int,
    ) -> str:
        """Layer 1: Generate verdict via Claude Opus plain text call."""
        user_prompt = build_report_verdict_prompt(
            prediction_question=campaign.prediction_question,
            winning_variant=winning_variant,
            all_variants=final_variants_with_scores,
            thresholds_met=thresholds_met,
            iterations_run=iterations_run,
        )

        verdict = await self._claude.call_opus(
            system=REPORT_VERDICT_SYSTEM,
            user=user_prompt,
            max_tokens=2048,
        )

        logger.info("Verdict generated: %d chars", len(verdict))
        return verdict

    def _assemble_scorecard(
        self,
        campaign: CampaignResponse,
        all_iterations: list[IterationRecord],
        best_scores_history: list[dict],
        stop_reason: str,
        thresholds_met: bool | None,
        final_variants_with_scores: list[dict[str, Any]],
        winning_variant: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Layer 2: Assemble scorecard programmatically.

        Ranks variants using find_best_composite logic, computes color coding,
        builds iteration trajectory and thresholds status. No LLM call for the
        data -- only for a narrative summary if desired.
        """
        # Rank variants by adjusted composite average (same logic as find_best_composite)
        ranked = self._rank_variants(final_variants_with_scores)

        # Build iteration trajectory from best_scores_history
        iteration_trajectory = []
        for i, scores in enumerate(best_scores_history):
            iteration_trajectory.append({
                "iteration": i + 1,
                "best_scores": scores,
            })

        # Build thresholds_status
        thresholds_status: dict[str, Any] = {}
        if campaign.thresholds:
            _, per_threshold = check_thresholds(
                winning_variant["composite_scores"], campaign.thresholds
            )
            thresholds_status = {
                "all_met": thresholds_met if thresholds_met is not None else False,
                "per_threshold": per_threshold,
            }

        # Summary from the winning variant data (simple template, avoids Opus call)
        winner_id = winning_variant.get("variant_id", "unknown")
        summary = (
            f"Variant {winner_id} ranked first. "
            f"Campaign completed after {len(best_scores_history)} iteration(s) "
            f"(stop reason: {stop_reason})."
        )

        return {
            "winning_variant_id": winner_id,
            "variants": ranked,
            "iteration_trajectory": iteration_trajectory,
            "thresholds_status": thresholds_status,
            "summary": summary,
        }

    def _assemble_deep_analysis(
        self,
        all_iterations: list[IterationRecord],
        all_analyses: list[AnalysisRecord],
    ) -> dict[str, Any]:
        """
        Layer 3: Pure data aggregation -- NO LLM call.

        Groups iterations by iteration_number. For each, builds variant data
        with all scores and matches the corresponding analysis record.
        """
        # Group iterations by iteration_number
        iter_groups: dict[int, list[IterationRecord]] = {}
        for it in all_iterations:
            iter_groups.setdefault(it.iteration_number, []).append(it)

        # Index analyses by iteration_number
        analysis_map: dict[int, dict[str, Any]] = {}
        for a in all_analyses:
            analysis_map[a.iteration_number] = a.analysis_json

        # Build per-iteration data
        result_iterations = []
        for iter_num in sorted(iter_groups.keys()):
            variants = []
            for it in iter_groups[iter_num]:
                variant_data: dict[str, Any] = {
                    "variant_id": it.variant_id,
                    "content": it.variant_content,
                    "strategy": it.variant_strategy,
                    "tribe_scores": (
                        it.tribe_scores.model_dump() if it.tribe_scores else None
                    ),
                    "mirofish_metrics": (
                        it.mirofish_metrics.model_dump()
                        if it.mirofish_metrics
                        else None
                    ),
                    "composite_scores": (
                        it.composite_scores.model_dump()
                        if it.composite_scores
                        else None
                    ),
                }
                variants.append(variant_data)

            result_iterations.append({
                "iteration": iter_num,
                "variants": variants,
                "analysis": analysis_map.get(iter_num, {}),
            })

        return {"iterations": result_iterations}

    async def _generate_psychology(
        self,
        campaign: CampaignResponse,
        final_variants_with_scores: list[dict[str, Any]],
        winning_variant: dict[str, Any],
    ) -> tuple[str, str]:
        """
        Layer 4: Generate both general and technical mass psychology texts.

        Two separate Opus calls to ensure distinct system prompts produce
        quality output (per Open Question #1 in RESEARCH.md).
        """
        # Resolve demographic description
        if campaign.demographic == "custom":
            demo_description = campaign.demographic_custom or "General audience"
        else:
            profile = get_profile(campaign.demographic)
            demo_description = profile["description"]

        # Build simulation summary from winning variant's mirofish metrics
        simulation_summary = winning_variant.get("mirofish_metrics", {})

        # Winning variant's tribe scores for technical analysis
        winning_tribe_scores = winning_variant.get("tribe_scores")

        # General psychology (Opus call 2)
        general_prompt = build_mass_psychology_general_prompt(
            campaign_brief=campaign.seed_content,
            demographic_description=demo_description,
            winning_variant=winning_variant,
            all_variants=final_variants_with_scores,
            simulation_summary=simulation_summary,
        )

        general_text = await self._claude.call_opus(
            system=MASS_PSYCHOLOGY_GENERAL_SYSTEM,
            user=general_prompt,
            max_tokens=2048,
        )

        # Technical psychology (Opus call 3)
        technical_prompt = build_mass_psychology_technical_prompt(
            campaign_brief=campaign.seed_content,
            demographic_description=demo_description,
            winning_variant=winning_variant,
            all_variants=final_variants_with_scores,
            simulation_summary=simulation_summary,
            tribe_scores=winning_tribe_scores,
        )

        technical_text = await self._claude.call_opus(
            system=MASS_PSYCHOLOGY_TECHNICAL_SYSTEM,
            user=technical_prompt,
            max_tokens=2048,
        )

        logger.info(
            "Psychology generated: general=%d chars, technical=%d chars",
            len(general_text),
            len(technical_text),
        )

        return general_text, technical_text

    # -- Helper methods ------------------------------------------------------

    @staticmethod
    def _build_variants_with_scores(
        iterations: list[IterationRecord],
    ) -> list[dict[str, Any]]:
        """Build variant dicts with all scores from IterationRecords."""
        variants = []
        for it in iterations:
            v: dict[str, Any] = {
                "variant_id": it.variant_id,
                "content": it.variant_content,
                "strategy": it.variant_strategy,
                "composite_scores": (
                    it.composite_scores.model_dump()
                    if it.composite_scores
                    else {}
                ),
                "tribe_scores": (
                    it.tribe_scores.model_dump() if it.tribe_scores else {}
                ),
                "mirofish_metrics": (
                    it.mirofish_metrics.model_dump()
                    if it.mirofish_metrics
                    else {}
                ),
            }
            variants.append(v)
        return variants

    @staticmethod
    def _rank_variants(
        variants_with_scores: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Rank variants by adjusted composite average (same logic as find_best_composite).

        Returns list of dicts with variant_id, rank, strategy, composite_scores,
        and color_coding -- sorted by rank ascending (best first).
        """

        def _adjusted_avg(scores: dict[str, float | None]) -> float:
            values: list[float] = []
            for key, val in scores.items():
                if val is None:
                    continue
                if key in INVERTED_SCORES:
                    values.append(100.0 - val)
                else:
                    values.append(val)
            return sum(values) / len(values) if values else 0.0

        # Sort by adjusted average descending
        sorted_variants = sorted(
            variants_with_scores,
            key=lambda v: _adjusted_avg(v.get("composite_scores", {})),
            reverse=True,
        )

        ranked = []
        for rank, v in enumerate(sorted_variants, start=1):
            scores = v.get("composite_scores", {})
            color_coding = {}
            for metric, value in scores.items():
                if value is not None:
                    color_coding[metric] = color_code_score(metric, value)

            ranked.append({
                "variant_id": v.get("variant_id", "unknown"),
                "rank": rank,
                "strategy": v.get("strategy", ""),
                "composite_average": round(_adjusted_avg(scores), 1),
                "composite_scores": scores,
                "color_coding": color_coding,
            })

        return ranked
