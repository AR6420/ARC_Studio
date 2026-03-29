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
from orchestrator.api.schemas import CampaignCreateRequest

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

        runner = CampaignRunner(
            variant_generator=variant_gen,
            tribe_scoring=tribe_scoring,
            mirofish_runner=mirofish_runner,
            result_analyzer=result_analyzer,
            campaign_store=store,
            tribe_client=tribe_client,
            mirofish_client=mirofish_client,
        )

        # Load seed content
        if args.seed_file:
            seed_content = Path(args.seed_file).read_text(encoding="utf-8")
        else:
            seed_content = args.seed_content

        # Create campaign
        request = CampaignCreateRequest(
            seed_content=seed_content,
            prediction_question=args.prediction_question,
            demographic=args.demographic,
            demographic_custom=args.demographic_custom,
            agent_count=args.agent_count,
            constraints=args.constraints,
            auto_start=False,
        )
        campaign = await store.create_campaign(request)
        print(f"\n{'='*60}")
        print(f"Campaign created: {campaign.id}")
        print(f"Demographic: {args.demographic}")
        print(f"Agent count: {args.agent_count}")
        print(f"{'='*60}\n")

        # Run single iteration
        result = await runner.run_single_iteration(
            campaign_id=campaign.id,
            iteration_number=1,
        )

        # Print summary
        _print_summary(result)

        return result

    finally:
        await tribe_http.aclose()
        await mirofish_http.aclose()
        await db.close()


def _print_summary(result: dict[str, Any]) -> None:
    """Print a human-readable summary of campaign results."""
    print(f"\n{'='*60}")
    print("CAMPAIGN RESULTS")
    print(f"{'='*60}\n")

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
