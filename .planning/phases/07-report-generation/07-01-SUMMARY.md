---
phase: 07-report-generation
plan: 01
subsystem: engine
tags: [report-generation, claude-opus, scorecard, color-coding, sqlite, pydantic]

# Dependency graph
requires:
  - phase: 05-orchestrator-core
    provides: CampaignStore, Database, Pydantic schemas, ClaudeClient, optimization_loop helpers
  - phase: 06-pipeline-integration
    provides: CampaignRunner, INVERTED_SCORES, find_best_composite, check_thresholds
provides:
  - ReportGenerator class with generate_report() for all 4 report layers
  - Reports table in SQLite schema (separate fields per D-01)
  - save_report() and get_report() on CampaignStore
  - ScorecardData, ScorecardVariant, ReportResponse Pydantic models
  - color_code_score utility with inverted logic for backlash/polarization
  - REPORT_SCORECARD_SYSTEM prompt template
affects: [07-02-pipeline-integration, 08-frontend, 09-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Programmatic scorecard assembly with Opus-only narrative summary"
    - "color_code_score with INVERTED_SCORES for backlash_risk and polarization_index"
    - "Separate report layer fields in DB for independent UI fetching (D-01)"

key-files:
  created:
    - orchestrator/engine/report_generator.py
    - orchestrator/prompts/report_scorecard.py
    - orchestrator/tests/test_report_generator.py
  modified:
    - orchestrator/storage/database.py
    - orchestrator/storage/campaign_store.py
    - orchestrator/api/schemas.py

key-decisions:
  - "Scorecard is programmatic (no Opus call for data), only narrative summary uses LLM"
  - "Layer 3 deep analysis is pure data aggregation from DB - no LLM call per research guidance"
  - "Two separate Opus calls for psychology general + technical to maintain distinct system prompts"
  - "Reports table separate from analyses table (one report per campaign, not per iteration)"

patterns-established:
  - "color_code_score: green/amber/red thresholds with inverted logic for lower-is-better metrics"
  - "ReportGenerator follows ResultAnalyzer pattern: ClaudeClient injected via constructor"
  - "Report layers stored as separate DB fields for independent fetching"

requirements-completed: [RPT-01, RPT-02, RPT-03, RPT-04, RPT-05]

# Metrics
duration: 12min
completed: 2026-03-29
---

# Phase 7 Plan 1: Report Generation Engine Summary

**ReportGenerator engine producing 4 report layers (verdict, scorecard, deep analysis, mass psychology) with programmatic scorecard ranking, color coding, and SQLite persistence**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-29T18:59:35Z
- **Completed:** 2026-03-29T19:11:07Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- ReportGenerator.generate_report() returns all 5 layer keys (verdict, scorecard, deep_analysis, mass_psychology_general, mass_psychology_technical)
- Reports table with separate fields per D-01 plus save_report/get_report on CampaignStore
- Scorecard assembled programmatically with variant ranking, color coding (inverted for backlash/polarization), iteration trajectory, and threshold status
- Deep analysis is pure data aggregation from stored iteration/analysis records without any LLM call
- 19 comprehensive tests covering all layers, color coding logic, and storage roundtrip

## Task Commits

Each task was committed atomically (TDD: test -> feat):

1. **Task 1: Report data layer** - `34e3536` (test) -> `4455997` (feat)
2. **Task 2: ReportGenerator engine** - `e5ec033` (test) -> `3d3dbce` (feat)

## Files Created/Modified
- `orchestrator/engine/report_generator.py` - ReportGenerator class with generate_report, color_code_score utility
- `orchestrator/prompts/report_scorecard.py` - REPORT_SCORECARD_SYSTEM prompt and build_report_scorecard_prompt
- `orchestrator/tests/test_report_generator.py` - 19 tests covering all report layers, models, storage, and color coding
- `orchestrator/storage/database.py` - Reports table added to SCHEMA_SQL
- `orchestrator/storage/campaign_store.py` - save_report() and get_report() methods
- `orchestrator/api/schemas.py` - ScorecardVariant, ScorecardData, ReportResponse Pydantic models

## Decisions Made
- Scorecard is programmatic (variant ranking, color coding, trajectory all computed from DB data). No Opus call for scorecard data -- only a template-based summary string. This saves 1 Opus call per campaign.
- Layer 3 deep analysis assembled from stored IterationRecords and AnalysisRecords. No LLM involvement per research guidance.
- Two separate Opus calls for psychology general + technical (per Open Question #1 in RESEARCH.md) to maintain distinct system prompts and quality.
- Reports table separate from analyses table (UNIQUE on campaign_id enforces one report per campaign).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all report layers produce real output (LLM calls mocked in tests, but the code paths are fully wired).

## Next Phase Readiness
- ReportGenerator is ready for Plan 02 to integrate into CampaignRunner.run_campaign() and add API endpoints
- save_report/get_report on CampaignStore ready for pipeline integration
- ScorecardData and ReportResponse models ready for API response serialization

## Self-Check: PASSED

All files verified present. All commit hashes verified in git log.

---
*Phase: 07-report-generation*
*Completed: 2026-03-29*
