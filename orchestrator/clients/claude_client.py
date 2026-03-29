"""
Claude API client for Nexus Sim orchestrator.

Wraps the Anthropic AsyncAnthropic SDK with:
- Dynamic credential loading (env var > credentials file)
- Retry logic with exponential backoff for rate limits and server errors
- JSON mode helpers that parse and retry on malformed output
- Credential refresh on 401 errors (OAuth token rotation)
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import anthropic
from anthropic import AsyncAnthropic, APIStatusError, APIConnectionError

logger = logging.getLogger(__name__)

# Default credential file path (Windows)
DEFAULT_CREDENTIALS_PATH = "C:/Users/adars/.claude/.credentials.json"

# Retry configuration
MAX_RETRIES = 3
BACKOFF_BASE = 1.0  # seconds — doubles each retry: 1s, 2s, 4s

# HTTP status codes that trigger a retry
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _load_api_key_from_credentials(credentials_path: str) -> str | None:
    """
    Read the OAuth access token from ~/.claude/.credentials.json.
    Returns None if the file doesn't exist or can't be parsed.
    """
    path = Path(credentials_path)
    if not path.exists():
        logger.debug("Credentials file not found at %s", credentials_path)
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        token = data.get("claudeAiOauth", {}).get("accessToken")
        if token:
            logger.debug("Loaded API key from credentials file")
            return token
        logger.warning(
            "Credentials file exists but claudeAiOauth.accessToken is missing"
        )
        return None
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read credentials file %s: %s", credentials_path, exc)
        return None


def _extract_json_from_text(text: str) -> dict[str, Any]:
    """
    Extract a JSON object from a model response that may contain surrounding prose.
    Handles markdown code fences (```json ... ```) and bare JSON objects.
    Raises ValueError if no valid JSON is found.
    """
    # Strip markdown code fences first
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        candidate = fence_match.group(1).strip()
        return json.loads(candidate)

    # Try the full text as JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Try to find the first {...} block
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        return json.loads(brace_match.group(0))

    raise ValueError(f"No valid JSON found in model response: {text[:200]!r}")


class ClaudeClient:
    """
    Async wrapper around the Anthropic SDK.

    Supports two models:
    - Opus: for deep analysis tasks (cross-system reasoning, report generation)
    - Haiku: for fast structured tasks (variant generation, agent persona configs)

    Model names are read from environment variables at construction time:
    - CLAUDE_OPUS_MODEL  (default: claude-opus-4-6)
    - CLAUDE_HAIKU_MODEL (default: claude-haiku-4-5-20251001)

    API key resolution order:
    1. ANTHROPIC_API_KEY environment variable (if non-empty)
    2. claudeAiOauth.accessToken from the credentials file
    """

    def __init__(self) -> None:
        self._credentials_path: str = os.environ.get(
            "CLAUDE_CREDENTIALS_PATH", DEFAULT_CREDENTIALS_PATH
        )
        self._opus_model: str = os.environ.get(
            "CLAUDE_OPUS_MODEL", "claude-opus-4-6"
        )
        self._haiku_model: str = os.environ.get(
            "CLAUDE_HAIKU_MODEL", "claude-haiku-4-5-20251001"
        )
        self._client: AsyncAnthropic = self._build_client()

    def _resolve_api_key(self) -> str:
        """
        Determine the API key to use.
        Priority: ANTHROPIC_API_KEY env var > credentials file.
        Raises RuntimeError if no key is found.
        """
        env_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if env_key:
            return env_key

        file_key = _load_api_key_from_credentials(self._credentials_path)
        if file_key:
            return file_key

        raise RuntimeError(
            "No Anthropic API key found. Set ANTHROPIC_API_KEY environment variable "
            f"or ensure {self._credentials_path} contains claudeAiOauth.accessToken."
        )

    def _build_client(self) -> AsyncAnthropic:
        """Create a fresh AsyncAnthropic client with the current API key."""
        api_key = self._resolve_api_key()
        return AsyncAnthropic(api_key=api_key)

    def _refresh_client(self) -> None:
        """
        Re-read credentials and rebuild the Anthropic client.
        Called when a 401 is received (OAuth token may have rotated).
        """
        logger.info("Refreshing Anthropic client credentials (token may have rotated)")
        self._client = self._build_client()

    async def _call(
        self,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
    ) -> str:
        """
        Core async call to the Anthropic messages API.

        Implements exponential backoff for rate limits (429) and server errors (5xx).
        Refreshes credentials on 401 and retries once.

        Returns the text content of the first content block.
        Raises anthropic.APIError on unrecoverable failure.
        """
        last_exception: Exception | None = None
        credential_refreshed = False

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self._client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                # Extract text from response
                text_blocks = [
                    block.text
                    for block in response.content
                    if hasattr(block, "text")
                ]
                return "".join(text_blocks)

            except APIStatusError as exc:
                last_exception = exc
                status = exc.status_code

                # Handle credential rotation — refresh and retry once
                if status == 401 and not credential_refreshed:
                    logger.warning(
                        "Received 401 from Anthropic API; refreshing credentials"
                    )
                    self._refresh_client()
                    credential_refreshed = True
                    continue  # Don't count this as a backoff attempt

                # Handle retryable errors with backoff
                if status in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "Anthropic API returned %d on attempt %d/%d; "
                        "retrying in %.1fs (model=%s)",
                        status, attempt + 1, MAX_RETRIES, wait, model,
                    )
                    await asyncio.sleep(wait)
                    continue

                # Non-retryable or exhausted retries
                logger.error(
                    "Anthropic API call failed with status %d after %d attempt(s): %s",
                    status, attempt + 1, exc,
                )
                raise

            except APIConnectionError as exc:
                last_exception = exc
                if attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "Connection error on attempt %d/%d; retrying in %.1fs: %s",
                        attempt + 1, MAX_RETRIES, wait, exc,
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.error("Anthropic API connection failed after %d attempts", attempt + 1)
                raise

        # Should not reach here in practice, but satisfy the type checker
        assert last_exception is not None
        raise last_exception

    async def call_opus(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> str:
        """
        Call Claude Opus for deep analysis tasks.

        Use for: cross-system analysis, final report generation, anything requiring
        multi-step reasoning over TRIBE v2 + MiroFish combined results.

        Returns the raw text response.
        """
        logger.debug("Calling Opus (model=%s, max_tokens=%d)", self._opus_model, max_tokens)
        return await self._call(
            model=self._opus_model,
            system=system,
            user=user,
            max_tokens=max_tokens,
        )

    async def call_haiku(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> str:
        """
        Call Claude Haiku for fast structured tasks.

        Use for: variant generation, demographic-to-agent-config translation,
        any task that is primarily structured output rather than deep reasoning.

        Returns the raw text response.
        """
        logger.debug("Calling Haiku (model=%s, max_tokens=%d)", self._haiku_model, max_tokens)
        return await self._call(
            model=self._haiku_model,
            system=system,
            user=user,
            max_tokens=max_tokens,
        )

    async def call_opus_json(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """
        Call Claude Opus and parse the response as JSON.

        The user prompt is augmented with a JSON-output instruction.
        If the first response fails to parse, a clarification message is sent
        as a retry (one extra attempt).

        Returns a parsed dict. Raises ValueError on unrecoverable parse failure.
        """
        return await self._call_json(
            call_fn=self.call_opus,
            system=system,
            user=user,
            max_tokens=max_tokens,
        )

    async def call_haiku_json(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """
        Call Claude Haiku and parse the response as JSON.

        The user prompt is augmented with a JSON-output instruction.
        If the first response fails to parse, a clarification message is sent
        as a retry (one extra attempt).

        Returns a parsed dict. Raises ValueError on unrecoverable parse failure.
        """
        return await self._call_json(
            call_fn=self.call_haiku,
            system=system,
            user=user,
            max_tokens=max_tokens,
        )

    async def _call_json(
        self,
        call_fn,
        system: str,
        user: str,
        max_tokens: int,
    ) -> dict[str, Any]:
        """
        Internal helper: call a model function and parse JSON from the response.

        On parse failure, retries once with an explicit "return only JSON" prompt.
        """
        json_instruction = (
            "\n\nIMPORTANT: Your entire response must be valid JSON only. "
            "Do not include any explanation, prose, or markdown code fences. "
            "Return only the raw JSON object."
        )
        augmented_user = user + json_instruction

        text = await call_fn(system=system, user=augmented_user, max_tokens=max_tokens)

        try:
            return _extract_json_from_text(text)
        except (json.JSONDecodeError, ValueError) as parse_err:
            logger.warning(
                "JSON parse failed on first attempt (%s); retrying with stricter prompt",
                parse_err,
            )

        # Retry with an even more explicit instruction
        retry_user = (
            "You previously responded with text that could not be parsed as JSON. "
            "Return ONLY the JSON object — no explanation, no markdown, no code fences. "
            "Start your response with { and end with }.\n\n"
            "Original request:\n"
            + user
        )
        retry_text = await call_fn(system=system, user=retry_user, max_tokens=max_tokens)

        try:
            return _extract_json_from_text(retry_text)
        except (json.JSONDecodeError, ValueError) as final_err:
            logger.error(
                "JSON parse failed after retry. Response was: %s",
                retry_text[:500],
            )
            raise ValueError(
                f"Model did not return valid JSON after two attempts. "
                f"Final parse error: {final_err}. "
                f"Response preview: {retry_text[:200]!r}"
            ) from final_err
