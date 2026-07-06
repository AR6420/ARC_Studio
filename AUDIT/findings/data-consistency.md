# Track 6 — Data Layer & Consistency

Scope audited: `orchestrator/storage/database.py`, `orchestrator/storage/campaign_store.py`,
`orchestrator/engine/campaign_runner.py`, `orchestrator/api/campaigns.py`, `orchestrator/api/progress.py`,
`mirofish/backend/app/storage/{neo4j_storage,graph_storage,neo4j_schema}.py`,
`mirofish/backend/app/services/{simulation_manager,simulation_runner,graph_memory_updater,oasis_profile_generator}.py`,
`mirofish/backend/app/api/simulation.py` (OASIS sqlite read paths).

Findings are ordered most-severe first. Each cites exact `file:line`.

---

## DATA-01 — CRITICAL
**`cleanup_orphaned_campaigns()` blanket-fails every `running` campaign for every user on any process restart**

`orchestrator/storage/campaign_store.py:75-97`, wired at `orchestrator/api/__init__.py:157-169`, combined with the shutdown handler at `orchestrator/api/__init__.py:215-220`.

```python
async def cleanup_orphaned_campaigns(self) -> int:
    ...
    UPDATE campaigns SET status = 'failed', error = 'Orphaned — no heartbeat (cleaned on startup)', ...
    WHERE status = 'running'
```

This runs unconditionally at every orchestrator startup, with no scoping by owner/user/worker-instance — it matches on `status='running'` globally. At the same time, the lifespan shutdown handler (`api/__init__.py:216-220`) unconditionally `task.cancel()`s **every** entry in `app.state.running_tasks` on any shutdown (SIGTERM from a deploy, a supervisor restart, an OOM-triggered restart caused by TRIBE/Ollama sharing the single GPU per the project's own hardware constraint).

**Why it fails at 100 users x 100 agents**: with 100 concurrent users each running campaigns that legitimately take many minutes (project's own SLA: "40 agents, 4 iterations must complete in <=20 minutes" — so 100-agent campaigns will run longer), a single process restart (deploy, crash from a downstream TRIBE/MiroFish failure, container OOM) cancels every in-flight asyncio task for every user simultaneously, then the next boot's `cleanup_orphaned_campaigns()` marks all of them `'failed'` — discarding potentially tens of minutes of GPU/LLM compute for the entire user base in one shot, with no way to resume. This is a designed behavior, not an accidental race, and it was written for the Phase-1 single-user POC assumption explicitly stated in `CLAUDE.md` ("Phase 1 POC: single-user, local machine") — it does not scale to multi-tenant concurrent use.

**Fix**: give campaigns an explicit heartbeat/lease and only fail rows whose heartbeat is stale (not merely `status='running'`); or partition by a worker-instance id so a restart only reaps that instance's own orphans; ideally persist enough iteration state that a restarted worker can resume a campaign rather than failing it outright.

---

## DATA-02 — HIGH
**Unsynchronized read-modify-write race between the simulation monitor thread and request-handling threads on `SimulationRunState`**

`mirofish/backend/app/services/simulation_runner.py:480-580` (`_monitor_simulation`) vs. `mirofish/backend/app/services/simulation_runner.py:774-820` (`stop_simulation`).

`_run_states: Dict[str, SimulationRunState]` (line 219) is a **class-level** dict; `get_run_state()` (230-239) returns the same live object reference to every caller — there is no copy and no lock. The monitor thread loops every 2 seconds mutating `state.current_round`, `state.twitter_completed`, etc. and calling `cls._save_run_state(state)` (line 513) for the entire lifetime of the simulation. Concurrently, a Flask request thread calling `stop_simulation()` sets `state.runner_status = STOPPING` (784), terminates the subprocess (791), then sets `state.runner_status = STOPPED` (804-808) on the **same object**.

**Concrete race**: the instant the subprocess is terminated, the monitor thread's own loop condition `while process.poll() is None` (499) also becomes false (from either thread's own process.poll() call), causing the monitor thread to independently fall into its "process ended" branch (517-545): it reads `exit_code = process.returncode` — for a SIGTERM/taskkill-terminated process this is non-zero — so it sets `state.runner_status = RunnerStatus.FAILED` with `state.error = f"Process exit code: {exit_code}..."` (529-540) and calls `cls._save_run_state(state)` (545). This runs concurrently with `stop_simulation()`'s own final `state.runner_status = STOPPED; ...; cls._save_run_state(state)` (804-808). Whichever thread's write lands last wins — the user-initiated "stopped" outcome can be silently overwritten with a confusing "failed, exit code -15" status, or vice versa, non-deterministically. There is no lock anywhere in this class guarding `SimulationRunState` mutation or the `_save_run_state` file write.

**Why it matters at 100 x 100 scale**: every running simulation has its own monitor thread hammering `_save_run_state` every 2s for the simulation's full duration; any stop/query request landing during that window races. At 100 concurrent simulations this is not a rare edge case, it is a near-certain occurrence for any user who stops a simulation while it's running.

**Fix**: introduce a `threading.Lock` per simulation (or one shared lock keyed by `simulation_id`) guarding all reads/mutations/saves of a given `SimulationRunState`; have `stop_simulation()` signal the monitor thread to exit its loop (e.g. an `Event`) rather than relying on `process.poll()` racing between two independent threads.

---

## DATA-03 — HIGH
**`run_state.json` / `state.json` are written with a plain `open(path, 'w')` — no atomic temp-file+rename — so a crash mid-write corrupts simulation state**

`mirofish/backend/app/services/simulation_runner.py:298-309` (`_save_run_state`), `mirofish/backend/app/services/simulation_manager.py:144-154` (`_save_simulation_state`), and the ad-hoc rewrite in `simulation_runner.py:1246-1252` (`cleanup_all_simulations`'s direct `state.json` patch).

```python
with open(state_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

None of these use write-to-temp-then-`os.replace()`. If the process is killed (OOM-killed subprocess supervisor, container restart, `SIGKILL` from an operator) or the disk write is interrupted while `json.dump` is mid-flush, the file is left truncated/invalid. The read path (`_load_run_state`, lines 242-295) catches the resulting `json.JSONDecodeError`/`Exception` broadly and returns `None` (line 293-295), which callers treat as "simulation state doesn't exist" — a silent, permanent loss of that simulation's run state, with no way to recover the last-known-good status short of manually deleting and re-running.

**Why it matters at scale**: `_save_run_state` is called every ~2 seconds per running simulation (line 513-514) for the simulation's whole lifetime. With 100 concurrent simulations, that's on the order of 50 writes/sec system-wide, each one a window during which any process-level termination event corrupts that simulation's persisted state.

**Fix**: write to `f"{state_file}.tmp"` then `os.replace(tmp, state_file)` (atomic on POSIX and Windows via `os.replace`) in all three save paths.

---

## DATA-04 — HIGH
**Neo4j `Entity` MERGE key has no backing uniqueness constraint — concurrent writers to the same graph create duplicate entities**

`mirofish/backend/app/storage/neo4j_storage.py:249-277` (the `_merge_entity` Cypher) vs. `mirofish/backend/app/storage/neo4j_schema.py:7-21` (only `graph_uuid`, `entity_uuid`, `episode_uuid` are declared unique).

```cypher
MERGE (n:Entity {graph_id: $gid, name_lower: $name_lower})
ON CREATE SET n.uuid = $uuid, ...
```

The dedup key is `(graph_id, name_lower)`, but there is **no unique constraint or index on that composite** — only `n.uuid` (which is freshly generated per call and therefore always "unique," providing no dedup protection at all) is constrained. Per Neo4j's own documented semantics, `MERGE` only guarantees no duplicate creation under **concurrent** transactions when a matching uniqueness constraint exists; without one, two concurrent transactions can both evaluate the `MATCH` half of the `MERGE` before either commits, see no existing node, and both execute the `CREATE` half — producing two `Entity` nodes with the same `(graph_id, name_lower)`.

**Why it's reachable at 100 x 100 scale**: `graph_memory_updater.py` (see DATA-11) runs one independent worker thread **per simulation**, each periodically calling `storage.add_text(graph_id, ...)` against whatever graph the simulation is configured for. Any two simulations/uploads that target the same `graph_id` concurrently (shared project graph reused across users/sims, or concurrent `add_text_batch` calls from parallel document ingestion) race on this exact MERGE pattern.

**Fix**: `CREATE CONSTRAINT entity_graph_namelower IF NOT EXISTS FOR (n:Entity) REQUIRE (n.graph_id, n.name_lower) IS UNIQUE` (Neo4j 5.x supports composite node key/uniqueness constraints), then let `MERGE` rely on it.

---

## DATA-05 — HIGH
**`add_text()` ingestion is not atomic — an episode is marked `processed: true` even when the entity/relation write loop fails partway**

`mirofish/backend/app/storage/neo4j_storage.py:176-350`.

The episode node is created first and unconditionally stamped `processed: true` (lines 214-231), *before* the per-entity `MERGE` loop (233-292) and per-relation `CREATE` loop (294-347) run. Each entity MERGE, each label SET, and each relation CREATE is its own separate `session.execute_write` (i.e., its own independent Neo4j transaction) — there is no single transaction wrapping the whole ingestion. If an exception occurs partway through the entity/relation loops (network blip to Neo4j, an embedding-service exception not caught by the `try/except` at 202-206 propagating from a different call site, a Neo4j `TransientError` exhausting all 3 retries in `_call_with_retry`), the exception propagates out of `add_text` — but the `Episode` node created at the top is already committed with `processed: true`, and whatever entities/relations were merged before the failure remain, permanently mixed with the ones that never got created.

**Why it matters**: there is no way to detect or re-run a partially-ingested episode — `processed: true` is supposed to mean "fully processed," but nothing rolls it back. At 100×100 scale, `graph_memory_updater.py`'s worker threads call this path continuously (every `BATCH_SIZE=5` activities, `graph_memory_updater.py:298`), so transient Neo4j overload under concurrent multi-simulation load will produce a steady trickle of permanently-inconsistent episodes.

**Fix**: wrap the whole `add_text` body (episode + entities + relations) in a single explicit transaction (`session.execute_write` around one function that does all the `tx.run` calls), and only mark/create the episode as processed after the transaction commits successfully.

---

## DATA-06 — HIGH
**No `PRAGMA busy_timeout`, and a second process (`orchestrator/cli.py`) opens an independent connection to the same SQLite file**

`orchestrator/storage/database.py:87-97` (`connect()` sets `journal_mode=WAL` and `foreign_keys=ON` but never sets `busy_timeout`), and `orchestrator/cli.py:89-90` which does `db = Database(str(settings.database_path_absolute)); await db.connect()` — a **second, independent** `aiosqlite.Connection` to the exact same file path used by the FastAPI server (`orchestrator/api/__init__.py:157`).

Within a single orchestrator process, all `db.conn.execute()` calls funnel through one shared `aiosqlite.Connection`, which serializes internally (no intra-process lock contention). But the module never issues `PRAGMA busy_timeout=<N>`, relying implicitly on whatever the stdlib `sqlite3.connect()` default happens to be. The moment a second OS process opens its own connection to the same file — which the codebase itself does via `cli.py`, and which is also the natural way to add throughput for 100 concurrent users (`uvicorn --workers N`, or horizontally-scaled replicas sharing one SQLite file/volume) — SQLite's single-writer-at-a-time lock becomes a real, cross-process contention point. Without an explicit, generous `busy_timeout`, a writer collision surfaces as `sqlite3.OperationalError: database is locked`, which is **not caught anywhere** in `campaign_store.py` — it propagates up through `run_single_iteration`'s `except Exception` (`campaign_runner.py:442-446`) and marks the whole campaign `'failed'` with that raw error message.

**Why it matters at scale**: this is the single most standard way an operator would try to scale this exact service to "100 concurrent users" (add workers/replicas), and doing so with the current code turns ordinary write contention into hard campaign failures.

**Fix**: `await self._conn.execute("PRAGMA busy_timeout=10000")` (or higher) right after enabling WAL; more importantly, if horizontal scaling is a real target, move off a single-file SQLite writer (e.g., one writer process + queue, or Postgres) rather than relying on WAL alone.

---

## DATA-07 — HIGH
**Per-variant iteration writes are not transactional — a crash/cancel mid-loop leaves a permanently "complete-looking" but partial iteration**

`orchestrator/engine/campaign_runner.py:319-333`.

```python
for i, variant in enumerate(variants):
    ...
    await self._store.save_iteration(campaign_id=campaign_id, iteration_number=iteration_number, variant_id=variant["id"], ...)
```

Each call to `save_iteration` (`campaign_store.py:289-329`) is its own `INSERT` + `commit()` — there is no transaction spanning the whole per-iteration variant loop. If the surrounding task is cancelled (the lifespan shutdown handler cancels every running task unconditionally, `orchestrator/api/__init__.py:216-219`; DELETE-during-run per DATA-08 also indirectly triggers this) or an exception is raised between two `save_iteration` calls, the DB permanently retains a row for variant 1 of that iteration but not variant 2 (or 3) — with **no column or marker anywhere indicating the iteration is incomplete**. `get_iterations()` (`campaign_store.py:331-350`) and everything downstream (`find_best_composite`, the report generator) has no way to distinguish "this iteration's variant set is complete" from "this iteration was cut short," and will silently treat the partial set as the full iteration.

**Fix**: wrap the per-iteration variant-save loop in a single explicit `BEGIN`/`COMMIT` (or at minimum write an iteration-level "started"/"complete" marker row) so partial writes are either rolled back or clearly flagged.

---

## DATA-08 — HIGH
**`DELETE /campaigns/{id}` does not cancel the associated running background task**

`orchestrator/api/campaigns.py:420-460`.

The handler looks up media info, deletes the campaign row (which cascades to `iterations`/`analyses` via `ON DELETE CASCADE`), and returns 204 — but it never touches `request.app.state.running_tasks[campaign_id]`. If a campaign is mid-execution when a user deletes it, its background `asyncio.Task` (`campaigns.py:383-397`) keeps running: it continues invoking TRIBE/MiroFish/Claude (wasting GPU/API budget) and, on its next `save_iteration`/`save_analysis` call, now attempts an `INSERT` referencing a `campaign_id` that `foreign_keys=ON` (`database.py:93`) will reject with an `IntegrityError` — which is swallowed by the generic `except Exception` in `run_single_iteration` (`campaign_runner.py:442-446`) and converted into `update_campaign_status(campaign_id, "failed", ...)`, a no-op `UPDATE ... WHERE id = ?` against a row that no longer exists. The failure is invisible; the task and its GPU/LLM work is simply wasted, and `running_tasks`/the SSE progress queue for that id linger until the task naturally errors out.

**Fix**: on delete, look up and `task.cancel()` any entry in `app.state.running_tasks[campaign_id]` (and drop the progress queue) before deleting the row.

---

## DATA-09 — MEDIUM
**Tailing an actively-growing `actions.jsonl` can silently drop or corrupt the last action record read**

`mirofish/backend/app/services/simulation_runner.py:581-689` (`_read_action_log`).

```python
with open(log_path, 'r', encoding='utf-8') as f:
    f.seek(position)
    for line in f:
        ...
    return f.tell()
```

Python's line iteration returns a trailing chunk with no `\n` as a final "line" when it hits EOF. If the OASIS subprocess (writer) has flushed only part of a JSONL record when this reader hits EOF, that partial chunk is handed to `json.loads`, fails, and is silently dropped (`except json.JSONDecodeError: pass`, line 684-685) — but the function still returns `f.tell()` (the position **past** that partial content) as the new read cursor. The next poll (2 seconds later, per the monitor loop at `simulation_runner.py:513-514`) seeks to that position and reads only the **continuation** of the writer's still-in-progress line — i.e., a fragment starting mid-JSON-object — which also fails to parse and is dropped. The action record straddling that flush boundary is permanently lost from `state.recent_actions`/round stats, and if a `round_end`/`simulation_end` marker (event-type records, handled the same way) straddles a flush boundary, round/completion detection can miss an update.

**Why it matters at scale**: with 100 concurrent simulations × up to 100 agents each generating actions continuously, flush-boundary timing collisions with the 2-second poll become common, not rare — this is a systemic (if usually low-impact per-occurrence) loss of simulation telemetry data.

**Fix**: only advance `position` to the offset of the last line that ended in `\n` (track the offset after each successfully-consumed newline, not `f.tell()` after the whole read), so an in-progress final line is re-read (and fully parsed) on the next poll.

---

## DATA-10 — MEDIUM
**Reads of OASIS-owned SQLite databases race the writer subprocess with no timeout override and no WAL awareness; failures are indistinguishable from "no data yet"**

`mirofish/backend/app/api/simulation.py:2019` and `:2092` (`get_simulation_posts`, `get_simulation_comments`), `mirofish/backend/app/services/simulation_runner.py:1673` (`_get_interview_history_from_db`).

All three call bare `sqlite3.connect(db_path)` with no `timeout=` kwarg and no `PRAGMA` set on the reader's side, while the OASIS subprocess (a separate process, entirely our own code's responsibility to coordinate with, since we spawn it in `simulation_runner.py:440-450`) is actively inserting posts/comments/trace rows into that same file. `get_simulation_posts` catches `sqlite3.OperationalError` around the query (`simulation.py:2035-2037`) and substitutes `posts=[]; total=0`; `_get_interview_history_from_db` catches a broad `Exception` (`simulation_runner.py:1709-1710`) and returns `[]`. Both cases render a lock-contention failure exactly the same as "the simulation legitimately has no posts/comments/interviews yet," which is misleading to users and hides genuine (recoverable) contention as a permanent-looking empty state on that request.

**Fix**: pass an explicit `timeout=` to `sqlite3.connect()` here and consider `PRAGMA query_only=1`/read-only URI mode for these reader connections; distinguish "locked, retry" from "genuinely empty" in the API response.

---

## DATA-11 — MEDIUM
**Agent-activity batches pushed to the knowledge graph are permanently dropped after 3 failed retries — no dead-letter/replay path**

`mirofish/backend/app/services/graph_memory_updater.py:311-338` (`_send_batch_activities`).

```python
for attempt in range(self.MAX_RETRIES):
    try:
        self.storage.add_text(self.graph_id, combined_text)
        ...
        return
    except Exception as e:
        if attempt < self.MAX_RETRIES - 1:
            time.sleep(self.RETRY_DELAY * (attempt + 1))
        else:
            self._failed_count += 1
```

The batch of up to `BATCH_SIZE=5` agent activities was already pulled off `self._activity_queue` and out of `self._platform_buffers` before this call (`_worker_loop`, lines 285-309) — on final failure it is not requeued, persisted, or logged anywhere retrievable; `_failed_count` is incremented and the content is gone. Given DATA-04/DATA-05 above (missing constraint + non-atomic multi-statement writes), transient Neo4j errors under concurrent load are a realistic, not theoretical, occurrence — and at 100 concurrent simulations each running their own `GraphMemoryUpdater` worker thread hammering the same Neo4j instance, contention-driven failures compound.

**Fix**: on exhausted retries, append the batch to a per-graph on-disk dead-letter file (or a `Queue` drained by a separate re-driver) instead of discarding it.

---

## DATA-12 — MEDIUM
**Relations are always `CREATE`d, never `MERGE`d/deduplicated — unbounded edge growth for repeated facts over a long-running simulation**

`mirofish/backend/app/storage/neo4j_storage.py:314-347`.

Unlike entities (which at least attempt a `MERGE`, modulo DATA-04), every relation extracted from every `add_text` call is unconditionally `CREATE`d as a brand-new `RELATION` edge — there is no dedup by `(source, target, type)` or fact-similarity. `graph_memory_updater.py` continuously feeds the same graph with activity descriptions like "Liked X's post" every `BATCH_SIZE` activities for the simulation's whole run (potentially hundreds of rounds × up to 100 agents), so semantically-repeated facts ("Agent A liked Agent B's post" happening many times) each mint a new edge rather than reinforcing/updating one. Combined with no archiving strategy (no code path ever deletes old episodes/relations for a graph short of `delete_graph`), per-simulation graphs accumulate edges without bound, degrading later `get_all_edges`/`search` query latency and Neo4j memory footprint as usage scales across concurrent long-running simulations.

**Fix**: MERGE relations on a stable key (e.g., `(source_uuid, target_uuid, type)` with episode_ids appended on match) instead of always creating new ones; add a retention/consolidation job for old episodes.

---

## DATA-13 — MEDIUM
**`campaigns` table has no index on `status` or `created_at`, and nothing ever archives/prunes old rows — full-table scans grow unbounded and contend with the single shared DB connection**

`orchestrator/storage/database.py:16-33` (schema — only implicit unique-constraint indexes on `iterations`/`analyses`/`reports` exist; `campaigns` has none beyond its primary key), used by `cleanup_orphaned_campaigns` (`campaign_store.py:83-92`, filters on `status`) and `list_campaigns` (`campaign_store.py:186-228`, `ORDER BY c.created_at DESC` over every row, with no pagination).

There is no cleanup/archival job anywhere in the codebase for completed/failed campaigns — `campaigns`, `iterations`, `analyses`, and `reports` all grow strictly monotonically for the operational lifetime of the deployment. Because all DB access in a given orchestrator process funnels through the single shared `aiosqlite.Connection` (`database.py:83-97`), a slow, ever-growing full scan (e.g., `list_campaigns`, polled routinely by the UI) serializes behind/ahead of every other concurrent user's campaign reads and writes — a single hot query degrades the whole service, not just the requester.

**Fix**: add `CREATE INDEX idx_campaigns_status ON campaigns(status)` and `CREATE INDEX idx_campaigns_created_at ON campaigns(created_at)`; paginate `list_campaigns`; add a retention policy (archive-to-file or delete) for campaigns older than N days.

---

## DATA-14 — LOW
**`progress_history` dict grows unboundedly for the life of the process**

`orchestrator/api/campaigns.py:371-374`.

```python
if not hasattr(request.app.state, "progress_history"):
    request.app.state.progress_history = {}
request.app.state.progress_history[campaign.id] = []
```

Every auto-started campaign adds a new entry keyed by `campaign.id`; each entry's *list* is capped at 500 events (`HISTORY_CAP`, line 375), but the outer dict itself is never pruned — `cleanup_queue()` (`orchestrator/api/progress.py:37-48`) only pops `progress_queues`, and the code comment at `progress.py:40-46` explicitly says the history buffer is intentionally left in place. Over the operational lifetime of a process serving 100 concurrent users creating many campaigns, this dict accumulates one (bounded-length) list per campaign forever — a slow, unbounded in-memory leak.

**Fix**: evict a campaign's `progress_history` entry once its terminal SSE event (`campaign_complete`/`campaign_error`) has been emitted and some grace period has elapsed (or cap the number of remembered campaigns with an LRU).

---

## Additional note (not separately scored)
`orchestrator/storage/campaign_store.py:255-285` (`update_campaign_status`) performs an unconditional blind `UPDATE` with no compare-and-swap against the row's current status. No currently-reachable API path races two status writers against the same campaign (no cancel/pause endpoint exists today), so this is not independently exploitable — but it is a latent foot-gun: any future feature that lets a user cancel a campaign (a natural addition at multi-tenant scale) will race this write against the pipeline's own terminal `update_campaign_status` calls in `campaign_runner.py` (`completed`/`failed`) with pure last-write-wins semantics.

---

## What breaks first at 100 users x 100 agents

**The very first orchestrator restart while campaigns are in flight (DATA-01) is the highest-confidence failure.** With 100 concurrent users, at any given moment there will almost certainly be campaigns mid-run — and given the project's own stated constraints (single shared GPU between TRIBE and Ollama, a single `threading.Lock` serializing all TRIBE inference, Claude API rate limits, MiroFish spawning one OS subprocess per simulation), sustained load from 100 users × up to 100 agents each is exactly the condition most likely to trigger a downstream timeout/crash/OOM that takes the orchestrator process down — which is also the trigger for the very code path (`cleanup_orphaned_campaigns` + the shutdown task-cancel loop) that blanket-fails *every* running campaign for *every* user, not just the one that caused the crash. This isn't a rare race that needs unlucky timing to manifest — it is a deterministic, guaranteed consequence of "the process restarts while anything is running," and at this scale the process restarting under load is close to certain rather than hypothetical. The result: one crash anywhere in the pipeline (not even one crash per user) wipes every concurrent user's in-flight work simultaneously, with no resumption path, on a system explicitly being evaluated for its ability to serve 100 concurrent users.
