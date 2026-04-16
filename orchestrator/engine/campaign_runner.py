"""
Campaign runner for A.R.C Studio -- the heart of the orchestration pipeline.

Wires all engine components into a single-iteration pipeline:
  1. Pre-flight health check (system availability)
  2. Generate N content variants (Claude Haiku)
  3. Score variants with TRIBE v2 (sequential, per D-03)
  4. Simulate variants with MiroFish (sequential, per D-04)
  5. Compute composite scores
  6. Cross-system analysis (Claude Opus)
  7. Persist everything to SQLite

Per ORCH-13: Single-iteration pipeline that can be called repeatedly
for multi-iteration optimization (Phase 6).
Per D-05: Graceful degradation when TRIBE or MiroFish is unavailable.
Per D-06: Pre-flight health check approach for simplicity.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, TYPE_CHECKING

from orchestrator.api.schemas import DataCompleteness, SystemAvailability

if TYPE_CHECKING:
    from orchestrator.engine.report_generator import ReportGenerator
from orchestrator.clients.tribe_client import TribeClient
from orchestrator.clients.mirofish_client import MirofishClient
from orchestrator.engine.variant_generator import VariantGenerator
from orchestrator.engine.tribe_scorer import TribeScoringPipeline
from orchestrator.engine.mirofish_runner import MirofishRunner
from orchestrator.engine.composite_scorer import compute_composite_scores
from orchestrator.engine.result_analyzer import ResultAnalyzer
from orchestrator.storage.campaign_store import CampaignStore
from orchestrator.engine.optimization_loop import (
    TimeEstimator,
    build_iteration_feedback,
    check_thresholds,
    compute_improvement,
    find_best_composite,
    is_converged,
)
from orchestrator.prompts.demographic_profiles import get_cognitive_weights

logger = logging.getLogger(__name__)


class CampaignRunner:
    """
    Main orchestration: wires variant generation, TRIBE scoring, MiroFish
    simulation, composite scoring, and cross-system analysis into a
    single-iteration campaign pipeline.

    Per D-05: Graceful degradation when TRIBE or MiroFish is unavailable.
    Per D-06 (Claude's discretion): Uses pre-flight health check approach.
    """

    def __init__(
        self,
        variant_generator: VariantGenerator,
        tribe_scoring: TribeScoringPipeline,
        mirofish_runner: MirofishRunner,
        result_analyzer: ResultAnalyzer,
        campaign_store: CampaignStore,
        tribe_client: TribeClient,
        mirofish_client: MirofishClient,
        report_generator: ReportGenerator | None = None,
    ):
        self._variant_gen = variant_generator
        self._tribe_scoring = tribe_scoring
        self._mirofish_runner = mirofish_runner
        self._result_analyzer = result_analyzer
        self._store = campaign_store
        self._tribe_client = tribe_client
        self._mirofish_client = mirofish_client
        self._report_generator = report_generator

    async def check_system_availability(self) -> SystemAvailability:
        """
        Pre-flight health check of downstream services.
        Per D-06: Check once before pipeline starts -- simpler and avoids
        partial state.
        """
        warnings: list[str] = []
        tribe_ok = await self._tribe_client.health_check()
        if not tribe_ok:
            warnings.append("TRIBE v2 scorer unavailable -- neural scores will be skipped")

        mirofish_ok = await self._mirofish_client.health_check()
        if not mirofish_ok:
            warnings.append("MiroFish simulator unavailable -- simulation metrics will be skipped")

        availability = SystemAvailability(
            tribe_available=tribe_ok,
            mirofish_available=mirofish_ok,
            warnings=warnings,
        )

        if warnings:
            for w in warnings:
                logger.warning(w)

        if not tribe_ok and not mirofish_ok:
            logger.warning(
                "Both TRIBE and MiroFish unavailable -- only variant generation and analysis will run"
            )

        return availability

    async def run_single_iteration(
        self,
        campaign_id: str,
        iteration_number: int = 1,
        previous_iteration_results: list[dict[str, Any]] | None = None,
        previous_analysis: dict[str, Any] | None = None,
        manage_status: bool = True,
    ) -> dict[str, Any]:
        """
        Run a single iteration of the campaign pipeline.

        Pipeline sequence (per ORCH-13):
        1. Pre-flight system health check
        2. Generate N content variants (Claude Haiku)
        3. Score all variants with TRIBE v2 (sequential, per D-03)
        4. Simulate all variants with MiroFish (sequential, per D-04)
        5. Compute composite scores for each variant
        6. Cross-system analysis (Claude Opus)
        7. Persist everything to SQLite

        Returns dict with: variants, tribe_scores, mirofish_metrics,
        composite_scores, analysis, system_availability, warnings.
        """
        # Load campaign from DB
        campaign = await self._store.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        # Update status to running (skip if caller manages status, e.g. run_campaign)
        if manage_status:
            await self._store.update_campaign_status(campaign_id, "running")

        try:
            # Step 1: Pre-flight health check
            availability = await self.check_system_availability()

            # Step 2: Generate variants
            logger.info("Step 2: Generating %d content variants", 2)
            variants = await self._variant_gen.generate_variants(
                campaign_brief=campaign.seed_content,
                demographic=campaign.demographic,
                demographic_custom=campaign.demographic_custom,
                num_variants=2,  # Per D-01, reduced from 3 in B.1 scope reduction
                constraints=campaign.constraints,
                previous_iteration_results=previous_iteration_results,
            )

            # Step 3: TRIBE scoring (if available)
            # Phase 2 A.1: dispatch on media_type. Audio campaigns route the
            # uploaded file to TRIBE's audio endpoint (via tribe_client.score_audio);
            # text campaigns keep the existing batch-scoring pipeline unchanged.
            media_type = getattr(campaign, "media_type", "text") or "text"
            media_path = getattr(campaign, "media_path", None)
            tribe_scores_list: list[dict[str, float] | None] = []
            if availability.tribe_available:
                if media_type == "audio":
                    if not media_path:
                        logger.warning(
                            "Campaign %s declared media_type='audio' but has no "
                            "media_path; skipping TRIBE scoring", campaign_id,
                        )
                        tribe_scores_list = [None] * len(variants)
                    else:
                        logger.info(
                            "Step 3: Scoring audio seed via TRIBE v2 (%s) — "
                            "one score broadcast to all %d variants",
                            media_path, len(variants),
                        )
                        # Single seed-audio score broadcast across variants —
                        # variant-level audio mutations are out of scope for A.1.
                        audio_score = await self._tribe_client.score_audio(media_path)
                        tribe_scores_list = [audio_score] * len(variants)
                elif media_type == "video":
                    if not media_path:
                        logger.warning(
                            "Campaign %s declared media_type='video' but has no "
                            "media_path; skipping TRIBE scoring", campaign_id,
                        )
                        tribe_scores_list = [None] * len(variants)
                    else:
                        logger.info(
                            "Step 3: Scoring video seed via TRIBE v2 V-JEPA2 (%s) — "
                            "one score broadcast to all %d variants",
                            media_path, len(variants),
                        )
                        # Same broadcast pattern as audio (Phase 2 A.2).
                        video_score = await self._tribe_client.score_video(media_path)
                        tribe_scores_list = [video_score] * len(variants)
                else:
                    logger.info("Step 3: Scoring %d variants with TRIBE v2", len(variants))
                    tribe_scores_list = await self._tribe_scoring.score_variants(variants)
            else:
                logger.info("Step 3: Skipping TRIBE scoring (unavailable)")
                tribe_scores_list = [None] * len(variants)

            # Step 4: MiroFish simulation (if available)
            mirofish_metrics_list: list[dict[str, Any] | None] = []
            if availability.mirofish_available:
                logger.info("Step 4: Running MiroFish simulations for %d variants", len(variants))
                mirofish_metrics_list = await self._mirofish_runner.simulate_variants(
                    variants=variants,
                    prediction_question=campaign.prediction_question,
                    campaign_id=campaign_id,
                    agent_count=campaign.agent_count,
                    max_rounds=5,
                )
            else:
                logger.info("Step 4: Skipping MiroFish simulation (unavailable)")
                mirofish_metrics_list = [None] * len(variants)

            # Step 5: Compute composite scores
            logger.info("Step 5: Computing composite scores")
            cognitive_weights = _get_weights(campaign.demographic)
            composite_scores_list: list[dict[str, float | None]] = []
            for i, variant in enumerate(variants):
                tribe = tribe_scores_list[i] if i < len(tribe_scores_list) else None
                mirofish = mirofish_metrics_list[i] if i < len(mirofish_metrics_list) else None
                composite = compute_composite_scores(
                    tribe=tribe,
                    mirofish=mirofish,
                    cognitive_weights=cognitive_weights,
                    agent_count=campaign.agent_count,
                )
                composite_scores_list.append(composite)

            # Step 5b: Persist iterations to DB
            for i, variant in enumerate(variants):
                tribe = tribe_scores_list[i] if i < len(tribe_scores_list) else None
                mirofish = mirofish_metrics_list[i] if i < len(mirofish_metrics_list) else None
                composite = composite_scores_list[i]
                await self._store.save_iteration(
                    campaign_id=campaign_id,
                    iteration_number=iteration_number,
                    variant_id=variant["id"],
                    variant_content=variant["content"],
                    variant_strategy=variant.get("strategy"),
                    tribe_scores=tribe,
                    mirofish_metrics=mirofish,
                    composite_scores=composite,
                )

            # Step 6: Cross-system analysis (Claude Opus)
            logger.info("Step 6: Running Claude Opus cross-system analysis")
            variants_with_scores = []
            for i, variant in enumerate(variants):
                variants_with_scores.append({
                    "variant_id": variant["id"],
                    "content": variant["content"],
                    "strategy": variant.get("strategy", ""),
                    "tribe_scores": tribe_scores_list[i] if i < len(tribe_scores_list) else None,
                    "mirofish_metrics": mirofish_metrics_list[i] if i < len(mirofish_metrics_list) else None,
                    "composite_scores": composite_scores_list[i],
                })

            analysis = await self._result_analyzer.analyze_iteration(
                iteration_number=iteration_number,
                campaign_brief=campaign.seed_content,
                prediction_question=campaign.prediction_question,
                demographic=campaign.demographic,
                demographic_custom=campaign.demographic_custom,
                variants_with_scores=variants_with_scores,
                thresholds=campaign.thresholds,
                previous_analysis=previous_analysis,
            )

            # Step 6b: Persist analysis to DB
            await self._store.save_analysis(
                campaign_id=campaign_id,
                iteration_number=iteration_number,
                analysis_json=analysis,
                system_availability={
                    "tribe_available": availability.tribe_available,
                    "mirofish_available": availability.mirofish_available,
                },
            )

            # Step 6c: Compute data_completeness (Landmine 5)
            tribe_real = sum(
                1 for t in tribe_scores_list if t and not t.get("is_pseudo_score")
            )
            tribe_pseudo = sum(
                1 for t in tribe_scores_list if t and t.get("is_pseudo_score")
            )
            mirofish_ok = any(m is not None for m in mirofish_metrics_list)

            missing: set[str] = set()
            for comp in composite_scores_list:
                if comp:
                    for key, val in comp.items():
                        if val is None:
                            missing.add(key)

            data_completeness = DataCompleteness(
                tribe_available=any(t is not None for t in tribe_scores_list),
                mirofish_available=mirofish_ok,
                tribe_real_score_count=tribe_real,
                tribe_pseudo_score_count=tribe_pseudo,
                missing_composite_dimensions=sorted(missing),
                has_audio=(media_type == "audio"),
                has_video=(media_type == "video"),
                media_type=media_type,
            )

            # Update status to completed (skip if caller manages status)
            if manage_status:
                await self._store.update_campaign_status(campaign_id, "completed")

            result = {
                "campaign_id": campaign_id,
                "iteration_number": iteration_number,
                "variants": variants,
                "tribe_scores": tribe_scores_list,
                "mirofish_metrics": mirofish_metrics_list,
                "composite_scores": composite_scores_list,
                "analysis": analysis,
                "system_availability": {
                    "tribe_available": availability.tribe_available,
                    "mirofish_available": availability.mirofish_available,
                },
                "data_completeness": data_completeness,
                "warnings": availability.warnings,
            }

            logger.info("Campaign %s iteration %d completed successfully", campaign_id, iteration_number)
            return result

        except Exception as e:
            logger.error("Campaign %s iteration %d failed: %s", campaign_id, iteration_number, e)
            if manage_status:
                await self._store.update_campaign_status(campaign_id, "failed", error=str(e))
            raise

    async def run_campaign(
        self,
        campaign_id: str,
        progress_callback: Callable[[dict], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """
        Multi-iteration optimization loop.

        Calls run_single_iteration() in a loop, passing previous results forward.
        Checks thresholds (D-06, D-07) and convergence (D-05) after each iteration.
        Emits progress events via optional callback.

        Per D-01: Full previous results passed forward.
        Per D-02: 3 variants per iteration (already default).
        Per D-03: Replace all variants each iteration (no carry-forward).
        Per D-04: Opus recommendations in iteration_note.
        Per D-08: max_iterations is hard cap.

        Args:
            campaign_id: Campaign to run.
            progress_callback: Optional async callback for progress events.

        Returns:
            Dict with campaign_id, iterations, stop_reason, iterations_completed,
            best_scores_history, improvement_history.
        """
        campaign = await self._store.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        max_iterations = campaign.max_iterations
        thresholds = campaign.thresholds

        # Set campaign status to running (loop manages status)
        await self._store.update_campaign_status(campaign_id, "running")

        estimator = TimeEstimator()
        total_steps_per_iteration = 5  # generating, scoring, simulating, analyzing, checking

        previous_results: list[dict[str, Any]] | None = None
        previous_analysis: dict[str, Any] | None = None
        best_scores_history: list[dict[str, float | None]] = []
        improvement_history: list[float] = []
        observed_step_durations: list[float] = []
        all_iteration_results: list[dict[str, Any]] = []
        stop_reason = "max_iterations"

        loop_error: Exception | None = None

        try:
            for iteration in range(1, max_iterations + 1):
                # Emit iteration_start event
                if progress_callback:
                    eta = estimator.estimate_remaining(
                        current_iteration=iteration,
                        current_step=0,
                        total_steps_per_iteration=total_steps_per_iteration,
                        max_iterations=max_iterations,
                        observed_step_durations=observed_step_durations,
                    )
                    await progress_callback({
                        "event": "iteration_start",
                        "campaign_id": campaign_id,
                        "iteration": iteration,
                        "max_iterations": max_iterations,
                        "eta_seconds": eta * 60,
                    })

                # Run the single iteration (status managed by this loop)
                result = await self.run_single_iteration(
                    campaign_id=campaign_id,
                    iteration_number=iteration,
                    previous_iteration_results=previous_results,
                    previous_analysis=previous_analysis,
                    manage_status=False,
                )

                # Extract best composite scores for threshold/convergence checks
                best_composite = find_best_composite(result["composite_scores"])
                best_scores_history.append(best_composite)

                # Compute improvement if we have 2+ iterations
                if len(best_scores_history) >= 2:
                    improvement = compute_improvement(
                        best_scores_history[-1], best_scores_history[-2]
                    )
                    improvement_history.append(improvement)

                # Build feedback for next iteration
                previous_results = build_iteration_feedback(result, result["analysis"])
                previous_analysis = result["analysis"]

                # Track result
                all_iteration_results.append(result)

                # Emit iteration_complete event
                if progress_callback:
                    await progress_callback({
                        "event": "iteration_complete",
                        "campaign_id": campaign_id,
                        "iteration": iteration,
                        "max_iterations": max_iterations,
                        "best_scores": best_composite,
                    })

                # Check thresholds (D-06, D-07)
                if thresholds:
                    all_met, threshold_status = check_thresholds(best_composite, thresholds)
                    if progress_callback:
                        await progress_callback({
                            "event": "threshold_check",
                            "campaign_id": campaign_id,
                            "iteration": iteration,
                            "all_met": all_met,
                            "status": threshold_status,
                        })
                    if all_met:
                        stop_reason = "thresholds_met"
                        break

                # Check convergence (D-05 -- need at least 2 improvement values)
                if len(improvement_history) >= 2:
                    if is_converged(improvement_history):
                        stop_reason = "converged"
                        break

        except Exception as e:
            logger.error("Campaign %s failed during iteration loop: %s", campaign_id, e)
            loop_error = e
            stop_reason = "error"
            if progress_callback:
                await progress_callback({
                    "event": "campaign_error",
                    "campaign_id": campaign_id,
                    "error": str(e),
                })

        # Generate report from whatever data was saved (even after partial failure).
        # Iterations are persisted to DB inside run_single_iteration before the
        # analysis step, so we may have usable data even if the loop errored out.
        if self._report_generator:
            try:
                all_iterations_db = await self._store.get_iterations(campaign_id)
                if all_iterations_db:
                    if progress_callback:
                        await progress_callback({
                            "event": "report_generating",
                            "campaign_id": campaign_id,
                        })

                    all_analyses_db = await self._store._get_analyses(campaign_id)

                    report = await self._report_generator.generate_report(
                        campaign=campaign,
                        all_iterations=all_iterations_db,
                        all_analyses=all_analyses_db,
                        best_scores_history=best_scores_history,
                        stop_reason=stop_reason,
                    )
                    await self._store.save_report(campaign_id=campaign_id, report=report)

                    if progress_callback:
                        await progress_callback({
                            "event": "report_complete",
                            "campaign_id": campaign_id,
                        })
                    logger.info("Report generated for campaign %s", campaign_id)
                else:
                    logger.warning("No iteration data saved for campaign %s; skipping report generation", campaign_id)
            except Exception as report_err:
                logger.error("Report generation failed for campaign %s: %s", campaign_id, report_err)
                if progress_callback:
                    await progress_callback({
                        "event": "report_failed",
                        "campaign_id": campaign_id,
                        "error": str(report_err),
                    })
                # Do NOT re-raise -- campaign data is already saved (per Pitfall 5)

        # Set final status based on whether the loop succeeded
        if loop_error:
            await self._store.update_campaign_status(campaign_id, "failed", error=str(loop_error))
            if progress_callback:
                await progress_callback({
                    "event": "campaign_complete",
                    "campaign_id": campaign_id,
                    "stop_reason": stop_reason,
                    "iterations_completed": len(all_iteration_results),
                })
            raise loop_error
        else:
            await self._store.update_campaign_status(campaign_id, "completed")

            # Emit campaign_complete event
            if progress_callback:
                await progress_callback({
                    "event": "campaign_complete",
                    "campaign_id": campaign_id,
                    "stop_reason": stop_reason,
                    "iterations_completed": len(all_iteration_results),
                })

            return {
                "campaign_id": campaign_id,
                "iterations": all_iteration_results,
                "stop_reason": stop_reason,
                "iterations_completed": len(all_iteration_results),
                "best_scores_history": best_scores_history,
                "improvement_history": improvement_history,
            }


def _get_weights(demographic: str) -> dict[str, float]:
    """Get cognitive weights for a demographic. Returns uniform weights for custom demographics."""
    if demographic == "custom":
        return {
            "attention_capture": 1.0,
            "emotional_resonance": 1.0,
            "memory_encoding": 1.0,
            "reward_response": 1.0,
            "threat_detection": 1.0,
            "cognitive_load": 1.0,
            "social_relevance": 1.0,
        }
    return get_cognitive_weights(demographic)
