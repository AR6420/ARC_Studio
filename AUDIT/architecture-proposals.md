# Architecture Proposals — structural changes requiring approval

These items from the audit **cannot be fixed as contained changes** — they require structural / deployment / data-model changes with real blast radius. Per the audit ground rules I have **NOT implemented these**; each is a concrete proposal awaiting your go/no-go. The contained fixes (see `master-report.md` Batches A–E) proceed independently.

---

## P-1 — TRIBE scoring: admission control + request queue (M-06 / CON-03 / PERF-01 / OBS-07 / RES-01)

> **UPDATE (approved + implemented):** direction given — *careful single-GPU local + optional multi-GPU cloud*. The contained parts are **done** (bounded admission gate + `queue_depth` on `/health` locally; least-in-flight multi-endpoint pool via `TRIBE_SCORER_URLS` for cloud). See **`p1-gpu-scaling-design.md`**. The only piece still open is **RES-01** (zombie-thread overlap on inference timeout), which is a scoring-internals change requiring a GPU to verify — deferred to a focused follow-up.


**Problem.** One process-wide `threading.Lock` (`tribe_scorer/main.py:400`) serializes all neural scoring for all users on one GPU, with `SCORE_TIMEOUT=5400s` so nothing fails fast. 100 concurrent campaigns → ~200 texts queue for 1.5–5h; `/api/health` reports "ok" throughout. On timeout the worker thread can't be killed and the lock releases anyway → concurrent `model.predict()` on a non-thread-safe model + VRAM leak.

**Contained slice already being done:** orchestrator-side max-concurrent-campaigns cap → 429 (M-14). That bounds the *queue*, it does not add *throughput*.

**Proposed structural change (pick one):**
1. **Bounded queue + visible position (lowest effort).** Replace the raw lock with a `queue.Queue(maxsize=N)` + a single worker thread; reject (503 `Retry-After`) when full; expose `queue_depth`/`position` on `/api/health` and stream it to the UI. Also fix RES-01: keep the lock held until the timed-out worker thread actually exits (or move inference to a **subprocess** pool so a hung inference can be killed).
2. **Horizontal GPU scale.** Run K TRIBE replicas behind a small load balancer; requires the model to load per-replica (VRAM budget) — likely needs more than the single RTX 5070 Ti / one MI300X partition.

**Recommendation:** (1) now (unblocks correctness + observability on existing hardware), (2) only if the 20-min SLA must hold at 100 concurrent campaigns — which one GPU physically cannot do.

**Risk if declined:** product appears frozen for ~99% of users under real concurrency; possible CUDA-context corruption taking down scoring for everyone.

---

## P-2 — Campaign durability: heartbeat/lease + resume instead of blanket-fail (M-07 / DATA-01)

**Problem.** `cleanup_orphaned_campaigns` (`campaign_store.py:75`) marks **every** `status='running'` row failed on startup, globally. One crash/deploy wipes all users' in-flight work with no resume.

**Proposed change.** Add `heartbeat_at` + `worker_id` columns; the runner touches `heartbeat_at` each stage; startup only fails rows whose heartbeat is stale (> T) AND not owned by a live worker. Persist enough per-iteration state (already largely in `iterations`) to **resume** an interrupted campaign from its last completed iteration rather than failing it.

**Risk if declined:** at 100 users, any restart under load = total loss of all concurrent work. Acceptable only for the single-user POC it was written for.

---

## P-3 — MiroFish: production WSGI server + bounded workers (M-31 / OBS-05 / CON-04 / PERF-01 / ERR-15)

**Problem.** `mirofish/backend/run.py:45` runs Werkzeug's dev server (`app.run(threaded=True)`); the Docker image launches `npm run dev`. Single GIL-bound process fields all ontology/build/prepare/start + per-sim monitor threads + poll storms.

**Proposed change.** Serve under `gunicorn`/`waitress` with a bounded worker/thread pool (`gunicorn -w N -k gthread`), drop the Vite dev server from the prod image. **Blocker:** MiroFish's process/thread state is class-level in-memory (`SimulationRunner._processes` etc.), so multi-worker requires externalizing that state (Redis / DB / sticky routing) — see P-4. Submodule change; keep minimal for upstream merge.

**Risk if declined:** MiroFish is the first tier to collapse under concurrent launches; orchestrator graceful-degradation silently drops most campaigns to TRIBE-only.

---

## P-4 — MiroFish execution model: subprocess orphan reconciliation + shared-state locking (M-33)

**Problem.** One detached OS subprocess (`start_new_session=True`) + one monitor thread per simulation, tracked only in process-local class dicts with **no locks** and **no startup reconciliation**. Hard-kill/OOM/restart orphans up to 100 subprocesses invisibly; `start_simulation` has a check-then-act TOCTOU; class dicts are read/written from Flask threads + monitor threads without synchronization; `_run_states`/`_simulations`/`_monitor_threads` never evicted.

**Proposed change.** (a) One `threading.RLock` (or per-`simulation_id` lock map) guarding all read-modify-write on the shared dicts + the start check-then-act; (b) startup scan of `run_state.json` for `running` PIDs → adopt or reap; (c) evict terminal entries. Contained atomic-write + eviction pieces (M-27) are being done now; the locking + reconciliation are structural (change concurrency semantics of a submodule).

**Risk if declined:** orphaned agent workloads burn GPU/LLM budget; "restart to fix" makes the leak worse; lost-update races corrupt run state.

---

## P-5 — MiroFish write-path performance: batch Neo4j + embeddings (M-32 / PERF-05 / PERF-06)

**Problem.** `add_text` does ~1+2·entities+relations separate Neo4j transactions (≈50–60 round-trips/chunk); profile gen does per-agent un-batched `embed()` + 4 Neo4j round-trips × 100 agents × 100 sims; graph build runs on unbounded raw `threading.Thread`s.

**Proposed change.** `UNWIND`-batch entity upserts + relation creates (2–3 statements/chunk); `embed_batch()` once per simulation; run builds on a bounded `ThreadPoolExecutor`. Submodule perf change; needs benchmarking against a live Neo4j.

**Risk if declined:** ~50× Neo4j round-trip overhead per graph build; ~10k un-batched embedding calls + ~40k round-trips per "generate personas" phase at target scale.

---

## P-6 — Multi-tenancy: identity + ownership scoping (SEC-05 / API-02)

**Problem.** No auth and **no owner concept** anywhere. Every list endpoint returns all users' records; every delete/stop accepts any ID. Cross-tenant read/hijack/delete is the default behavior, not a bypass. (Explicitly out of Phase-1 scope, but a hard wall for the 100-user target.)

**Proposed change.** Minimal per-request identity (API key/session); `owner_id` on campaign/project/simulation rows at creation; filter every list/get/delete by owner; pagination on list endpoints (M-14 admission cap is complementary). Cross-cutting across both services + DB schema.

**Risk if declined:** any one of 100 users can read/delete every other user's data. Must be an explicit, signed-off scope boundary before multi-user exposure.

---

### Summary recommendation
Do **P-1(1)** and **P-2** first (they convert silent, fleet-wide failures into bounded, observable behavior on existing hardware). **P-3/P-4/P-5** are the MiroFish scale track (submodule; coordinate with upstream). **P-6** is the gate before any real multi-user deployment. None are started; awaiting your call.
