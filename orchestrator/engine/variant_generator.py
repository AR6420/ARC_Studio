"""
Content variant generator for A.R.C Studio.

Uses Claude Haiku to generate N distinct content variants from a campaign brief
and demographic profile. Each variant takes a meaningfully different strategic
approach so that TRIBE v2 + MiroFish scoring can distinguish them and the
feedback loop can converge toward an optimal strategy.

Per D-01: generates 2 variants per iteration by default (reduced from 3 in B.1 scope reduction).
"""

import logging
from typing import Any

from orchestrator.clients.claude_client import ClaudeClient
from orchestrator.prompts.variant_generation import (
    VARIANT_GENERATION_SYSTEM,
    build_variant_generation_prompt,
)
from orchestrator.prompts.demographic_profiles import get_profile

logger = logging.getLogger(__name__)


class VariantGenerator:
    """
    Generates content variants using Claude Haiku.
    Per D-01: generates 2 variants per iteration (reduced from 3 in B.1 scope reduction).
    """

    def __init__(self, claude_client: ClaudeClient) -> None:
        self._claude = claude_client

    async def generate_variants(
        self,
        campaign_brief: str,
        demographic: str,
        demographic_custom: str | None = None,
        num_variants: int = 2,
        constraints: str | None = None,
        previous_iteration_results: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generate N content variants using Claude Haiku.

        Args:
            campaign_brief: The seed content / campaign description.
            demographic: Preset key (e.g., "tech_professionals") or "custom".
            demographic_custom: Free-text description if demographic="custom".
            num_variants: Number of variants to generate (default 2, per D-01 + B.1 scope reduction).
            constraints: Optional brand guidelines.
            previous_iteration_results: Scores from prior iteration for improvement (Phase 6).

        Returns:
            List of variant dicts, each with: id, content, strategy,
            key_psychological_mechanisms, expected_strengths, potential_risks.

        Raises:
            ValueError: If Claude returns unparseable or invalid response after retries.
        """
        # Resolve demographic description
        if demographic == "custom":
            demo_description = demographic_custom or "General audience"
        else:
            profile = get_profile(demographic)
            demo_description = profile["description"]

        # Build the prompt
        user_prompt = build_variant_generation_prompt(
            campaign_brief=campaign_brief,
            demographic_description=demo_description,
            num_variants=num_variants,
            constraints=constraints,
            previous_iteration_results=previous_iteration_results,
        )

        # Call Claude Haiku (JSON mode)
        result = await self._claude.call_haiku_json(
            system=VARIANT_GENERATION_SYSTEM,
            user=user_prompt,
            max_tokens=8192,
        )

        variants = result.get("variants", [])
        if len(variants) != num_variants:
            logger.warning(
                "Expected %d variants but got %d; using what was returned",
                num_variants,
                len(variants),
            )

        # Validate each variant has required fields
        validated: list[dict[str, Any]] = []
        for v in variants:
            validated.append(
                {
                    "id": v.get("id", f"v{len(validated) + 1}_unknown"),
                    "content": v.get("content", ""),
                    "strategy": v.get("strategy", ""),
                    "key_psychological_mechanisms": v.get(
                        "key_psychological_mechanisms", []
                    ),
                    "expected_strengths": v.get("expected_strengths", []),
                    "potential_risks": v.get("potential_risks", []),
                }
            )

        # Enforce 150-word hard limit (B.1 scope reduction)
        MAX_VARIANT_WORDS = 150
        for v in validated:
            words = v["content"].split()
            if len(words) > MAX_VARIANT_WORDS:
                logger.warning(
                    "Variant %s has %d words (limit %d). Truncating at sentence boundary.",
                    v["id"], len(words), MAX_VARIANT_WORDS,
                )
                truncated = " ".join(words[:MAX_VARIANT_WORDS])
                # Try to end at a sentence boundary
                for end_char in (".", "!", "?"):
                    last_pos = truncated.rfind(end_char)
                    if last_pos > len(truncated) // 2:  # Don't cut more than half
                        truncated = truncated[: last_pos + 1]
                        break
                v["content"] = truncated

        logger.info(
            "Generated %d variants for demographic '%s'",
            len(validated),
            demographic,
        )
        return validated
