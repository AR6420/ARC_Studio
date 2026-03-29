"""Load and cache the TRIBE v2 model for inference.

The model is loaded once at application startup via FastAPI lifespan and kept
in memory for the lifetime of the process.  Loading takes 30-60 seconds and
requires ~8-10 GB of VRAM when running on CUDA.
"""

import logging
import sys
from pathlib import Path

import torch

logger = logging.getLogger(__name__)

# Global singleton — set by load_model(), read by get_model()
_model = None


def load_model(model_path: str, device: str, cache_folder: str) -> None:
    """Load TRIBE v2 from *model_path* and store it in the module-level singleton.

    Parameters
    ----------
    model_path:
        HuggingFace repo id (e.g. ``"facebook/tribev2"``) or local directory
        that contains ``config.yaml`` and ``best.ckpt``.
    device:
        Torch device string such as ``"cuda"`` or ``"cpu"``.  When ``"cuda"``
        is requested but CUDA is not available the loader falls back to CPU
        and logs a warning.
    cache_folder:
        Directory used to cache extracted features (forwarded to
        ``TribeModel.from_pretrained``).

    Raises
    ------
    RuntimeError
        If the model cannot be loaded for any reason.
    """
    global _model

    # Resolve device, falling back gracefully
    if device == "cuda" and not torch.cuda.is_available():
        logger.warning(
            "CUDA requested but not available — falling back to CPU. "
            "Inference will be slow."
        )
        device = "cpu"

    # Ensure the vendor package is importable
    vendor_path = Path(__file__).resolve().parent.parent / "vendor" / "tribev2"
    if vendor_path.exists() and str(vendor_path) not in sys.path:
        sys.path.insert(0, str(vendor_path))

    try:
        from tribev2 import TribeModel  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            f"Could not import tribev2 from {vendor_path}. "
            "Make sure the vendor directory is present and dependencies are installed."
        ) from exc

    Path(cache_folder).mkdir(parents=True, exist_ok=True)
    logger.info("Loading TRIBE v2 from '%s' onto device '%s'…", model_path, device)
    try:
        model = TribeModel.from_pretrained(
            model_path,
            cache_folder=cache_folder,
            device=device,
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to load TRIBE v2 model: {exc}") from exc

    _model = model
    logger.info("TRIBE v2 model loaded successfully.")


def get_model():
    """Return the loaded model singleton.

    Returns
    -------
    TribeModel or None
        ``None`` if :func:`load_model` has not been called or failed.
    """
    return _model


def is_model_loaded() -> bool:
    """Return True if the model singleton is available."""
    return _model is not None
