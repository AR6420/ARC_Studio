"""Convert a video file into per-vertex cortical activation via TRIBE v2.

The TRIBE v2 video pipeline uses V-JEPA2 (``facebook/vjepa2-vitg-fpc64-256``)
for video frame encoding. The vendor's lazy-loading pattern
(``_free_extractor_model`` in ``vendor/tribev2/tribev2/main.py``) means
extractors load → run → release one at a time, so peak VRAM stays bounded
at ``max(V-JEPA2, LLaMA, Wav2Vec-BERT) + brain encoder`` — not the sum.

Vendor entry point
------------------
``TribeModel.get_events_dataframe(video_path=...)`` followed by
``TribeModel.predict(events, verbose=False)`` — same dispatcher as text/audio.

VRAM tracking
-------------
Captures ``torch.cuda.max_memory_allocated()`` peak across the inference
window (reset before, read after). Returned in metadata so the API caller
can verify hardware-class fit.
"""

from __future__ import annotations

import concurrent.futures
import logging
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import torch

logger = logging.getLogger(__name__)

# Must match text/audio scorer — TRIBE v2 predicts on fsaverage5 (both hemispheres).
FSAVERAGE5_N_VERTICES = 20484

# File-format allowlist — matches VALID_SUFFIXES["video_path"] in demo_utils.py
# (intersected with formats we accept on the upload endpoint).
SUPPORTED_SUFFIXES: tuple[str, ...] = (".mp4", ".webm", ".mov")

_DEFAULT_VIDEO_TIMEOUT = 1800  # 30 minutes


class VideoValidationError(ValueError):
    """Raised when a video input fails pre-inference validation.

    The server turns these into HTTP 400 responses.
    """


def _ffprobe_metadata(path: Path) -> dict[str, float]:
    """Return ``{'duration': float, 'width': int, 'height': int}`` for *path*.

    Raises VideoValidationError if ffprobe is unavailable, the file isn't
    parseable, or there's no video stream.
    """
    if shutil.which("ffprobe") is None:
        raise VideoValidationError(
            "ffprobe not found on PATH; cannot probe video metadata. "
            "Install ffmpeg/ffprobe or provide a duration/resolution shim."
        )
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,duration",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1",
                str(path),
            ],
            capture_output=True, text=True, timeout=15, check=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoValidationError(f"ffprobe timed out for {path}: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise VideoValidationError(
            f"ffprobe failed for {path}: {exc.stderr.strip()[:200]}"
        ) from exc

    md: dict[str, float] = {}
    for line in out.stdout.splitlines():
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if not val or val == "N/A":
            continue
        if key in ("width", "height"):
            try:
                md[key] = int(val)
            except ValueError:
                pass
        elif key == "duration":
            try:
                # ffprobe may emit duration twice (stream + format); prefer non-zero
                d = float(val)
                if d > 0:
                    md["duration"] = d
            except ValueError:
                pass

    if "width" not in md or "height" not in md:
        raise VideoValidationError(
            f"No video stream found in {path} (ffprobe returned no width/height)"
        )
    if "duration" not in md or md["duration"] <= 0:
        raise VideoValidationError(
            f"Could not determine duration for {path} (ffprobe returned no value)"
        )
    return md


def validate_video_file(
    video_path: str,
    *,
    max_duration_seconds: float,
    max_resolution_height: int,
) -> dict[str, float]:
    """Validate that *video_path* exists, is supported, and within limits.

    Returns ``{'duration_seconds': float, 'width': int, 'height': int}``.

    Raises
    ------
    VideoValidationError
        On any validation failure.
    """
    path = Path(video_path)
    if not path.is_absolute():
        raise VideoValidationError(
            f"video_path must be absolute, got: {video_path!r}"
        )
    if not path.is_file():
        raise VideoValidationError(f"video file not found: {video_path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise VideoValidationError(
            f"unsupported video format {suffix!r}; "
            f"expected one of {list(SUPPORTED_SUFFIXES)}"
        )

    md = _ffprobe_metadata(path)
    duration = md["duration"]
    if duration > max_duration_seconds:
        raise VideoValidationError(
            f"video too long: {duration:.2f}s exceeds limit of "
            f"{max_duration_seconds:.2f}s"
        )

    height = int(md["height"])
    if height > max_resolution_height:
        raise VideoValidationError(
            f"video resolution too large: {int(md['width'])}x{height} "
            f"exceeds {max_resolution_height}p height limit "
            "(downscale on the orchestrator before forwarding)"
        )

    return {
        "duration_seconds": duration,
        "width": int(md["width"]),
        "height": height,
    }


def _run_pipeline(video_path: str, model):
    events = model.get_events_dataframe(video_path=video_path)
    preds, segments = model.predict(events, verbose=False)
    return preds, segments


def score_video(
    video_path: str,
    model,
    *,
    timeout: int = _DEFAULT_VIDEO_TIMEOUT,
) -> tuple[np.ndarray, bool, float]:
    """Run TRIBE v2 video inference and return mean vertex activations.

    Parameters
    ----------
    video_path:
        Absolute path to a validated video file (caller is responsible for
        running :func:`validate_video_file` first).
    model:
        A loaded ``TribeModel`` instance.
    timeout:
        Seconds to wait for inference before falling back to pseudo.

    Returns
    -------
    tuple[np.ndarray, bool, float]
        ``(vertex_activations, is_pseudo, peak_vram_mb)``. Vertex shape
        matches text/audio scorers so the existing ROI extractor + normalizer
        consume it unchanged. ``peak_vram_mb`` is 0.0 on CPU or when CUDA
        accounting is unavailable.
    """
    cuda_available = torch.cuda.is_available()
    if cuda_available:
        try:
            torch.cuda.reset_peak_memory_stats()
        except Exception:  # noqa: BLE001 — older torch builds may lack this
            pass

    t0 = time.perf_counter()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(_run_pipeline, video_path, model)
        try:
            preds, _segments = future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            elapsed = time.perf_counter() - t0
            logger.warning(
                "Video inference timed out after %.1fs (limit %ds) for %s — "
                "falling back to pseudo.",
                elapsed, timeout, video_path,
            )
            executor.shutdown(wait=False, cancel_futures=True)
            return _pseudo_score_from_video(video_path), True, _read_peak_vram_mb()
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            logger.warning(
                "Video inference failed after %.1fs (%s: %s) — falling back to pseudo.",
                elapsed, type(exc).__name__, exc,
            )
            executor.shutdown(wait=False, cancel_futures=True)
            return _pseudo_score_from_video(video_path), True, _read_peak_vram_mb()
        else:
            executor.shutdown(wait=False)
    finally:
        pass

    elapsed = time.perf_counter() - t0
    peak_vram_mb = _read_peak_vram_mb()

    if preds is None or preds.ndim != 2 or preds.shape[0] == 0:
        logger.warning(
            "Video inference returned degenerate predictions %s after %.1fs — "
            "falling back to pseudo.",
            None if preds is None else preds.shape, elapsed,
        )
        return _pseudo_score_from_video(video_path), True, peak_vram_mb

    avg_pred = preds.mean(axis=0).astype(np.float32)
    logger.info(
        "Video inference completed in %.2fs for %s (shape %s, peak VRAM %.1f MB).",
        elapsed, video_path, preds.shape, peak_vram_mb,
    )
    return avg_pred, False, peak_vram_mb


def _read_peak_vram_mb() -> float:
    """Return torch.cuda.max_memory_allocated() in MB, or 0.0 if CUDA unavailable."""
    if not torch.cuda.is_available():
        return 0.0
    try:
        return torch.cuda.max_memory_allocated() / (1024 * 1024)
    except Exception:  # noqa: BLE001
        return 0.0


def _pseudo_score_from_video(video_path: str) -> np.ndarray:
    """Deterministic pseudo vertex activations derived from video file metadata.

    Used when the real video pipeline raises (V-JEPA2 OOM, decode error, etc.).
    Mirrors the pattern in ``audio_scorer._pseudo_score_from_audio``: numbers
    vary meaningfully with the input so downstream ROI/normalizer/composite
    steps produce differentiated output, and the server flags the response
    with ``is_pseudo_score=True`` + ``pseudo_reason``.
    """
    import hashlib

    path = Path(video_path)
    try:
        size = path.stat().st_size if path.exists() else len(video_path)
    except OSError:
        size = len(video_path)
    seed_material = f"video:{path.name}:{size}".encode()
    seed = int(hashlib.sha256(seed_material).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)

    base = rng.normal(loc=0.0, scale=0.02, size=FSAVERAGE5_N_VERTICES).astype(np.float32)
    # Mild modulation by file size as a stand-in for content features.
    scale = min(size / (25 * 1024 * 1024), 2.0)  # cap at 2.0 for 25 MB+
    # Bias toward visual cortex (occipital ROIs are roughly the 2nd vertex quartile).
    base[5121:10242] += 0.008 * scale
    base[10242:15363] += 0.005 * (2.0 - scale)

    logger.info(
        "Pseudo-scored video %s (size=%d) → shape %s, range [%.4f, %.4f]",
        path.name, size, base.shape, float(base.min()), float(base.max()),
    )
    return base
