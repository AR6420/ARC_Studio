# Run the orchestrator locally against a mock vLLM endpoint

This is the development-loop guide for Phase 0+. It lets you exercise the `LLM_PROVIDER=vllm` code path on your laptop without a GPU, real vLLM, or HuggingFace weights. Phase 6 will extend this into `04_run_on_amd.md` (the real-MI300X version).

## What you need

- The repo on `competition/amd-hackathon` branch.
- Python venv with `pip install -r orchestrator/requirements.txt` (now includes `openai>=1.40.0`).
- TRIBE v2 + MiroFish are still mocked (or running locally). Nothing about the LLM swap touches them.

## Option A — point at a fake vLLM (zero external deps)

The test suite ships a tiny in-process FastAPI app that mimics `/v1/chat/completions`. To use it interactively, run it standalone:

```python
# scripts/fake_vllm.py  (or just paste in a Python REPL)
import json, uvicorn
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/v1/chat/completions")
async def chat(req: Request):
    body = await req.json()
    return {
        "id": "fake-1",
        "object": "chat.completion",
        "created": 0,
        "model": body.get("model", ""),
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": json.dumps({
                "variants": [
                    {"id": "v1", "content": "Mock variant 1", "strategy": "social_proof",
                     "key_psychological_mechanisms": ["bandwagon"],
                     "expected_strengths": ["fast"], "potential_risks": ["thin"]},
                    {"id": "v2", "content": "Mock variant 2", "strategy": "urgency",
                     "key_psychological_mechanisms": ["scarcity"],
                     "expected_strengths": ["actionable"], "potential_risks": ["pushy"]},
                ]
            })},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=18000, log_level="warning")
```

Then `.env`:

```bash
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://127.0.0.1:18000/v1
VLLM_ORCHESTRATOR_MODEL=Qwen/Qwen3.5-27B
VLLM_AGENT_MODEL=Qwen/Qwen3.5-9B
```

Run the orchestrator API or CLI as normal. All Claude calls now hit the fake server. Same JSON shape comes back; nothing else in the pipeline notices.

## Option B — point at a real local Ollama (still no GPU needed for the test)

Ollama serves an OpenAI-compatible `/v1` surface. Pull a small Qwen and aim the orchestrator at it:

```bash
ollama pull qwen2.5:7b
```

`.env`:

```bash
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://127.0.0.1:11434/v1
VLLM_ORCHESTRATOR_MODEL=qwen2.5:7b
VLLM_AGENT_MODEL=qwen2.5:7b
```

Same model on both tiers is fine for local sanity-checking — it just exercises the code path.

## Confirming the swap

When the orchestrator starts, look for:

```
LLM provider: vllm (OpenAICompatClient -> http://127.0.0.1:18000/v1)
LLM_PROVIDER=vllm -- skipping LiteLLM key refresh
OpenAICompatClient initialised: base_url=..., orchestrator=..., agent=...
```

Three log lines, in that order. If you see `LLM provider: anthropic (ClaudeClient)`, your `.env` didn't load — check that `LLM_PROVIDER=vllm` is set.

## Reverting to production (Anthropic)

```bash
LLM_PROVIDER=anthropic
```

(or just delete the line — `anthropic` is the default). The factory returns the unmodified `ClaudeClient`, OAuth + LiteLLM refresh wake back up, no other change.

## Tests

```bash
pytest orchestrator/tests/test_openai_compat_client.py -v   # unit
pytest orchestrator/tests/test_vllm_smoke.py -v             # in-process E2E
pytest --ignore=orchestrator/tests/test_tribe_timeout.py    # full suite
```

The `--ignore` is for a pre-existing broken test on `main` (commit 495956b imports `CHUNK_SIZE_WORDS` that doesn't exist). Will be fixed separately.
