"""
Run MiroFish simulations for existing PSA campaign variants and patch results.

Reads variant content from results/public_health_psa_rerun.json,
runs MiroFish for each variant, computes metrics, and patches them
back into the results file.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

import httpx

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.config import settings
from orchestrator.clients.mirofish_client import MirofishClient
from orchestrator.engine.mirofish_runner import MirofishRunner, compute_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

RESULTS_PATH = Path("results/public_health_psa_rerun.json")
PREDICTION_QUESTION = "Will this PSA drive vaccine uptake or create anti-vaccine backlash?"
AGENT_COUNT = 20
MAX_ROUNDS = 30


async def main():
    # Load existing results
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    iterations = data.get("iterations", [])
    campaign_id = data.get("campaign_id", "psa_mirofish_patch")

    # Collect all variants across iterations
    all_variants = []
    for it_idx, iteration in enumerate(iterations):
        for variant in iteration.get("variants", []):
            all_variants.append({
                "iteration": it_idx,
                "id": variant["id"],
                "content": variant["content"],
            })

    logger.info("Found %d variants across %d iterations", len(all_variants), len(iterations))

    # Initialize MiroFish client
    mirofish_http = httpx.AsyncClient(base_url=settings.mirofish_url, timeout=300.0)
    mirofish_client = MirofishClient(mirofish_http, litellm_url=settings.litellm_url)

    try:
        # Health check
        healthy = await mirofish_client.health_check()
        if not healthy:
            logger.error("MiroFish is not healthy. Aborting.")
            return

        logger.info("MiroFish is healthy. Starting simulations...")

        # Run simulations sequentially (Neo4j conflict avoidance)
        for i, var_info in enumerate(all_variants):
            it_idx = var_info["iteration"]
            variant_id = var_info["id"]
            content = var_info["content"]

            # Check if this variant already has MiroFish metrics
            existing_metrics = iterations[it_idx].get("mirofish_metrics", [])
            var_index = next(
                (j for j, v in enumerate(iterations[it_idx]["variants"]) if v["id"] == variant_id),
                None,
            )
            if var_index is not None and var_index < len(existing_metrics) and existing_metrics[var_index]:
                logger.info(
                    "Skipping %s (iter %d) - already has MiroFish metrics",
                    variant_id, it_idx + 1,
                )
                continue

            logger.info(
                "Running MiroFish for %s (iter %d, %d/%d)",
                variant_id, it_idx + 1, i + 1, len(all_variants),
            )

            # Run simulation
            raw_results = await mirofish_client.run_simulation(
                content=content,
                simulation_requirement=PREDICTION_QUESTION,
                project_name=f"{campaign_id}_{variant_id}",
                max_rounds=MAX_ROUNDS,
            )

            if not raw_results:
                logger.warning("MiroFish returned None for %s", variant_id)
                # Ensure mirofish_metrics list exists and has None at this index
                while len(iterations[it_idx].setdefault("mirofish_metrics", [])) <= var_index:
                    iterations[it_idx]["mirofish_metrics"].append(None)
                iterations[it_idx]["mirofish_metrics"][var_index] = None
                continue

            # Unwrap nested response format
            unwrapped = {}
            for key in ("posts", "actions", "timeline", "agent_stats"):
                val = raw_results.get(key, [])
                if isinstance(val, dict):
                    inner = val.get(key) or val.get("stats") or val.get("timeline") or []
                    unwrapped[key] = inner
                else:
                    unwrapped[key] = val
            unwrapped["simulation_id"] = raw_results.get("simulation_id")

            # Compute metrics
            metrics = compute_metrics(unwrapped, AGENT_COUNT)
            total_shares = metrics.get("organic_shares", 0)
            counter = metrics.get("counter_narrative_count", 0)
            drift = metrics.get("sentiment_drift", 0)
            logger.info(
                "MiroFish metrics for %s: shares=%d, counter=%d, drift=%.2f",
                variant_id, total_shares, counter, drift,
            )

            # Patch into results
            while len(iterations[it_idx].setdefault("mirofish_metrics", [])) <= var_index:
                iterations[it_idx]["mirofish_metrics"].append(None)
            iterations[it_idx]["mirofish_metrics"][var_index] = metrics

            # Update system_availability
            iterations[it_idx].setdefault("system_availability", {})["mirofish_available"] = True

        # Save patched results
        data["iterations"] = iterations
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("Patched results saved to %s", RESULTS_PATH)

        # Print summary
        print(f"\n{'='*60}")
        print("MIROFISH PATCH SUMMARY")
        print(f"{'='*60}")
        for it_idx, iteration in enumerate(iterations):
            print(f"\nIteration {it_idx + 1}:")
            metrics_list = iteration.get("mirofish_metrics", [])
            for vi, variant in enumerate(iteration.get("variants", [])):
                m = metrics_list[vi] if vi < len(metrics_list) and metrics_list[vi] else None
                if m:
                    print(f"  {variant['id']}: shares={m['organic_shares']}, "
                          f"counter={m['counter_narrative_count']}, "
                          f"drift={m['sentiment_drift']:.2f}, "
                          f"coalitions={m['coalition_formation']}, "
                          f"gini={m['influence_concentration']:.3f}")
                else:
                    print(f"  {variant['id']}: N/A")
        print(f"\n{'='*60}")

    finally:
        await mirofish_http.aclose()


if __name__ == "__main__":
    asyncio.run(main())
