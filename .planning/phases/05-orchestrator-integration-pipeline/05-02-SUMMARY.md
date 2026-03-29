---
phase: 05-orchestrator-integration-pipeline
plan: 02
subsystem: api
tags: [httpx, async, http-client, tribe-v2, mirofish, polling, multipart-upload]

# Dependency graph
requires:
  - phase: 05-01
    provides: "orchestrator config with tribe_scorer_url and mirofish_url settings"
provides:
  - "TribeClient: async HTTP client for TRIBE v2 neural scoring (/api/health, /api/score)"
  - "MirofishClient: async HTTP client for MiroFish social simulation (full 9-step workflow)"
  - "Shared test infrastructure with httpx.MockTransport for mocking HTTP responses"
affects: [05-03, 05-04, 05-05]

# Tech tracking
tech-stack:
  added: [httpx, pytest-asyncio]
  patterns: [async-http-client, constructor-injection, mock-transport-testing, exponential-backoff-polling, multipart-file-upload, graceful-degradation]

key-files:
  created:
    - orchestrator/clients/tribe_client.py
    - orchestrator/clients/mirofish_client.py
    - orchestrator/tests/__init__.py
    - orchestrator/tests/test_clients.py
  modified:
    - orchestrator/clients/__init__.py

key-decisions:
  - "httpx.AsyncClient injected via constructor for shared connection pooling and testability"
  - "120s timeout for TRIBE GPU inference; exponential backoff polling for MiroFish async tasks"
  - "Both clients return None on failure for graceful degradation (D-05)"
  - "MiroFish content sent as multipart/form-data file upload to match Flask backend expectations"

patterns-established:
  - "Constructor injection: clients receive httpx.AsyncClient, caller manages lifecycle/base_url"
  - "Mock transport testing: httpx.MockTransport with URL-routing handlers for integration tests"
  - "Graceful None returns: all client methods return None on failure instead of raising"
  - "Exponential backoff polling: configurable initial interval, max interval, and backoff factor"

requirements-completed: [ORCH-07]

# Metrics
duration: 7min
completed: 2026-03-29
---

# Phase 05 Plan 02: Service Integration Clients Summary

**Async HTTP clients for TRIBE v2 neural scoring and MiroFish social simulation with 120s GPU timeout, 9-step polling workflow, multipart uploads, and 15 mocked tests**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-29T10:41:55Z
- **Completed:** 2026-03-29T10:48:55Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- TribeClient with health_check and score_text methods, 120s GPU inference timeout, 7-dimension score filtering
- MirofishClient implementing full 9-step async workflow: ontology/generate (multipart) -> graph/build -> poll -> sim/create -> sim/prepare -> poll -> sim/start -> poll -> extract results
- 15 tests covering both clients: health checks, scoring, full workflow, graph build failure, poll timeout, connection errors, missing dimensions

## Task Commits

Each task was committed atomically:

1. **Task 1: Create TRIBE v2 HTTP client** - `d521930` (feat)
2. **Task 2: Create MiroFish HTTP client with full simulation workflow** - `c943368` (feat)

## Files Created/Modified
- `orchestrator/clients/tribe_client.py` - Async TRIBE v2 client with health_check and score_text (120s timeout, 7-dimension filtering)
- `orchestrator/clients/mirofish_client.py` - Async MiroFish client with full 9-step simulation workflow (polling, multipart upload)
- `orchestrator/clients/__init__.py` - Updated to export TribeClient and MirofishClient
- `orchestrator/tests/__init__.py` - Test package init
- `orchestrator/tests/test_clients.py` - 15 tests using httpx.MockTransport for both clients

## Decisions Made
- Used httpx.AsyncClient constructor injection instead of creating clients internally -- enables shared connection pooling in FastAPI lifespan and easy testing with MockTransport
- Set 120-second timeout for TRIBE score_text (GPU inference takes 10-30s, buffer for load spikes)
- MiroFish polling uses exponential backoff: 2s initial, 1.5x factor, 10s max interval with configurable timeouts per stage (5min graph build, 5min prepare, 10min run)
- Content sent as multipart/form-data file upload matching MiroFish Flask backend expectations (Pitfall 2 from research)
- Both clients return None on failure for graceful degradation (design decision D-05)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all functionality is fully implemented and wired.

## Next Phase Readiness
- TribeClient and MirofishClient are ready for use by the pipeline engine (Plan 03, 04)
- Both clients accept httpx.AsyncClient via constructor, which should be created in the FastAPI app lifespan with base_url set from settings
- Test infrastructure (MockTransport pattern) is established for future client tests

## Self-Check: PASSED

- All 6 files verified present on disk
- Commit d521930 (Task 1) verified in git log
- Commit c943368 (Task 2) verified in git log
- All 15 tests pass

---
*Phase: 05-orchestrator-integration-pipeline*
*Completed: 2026-03-29*
