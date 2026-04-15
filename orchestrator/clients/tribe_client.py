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

# Per-request timeout for scoring.
# With chunking (B.1): 250 words/chunk × 15 min/chunk.  A 1000-word text
# becomes 4 chunks × 900s = 3600s.  We add headroom for TTS/cache overhead.
SCORE_TIMEOUT = 5400.0  # 90 min — enough for ~5 chunks with margin

# Per-text budget for batch scoring — 3 chunked variants.
BATCH_PER_TEXT_TIMEOUT = 5400.0

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
    scores["is_pseudo_score"] = bool(data.get("is_pseudo_score", False))
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
        """Check if TRIBE v2 is healthy. Returns True if status is 'ok'.

        Also detects stale CUDA contexts (e.g. after laptop sleep/wake) by
        inspecting the ``cuda_healthy`` field in the health response. When
        CUDA is stale the scorer cannot run inference and needs a restart.
        """
        try:
            resp = await self._client.get("/api/health", timeout=10.0)
            data = resp.json()

            # Detect CUDA stale state (may come as 503 or 200-with-degraded)
            cuda_healthy = data.get("cuda_healthy")
            if cuda_healthy is False:
                logger.warning(
                    "TRIBE CUDA context is stale (cuda_healthy=false). "
                    "The TRIBE scorer needs a restart — run: bash scripts/restart_tribe.sh"
                )
                return False

            resp.raise_for_status()
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
            if scores.get("is_pseudo_score"):
                logger.warning("TRIBE returned PSEUDO-SCORES (not real brain-encoding) for this text")
        return scores

    async def score_audio(self, audio_path: str) -> dict[str, float] | None:
        """Score an audio file via TRIBE v2's audio ingest endpoint.

        Phase 2 A.1 placeholder: Agent 3 (tribe_scorer track) is responsible for
        wiring up the actual multipart POST against TRIBE's audio endpoint and
        the text+audio fusion pipeline. Until that lands, this method keeps the
        orchestrator interface stable so the campaign runner can already
        dispatch on media_type without crashing.

        Expected final contract:
          - ``audio_path`` is an absolute path on the orchestrator host to an
            audio file that was validated by the upload endpoint.
          - Returns the same 7-dimension score dict shape as ``score_text`` on
            success, or None on any failure.

        Current behavior: returns None (graceful degradation, per D-05), logs
        a clear warning so operators understand why audio campaigns produce no
        neural scores yet.
        """
        logger.warning(
            "TribeClient.score_audio is a Phase 2 A.1 placeholder "
            "(audio_path=%s). Agent 3 wires the real implementation; returning "
            "None so the campaign runner falls back to the neural-unavailable "
            "code path.",
            audio_path,
        )
        return None

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
            if scores and scores.get("is_pseudo_score"):
                logger.warning("TRIBE returned PSEUDO-SCORES (not real brain-encoding) for this text")
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
