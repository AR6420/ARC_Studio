"""
Tests for the LLM_PROVIDER=vllm skip in MirofishClient (Phase 3 backport).

When the orchestrator is wired to vLLM (AMD hackathon stack), MiroFish
talks directly to vllm-agents instead of LiteLLM. The LiteLLM probes
in health_check and verify_llm_token would otherwise 401 (no Anthropic
key present) and abort all simulations — that was the only blocker
between a working mirofish container and populated mirofish_metrics
during the Phase 3 smoke run.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from orchestrator.clients.mirofish_client import MirofishClient


def _stub_httpx_response(status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = {"status": "ok"}
    return r


@pytest.fixture
def mirofish_client_with_healthy_flask():
    """MirofishClient whose Flask /health returns 200 OK."""
    http = MagicMock(spec=httpx.AsyncClient)
    http.get = AsyncMock(return_value=_stub_httpx_response(200))
    return MirofishClient(http, litellm_url="http://litellm:4000")


@pytest.mark.asyncio
async def test_health_check_skips_litellm_probe_when_vllm_provider(
    mirofish_client_with_healthy_flask, monkeypatch
):
    """LLM_PROVIDER=vllm → health_check returns True after Flask probe only."""
    monkeypatch.setenv("LLM_PROVIDER", "vllm")
    ok = await mirofish_client_with_healthy_flask.health_check()
    assert ok is True


@pytest.mark.asyncio
async def test_verify_llm_token_returns_true_when_vllm_provider(monkeypatch):
    """LLM_PROVIDER=vllm → verify_llm_token short-circuits to True (no HTTP)."""
    monkeypatch.setenv("LLM_PROVIDER", "vllm")
    http = MagicMock(spec=httpx.AsyncClient)  # never touched
    client = MirofishClient(http, litellm_url="http://litellm:4000")
    assert await client.verify_llm_token() is True


@pytest.mark.asyncio
async def test_health_check_still_returns_false_when_flask_down_under_vllm(
    monkeypatch,
):
    """Even with the LiteLLM skip, Flask must still be reachable."""
    monkeypatch.setenv("LLM_PROVIDER", "vllm")
    http = MagicMock(spec=httpx.AsyncClient)
    http.get = AsyncMock(return_value=_stub_httpx_response(503))
    client = MirofishClient(http, litellm_url="http://litellm:4000")
    assert await client.health_check() is False
