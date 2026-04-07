"""Load and cache the TRIBE v2 model for inference.

The model is loaded once at application startup via FastAPI lifespan and kept
in memory for the lifetime of the process.  Loading takes 30-60 seconds and
requires ~8-10 GB of VRAM when running on CUDA.
"""

import logging
import os
import pathlib
import sys
from pathlib import Path

import torch

# CRITICAL: Force CPU BEFORE any neuralset/whisperx imports.
# neuralset.extractors.base.__init__ reads torch.cuda.is_available() at class
# instantiation time to set self.device. If CUDA appears available, every
# extractor instance defaults to device="cuda" and later calls model.to("cuda")
# which fails with CPU-only PyTorch (RTX 5070 Ti sm_120 needs PyTorch 2.8+).
# This patch MUST run before neuralset is imported (which happens when
# tribev2.TribeModel is imported in load_model below).
if os.environ.get("TRIBE_DEVICE", "").lower() == "cpu":
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    torch.cuda.is_available = lambda: False

# Windows fix: TRIBE v2 checkpoint was saved on Linux with PosixPath objects.
# torch.load on Windows cannot deserialize PosixPath — patch it to WindowsPath.
if sys.platform == "win32":
    pathlib.PosixPath = pathlib.WindowsPath

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

    # Resolve local paths to absolute to prevent Windows backslash from being
    # misinterpreted as a HuggingFace repo ID separator.
    local_path = Path(model_path)
    if local_path.exists():
        model_path = str(local_path.resolve())
        logger.info("Resolved local model path: %s", model_path)
    else:
        # Ensure forward slashes for HuggingFace repo IDs on Windows
        model_path = model_path.replace("\\", "/")

    # The shipped config.yaml sets num_workers=20 for cluster training.  On
    # Windows (spawn-based multiprocessing) each worker re-imports torch and
    # the main module, easily exhausting the paging file.  For single-item
    # inference we don't need parallel data loading at all.
    config_override: dict = {}
    if sys.platform == "win32":
        config_override["data.num_workers"] = 0

    logger.info("Loading TRIBE v2 from '%s' onto device '%s'…", model_path, device)
    try:
        model = TribeModel.from_pretrained(
            model_path,
            cache_folder=cache_folder,
            device=device,
            config_update=config_override or None,
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
