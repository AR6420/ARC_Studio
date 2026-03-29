"""
HTTP clients for downstream services.

Provides async client wrappers for:
- TRIBE v2 neural scoring (TribeClient)
- MiroFish social simulation (MirofishClient)
- Claude LLM API (ClaudeClient)
"""

from orchestrator.clients.claude_client import ClaudeClient
from orchestrator.clients.mirofish_client import MirofishClient
from orchestrator.clients.tribe_client import TribeClient

__all__ = ["ClaudeClient", "MirofishClient", "TribeClient"]
