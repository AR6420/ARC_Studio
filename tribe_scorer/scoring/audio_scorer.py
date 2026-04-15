"""Convert an audio file into per-vertex cortical activation via TRIBE v2.

The TRIBE v2 audio pipeline uses Wav2Vec-BERT (not LLaMA) to extract features,
then runs the same brain-encoding head as the text path. The vertex activation
output shape is identical to ``text_scorer.score_text`` so the downstream
``roi_extractor`` + ``normalizer`` modules consume it unchanged.

Vendor entry point
------------------
``TribeModel.get_events_dataframe(audio_path=...)`` followed by
``TribeModel.predict(events, verbose=False)``.

See ``tribe_scorer/vendor/tribev2/tribev2/demo_utils.py`` for the vendor
implementation (lines ~243-320).
"""

from __future__ import annotations

import concurrent.futures
import logging
import time
import wave
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Must match text_scorer — TRIBE v2 predicts on fsaverage5 (both hemispheres).
FSAVERAGE5_N_VERTICES = 20484

# File-format allowlist — matches VALID_SUFFIXES["audio_path"] in demo_utils.py.
SUPPORTED_SUFFIXES: tuple[str, ...] = (".wav", ".mp3", ".flac", ".ogg")

_DEFAULT_AUDIO_TIMEOUT = 1800  # 30 minutes


class AudioValidationError(ValueError):
    """Raised when an audio input fails pre-inference validation.

    The server turns these into HTTP 400 responses.
    """


def validate_audio_file(audio_path: str, max_duration_seconds: float) -> float:
    """Validate that *audio_path* exists, has a supported format, and is short enough.

    Returns the detected duration in seconds.

    Raises
    ------
    AudioValidationError
        On any validation failure (missing file, bad suffix, too long, unreadable).
    """
    path = Path(audio_path)
    if not path.is_absolute():
        raise AudioValidationError(
            f"audio_path must be absolute, got: {audio_path!r}"
        )
    if not path.is_file():
        raise AudioValidationError(f"audio file not found: {audio_path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise AudioValidationError(
            f"unsupported audio format {suffix!r}; "
            f"expected one of {list(SUPPORTED_SUFFIXES)}"
        )

    duration = _probe_duration_seconds(path)
    if duration > max_duration_seconds:
        raise AudioValidationError(
            f"audio too long: {duration:.2f}s exceeds limit of "
            f"{max_duration_seconds:.2f}s"
        )
    if duration <= 0:
        raise AudioValidationError(
            f"audio has non-positive duration ({duration:.2f}s): {audio_path}"
        )

    return duration


def _probe_duration_seconds(path: Path) -> float:
    """Return the duration of *path* in seconds.

    Uses stdlib ``wave`` for WAV files and falls back to optional dependencies
    for other formats. We intentionally avoid importing heavy ML deps here —
    the goal is a cheap pre-inference sanity check.
    """
    suffix = path.suffix.lower()
    if suffix == ".wav":
        try:
            with wave.open(str(path), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate <= 0:
                    raise AudioValidationError(
                        f"wav file reports invalid sample rate: {path}"
                    )
                return frames / float(rate)
        except wave.Error as exc:
            raise AudioValidationError(f"could not read wav file {path}: {exc}") from exc

    # Non-wav formats — try a few lightweight probes in order of preference.
    try:
        import soundfile as sf  # type: ignore[import]

        info = sf.info(str(path))
        return float(info.duration)
    except ImportError:
        pass
    except Exception as exc:  # pragma: no cover — soundfile-specific errors
        logger.warning("soundfile probe failed for %s: %s", path, exc)

    try:
        from mutagen import File as MutagenFile  # type: ignore[import]

        meta = MutagenFile(str(path))
        if meta is not None and getattr(meta, "info", None) is not None:
            length = float(meta.info.length)
            if length > 0:
                return length
    except ImportError:
        pass
    except Exception as exc:  # pragma: no cover
        logger.warning("mutagen probe failed for %s: %s", path, exc)

    # Last resort: ffprobe via subprocess. We don't hard-require ffmpeg, so a
    # failure here produces a validation error rather than silent success.
    try:
        import subprocess

        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return float(out.stdout.strip())
    except FileNotFoundError as exc:
        raise AudioValidationError(
            f"cannot probe duration for {suffix!r}; install soundfile, mutagen, "
            "or ffmpeg on PATH"
        ) from exc
    except Exception as exc:
        raise AudioValidationError(
            f"failed to determine duration for {path}: {exc}"
        ) from exc


def _run_pipeline(audio_path: str, model):
    events = model.get_events_dataframe(audio_path=audio_path)
    preds, segments = model.predict(events, verbose=False)
    return preds, segments


def score_audio(
    audio_path: str,
    model,
    *,
    timeout: int = _DEFAULT_AUDIO_TIMEOUT,
) -> tuple[np.ndarray, bool]:
    """Run TRIBE v2 audio inference and return mean vertex activations.

    Parameters
    ----------
    audio_path:
        Absolute path to a validated audio file (caller is responsible for
        running :func:`validate_audio_file` first).
    model:
        A loaded ``TribeModel`` instance.
    timeout:
        Seconds to wait for inference before falling back to pseudo.

    Returns
    -------
    tuple[np.ndarray, bool]
        ``(vertex_activations, is_pseudo)``. Shape matches text_scorer output
        so the existing ROI extractor + normalizer consume it unchanged.
    """
    t0 = time.perf_counter()

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(_run_pipeline, audio_path, model)
        try:
            preds, _segments = future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            elapsed = time.perf_counter() - t0
            logger.warning(
                "Audio inference timed out after %.1fs (limit %ds) for %s — "
                "falling back to pseudo.",
                elapsed, timeout, audio_path,
            )
            executor.shutdown(wait=False, cancel_futures=True)
            return _pseudo_score_from_audio(audio_path), True
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            logger.warning(
                "Audio inference failed after %.1fs (%s: %s) — falling back to pseudo.",
                elapsed, type(exc).__name__, exc,
            )
            executor.shutdown(wait=False, cancel_futures=True)
            return _pseudo_score_from_audio(audio_path), True
        else:
            executor.shutdown(wait=False)
    finally:
        # No temp file to clean up — caller owns audio_path.
        pass

    elapsed = time.perf_counter() - t0

    if preds is None or preds.ndim != 2 or preds.shape[0] == 0:
        logger.warning(
            "Audio inference returned degenerate predictions %s after %.1fs — "
            "falling back to pseudo.",
            None if preds is None else preds.shape, elapsed,
        )
        return _pseudo_score_from_audio(audio_path), True

    avg_pred = preds.mean(axis=0).astype(np.float32)
    logger.info(
        "Audio inference completed in %.2fs for %s (shape %s).",
        elapsed, audio_path, preds.shape,
    )
    return avg_pred, False


def _pseudo_score_from_audio(audio_path: str) -> np.ndarray:
    """Deterministic pseudo vertex activations derived from audio file metadata.

    Used when the real audio pipeline raises (dep missing, CUDA OOM, etc.).
    Mirrors the pattern in ``text_scorer._pseudo_score_from_text``: the numbers
    vary meaningfully with the input so downstream ROI/normalizer/composite
    steps produce differentiated output, and the server flags the response
    with ``is_pseudo_score=True`` + ``pseudo_reason``.
    """
    import hashlib

    path = Path(audio_path)
    try:
        size = path.stat().st_size if path.exists() else len(audio_path)
    except OSError:
        size = len(audio_path)
    seed_material = f"{path.name}:{size}".encode()
    seed = int(hashlib.sha256(seed_material).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)

    base = rng.normal(loc=0.0, scale=0.02, size=FSAVERAGE5_N_VERTICES).astype(np.float32)
    # Mild modulation by file size as a stand-in for content features.
    scale = min(size / (10 * 1024 * 1024), 2.0)  # cap at 2.0 for 10 MB+
    base[:10242] += 0.005 * scale  # left hemisphere bias
    base[10242:] += 0.005 * (2.0 - scale)  # right hemisphere bias

    logger.info(
        "Pseudo-scored audio %s (size=%d) → shape %s, range [%.4f, %.4f]",
        path.name, size, base.shape, float(base.min()), float(base.max()),
    )
    return base
