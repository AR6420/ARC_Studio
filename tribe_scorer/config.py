"""Pydantic settings for the TRIBE v2 scoring service."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    tribe_model_path: str = "facebook/tribev2"
    tribe_device: str = "cuda"
    tribe_text_only: bool = True
    cache_folder: str = "./cache"
    host: str = "0.0.0.0"
    port: int = 8001

    model_config = {"env_prefix": "TRIBE_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
