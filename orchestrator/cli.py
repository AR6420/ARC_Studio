"""
CLI entry point for running Nexus Sim campaigns from the command line.

Usage:
    python -m orchestrator.cli --seed-content "Your content here..." --prediction-question "How will the audience react?" --demographic tech_professionals

    # Or with a file:
    python -m orchestrator.cli --seed-file content.txt --prediction-question "..." --demographic tech_professionals

Per ORCH-14: Produces variants, scores, metrics, and analysis without needing the FastAPI server.
"""

import argparse
import asyncio
import json
import json as json_module
import logging
import sys
from pathlib import Path
from typing import Any

import httpx

from orchestrator.config import settings
from orchestrator.storage.database import Database
from orchestrator.storage.campaign_store import CampaignStore
from orchestrator.clients.claude_client import ClaudeClient
from orchestrator.clients.tribe_client import TribeClient
from orchestrator.clients.mirofish_client import MirofishClient
from orchestrator.engine.variant_generator import VariantGenerator
from orchestrator.engine.tribe_scorer import TribeScoringPipeline
from orchestrator.engine.mirofish_runner import MirofishRunner
from orchestrator.engine.result_analyzer import ResultAnalyzer
from orchestrator.engine.campaign_runner import CampaignRunner
from orchestrator.engine.report_generator import ReportGenerator
from orchestrator.api.schemas import CampaignCreateRequest, ReportResponse

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a Nexus Sim campaign from the command line",
        prog="python -m orchestrator.cli",
    )
    content_group = parser.add_mutually_exclusive_group(required=True)
    content_group.add_argument("--seed-content", type=str, help="Seed content text (inline)")
    content_group.add_argument("--seed-file", type=str, help="Path to a text file with seed content")

    parser.add_argument("--prediction-question", required=True, type=str,
                       help="What you want to know about audience response")
    parser.add_argument("--demographic", required=True, type=str,
                       help="Demographic preset key (e.g., tech_professionals) or 'custom'")
    parser.add_argument("--demographic-custom", type=str, default=None,
                       help="Custom demographic description (when --demographic=custom)")
    parser.add_argument("--agent-count", type=int, default=40, help="Number of MiroFish agents (default: 40)")
    parser.add_argument("--max-iterations", type=int, default=4, help="Max optimization iterations (default: 4)")
    parser.add_argument("--thresholds", type=str, default=None,
                       help='JSON thresholds, e.g. \'{"attention_score": 70.0}\'')
    parser.add_argument("--constraints", type=str, default=None, help="Brand guidelines or constraints")
    parser.add_argument("--output", type=str, default=None, help="Path to write JSON results (default: stdout)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    return parser.parse_args(argv)


async def run_campaign(args: argparse.Namespace) -> dict[str, Any]:
    """
    Run a single-iteration campaign programmatically.
    Initializes all dependencies, creates campaign, runs pipeline, returns results.
    """
    # Initialize all resources
    db = Database(str(settings.database_path_absolute))
    await db.connect()

    tribe_http = httpx.AsyncClient(base_url=settings.tribe_scorer_url, timeout=120.0)
    mirofish_http = httpx.AsyncClient(base_url=settings.mirofish_url, timeout=300.0)

    try:
        # Create all components
        store = CampaignStore(db)
        claude = ClaudeClient()
        tribe_client = TribeClient(tribe_http)
        mirofish_client = MirofishClient(mirofish_http)

        variant_gen = VariantGenerator(claude)
        tribe_scoring = TribeScoringPipeline(tribe_client)
        mirofish_runner = MirofishRunner(mirofish_client)
        result_analyzer = ResultAnalyzer(claude)
        report_generator = ReportGenerator(claude)

        runner = CampaignRunner(
            variant_generator=variant_gen,
            tribe_scoring=tribe_scoring,
            mirofish_runner=mirofish_runner,
            result_analyzer=result_analyzer,
            campaign_store=store,
            tribe_client=tribe_client,
            mirofish_client=mirofish_client,
            report_generator=report_generator,
        )

        # Load seed content
        if args.seed_file:
            seed_content = Path(args.seed_file).read_text(encoding="utf-8")
        else:
            seed_content = args.seed_content

        # Parse thresholds if provided
        thresholds = None
        if hasattr(args, "thresholds") and args.thresholds:
            thresholds = json_module.loads(args.thresholds)

        max_iterations = getattr(args, "max_iterations", 4)

        # Create campaign
        request = CampaignCreateRequest(
            seed_content=seed_content,
            prediction_question=args.prediction_question,
            demographic=args.demographic,
            demographic_custom=args.demographic_custom,
            agent_count=args.agent_count,
            max_iterations=max_iterations,
            thresholds=thresholds,
            constraints=args.constraints,
            auto_start=False,
        )
        campaign = await store.create_campaign(request)
        print(f"\n{'='*60}")
        print(f"Campaign created: {campaign.id}")
        print(f"Demographic: {args.demographic}")
        print(f"Agent count: {args.agent_count}")
        print(f"Max iterations: {max_iterations}")
        print(f"{'='*60}\n")

        async def cli_progress_callback(event: dict):
            """Print progress events to console."""
            evt = event.get("event", "")
            if evt == "iteration_start":
                iteration = event.get("iteration", "?")
                max_iter = event.get("max_iterations", "?")
                eta = event.get("eta_seconds")
                eta_str = f" (ETA: {eta:.0f}s)" if eta else ""
                print(f"\n--- Iteration {iteration}/{max_iter}{eta_str} ---")
            elif evt == "iteration_complete":
                iteration = event.get("iteration", "?")
                print(f"--- Iteration {iteration} complete ---")
            elif evt == "threshold_check":
                all_met = event.get("all_met", False)
                print(f"  Thresholds: {'ALL MET' if all_met else 'not yet met'}")
            elif evt == "convergence_check":
                data = event.get("data", {})
                converged = data.get("converged", False)
                print(f"  Convergence: {'CONVERGED' if converged else 'continuing'}")
            elif evt == "report_generating":
                print("\nGenerating final report...")
            elif evt == "report_complete":
                print("Report generated successfully.")
            elif evt == "report_failed":
                print(f"  WARNING: Report generation failed: {event.get('error', 'unknown')}")
            elif evt == "campaign_complete":
                reason = event.get("stop_reason", "unknown")
                print(f"\nCampaign complete. Stop reason: {reason}")

        # Run multi-iteration campaign
        result = await runner.run_campaign(
            campaign_id=campaign.id,
            progress_callback=cli_progress_callback,
        )

        # Print summary
        _print_summary(result)

        # Print report summary if available
        report = await store.get_report(campaign.id)
        if report:
            _print_report_summary(report)

        return result

    finally:
        await tribe_http.aclose()
        await mirofish_http.aclose()
        await db.close()


def _print_summary(result: dict[str, Any]) -> None:
    """Print a human-readable summary of campaign results.

    Handles both multi-iteration results (from run_campaign()) with
    'iterations', 'stop_reason', 'iterations_completed', 'best_scores_history'
    and single-iteration results (from run_single_iteration()) with
    'variants', 'tribe_scores', etc.
    """
    print(f"\n{'='*60}")

    # Multi-iteration result (from run_campaign)
    iterations = result.get("iterations")
    if iterations is not None:
        stop_reason = result.get("stop_reason", "unknown")
        iterations_completed = result.get("iterations_completed", len(iterations))
        best_scores_history = result.get("best_scores_history", [])

        print(f"CAMPAIGN RESULTS ({iterations_completed} iteration(s), stop: {stop_reason})")
        print(f"{'='*60}\n")

        # Best scores trajectory
        if best_scores_history:
            print("BEST SCORES TRAJECTORY:")
            for i, scores in enumerate(best_scores_history, 1):
                summary_parts = []
                for name, val in scores.items():
                    if val is not None:
                        summary_parts.append(f"{name}={val:.1f}" if isinstance(val, float) else f"{name}={val}")
                print(f"  Iteration {i}: {', '.join(summary_parts) if summary_parts else 'N/A'}")
            print()

        # Print details for the last iteration
        if iterations:
            last = iterations[-1]
            _print_single_iteration(last)
        return

    # Single-iteration result (from run_single_iteration -- backward compat)
    print("CAMPAIGN RESULTS")
    print(f"{'='*60}\n")
    _print_single_iteration(result)


def _print_single_iteration(result: dict[str, Any]) -> None:
    """Print details for a single iteration result."""
    # System availability
    avail = result.get("system_availability", {})
    warnings = result.get("warnings", [])
    print(f"TRIBE v2: {'Available' if avail.get('tribe_available') else 'UNAVAILABLE'}")
    print(f"MiroFish: {'Available' if avail.get('mirofish_available') else 'UNAVAILABLE'}")
    if warnings:
        for w in warnings:
            print(f"  WARNING: {w}")
    print()

    # Variants and scores
    variants = result.get("variants", [])
    tribe_scores = result.get("tribe_scores", [])
    mirofish_metrics = result.get("mirofish_metrics", [])
    composite_scores = result.get("composite_scores", [])

    for i, variant in enumerate(variants):
        print(f"--- Variant: {variant.get('id', f'v{i+1}')} ---")
        print(f"Strategy: {variant.get('strategy', 'N/A')}")
        print(f"Content preview: {variant.get('content', '')[:150]}...")
        print()

        # TRIBE scores
        tribe = tribe_scores[i] if i < len(tribe_scores) and tribe_scores[i] else None
        if tribe:
            print("  TRIBE v2 scores:")
            for dim, score in tribe.items():
                print(f"    {dim}: {score:.1f}")
        else:
            print("  TRIBE v2 scores: N/A")

        # MiroFish metrics
        miro = mirofish_metrics[i] if i < len(mirofish_metrics) and mirofish_metrics[i] else None
        if miro:
            print("  MiroFish metrics:")
            for key, val in miro.items():
                if not isinstance(val, list):
                    print(f"    {key}: {val}")
        else:
            print("  MiroFish metrics: N/A")

        # Composite scores
        comp = composite_scores[i] if i < len(composite_scores) else {}
        if comp:
            print("  Composite scores:")
            for name, score in comp.items():
                print(f"    {name}: {score if score is not None else 'N/A'}")
        print()

    # Analysis
    analysis = result.get("analysis", {})
    ranking = analysis.get("ranking", [])
    if ranking:
        print(f"RANKING: {' > '.join(ranking)}")
    print()

    insights = analysis.get("cross_system_insights", [])
    if insights:
        print("CROSS-SYSTEM INSIGHTS:")
        for insight in insights:
            print(f"  - {insight}")
    print()

    recs = analysis.get("recommendations_for_next_iteration", [])
    if recs:
        print("RECOMMENDATIONS:")
        for rec in recs:
            print(f"  - {rec}")

    print(f"\n{'='*60}\n")


def _print_report_summary(report: ReportResponse) -> None:
    """Print a concise report summary after campaign completion."""
    print(f"\n{'='*60}")
    print("REPORT SUMMARY")
    print(f"{'='*60}\n")

    # Verdict (first 300 chars)
    if report.verdict:
        verdict_preview = report.verdict[:300]
        if len(report.verdict) > 300:
            verdict_preview += "..."
        print(f"VERDICT: {verdict_preview}")
        print()

    # Winning variant from scorecard
    if report.scorecard:
        print(f"WINNING VARIANT: {report.scorecard.winning_variant_id}")
        print(f"SCORECARD: {report.scorecard.summary}")
        print()

    # Mass psychology note
    has_general = report.mass_psychology_general is not None
    has_technical = report.mass_psychology_technical is not None
    if has_general or has_technical:
        parts = []
        if has_general:
            parts.append("general narrative")
        if has_technical:
            parts.append("technical analysis")
        print(f"MASS PSYCHOLOGY: {', '.join(parts)} available")

    print(f"\n{'='*60}\n")


def main(argv: list[str] | None = None):
    args = parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

    result = asyncio.run(run_campaign(args))

    if args.output:
        # Write full results as JSON
        output_path = Path(args.output)
        # Convert to JSON-serializable format (handle None, etc.)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"Full results written to {output_path}")


if __name__ == "__main__":
    main()
