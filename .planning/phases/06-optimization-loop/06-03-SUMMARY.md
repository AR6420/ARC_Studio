---
phase: 06-optimization-loop
plan: 03
subsystem: api
tags: [fastapi, asyncio, sse, background-tasks, cli, integration-wiring]

# Dependency graph
requires:
  - phase: 06-optimization-loop
    provides: CampaignRunner.run_campaign() with progress_callback (Plan 01), SSE progress router and queue helpers (Plan 02)
provides:
  - CampaignRunner constructed in lifespan and stored on app.state.campaign_runner
  - Background campaign execution via asyncio.create_task on POST /campaigns with auto_start=True
  - Progress router mounted at /api prefix (SSE and estimate endpoints accessible)
  - CLI multi-iteration support via --max-iterations and --thresholds args
  - Integration tests verifying full wiring between API, background tasks, SSE, and CLI
affects: [07-report-generation, 08-ui-dashboard, 09-demo-scenarios]

# Tech tracking
tech-stack:
  added: []
  patterns: [background-task-pattern, queue-before-task-launch, lifespan-component-construction, cli-progress-callback]

key-files:
  created:
    - orchestrator/tests/test_integration_loop.py
  modified:
    - orchestrator/api/__init__.py
    - orchestrator/api/campaigns.py
    - orchestrator/cli.py
    - orchestrator/tests/test_cli.py

key-decisions:
  - "CampaignRunner constructed once in lifespan to share connection-pooled clients across all requests"
  - "Queue created BEFORE asyncio.create_task to prevent race condition (Pitfall 4)"
  - "running_tasks dict on app.state enables graceful shutdown via task.cancel()"
  - "CLI uses getattr for max_iterations/thresholds to maintain backward compat with existing test patterns"

patterns-established:
  - "Background task pattern: create queue -> define progress_callback -> asyncio.create_task -> track in running_tasks -> cleanup in finally"
  - "Lifespan component construction: engine components (VariantGenerator, TribeScoringPipeline, etc.) constructed from shared clients in lifespan"
  - "CLI progress callback: async function printing events for iteration_start/complete, threshold_check, convergence_check, campaign_complete"

requirements-completed: [OPT-01, OPT-06, OPT-07]

# Metrics
duration: 10min
completed: 2026-03-29
---

# Phase 6 Plan 3: API/CLI Wiring Summary

**Background campaign execution via asyncio.create_task with SSE progress streaming, CLI multi-iteration with --max-iterations/--thresholds, and full wiring integration tests**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-29T15:20:31Z
- **Completed:** 2026-03-29T15:30:41Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Wired CampaignRunner construction in FastAPI lifespan with all engine components (VariantGenerator, TribeScoringPipeline, MirofishRunner, ResultAnalyzer)
- POST /campaigns with auto_start=True now launches asyncio background task calling run_campaign() with SSE progress events
- CLI supports multi-iteration campaigns via --max-iterations and --thresholds args, console progress output
- 3 new integration tests + updated existing CLI tests, all 168 tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire CampaignRunner in lifespan, mount progress router, enable background execution** - `323555b` (feat)
2. **Task 2: Update CLI for multi-iteration, add integration tests** - `c134579` (feat)

## Files Created/Modified
- `orchestrator/api/__init__.py` - CampaignRunner construction in lifespan, progress router mounting, running_tasks + progress_queues init, shutdown cleanup
- `orchestrator/api/campaigns.py` - Background task launch on auto_start via asyncio.create_task with queue-first pattern
- `orchestrator/cli.py` - Multi-iteration via run_campaign(), --max-iterations, --thresholds, cli_progress_callback, updated _print_summary
- `orchestrator/tests/test_integration_loop.py` - 3 integration tests: CLI multi-iteration, API background task, progress router mounting
- `orchestrator/tests/test_cli.py` - Updated existing tests for multi-iteration result format and new args

## Decisions Made
- CampaignRunner is constructed once in lifespan (not per-request) to share connection-pooled HTTP clients across all campaigns
- Queue is created BEFORE launching the background task per Pitfall 4 to prevent the SSE endpoint from getting a 404
- running_tasks dict tracks active asyncio tasks on app.state for graceful cancellation during shutdown
- _print_summary refactored into _print_summary + _print_single_iteration to handle both multi-iteration and backward-compat single-iteration formats

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated existing CLI tests for multi-iteration format**
- **Found during:** Task 2 (CLI multi-iteration update)
- **Issue:** Existing test_cli.py mocked run_single_iteration() but CLI now calls run_campaign(); test failed with TypeError
- **Fix:** Updated test_run_campaign_mocked and test_run_campaign_with_seed_file to mock run_campaign() with multi-iteration result format, added max_iterations/thresholds to args Namespace
- **Files modified:** orchestrator/tests/test_cli.py
- **Verification:** All 11 CLI tests pass
- **Committed in:** c134579 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Test update was necessary since CLI behavior changed from single-iteration to multi-iteration. No scope creep.

## Known Stubs

None - all functions are fully implemented, no placeholders.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full optimization loop is wired: POST /campaigns -> background task -> run_campaign() -> SSE progress events
- CLI can run multi-iteration campaigns with console output
- Ready for Phase 07 (report generation) which can consume campaign results
- Ready for Phase 08 (UI dashboard) which can POST campaigns with auto_start and subscribe to SSE progress
- All 168 tests pass with no regressions

## Self-Check: PASSED

All files exist. All commit hashes verified (323555b, c134579).

---
*Phase: 06-optimization-loop*
*Completed: 2026-03-29*
