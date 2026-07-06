# A.R.C Studio — Full-Codebase Audit Summary

Date: 2026-07-05 · Branch: `competition/amd-hackathon`
Target assessed: **100 concurrent users × up to 100 in-app agents each** (~10k concurrent agents).

## What was done
- **Recon + baseline** (`baseline.md`) — mapped the stack, identified the agent-execution layer (orchestrator campaign tasks + MiroFish per-simulation subprocesses + TRIBE single-GPU lock), ran the suites.
- **9-track parallel deep inspection** — 9 Sonnet agents read the actual code; produced 124 findings (`findings/*.md`).
- **Synthesis + verification** (`master-report.md`) — deduplicated to canonical issues; every fixed finding was re-read against the code and marked VERIFIED before touching it; 3 were REJECTED/downgraded.
- **Fixes** — 30 contained fixes across orchestrator + TRIBE + the MiroFish submodule, each with a regression test or explicit verification.
- **Verification** — full suites re-run, a purpose-built concurrency stress test added, and a fresh adversarial Sonnet reviewer audited the diff (found 1 real regression, now fixed).
- **Structural items** (`architecture-proposals.md`) — 6 changes that can't be contained were written up and **NOT implemented**; they await your go/no-go.

## Before / after

| Gate | Before | After |
|---|---|---|
| Orchestrator pytest | **collection error** (stale `CHUNK_SIZE_WORDS` import aborted the whole suite) → 311 when excluded | **319 passed, 19 skipped** (TRIBE-venv-gated) |
| TRIBE scorer pytest (py3.11 venv) | 32 passed | 32 passed |
| Concurrency stress test | none existed | **2 passed** (admission bound, no leak, bounded concurrency, reconnect, no deadlock) |
| UI `tsc --noEmit` | clean | clean |
| UI ESLint | 9 errors (pre-existing) | 9 errors (out of scope — logged in `deferred.md`) |
| Adversarial diff review | — | 1 HIGH regression found + fixed; all other categories verified clean |

## What was fixed (30 issues)

**CRITICAL**
- **M-01** `find_best_composite([])` IndexError killed the campaign on any zero-variant round → guarded + raises an attributable `ValueError` upstream.
- **M-02** LiteLLM token refresh ran a blocking `subprocess.run` inside the event loop, freezing all users ~75-90s → `run_in_executor` + lock + concurrent-caller coalescing.
- **M-03** `media_path` accepted any absolute path (Whisper file-disclosure oracle) → resolved-path containment against the upload dir.
- **M-04 (submodule)** Cypher label injection into the shared Neo4j from LLM-extracted entity types → `_safe_label` allowlist at both sinks.
- **M-05 (submodule)** Path traversal via `project_id` / `platform` / body `simulation_id` → regex guards + realpath containment.

**HIGH** — audience_fit weighted-average math (M-08); report [0,1]→[0,100] scaling + dead coalition branch (M-09/M-10); CLI crash on real scores (M-11); false "converged" on no-data (M-26); graceful-shutdown task drain (M-12); DELETE cancels its task (M-13); admission control 429 (M-14, race-free reservation counter); progress queue/history eviction + SSE-reconnect fix (M-15/M-16); LLM retry jitter (M-17); TRIBE OOM→503-retryable + `empty_cache` (M-18); Whisper transcript read moved inside the lock (M-21, cross-user leak); audio transcript grounding (M-25); batch per-item resilience (M-30); hot-path indexes + `busy_timeout` (M-19); demographic request-time validation (M-20); logging on the uvicorn path (M-22); MiroFish port default 5001 (M-23); env-driven CORS (M-24); atomic state writes (M-27, submodule); Neo4j entity uniqueness constraint (M-28, submodule); Flask insecure defaults (M-29, submodule); leaked HF token reverted (SEC-08).

**MEDIUM (low-risk)** — completeness per-variant (M-34); estimate uses agent_count (M-35); 401 refresh retry-slot (M-36); tribe_http fail-safe timeout (M-37); sqlite `closing()` leak (M-38, submodule).

The adversarial reviewer then caught **one regression the fixes introduced** — the new `project_id` guard made a stray directory entry 500 the whole project list. Fixed: `get_project`/`delete_project` treat a malformed id as "not found" (404/skip) while the traversal guard stays intact.

## Remaining risks (NOT fixed — require your approval)
The scale target is gated by 6 structural items in `architecture-proposals.md`. The most important:

1. **P-1 — TRIBE is one GPU behind one process-wide lock.** The contained admission cap (M-14) now bounds the *queue* and returns 429 past capacity, but one GPU physically cannot score 100 concurrent campaigns inside the 20-min SLA. You need the bounded-queue-with-visible-position rework (and the RES-01 hung-inference-thread fix) or horizontal GPU scale.
2. **P-2 — a restart blanket-fails every running campaign.** Needs heartbeat/lease + resume before multi-tenant use.
3. **P-3/P-4 — MiroFish is a single Werkzeug dev-server process** with per-simulation OS subprocesses tracked in unlocked, un-reconciled class dicts. Needs a WSGI server + state externalization + orphan reconciliation.
4. **P-6 — no auth / no tenant ownership.** Every list/delete is cross-user by default. Hard gate before exposing to >1 trusted user.

Also deferred (see `deferred.md`): the broken agent-chat contract (API-01, feature-dead), MiroFish N+1 Neo4j/embedding batching (P-5), assorted MEDIUM/LOW hygiene, and the 9 pre-existing UI ESLint errors.

## Go / No-Go for 100 users × 100 agents

**NO-GO as-is** for the full 100×100 target — the architecture (one shared GPU + one TRIBE lock + one MiroFish dev-server process + no tenancy) cannot sustain it; that requires P-1, P-3/P-4, and P-6. The contained fixes make the system **fail safely and observably** instead of silently hanging/leaking/corrupting, which is the prerequisite for the structural work.

**GO for a bounded pilot** once you set the limits below and accept per-request queuing rather than the 20-min SLA at peak.

### Production limits to configure

| Setting | Where | Recommended | Why |
|---|---|---|---|
| `max_concurrent_campaigns` | `orchestrator/config.py` (new) | **≈ 2–4 × GPU count** (default 8) | Each admitted campaign ultimately serializes on the one TRIBE lock; past this, 429. Raising it just deepens the invisible queue. |
| `cors_allowed_origins` | `orchestrator/config.py` (new) | your real UI origin(s), comma-sep | Never `*` with credentials. |
| SQLite | already set | WAL + `busy_timeout=10000` | Single-writer; do NOT run multiple uvicorn workers against one file — move to Postgres first (P-2). |
| uvicorn workers | deploy | **1** until P-2/P-4 | Per-process in-memory state (running_tasks, progress queues) is not shared across workers. |
| httpx pool | `orchestrator/api/__init__.py` | set explicit `httpx.Limits` sized to `max_concurrent_campaigns` | Default 100 lines up with the target and hides exhaustion. |
| MiroFish | `docker-compose` | gunicorn `-w N -k gthread`, bounded (P-3) | Werkzeug dev server won't hold 100 concurrent long requests. |
| Neo4j heap / cleanup | `docker-compose` | scale off actual agent_count; schedule cleanup | 2 GB heap + manual cleanup was calibrated for 40 agents, not 100. |
| TRIBE queue depth | new (P-1) | expose on `/api/health` + a `/metrics` endpoint | Today the lock backs up invisibly; add queue-depth before load. |
| Rotate `HF_TOKEN` | secret store | now | It was present in the working tree; treat as compromised. |

**Bottom line:** every silent, fleet-wide failure mode the audit found (IndexError crash, event-loop freeze, transcript cross-contamination, unbounded queue/leak, Cypher injection, path traversal, file-disclosure, false convergence) is now closed or converted into a bounded, observable, 429-signalled condition — verified by 319 passing tests + a concurrency stress test + an adversarial diff review. Reaching a true 100×100 SLA is a hardware/architecture decision captured in `architecture-proposals.md`, not a code-correctness gap.
