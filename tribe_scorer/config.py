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
