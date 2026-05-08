"""
End-to-end smoke test: orchestrator's variant_generator -> OpenAICompatClient
-> a tiny in-process FastAPI app pretending to be vLLM.

This exercises the full call path used by Phase 1 of a campaign — variant
generation against a vLLM endpoint — without an actual model, GPU, or
external network. Validates the wiring before MI300X provisioning.

The fake server emits OpenAI-shaped /v1/chat/completions responses,
sometimes returning structured JSON that variant_generator can parse.
"""

import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request

from orchestrator.clients.openai_compat_client import OpenAICompatClient
from orchestrator.engine.variant_generator import VariantGenerator


FAKE_VARIANTS_PAYLOAD = {
    "variants": [
        {
            "id": "v1_smoke",
            "content": "Smoke-test variant content.",
            "strategy": "social_proof",
            "key_psychological_mechanisms": ["bandwagon"],
            "expected_strengths": ["fast"],
            "potential_risks": ["thin"],
        },
        {
            "id": "v2_smoke",
            "content": "Second smoke-test variant with a different angle.",
            "strategy": "urgency",
            "key_psychological_mechanisms": ["scarcity"],
            "expected_strengths": ["actionable"],
            "potential_risks": ["pushy"],
        },
    ]
}


def build_fake_vllm_app() -> FastAPI:
    """Tiny FastAPI app mimicking vLLM's /v1/chat/completions surface."""
    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        body = await request.json()
        # Model echoed back so the test can confirm correct routing.
        model = body.get("model", "")
        # Always return the same fake JSON payload; the orchestrator will parse it.
        content = json.dumps(FAKE_VARIANTS_PAYLOAD)
        return {
            "id": "smoke-1",
            "object": "chat.completion",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    return app


@asynccontextmanager
async def run_fake_vllm(port: int):
    """Run the fake vLLM in a background task; yield the base URL."""
    config = uvicorn.Config(
        build_fake_vllm_app(),
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    base_url = f"http://127.0.0.1:{port}"
    # Poll until the uvicorn loop has set started=True. This avoids the
    # race where the test's first POST hits the port before bind completes.
    for _ in range(200):
        if getattr(server, "started", False):
            break
        await asyncio.sleep(0.05)
    else:
        raise RuntimeError("fake vLLM never came up")
    try:
        yield base_url
    finally:
        server.should_exit = True
        await task


@pytest.mark.asyncio
async def test_variant_generator_against_fake_vllm():
    """
    Full path: OpenAICompatClient hits a real httpx /v1/chat/completions
    endpoint that the test owns, parses the JSON payload, and the
    variant_generator returns 2 valid variant dicts.

    Validates that the abstraction wires together end-to-end before we
    ever provision the MI300X.
    """
    async with run_fake_vllm(port=18000) as base_url:
        client = OpenAICompatClient(
            base_url=f"{base_url}/v1",
            orchestrator_model="Qwen/Qwen3.5-27B",
            agent_model="Qwen/Qwen3.5-9B",
        )
        gen = VariantGenerator(claude_client=client)
        variants = await gen.generate_variants(
            campaign_brief="Test seed content.",
            demographic="tech_professionals",
            num_variants=2,
        )
    assert len(variants) == 2
    assert variants[0]["id"] == "v1_smoke"
    assert variants[1]["strategy"] == "urgency"
    # Confirm both required structural fields are present
    for v in variants:
        assert "content" in v
        assert "strategy" in v
