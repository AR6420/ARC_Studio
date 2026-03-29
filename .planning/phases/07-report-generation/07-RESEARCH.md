# Phase 7: Report Generation - Research

**Researched:** 2026-03-29
**Domain:** Report generation, LLM-driven content synthesis, JSON/Markdown export
**Confidence:** HIGH

## Summary

Phase 7 adds a report generation layer that runs after the final iteration of a campaign. The system already has prompt templates for Layer 1 (verdict) and Layer 4 (mass psychology) built in Phase 4, a working `ClaudeClient` with `call_opus` and `call_opus_json` methods, and an established pattern of persisting JSON data in SQLite via `CampaignStore`. The core work is: (1) building a `ReportGenerator` engine class that orchestrates 3 Claude Opus calls (verdict, scorecard, psychology), (2) assembling Layer 3 deep analysis from existing stored data without an LLM call, (3) adding a `reports` table or extending the existing `analyses` table to store report layers, (4) adding API endpoints for report retrieval and JSON/Markdown export, and (5) hooking report generation into `run_campaign()` after the loop completes.

The existing codebase is well-structured with dependency injection, async patterns, and Pydantic response models. Report generation follows the exact same patterns. The main risks are: Opus API cost (3 sequential calls per campaign adds to the 4-8 budget), prompt quality for the scorecard JSON format, and ensuring Markdown export is clean and complete.

**Primary recommendation:** Build a `ReportGenerator` class in `orchestrator/engine/report_generator.py` that takes `ClaudeClient` via constructor injection, uses the existing prompt templates, and is called from `CampaignRunner.run_campaign()` after the iteration loop. Store report layers as separate JSON fields in a new `reports` table. Add 3 new API endpoints: GET report, GET export/json, GET export/markdown.

## Project Constraints (from CLAUDE.md)

- Hardware: Single RTX 5070 Ti GPU shared between TRIBE v2 and Ollama embeddings
- API: Claude API rate limits -- Haiku batched, Opus sequential (4-8 calls/campaign)
- Performance: Full campaign (40 agents, 4 iterations) must complete in <= 20 minutes
- Scope: Phase 1 POC only -- no auth, no HTTPS, no multi-user
- GSD Workflow: Must use GSD commands for file changes

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Store each report layer as a separate JSON field in the analysis table -- UI can fetch layers independently.
- **D-02:** Generate reports after the final iteration completes (not per-iteration). Single report generation call using Claude Opus.
- **D-03:** Mass psychology: store both general + technical modes in the same report record. UI toggles display, no separate API calls.
- **D-04:** JSON export includes full campaign data -- all iterations, all scores, all analysis layers. Complete audit trail.
- **D-05:** Markdown export is a readable summary with all 4 layers formatted as sections with headers.

### Claude's Discretion
- Report generation prompt engineering (quality of Layer 1 verdict, Layer 4 psychology)
- Exact JSON schema for Layer 2 scorecard
- How to structure the export API endpoints (separate routes vs query params)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RPT-01 | Layer 1 Verdict -- plain English recommendation (100-400 words, no jargon) | Existing `report_verdict.py` prompt template with `REPORT_VERDICT_SYSTEM` and `build_report_verdict_prompt()` already built. Use `ClaudeClient.call_opus()` (plain text, not JSON). |
| RPT-02 | Layer 2 Scorecard -- composite scores, variant ranking, iteration trajectory as structured JSON | New prompt + `call_opus_json()`. Schema defined below in Architecture Patterns. Data sourced from `best_scores_history` and stored iteration records. |
| RPT-03 | Layer 3 Deep Analysis -- all raw scores, metrics, reasoning chains, per-iteration data | No LLM call needed. Assemble from existing DB data: all iteration records + all analysis records. Pure data aggregation. |
| RPT-04 | Layer 4 Mass Psychology General -- narrative prose about crowd dynamics (200-600 words) | Existing `report_psychology.py` with `MASS_PSYCHOLOGY_GENERAL_SYSTEM` and `build_mass_psychology_general_prompt()`. Use `ClaudeClient.call_opus()`. |
| RPT-05 | Layer 4 Mass Psychology Technical -- psychology theory references (>= 2 named theories) | Existing `report_psychology.py` with `MASS_PSYCHOLOGY_TECHNICAL_SYSTEM` and `build_mass_psychology_technical_prompt()`. Use `ClaudeClient.call_opus()`. |
| RPT-06 | JSON export of full campaign results | Assemble full campaign JSON from DB records matching Results.md section 7 schema. Serve via GET endpoint with `application/json` content type and Content-Disposition header. |
| RPT-07 | Markdown summary export | Template-based Markdown rendering of all 4 layers. Serve via GET endpoint with `text/markdown` content type and Content-Disposition header. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | 0.86.0 | Claude API calls for report generation | Already installed and used via ClaudeClient |
| pydantic | 2.12.5 | Report response models, JSON serialization | Already the schema standard for all API models |
| fastapi | 0.128.1 | Export endpoint routing | Already the API framework |
| aiosqlite | 0.22.1 | Report persistence | Already the DB layer |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 | Report generation tests | All new code needs tests |
| pytest-asyncio | 1.3.0 | Async test support | All async report generation tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom Markdown templates | Jinja2 templates | Jinja2 adds a dependency for simple string formatting. Python f-strings and string concatenation are sufficient for 4-section Markdown. |
| Separate reports table | Extend campaigns table | Separate table is cleaner (D-01 says separate fields); keeps campaign table lean. |

**Installation:**
No new packages needed. All dependencies are already installed.

## Architecture Patterns

### Recommended Project Structure
```
orchestrator/
  engine/
    report_generator.py    # NEW: ReportGenerator class
  prompts/
    report_verdict.py      # EXISTS: Layer 1 prompt
    report_psychology.py   # EXISTS: Layer 4 prompts
    report_scorecard.py    # NEW: Layer 2 scorecard prompt
  storage/
    campaign_store.py      # EXTEND: save_report(), get_report() methods
    database.py            # EXTEND: reports table in SCHEMA_SQL
  api/
    reports.py             # NEW: Report retrieval + export endpoints
    schemas.py             # EXTEND: Report response models
  tests/
    test_report_generator.py  # NEW
    test_reports_api.py       # NEW
```

### Pattern 1: ReportGenerator Class (follows ResultAnalyzer pattern)
**What:** A new engine class that takes ClaudeClient via constructor injection, calls Opus for each report layer, and returns a structured report dict.
**When to use:** After the campaign iteration loop completes in `run_campaign()`.
**Example:**
```python
# Source: Follows existing ResultAnalyzer pattern in orchestrator/engine/result_analyzer.py
class ReportGenerator:
    def __init__(self, claude_client: ClaudeClient):
        self._claude = claude_client

    async def generate_report(
        self,
        campaign: CampaignResponse,
        all_iterations: list[IterationRecord],
        all_analyses: list[AnalysisRecord],
        best_scores_history: list[dict],
        stop_reason: str,
    ) -> dict[str, Any]:
        """Generate all 4 report layers. Returns dict with layer keys."""
        # Layer 1: Verdict (call_opus - plain text)
        verdict = await self._generate_verdict(...)
        # Layer 2: Scorecard (call_opus_json - structured JSON)
        scorecard = await self._generate_scorecard(...)
        # Layer 3: Deep analysis (pure data aggregation, no LLM call)
        deep_analysis = self._assemble_deep_analysis(...)
        # Layer 4: Mass psychology (call_opus - both modes)
        psych_general = await self._generate_psychology_general(...)
        psych_technical = await self._generate_psychology_technical(...)

        return {
            "verdict": verdict,
            "scorecard": scorecard,
            "deep_analysis": deep_analysis,
            "mass_psychology_general": psych_general,
            "mass_psychology_technical": psych_technical,
        }
```

### Pattern 2: Layer 2 Scorecard JSON Schema
**What:** The scorecard structured JSON that Claude Opus generates.
**When to use:** RPT-02 implementation.
**Example:**
```python
# Layer 2 scorecard schema for call_opus_json
SCORECARD_SCHEMA = {
    "winning_variant_id": "str",
    "variants": [
        {
            "variant_id": "str",
            "rank": "int",
            "strategy": "str",
            "composite_scores": {
                "attention_score": "float 0-100",
                "virality_potential": "float 0-100",
                "backlash_risk": "float 0-100",
                "memory_durability": "float 0-100",
                "conversion_potential": "float 0-100",
                "audience_fit": "float 0-100",
                "polarization_index": "float 0-100",
            },
            "color_coding": {
                "attention_score": "green|amber|red",  # >=70 green, 40-69 amber, <40 red
                # backlash_risk and polarization_index inverted
            },
        }
    ],
    "iteration_trajectory": [
        {
            "iteration": "int",
            "best_scores": {"attention_score": "float", ...},
        }
    ],
    "thresholds_status": {
        "all_met": "bool",
        "per_threshold": {"metric_name": "bool"},
    },
    "summary": "str (2-3 sentence overview)",
}
```

### Pattern 3: Report Storage Schema (new reports table)
**What:** Database table and Pydantic model for persisting report layers.
**When to use:** D-01 compliance -- separate JSON fields for each layer.
**Example:**
```sql
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL UNIQUE REFERENCES campaigns(id) ON DELETE CASCADE,
    verdict TEXT,                      -- Layer 1: plain text string
    scorecard TEXT,                    -- Layer 2: JSON string
    deep_analysis TEXT,                -- Layer 3: JSON string
    mass_psychology_general TEXT,      -- Layer 4 general: plain text string
    mass_psychology_technical TEXT,    -- Layer 4 technical: plain text string
    created_at TEXT NOT NULL
);
```

### Pattern 4: Export Endpoints
**What:** API routes for JSON and Markdown export with download headers.
**When to use:** RPT-06, RPT-07 implementation.
**Example:**
```python
# Source: Follows existing campaigns.py router pattern

# Recommendation: Separate routes (cleaner than query params)
@router.get("/campaigns/{campaign_id}/report")
async def get_report(request: Request, campaign_id: str):
    """Get report layers for a campaign (for UI display)."""
    ...

@router.get("/campaigns/{campaign_id}/export/json")
async def export_json(request: Request, campaign_id: str):
    """Full campaign JSON export (RPT-06). Content-Disposition: attachment."""
    ...

@router.get("/campaigns/{campaign_id}/export/markdown")
async def export_markdown(request: Request, campaign_id: str):
    """Markdown summary export (RPT-07). Content-Disposition: attachment."""
    ...
```

### Pattern 5: Hook into run_campaign()
**What:** Add report generation step after the iteration loop in `CampaignRunner.run_campaign()`.
**When to use:** D-02 compliance -- generate after final iteration.
**Example:**
```python
# In CampaignRunner.run_campaign(), after the iteration loop:

# Generate final report (D-02: after final iteration)
if progress_callback:
    await progress_callback({
        "event": "report_generating",
        "campaign_id": campaign_id,
    })

report = await self._report_generator.generate_report(
    campaign=campaign,
    all_iterations=all_iteration_results,
    all_analyses=[r["analysis"] for r in all_iteration_results],
    best_scores_history=best_scores_history,
    stop_reason=stop_reason,
)

await self._store.save_report(campaign_id=campaign_id, report=report)
```

### Pattern 6: Markdown Export Template
**What:** The structure of the Markdown summary export.
**When to use:** RPT-07 implementation.
**Example:**
```markdown
# Campaign Report: {campaign_id}

**Generated:** {timestamp}
**Demographic:** {demographic}
**Iterations:** {iterations_completed} ({stop_reason})

---

## Verdict

{verdict_text}

---

## Scorecard

### Variant Ranking

| Rank | Variant | Attention | Virality | Backlash | Memory | Conversion | Audience Fit | Polarization |
|------|---------|-----------|----------|----------|--------|------------|--------------|--------------|
| 1    | v3      | 82        | 71       | 12       | 68     | 75         | 80           | 15           |

### Iteration Trajectory

| Iteration | Best Attention | Best Virality | ... |
|-----------|---------------|---------------|-----|

### Thresholds

{threshold_status}

---

## Deep Analysis

### Iteration {n}

#### Variant: {variant_id}

**TRIBE v2 Neural Scores:**
| Dimension | Score |
|-----------|-------|

**MiroFish Simulation Metrics:**
| Metric | Value |
|--------|-------|

**Composite Scores:**
| Score | Value |
|-------|-------|

**Claude Opus Analysis:**
{reasoning_chain}

---

## Mass Psychology

### General Narrative

{mass_psychology_general}

### Technical Analysis

{mass_psychology_technical}

---

*Exported from Nexus Sim*
```

### Anti-Patterns to Avoid
- **Generating reports per-iteration:** D-02 explicitly says generate after the final iteration. One report per campaign, not per iteration.
- **Making Layer 3 an LLM call:** Layer 3 is raw data aggregation. Every score, metric, and reasoning chain is already stored in the DB. Assembling it is a database query + formatting task, not an LLM call. Do not waste Opus budget on this.
- **Storing report as a single JSON blob:** D-01 says separate fields. The UI needs to fetch layers independently without deserializing the entire report.
- **Blocking on report generation before setting campaign status:** Generate the report, save it, then set status to completed. If report generation fails, the campaign data is still intact -- degrade gracefully (log error, set status to completed with a warning).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON extraction from LLM output | Custom JSON parser | `ClaudeClient.call_opus_json()` | Already handles markdown fences, bare JSON, retries on parse failure |
| Color coding logic (green/amber/red) | Ad-hoc threshold checks | Reusable `color_code_score()` utility | Consistency across scorecard and future UI. Inverted logic for backlash_risk and polarization_index. |
| Markdown table generation | Manual string building | Simple utility function | Markdown tables have alignment syntax that is easy to get wrong |
| File download headers | Manual Response construction | `fastapi.responses.Response` with Content-Disposition | FastAPI handles encoding, content-type correctly |

**Key insight:** The hard part of this phase is prompt engineering, not infrastructure. The codebase already has all the patterns needed (Claude client, DB storage, API routing, Pydantic models). Focus effort on prompt quality and data assembly logic.

## Common Pitfalls

### Pitfall 1: Opus API Budget Overrun
**What goes wrong:** 3 Opus calls for report generation (verdict, scorecard, psychology) added to 4 per-iteration analysis calls across 4 iterations = 19 total. The budget constraint says 4-8 Opus calls per campaign.
**Why it happens:** The constraint was written for the iteration loop alone. Report generation adds calls.
**How to avoid:** The existing per-iteration analysis calls already use Opus. The 3 report calls are additive but necessary. Two mitigations: (1) Layer 4 general and technical can potentially be combined into a single Opus call that returns both (saves 1 call), and (2) the scorecard can potentially be computed from data without Opus if the "summary" field is dropped or generated from a template. Minimum: 2 additional Opus calls (verdict + combined psychology). Maximum: 3 (verdict + scorecard + combined psychology).
**Warning signs:** API rate limit 429 errors during report generation. Watch for total campaign time exceeding 20 minutes.

### Pitfall 2: Scorecard Prompt Producing Invalid JSON
**What goes wrong:** Opus returns JSON that does not match the expected scorecard schema. Missing fields, wrong types, or extra prose.
**Why it happens:** JSON-mode prompts are fragile. The scorecard has a complex nested structure.
**How to avoid:** Use `call_opus_json()` which already retries once on parse failure. Additionally, validate the response against a Pydantic model (ScorecardReport) and fill in missing fields from DB data as a fallback. The scorecard data is already available in the DB -- Opus is mainly adding the ranking rationale and summary, not computing numbers.
**Warning signs:** ValueError exceptions from `call_opus_json()` during report generation.

### Pitfall 3: Assembling Deep Analysis from Multiple Iterations
**What goes wrong:** Layer 3 needs all iterations, all variants per iteration, all scores per variant, and all analysis chains. Getting the data structure right is fiddly.
**Why it happens:** Data is spread across iterations table (per-variant scores) and analyses table (per-iteration analysis). Need to group by iteration, then by variant within each iteration.
**How to avoid:** Use `CampaignStore.get_iterations()` (already groups by iteration_number) and `_get_analyses()`. Build a dict keyed by iteration_number. The existing `IterationRecord` and `AnalysisRecord` Pydantic models handle deserialization.
**Warning signs:** Missing data for early iterations. Verify all iteration numbers are present.

### Pitfall 4: Markdown Export Encoding Issues
**What goes wrong:** Special characters in variant content (pipes, asterisks, backticks) break Markdown table formatting.
**Why it happens:** User seed content and LLM-generated variants can contain any characters.
**How to avoid:** Escape pipe characters (`|` to `\|`) in table cell content. For prose sections (verdict, psychology), no escaping needed since they are not in tables.
**Warning signs:** Malformed Markdown tables in export. Test with content containing special characters.

### Pitfall 5: Report Generation Failure Crashing the Campaign
**What goes wrong:** If report generation throws an exception (API error, parse failure), the entire campaign fails and status is set to "failed" even though all iterations completed successfully.
**Why it happens:** Report generation is inside the try/except of run_campaign().
**How to avoid:** Wrap report generation in its own try/except within run_campaign(). If it fails, log the error, emit a warning event, but still set campaign status to "completed". The iteration data is already persisted. A missing report is recoverable; lost iteration data is not.
**Warning signs:** Campaign status "failed" when all iterations actually completed fine.

### Pitfall 6: Winner Selection Logic Duplication
**What goes wrong:** ReportGenerator picks a different "winning variant" than what the optimization loop tracks.
**Why it happens:** `find_best_composite()` in `optimization_loop.py` selects the best variant per iteration. The report needs the overall best across all iterations, or specifically the best from the final iteration.
**How to avoid:** Pass the `best_scores_history` and the final iteration's `composite_scores` to ReportGenerator. Use `find_best_composite()` on the final iteration's scores to identify the winner. Reuse the same function -- do not duplicate the ranking logic.
**Warning signs:** Report verdict discusses a different variant than what the scorecard ranks #1.

## Code Examples

### Verified: Calling Claude Opus for Plain Text (Verdict pattern)
```python
# Source: orchestrator/clients/claude_client.py + orchestrator/engine/result_analyzer.py
# call_opus returns raw text; call_opus_json returns parsed dict
verdict_text = await self._claude.call_opus(
    system=REPORT_VERDICT_SYSTEM,
    user=build_report_verdict_prompt(
        prediction_question=campaign.prediction_question,
        winning_variant=winning_variant_dict,
        all_variants=final_variants_list,
        thresholds_met=thresholds_met,
        iterations_run=iterations_completed,
    ),
    max_tokens=2048,
)
```

### Verified: Calling Claude Opus for JSON (Scorecard pattern)
```python
# Source: orchestrator/clients/claude_client.py
scorecard = await self._claude.call_opus_json(
    system=REPORT_SCORECARD_SYSTEM,
    user=build_report_scorecard_prompt(...),
    max_tokens=4096,
)
# call_opus_json automatically retries on parse failure
```

### Verified: Persisting JSON to SQLite
```python
# Source: orchestrator/storage/campaign_store.py (save_analysis pattern)
await self._db.conn.execute(
    """
    INSERT INTO reports
        (id, campaign_id, verdict, scorecard, deep_analysis,
         mass_psychology_general, mass_psychology_technical, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        report_id,
        campaign_id,
        verdict_text,  # plain text
        json.dumps(scorecard),  # JSON string
        json.dumps(deep_analysis),  # JSON string
        psych_general_text,  # plain text
        psych_technical_text,  # plain text
        _now_iso(),
    ),
)
await self._db.conn.commit()
```

### Verified: FastAPI File Download Response
```python
# Source: FastAPI docs pattern
from fastapi.responses import Response

@router.get("/campaigns/{campaign_id}/export/json")
async def export_json(request: Request, campaign_id: str):
    # Assemble full JSON from DB
    campaign_data = await _assemble_full_export(request, campaign_id)
    content = json.dumps(campaign_data, indent=2, default=str)
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="campaign_{campaign_id}.json"'
        },
    )

@router.get("/campaigns/{campaign_id}/export/markdown")
async def export_markdown(request: Request, campaign_id: str):
    md_content = await _render_markdown_report(request, campaign_id)
    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="campaign_{campaign_id}.md"'
        },
    )
```

### Verified: Color Coding Logic
```python
# Source: Results.md section 4.2
# green >= 70, amber 40-69, red < 40
# Inverted for backlash_risk and polarization_index (lower is better)
INVERTED_SCORES = {"backlash_risk", "polarization_index"}

def color_code_score(metric_name: str, value: float) -> str:
    if metric_name in INVERTED_SCORES:
        # Inverted: <30 is green, 30-59 amber, >=60 red
        if value < 30:
            return "green"
        elif value < 60:
            return "amber"
        else:
            return "red"
    else:
        if value >= 70:
            return "green"
        elif value >= 40:
            return "amber"
        else:
            return "red"
```

### Existing Prompt Template Example: Mass Psychology General
```python
# Source: orchestrator/prompts/report_psychology.py (already built)
# build_mass_psychology_general_prompt() takes:
#   campaign_brief, demographic_description, winning_variant,
#   all_variants, simulation_summary
# Returns formatted prompt string for MASS_PSYCHOLOGY_GENERAL_SYSTEM
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single monolithic report | 4-layer progressive disclosure | Project design | Each audience gets appropriate detail level |
| LLM generates all data | LLM for narrative, DB for data | Project design | Layer 3 uses stored data, not LLM hallucination |

**Deprecated/outdated:**
- None relevant. This phase uses established patterns already in the codebase.

## Open Questions

1. **Opus Call Budget**
   - What we know: Results.md says 4-8 Opus calls/campaign. The iteration loop uses 1 per iteration (up to 4). Report needs 2-3 more.
   - What's unclear: Whether 7 total Opus calls (4 iteration + 3 report) violates the spirit of the budget.
   - Recommendation: Combine psychology general + technical into a single Opus call that outputs both (system prompt asks for two sections). This brings report calls to 2 (verdict + combined scorecard/psychology is too different to combine). Total: 6 Opus calls for 4-iteration campaign. Acceptable.

2. **Scorecard: LLM-Generated vs Pure Data**
   - What we know: All numerical data for the scorecard exists in the DB. The only value Opus adds is a narrative summary and ranking rationale.
   - What's unclear: Whether to use Opus for the scorecard at all.
   - Recommendation: Generate the scorecard programmatically from DB data (variant ranking, scores, color coding, trajectory). Add a short "ranking_rationale" field generated by Opus as part of the combined psychology call. This saves 1 Opus call. Total: 2 Opus calls for report (verdict + combined psychology).

3. **Report Persistence: New Table vs Extended Analyses Table**
   - What we know: D-01 says "store each report layer as a separate JSON field in the analysis table." However, the analyses table stores per-iteration analysis (one row per iteration). A report is per-campaign (one row per campaign).
   - What's unclear: Whether D-01 literally means the analyses table or just the general storage approach.
   - Recommendation: Create a new `reports` table with UNIQUE constraint on campaign_id. This is cleaner than overloading the analyses table which is per-iteration. The spirit of D-01 (separate fields, independent fetch) is preserved.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | None (pytest defaults, tests collected from orchestrator/tests/) |
| Quick run command | `python -m pytest orchestrator/tests/test_report_generator.py -x -q` |
| Full suite command | `python -m pytest orchestrator/tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RPT-01 | Layer 1 verdict is plain English, 100-400 words, no jargon, clear recommendation | unit | `python -m pytest orchestrator/tests/test_report_generator.py::test_verdict_generation -x` | Wave 0 |
| RPT-02 | Layer 2 scorecard has composite scores, variant ranking, iteration trajectory JSON | unit | `python -m pytest orchestrator/tests/test_report_generator.py::test_scorecard_assembly -x` | Wave 0 |
| RPT-03 | Layer 3 deep analysis contains all raw scores, metrics, reasoning per iteration | unit | `python -m pytest orchestrator/tests/test_report_generator.py::test_deep_analysis_assembly -x` | Wave 0 |
| RPT-04 | Layer 4 general narrative is 200-600 words, references simulation cycles | unit | `python -m pytest orchestrator/tests/test_report_generator.py::test_psychology_general -x` | Wave 0 |
| RPT-05 | Layer 4 technical references >= 2 named psychology theories | unit | `python -m pytest orchestrator/tests/test_report_generator.py::test_psychology_technical -x` | Wave 0 |
| RPT-06 | JSON export includes full campaign data | unit + integration | `python -m pytest orchestrator/tests/test_reports_api.py::test_json_export -x` | Wave 0 |
| RPT-07 | Markdown summary export with all 4 layers | unit + integration | `python -m pytest orchestrator/tests/test_reports_api.py::test_markdown_export -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest orchestrator/tests/test_report_generator.py -x -q`
- **Per wave merge:** `python -m pytest orchestrator/tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `orchestrator/tests/test_report_generator.py` -- covers RPT-01, RPT-02, RPT-03, RPT-04, RPT-05
- [ ] `orchestrator/tests/test_reports_api.py` -- covers RPT-06, RPT-07
- [ ] No new framework install needed -- pytest and pytest-asyncio already installed

## Sources

### Primary (HIGH confidence)
- `orchestrator/prompts/report_verdict.py` -- Existing Layer 1 prompt template (read directly)
- `orchestrator/prompts/report_psychology.py` -- Existing Layer 4 prompt templates (read directly)
- `orchestrator/engine/result_analyzer.py` -- Established Claude Opus calling pattern (read directly)
- `orchestrator/engine/campaign_runner.py` -- run_campaign() integration point (read directly)
- `orchestrator/storage/campaign_store.py` -- DB persistence patterns (read directly)
- `orchestrator/storage/database.py` -- Schema definition patterns (read directly)
- `orchestrator/api/schemas.py` -- Pydantic response model patterns (read directly)
- `orchestrator/api/campaigns.py` -- Router + endpoint patterns (read directly)
- `orchestrator/clients/claude_client.py` -- call_opus, call_opus_json API (read directly)
- `docs/Results.md` -- Quality standards, output layer specs, JSON schema (read directly)

### Secondary (MEDIUM confidence)
- FastAPI Response with Content-Disposition for file download -- standard FastAPI pattern, well-documented

### Tertiary (LOW confidence)
- None. All findings are from direct codebase inspection and project documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and used in the project
- Architecture: HIGH -- follows established patterns from Phase 5/6 codebase
- Pitfalls: HIGH -- derived from direct code analysis and known constraints

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable -- no external dependency changes expected)
