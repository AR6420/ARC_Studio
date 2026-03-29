"""
Orchestrator configuration.

Loads all settings from environment variables and the .env file at the repo root.
Uses Pydantic BaseSettings for validation and type coercion.

Usage:
    from orchestrator.config import settings
    print(settings.orchestrator_port)
"""

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env is at the repo root — one level above orchestrator/
_REPO_ROOT = Path(__file__).parent.parent
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    """
    All runtime configuration for the orchestrator.

    Values are loaded from (in priority order):
    1. Actual environment variables
    2. .env file at the repo root
    3. Default values defined here
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        # Allow extra env vars without raising errors (other services share the same .env)
        extra="ignore",
        case_sensitive=False,
    )

    # ── Claude API ──────────────────────────────────────────────────────────────
    anthropic_api_key: str = Field(
        default="",
        description=(
            "Anthropic API key. If empty, the client will fall back to reading "
            "claudeAiOauth.accessToken from CLAUDE_CREDENTIALS_PATH."
        ),
    )
    claude_credentials_path: str = Field(
        default="C:/Users/adars/.claude/.credentials.json",
        description="Path to the Claude credentials JSON file (OAuth token fallback).",
    )
    claude_opus_model: str = Field(
        default="claude-opus-4-6",
        description="Model ID for Claude Opus (deep analysis tasks).",
    )
    claude_haiku_model: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Model ID for Claude Haiku (fast structured tasks).",
    )

    # ── Downstream services ─────────────────────────────────────────────────────
    tribe_scorer_url: str = Field(
        default="http://localhost:8001",
        description="Base URL for the TRIBE v2 neural scoring service.",
    )
    mirofish_url: str = Field(
        default="http://localhost:5000",
        description="Base URL for the MiroFish social simulation service.",
    )

    # ── Neo4j ───────────────────────────────────────────────────────────────────
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j Bolt connection URI.",
    )
    neo4j_user: str = Field(
        default="neo4j",
        description="Neo4j username.",
    )
    neo4j_password: str = Field(
        default="mirofish",
        description="Neo4j password.",
    )

    # ── Orchestrator server ─────────────────────────────────────────────────────
    orchestrator_port: int = Field(
        default=8000,
        description="Port the orchestrator FastAPI server listens on.",
    )
    database_path: str = Field(
        default="./data/nexus_sim.db",
        description="Path to the SQLite database file.",
    )

    # ── Simulation defaults ─────────────────────────────────────────────────────
    default_agent_count: int = Field(
        default=40,
        ge=20,
        le=200,
        description="Default number of MiroFish agents per simulation.",
    )
    default_max_iterations: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Default maximum number of optimization iterations per campaign.",
    )
    default_simulation_cycles: int = Field(
        default=30,
        ge=1,
        description="Default number of simulation time cycles in each MiroFish run.",
    )

    # ── LLM fallback ────────────────────────────────────────────────────────────
    llm_fallback_enabled: bool = Field(
        default=True,
        description=(
            "When True, fall back to a local Ollama model if Claude Haiku is "
            "rate-limited during simulation."
        ),
    )
    llm_fallback_model: str = Field(
        default="qwen2.5:7b",
        description="Ollama model name to use when the primary LLM is unavailable.",
    )
    llm_fallback_base_url: str = Field(
        default="http://localhost:11434/v1",
        description="OpenAI-compatible base URL for the fallback LLM (Ollama).",
    )

    # ── Validators ──────────────────────────────────────────────────────────────
    @field_validator("default_agent_count")
    @classmethod
    def agent_count_must_be_multiple_of_ten(cls, v: int) -> int:
        if v % 10 != 0:
            raise ValueError(
                f"default_agent_count must be a multiple of 10, got {v}"
            )
        return v

    # ── Computed helpers ────────────────────────────────────────────────────────
    @property
    def database_path_absolute(self) -> Path:
        """Resolve DATABASE_PATH relative to the repo root."""
        p = Path(self.database_path)
        if p.is_absolute():
            return p
        return (_REPO_ROOT / p).resolve()


# Module-level singleton — import this everywhere
settings = Settings()
