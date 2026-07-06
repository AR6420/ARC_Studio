# Track 2 — Concurrency & Agent Lifecycle

Scope audited: `orchestrator/api/__init__.py`, `campaigns.py`, `progress.py`, `agents.py`;
`orchestrator/engine/campaign_runner.py`, `mirofish_runner.py`; `orchestrator/clients/mirofish_client.py`,
`tribe_client.py`; `tribe_scorer/main.py`; `mirofish/backend/app/services/simulation_runner.py`,
`simulation_manager.py`, `simulation_ipc.py`, `graph_memory_updater.py`;
`mirofish/backend/scripts/run_parallel_simulation.py`, `action_logger.py`;
`mirofish/backend/run.py` + `app/__init__.py`.

Scaling target evaluated against: ~100 concurrent users × ~100 agents each (~10,000 concurrent
simulated agents; many concurrent campaigns/simulations), local or cloud hardware.

Severity scheme: CRITICAL (data loss / crash / security breach / hard failure at target scale),
HIGH (breaks under concurrency or realistic load, serious correctness bug), MEDIUM (degradation,
edge-case bug), LOW (hygiene).

---

## CON-01 — CRITICAL — MiroFish simulation subprocesses become permanent, unmanaged orphans on any ungraceful server stop

**File:** `mirofish/backend/app/services/simulation_runner.py:440-478` (subprocess spawn), `:1285-1356`
(`register_cleanup`), `mirofish/backend/app/__init__.py:57-61` (registration call).

**What's wrong:** Every simulation is a `subprocess.Popen(..., start_new_session=True)` child
(line 440-450). Cleanup of these child processes (`_terminate_process` / `cleanup_all_simulations`,
lines 719-820, 1184-1283) only runs from three places: the `atexit` hook, the `SIGTERM`/`SIGINT`/`SIGHUP`
handler, or an explicit `/stop` API call. All in-memory bookkeeping that would let a *future* process
find and reap these children (`_processes`, `_run_states`, `_monitor_threads`) is a **process-local
class-level dict** (lines 218-227) — nothing is written that a subsequent process instance reads back
to reconcile state. There is no startup-time scan of `RUN_STATE_DIR`/`run_state.json` for
`runner_status: "running"` entries with a live `process_pid` from a previous instance.

**Why it fails:** `kill -9` / OOM-killer / Docker `stop -t 0` / Windows "End task" / a crash inside the
Flask process itself all bypass Python signal handlers and `atexit` entirely. `start_new_session=True`
detaches each simulation subprocess into its own session, so it is **not** reaped when the parent dies
either (no process-group / job-object linkage the OS would use to cascade-kill it). At 100 concurrent
simulations, any one hard-kill of the MiroFish container leaves up to 100 OASIS/CAMEL subprocesses
running indefinitely, each holding a `semaphore=30` concurrent-LLM-call budget and consuming
GPU/embedding/API resources with zero visibility to the newly-started server (`_processes` dict starts
empty). This is the textbook "restart the service to fix it" action that, on this codebase, makes the
resource leak *worse* rather than better.

**Proposed minimal fix:** On `create_app()` startup, scan `RUN_STATE_DIR/*/run_state.json` for
`runner_status == "running"` with a `process_pid`; for each, check liveness (`psutil.pid_exists` /
`os.kill(pid, 0)`) and either adopt (re-attach a monitor thread) or forcibly terminate + mark
`FAILED`/`STOPPED` before serving new requests.

---

## CON-02 — CRITICAL — Check-then-act race in `SimulationRunner.start_simulation()` lets two requests spawn two subprocesses against the same simulation directory/database

**File:** `mirofish/backend/app/services/simulation_runner.py:334-478`; also reachable via
`mirofish/backend/app/api/simulation.py` `/api/simulation/start` (no request-level lock either — the
handler does its own separate `get_simulation()` → status-check → `start_simulation()` sequence with
no synchronization).

**What's wrong:**
```python
existing = cls.get_run_state(simulation_id)
if existing and existing.runner_status in [RunnerStatus.RUNNING, RunnerStatus.STARTING]:
    raise ValueError(...)
...
cls._save_run_state(state)          # state = STARTING, written AFTER the check
...
process = subprocess.Popen(cmd, cwd=sim_dir, ...)   # deletes/recreates twitter_simulation.db, reddit_simulation.db
cls._processes[simulation_id] = process
```
The existence check and the state write are two separate operations with I/O (file read, `Popen`) in
between — a classic TOCTOU window, unprotected by any lock.

**Why it fails:** Two near-simultaneous `POST /api/simulation/start` calls for the same `simulation_id`
(client retry after a slow/timed-out first response, a UI double-click, or a future "restart" affordance)
both read `existing` before either writes `STARTING`. Both proceed to `Popen` a full OASIS/CAMEL
simulation process against the *same* `sim_dir`, both delete-then-recreate the same
`twitter_simulation.db` / `reddit_simulation.db` SQLite files (lines ~1151-1153, ~1342-1344 in
`run_parallel_simulation.py`), and both write `cls._processes[simulation_id] = process` — the second
write silently clobbers the first, so the earlier subprocess becomes untracked (can never be
`stop()`-ped or cleaned by `cleanup_all_simulations`) while both processes fight over the same SQLite
file, producing "database is locked" errors or corrupted data mid-run. Under Werkzeug's threaded dev
server (see CON-04) this window is easily wide enough to hit in practice — there is no serialization
across concurrent HTTP requests at all.

**Proposed minimal fix:** Add a per-`simulation_id` lock (e.g. a `threading.Lock()` in a
`Dict[str, Lock]` guarded by one global lock, or a single lock guarding the read-check-write sequence)
around the check-then-write in `start_simulation()`, and re-check `runner_status` after acquiring it.

---

## CON-03 — CRITICAL — TRIBE's single `threading.Lock` serializes ALL neural scoring for ALL users on one GPU, with no admission control anywhere upstream

**File:** `tribe_scorer/main.py:400` (`_inference_lock = threading.Lock()`), used at lines 496, 534, 608,
687 (text / batch / video / audio inference paths — all four share the *same* lock);
`orchestrator/clients/tribe_client.py:29` (`SCORE_TIMEOUT = 5400.0` — 90 minutes per request);
`orchestrator/api/campaigns.py:352-400` (`create_campaign` — no cap on concurrently auto-started
campaigns).

**What's wrong:** Every `/api/score`, `/api/score/batch`, `/api/score_audio`, `/api/score_video` request
— from every campaign, from every user — funnels through one process-wide lock before touching the GPU.
There is no queue-depth limit, no per-user fairness, and no admission control anywhere in the call chain
(`campaigns.py` → `campaign_runner.py` → `tribe_scorer.py` → `tribe_client.py` → TRIBE FastAPI) that
would reject or shed load instead of piling up behind the lock. The client-side timeout
(`SCORE_TIMEOUT = 5400s`) is long enough that nothing times out early — it just queues.

**Why it fails:** 100 users each launch a campaign at roughly the same time; `run_single_iteration`
Step 3 calls TRIBE for each of the 2 variants per campaign (200 texts total). All 100 requests arrive
at TRIBE concurrently, each occupies a thread from FastAPI's default executor and immediately blocks on
`_inference_lock.acquire()`. Only one text scores at a time; at a conservative 30-90s per short,
non-chunked text, draining a 200-deep queue takes on the order of 1.5-5 hours before the *last*
campaign's TRIBE step even starts — let alone MiroFish. This directly and severely violates the stated
performance target ("Full campaign ... must complete in <= 20 minutes") once more than a handful of
campaigns overlap, and it is silent: no error, no shed load, just an unbounded wait that looks to 99 of
100 users like the product is frozen.

**Proposed minimal fix:** Add a bounded semaphore/queue at the orchestrator (or TRIBE ingress) limiting
in-flight scoring requests, with fast-fail/backpressure (HTTP 429) beyond a small concurrency budget,
and surface queue position/ETA to the UI instead of an unbounded block. Longer term: this is a hardware
constraint (`CLAUDE.md`: "single RTX 5070 Ti GPU shared between TRIBE v2 and Ollama") that the POC scope
explicitly accepts for a single user — it does not hold at 100 concurrent users and needs either
horizontal GPU scaling or explicit per-user queuing/rate-limiting before this scale target is viable.

---

## CON-04 — HIGH — MiroFish Flask backend runs on Werkzeug's development server, not a production WSGI server

**File:** `mirofish/backend/run.py:45` — `app.run(host=host, port=port, debug=debug, threaded=True)`.

**What's wrong:** `threaded=True` on Werkzeug's built-in dev server spawns one raw OS thread per
inbound connection with no bound on worker count, no request queueing discipline, no process
supervision/recycling, and the documentation explicitly warns it is not intended for production
traffic. Combined with CON-08 (unlocked class-level shared dicts) and CON-11 (IPC busy-wait loops that
pin a Flask thread for up to 180s per interview), this server model is the actual concurrency substrate
every other MiroFish finding runs on top of.

**Why it fails:** At 100 concurrent users each polling `/run-status`, sending interview/chat messages,
and hitting `/prepare`/`/start`, Werkzeug's dev server has no admission control — it will keep spawning
threads until the OS/GIL contention degrades response times sharply or the process becomes unstable.
This is a known, well-documented failure mode of running `werkzeug`'s dev server under sustained
concurrent load.

**Proposed minimal fix:** Front MiroFish with a production WSGI server (gunicorn with a bounded worker/
thread pool, or waitress on Windows) and cap concurrent workers to a number the host can actually
support; keep `threaded=True` dev mode for local single-user development only.

---

## CON-05 — HIGH — "Sequential simulations" design assumption only holds within one campaign, not across concurrent users

**File:** `orchestrator/engine/mirofish_runner.py:1-13, 34-62` (module docstring: "Per D-04: Simulations
run SEQUENTIALLY to avoid Neo4j graph DB conflicts"); `mirofish/backend/app/services/simulation_runner.py`
(no global concurrency cap in `start_simulation`).

**What's wrong:** `MirofishRunner.simulate_variants()` loops over a single campaign's variants
sequentially (`for i, variant in enumerate(variants): ... await self._client.run_simulation(...)`), which
does avoid Neo4j conflicts *for one campaign's own variants*. But this sequencing is per-`CampaignRunner`
instance/asyncio task; nothing serializes *across* the 100 independent campaign tasks each orchestrator
process runs concurrently (`app.state.running_tasks`, unbounded — see CON-06/CON-07). Each concurrently
hits the same shared Neo4j instance and the same MiroFish Flask backend to build a graph, spawn a
simulation subprocess, etc.

**Why it fails:** At 100 concurrent users, up to ~100 concurrent `POST /api/graph/ontology/generate` +
`/api/graph/build` + `/api/simulation/create/prepare/start` sequences hit the single Neo4j instance and
single MiroFish backend at once — exactly the conflict class D-04's "sequential" design was meant to
avoid, just moved up one level to the multi-user case that wasn't in scope when D-04 was decided. There
is no per-campaign or global cap anywhere (orchestrator or MiroFish) on how many simulations may run
concurrently.

**Proposed minimal fix:** Add a global (config-driven) semaphore in the orchestrator around MiroFish
simulation calls (and/or in MiroFish itself around `start_simulation`) sized to what the host's CPU/
memory/Neo4j connection pool can sustain; queue excess campaigns with visible ETA rather than free-running
them all.

---

## CON-06 — HIGH — Orchestrator shutdown cancels campaign tasks without awaiting them, racing DB/HTTP-client teardown

**File:** `orchestrator/api/__init__.py:215-225`.

```python
for task_id, task in app.state.running_tasks.items():
    if not task.done():
        task.cancel()
        logger.info("Cancelled running task for campaign %s", task_id)
app.state.running_tasks.clear()
app.state.progress_queues.clear()

await tribe_http.aclose()
await mirofish_http.aclose()
await db.close()
```

**What's wrong:** `task.cancel()` only *schedules* delivery of `CancelledError` at the task's next
`await` point; it does not wait for the task to actually unwind. The very next lines close the shared
httpx clients and the SQLite connection that those still-unwinding tasks may be mid-use of. Separately,
`asyncio.CancelledError` (Python ≥3.8) is **not** a subclass of `Exception`, so the
`except Exception as e:` blocks in `campaign_runner.py`'s `run_single_iteration`/`run_campaign` (which
are what would normally persist a `"failed"` status to SQLite) never fire on cancellation — a cancelled
campaign's DB row is left in whatever state it was last set to (often still `"running"`).

**Why it fails:** On any orchestrator restart/deploy while campaigns are in flight (entirely plausible
with 100 concurrent users and long-running campaigns), in-flight tasks can raise on a closed httpx
client or closed DB connection instead of exiting cleanly, and their campaign rows are left stuck in
`"running"` — only fixed retroactively by `cleanup_orphaned_campaigns()` on the *next* startup, during
which the UI shows a permanently "in progress" campaign that will never advance.

**Proposed minimal fix:** `await asyncio.gather(*app.state.running_tasks.values(), return_exceptions=True)`
after issuing `cancel()`, before closing `tribe_http`/`mirofish_http`/`db`; optionally catch
`asyncio.CancelledError` explicitly in `run_campaign`/`run_single_iteration` to write a `"cancelled"`
status before re-raising.

---

## CON-07 — HIGH — `progress_queues`/`progress_history` leak forever for any campaign whose SSE endpoint is never opened

**File:** `orchestrator/api/progress.py:27-49` (`get_or_create_queue`/`cleanup_queue`);
`orchestrator/api/campaigns.py:361-398` (`create_campaign` creates the queue + `progress_history[cid]`
entry before launching the background task).

**What's wrong:** `cleanup_queue()` is only ever invoked from inside `campaign_progress`'s
`event_generator()` `finally` block (`progress.py:109-110`) — i.e., only if some client actually opens
`GET /api/campaigns/{id}/progress` and it later disconnects or hits a terminal event. Nothing removes
`app.state.progress_queues[cid]` or `app.state.progress_history[cid]` for a campaign whose SSE endpoint
is *never* opened (headless kickoff, tab closed before the UI subscribes, `auto_start` campaigns created
by an API script). `progress_history` is capped per-campaign at 500 events (`HISTORY_CAP`), but the
outer dict entry itself is never evicted.

**Why it fails:** At 100 users running many campaigns over the orchestrator's uptime, every campaign
that nobody actively watches via SSE leaves a permanent `asyncio.Queue` (which itself has no `maxsize`,
so it can also grow unbounded while a producer runs with no consumer at all) plus a `list` in
`progress_history` that is never freed. This is unbounded memory growth proportional to total campaigns
run, not to concurrently-running campaigns — a slow leak that eventually degrades or crashes the
orchestrator process under sustained multi-user usage.

**Proposed minimal fix:** Evict `progress_queues`/`progress_history` entries from the campaign-store's
completion path (`update_campaign_status(..., "completed"/"failed")`) regardless of whether an SSE
client ever connected, with a short grace period (e.g., TTL) rather than requiring a live SSE
subscriber to trigger cleanup.

---

## CON-08 — HIGH — `SimulationRunner`'s class-level shared dicts are mutated without locks under Werkzeug's threaded model

**File:** `mirofish/backend/app/services/simulation_runner.py:218-227` (`_run_states`, `_processes`,
`_action_queues`, `_monitor_threads`, `_stdout_files`, `_stderr_files`, `_graph_memory_enabled` — all
plain class-level `Dict`s, no `threading.Lock` anywhere in the file).

**What's wrong:** These dicts are read and written from: (a) Flask request-handler threads (one per
connection under `threaded=True`, e.g. `/start`, `/stop`, `/run-status`, `cleanup_simulation_logs`), and
(b) each simulation's dedicated monitor thread (`_monitor_simulation`, spawned per `start_simulation`
call) — concurrently, with zero synchronization. Individual `dict[key] = value` operations are
GIL-atomic, but every meaningful operation here is a multi-step sequence (check-then-act in
`start_simulation`, per-platform completion tracking in `_check_all_platforms_completed`, snapshot-then-
iterate in `cleanup_all_simulations`) that is not.

**Why it fails:** At 100 concurrently active simulations (100 monitor threads + N concurrent request
threads touching the same class), lost updates are possible wherever two threads read-modify-write the
same key without a lock — e.g., a `/stop` request racing the monitor thread's own end-of-process cleanup
(`_processes.pop`, `_stdout_files.pop`) can double-close an already-closed file handle or operate on a
process object the monitor thread has already removed, or (as in CON-02) a start/restart race stomping
the tracked `Popen` handle.

**Proposed minimal fix:** Introduce one `threading.RLock` guarding all read-modify-write sequences on
`_run_states`/`_processes`/`_monitor_threads`/`_stdout_files`/`_stderr_files`, or migrate to per-
simulation locks keyed the same way `GraphMemoryManager._lock` already does for `_updaters`.

---

## CON-09 — MEDIUM — Non-atomic JSON persistence across MiroFish's file-based state (state, run-state, IPC, env-status)

**File:** `mirofish/backend/app/services/simulation_runner.py:298-309` (`_save_run_state`);
`mirofish/backend/app/services/simulation_manager.py:144-154` (`_save_simulation_state`);
`mirofish/backend/app/services/simulation_ipc.py:322-329` (`_update_env_status`), `:361-370`
(`send_response`).

**What's wrong:** Every one of these writers does a direct `open(path, 'w')` + `json.dump(...)` to the
*final* path — no write-to-temp-file-then-`os.replace()`. Readers (`_load_run_state`,
`_load_simulation_state`, `check_env_alive`) catch `JSONDecodeError`/`OSError` and silently fall back to
`None`/a default rather than retrying.

**Why it fails:** A reader thread opening `run_state.json` at the exact moment a writer thread (monitor
thread, every 2s per active simulation — see CON-12) is mid-`json.dump` on Windows can observe a
partially-written file. This is caught and treated as "state missing" (e.g., `run-status` briefly
reporting `"idle"` for a simulation that is actually running), and if the *process* dies mid-write
(matches CON-01's failure mode), the file is left truncated permanently, and the next server start
reads a broken/incomplete state for that simulation with no error surfaced anywhere.

**Proposed minimal fix:** Write to `f"{path}.tmp"` then `os.replace(tmp, path)` for all four writers;
this makes concurrent reads always see either the old or fully-new content, and crash-mid-write leaves
the old (still-valid) file in place.

---

## CON-10 — MEDIUM — Daemon-thread buffers can silently drop the last agent activities on a hard kill

**File:** `mirofish/backend/app/services/graph_memory_updater.py:206-249` (`start`/`_worker_loop`,
`daemon=True` at line 236), `:340-360` (`_flush_remaining`, only reachable via explicit `.stop()`).

**What's wrong:** `GraphMemoryUpdater` batches up to `BATCH_SIZE=5` activities per platform in an
in-memory list (`_platform_buffers`) before flushing to Neo4j; the only path that flushes a partial
(<5) buffer is `stop()` → `_flush_remaining()`, called from `_monitor_simulation`'s `finally` block or
`GraphMemoryManager.stop_all()`. Both of those are themselves only reached on graceful shutdown paths
(see CON-01).

**Why it fails:** Any of CON-01's hard-kill scenarios also drops up to 4 buffered, not-yet-persisted
agent activities per platform per simulation — silent, unrecoverable data loss in the knowledge graph
that compounds with the underlying process becoming orphaned rather than being restarted cleanly.

**Proposed minimal fix:** Flush on every batch tick regardless of size (e.g., time-based flush every N
seconds in addition to size-based), or persist the buffer to disk so a reconciliation pass (paired with
CON-01's fix) can recover it.

---

## CON-11 — MEDIUM — File-based interview/chat IPC is a synchronous busy-wait that pins a Flask thread for up to 180s per request

**File:** `mirofish/backend/app/services/simulation_ipc.py:116-186` (`send_command` —
`while time.time() - start_time < timeout: ... time.sleep(poll_interval)`);
`mirofish/backend/scripts/run_parallel_simulation.py:1613-1631` (simulation-side command loop processes
one command per ~0.5s tick via `process_commands()` + `asyncio.wait_for(_shutdown_event.wait(), timeout=0.5)`).

**What's wrong:** Every `interview_agent`/`interview_agents_batch`/`close_simulation_env` call
synchronously polls a response file on disk from the calling Flask request thread, blocking that thread
for the command's full `timeout` (60-180s) if the simulation is slow to answer. The simulation subprocess
drains at most one command per ~0.5s loop tick.

**Why it fails:** At 100 concurrent users each opening agent-chat panels, every concurrent interview/chat
request occupies its own OS thread on the (already unbounded, CON-04) Werkzeug dev server for the
duration of the wait, and multiple concurrent interview requests *targeting the same simulation*
serialize behind the subprocess's single ~2-commands/sec drain rate — a burst of interview requests to
one popular simulation can queue long enough to approach the per-request timeout and fail even though
the simulation itself is healthy.

**Proposed minimal fix:** Cap concurrent in-flight interview requests per simulation (reject/queue with
a fast 429 beyond a small number), and/or replace the busy-wait with a shorter poll interval plus
early-return once the response file appears, to reduce worst-case thread pinning.

---

## CON-12 — MEDIUM — One dedicated monitor thread per active simulation with unconditional per-tick JSON rewrite

**File:** `mirofish/backend/app/services/simulation_runner.py:461-468` (thread spawned per
`start_simulation`), `:481-580` (`_monitor_simulation` — `while process.poll() is None: ...
cls._save_run_state(state); time.sleep(2)`).

**What's wrong:** Each active simulation gets its own Python thread that, every 2 seconds, re-opens and
re-reads both platforms' `actions.jsonl` from the last seek position, rebuilds the state object, and
unconditionally rewrites the *entire* `run_state.json` (including up to 50 `recent_actions` entries) —
even if nothing changed since the last tick.

**Why it fails:** At 100 concurrently running simulations this is up to 50 full JSON
serialize+file-write operations per second sustained for the simulation's whole runtime, all competing
for the GIL and disk I/O, purely as fixed overhead independent of actual activity — measurable but not
catastrophic on its own; it compounds with CON-04 (unbounded request threads) and CON-08 (unlocked
shared state) to reduce the host's effective concurrency ceiling below what the hardware could otherwise
sustain.

**Proposed minimal fix:** Only rewrite `run_state.json` when the read position(s) actually advanced or
status changed; increase the poll interval adaptively when a simulation is idle between active rounds.

---

## CON-13 — MEDIUM — TRIBE's CUDA-health probe runs outside `_inference_lock`, contradicting the module's own thread-safety invariant

**File:** `tribe_scorer/main.py:420-435` (`_require_cuda_healthy`/`_check_cuda_health`, which calls
`torch.cuda.synchronize()` and allocates/frees a CUDA tensor), called at lines 491, 527, 598, 678 —
**before** `_inference_lock` is acquired in `_run_single_score`, `_run_batch_score`,
`_run_single_video_score`, `_run_single_audio_score`.

**What's wrong:** The module's own docstring states "the TRIBE model ... and its exca cache are NOT
thread-safe. If FastAPI dispatches overlapping requests to the thread pool, concurrent model.predict()
or cache access can crash. This lock ensures only one inference runs at a time" (lines 396-400) — but the
CUDA liveness probe deliberately runs *before* that lock is taken, so it executes concurrently with
another thread's in-flight, lock-protected inference.

**Why it fails:** Under concurrent load (multiple threadpool-executor threads hitting `/api/score*`
simultaneously — FastAPI's default executor permits up to `min(32, cpu_count()+4)` concurrent worker
threads before further requests queue), one thread's `torch.cuda.synchronize()` + tensor
alloc/dealloc in `_check_cuda_health()` runs while another thread is mid-`model.predict()` under the
lock, touching the same shared CUDA context/stream the lock was specifically introduced to protect.
This is a plausible (if lower-probability, since PyTorch's caching allocator has its own internal
locking) source of intermittent CUDA errors or corrupted inference under concurrency that would be very
hard to reproduce/diagnose after the fact.

**Proposed minimal fix:** Move `_require_cuda_healthy()` inside `with _inference_lock:` (accepting the
minor latency cost of not fast-failing before waiting for the lock), or use a separate dedicated lock
that both the health probe and inference acquire.

---

## CON-14 — LOW — TRIBE/MiroFish httpx clients rely on default connection-pool limits with very long per-request timeout overrides

**File:** `orchestrator/api/__init__.py:160-161` — `httpx.AsyncClient(base_url=..., timeout=300.0)` for
both `tribe_http` and `mirofish_http`, no `limits=httpx.Limits(...)` specified.

**What's wrong:** httpx's default `Limits(max_connections=100, max_keepalive_connections=20)` applies.
`tribe_client.py` overrides the per-request timeout up to `SCORE_TIMEOUT=5400s` for scoring calls, so a
held connection can occupy a pool slot for up to 90 minutes.

**Why it fails:** At exactly the target scale (100 concurrent users, each campaign potentially holding
one TRIBE connection open for the SCORE_TIMEOUT duration — see CON-03), the pool's `max_connections=100`
is right at the edge; any additional concurrent TRIBE call (health checks, audio/video scoring
alongside text scoring) beyond 100 in-flight would wait on the pool rather than being surfaced as an
explicit capacity error, making an already-severe queuing problem (CON-03) harder to diagnose because
it looks identical to "no connection available" vs. "GPU busy."

**Proposed minimal fix:** Set an explicit `httpx.Limits` sized to the concurrency budget you actually
intend to support, and prefer a distinct `httpx.PoolTimeout` short enough to fail fast and surface a
clear "TRIBE is at capacity" error rather than silently waiting alongside the GPU-lock queue.

---

## What breaks first at 100 users x 100 agents

**TRIBE's single, process-wide `threading.Lock` (`tribe_scorer/main.py:400`) turns the one shared GPU
into a hard, unconditional serialization point for every user's neural-scoring step, with zero admission
control anywhere in the call chain from `POST /api/campaigns` down to the TRIBE endpoint** (CON-03). The
moment more than a handful of the 100 users' campaigns reach `run_single_iteration`'s Step 3
simultaneously, every one of their TRIBE scoring calls queues behind that single lock — at even a
conservative ~30-90s per short, non-chunked text, 100 campaigns × 2 variants = 200 sequential inference
calls means the *last* campaign in the queue doesn't even start MiroFish simulation for 1.5-5+ hours,
against a documented single-campaign target of ≤20 minutes end-to-end. Unlike a crash, this failure is
silent and diagnostically confusing: no error is raised (the 5400s client-side timeout never trips), the
UI's SSE stream simply stops advancing past the "tribe" stage for 99 of 100 users, and nothing in the
system (health checks, logs, or the UI) distinguishes "still queued behind other users" from "hung." This
is also the *first* thing to manifest, chronologically — it gates entry to MiroFish (CON-05), so the
MiroFish-side subprocess-proliferation and Werkzeug-dev-server risks (CON-01/CON-02/CON-04) only get
exercised at whatever throttled rate the TRIBE queue happens to release campaigns, softening (but not
eliminating) their blast radius. The single highest-confidence prediction: **at 100 concurrent
campaigns, TRIBE scoring throughput collapses to one request at a time on one GPU, and the product
appears completely frozen to the overwhelming majority of users for hours, with no error surfaced
anywhere to explain why.**
