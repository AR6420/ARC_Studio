# Phase 5: Orchestrator Integration Pipeline - Research

**Researched:** 2026-03-29
**Domain:** FastAPI orchestration pipeline, async HTTP service integration, SQLite persistence, composite scoring
**Confidence:** HIGH

## Summary

Phase 5 wires three existing subsystems (TRIBE v2 neural scorer, MiroFish social simulation, Claude LLM client) into a single-iteration campaign pipeline exposed via a FastAPI orchestrator on port 8000. The orchestrator already has foundational assets in place: a fully async `ClaudeClient` with Opus/Haiku/JSON modes, Pydantic `Settings` with all service URLs configured, complete prompt templates for variant generation and cross-system analysis, and 6 demographic presets with cognitive weights. The three directories that need to be populated are `api/`, `engine/`, and `storage/` -- all currently empty.

The integration surface is well-defined but complex. TRIBE v2 is a straightforward FastAPI service (POST /api/score, POST /api/score/batch, GET /api/health on port 8001). MiroFish is a Flask service on port 5000 with a multi-step async workflow: ontology generation (POST /api/graph/ontology/generate with multipart/form-data), graph build (POST /api/graph/build), simulation create (POST /api/simulation/create), simulation prepare (POST /api/simulation/prepare), simulation start (POST /api/simulation/start), and polling for completion (GET /api/simulation/{id}/run-status). The MiroFish flow requires polling task status between steps since graph build and simulation preparation are background tasks.

**Primary recommendation:** Build bottom-up: storage layer first (SQLite schema + CRUD), then HTTP clients for TRIBE/MiroFish, then engine modules (variant generator, composite scorer, result analyzer, campaign runner), then FastAPI API layer, and finally the CLI. Use the existing `ClaudeClient`, `Settings`, prompt templates, and demographic profiles as-is -- they are production-ready.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Generate **3 content variants** per campaign iteration using Claude Haiku.
- **D-02:** All 3 variants are scored by TRIBE v2 -- **no early elimination**. All 3 also go to MiroFish simulation.
- **D-03:** TRIBE v2 scoring is **sequential** (one variant at a time) to avoid GPU contention on the single RTX 5070 Ti.
- **D-04:** MiroFish simulations are **sequential** (one variant at a time) to avoid Neo4j graph DB conflicts. Graph is rebuilt per variant.
- **D-05:** Follow the requirement as originally specified: **graceful degradation with partial data**. When TRIBE or MiroFish is unavailable, skip the unavailable system, warn the user, and note the gap in results. Composite scores that depend on missing inputs show as N/A.
- **D-06:** Health detection approach is **Claude's discretion** -- pre-flight check or fail-on-first-call, whichever is more robust.
- **D-07:** **Full persistence** in SQLite -- store everything: campaign config, all variant texts, all raw TRIBE scores, all raw MiroFish metrics, composite scores, Claude analysis text, per iteration.
- **D-08:** TRIBE scores (7 dims), MiroFish metrics (8 fields), and composite scores (7 formulas) stored as **JSON text columns**.
- **D-09:** Campaigns have an explicit **status column** (pending, running, completed, failed) updated as the pipeline progresses.
- **D-10:** Campaign creation via a **single POST** with all config (seed_content, prediction_question, demographic, agent_count, max_iterations, thresholds). One call creates and optionally starts.

### Claude's Discretion
- Health check implementation approach (D-06) -- pre-flight vs fail-on-first-call
- CLI execution interface design -- not discussed, Claude has flexibility on the CLI shape

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ORCH-01 | FastAPI app with CORS for localhost:5173, lifespan hooks | FastAPI lifespan pattern documented; CORS config from tech spec; existing `settings.orchestrator_port` = 8000 |
| ORCH-02 | SQLite database with campaign and iteration tables | aiosqlite available; D-07/D-08/D-09 define schema requirements; JSON text columns for flexible score storage |
| ORCH-03 | Pydantic schemas for all request/response models | Tech spec defines CampaignCreate and CampaignResponse schemas; Pydantic v2 installed |
| ORCH-04 | Campaign CRUD endpoints (POST, GET, GET list, DELETE) | D-10 defines single POST with all config; tech spec defines `/api/campaigns` routes |
| ORCH-05 | System health endpoint pinging all downstream services | TRIBE has GET /api/health; MiroFish has GET /health; Claude client can be tested with a lightweight call |
| ORCH-06 | Demographics endpoint returning preset list | `demographic_profiles.py` already has `list_profiles()` helper returning key/label/description dicts |
| ORCH-07 | Async HTTP clients for TRIBE scorer and MiroFish | httpx AsyncClient available; TRIBE is simple POST; MiroFish requires multi-step stateful workflow |
| ORCH-08 | Variant generator using Claude to create N content variants | `ClaudeClient.call_haiku_json()` + `variant_generation.py` prompts ready; D-01 says 3 variants |
| ORCH-09 | TRIBE scoring pipeline (orchestrator -> tribe_scorer -> composite scores) | TRIBE endpoint: POST /api/score with `{"text": "..."}` returns 7 scores; D-03 says sequential |
| ORCH-10 | MiroFish simulation pipeline (orchestrator -> graph build -> simulation -> results) | Multi-step API: ontology/generate -> build -> create -> prepare -> start -> poll -> extract metrics |
| ORCH-11 | Composite score calculator implementing all 7 formulas from Results.md | All 7 formulas documented in Results.md section 3.2; cognitive weights from demographic_profiles.py |
| ORCH-12 | Result analyzer using Claude Opus for cross-system analysis | `ClaudeClient.call_opus_json()` + `result_analysis.py` prompts ready; must reference both systems |
| ORCH-13 | Campaign runner wiring all components into single-iteration pipeline | Sequence: generate variants -> score all 3 -> simulate all 3 -> compute composites -> analyze |
| ORCH-14 | End-to-end CLI execution producing variants, scores, metrics, and analysis | CLI shape is Claude's discretion; needs to call campaign_runner programmatically |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Hardware**: Single RTX 5070 Ti GPU shared between TRIBE v2 and Ollama embeddings -- sequential scoring is mandatory
- **API**: Claude API rate limits -- Haiku batched, Opus sequential (4-8 calls/campaign)
- **Performance**: Full campaign (40 agents, 4 iterations) must complete in <= 20 minutes
- **Scope**: Phase 1 POC only -- no auth, no HTTPS, no multi-user
- **GSD Workflow**: Must follow GSD workflow enforcement for all edits

## Standard Stack

### Core (Already Installed)
| Library | Installed Version | Latest | Purpose | Why Standard |
|---------|-------------------|--------|---------|--------------|
| fastapi | 0.128.1 | 0.135.2 | Web framework | Async native, Pydantic integration, OpenAPI docs |
| uvicorn | 0.40.0 | 0.40.0 | ASGI server | Standard FastAPI production server |
| pydantic | 2.12.5 | 2.12.5 | Schema validation | Type-safe request/response models |
| pydantic-settings | 2.12.0 | 2.12.0 | Config management | Already used in orchestrator/config.py |
| httpx | 0.28.1 | 0.28.1 | Async HTTP client | For calling TRIBE v2 and MiroFish services |
| aiosqlite | 0.22.1 | 0.22.1 | Async SQLite | Non-blocking database access |
| anthropic | 0.86.0 | 0.86.0 | Claude API SDK | Already used in ClaudeClient |
| sse-starlette | 3.3.3 | 3.3.3 | Server-Sent Events | Future use in Phase 6, already installed |
| python-dotenv | 1.2.1 | 1.2.1 | Env loading | .env file support |

**All dependencies are already installed and listed in `orchestrator/requirements.txt`.** No new packages needed for Phase 5.

### Supporting (For Testing -- Wave 0)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 | Test framework | Already installed; use for unit/integration tests |
| pytest-asyncio | (need install) | Async test support | Required for testing async endpoints and engine |

**Installation (testing only):**
```bash
pip install pytest-asyncio
```

## Architecture Patterns

### Recommended Project Structure
```
orchestrator/
  __init__.py
  config.py                     # [EXISTS] Pydantic settings singleton
  requirements.txt              # [EXISTS] All deps listed
  api/
    __init__.py                 # FastAPI app factory, lifespan, CORS
    campaigns.py                # Campaign CRUD endpoints
    health.py                   # System health + demographics endpoints
    schemas.py                  # All Pydantic request/response models
  engine/
    __init__.py
    variant_generator.py        # Claude Haiku variant generation
    tribe_scorer.py             # TRIBE v2 scoring pipeline
    mirofish_runner.py          # MiroFish simulation pipeline
    composite_scorer.py         # 7 composite score formulas
    result_analyzer.py          # Claude Opus cross-system analysis
    campaign_runner.py          # Main orchestration: wires all components
  clients/
    claude_client.py            # [EXISTS] Full async Claude client
    tribe_client.py             # httpx client for TRIBE v2 (port 8001)
    mirofish_client.py          # httpx client for MiroFish (port 5000)
  storage/
    __init__.py
    database.py                 # aiosqlite connection, schema init
    campaign_store.py           # Campaign/iteration CRUD operations
  prompts/
    variant_generation.py       # [EXISTS] Variant gen prompts
    result_analysis.py          # [EXISTS] Cross-system analysis prompts
    report_verdict.py           # [EXISTS] Layer 1 verdict prompts
    report_psychology.py        # [EXISTS] Layer 4 mass psych prompts
    demographic_profiles.py     # [EXISTS] 6 presets with cognitive weights
```

### Pattern 1: FastAPI Lifespan for Resource Management
**What:** Use `@asynccontextmanager` lifespan to initialize shared resources (DB connection, HTTP clients) on startup and close them on shutdown.
**When to use:** Always for the orchestrator app -- manages DB pool and httpx clients.
**Example:**
```python
# Source: FastAPI official docs (https://fastapi.tiangolo.com/advanced/events/)
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init DB, create tables, init HTTP clients
    db = await init_database()
    tribe_client = httpx.AsyncClient(base_url=settings.tribe_scorer_url, timeout=120.0)
    mirofish_client = httpx.AsyncClient(base_url=settings.mirofish_url, timeout=300.0)
    app.state.db = db
    app.state.tribe_client = tribe_client
    app.state.mirofish_client = mirofish_client
    yield
    # Shutdown: close connections
    await tribe_client.aclose()
    await mirofish_client.aclose()
    await db.close()

app = FastAPI(title="Nexus Sim Orchestrator", lifespan=lifespan)
```

### Pattern 2: aiosqlite Connection Management
**What:** Use aiosqlite with `async with` context managers. Single connection for POC (SQLite is single-writer anyway).
**When to use:** All database operations in storage layer.
**Example:**
```python
import aiosqlite

class Database:
    def __init__(self, path: str):
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self):
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._init_schema()

    async def close(self):
        if self._conn:
            await self._conn.close()
```

### Pattern 3: Graceful Degradation with Service Availability Flags
**What:** Pre-flight health check before pipeline execution, then carry availability flags through the pipeline.
**When to use:** Campaign runner startup, before scoring/simulation loops.
**Recommendation (Claude's discretion -- D-06):** Use **pre-flight health check** approach. Rationale: checking once before the pipeline starts is simpler, avoids partial state issues, and lets the user know upfront which systems are available. Fail-on-first-call would mean discovering MiroFish is down only after spending time on TRIBE scoring.
**Example:**
```python
@dataclass
class SystemAvailability:
    tribe_available: bool
    mirofish_available: bool
    warnings: list[str]

async def check_systems(tribe_client, mirofish_client) -> SystemAvailability:
    warnings = []
    tribe_ok = False
    mirofish_ok = False
    try:
        resp = await tribe_client.get("/api/health", timeout=10.0)
        tribe_ok = resp.status_code == 200
    except Exception:
        warnings.append("TRIBE v2 scorer unavailable -- neural scores will be skipped")
    try:
        resp = await mirofish_client.get("/health", timeout=10.0)
        mirofish_ok = resp.status_code == 200
    except Exception:
        warnings.append("MiroFish simulator unavailable -- simulation metrics will be skipped")
    return SystemAvailability(tribe_ok, mirofish_ok, warnings)
```

### Pattern 4: Sequential Processing with Status Updates
**What:** Process variants one-at-a-time (D-03, D-04) with status updates written to DB after each step.
**When to use:** TRIBE scoring loop and MiroFish simulation loop.
**Why:** GPU contention (TRIBE) and Neo4j graph conflicts (MiroFish) require sequential execution.

### Pattern 5: MiroFish Multi-Step Workflow with Polling
**What:** The MiroFish integration requires a 6-step async workflow: create project with ontology -> build graph -> create simulation -> prepare simulation -> start simulation -> poll until complete -> extract results.
**When to use:** Each variant's simulation run.
**Critical detail:** Steps 2 (graph build) and 4 (simulation prepare) are background tasks. The orchestrator must poll `/api/graph/task/{task_id}` and `/api/simulation/prepare/status` until completion before proceeding.

### Anti-Patterns to Avoid
- **Concurrent GPU access:** Never run TRIBE scoring for multiple variants in parallel -- single RTX 5070 Ti is shared
- **Concurrent Neo4j writes:** Never run multiple MiroFish simulations in parallel -- graph DB conflicts
- **Blocking the event loop:** Never call synchronous operations (file I/O, CPU-heavy computation) directly in async code -- use `asyncio.to_thread()` or thread executors
- **Huge JSON in memory:** MiroFish action logs can be large -- extract only the metrics needed, don't store raw action dumps
- **Missing error boundaries:** Each service call must have try/except with timeout -- a hung TRIBE inference should not block the entire pipeline

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retry logic | Custom retry loops for TRIBE/MiroFish | httpx with `Timeout` + manual retry (simple loop) or `tenacity` | httpx has built-in timeout; for retries, the existing ClaudeClient pattern (exponential backoff) can be replicated |
| JSON extraction from LLM | Custom regex parsing | Existing `_extract_json_from_text()` from claude_client.py | Already handles markdown fences, bare JSON, and brace extraction |
| Demographic lookup | New config system | Existing `demographic_profiles.py` helpers | `get_profile()`, `list_profiles()`, `get_cognitive_weights()` already implemented |
| Prompt assembly | String concatenation | Existing prompt template functions | `build_variant_generation_prompt()`, `build_result_analysis_prompt()` are ready |
| Config/settings | New env loading | Existing `orchestrator/config.py` Settings singleton | All URLs, ports, defaults already configured |
| UUID generation | Custom ID schemes | Python's `uuid.uuid4()` | Standard, collision-free |

**Key insight:** Approximately 60% of the orchestrator's complexity is already coded in existing modules (ClaudeClient, Settings, prompt templates, demographic profiles). The new code is primarily integration glue, HTTP clients for TRIBE/MiroFish, the SQLite storage layer, the composite scorer formulas, and the campaign runner that wires everything together.

## MiroFish Integration Surface (Critical Detail)

The MiroFish Flask API has a complex multi-step workflow. All routes are prefixed:
- Graph operations: `/api/graph/...`
- Simulation operations: `/api/simulation/...`
- Report operations: `/api/report/...`
- Health check: `/health`

### Full MiroFish Flow for One Variant

```
1. POST /api/graph/ontology/generate
   Body: multipart/form-data with files (content as .txt) + simulation_requirement
   Returns: { project_id, ontology }
   NOTE: Synchronous -- returns immediately with result

2. POST /api/graph/build
   Body: { project_id }
   Returns: { task_id }
   NOTE: Background task -- must poll

3. GET /api/graph/task/{task_id}
   Returns: { status: "processing"|"completed"|"failed", progress, ... }
   Poll until status == "completed"

4. POST /api/simulation/create
   Body: { project_id, enable_twitter: true, enable_reddit: true }
   Returns: { simulation_id }

5. POST /api/simulation/prepare
   Body: { simulation_id, use_llm_for_profiles: true }
   Returns: { task_id } or { already_prepared: true }
   NOTE: Background task -- must poll

6. POST /api/simulation/prepare/status
   Body: { task_id }
   Poll until ready

7. POST /api/simulation/start
   Body: { simulation_id, platform: "parallel", max_rounds: N }
   Returns: { runner_status: "running" }

8. GET /api/simulation/{simulation_id}/run-status
   Returns: { runner_status: "running"|"completed", current_round, total_rounds, progress_percent }
   Poll until runner_status == "completed"

9. Extract results from multiple endpoints:
   - GET /api/simulation/{simulation_id}/posts (share counts)
   - GET /api/simulation/{simulation_id}/actions (all agent actions)
   - GET /api/simulation/{simulation_id}/timeline (per-round summary)
   - GET /api/simulation/{simulation_id}/agent-stats (per-agent stats)
```

### MiroFish Metric Extraction Challenge

MiroFish does NOT return the 8 metrics (organic_shares, sentiment_trajectory, etc.) in a single structured endpoint. The orchestrator's `mirofish_client.py` must **compute** these metrics from raw simulation data:

1. **organic_shares** -- Count CREATE_POST actions that reference the content
2. **sentiment_trajectory** -- Compute from agent actions per round (requires sentiment analysis of posts/comments)
3. **counter_narrative_count** -- Count distinct opposing narratives from posts
4. **peak_virality_cycle** -- Round with the most sharing activity
5. **sentiment_drift** -- Delta between first and last round sentiment
6. **coalition_formation** -- Derived from agent clustering behavior
7. **influence_concentration** -- Gini coefficient of per-agent action counts
8. **platform_divergence** -- Compare Twitter vs Reddit metrics

This metric computation is a significant piece of logic in the `mirofish_runner.py` engine module. The alternative is to use MiroFish's `/api/report/generate` endpoint, which runs its own analysis with an LLM -- but that would add latency and not give us the structured numeric metrics we need for composite scoring.

**Recommendation:** Build a metrics extractor in `mirofish_runner.py` that computes the 8 metrics from raw actions/posts/timeline data. This is more reliable and faster than depending on MiroFish's report agent.

## TRIBE v2 Integration Surface

Much simpler than MiroFish:

```
POST http://localhost:8001/api/score
Body: { "text": "content to score" }
Response: {
    "attention_capture": 72.0,
    "emotional_resonance": 65.0,
    "memory_encoding": 58.0,
    "reward_response": 70.0,
    "threat_detection": 15.0,
    "cognitive_load": 42.0,
    "social_relevance": 68.0,
    "inference_time_ms": 1234.56
}

GET http://localhost:8001/api/health
Response: { "status": "ok"|"degraded", "model_loaded": bool, "gpu_available": bool, ... }
```

Timeout should be generous (60-120 seconds) since TRIBE v2 inference is GPU-bound and can take 10-30 seconds per text.

## Composite Score Formulas (from Results.md section 3.2)

All 7 formulas with exact definitions:

| Score | Formula | Notes |
|-------|---------|-------|
| Attention score | `0.6 * attention_capture + 0.4 * emotional_resonance` | Pure TRIBE scores |
| Virality potential | `(emotional_resonance * social_relevance) / max(cognitive_load, 10) * mirofish_share_rate_normalized` | Cross-system; mirofish_share_rate_normalized = organic_shares / agent_count * 100 |
| Backlash risk | `threat_detection / max(reward_response + social_relevance, 10) * mirofish_counter_narrative_factor` | Cross-system; counter_narrative_factor = counter_narrative_count / agent_count * 100 |
| Memory durability | `memory_encoding * emotional_resonance * mirofish_sentiment_stability` | Cross-system; sentiment_stability needs derivation from sentiment_trajectory |
| Conversion potential | `reward_response * attention_capture / max(threat_detection, 10)` | Pure TRIBE scores |
| Audience fit | `demographic_weight_adjusted_composite` | Apply cognitive_weights from demographic to all TRIBE scores, then average |
| Polarization index | `mirofish_coalition_count * mirofish_platform_divergence * (1 - sentiment_stability)` | Pure MiroFish metrics |

**Graceful degradation for formulas:**
- If TRIBE unavailable: Attention, Conversion = N/A; Virality/Backlash/Memory use only MiroFish components; Audience fit = N/A
- If MiroFish unavailable: Virality/Backlash/Memory/Polarization = N/A; Attention, Conversion, Audience fit use only TRIBE components

## SQLite Schema Design

Based on D-07 through D-10:

```sql
-- Campaign table
CREATE TABLE campaigns (
    id TEXT PRIMARY KEY,                    -- UUID
    status TEXT NOT NULL DEFAULT 'pending', -- pending, running, completed, failed
    seed_content TEXT NOT NULL,
    prediction_question TEXT NOT NULL,
    demographic TEXT NOT NULL,
    demographic_custom TEXT,
    agent_count INTEGER NOT NULL DEFAULT 40,
    max_iterations INTEGER NOT NULL DEFAULT 4,
    thresholds TEXT,                        -- JSON: {"attention_score": 70, ...}
    constraints TEXT,                       -- Brand guidelines
    baseline_content TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    error TEXT                              -- Error message if failed
);

-- Iteration table (one row per variant per iteration)
CREATE TABLE iterations (
    id TEXT PRIMARY KEY,                    -- UUID
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    iteration_number INTEGER NOT NULL,
    variant_id TEXT NOT NULL,               -- e.g., "v1_trust_first"
    variant_content TEXT NOT NULL,
    variant_strategy TEXT,
    tribe_scores TEXT,                      -- JSON: 7 dimension scores
    mirofish_metrics TEXT,                  -- JSON: 8 simulation metrics
    composite_scores TEXT,                  -- JSON: 7 composite scores
    created_at TEXT NOT NULL,
    UNIQUE(campaign_id, iteration_number, variant_id)
);

-- Analysis table (one per iteration)
CREATE TABLE analyses (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    iteration_number INTEGER NOT NULL,
    analysis_json TEXT NOT NULL,            -- Full Claude Opus analysis
    system_availability TEXT,               -- JSON: which systems were available
    created_at TEXT NOT NULL,
    UNIQUE(campaign_id, iteration_number)
);
```

## Common Pitfalls

### Pitfall 1: MiroFish Ontology/Graph Build Timeout
**What goes wrong:** MiroFish graph build uses LLM calls under the hood (ontology generation, entity extraction). On complex content, this can take 2-5 minutes.
**Why it happens:** MiroFish was designed for interactive use with a UI polling status, not programmatic pipeline use.
**How to avoid:** Set generous timeouts on httpx calls to MiroFish (300s). Implement polling with exponential backoff (start 2s, max 10s) for background tasks. Set a hard ceiling (e.g., 5 minutes per graph build) and fail gracefully.
**Warning signs:** Hung pipeline, no progress updates for minutes.

### Pitfall 2: MiroFish Multipart Form Data for Ontology Generation
**What goes wrong:** The `/api/graph/ontology/generate` endpoint expects multipart/form-data with actual file uploads, not JSON. Sending the content as JSON will fail.
**Why it happens:** MiroFish was designed for file upload workflows, not programmatic text input.
**How to avoid:** Use httpx's `files` parameter to send content as an in-memory file upload:
```python
files = {"files": ("content.txt", content_bytes, "text/plain")}
data = {"simulation_requirement": requirement, "project_name": campaign_id}
response = await client.post("/api/graph/ontology/generate", files=files, data=data)
```
**Warning signs:** 400 errors from MiroFish "Please upload at least one document file".

### Pitfall 3: SQLite Write Contention in Async Context
**What goes wrong:** Multiple async tasks try to write to SQLite simultaneously, causing "database is locked" errors.
**Why it happens:** SQLite only allows one writer at a time. With WAL mode, reads can happen concurrently with one writer, but multiple writers will contend.
**How to avoid:** Use WAL journal mode (`PRAGMA journal_mode=WAL`). Ensure all writes go through a single connection. For POC single-user, this is sufficient.
**Warning signs:** "database is locked" errors during pipeline execution.

### Pitfall 4: MiroFish Graph Rebuild Per Variant (D-04)
**What goes wrong:** Each variant needs its own MiroFish simulation. D-04 states the graph is rebuilt per variant to avoid Neo4j conflicts. This means the full MiroFish flow (ontology -> build -> create -> prepare -> start -> poll) runs N times (3 times for 3 variants).
**Why it happens:** Neo4j graph state from one variant would contaminate the next variant's simulation.
**How to avoid:** Accept the sequential overhead. Estimate ~2-4 minutes per variant for the full MiroFish flow. For 3 variants that is 6-12 minutes of MiroFish time alone. The campaign runner must be designed for this latency.
**Warning signs:** Pipeline exceeding the 20-minute budget for a full campaign.

### Pitfall 5: Composite Score Normalization
**What goes wrong:** Raw composite formula outputs are not on a 0-100 scale. For example, `memory_encoding * emotional_resonance * sentiment_stability` could produce values in the thousands.
**Why it happens:** The formulas in Results.md are conceptual -- they show the relationships, not the final scaling.
**How to avoid:** After computing raw formula outputs, normalize each to 0-100. For multiplicative formulas, apply a scaling factor (e.g., divide by 100 for products of two 0-100 values, divide by 10000 for products of three, etc.). Document the normalization approach clearly.
**Warning signs:** Composite scores appearing as 5000+ or 0.005 instead of the expected 0-100 range.

### Pitfall 6: MiroFish Metric Extraction Requires Inference
**What goes wrong:** Expecting MiroFish to return the 8 metrics directly -- it does not.
**Why it happens:** MiroFish returns raw actions (posts, comments, follows) not aggregated metrics.
**How to avoid:** Build a metrics computation module in `mirofish_runner.py`. Some metrics (organic_shares, peak_virality_cycle) are straightforward counts. Others (sentiment_trajectory, coalition_formation) require computation from raw data. Sentiment analysis of individual posts may require a lightweight Claude Haiku call or a simple heuristic (e.g., keyword-based positive/negative classification from the post content and reactions).
**Warning signs:** Empty or nonsensical MiroFish metrics in the composite scores.

## Code Examples

### Campaign Create Schema (Pydantic v2)
```python
# Source: Tech spec CampaignCreate + D-10
from pydantic import BaseModel, Field

class CampaignCreateRequest(BaseModel):
    seed_content: str = Field(..., min_length=100, max_length=25000)
    prediction_question: str = Field(..., min_length=10)
    demographic: str = Field(...)  # Preset key or "custom"
    demographic_custom: str | None = None
    agent_count: int = Field(default=40, ge=20, le=200)
    max_iterations: int = Field(default=4, ge=1, le=10)
    thresholds: dict[str, float] | None = None
    constraints: str | None = None
    auto_start: bool = Field(default=True)  # D-10: optionally starts
```

### TRIBE Client Pattern
```python
# Source: tribe_scorer/main.py endpoint schemas
import httpx
from typing import Any

class TribeClient:
    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get("/api/health", timeout=10.0)
            data = resp.json()
            return data.get("status") == "ok"
        except Exception:
            return False

    async def score_text(self, text: str) -> dict[str, float] | None:
        try:
            resp = await self._client.post(
                "/api/score",
                json={"text": text},
                timeout=120.0,  # GPU inference can be slow
            )
            resp.raise_for_status()
            data = resp.json()
            # Return 7 dimensions, exclude inference_time_ms
            return {k: v for k, v in data.items() if k != "inference_time_ms"}
        except Exception as e:
            logger.warning("TRIBE scoring failed: %s", e)
            return None
```

### aiosqlite Schema Init
```python
# Source: aiosqlite docs + D-07/D-08/D-09
import aiosqlite

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    seed_content TEXT NOT NULL,
    prediction_question TEXT NOT NULL,
    demographic TEXT NOT NULL,
    demographic_custom TEXT,
    agent_count INTEGER NOT NULL DEFAULT 40,
    max_iterations INTEGER NOT NULL DEFAULT 4,
    thresholds TEXT,
    constraints TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS iterations (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    iteration_number INTEGER NOT NULL,
    variant_id TEXT NOT NULL,
    variant_content TEXT NOT NULL,
    variant_strategy TEXT,
    tribe_scores TEXT,
    mirofish_metrics TEXT,
    composite_scores TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(campaign_id, iteration_number, variant_id)
);

CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    iteration_number INTEGER NOT NULL,
    analysis_json TEXT NOT NULL,
    system_availability TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(campaign_id, iteration_number)
);
"""

async def init_database(path: str) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.executescript(SCHEMA_SQL)
    await conn.commit()
    return conn
```

### Composite Scorer Pattern
```python
# Source: Results.md section 3.2 + demographic_profiles.py
def compute_composite_scores(
    tribe: dict[str, float] | None,
    mirofish: dict[str, Any] | None,
    cognitive_weights: dict[str, float],
    agent_count: int,
) -> dict[str, float | None]:
    scores = {}

    # Attention score (TRIBE only)
    if tribe:
        scores["attention_score"] = round(
            0.6 * tribe["attention_capture"] + 0.4 * tribe["emotional_resonance"], 1
        )
    else:
        scores["attention_score"] = None

    # Virality potential (cross-system)
    if tribe and mirofish:
        share_rate = mirofish["organic_shares"] / max(agent_count, 1) * 100
        raw = (tribe["emotional_resonance"] * tribe["social_relevance"]
               / max(tribe["cognitive_load"], 10) * share_rate)
        scores["virality_potential"] = round(min(raw / 100, 100), 1)  # normalize
    else:
        scores["virality_potential"] = None

    # ... similar for remaining 5 formulas
    return scores
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `lifespan` asynccontextmanager | FastAPI 0.109+ | Lifespan is the recommended approach; on_event still works but deprecated |
| sqlite3 (sync) | aiosqlite (async) | Stable since 2023 | Non-blocking DB access in async FastAPI |
| requests (sync) | httpx (async) | Mature since 2024 | Native async HTTP client with similar API to requests |

**Deprecated/outdated:**
- FastAPI `@app.on_event("startup")` / `@app.on_event("shutdown")`: Still functional but officially superseded by `lifespan` parameter

## Open Questions

1. **MiroFish sentiment computation**
   - What we know: MiroFish actions include posts and comments with text content. Sentiment must be derived from this text.
   - What's unclear: Whether to use Claude Haiku for sentiment analysis of each post (accurate but slow) or a simple heuristic (fast but less accurate). For a POC with potentially hundreds of posts per simulation, Haiku calls could add significant latency and cost.
   - Recommendation: Use a keyword/reaction-based heuristic for sentiment computation in Phase 5. If sentiment quality is insufficient, upgrade to Haiku calls in a future iteration.

2. **MiroFish coalition detection**
   - What we know: Coalition formation requires analyzing agent interaction patterns (who follows/agrees with whom).
   - What's unclear: Exact algorithm for detecting coalitions from raw action data.
   - Recommendation: Use a simple clustering approach -- group agents by whether they shared (pro) or counter-narrated (anti) the content. Coalition count = number of distinct groups. Stability = consistency of grouping over simulation rounds.

3. **Composite score normalization constants**
   - What we know: The formulas in Results.md are conceptual. Products of 0-100 values need rescaling.
   - What's unclear: The exact scaling factors that produce "intuitive" 0-100 composite scores.
   - Recommendation: Implement initial scaling factors, then calibrate against the 5 demo scenarios in Phase 9 validation.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All orchestrator code | Yes | 3.14.3 | -- |
| FastAPI | ORCH-01 | Yes | 0.128.1 | -- |
| aiosqlite | ORCH-02 | Yes | 0.22.1 | -- |
| httpx | ORCH-07 | Yes | 0.28.1 | -- |
| Pydantic | ORCH-03 | Yes | 2.12.5 | -- |
| anthropic SDK | ORCH-08, ORCH-12 | Yes | 0.86.0 | -- |
| pytest | Testing | Yes | 9.0.2 | -- |
| pytest-asyncio | Async testing | No | -- | Install: `pip install pytest-asyncio` |
| TRIBE v2 service | ORCH-09 | Runtime* | Port 8001 | Graceful degradation (D-05) |
| MiroFish service | ORCH-10 | Runtime* | Port 5000 | Graceful degradation (D-05) |
| Neo4j | MiroFish dependency | Runtime* | Docker | MiroFish handles this |
| SQLite | ORCH-02 | Yes | Built-in | -- |

*Runtime dependencies checked at campaign execution time, not build time. Graceful degradation per D-05.

**Missing dependencies with no fallback:** None (all blocking deps installed)

**Missing dependencies with fallback:**
- pytest-asyncio: Easy install, not blocking

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio (to install) |
| Config file | none -- see Wave 0 |
| Quick run command | `pytest orchestrator/tests/ -x -q` |
| Full suite command | `pytest orchestrator/tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ORCH-01 | FastAPI app starts with CORS and lifespan | unit | `pytest orchestrator/tests/test_app.py -x` | Wave 0 |
| ORCH-02 | SQLite schema creates tables correctly | unit | `pytest orchestrator/tests/test_storage.py::test_schema_init -x` | Wave 0 |
| ORCH-03 | Pydantic schemas validate correctly | unit | `pytest orchestrator/tests/test_schemas.py -x` | Wave 0 |
| ORCH-04 | Campaign CRUD endpoints work | integration | `pytest orchestrator/tests/test_campaigns.py -x` | Wave 0 |
| ORCH-05 | Health endpoint pings downstream services | unit | `pytest orchestrator/tests/test_health.py -x` | Wave 0 |
| ORCH-06 | Demographics endpoint returns presets | unit | `pytest orchestrator/tests/test_health.py::test_demographics -x` | Wave 0 |
| ORCH-07 | HTTP clients handle success/failure | unit | `pytest orchestrator/tests/test_clients.py -x` | Wave 0 |
| ORCH-08 | Variant generator produces N variants | unit (mock) | `pytest orchestrator/tests/test_variant_generator.py -x` | Wave 0 |
| ORCH-09 | TRIBE scoring pipeline processes variants | unit (mock) | `pytest orchestrator/tests/test_tribe_scorer.py -x` | Wave 0 |
| ORCH-10 | MiroFish pipeline runs full workflow | unit (mock) | `pytest orchestrator/tests/test_mirofish_runner.py -x` | Wave 0 |
| ORCH-11 | Composite scorer computes all 7 formulas | unit | `pytest orchestrator/tests/test_composite_scorer.py -x` | Wave 0 |
| ORCH-12 | Result analyzer calls Opus with correct data | unit (mock) | `pytest orchestrator/tests/test_result_analyzer.py -x` | Wave 0 |
| ORCH-13 | Campaign runner wires all components | integration (mock) | `pytest orchestrator/tests/test_campaign_runner.py -x` | Wave 0 |
| ORCH-14 | CLI produces end-to-end results | smoke (mock) | `pytest orchestrator/tests/test_cli.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest orchestrator/tests/ -x -q`
- **Per wave merge:** `pytest orchestrator/tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `orchestrator/tests/__init__.py` -- package init
- [ ] `orchestrator/tests/conftest.py` -- shared fixtures (mock DB, mock clients, mock Claude)
- [ ] `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` -- test config with asyncio_mode = "auto"
- [ ] Framework install: `pip install pytest-asyncio`

## Sources

### Primary (HIGH confidence)
- `orchestrator/config.py` -- Pydantic Settings with all service URLs, ports, defaults
- `orchestrator/clients/claude_client.py` -- Full async Claude client implementation
- `orchestrator/prompts/*.py` -- All 5 prompt template modules
- `tribe_scorer/main.py` -- TRIBE v2 FastAPI service with exact endpoint schemas
- `mirofish/backend/app/api/*.py` -- MiroFish Flask API with all route definitions
- `mirofish/backend/app/__init__.py` -- Blueprint route prefixes (/api/graph, /api/simulation, /api/report)
- `docs/Results.md` section 3.2 -- All 7 composite score formulas
- `docs/Application_Technical_Spec.md` section 2.1 -- Orchestrator directory structure and API design

### Secondary (MEDIUM confidence)
- [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/) -- Official docs on asynccontextmanager lifespan
- [aiosqlite GitHub](https://github.com/omnilib/aiosqlite) -- Async SQLite bridge documentation
- [httpx AsyncClient](https://www.python-httpx.org/) -- Async HTTP client for service calls

### Tertiary (LOW confidence)
- MiroFish metric extraction approach -- Based on analysis of MiroFish's raw data endpoints; the exact computation logic for all 8 metrics needs validation against actual simulation output
- Composite score normalization constants -- Based on mathematical analysis of formulas; calibration against real data needed

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages already installed, versions verified from pip
- Architecture: HIGH -- based on existing codebase analysis and official tech spec
- Integration surface (TRIBE): HIGH -- simple REST API, fully documented in main.py
- Integration surface (MiroFish): MEDIUM -- complex multi-step workflow, metric extraction needs validation
- Composite scoring: MEDIUM -- formulas documented but normalization needs calibration
- Pitfalls: HIGH -- derived from actual code analysis of downstream services

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable domain -- no fast-moving external dependencies)
