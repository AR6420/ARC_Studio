"""FastAPI scoring service for TRIBE v2 brain-encoding predictions.

Endpoints
---------
POST /api/score        — Score a single text, return 7 dimension scores (0-100)
POST /api/score/batch  — Score multiple texts in one call
GET  /api/health       — Report model and GPU status

The model is loaded once during the FastAPI lifespan.  GPU inference is
synchronous; each endpoint offloads the blocking work to a thread-pool
executor so the async event loop is not blocked.
"""

import os

# CRITICAL: Force CPU before ANY torch/neuralset imports.
# Must be the very first thing that runs. See model_loader.py for rationale.
if os.environ.get("TRIBE_DEVICE", "").lower() == "cpu":
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import torch
    torch.cuda.is_available = lambda: False

import asyncio
import logging
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import torch
import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

# Make the package root importable regardless of working directory
_pkg_root = Path(__file__).resolve().parent
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from config import settings
from scoring.model_loader import get_model, is_model_loaded, load_model
from scoring.normalizer import build_baseline_from_model, get_normalizer
from scoring.roi_extractor import extract_roi_activations
from scoring.text_scorer import score_text

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s %(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


# ---------------------------------------------------------------------------
# Lifespan — model loading on startup
# ---------------------------------------------------------------------------

_startup_error: str | None = None


def _clean_stale_inflight_records() -> None:
    """Clean stale inflight records from exca cache on startup.

    The exca caching library tracks "in-flight" operations in SQLite databases.
    If the TRIBE service crashes or is killed during inference, these records
    are left behind.  On Windows, exca's liveness check (os.kill(pid, 0))
    raises OSError instead of ProcessLookupError for dead PIDs, which prevents
    the library from auto-cleaning stale records.

    This function deletes ALL inflight records at startup, since any records
    from a previous process are by definition stale (this is a fresh start).
    """
    import glob
    import sqlite3

    pattern = os.path.join(settings.cache_folder, "**", "inflight.db")
    db_files = glob.glob(pattern, recursive=True)

    total_cleaned = 0
    for db_path in db_files:
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM inflight")
            count = cursor.fetchone()[0]
            if count > 0:
                cursor.execute("DELETE FROM inflight")
                conn.commit()
                total_cleaned += count
                logger.info("Cleaned %d stale inflight records from %s", count, db_path)
            conn.close()
        except Exception as exc:
            logger.warning("Could not clean inflight DB %s: %s", db_path, exc)

    if total_cleaned > 0:
        logger.info("Total stale inflight records cleaned: %d", total_cleaned)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _startup_error
    loop = asyncio.get_event_loop()

    # Clean stale inflight records from previous crashed sessions.
    # Must run BEFORE model loading since model loading also uses the cache.
    _clean_stale_inflight_records()

    try:
        logger.info("Loading TRIBE v2 model (this may take 30-60 s)...")
        await loop.run_in_executor(
            None,
            lambda: load_model(
                model_path=settings.resolved_model_path,
                device=settings.tribe_device,
                cache_folder=settings.cache_folder,
            ),
        )
        logger.info("TRIBE v2 model loaded. Seeding baseline...")
        await loop.run_in_executor(
            None,
            lambda: build_baseline_from_model(get_model(), score_text),
        )
        logger.info("Baseline ready. Service is up.")
    except Exception as exc:
        _startup_error = str(exc)
        logger.error("Model failed to load: %s", exc)
        # We do NOT re-raise — the service starts in degraded mode and
        # /api/health will report the failure.
    yield
    # Shutdown — nothing special needed; Python GC handles GPU tensors.
    logger.info("Shutting down TRIBE scorer service.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="TRIBE v2 Brain Scoring Service",
    description=(
        "Predicts fMRI-based brain-region activation scores (0-100) "
        "for text content using the TRIBE v2 multimodal brain-encoding model."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ScoreRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        description="The content to score (recommended 100–5000 words).",
    )


class ScoreResponse(BaseModel):
    attention_capture: float = Field(
        ..., ge=0.0, le=100.0,
        description="Visual cortex + FEF + IPS activity (0-100).",
    )
    emotional_resonance: float = Field(
        ..., ge=0.0, le=100.0,
        description="Amygdala + anterior insula + ACC activity (0-100).",
    )
    memory_encoding: float = Field(
        ..., ge=0.0, le=100.0,
        description="Hippocampus + parahippocampal + entorhinal activity (0-100).",
    )
    reward_response: float = Field(
        ..., ge=0.0, le=100.0,
        description="Nucleus accumbens / VTA proxy + OFC activity (0-100).",
    )
    threat_detection: float = Field(
        ..., ge=0.0, le=100.0,
        description="Basolateral amygdala proxy + ACC / insula activity (0-100).",
    )
    cognitive_load: float = Field(
        ..., ge=0.0, le=100.0,
        description="DLPFC + anterior PFC activity (0-100).",
    )
    social_relevance: float = Field(
        ..., ge=0.0, le=100.0,
        description="TPJ + mPFC + pSTS activity (0-100).",
    )
    inference_time_ms: float = Field(
        ..., ge=0.0,
        description="Total inference time in milliseconds.",
    )


class BatchScoreRequest(BaseModel):
    texts: list[str] = Field(
        ...,
        min_length=1,
        description="List of texts to score.",
    )


class BatchScoreResponse(BaseModel):
    scores: list[ScoreResponse]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    gpu_available: bool
    gpu_name: str | None
    gpu_memory_used_gb: float | None
    gpu_memory_total_gb: float | None
    baseline_size: int
    startup_failed: bool


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Serialize model access: the TRIBE model (LLaMA 3.2-3B) and its exca cache
# are NOT thread-safe. If FastAPI dispatches overlapping requests to the
# thread pool, concurrent model.predict() or cache access can crash.
# This lock ensures only one inference runs at a time.
_inference_lock = threading.Lock()


def _require_model() -> Any:
    """Return the loaded model or raise 503 if unavailable."""
    model = get_model()
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TRIBE v2 model is not loaded. Check /api/health for details.",
        )
    return model


def _score_response_from_activations(
    vertex_activations, normalizer, elapsed_ms: float
) -> ScoreResponse:
    """Convert vertex activations to a ScoreResponse."""
    raw_activations = extract_roi_activations(vertex_activations)
    scores = normalizer.normalize(raw_activations)
    return ScoreResponse(
        attention_capture=scores["attention_capture"],
        emotional_resonance=scores["emotional_resonance"],
        memory_encoding=scores["memory_encoding"],
        reward_response=scores["reward_response"],
        threat_detection=scores["threat_detection"],
        cognitive_load=scores["cognitive_load"],
        social_relevance=scores["social_relevance"],
        inference_time_ms=round(elapsed_ms, 2),
    )


def _run_single_score(text: str) -> ScoreResponse:
    """Blocking inference for one text. Runs inside a thread executor."""
    model = _require_model()
    t_start = time.perf_counter()

    with _inference_lock:
        try:
            vertex_activations = score_text(text, model)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Inference failed: {exc}",
            )
        except Exception as exc:
            logger.error("Unexpected inference error: %s: %s", type(exc).__name__, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal inference error — check server logs",
            )

    elapsed_ms = (time.perf_counter() - t_start) * 1000.0
    return _score_response_from_activations(
        vertex_activations, get_normalizer(), elapsed_ms
    )


def _run_batch_score(texts: list[str]) -> list[ScoreResponse]:
    """Blocking inference for a batch of texts. Runs inside a thread executor."""
    model = _require_model()
    normalizer = get_normalizer()
    results: list[ScoreResponse] = []

    for text in texts:
        t_start = time.perf_counter()
        with _inference_lock:
            try:
                vertex_activations = score_text(text, model)
            except (ValueError, RuntimeError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Inference failed for one of the texts: {exc}",
                )
            except Exception as exc:
                logger.error(
                    "Unexpected batch inference error: %s: %s",
                    type(exc).__name__, exc,
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal inference error — check server logs",
                )
        raw_activations = extract_roi_activations(vertex_activations)
        elapsed_ms = (time.perf_counter() - t_start) * 1000.0

        # Collect raw_activations list for batch normalization later
        results.append((raw_activations, elapsed_ms))

    # Normalize the whole batch together for consistent relative scaling
    raw_list = [r[0] for r in results]
    elapsed_list = [r[1] for r in results]
    score_dicts = normalizer.normalize_batch(raw_list)

    return [
        ScoreResponse(
            attention_capture=sd["attention_capture"],
            emotional_resonance=sd["emotional_resonance"],
            memory_encoding=sd["memory_encoding"],
            reward_response=sd["reward_response"],
            threat_detection=sd["threat_detection"],
            cognitive_load=sd["cognitive_load"],
            social_relevance=sd["social_relevance"],
            inference_time_ms=round(elapsed_list[i], 2),
        )
        for i, sd in enumerate(score_dicts)
    ]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/api/score",
    response_model=ScoreResponse,
    summary="Score a single text",
    description=(
        "Run TRIBE v2 inference on the provided text and return predicted "
        "brain-region activation scores (0-100) for 7 psychological dimensions."
    ),
)
async def score_single(request: ScoreRequest) -> ScoreResponse:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: _run_single_score(request.text))
    return result


@app.post(
    "/api/score/batch",
    response_model=BatchScoreResponse,
    summary="Score multiple texts in one call",
    description=(
        "Run TRIBE v2 inference on each text in the batch sequentially. "
        "Normalization is applied across the batch for consistent relative scaling."
    ),
)
async def score_batch(request: BatchScoreRequest) -> BatchScoreResponse:
    if not request.texts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="texts list must not be empty.",
        )
    loop = asyncio.get_event_loop()
    scores = await loop.run_in_executor(None, lambda: _run_batch_score(request.texts))
    return BatchScoreResponse(scores=scores)


@app.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Service health check",
    description="Returns model load status, GPU availability, and baseline size.",
)
async def health() -> HealthResponse:
    model_loaded = is_model_loaded()
    gpu_available = torch.cuda.is_available()

    gpu_name: str | None = None
    gpu_mem_used: float | None = None
    gpu_mem_total: float | None = None

    if gpu_available:
        try:
            gpu_name = torch.cuda.get_device_name(0)
            mem_info = torch.cuda.mem_get_info(0)
            # mem_get_info returns (free, total) in bytes
            free_bytes, total_bytes = mem_info
            gpu_mem_used = round((total_bytes - free_bytes) / (1024 ** 3), 2)
            gpu_mem_total = round(total_bytes / (1024 ** 3), 2)
        except Exception:
            pass

    overall_status = "ok" if (model_loaded and _startup_error is None) else "degraded"

    return HealthResponse(
        status=overall_status,
        model_loaded=model_loaded,
        gpu_available=gpu_available,
        gpu_name=gpu_name,
        gpu_memory_used_gb=gpu_mem_used,
        gpu_memory_total_gb=gpu_mem_total,
        baseline_size=get_normalizer().baseline_size(),
        startup_failed=_startup_error is not None,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )
