# Phase 5: Orchestrator Integration Pipeline - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire TRIBE v2, MiroFish, and Claude Client into a single-iteration campaign pipeline. Deliver a FastAPI orchestrator on port 8000 with campaign CRUD, system health checking, variant generation, neural scoring, social simulation, composite scoring, and cross-system analysis — producing complete results for one campaign iteration via API or CLI.

Requirements: ORCH-01 through ORCH-14.

</domain>

<decisions>
## Implementation Decisions

### Variant-to-Simulation Flow
- **D-01:** Generate **3 content variants** per campaign iteration using Claude Haiku.
- **D-02:** All 3 variants are scored by TRIBE v2 — **no early elimination**. All 3 also go to MiroFish simulation.
- **D-03:** TRIBE v2 scoring is **sequential** (one variant at a time) to avoid GPU contention on the single RTX 5070 Ti.
- **D-04:** MiroFish simulations are **sequential** (one variant at a time) to avoid Neo4j graph DB conflicts. Graph is rebuilt per variant.

### Graceful Degradation
- **D-05:** Follow the requirement as originally specified: **graceful degradation with partial data**. When TRIBE or MiroFish is unavailable, skip the unavailable system, warn the user, and note the gap in results. Composite scores that depend on missing inputs show as N/A.
- **D-06:** Health detection approach is **Claude's discretion** — pre-flight check or fail-on-first-call, whichever is more robust.

### Campaign Data Model
- **D-07:** **Full persistence** in SQLite — store everything: campaign config, all variant texts, all raw TRIBE scores, all raw MiroFish metrics, composite scores, Claude analysis text, per iteration. The UI can reconstruct the full picture from the DB alone.
- **D-08:** TRIBE scores (7 dims), MiroFish metrics (8 fields), and composite scores (7 formulas) stored as **JSON text columns**. Flexible, easy to evolve, queryable via json_extract() if needed.
- **D-09:** Campaigns have an explicit **status column** (pending, running, completed, failed) updated as the pipeline progresses. Enables UI status badges and future resume/retry logic.
- **D-10:** Campaign creation via a **single POST** with all config (seed_content, prediction_question, demographic, agent_count, max_iterations, thresholds). One call creates and optionally starts.

### Claude's Discretion
- Health check implementation approach (D-06) — pre-flight vs fail-on-first-call
- CLI execution interface design — not discussed, Claude has flexibility on the CLI shape

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Composite Score Formulas
- `docs/Results.md` §3.2 — All 7 composite score formulas (attention, virality, backlash, memory, conversion, audience fit, polarization) with exact calculation definitions

### Technical Specification
- `docs/Application_Technical_Spec.md` — Full technical specification for the platform

### Existing Orchestrator Code
- `orchestrator/config.py` — Pydantic settings with all service URLs, database path, simulation defaults, LLM fallback config
- `orchestrator/clients/claude_client.py` — Complete Claude client (Opus/Haiku/JSON modes, retry with backoff, credential refresh)
- `orchestrator/prompts/variant_generation.py` — Variant generation prompt templates
- `orchestrator/prompts/result_analysis.py` — Cross-system analysis prompt templates (requires both TRIBE + MiroFish references)
- `orchestrator/prompts/report_verdict.py` — Report verdict prompt templates
- `orchestrator/prompts/report_psychology.py` — Mass psychology prompt templates
- `orchestrator/prompts/demographic_profiles.py` — 6 demographic presets with agent persona configs

### Downstream Services
- `tribe_scorer/main.py` — TRIBE v2 FastAPI service (port 8001, endpoints: /api/score, /api/score/batch, /api/health)
- `mirofish/backend/` — MiroFish Flask backend (port 5000) with graph build and simulation APIs

### Project Requirements
- `.planning/REQUIREMENTS.md` — ORCH-01 through ORCH-14 requirement definitions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **ClaudeClient** (`orchestrator/clients/claude_client.py`): Full async client with call_opus, call_haiku, call_opus_json, call_haiku_json — ready for orchestrator consumption
- **Settings** (`orchestrator/config.py`): All service URLs, database path, simulation defaults already configured via Pydantic BaseSettings
- **Prompt templates** (`orchestrator/prompts/`): Variant generation, result analysis, report verdict, report psychology, demographic profiles — all ready
- **Demographic profiles** (`orchestrator/prompts/demographic_profiles.py`): 6 presets with full persona descriptions

### Established Patterns
- **Pydantic for config**: Settings loaded from .env with validation and type coercion
- **Async pattern**: ClaudeClient is fully async (AsyncAnthropic SDK) — orchestrator should follow async patterns throughout
- **JSON extraction**: `_extract_json_from_text()` handles markdown fences and bare JSON — reusable for parsing downstream service responses
- **Credential handling**: OAuth token fallback from ~/.claude/.credentials.json with 401 refresh

### Integration Points
- **api/**: Empty — needs FastAPI app with CORS, campaign CRUD routes, health endpoint, demographics endpoint
- **engine/**: Empty — needs variant generator, TRIBE scoring pipeline, MiroFish simulation pipeline, composite scorer, result analyzer, campaign runner
- **storage/**: Empty — needs SQLite schema, campaign/iteration CRUD operations
- **Port 8000**: Configured in settings as `orchestrator_port`
- **CORS origin**: Needs `localhost:5173` for UI (Vite dev server)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-orchestrator-integration-pipeline*
*Context gathered: 2026-03-29*
