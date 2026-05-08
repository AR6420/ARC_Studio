"""
OpenAI-compatible LLM client for the orchestrator.

Talks to any /v1/chat/completions endpoint: vLLM (primary target on the
AMD hackathon MI300X), OpenAI proper, Ollama, LiteLLM. Mirrors the
ClaudeClient public surface so call sites are provider-agnostic via
LLM_PROVIDER and the llm_factory module.

Design choices:
- No OAuth/credentials-file loading. vLLM in dev runs without auth; an
  `api_key` is still required by the OpenAI SDK so we pass a sentinel.
- No sticky orchestrator->agent fallback. vLLM either serves the model
  or it doesn't; degrade by failing loudly.
- JSON variants set `response_format={"type":"json_object"}` (vLLM
  supports this via guided decoding) and still run the
  permissive text-extraction fallback in case the server returns
  prose-wrapped JSON.
- No model-name-specific branching. The orchestrator/agent model names
  are env-driven so swapping Qwen3.5 -> Qwen3 is a config change only.
"""

import asyncio
import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI, APIConnectionError, APIStatusError

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
BACKOFF_BASE = 2.0
RATE_LIMIT_BACKOFF = 30.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# vLLM accepts any non-empty api_key when started without `--api-key`.
DUMMY_API_KEY = "vllm-no-auth"

# Reasoning models (Qwen3.5, MiniMax M2.5, ...) emit <think>...</think>
# blocks before the final answer in non-JSON mode. JSON-mode (the
# response_format=json_object path) suppresses them via vLLM's structured
# output constraint, so this only matters for call_opus / call_haiku
# (raw-text). Mirror what mirofish/backend/app/utils/llm_client.py:85
# already does for the same reason.
_THINK_BLOCK = re.compile(r"<think>[\s\S]*?</think>")


def _strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> reasoning prefaces from model output."""
    return _THINK_BLOCK.sub("", text).strip()


def _extract_json_from_text(text: str) -> dict[str, Any]:
    """
    Permissive JSON extractor: handles raw JSON, fenced JSON, or JSON
    embedded in surrounding prose. Used as a safety net even when
    response_format=json_object is requested.
    """
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        return json.loads(fence_match.group(1).strip())

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        return json.loads(brace_match.group(0))

    raise ValueError(f"No valid JSON found in model response: {text[:200]!r}")


class OpenAICompatClient:
    """
    Async wrapper around `openai.AsyncOpenAI` pointed at any
    OpenAI-compatible endpoint.

    Constructor args (all optional; defaults read from
    orchestrator.config.settings):
        base_url:           e.g. "http://localhost:8000/v1"
        orchestrator_model: model id served at orchestrator tier
        agent_model:        model id served at agent tier
        api_key:            ignored by vLLM; kept for OpenAI compatibility
        timeout_s:          per-request timeout
    """

    def __init__(
        self,
        base_url: str | None = None,
        orchestrator_model: str | None = None,
        agent_model: str | None = None,
        api_key: str | None = None,
        timeout_s: float = 300.0,
        agent_base_url: str | None = None,
    ) -> None:
        # Deferred import to keep the protocol module light.
        from orchestrator.config import settings

        self._base_url = base_url or settings.vllm_base_url
        self._orchestrator_model = orchestrator_model or settings.vllm_orchestrator_model
        self._agent_model = agent_model or settings.vllm_agent_model
        self._client = AsyncOpenAI(
            base_url=self._base_url,
            api_key=api_key or DUMMY_API_KEY,
            timeout=timeout_s,
        )
        # Optional separate endpoint for the agent tier. The AMD hackathon
        # stack runs orchestrator-tier and agent-tier as two distinct vLLM
        # instances on different ports, so call_haiku* must hit a different
        # base_url than call_opus*. When agent_base_url is empty / None the
        # agent client aliases the orchestrator client (single-endpoint
        # deployment, e.g. local Ollama dev).
        agent_url = (agent_base_url or settings.vllm_agent_base_url or "").strip()
        if agent_url:
            self._agent_client = AsyncOpenAI(
                base_url=agent_url,
                api_key=api_key or DUMMY_API_KEY,
                timeout=timeout_s,
            )
            self._agent_base_url = agent_url
            logger.info("Separate agent-tier endpoint: %s", agent_url)
        else:
            self._agent_client = self._client
            self._agent_base_url = self._base_url
        logger.info(
            "OpenAICompatClient initialised: base_url=%s, orchestrator=%s, agent=%s, agent_base_url=%s",
            self._base_url,
            self._orchestrator_model,
            self._agent_model,
            self._agent_base_url,
        )

    async def _chat(
        self,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
        json_mode: bool,
    ) -> str:
        """Core retrying chat call. Returns the assistant message text."""
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        # Pick the right client: agent-tier model goes to the agent endpoint,
        # everything else to the orchestrator endpoint. In single-endpoint
        # deployments self._agent_client is self._client so this is a no-op.
        client = self._agent_client if model == self._agent_model else self._client
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                return content or ""

            except APIStatusError as exc:
                last_exc = exc
                status = getattr(exc, "status_code", None)
                if status in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                    wait = (
                        RATE_LIMIT_BACKOFF * (1.5 ** attempt)
                        if status == 429
                        else BACKOFF_BASE * (2 ** attempt)
                    )
                    logger.warning(
                        "vLLM endpoint returned %s on attempt %d/%d; retrying in %.1fs (model=%s)",
                        status, attempt + 1, MAX_RETRIES, wait, model,
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.error(
                    "vLLM call failed with status %s after %d attempt(s): %s",
                    status, attempt + 1, exc,
                )
                raise

            except APIConnectionError as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "Connection error on attempt %d/%d; retrying in %.1fs: %s",
                        attempt + 1, MAX_RETRIES, wait, exc,
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.error("vLLM connection failed after %d attempts", attempt + 1)
                raise

        assert last_exc is not None
        raise last_exc

    # ── Public surface (mirrors ClaudeClient) ───────────────────────────────

    async def call_opus(self, system: str, user: str, max_tokens: int = 4096) -> str:
        logger.debug("Calling orchestrator-tier model %s (max_tokens=%d)", self._orchestrator_model, max_tokens)
        text = await self._chat(
            model=self._orchestrator_model,
            system=system, user=user, max_tokens=max_tokens, json_mode=False,
        )
        return _strip_think_blocks(text)

    async def call_haiku(self, system: str, user: str, max_tokens: int = 4096) -> str:
        logger.debug("Calling agent-tier model %s (max_tokens=%d)", self._agent_model, max_tokens)
        text = await self._chat(
            model=self._agent_model,
            system=system, user=user, max_tokens=max_tokens, json_mode=False,
        )
        return _strip_think_blocks(text)

    async def call_opus_json(
        self, system: str, user: str, max_tokens: int = 4096
    ) -> dict[str, Any]:
        return await self._call_json(self._orchestrator_model, system, user, max_tokens)

    async def call_haiku_json(
        self, system: str, user: str, max_tokens: int = 4096
    ) -> dict[str, Any]:
        return await self._call_json(self._agent_model, system, user, max_tokens)

    async def _call_json(
        self, model: str, system: str, user: str, max_tokens: int
    ) -> dict[str, Any]:
        """
        Two-attempt JSON helper. First attempt uses native
        response_format=json_object. Second attempt re-issues with a
        stricter user prompt and the permissive extractor as a safety net.
        """
        json_instruction = (
            "\n\nReturn valid JSON only. No prose, no markdown, no code fences."
        )
        text = await self._chat(
            model=model,
            system=system,
            user=user + json_instruction,
            max_tokens=max_tokens,
            json_mode=True,
        )
        try:
            return _extract_json_from_text(text)
        except (json.JSONDecodeError, ValueError) as parse_err:
            logger.warning(
                "JSON parse failed on first attempt (%s); retrying with stricter prompt",
                parse_err,
            )

        retry_user = (
            "Your previous response could not be parsed as JSON. "
            "Return ONLY the JSON object — start with { and end with }.\n\n"
            "Original request:\n" + user
        )
        retry_text = await self._chat(
            model=model,
            system=system,
            user=retry_user,
            max_tokens=max_tokens,
            json_mode=True,
        )
        try:
            return _extract_json_from_text(retry_text)
        except (json.JSONDecodeError, ValueError) as final_err:
            logger.error(
                "JSON parse failed after retry. Response was: %s",
                retry_text[:500],
            )
            raise ValueError(
                f"vLLM model {model} did not return valid JSON after two attempts. "
                f"Final parse error: {final_err}. "
                f"Response preview: {retry_text[:200]!r}"
            ) from final_err
