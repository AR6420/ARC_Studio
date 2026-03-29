---
phase: 5
slug: orchestrator-integration-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | orchestrator/pytest.ini or pyproject.toml (Wave 0 creates) |
| **Quick run command** | `python -m pytest orchestrator/tests/ -x -q` |
| **Full suite command** | `python -m pytest orchestrator/tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest orchestrator/tests/ -x -q`
- **After every plan wave:** Run `python -m pytest orchestrator/tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | ORCH-01 | integration | `pytest orchestrator/tests/test_app.py -k test_cors_and_lifespan` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | ORCH-02 | unit | `pytest orchestrator/tests/test_storage.py -k test_schema` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | ORCH-03 | unit | `pytest orchestrator/tests/test_schemas.py` | ❌ W0 | ⬜ pending |
| 05-01-04 | 01 | 1 | ORCH-04 | integration | `pytest orchestrator/tests/test_api.py -k test_campaign_crud` | ❌ W0 | ⬜ pending |
| 05-01-05 | 01 | 1 | ORCH-05 | integration | `pytest orchestrator/tests/test_api.py -k test_health` | ❌ W0 | ⬜ pending |
| 05-01-06 | 01 | 1 | ORCH-06 | integration | `pytest orchestrator/tests/test_api.py -k test_demographics` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 2 | ORCH-07 | unit | `pytest orchestrator/tests/test_clients.py` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 2 | ORCH-08 | unit | `pytest orchestrator/tests/test_engine.py -k test_variant_generator` | ❌ W0 | ⬜ pending |
| 05-02-03 | 02 | 2 | ORCH-09 | unit | `pytest orchestrator/tests/test_engine.py -k test_tribe_pipeline` | ❌ W0 | ⬜ pending |
| 05-02-04 | 02 | 2 | ORCH-10 | unit | `pytest orchestrator/tests/test_engine.py -k test_mirofish_pipeline` | ❌ W0 | ⬜ pending |
| 05-02-05 | 02 | 2 | ORCH-11 | unit | `pytest orchestrator/tests/test_engine.py -k test_composite_scorer` | ❌ W0 | ⬜ pending |
| 05-02-06 | 02 | 2 | ORCH-12 | unit | `pytest orchestrator/tests/test_engine.py -k test_result_analyzer` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 3 | ORCH-13 | integration | `pytest orchestrator/tests/test_engine.py -k test_campaign_runner` | ❌ W0 | ⬜ pending |
| 05-03-02 | 03 | 3 | ORCH-14 | integration | `pytest orchestrator/tests/test_cli.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `orchestrator/tests/__init__.py` — test package init
- [ ] `orchestrator/tests/conftest.py` — shared fixtures (mock HTTP clients, test DB, test settings)
- [ ] `orchestrator/tests/test_storage.py` — stubs for ORCH-02
- [ ] `orchestrator/tests/test_schemas.py` — stubs for ORCH-03
- [ ] `orchestrator/tests/test_app.py` — stubs for ORCH-01
- [ ] `orchestrator/tests/test_api.py` — stubs for ORCH-04, ORCH-05, ORCH-06
- [ ] `orchestrator/tests/test_clients.py` — stubs for ORCH-07
- [ ] `orchestrator/tests/test_engine.py` — stubs for ORCH-08 through ORCH-13
- [ ] `orchestrator/tests/test_cli.py` — stubs for ORCH-14
- [ ] pytest + pytest-asyncio installed (check requirements.txt)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cross-system analysis references both TRIBE + MiroFish | ORCH-12 | LLM output content cannot be deterministically asserted | Read analysis output, confirm both system references present |
| Graceful degradation with real service outage | ORCH-14 (SC-5) | Requires actually stopping TRIBE/MiroFish services | Stop tribe_scorer, run campaign, verify partial results with gap warnings |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
