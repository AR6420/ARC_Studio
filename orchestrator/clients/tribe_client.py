"""
Async HTTP client for the TRIBE v2 neural scoring service.

Communicates with the TRIBE v2 FastAPI service (default: http://localhost:8001)
via an httpx.AsyncClient passed to the constructor. This allows the caller to
manage connection pooling and base_url centrally (e.g., in the FastAPI lifespan).

Design decisions:
- Constructor receives an httpx.AsyncClient (not a URL string) -- shared pool.
- 300-second per-request timeout for scoring (CPU inference takes 30-90s per text).
- Returns None on any failure for graceful degradation (D-05).
- Filters response to only the 7 known brain-region dimensions.
- Retry logic with exponential backoff for transient failures.
- Batch endpoint preferred when scoring multiple texts.
"""

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Per-request timeout for scoring: long content (500+ words) takes 40-60 min
# per text through the full TTS+WhisperX+LLaMA pipeline on GPU.
SCORE_TIMEOUT = 7200.0

# Per-text budget for batch scoring — 3 long variants can take 2+ hours total.
BATCH_PER_TEXT_TIMEOUT = 7200.0

# Retry configuration for transient failures
MAX_RETRIES = 2
RETRY_BACKOFF_BASE = 5.0  # seconds

TRIBE_SCORE_DIMENSIONS = [
    "attention_capture",
    "emotional_resonance",
    "memory_encoding",
    "reward_response",
    "threat_detection",
    "cognitive_load",
    "social_relevance",
]


def _extract_scores(data: dict[str, Any]) -> dict[str, float] | None:
    """Extract the 7 brain-region dimension scores from a TRIBE response.

    Returns None if any dimension is missing.
    """
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


class TribeClient:
    """Async HTTP client for the TRIBE v2 neural scoring service (port 8001)."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        max_retries: int = MAX_RETRIES,
        retry_backoff_base: float = RETRY_BACKOFF_BASE,
    ) -> None:
        self._client = client
        self._max_retries = max_retries
        self._retry_backoff_base = retry_backoff_base

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

    async def _retry_loop(
        self,
        label: str,
        request_fn,
        timeout: float,
    ) -> httpx.Response | None:
        """Generic retry loop for TRIBE HTTP requests.

        Returns the httpx.Response on success (2xx), or None after all retries
        are exhausted. Retries on 5xx, timeouts, and connection errors.
        """
        max_retries = self._max_retries
        total_attempts = max_retries + 1
        last_error: str = ""

        for attempt in range(1, total_attempts + 1):
            t_start = time.perf_counter()
            try:
                resp = await request_fn(timeout)
                elapsed = time.perf_counter() - t_start

                if resp.status_code >= 500:
                    body = resp.text[:500]
                    last_error = f"HTTP {resp.status_code} after {elapsed:.1f}s: {body}"
                    logger.warning(
                        "TRIBE %s returned %d (attempt %d/%d, %.1fs): %s",
                        label, resp.status_code, attempt, total_attempts, elapsed, body,
                    )
                    if attempt < total_attempts:
                        backoff = self._retry_backoff_base * (2 ** (attempt - 1))
                        logger.info("Retrying TRIBE %s in %.1fs...", label, backoff)
                        await asyncio.sleep(backoff)
                        continue
                    return None

                if resp.status_code >= 400:
                    body = resp.text[:500]
                    logger.warning(
                        "TRIBE %s client error HTTP %d after %.1fs: %s",
                        label, resp.status_code, elapsed, body,
                    )
                    return None

                return resp

            except httpx.TimeoutException as e:
                elapsed = time.perf_counter() - t_start
                last_error = f"Timeout ({type(e).__name__}) after {elapsed:.1f}s"
                logger.warning(
                    "TRIBE %s timed out (attempt %d/%d, %.1fs, limit=%.0fs): %s",
                    label, attempt, total_attempts, elapsed, timeout, type(e).__name__,
                )
            except httpx.ConnectError as e:
                elapsed = time.perf_counter() - t_start
                last_error = f"Connection error after {elapsed:.1f}s: {e}"
                logger.warning(
                    "TRIBE %s connection error (attempt %d/%d, %.1fs): %s",
                    label, attempt, total_attempts, elapsed, e,
                )
            except Exception as e:
                elapsed = time.perf_counter() - t_start
                last_error = f"{type(e).__name__}: {e} after {elapsed:.1f}s"
                logger.warning(
                    "TRIBE %s failed (attempt %d/%d, %.1fs): %s: %s",
                    label, attempt, total_attempts, elapsed, type(e).__name__, e,
                )
                # Non-retryable (unknown exception)
                return None

            # Retryable error -- back off
            if attempt < total_attempts:
                backoff = self._retry_backoff_base * (2 ** (attempt - 1))
                logger.info("Retrying TRIBE %s in %.1fs...", label, backoff)
                await asyncio.sleep(backoff)

        logger.error(
            "TRIBE %s failed after %d attempts. Last error: %s",
            label, total_attempts, last_error,
        )
        return None

    async def score_text(self, text: str) -> dict[str, float] | None:
        """
        Score a single text via TRIBE v2 with retry logic.

        Returns a dict with 7 dimension scores (0-100 float), or None on failure.
        Retries on transient failures (timeouts, connection errors, 5xx).
        """

        async def _request(timeout: float) -> httpx.Response:
            return await self._client.post(
                "/api/score",
                json={"text": text},
                timeout=timeout,
            )

        resp = await self._retry_loop("scoring", _request, SCORE_TIMEOUT)
        if resp is None:
            return None

        data = resp.json()
        scores = _extract_scores(data)
        if scores is not None:
            inference_ms = data.get("inference_time_ms", 0)
            logger.info(
                "TRIBE scored text in %.0fms inference time",
                inference_ms,
            )
        return scores

    async def score_texts_batch(self, texts: list[str]) -> list[dict[str, float] | None]:
        """
        Score multiple texts via TRIBE v2 batch endpoint with retry logic.

        Uses the /api/score/batch endpoint which processes texts sequentially
        on the server side and applies batch normalization for consistent
        relative scaling across the batch.

        Returns a list of score dicts (7 dimensions, 0-100) or None per text.
        Position matches input list. If the entire batch fails, returns [None] * len(texts).
        """
        if not texts:
            return []

        # Batch timeout: each text takes 30-90s on CPU.
        # Budget 120s per text to handle cold cache + overhead.
        batch_timeout = max(SCORE_TIMEOUT, len(texts) * BATCH_PER_TEXT_TIMEOUT)

        async def _request(timeout: float) -> httpx.Response:
            return await self._client.post(
                "/api/score/batch",
                json={"texts": texts},
                timeout=timeout,
            )

        resp = await self._retry_loop("batch scoring", _request, batch_timeout)
        if resp is None:
            return [None] * len(texts)

        data = resp.json()
        score_list = data.get("scores", [])
        if len(score_list) != len(texts):
            logger.warning(
                "TRIBE batch returned %d scores for %d texts",
                len(score_list), len(texts),
            )
            return [None] * len(texts)

        results: list[dict[str, float] | None] = []
        for score_data in score_list:
            scores = _extract_scores(score_data)
            results.append(scores)

        scored = sum(1 for r in results if r is not None)
        total_inference = sum(
            s.get("inference_time_ms", 0) for s in score_list
        )
        logger.info(
            "TRIBE batch scored %d/%d texts (total inference: %.0fms)",
            scored, len(texts), total_inference,
        )
        return results
