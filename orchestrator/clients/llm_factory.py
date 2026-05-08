"""
Factory for the orchestrator's LLM client.

Reads `settings.llm_provider` and returns either the production
ClaudeClient (Anthropic SDK) or the OpenAICompatClient (vLLM /
OpenAI-compatible endpoint).

Usage:
    from orchestrator.clients.llm_factory import build_llm_client
    llm = build_llm_client()

The returned object satisfies the LLMClient Protocol regardless of
provider.
"""

import logging

from orchestrator.clients.llm_protocol import LLMClient

logger = logging.getLogger(__name__)


def build_llm_client(provider: str | None = None) -> LLMClient:
    """
    Construct the LLM client selected by `LLM_PROVIDER` (or the
    `provider` override).

    provider: "anthropic" (default) or "vllm".

    Raises ValueError for unknown providers.
    """
    from orchestrator.config import settings

    chosen = (provider or settings.llm_provider or "anthropic").lower().strip()

    if chosen == "anthropic":
        # Lazy import keeps the openai SDK off the import path when
        # the production provider is selected, and vice versa.
        from orchestrator.clients.claude_client import ClaudeClient
        logger.info("LLM provider: anthropic (ClaudeClient)")
        return ClaudeClient()

    if chosen == "vllm":
        from orchestrator.clients.openai_compat_client import OpenAICompatClient
        logger.info("LLM provider: vllm (OpenAICompatClient -> %s)", settings.vllm_base_url)
        return OpenAICompatClient()

    raise ValueError(
        f"Unknown LLM_PROVIDER {chosen!r}. Expected 'anthropic' or 'vllm'."
    )
