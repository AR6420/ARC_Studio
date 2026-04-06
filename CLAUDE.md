# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Nexus Sim** — Content optimization platform combining neural response prediction (TRIBE v2), multi-agent social simulation (MiroFish-Offline), and LLM-driven iterative optimization (Claude) into a single feedback loop. Phase 1 POC: single-user, local machine, non-commercial.

### Constraints

- **Hardware**: Single RTX 5070 Ti GPU shared between TRIBE v2 and Ollama embeddings
- **API**: Claude API rate limits — Haiku batched, Opus sequential (4-8 calls/campaign)
- **Dependency**: TRIBE v2 requires HuggingFace LLaMA 3.2-3B gated model approval
- **Dependency**: MiroFish-Offline is a Git submodule — minimal modifications to enable upstream merges
- **Performance**: Full campaign (40 agents, 4 iterations) must complete in <= 20 minutes
- **Scope**: Phase 1 POC only — no auth, no HTTPS, no multi-user
<!-- GSD:project-end -->

## Build and Run Commands

### Docker services (Neo4j, LiteLLM, MiroFish)
```bash
docker compose up -d          # Start all Docker services
docker compose down            # Stop all
docker compose up -d litellm   # Restart just LiteLLM (e.g., after API key refresh)
```

### TRIBE v2 scorer (Python 3.11 venv, port 8001)
```bash
bash tribe_scorer/start.sh     # Start scorer (loads model ~60s, then seeds baseline)
```

### Orchestrator API (system Python, port 8000)
```bash
# Via uvicorn directly:
cd orchestrator && python -m uvicorn api:app --port 8000
# Or via factory:
cd orchestrator && python -m uvicorn api:create_app --factory --port 8000
```

### UI (port 5173)
```bash
cd ui && npm run dev           # Vite dev server
cd ui && npm run build         # Production build (tsc + vite)
cd ui && npm run lint          # ESLint
```

### CLI campaign runner (no server needed)
```bash
python -m orchestrator.cli \
  --seed-content "Your content..." \
  --prediction-question "How will the audience react?" \
  --demographic tech_professionals \
  --max-iterations 2 \
  --output results/my_campaign.json
```

### Tests
```bash
# All orchestrator tests (194 tests, pytest with asyncio_mode=auto)
pytest

# Single test file
pytest orchestrator/tests/test_campaign_runner.py

# Single test
pytest orchestrator/tests/test_campaign_runner.py::test_function_name -v

# With output
pytest -s orchestrator/tests/test_composite_scorer.py
```
`pyproject.toml` sets `testpaths = ["orchestrator/tests"]` and `asyncio_mode = "auto"`.

### OAuth token refresh
```bash
# Update .env with current Claude OAuth token
bash scripts/refresh-env.sh
# Also restart LiteLLM container to pick up new key
bash scripts/refresh-env.sh --restart
```
The orchestrator also auto-refreshes the LiteLLM API key on startup via `_refresh_litellm_api_key()` in `orchestrator/api/__init__.py`.

## Architecture

### System overview
```
React UI (5173) → Orchestrator FastAPI (8000) → TRIBE v2 (8001) + MiroFish (5001)
                                               ↕ Claude API (Haiku + Opus)
MiroFish (Docker) → LiteLLM (4000) → Anthropic API
                  → Neo4j (7687)
                  → Ollama (11434, host)
```

### Pipeline flow (per campaign iteration)
1. **Variant generation** — Claude Haiku generates N content variants from seed + feedback
2. **TRIBE v2 scoring** — Each variant scored on 7 neural dimensions (text → TTS → WhisperX → LLaMA 3.2-3B → brain-encoding → ROI extraction → normalization)
3. **MiroFish simulation** — Multi-agent social simulation with Claude Haiku agents (create ontology → spawn agents → simulate → extract metrics)
4. **Composite scoring** — 7 formulas blend TRIBE neural scores + MiroFish social metrics
5. **Cross-system analysis** — Claude Opus analyzes why neural patterns led to social outcomes
6. **Optimization loop** — Threshold checking, convergence detection, iteration feedback
7. **Report generation** — 4-layer report (verdict, scorecard, mass psychology general + technical)

### Key design patterns

**Graceful degradation**: When TRIBE or MiroFish is unavailable, the pipeline continues with partial data. Composite scores that need the missing system return `None`. The system does a pre-flight health check at iteration start.

**Two Python runtimes**: The orchestrator runs on system Python 3.13+. TRIBE v2 requires Python 3.11 specifically (pyannote.audio dependency) and runs in its own venv at `tribe_scorer/.venv/`.

**OAuth credential flow**: The Claude API key can come from `ANTHROPIC_API_KEY` env var, or falls back to reading the OAuth token from `~/.claude/.credentials.json`. On 401 errors, the client refreshes credentials automatically. LiteLLM needs the key in `.env` and must be restarted when the token rotates.

**Configuration**: Both services use Pydantic `BaseSettings` loading from a shared `.env` file at repo root. Orchestrator config: `orchestrator/config.py`. TRIBE config: `tribe_scorer/config.py`.

**TRIBE inference serialization**: The TRIBE v2 model and its exca cache are not thread-safe. A `threading.Lock` (`_inference_lock` in `tribe_scorer/main.py`) ensures only one inference runs at a time.

**Windows MAX_PATH workaround**: TRIBE v2's exca cache creates deeply nested paths. On Windows, the cache folder defaults to `C:\tc` to stay under the 260-char limit.

**Prompt templates**: All Claude prompt templates live in `orchestrator/prompts/`. Demographic-specific cognitive weights are in `demographic_profiles.py`.

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

- **Orchestrator package layout**: `api/` (FastAPI routes, schemas), `clients/` (HTTP clients for TRIBE + MiroFish + Claude), `engine/` (pipeline logic), `storage/` (SQLite via aiosqlite), `prompts/` (Claude prompt templates)
- **TRIBE scorer layout**: `scoring/` (model_loader, text_scorer, roi_extractor, normalizer), `vendor/tribev2/` (Git submodule, vendored TRIBE v2 source)
- **Tests**: All in `orchestrator/tests/`, use pytest-asyncio with `asyncio_mode=auto`. Shared fixtures in `conftest.py`. External services are mocked — `mock_claude_client` fixture provides `AsyncMock` with `call_haiku_json`/`call_opus_json`.
- **API routes**: All under `/api` prefix. Routers split by domain: `campaigns.py`, `health.py`, `progress.py`, `reports.py`, `agents.py`
- **SSE streaming**: Campaign progress uses Server-Sent Events via `sse-starlette`. Progress queues stored on `app.state.progress_queues`.
- **Frontend**: React 19 + Vite + TypeScript + Tailwind CSS v4 + shadcn/ui. Data fetching via TanStack React Query. Hooks in `src/hooks/`, API types in `src/api/`.
<!-- GSD:conventions-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite 8, TypeScript 5.9, Tailwind CSS 4, shadcn/ui, TanStack React Query, Recharts, React Router 7 |
| Orchestrator API | FastAPI, Pydantic v2, uvicorn, httpx, aiosqlite, anthropic SDK |
| TRIBE v2 Scorer | FastAPI, PyTorch, Transformers (LLaMA 3.2-3B), WhisperX, gTTS, spaCy |
| MiroFish | Flask (Docker), Neo4j 5.18, CAMEL-AI/OASIS agents |
| LLM Proxy | LiteLLM (Docker, OpenAI→Anthropic translation) |
| Embeddings | Ollama (nomic-embed-text, host-native) |
| Database | SQLite (orchestrator), Neo4j (MiroFish knowledge graphs) |
| Claude Models | Opus (cross-system analysis, reports), Haiku (variant generation, MiroFish agents) |
<!-- GSD:stack-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
