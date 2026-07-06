# AUDIT Baseline — 2026-07-05

Branch: `competition/amd-hackathon` @ 71dda9b (dirty: .env.hackathon.example, submodule content)

## Repo map

| Component | Tech | Entry point | Port |
|---|---|---|---|
| Orchestrator API | FastAPI, Python 3.14 (system), async | `orchestrator/api/__init__.py` (`create_app`) | 8000 |
| Orchestrator CLI | same | `orchestrator/cli.py` | — |
| TRIBE v2 scorer | FastAPI, Python 3.11 venv, PyTorch | `tribe_scorer/main.py` | 8001 |
| MiroFish backend | Flask (Docker), git submodule | `mirofish/backend/run.py` | 5001 |
| LiteLLM proxy | Docker | docker-compose | 4000 |
| Neo4j | Docker, 5.18 | docker-compose | 7474/7687 |
| UI | React 19 + Vite + TS | `ui/` | 5173 |
| Vendored TRIBE | `tribe_scorer/vendor/tribev2` (submodule) | — | — |

## Agent-execution layer (highest-risk for scale target)

- Orchestrator `campaign_runner.py` drives per-campaign pipeline; background tasks tracked in `app.state.running_tasks` (plain dict), progress via `app.state.progress_queues` + SSE.
- `MirofishRunner` → `mirofish_client.py` (631 ln) → MiroFish Flask API.
- MiroFish `SimulationManager` (per-sim state.json files + in-memory dict) prepares agent profiles from Neo4j graph entities.
- MiroFish `SimulationRunner`: **class-level mutable dicts** (`_processes`, `_run_states`, `_action_queues`, `_monitor_threads`, `_stdout_files`) — spawns one **OS subprocess per simulation** (`run_parallel_simulation.py` → OASIS/CAMEL agents), 1 monitor **thread** per sim polling JSONL action logs every 2s, file-based IPC (`simulation_ipc.py`) for agent interviews.
- Agent LLM calls: OASIS agents → LiteLLM (4000) → Anthropic Haiku (or vLLM path on this branch).
- TRIBE inference serialized by a single `threading.Lock` in `tribe_scorer/main.py`.

## Baseline results

### Orchestrator pytest (system Python 3.14, `pytest -q`)
- **FAIL (collection error)**: `orchestrator/tests/test_tribe_timeout.py:17` — `ImportError: cannot import name 'CHUNK_SIZE_WORDS' from orchestrator.clients.tribe_client`. Constant was removed/renamed (tribe_client.py now only mentions chunking in comments). Collection error aborts entire suite.
- With `--ignore=orchestrator/tests/test_tribe_timeout.py`: **311 passed**, 2 deprecation warnings (websockets.legacy via test_vllm_smoke), 61.7s.

### TRIBE scorer pytest (py311 venv, `tests/`)
- **32 passed**, 17.4s. 1 warning: `Unknown config option: asyncio_mode` (pytest-asyncio not installed in tribe venv — repo-root pyproject leaks config).

### UI (`ui/`)
- `npm run lint`: **9 errors, 1 warning**
  - 6× `react-refresh/only-export-components`
  - 3× `react-hooks/set-state-in-effect` (cascading render risk; incl. `src/pages/campaign-detail.tsx:745`)
  - 1× `react-hooks/exhaustive-deps` warning (campaign-detail.tsx:272 `iterations`)
- `npx tsc --noEmit`: **clean**

### Environment notes
- System Python is **3.14** (CLAUDE.md says 3.13+; requests/urllib3 version-mismatch warning at import).
- No Python linter (ruff/flake8) configured for orchestrator; no mypy config.
- MiroFish is a submodule — fix policy: minimal, contained changes only.
- `tribe_scorer/vendor/tribev2` vendored — audit interface use only, not internals.
