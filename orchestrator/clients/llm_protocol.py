"""
LLM client protocol shared by ClaudeClient and OpenAICompatClient.

Defines the contract every orchestrator-facing LLM client must satisfy.
The four methods mirror the original ClaudeClient public surface so
existing call sites (variant_generator, result_analyzer, report_generator)
need no refactoring beyond the construction site.

Methods:
    call_opus / call_haiku       -> raw text response
    call_opus_json / call_haiku_json -> parsed JSON dict

In both providers:
- "opus" maps to the orchestrator-tier model (deep reasoning)
- "haiku" maps to the agent-tier model (fast structured tasks)
The opus/haiku names are kept for consistency with Anthropic terminology
across call sites, even when the underlying model is a Qwen variant.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Async LLM client protocol used throughout the orchestrator."""

    async def call_opus(self, system: str, user: str, max_tokens: int = 4096) -> str: ...

    async def call_haiku(self, system: str, user: str, max_tokens: int = 4096) -> str: ...

    async def call_opus_json(
        self, system: str, user: str, max_tokens: int = 4096
    ) -> dict[str, Any]: ...

    async def call_haiku_json(
        self, system: str, user: str, max_tokens: int = 4096
    ) -> dict[str, Any]: ...
