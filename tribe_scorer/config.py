"""Pydantic settings for the TRIBE v2 scoring service."""

from pathlib import Path

from pydantic_settings import BaseSettings

# .env is at the repo root — one level above tribe_scorer/
_REPO_ROOT = Path(__file__).parent.parent
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    tribe_model_path: str = "facebook/tribev2"
    tribe_device: str = "cuda"
    tribe_text_only: bool = True
    cache_folder: str = "./cache"
    host: str = "0.0.0.0"
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
