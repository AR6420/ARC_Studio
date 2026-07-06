# Track 4 — Resource Management & Leaks

Scope audited: `orchestrator/` (api, clients, engine, storage, cli.py), `tribe_scorer/main.py` +
`tribe_scorer/scoring/*.py`, `mirofish/backend/app/**` (services, storage, utils, api),
`mirofish/backend/scripts/*.py`. `mirofish/` internals and `tribe_scorer/vendor/tribev2` treated
as vendored/out-of-scope except for how our code calls them.

Findings are ordered most-severe first. Every finding cites exact `file:line` from the code as it
exists on disk right now.

---

## RES-01 — CRITICAL — Timed-out TRIBE inference leaves a zombie thread holding the GPU, and the outer lock releases anyway, permitting concurrent access to the documented-non-thread-safe model

**Files:**
- `tribe_scorer/scoring/text_scorer.py:66-95` (`_score_single_chunk`)
- `tribe_scorer/scoring/audio_scorer.py:194-220` (`score_audio`), `:255-279` (`score_audio_with_timeline`)
- `tribe_scorer/scoring/video_scorer.py:210-235` (`score_video`), `:276-294` (`score_video_with_timeline`)
- Caller: `tribe_scorer/main.py:396-400` (`_inference_lock`), `:496-513`, `:608-616`, `:687-693`

**What's wrong:** Every one of these functions does the same thing to bound inference latency:

```python
executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
future = executor.submit(_run_pipeline, path_or_text, model)
try:
    preds, _segments = future.result(timeout=timeout)
except concurrent.futures.TimeoutError:
    executor.shutdown(wait=False, cancel_futures=True)
    return _pseudo_score_from_...(...), True, ...   # or None for timeline
```

`cancel_futures=True` only cancels futures that have **not started running yet**. With
`max_workers=1` the single submitted future is already running (blocked inside
`model.get_events_dataframe(...)` / `model.predict(...)`, a synchronous, uninterruptible GPU call).
`executor.shutdown(wait=False, ...)` does not stop it — Python threads cannot be forcibly killed.
The worker thread keeps executing the vendor `TribeModel.predict()` call in the background
indefinitely (or until it errors/finishes on its own), still holding whatever CUDA tensors and exca
cache handles it allocated.

Meanwhile, in `main.py` this call happens **inside** `with _inference_lock:` (`text_scorer` path:
`main.py:496-513`; audio: `:687-693`; video: `:608-616`). As soon as the timeout fires and a pseudo
result is returned, the `with _inference_lock:` block exits and the lock is released — even though
the abandoned background thread is still mid-inference on the shared, singleton `TribeModel`
instance. The very next queued HTTP request acquires `_inference_lock` and calls
`model.predict()` again. `main.py`'s own docstring states the invariant this violates:

> "the TRIBE model (LLaMA 3.2-3B) and its exca cache are NOT thread-safe. If FastAPI dispatches
> overlapping requests to the thread pool, concurrent model.predict() or cache access can crash."
> (`tribe_scorer/main.py:396-399`)

A timeout is exactly the condition that produces this forbidden concurrent access.

**Why it fails (concrete repro):** Client sends a variant whose chunk takes longer than
`per_chunk_timeout` (900s default, `tribe_scorer/config.py:43`) — realistic under GPU contention
from queued concurrent requests, which is the normal state at 100-concurrent-user load. The chunk's
executor times out, `_score_single_chunk` returns pseudo scores while thread T1 (still running
`mdl.predict()`) is abandoned. Additionally, `text_scorer.py:94-95`'s `finally: Path(tmp_path).unlink(missing_ok=True)` deletes the temp `.txt` file the abandoned thread is still reading via
`get_events_dataframe(text_path=path)`, so T1 can also blow up mid-read on a file that no longer
exists. The caller (`main.py`) releases `_inference_lock` and returns HTTP 200 with pseudo scores.
The next request acquires the lock and starts a *second* concurrent `model.predict()` call (T2)
against the same model/cache while T1 is still in flight — the exact "concurrent model.predict()"
scenario the code comment warns will crash. Each additional timeout compounds: another zombie
thread, more never-freed VRAM (no `torch.cuda.empty_cache()` runs for the abandoned thread's
tensors — that only happens on the *next* chunk of the *next* successful call, `text_scorer.py:106-113`), and a growing chance of two threads corrupting the exca on-disk cache simultaneously
(`main.py:83-118`'s own stale-inflight-cleanup routine exists specifically because this class of
corruption happens).

**Blast radius at 100 users × 100 agents:** TRIBE is a *single shared GPU process* serialized by one
lock for the whole fleet. Under real concurrency, per-request queueing delay is unavoidable, which
makes hitting `per_chunk_timeout`/`audio_inference_timeout_seconds`/`video_inference_timeout_seconds`
(1800s, `config.py:48,56`) routine rather than rare. Every timeout leaks one more zombie GPU thread;
VRAM never comes back until/unless that thread happens to finish cleanly. This is a monotonically
growing VRAM leak on the one shared GPU, with a realistic path to CUDA OOM or a corrupted CUDA
context (which `main.py:403-417`'s own health check exists to detect) — taking down inference for
all 100 users at once.

**Minimal fix:** Do not release `_inference_lock` (or return a usable response) while the timed-out
worker thread is still alive. Either (a) block on `future.result()` with no timeout while holding the
lock and instead bound overall wall-clock via a *supervising* timeout that kills the whole worker
process (not thread) via a subprocess pool, or (b) keep holding `_inference_lock` until
`executor.shutdown(wait=True)` actually confirms the thread exited, accepting that a slow chunk
blocks the queue (which it already effectively does via the shared lock) instead of silently
returning while corruption is still possible. At minimum, do not delete the temp file
(`text_scorer.py:95`) until the abandoned thread is confirmed dead.

---

## RES-02 — HIGH — `SimulationRunner._monitor_threads` grows forever; per-simulation Thread objects are never removed or joined

**File:** `mirofish/backend/app/services/simulation_runner.py:222` (declaration),
`:462-468` (`cls._monitor_threads[simulation_id] = monitor_thread`)

**What's wrong:** `_monitor_threads` is a class-level dict populated once per simulation start. Grep
across the entire file shows zero `.pop()`, `del`, or `.join()` calls against it — `_processes`,
`_action_queues`, `_stdout_files`, and `_stderr_files` all get cleaned up somewhere (monitor thread's
`finally:`, `cleanup_all_simulations`), but `_monitor_threads` never does.

**Why it fails:** Every `POST /api/simulation/start` (`simulation.py:1446`) adds one entry that lives
for the remainder of the Flask process's uptime, regardless of whether the simulation later
completes, fails, or is stopped. The `Thread` object itself keeps its target function's closure
(`args=(simulation_id,)`) referenced, so nothing here is reclaimable by GC.

**Blast radius:** At "100 users × 100 agents", each orchestrator campaign iteration triggers a fresh
MiroFish simulation per content variant (`orchestrator/engine/mirofish_runner.py:89-95` calls
`run_simulation` sequentially per variant, and the orchestrator runs multiple iterations per
campaign). Across many users and iterations over the life of the MiroFish backend process, this is
thousands of entries that never shrink — a straightforward, unbounded memory leak, exactly the
"threads never joined ... dict entries never evicted" pattern called out in this track's brief.

**Minimal fix:** In the monitor thread's own `finally:` block (`simulation_runner.py:553-579`,
alongside the existing `_processes.pop`/`_action_queues.pop`/file-handle cleanup), add
`cls._monitor_threads.pop(simulation_id, None)`. Also add the same cleanup to
`cleanup_simulation_logs` (`:1101-1179`) for the forced-restart path.

---

## RES-03 — HIGH — `SimulationRunner._run_states` (and `SimulationManager._simulations`) are never evicted on normal completion — unbounded in-memory growth

**Files:**
- `mirofish/backend/app/services/simulation_runner.py:219` (`_run_states` declaration), `:230-239`
  (`get_run_state` populates it on load), `:297-309` (`_save_run_state` also writes it on every
  status update), `:1170-1171` (the *only* place an entry is ever deleted — inside
  `cleanup_simulation_logs`, an explicit admin/"force restart" operation, never called on normal
  completion)
- `mirofish/backend/app/services/simulation_manager.py:136` (`_simulations` declaration), `:154`,
  `:190` (populated on every save/load), `:465-481` (`list_simulations` walks
  `SIMULATION_DATA_DIR` and force-loads **every simulation that has ever existed on disk** into this
  dict the first time anyone calls `GET /api/simulation/list`)

**What's wrong:** Both class-level caches are write-only from the perspective of a completed
simulation's normal lifecycle. `_run_states` accumulates one `SimulationRunState` (which itself
holds up to 50 `AgentAction` records plus a `rounds: List[RoundSummary]`) per simulation ID for the
life of the process. `_simulations` similarly accumulates one `SimulationState` per simulation ID,
and `list_simulations()` actively *forces* every historical simulation directory under
`uploads/simulations/` to be loaded and cached in memory the moment the list endpoint is hit once.

**Why it fails:** Neither dict is ever bounded or LRU-evicted. A long-running MiroFish backend
process that has serviced many campaigns will hold state for every simulation it has ever run, even
long after the simulation completed/failed/was stopped and its result was already persisted to disk
and consumed by the orchestrator.

**Blast radius at 100 users × 100 agents:** Sustained operation (the target scale implies many
campaigns run back-to-back, each spawning ≥1 simulation per variant per iteration) means these two
dicts grow monotonically with total simulations ever run, not concurrently-active simulations. This
is memory growth proportional to *lifetime* traffic, which for a service meant to run continuously
will eventually exhaust available RAM.

**Minimal fix:** Evict from `_run_states`/`_simulations` once a simulation reaches a terminal status
(`COMPLETED`/`FAILED`/`STOPPED`) and some grace period has passed (or once the orchestrator has
fetched final results), not only on the explicit `cleanup_simulation_logs` admin path. Consider an
LRU cap independent of terminal-status logic as a backstop.

---

## RES-04 — HIGH — Seven `sqlite3.connect()` call sites across the MiroFish scripts/API close the connection only on the happy path — any exception leaks the connection and its OS file handle

**Files (all identical pattern: `conn = sqlite3.connect(...)` then `conn.close()` inside the same
`try`, with no `finally`, so any exception between the two skips the close):**
- `mirofish/backend/scripts/run_parallel_simulation.py:531-553` (`_get_interview_result`) — **called
  from every interview command handled by the running subprocess**
- `mirofish/backend/scripts/run_parallel_simulation.py:682-746` (`fetch_new_actions_from_db`) — **called once per simulation round from the main per-round polling loop** (`:1256-1259`, and again
  `:1456` for the other platform loop)
- `mirofish/backend/scripts/run_twitter_simulation.py:314-336` (`_get_interview_result`)
- `mirofish/backend/scripts/run_reddit_simulation.py:314-336` (`_get_interview_result`, same shape)
- `mirofish/backend/app/services/simulation_runner.py:1656-1712`
  (`_get_interview_history_from_db`, called from the `GET /api/simulation/interview/history` path)
- `mirofish/backend/app/api/simulation.py:2018-2039` (`get_simulation_posts`) — inner `try/except
  sqlite3.OperationalError` only catches *that* exception class; any other exception (e.g. a
  `dict(row)` conversion error, a corrupted row) skips `conn.close()` at line 2039 entirely and
  propagates to the outer handler
- `mirofish/backend/app/api/simulation.py:2091-2116` (`get_simulation_comments`) — same shape

**Why it fails:** `fetch_new_actions_from_db` runs on **every simulation round**, reading from the
same SQLite file that the OASIS environment's own writer is concurrently writing to
(`twitter_simulation.db`/`reddit_simulation.db`). Concurrent writer + reader against one SQLite file
is the textbook trigger for `sqlite3.OperationalError: database is locked` — which is exactly the
kind of exception this code does *not* guard with a `finally`. Each lock-contention hit during a
simulation's lifetime leaks one more open connection/file handle; the leaked handles increase the
odds of the *next* poll also hitting contention (more open handles against the same file), so the
failure mode is self-reinforcing rather than self-correcting. On Windows (the project's primary dev
target per `tribe_scorer/config.py`'s `MAX_PATH` workaround and `CLAUDE.md`), a still-open
`sqlite3.Connection` also blocks later attempts to delete/replace the same `.db` file, so
`SimulationRunner.cleanup_simulation_logs()` (`simulation_runner.py:1148-1155`,
`os.remove(file_path)`) can start failing with `PermissionError: [WinError 32]` for a simulation that
leaked a connection earlier in its life.

**Blast radius at 100 users × 100 agents:** Many concurrent simulations, each independently polling
its own DB every round for the duration of the run (rounds can number in the dozens to hundreds per
simulation, per `total_rounds = total_hours * 60 / minutes_per_round`,
`simulation_runner.py:350-353`), each with its own OASIS writer contending for the same file. Lock
contention under concurrent read/write at this call frequency is the norm, not the exception, so
this leak is expected to trigger repeatedly across the fleet, not as a rare edge case.

**Minimal fix:** Wrap every one of the seven call sites in `try/finally: conn.close()` (or
`with sqlite3.connect(...) as conn:`, noting that SQLite's context-manager form only auto-commits/
-rollbacks and does **not** auto-close — `contextlib.closing(sqlite3.connect(...))` is the correct
idiom). Also widen `get_simulation_posts`/`get_simulation_comments`'s inner `except` to guarantee
`conn.close()` regardless of exception type.

---

## RES-05 — HIGH — `ClaudeClient._refresh_client()` replaces the shared Anthropic client on every 401 without closing the old one

**File:** `orchestrator/clients/claude_client.py:154-164` (`_refresh_client`), constructed once and
shared across all requests via `orchestrator/api/__init__.py:180` (`app.state.claude_client =
build_llm_client()`)

**What's wrong:**

```python
def _refresh_client(self) -> None:
    ...
    self._env_key_failed = True
    self._client = self._build_client()
```

`self._client` was an `AsyncAnthropic` instance (wraps its own `httpx.AsyncClient` connection pool).
Reassigning it drops the only reference to the old client without ever calling `.close()`/`.aclose()`
on it. `httpx.AsyncClient` has no reliable synchronous `__del__` that tears down its async transport,
so the old pool's open sockets are only reclaimed on a best-effort basis by garbage collection (and
potentially not at all if the event loop has moved on).

**Why it fails:** `app.state.claude_client` is a **single instance shared by every concurrent user**
of the orchestrator (constructed once at startup, never per-request). This project's own tooling
(`scripts/refresh-env.sh`, `_refresh_litellm_api_key()` in `orchestrator/api/__init__.py:28-122`)
treats OAuth token rotation as a routine, expected event, not a rare failure — meaning
`_refresh_client()` fires periodically in normal operation, and each firing discards one client's
worth of pooled connections without closing them.

**Blast radius at 100 users × 100 agents:** Every rotation event leaks a connection pool shared by
the whole fleet; over the process's lifetime this accumulates unclosed sockets/file descriptors.
Combined with the fact that any request that was mid-flight on the *old* client at refresh time has
no coordinated drain, this is both a resource leak and a minor correctness risk (in-flight calls on
a client whose credentials are already known-stale).

**Minimal fix:** Before reassigning `self._client`, capture the old reference and schedule
`await old_client.close()` (fire-and-forget via `asyncio.create_task`, since `_refresh_client` itself
is synchronous) once any in-flight requests using it have had a chance to finish, or at minimum call
`old_client.close()` synchronously-best-effort immediately after reassignment.

---

## RES-06 — MEDIUM — `app.state.progress_history` per-campaign entries are never evicted despite the code comment claiming otherwise

**Files:** `orchestrator/api/campaigns.py:371-380` (creates `progress_history[campaign.id] = []` and
appends up to `HISTORY_CAP = 500` events per campaign), `orchestrator/api/progress.py:37-49`
(`cleanup_queue` — its docstring explicitly says *"The campaign-store completion path is responsible
for evicting it [progress_history] when the campaign reaches a terminal state"*)

**What's wrong:** Grepping the whole `orchestrator/` tree for `progress_history` turns up exactly
three references — the two writes in `campaigns.py` and the one read in `progress.py`. No code
anywhere pops a campaign's key out of `app.state.progress_history`. The comment describing where
the eviction supposedly happens ("the campaign-store completion path") does not correspond to any
code that exists.

**Why it fails:** Each auto-started campaign gets a list capped at 500 events, but the *dict entry
itself* — one per campaign, forever — is never removed, even long after the campaign reaches
`completed`/`failed` and all SSE clients have disconnected (`cleanup_queue` only pops
`progress_queues`, not `progress_history`).

**Blast radius at 100 users × 100 agents:** Every campaign ever auto-started leaves a
(bounded-per-entry but unbounded-in-count) list behind for the life of the orchestrator process.
With many users running many campaigns over time, this grows without bound.

**Minimal fix:** Pop `app.state.progress_history[campaign_id]` once the campaign reaches a terminal
status inside `CampaignRunner.run_campaign`'s completion path (`orchestrator/engine/campaign_runner.py:630-660`), or apply the same bounded-map/TTL eviction strategy already used for
`progress_queues`.

---

## RES-07 — MEDIUM — Orphaned IPC response files accumulate forever on interview timeout

**File:** `mirofish/backend/app/services/simulation_ipc.py:116-186` (`send_command`)

**What's wrong:** On success, the response file is deleted (`:164-166`). On timeout, only the
**command** file is removed (`:180-184`); the code has no mechanism to later delete a **response**
file that the simulation subprocess writes *after* the Flask-side timeout has already elapsed —
which is a real race under load, since a subprocess busy processing many interview commands can
easily exceed a caller's `timeout` (default 60-180s depending on caller,
`simulation_runner.py:1432,1495,1554`).

**Why it fails:** Nothing else in the codebase ever reads or deletes an orphaned
`ipc_responses/<uuid>.json` file once its corresponding `send_command()` call has already timed out
and returned. Files accumulate in `sim_dir/ipc_responses/` indefinitely.

**Blast radius:** Small individual files, but unbounded count over a simulation's (and the whole
fleet's) lifetime, compounding with RES-08's total absence of simulation-directory cleanup.

**Minimal fix:** On timeout, still attempt to delete the response file if it later appears (e.g., a
short best-effort grace-period cleanup pass, or a periodic sweep of `ipc_responses/` for files older
than their corresponding command's timeout).

---

## RES-08 — MEDIUM — No delete/cleanup endpoint for MiroFish simulation data anywhere; per-simulation directories persist on disk forever

**File:** `mirofish/backend/app/api/simulation.py` (full route list at top of file — no `DELETE`
verb exists anywhere in the blueprint); `mirofish/backend/app/services/simulation_runner.py:1101-1179` (`cleanup_simulation_logs`) is the only cleanup path and is opt-in/admin-only (used for
"force restart"), and even it explicitly preserves config/profile files and never removes the
simulation's directory, `ipc_commands/`, or `ipc_responses/` subfolders.

**Why it fails:** Every simulation ever created leaves its full directory (profiles JSON/CSV,
`simulation_config.json`, per-platform `actions.jsonl`, `*_simulation.db`, `simulation.log`,
`run_state.json`, IPC folders) on disk permanently. There is no TTL, no rotation job, and no bulk
"delete old simulations" endpoint.

**Blast radius at 100 users × 100 agents:** Sustained operation with many campaigns/simulations over
time means unbounded disk growth with no eviction path — this will eventually fill the disk on
whatever host runs the MiroFish backend, taking down every user's simulations at once (SQLite writes
failing, log writes failing) rather than degrading gracefully.

**Minimal fix:** Add a `DELETE /api/simulation/{id}` endpoint that removes the whole
`uploads/simulations/{id}/` tree, and/or a scheduled janitor that removes simulations older than N
days. The orchestrator side already has an analogous, working pattern to copy: `orchestrator/api/campaigns.py:420-460`'s `delete_campaign` unlinks the associated uploaded media file on cascade
delete.

---

## RES-09 — MEDIUM — Deleting a campaign mid-run does not cancel its background asyncio task

**Files:** `orchestrator/api/campaigns.py:420-460` (`delete_campaign`), `:383-398`
(`_run_background`/`app.state.running_tasks`)

**What's wrong:** `delete_campaign` deletes the campaign's DB row (with `ON DELETE CASCADE` for
iterations/analyses) and best-effort unlinks its media file, but never checks
`app.state.running_tasks` for a task still running against that `campaign_id`, and never calls
`task.cancel()`.

**Why it fails:** If a user deletes a campaign while its background `run_campaign()` task
(`campaigns.py:383-398`) is still executing, that task keeps running — still calling TRIBE, MiroFish,
and the LLM client — for a campaign that no longer exists in the database. Its next
`self._store.save_iteration(...)` call attempts an `INSERT` referencing a now-nonexistent
`campaign_id` foreign key (`orchestrator/storage/database.py:93` has `PRAGMA foreign_keys=ON`),
raising an `IntegrityError` that is caught by the broad `except Exception` in
`CampaignRunner.run_single_iteration` (`orchestrator/engine/campaign_runner.py:442-446`) and
`run_campaign` (`:576-585`), which do eventually terminate the task (so it's not a *permanent* leak
of the task itself) — but only after burning a full TRIBE scoring pass and/or a full MiroFish
simulation (potentially the most GPU/LLM-expensive parts of the pipeline) for data nobody can ever
see again.

**Blast radius at 100 users × 100 agents:** Every "delete while running" click wastes a full
GPU/LLM-costed pipeline iteration that was already contended for by 99 other users, directly
increasing queueing delay for everyone else — this interacts with RES-01 by increasing the chance of
hitting TRIBE's `per_chunk_timeout`.

**Minimal fix:** In `delete_campaign`, look up and `cancel()` any entry in
`request.app.state.running_tasks` for `campaign_id` before deleting the row (mirroring the shutdown
cleanup already done in `orchestrator/api/__init__.py:215-221`).

---

## RES-10 — MEDIUM — `_monitor_simulation`'s early-return path skips all cleanup, leaving an untracked, unmonitored subprocess and (if enabled) an unstoppable graph-memory worker thread

**File:** `mirofish/backend/app/services/simulation_runner.py:480-579`

**What's wrong:**

```python
process = cls._processes.get(simulation_id)
state = cls.get_run_state(simulation_id)

if not process or not state:
    return          # <-- before the try/finally block that does all cleanup
```

If this guard fires, the function returns before ever reaching the `try:` at `:498` — so the
`finally:` block at `:553-579` (which pops `_processes`, `_action_queues`, closes and pops
`_stdout_files`/`_stderr_files`, and stops any `GraphMemoryManager` updater via `_graph_memory_enabled`) never executes.

**Why it fails:** The subprocess was already registered in `_processes[simulation_id]`
(`:458`, before the monitor thread is even started at `:462-468`), and its log file handle was
already stashed in `_stdout_files[simulation_id]` (`:453`) — both *before* the monitor thread runs.
If `get_run_state(simulation_id)` returns `None` on this first call (e.g., a transient read failure
right after `_save_run_state` just wrote the file, or a state-file corruption edge case), the
subprocess becomes permanently unmonitored: nobody polls its action logs, nobody updates
`run_state.json` again, and — if `enable_graph_memory_update=True` — the `GraphMemoryUpdater`'s
background worker thread (`graph_memory_updater.py:234-236`, `daemon=True`) and its Neo4j-writing
`Queue` are never told to stop, since `GraphMemoryManager.stop_updater()` is only called from this
same skipped `finally:` block or from `stop_simulation()` (which a user has no reason to call for a
simulation the UI now shows no progress for).

**Blast radius:** Low probability per-simulation, but at "100 concurrent simulations" scale the
absolute number of chances for this race to fire is much higher, and each occurrence leaves a
process + a background thread genuinely un-managed until process-wide shutdown (`cleanup_all_simulations`, which *does* still terminate it, so this is bounded by app lifetime, not permanent — but "the running app has a silently-orphaned, still-billing-GPU-and-LLM subprocess with zero way to see or stop it short of a server restart" is still a real operational hazard).

**Minimal fix:** Move the `if not process or not state: return` guard's minimal cleanup (or simply
restructure so `_processes`/`_stdout_files` entries are only added once we're sure a monitor will run)
so that no path can leave a tracked-but-unmonitored process.

---

## RES-11 — LOW — Ad hoc `httpx.AsyncClient()` instances created per health-check call instead of reusing the injected shared client

**Files:** `orchestrator/clients/mirofish_client.py:101-110` (`health_check`), `:147-156`
(`verify_llm_token`), `:183-192` (`_attempt_token_refresh`), `:232` (`get_neo4j_stats`);
`orchestrator/api/health.py:58-61` (LiteLLM probe inside `/api/health`)

**What's wrong:** Each of these opens a brand-new `httpx.AsyncClient()` via `async with`, instead of
reusing `app.state.mirofish_http`/`app.state.tribe_http` (already injected for exactly this purpose
per the module docstring's "shared connection pool" design). Each is properly closed by the `async
with` block, so this is not a leak — but it discards connection reuse and re-does TLS/TCP setup on
every call.

**Why it matters at scale:** `/api/health` is a typical dashboard-polling endpoint; at "100
concurrent users" polling it periodically, this needlessly creates and tears down a fresh connection
pool on every single poll rather than reusing a keep-alive connection — pure overhead, not a
leak.

**Minimal fix:** Thread the already-injected shared client (or a small persistent client held on
`MirofishClient`) through these methods instead of constructing throwaway ones per call.

---

## RES-12 — LOW — exca inference cache grows without any eviction policy

**Files:** `tribe_scorer/config.py:25-30` (`cache_folder`, defaults to `C:\tc` on Windows),
`tribe_scorer/main.py:83-119` (`_clean_stale_inflight_records` — only purges *in-flight tracking*
rows, never the cached artifacts themselves)

**What's wrong:** Our own code configures and depends on the exca on-disk cache but implements no
eviction/expiry for the cached inference artifacts themselves, only for the stale "in-flight" SQLite
tracking rows left behind by crashes.

**Why it matters:** At high variant throughput (100 users each generating and scoring many distinct
content variants), the cache directory grows unboundedly over the service's uptime. This is by
design a cache (correctness is unaffected), so severity is low, but it is unbounded disk growth with
no operational knob provided by our code to cap it.

**Minimal fix:** Add a size- or age-based eviction sweep for `cache_folder` at startup or on a timer,
alongside the existing stale-inflight cleanup.

---

## Severity summary

| Sev | Count |
|-----|-------|
| CRITICAL | 1 |
| HIGH | 4 |
| MEDIUM | 5 |
| LOW | 2 |

---

## What breaks first at 100 users × 100 agents

**RES-01 (TRIBE zombie inference thread on timeout) breaks first, and it breaks the whole fleet at
once, not just one user's request.**

TRIBE v2 is a *single process on a single GPU*, and all inference across all 100 concurrent users is
serialized through one `threading.Lock` (`main.py:400`). Under real concurrent load, per-request
queueing delay is unavoidable — with 100 users each triggering multi-variant, multi-iteration
campaigns, requests *will* queue behind the shared lock long enough to hit the 900s/1800s per-chunk
and per-media timeouts routinely, not as a rare edge case. Every timeout leaves a zombie thread still
executing `model.predict()` in the background while the lock is released and the *next* request
starts a second, concurrent `model.predict()` call against the same singleton model — the exact
scenario the codebase's own comment says "can crash." Layer in that the timed-out chunk's temp input
file is deleted out from under the still-running zombie thread (`text_scorer.py:95`), and that GPU
memory the zombie thread holds is never reclaimed until it happens to finish, and you get a
monotonic VRAM leak plus a rising probability of a hard crash or CUDA-context corruption (which
`main.py`'s own health check exists to detect) as load increases. Because TRIBE is a single shared
GPU dependency for every campaign in the system, this is a single point of failure: once it crashes
or its CUDA context goes stale, *every* user's in-flight and future campaigns lose neural scoring
simultaneously (graceful degradation kicks in per D-05, but the "differentiated, ranked variants"
value proposition of the whole product disappears for everyone at once). This will be the first
thing to visibly break as concurrent load ramps toward 100 users, well before the MiroFish
dict/file-count leaks (RES-02/03/04/07/08) accumulate enough to matter — those degrade slowly over
days of uptime, whereas RES-01 can be triggered within the first sustained burst of concurrent
campaigns.
