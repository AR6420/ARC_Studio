# Phase 7: Report Generation - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Generate 4-layer reports from campaign results: Layer 1 verdict (plain English), Layer 2 scorecard (structured JSON), Layer 3 deep analysis (all raw data), Layer 4 mass psychology (general + technical toggle). Add JSON and Markdown export endpoints.

Requirements: RPT-01 through RPT-07.

</domain>

<decisions>
## Implementation Decisions

### Report Structure
- **D-01:** Store each report layer as a **separate JSON field** in the analysis table — UI can fetch layers independently.
- **D-02:** Generate reports **after the final iteration** completes (not per-iteration). Single report generation call using Claude Opus.
- **D-03:** Mass psychology: store **both general + technical** modes in the same report record. UI toggles display, no separate API calls.

### Export
- **D-04:** JSON export includes **full campaign data** — all iterations, all scores, all analysis layers. Complete audit trail.
- **D-05:** Markdown export is a **readable summary with all 4 layers** formatted as sections with headers.

### Claude's Discretion
- Report generation prompt engineering (quality of Layer 1 verdict, Layer 4 psychology)
- Exact JSON schema for Layer 2 scorecard
- How to structure the export API endpoints (separate routes vs query params)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Report Specifications
- `docs/Results.md` §3.1 — All 4 output layers with quality standards, word counts, content requirements
- `docs/Results.md` §4.2 — Output quality standards (verdict word count, scorecard color coding, psychology theory count)

### Existing Report Prompts
- `orchestrator/prompts/report_verdict.py` — Layer 1 verdict prompt template (already built in Phase 4)
- `orchestrator/prompts/report_psychology.py` — Layer 4 mass psychology prompt template (already built in Phase 4)

### Pipeline Code
- `orchestrator/engine/campaign_runner.py` — run_campaign() where report generation should be triggered
- `orchestrator/engine/result_analyzer.py` — Claude Opus analysis (can be extended for report generation)
- `orchestrator/storage/campaign_store.py` — save_analysis() for persisting report layers
- `orchestrator/api/schemas.py` — Response models to extend with report fields

### Project Requirements
- `.planning/REQUIREMENTS.md` — RPT-01 through RPT-07 requirement definitions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **report_verdict.py** prompt template — Layer 1 verdict generation ready
- **report_psychology.py** prompt template — Layer 4 mass psychology ready (general + technical)
- **result_analyzer.py** — Claude Opus calling pattern (call_opus_json) reusable for report generation
- **campaign_store.save_analysis()** — Already persists analysis text, can be extended for structured layers

### Established Patterns
- Async Claude Opus calls via ClaudeClient.call_opus / call_opus_json
- JSON persistence in SQLite with json_extract() capability
- FastAPI router pattern with Pydantic response models

### Integration Points
- **campaign_runner.py**: After final iteration, call report generator
- **api/campaigns.py**: Add export endpoints for JSON/Markdown download
- **api/schemas.py**: Add report layer response models

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

*Phase: 07-report-generation*
*Context gathered: 2026-03-29*
