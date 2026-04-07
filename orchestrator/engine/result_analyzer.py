"""
Cross-system result analyzer for A.R.C Studio.

Uses Claude Opus to perform deep analysis that bridges TRIBE v2 neural scores
and MiroFish simulation metrics. The analysis MUST reference BOTH systems'
outputs -- an analysis that ignores one system fails the quality standard.

Per ORCH-12: Uses Claude Opus for deep cross-system reasoning.
"""

import json
import logging
from typing import Any

from orchestrator.clients.claude_client import ClaudeClient
from orchestrator.prompts.result_analysis import (
    RESULT_ANALYSIS_SYSTEM,
    build_result_analysis_prompt,
)
from orchestrator.prompts.demographic_profiles import get_profile

logger = logging.getLogger(__name__)


class ResultAnalyzer:
    """
    Performs cross-system analysis using Claude Opus.
    The analysis MUST reference BOTH TRIBE v2 neural scores AND MiroFish
    simulation metrics.
    Per ORCH-12: Uses Claude Opus for deep cross-system reasoning.
    """

    def __init__(self, claude_client: ClaudeClient):
        self._claude = claude_client

    async def analyze_iteration(
        self,
        iteration_number: int,
        campaign_brief: str,
        prediction_question: str,
        demographic: str,
        demographic_custom: str | None,
        variants_with_scores: list[dict[str, Any]],
        thresholds: dict[str, float] | None = None,
        previous_analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze a complete iteration's results using Claude Opus.

        Args:
            iteration_number: Which iteration (1-indexed).
            campaign_brief: Original seed content.
            prediction_question: What the user wants to know.
            demographic: Preset key or "custom".
            demographic_custom: Custom description if demographic="custom".
            variants_with_scores: List of dicts with variant_id, content, strategy,
                tribe_scores, mirofish_metrics, composite_scores.
            thresholds: User-defined score targets.
            previous_analysis: JSON from prior iteration analysis (for iteration > 1).

        Returns:
            Parsed analysis dict from Claude Opus with per_variant_assessment,
            ranking, cross_system_insights, recommendations_for_next_iteration, etc.

        Raises:
            ValueError: If Claude Opus response cannot be parsed.
        """
        # Resolve demographic description
        if demographic == "custom":
            demo_description = demographic_custom or "General audience"
        else:
            profile = get_profile(demographic)
            demo_description = profile["description"]

        # Build the prompt
        previous_analysis_str = None
        if previous_analysis:
            previous_analysis_str = json.dumps(previous_analysis, indent=2)

        user_prompt = build_result_analysis_prompt(
            iteration_number=iteration_number,
            campaign_brief=campaign_brief,
            prediction_question=prediction_question,
            demographic_description=demo_description,
            variants_with_scores=variants_with_scores,
            thresholds=thresholds,
            previous_analysis=previous_analysis_str,
        )

        logger.info("Calling Claude Opus for iteration %d cross-system analysis", iteration_number)

        result = await self._claude.call_opus_json(
            system=RESULT_ANALYSIS_SYSTEM,
            user=user_prompt,
            max_tokens=8192,
        )

        # Validate required fields
        required_keys = ["per_variant_assessment", "ranking", "cross_system_insights"]
        for key in required_keys:
            if key not in result:
                logger.warning("Opus analysis missing key '%s'", key)

        logger.info(
            "Opus analysis complete: ranked %d variants, %d cross-system insights",
            len(result.get("ranking", [])),
            len(result.get("cross_system_insights", [])),
        )

        return result
