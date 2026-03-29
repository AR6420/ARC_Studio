"""Convert raw text into a per-vertex cortical activation array.

The TRIBE v2 model requires a path to a ``.txt`` file; this module handles
writing the text to a temporary file, running the TTS → transcription →
inference pipeline, and averaging the per-TR predictions into a single
``(n_vertices,)`` array.
"""

import logging
import tempfile
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Expected number of cortical surface vertices for fsaverage5 (both hemispheres).
FSAVERAGE5_N_VERTICES = 20484


def score_text(text: str, model) -> np.ndarray:
    """Run TRIBE v2 inference on *text* and return mean vertex activations.

    Parameters
    ----------
    text:
        The content to score.  Must be non-empty.
    model:
        A loaded ``TribeModel`` instance (from :mod:`scoring.model_loader`).

    Returns
    -------
    np.ndarray
        1-D float32 array of shape ``(n_vertices,)`` — typically 20 484
        entries for fsaverage5.  Values are the mean predicted activation
        across all kept time-segments.

    Raises
    ------
    ValueError
        If *text* is empty or the model produces an unexpected output shape.
    RuntimeError
        On inference failure.
    """
    text = text.strip()
    if not text:
        raise ValueError("text must be non-empty")

    # Write to a named temp file; get_events_dataframe() checks the suffix.
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".txt",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(text)
        tmp_path = tmp.name

    try:
        logger.debug("Running get_events_dataframe on temp file '%s'", tmp_path)
        events = model.get_events_dataframe(text_path=tmp_path)

        logger.debug("Running predict()…")
        preds, segments = model.predict(events, verbose=False)
        # preds: (n_segments, n_vertices)
    except Exception as exc:
        raise RuntimeError(f"TRIBE v2 inference failed: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if preds.ndim != 2 or preds.shape[0] == 0:
        raise ValueError(
            f"Unexpected predictions shape from TRIBE v2: {preds.shape}. "
            "Expected (n_segments, n_vertices) with at least one segment."
        )

    avg_pred = preds.mean(axis=0).astype(np.float32)  # (n_vertices,)
    logger.debug(
        "Scored %d segments → avg_pred shape %s, range [%.4f, %.4f]",
        preds.shape[0],
        avg_pred.shape,
        float(avg_pred.min()),
        float(avg_pred.max()),
    )
    return avg_pred
