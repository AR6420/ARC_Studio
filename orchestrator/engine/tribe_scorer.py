"""
TRIBE v2 neural scoring pipeline for the Nexus Sim orchestrator.

Orchestrates sequential TRIBE v2 scoring of multiple content variants.
Per D-03: Variants are scored SEQUENTIALLY to avoid GPU contention
on the single RTX 5070 Ti.

Returns None per variant on failure without crashing the overall campaign (D-05).
"""

import logging
from typing import Any

from orchestrator.clients.tribe_client import TribeClient

logger = logging.getLogger(__name__)


class TribeScoringPipeline:
    """
    Orchestrates TRIBE v2 neural scoring for multiple content variants.
    Per D-03: Variants are scored SEQUENTIALLY to avoid GPU contention
    on the single RTX 5070 Ti.
    """

    def __init__(self, tribe_client: TribeClient):
        self._client = tribe_client

    async def score_variants(
        self, variants: list[dict[str, Any]]
    ) -> list[dict[str, float] | None]:
        """
        Score each variant's content text through TRIBE v2.

        Args:
            variants: List of variant dicts, each with at least a "content" key.

        Returns:
            List of score dicts (7 dimensions, 0-100) or None per variant.
            Position matches input list. None indicates scoring failure for that variant.
        """
        results: list[dict[str, float] | None] = []

        for i, variant in enumerate(variants):
            variant_id = variant.get("id", f"variant_{i}")
            content = variant.get("content", "")

            if not content.strip():
                logger.warning("Variant %s has empty content, skipping TRIBE scoring", variant_id)
                results.append(None)
                continue

            logger.info("Scoring variant %s with TRIBE v2 (%d/%d)", variant_id, i + 1, len(variants))

            scores = await self._client.score_text(content)

            if scores:
                logger.info(
                    "TRIBE scores for %s: attention=%.1f, emotion=%.1f, memory=%.1f",
                    variant_id,
                    scores.get("attention_capture", 0),
                    scores.get("emotional_resonance", 0),
                    scores.get("memory_encoding", 0),
                )
            else:
                logger.warning("TRIBE scoring returned None for variant %s", variant_id)

            results.append(scores)

        scored_count = sum(1 for r in results if r is not None)
        logger.info("TRIBE scoring complete: %d/%d variants scored", scored_count, len(variants))

        return results
