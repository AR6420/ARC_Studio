"""
Tests for orchestrator.clients.openai_compat_client.OpenAICompatClient.

Mirrors the test surface of test_claude_client.py (where it exists) plus
provider-specific concerns:
- correct mapping of opus/haiku -> orchestrator/agent model
- response_format=json_object passed for *_json variants
- retry/backoff on 429 and 5xx
- JSON extractor handles raw, fenced, and prose-wrapped output
- works identically with Qwen3.5-* and Qwen3-* model names (no model
  branching anywhere)
"""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from openai import APIStatusError

from orchestrator.clients.openai_compat_client import (
    OpenAICompatClient,
    _clean_response_text,
    _extract_json_from_text,
    _strip_naked_preamble,
    _strip_think_blocks,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_completion(text: str):
    """Build a minimal AsyncOpenAI ChatCompletion-like object."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    return completion


def _make_status_error(status: int, message: str = "boom") -> APIStatusError:
    """Build an APIStatusError without invoking the real httpx response chain."""
    response = MagicMock()
    response.status_code = status
    response.headers = {}
    err = APIStatusError(message=message, response=response, body=None)
    err.status_code = status
    return err


@pytest.fixture
def stub_async_openai():
    """
    Patch openai.AsyncOpenAI so OpenAICompatClient never touches a real
    network. Returns the mock instance the client will use; tests configure
    `.chat.completions.create` per case.
    """
    with patch("orchestrator.clients.openai_compat_client.AsyncOpenAI") as cls:
        instance = MagicMock()
        instance.chat = MagicMock()
        instance.chat.completions = MagicMock()
        instance.chat.completions.create = AsyncMock()
        cls.return_value = instance
        yield instance


# ── 1. Construction + model routing ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_call_opus_uses_orchestrator_model(stub_async_openai):
    stub_async_openai.chat.completions.create.return_value = _make_completion("hi")
    client = OpenAICompatClient(
        base_url="http://fake/v1",
        orchestrator_model="Qwen/Qwen3.5-27B",
        agent_model="Qwen/Qwen3.5-9B",
    )
    out = await client.call_opus(system="s", user="u", max_tokens=64)
    assert out == "hi"
    kwargs = stub_async_openai.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "Qwen/Qwen3.5-27B"
    assert kwargs["max_tokens"] == 64
    assert kwargs["messages"][0] == {"role": "system", "content": "s"}
    assert kwargs["messages"][1] == {"role": "user", "content": "u"}
    assert "response_format" not in kwargs


@pytest.mark.asyncio
async def test_call_haiku_uses_agent_model(stub_async_openai):
    stub_async_openai.chat.completions.create.return_value = _make_completion("ok")
    client = OpenAICompatClient(
        base_url="http://fake/v1",
        orchestrator_model="Qwen/Qwen3.5-27B",
        agent_model="Qwen/Qwen3.5-9B",
    )
    await client.call_haiku(system="s", user="u")
    kwargs = stub_async_openai.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "Qwen/Qwen3.5-9B"


@pytest.mark.asyncio
async def test_works_with_qwen3_fallback_names(stub_async_openai):
    """No model-name-specific branching: Qwen3 names route identically."""
    stub_async_openai.chat.completions.create.return_value = _make_completion("ok")
    client = OpenAICompatClient(
        base_url="http://fake/v1",
        orchestrator_model="Qwen/Qwen3-32B",
        agent_model="Qwen/Qwen3-8B",
    )
    await client.call_opus(system="s", user="u")
    assert stub_async_openai.chat.completions.create.call_args.kwargs["model"] == "Qwen/Qwen3-32B"
    await client.call_haiku(system="s", user="u")
    assert stub_async_openai.chat.completions.create.call_args.kwargs["model"] == "Qwen/Qwen3-8B"


# ── 2. JSON variants ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_call_opus_json_requests_json_object_response_format(stub_async_openai):
    stub_async_openai.chat.completions.create.return_value = _make_completion(
        '{"answer": 42}'
    )
    client = OpenAICompatClient(
        base_url="http://fake/v1",
        orchestrator_model="orch",
        agent_model="agent",
    )
    out = await client.call_opus_json(system="s", user="u")
    assert out == {"answer": 42}
    kwargs = stub_async_openai.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_call_haiku_json_retries_on_first_parse_failure(stub_async_openai):
    """
    Server returns prose first, then valid JSON on the strict retry. Client
    should swallow the first failure, issue a strict reprompt, and return
    parsed JSON.
    """
    stub_async_openai.chat.completions.create.side_effect = [
        _make_completion("Sorry, I cannot do that."),
        _make_completion('{"variants": []}'),
    ]
    client = OpenAICompatClient(
        base_url="http://fake/v1",
        orchestrator_model="orch",
        agent_model="agent",
    )
    out = await client.call_haiku_json(system="s", user="u")
    assert out == {"variants": []}
    assert stub_async_openai.chat.completions.create.await_count == 2


@pytest.mark.asyncio
async def test_call_opus_json_raises_after_two_failures(stub_async_openai):
    stub_async_openai.chat.completions.create.return_value = _make_completion(
        "definitely not json"
    )
    client = OpenAICompatClient(
        base_url="http://fake/v1",
        orchestrator_model="orch",
        agent_model="agent",
    )
    with pytest.raises(ValueError, match="did not return valid JSON"):
        await client.call_opus_json(system="s", user="u")


# ── 3. Retry / backoff ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retries_on_503_then_succeeds(stub_async_openai, monkeypatch):
    monkeypatch.setattr(
        "orchestrator.clients.openai_compat_client.asyncio.sleep",
        AsyncMock(),
    )
    stub_async_openai.chat.completions.create.side_effect = [
        _make_status_error(503),
        _make_completion("recovered"),
    ]
    client = OpenAICompatClient(
        base_url="http://fake/v1",
        orchestrator_model="orch",
        agent_model="agent",
    )
    out = await client.call_haiku(system="s", user="u")
    assert out == "recovered"
    assert stub_async_openai.chat.completions.create.await_count == 2


@pytest.mark.asyncio
async def test_does_not_retry_on_400(stub_async_openai, monkeypatch):
    monkeypatch.setattr(
        "orchestrator.clients.openai_compat_client.asyncio.sleep",
        AsyncMock(),
    )
    stub_async_openai.chat.completions.create.side_effect = _make_status_error(400)
    client = OpenAICompatClient(
        base_url="http://fake/v1",
        orchestrator_model="orch",
        agent_model="agent",
    )
    with pytest.raises(APIStatusError):
        await client.call_opus(system="s", user="u")
    assert stub_async_openai.chat.completions.create.await_count == 1


# ── 4. JSON extractor unit tests ────────────────────────────────────────────

def test_extractor_handles_raw_json():
    assert _extract_json_from_text('{"x": 1}') == {"x": 1}


def test_extractor_handles_fenced_json():
    text = "Here you go:\n```json\n{\"x\": 1}\n```\n"
    assert _extract_json_from_text(text) == {"x": 1}


def test_extractor_handles_prose_wrapped_json():
    text = 'I think the answer is {"x": 1, "y": 2} as shown.'
    assert _extract_json_from_text(text) == {"x": 1, "y": 2}


def test_extractor_raises_on_no_json():
    with pytest.raises(ValueError, match="No valid JSON"):
        _extract_json_from_text("nothing here")


# ── 5. Factory wiring ───────────────────────────────────────────────────────

def test_factory_returns_claude_client_for_anthropic_provider(monkeypatch):
    """The factory must remain a no-op-equivalent for the production path."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from orchestrator.clients.llm_factory import build_llm_client
    from orchestrator.clients.claude_client import ClaudeClient
    client = build_llm_client(provider="anthropic")
    assert isinstance(client, ClaudeClient)


def test_factory_returns_openai_compat_for_vllm_provider(stub_async_openai):
    from orchestrator.clients.llm_factory import build_llm_client
    client = build_llm_client(provider="vllm")
    assert isinstance(client, OpenAICompatClient)


def test_factory_rejects_unknown_provider():
    from orchestrator.clients.llm_factory import build_llm_client
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        build_llm_client(provider="bogus")


# ── 6. Dual base URL routing (Phase 3 backport) ─────────────────────────────


def _make_routed_async_openai():
    """
    Patch AsyncOpenAI to return a fresh stub instance per call AND record
    the base_url used to construct each one. Returns (cls_mock,
    instances_by_base_url, calls_by_base_url) so tests can assert which
    endpoint a request hit.
    """
    instances: dict[str, MagicMock] = {}

    def _factory(*, base_url, api_key, timeout):  # match AsyncOpenAI signature
        inst = MagicMock()
        inst.chat = MagicMock()
        inst.chat.completions = MagicMock()
        inst.chat.completions.create = AsyncMock(return_value=_make_completion("ok"))
        inst._base_url = base_url
        instances[base_url] = inst
        return inst

    return _factory, instances


@pytest.mark.asyncio
async def test_dual_endpoints_route_by_model():
    """
    With agent_base_url set, call_opus must hit the orchestrator endpoint
    and call_haiku must hit the agent endpoint. Confirms the Phase 3
    finding that the two vLLM tiers live on different ports.
    """
    factory, instances = _make_routed_async_openai()
    with patch(
        "orchestrator.clients.openai_compat_client.AsyncOpenAI",
        side_effect=factory,
    ):
        client = OpenAICompatClient(
            base_url="http://orch.fake/v1",
            agent_base_url="http://agent.fake/v1",
            orchestrator_model="Qwen/Qwen3.5-27B",
            agent_model="Qwen/Qwen3.5-9B",
        )
        await client.call_opus(system="s", user="u")
        await client.call_haiku(system="s", user="u")

    assert set(instances.keys()) == {"http://orch.fake/v1", "http://agent.fake/v1"}
    orch = instances["http://orch.fake/v1"].chat.completions.create
    agent = instances["http://agent.fake/v1"].chat.completions.create
    assert orch.await_count == 1
    assert agent.await_count == 1
    assert orch.await_args.kwargs["model"] == "Qwen/Qwen3.5-27B"
    assert agent.await_args.kwargs["model"] == "Qwen/Qwen3.5-9B"


# ── 7. <think> block stripping (Phase 3 backport) ──────────────────────────


def test_strip_think_blocks_removes_single_block():
    out = _strip_think_blocks("<think>reasoning here</think>\n\nFinal answer: 42")
    assert out == "Final answer: 42"


def test_strip_think_blocks_removes_multiple_blocks():
    out = _strip_think_blocks(
        "<think>step 1</think>middle<think>step 2</think>end"
    )
    assert out == "middleend"


def test_strip_think_blocks_handles_multiline_content():
    out = _strip_think_blocks(
        "<think>line one\nline two\n  indented line three</think>\n\nResult"
    )
    assert out == "Result"


def test_strip_think_blocks_passthrough_when_no_block():
    assert _strip_think_blocks("just plain text") == "just plain text"


@pytest.mark.asyncio
async def test_call_opus_strips_think_block(stub_async_openai):
    """Phase 3 finding: Qwen3.5 emits <think>...</think> in non-JSON mode."""
    stub_async_openai.chat.completions.create.return_value = _make_completion(
        "<think>analysing prompt</think>PONG"
    )
    client = OpenAICompatClient(
        base_url="http://fake/v1",
        orchestrator_model="orch",
        agent_model="agent",
    )
    out = await client.call_opus(system="s", user="u")
    assert out == "PONG"


@pytest.mark.asyncio
async def test_call_haiku_strips_think_block(stub_async_openai):
    stub_async_openai.chat.completions.create.return_value = _make_completion(
        "<think>thinking</think>\n\nVariant body."
    )
    client = OpenAICompatClient(
        base_url="http://fake/v1",
        orchestrator_model="orch",
        agent_model="agent",
    )
    out = await client.call_haiku(system="s", user="u")
    assert out == "Variant body."


@pytest.mark.asyncio
async def test_no_agent_url_means_single_endpoint_for_both_tiers():
    """
    Backward-compat: when agent_base_url is empty (the dev / Ollama case),
    call_opus and call_haiku BOTH hit the orchestrator endpoint and only
    one AsyncOpenAI instance is constructed.
    """
    factory, instances = _make_routed_async_openai()
    with patch(
        "orchestrator.clients.openai_compat_client.AsyncOpenAI",
        side_effect=factory,
    ):
        client = OpenAICompatClient(
            base_url="http://only.fake/v1",
            orchestrator_model="orch",
            agent_model="agent",
        )
        await client.call_opus(system="s", user="u")
        await client.call_haiku(system="s", user="u")

    assert list(instances.keys()) == ["http://only.fake/v1"]
    create = instances["http://only.fake/v1"].chat.completions.create
    assert create.await_count == 2


# ── 8. Naked-preamble stripping (Phase 4 backport) ─────────────────────────


def test_naked_preamble_passthrough_when_no_marker():
    """Clean response with no preamble marker is returned unchanged."""
    text = "**Verdict**\n\nThis ad is strong because..."
    assert _strip_naked_preamble(text) == text


def test_naked_preamble_strips_thinking_process_with_heading_transition():
    """Phase 4 finding: 'Thinking Process: 1. ... \\n\\n**Verdict**' -> strip."""
    text = (
        "Thinking Process:\n"
        "1. **Analyze the Request:** The user wants...\n"
        "2. **Score the variants:** I'll rank...\n\n"
        "**Verdict**\n\nThe winner is variant 2."
    )
    out = _strip_naked_preamble(text)
    assert out == "**Verdict**\n\nThe winner is variant 2."


def test_naked_preamble_strips_let_me_think_variant():
    text = (
        "Let me think through this carefully. The seed is about X "
        "and the audience is Y, so...\n\n"
        "**Analysis**\n\nReal content here."
    )
    out = _strip_naked_preamble(text)
    assert out == "**Analysis**\n\nReal content here."


def test_naked_preamble_does_not_strip_response_that_is_legit_reasoning():
    """
    Edge case: marker is present but no `\\n\\n**Heading**` transition exists.
    The response IS the reasoning — under-strip rather than over-strip.
    """
    text = (
        "Reasoning: the variant scored higher because of stronger "
        "emotional resonance and better pacing in the closing line."
    )
    assert _strip_naked_preamble(text) == text


def test_naked_preamble_does_not_strip_when_marker_is_mid_response():
    """Marker only matches at the start of the response."""
    text = (
        "**Verdict**\n\nThe winner is variant 2. "
        "Reasoning: stronger emotional resonance."
    )
    assert _strip_naked_preamble(text) == text


def test_clean_response_combines_think_block_and_preamble():
    """Both signals together: <think> wrap removed, then naked preamble removed."""
    text = (
        "<think>private</think>\n"
        "Thinking Process:\n1. analyze\n2. respond\n\n"
        "**Verdict**\n\nFinal."
    )
    assert _clean_response_text(text) == "**Verdict**\n\nFinal."


@pytest.mark.asyncio
async def test_call_opus_strips_naked_preamble(stub_async_openai):
    stub_async_openai.chat.completions.create.return_value = _make_completion(
        "Thinking Process:\n1. step\n2. step\n\n**Verdict**\n\nA wins."
    )
    client = OpenAICompatClient(
        base_url="http://fake/v1",
        orchestrator_model="orch",
        agent_model="agent",
    )
    out = await client.call_opus(system="s", user="u")
    assert out == "**Verdict**\n\nA wins."
