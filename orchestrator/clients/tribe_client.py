"""
Async HTTP client for the TRIBE v2 neural scoring service.

Communicates with the TRIBE v2 FastAPI service (default: http://localhost:8001)
via an httpx.AsyncClient passed to the constructor. This allows the caller to
manage connection pooling and base_url centrally (e.g., in the FastAPI lifespan).

Design decisions:
- Constructor receives an httpx.AsyncClient (not a URL string) — shared pool.
- 120-second timeout for scoring (GPU inference takes 10-30s, budget for load).
- Returns None on any failure for graceful degradation (D-05).
- Filters response to only the 7 known brain-region dimensions.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TRIBE_SCORE_DIMENSIONS = [
    "attention_capture",
    "emotional_resonance",
    "memory_encoding",
    "reward_response",
    "threat_detection",
    "cognitive_load",
    "social_relevance",
]


class TribeClient:
    """Async HTTP client for the TRIBE v2 neural scoring service (port 8001)."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def health_check(self) -> bool:
        """Check if TRIBE v2 is healthy. Returns True if status is 'ok'."""
        try:
            resp = await self._client.get("/api/health", timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            return data.get("status") == "ok"
        except Exception as e:
            logger.warning("TRIBE health check failed: %s", e)
            return False

    async def score_text(self, text: str) -> dict[str, float] | None:
        """
        Score a single text via TRIBE v2.

        Returns a dict with 7 dimension scores (0-100 float), or None on failure.
        Per D-03: called sequentially, one variant at a time.
        """
        try:
            resp = await self._client.post(
                "/api/score",
                json={"text": text},
                timeout=120.0,  # GPU inference can take 10-30 seconds
            )
            resp.raise_for_status()
            data = resp.json()
            # Extract only the 7 brain-region scores, exclude metadata like inference_time_ms
            scores: dict[str, float] = {}
            for dim in TRIBE_SCORE_DIMENSIONS:
                if dim in data:
                    scores[dim] = float(data[dim])
            if len(scores) != 7:
                logger.warning(
                    "TRIBE returned %d dimensions instead of 7: %s",
                    len(scores),
                    list(data.keys()),
                )
                return None
            return scores
        except httpx.TimeoutException:
            logger.warning("TRIBE scoring timed out (120s limit)")
            return None
        except Exception as e:
            logger.warning("TRIBE scoring failed: %s", e)
            return None
