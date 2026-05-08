"""
HTTP clients for downstream services.

Provides async client wrappers for:
- TRIBE v2 neural scoring (TribeClient)
- MiroFish social simulation (MirofishClient)
- Claude LLM API (ClaudeClient)
"""

from orchestrator.clients.claude_client import ClaudeClient
from orchestrator.clients.llm_factory import build_llm_client
from orchestrator.clients.llm_protocol import LLMClient
from orchestrator.clients.mirofish_client import MirofishClient
from orchestrator.clients.openai_compat_client import OpenAICompatClient
from orchestrator.clients.tribe_client import TribeClient

__all__ = [
    "ClaudeClient",
    "LLMClient",
    "MirofishClient",
    "OpenAICompatClient",
    "TribeClient",
    "build_llm_client",
]
