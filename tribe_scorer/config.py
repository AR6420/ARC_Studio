"""Pydantic settings for the TRIBE v2 scoring service."""

import sys
from pathlib import Path

from pydantic_settings import BaseSettings

# .env is at the repo root — one level above tribe_scorer/
_REPO_ROOT = Path(__file__).parent.parent
_ENV_FILE = _REPO_ROOT / ".env"

# ---------------------------------------------------------------------------
# Windows MAX_PATH workaround for exca cache
# ---------------------------------------------------------------------------
# The exca caching library (used by TRIBE v2 / neuralset) creates deeply
# nested cache directories with text-content-derived UIDs.  It also writes
# temporary files like ``save-tmp-XXXXXXXX-full-uid.yaml`` inside those dirs.
# On Windows the total path can exceed the 260-character MAX_PATH limit,
# causing FileNotFoundError.  Using a short base cache path (e.g. ``C:\tc``)
# keeps all paths well under the limit.
#
# On non-Windows platforms we keep the project-local ``./cache`` default.


def _default_cache_folder() -> str:
    if sys.platform == "win32":
        short = Path("C:/tc")
        short.mkdir(parents=True, exist_ok=True)
        return str(short)
    return "./cache"


class Settings(BaseSettings):
    tribe_model_path: str = "facebook/tribev2"
    tribe_device: str = "cuda"
    tribe_text_only: bool = True
    cache_folder: str = _default_cache_folder()
    host: str = "127.0.0.1"
    port: int = 8001

    # Text chunking for long variants (Phase 2 B.1)
    max_words_per_chunk: int = 500
    per_chunk_timeout: int = 900  # 15 minutes per chunk

    # Audio scoring (Phase 2 A.1) — reject clips longer than this before inference.
    max_audio_duration_seconds: float = 60.0
    # Max wall-clock budget for a single audio inference call (Wav2Vec-BERT path).
    audio_inference_timeout_seconds: int = 1800  # 30 minutes

    # Video scoring (Phase 2 A.2) — V-JEPA2 path. Tighter limits to bound VRAM
    # peak (vendor lazy-loads V-JEPA2 + brain encoder ≈ 5-6 GB) and inference
    # time (audio extract → transcribe → V-JEPA2 → brain encoding all run
    # sequentially per the _free_extractor_model pattern).
    max_video_duration_seconds: float = 15.0
    max_video_resolution_height: int = 720
    video_inference_timeout_seconds: int = 1800  # 30 minutes

    model_config = {"env_prefix": "", "env_file": str(_ENV_FILE), "extra": "ignore"}

    @property
    def resolved_model_path(self) -> str:
        """Resolve model path relative to repo root, not cwd."""
        p = Path(self.tribe_model_path)
        if p.is_absolute():
            return str(p)
        # Try relative to repo root first
        repo_relative = _REPO_ROOT / self.tribe_model_path
        if repo_relative.exists():
            return str(repo_relative.resolve())
        # Fall back to cwd-relative
        if p.exists():
            return str(p.resolve())
        # Return as-is (may be a HuggingFace repo ID)
        return self.tribe_model_path.replace("\\", "/")


settings = Settings()
