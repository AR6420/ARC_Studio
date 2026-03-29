# Phase 6: Optimization Loop - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Add multi-iteration optimization to the existing single-iteration campaign pipeline. The system iterates on content variants, passing previous results to variant generation, checking user-defined thresholds, detecting convergence (<5% improvement for 2 consecutive iterations), and streaming real-time progress via SSE. Includes a time estimation endpoint.

Requirements: OPT-01 through OPT-07.

</domain>

<decisions>
## Implementation Decisions

### Iteration Feedback Strategy
- **D-01:** Pass **full previous iteration results** (all scores + Claude Opus analysis) to variant generation prompt — gives Haiku maximum context for improvement.
- **D-02:** Generate **3 new variants** each iteration (consistent with Phase 5 D-01 for time budget).
- **D-03:** **Replace all variants** each iteration — do not carry forward best variants. Simpler, avoids variant-count growth.
- **D-04:** Claude Haiku prompt **includes specific improvement instructions** extracted from the Opus analysis — closes the neural→social→cognitive feedback loop.

### Convergence & Threshold Detection
- **D-05:** Convergence threshold: **<5% improvement for 2 consecutive iterations** (per spec OPT-03).
- **D-06:** Threshold comparison: compare **top variant's composite scores** against user-defined targets (not average across all variants).
- **D-07:** Early stop requires **all user-enabled thresholds** to be met (not just any single one).
- **D-08:** Max iterations is a **hard cap** from campaign config (default 4 per Phase 5 settings).

### SSE Progress Streaming
- **D-09:** SSE endpoint at **GET /api/campaigns/{id}/progress** — server-sent events, not WebSocket.
- **D-10:** Event granularity: **per-step within each iteration** (generating, scoring, simulating, analyzing) — not just per-iteration.
- **D-11:** ETA calculation: **formula-based** (steps remaining × avg step duration) **refined at runtime** as actual durations are observed.
- **D-12:** Time estimate endpoint: **POST /api/estimate** returns pre-run prediction (per OPT-05).

### Claude's Discretion
- SSE event format (JSON structure, event types naming)
- Background task management for async campaign execution
- How to wire SSE into existing FastAPI app (asyncio.Queue, or broadcast pattern)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Pipeline Code
- `orchestrator/engine/campaign_runner.py` — CampaignRunner.run_single_iteration() to be extended to multi-iteration
- `orchestrator/engine/variant_generator.py` — VariantGenerator needs iteration feedback parameter
- `orchestrator/prompts/variant_generation.py` — Prompt template needs previous results injection
- `orchestrator/engine/composite_scorer.py` — compute_composite_scores() for threshold checking
- `orchestrator/api/__init__.py` — FastAPI app to add SSE endpoint
- `orchestrator/api/campaigns.py` — Campaign endpoints, auto_start path needs SSE wiring
- `orchestrator/config.py` — Settings with default_max_iterations=4

### Score Formulas
- `docs/Results.md` §3.2 — Composite score formulas (for threshold comparison)
- `docs/Results.md` §4.3 — Performance standards (<=5min/iteration, <=20min total)

### Project Requirements
- `.planning/REQUIREMENTS.md` — OPT-01 through OPT-07 requirement definitions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **CampaignRunner** (`orchestrator/engine/campaign_runner.py`): Already wires all 5 pipeline steps for single iteration — extend to loop
- **CampaignStore** (`orchestrator/storage/campaign_store.py`): save_iteration() already persists per-iteration data
- **CompositeScorer** (`orchestrator/engine/composite_scorer.py`): compute_composite_scores() returns dict ready for threshold comparison
- **Settings** (`orchestrator/config.py`): default_max_iterations=4 already configured

### Established Patterns
- **Async throughout**: All engine components are async — SSE can use asyncio natively
- **Dependency injection**: Components receive clients/stores via constructor — consistent pattern for new modules
- **JSON persistence**: Score data stored as JSON columns — iteration comparison can use same format

### Integration Points
- **campaign_runner.py**: Main extension point — add run_campaign() wrapping run_single_iteration() in a loop
- **api/campaigns.py**: POST endpoint needs to trigger background execution
- **api/__init__.py**: Add SSE route for progress streaming
- **variant_generation.py**: Prompt template needs previous_results parameter

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

*Phase: 06-optimization-loop*
*Context gathered: 2026-03-29*
