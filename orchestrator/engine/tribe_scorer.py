"""
TRIBE v2 neural scoring pipeline for the A.R.C Studio orchestrator.

Orchestrates TRIBE v2 scoring of multiple content variants using the batch
endpoint for efficiency and reliability. Falls back to sequential single-text
scoring if the batch endpoint fails.

Per D-03: Variants are scored without GPU contention on the single RTX 5070 Ti.
Returns None per variant on failure without crashing the overall campaign (D-05).
"""

import logging
from typing import Any

from orchestrator.clients.tribe_client import TribeClient

logger = logging.getLogger(__name__)


class TribeScoringPipeline:
    """
    Orchestrates TRIBE v2 neural scoring for multiple content variants.

    Prefers batch scoring via /api/score/batch for:
    - Reduced HTTP overhead (1 request instead of N)
    - Server-side sequential processing with consistent batch normalization
    - Single timeout window instead of N separate timeouts
    - Automatic retry logic in the client

    Falls back to sequential single-text scoring if the batch call fails.
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
        if not variants:
            return []

        # Collect texts, tracking which variants have empty content
        texts: list[str] = []
        text_indices: list[int] = []  # maps position in texts[] back to variants[]
        results: list[dict[str, float] | None] = [None] * len(variants)

        for i, variant in enumerate(variants):
            content = variant.get("content", "")
            variant_id = variant.get("id", f"variant_{i}")
            if not content.strip():
                logger.warning(
                    "Variant %s has empty content, skipping TRIBE scoring",
                    variant_id,
                )
                continue
            texts.append(content)
            text_indices.append(i)

        if not texts:
            logger.warning("No variants with content to score")
            return results

        logger.info("Scoring %d variants with TRIBE v2 (batch mode)", len(texts))

        # Try batch scoring first
        batch_scores = await self._client.score_texts_batch(texts)

        if batch_scores is not None and any(s is not None for s in batch_scores):
            # Batch produced at least some results -- use them
            for j, scores in enumerate(batch_scores):
                variant_idx = text_indices[j]
                variant_id = variants[variant_idx].get("id", f"variant_{variant_idx}")
                results[variant_idx] = scores
                if scores:
                    pseudo_tag = " [PSEUDO]" if scores.get("is_pseudo_score") else ""
                    logger.info(
                        "TRIBE scores for %s%s: attention=%.1f, emotion=%.1f, memory=%.1f",
                        variant_id, pseudo_tag,
                        scores.get("attention_capture", 0),
                        scores.get("emotional_resonance", 0),
                        scores.get("memory_encoding", 0),
                    )
                    if scores.get("is_pseudo_score"):
                        logger.warning(
                            "Variant %s received PSEUDO-SCORES — results are text-feature approximations, NOT real brain-encoding predictions",
                            variant_id,
                        )
                else:
                    logger.warning("TRIBE batch returned None for variant %s", variant_id)
        else:
            # Batch failed entirely -- fall back to sequential single-text scoring
            logger.warning(
                "TRIBE batch scoring failed for all texts, falling back to sequential"
            )
            for j, text in enumerate(texts):
                variant_idx = text_indices[j]
                variant_id = variants[variant_idx].get("id", f"variant_{variant_idx}")

                logger.info(
                    "Scoring variant %s with TRIBE v2 (%d/%d, sequential fallback)",
                    variant_id, j + 1, len(texts),
                )

                scores = await self._client.score_text(text)
                results[variant_idx] = scores

                if scores:
                    pseudo_tag = " [PSEUDO]" if scores.get("is_pseudo_score") else ""
                    logger.info(
                        "TRIBE scores for %s%s: attention=%.1f, emotion=%.1f, memory=%.1f",
                        variant_id, pseudo_tag,
                        scores.get("attention_capture", 0),
                        scores.get("emotional_resonance", 0),
                        scores.get("memory_encoding", 0),
                    )
                    if scores.get("is_pseudo_score"):
                        logger.warning(
                            "Variant %s received PSEUDO-SCORES — results are text-feature approximations, NOT real brain-encoding predictions",
                            variant_id,
                        )
                else:
                    logger.warning("TRIBE scoring returned None for variant %s", variant_id)

        scored_count = sum(1 for r in results if r is not None)
        logger.info("TRIBE scoring complete: %d/%d variants scored", scored_count, len(variants))

        return results
