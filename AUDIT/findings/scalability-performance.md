# Scalability & Performance Audit — Track 3

Scope: `mirofish/backend/app/storage/*`, `mirofish/backend/app/services/{entity_reader,graph_builder,oasis_profile_generator,simulation_runner,report_agent}.py`, `orchestrator/clients/*.py`, `orchestrator/api/{progress,campaigns}.py`, `orchestrator/storage/campaign_store.py`, `ui/src/hooks/*`, `docker-compose*.yml`.

Scaling target audited against: ~100 concurrent users × up to 100 in-app agents each (~10,000 concurrent simulated agents across many concurrent campaigns/simulations).

---

## PERF-01 — CRITICAL — MiroFish's entire backend runs on Flask's development server, single process, GIL-bound

**File:** `mirofish/backend/run.py:39`

```python
app.run(host=host, port=port, debug=debug, threaded=True)
```

There is no gunicorn/uwsgi/waitress in front of this. `docker-compose.yml`'s `mirofish` service `CMD ["npm", "run", "dev"]` runs this same dev-mode entry point in the container (confirmed no alternate WSGI launch script exists under `mirofish/backend`). `threaded=True` allows multiple Python threads to handle concurrent requests, but they all share one GIL and one process — every one of the following runs inside that single process for every one of the ~100 concurrent users' campaigns:

- Ontology generation LLM calls (`app/services/ontology_generator.py`, blocking `openai` sync client)
- Graph building: a raw `threading.Thread` per build (`graph_builder.py:80-87`, unbounded — no pool, no cap), each doing spaCy NER + embedding HTTP calls + dozens of sequential Neo4j write transactions (see PERF-05)
- Simulation prepare: `ThreadPoolExecutor(max_workers=5)` doing up to 100 sequential-ish LLM + hybrid-search calls to generate agent personas (`oasis_profile_generator.py:899`, see PERF-06)
- Simulation run: `subprocess.Popen` + one dedicated monitor `threading.Thread` per simulation (`simulation_runner.py:461-468`) polling JSONL logs every 2s
- Every poll from the orchestrator (`run-status` every 2-10s per active campaign) and every poll from MiroFish's own Vue live-view iframe (embedded directly in ARC Studio's UI — see PERF-02)

**Why it fails:** the Werkzeug dev server is explicitly documented by Flask as unsuitable for production; it has no multi-process worker model, a small/naive connection-handling loop, and under sustained concurrent load either serializes badly (GIL contention on every CPU-bound step above: JSON parsing, NER, keyword scoring, list comprehensions over full node/edge sets) or drops/hangs connections outright. At 100 concurrent users simultaneously launching campaigns, MiroFish must field ~100 concurrent long-lived HTTP requests (ontology/build/prepare/start, each blocking a thread for potentially minutes) plus service ~100 background monitor threads plus ~100 OS subprocesses — all funneled through one Python process with one GIL. This is the layer most likely to visibly fail first (hangs, 500s, dropped keep-alives) well before any individual simulation reaches its agent-round logic.

**Minimal fix:** run the Flask app behind gunicorn/waitress with multiple worker processes (`gunicorn -w N --threads M -b 0.0.0.0:5001 app:create_app()`), and move the class-level in-memory state (PERF-08) to a shared store (Redis/DB) so it survives being multi-process.

---

## PERF-02 — CRITICAL — Simulation action/timeline/agent-stats endpoints re-parse the entire JSONL log on every call; this is the endpoint MiroFish's own "live" view polls continuously

**Files:** `mirofish/backend/app/services/simulation_runner.py:822-889` (`_read_actions_from_file`), `:891-950` (`get_all_actions`), `:986-1055` (`get_timeline`), `:1057-1098` (`get_agent_stats`); consumed by `mirofish/backend/app/api/simulation.py:1758-1856` (`/run-status/detail`) and `:1913-1977` (`/timeline`, `/agent-stats`).

`_read_actions_from_file` opens the file, reads every line from byte 0, and `json.loads()`s each one — with **no cursor/offset**, unlike the internal monitor thread's own `_read_action_log`, which correctly seeks from a saved position (`simulation_runner.py:502-514`). `get_timeline`/`get_agent_stats` both call `get_actions(limit=10000)` → `get_all_actions()` → this full un-cursored read, then do the round/agent aggregation in Python. `/run-status/detail` (explicitly documented "For frontend to display real-time dynamics") calls `get_all_actions()` **three separate times** in one request (unfiltered, twitter-only, reddit-only) plus a fourth filtered-by-round call for `recent_actions` — each a fresh full-file read+parse of both `twitter/actions.jsonl` and `reddit/actions.jsonl`.

`ui/src/components/simulation/simulation-graph-panel.tsx:1-18` iframe-embeds MiroFish's own Vue frontend (`/simulation/:id/start`) directly into ARC Studio's campaign-detail page — the in-repo comment states this route "polls the running OASIS sim and renders agents + ontology edges as they materialise," i.e. it is a live-updating view, which necessarily polls one of these action/status endpoints on a short interval from the user's own browser, bypassing the orchestrator entirely.

**Why it fails:** file size grows unboundedly for the duration of a simulation (100 agents × up to 144 rounds × 1-3 actions/round ≈ tens of thousands of JSON lines per platform, single-digit-to-double-digit MB). Every poll — from either the orchestrator's result-extraction step *or* the live iframe — costs O(file size) disk I/O + JSON parsing, multiplied 3-6x per single HTTP request to `/run-status/detail`. With ~100 concurrently running simulations each being watched by an open browser tab (the demo-oriented iframe design implies this is the common case), this is O(hundreds of MB) of redundant re-reads and re-parses per polling cycle, all serialized through the single Flask process from PERF-01.

**Minimal fix:** maintain the parsed/aggregated action state in the existing `SimulationRunState` object incrementally (the monitor thread already does this via `state.add_action()`/`state.rounds` — the read-side handlers should serve from that in-memory state instead of re-reading the file), and cap `/run-status/detail`'s `all_actions`/`twitter_actions`/`reddit_actions` payload with real pagination instead of "no pagination limit" (explicit in the docstring at `simulation_runner.py:899-900`).

---

## PERF-03 — HIGH — SSE progress endpoint cannot survive a single client disconnect: reconnection permanently 404s for the rest of the campaign

**Files:** `orchestrator/api/progress.py:27-48` (`get_or_create_queue`/`cleanup_queue`), `:54-64` (`campaign_progress`); `ui/src/hooks/use-progress.ts:80-84` (`es.onerror`).

`cleanup_queue()` unconditionally pops `app.state.progress_queues[campaign_id]` in the SSE generator's `finally` block — i.e. as soon as **any** client of that campaign's stream disconnects (browser tab refresh, network blip, laptop sleep, or the frontend's own `es.onerror` handler which closes the `EventSource` without ever reconnecting). The route handler then looks the queue up with a plain `.get()`:

```python
queue = queues.get(campaign_id)
if queue is None:
    raise HTTPException(status_code=404, detail="No active campaign run")
```

— not `get_or_create_queue` — so any later reconnect attempt to the *same still-running* campaign's `/progress` endpoint gets a hard 404, even though the background campaign task is still alive and its `progress_callback` closure is still writing events into the now-orphaned queue object that nothing reads anymore.

**Why it fails:** at 100 concurrent users, browser tab refreshes/backgrounding/navigation are routine, not edge cases. The very first such event for any given campaign permanently kills its live progress stream (SSE) for the remainder of the run — the UI silently degrades to the coarse 3s `useCampaign` poll (status field only, no per-step detail), and any later attempt to reopen the progress view for that campaign gets a 404 the frontend has no retry/backoff for. This will read to users/support as "progress just stopped working" on a large fraction of campaigns at this scale.

**Minimal fix:** make `campaign_progress` call `get_or_create_queue` (so a reconnect gets a fresh queue), and route `progress_callback`'s target queue through `app.state.progress_queues[campaign_id]` (a fresh lookup) rather than a closure captured at task-launch time, so a new queue actually receives subsequent events.

---

## PERF-04 — HIGH — No index on `iterations.campaign_id` / `analyses.campaign_id`; every 3s campaign poll and every campaign-list fetch does an unindexed scan that grows with *global* row count

**Files:** `orchestrator/storage/database.py:15-69` (schema — no `CREATE INDEX` statements anywhere besides implicit PK/UNIQUE indexes), `orchestrator/storage/campaign_store.py:150-184` (`get_campaign` → `get_iterations`/`_get_analyses`), `:186-228` (`list_campaigns` correlated subquery), `ui/src/hooks/use-campaigns.ts:27-30` (`useCampaign` polls `GET /api/campaigns/{id}` every 3s while `status==='running'`).

`iterations` and `analyses` both have `campaign_id` as an `FK REFERENCES campaigns(id)` with **no** `CREATE INDEX idx_iterations_campaign_id ON iterations(campaign_id)` (SQLite does not auto-index FK columns). `get_iterations()`/`_get_analyses()` run `SELECT * FROM ... WHERE campaign_id = ?` as full table scans. `list_campaigns()` additionally runs a correlated subquery per campaign row (`SELECT COUNT(DISTINCT iteration_number) FROM iterations i WHERE i.campaign_id = c.id`) with the same missing index.

All of this funnels through a **single** shared `aiosqlite` connection (`orchestrator/storage/database.py:83-97`, one `self._conn` for the whole app) — aiosqlite serializes all operations on that connection through one internal worker thread, so there is exactly one DB-access lane for the entire orchestrator regardless of how many campaigns are concurrently running.

**Why it fails:** the cost of each scan is proportional to the **total row count across all users' campaigns**, not just the polled campaign's own rows. At 100 concurrently running campaigns each polled every 3s (~33 req/s), each request does 2 full scans (`iterations`, `analyses`) plus (on the list page) one correlated-subquery scan per campaign row — and this cost only grows as more users create more campaigns over the product's lifetime, i.e. this scan-cost regression compounds with adoption, not just concurrency. All serialized on one SQLite connection thread means this is also a single point of contention: a slow scan for one campaign's poll delays every other concurrently polling user's request behind it.

**Minimal fix:** `CREATE INDEX idx_iterations_campaign_id ON iterations(campaign_id)` and `CREATE INDEX idx_analyses_campaign_id ON analyses(campaign_id)` in `SCHEMA_SQL`/`_migrate_schema`; consider a lighter "status-only" endpoint for the 3s poll so it doesn't have to hydrate every iteration/analysis row each time.

---

## PERF-05 — HIGH — Neo4j graph writes are per-entity/per-relation individual transactions (N+1), not batched

**File:** `mirofish/backend/app/storage/neo4j_storage.py:212-350` (`add_text`).

For every text chunk, `add_text()` opens one `session.execute_write` for the episode node, then loops over every extracted entity doing **one** `MERGE` transaction plus (conditionally) **one more** `SET label` transaction each, then loops over every extracted relation doing **one** `CREATE` transaction each:

```python
for idx, entity in enumerate(entities):
    ...
    actual_uuid = self._call_with_retry(session.execute_write, _merge_entity)   # round-trip #1
    if etype and etype != "Entity":
        self._call_with_retry(session.execute_write, _add_label)               # round-trip #2
for idx, relation in enumerate(relations):
    ...
    self._call_with_retry(session.execute_write, _create_relation)             # round-trip #3
```

For a chunk yielding, say, 20 entities + 15 relations, that is ~1 + 20 + 20 + 15 ≈ **56 separate Neo4j network round-trips** where a single `UNWIND $entities AS e MERGE ...` / `UNWIND $relations AS r CREATE ...` pair (2-3 round trips total) would do the same work. `graph_builder.py:185-236` (`add_text_batches`) calls `add_text()` once per chunk sequentially, and `build_graph_async` launches this whole pipeline on a **raw, unbounded `threading.Thread`** per graph build (`graph_builder.py:80-87` — no `ThreadPoolExecutor`, no cap).

**Why it fails:** at 100 concurrent MiroFish simulations (one graph build per active campaign), this multiplies Neo4j round-trip overhead by roughly 50x versus a batched write, on top of already running inside the single GIL-bound Flask process (PERF-01) and inside unmanaged, uncapped native OS threads — 100 concurrent graph builds means 100 uncapped threads simultaneously hammering Neo4j with ~50-60 sequential round trips apiece.

**Minimal fix:** batch entity upserts and relation creates with `UNWIND` (2-3 Cypher statements per chunk instead of one per entity/relation), and run `_build_graph_worker` on a bounded `ThreadPoolExecutor` instead of an unbounded raw `Thread` per request.

---

## PERF-06 — MEDIUM/HIGH — Agent-profile generation issues one un-batched embedding call pair and 4 Neo4j round-trips per agent, ×100 agents ×100 concurrent sims

**Files:** `mirofish/backend/app/services/oasis_profile_generator.py:278-356` (`_search_graph_for_entity`), `:795-954` (`generate_profiles_from_entities`, `ThreadPoolExecutor(max_workers=5)`); `mirofish/backend/app/storage/search_service.py:67-122` (`search_edges`/`search_nodes` each call `self.embedding.embed(query)` — singular, not `embed_batch`).

For every agent persona generated, `_search_graph_for_entity()` calls `storage.search(scope="edges")` and `storage.search(scope="nodes")` — each of which independently calls `EmbeddingService.embed()` (a single-text HTTP call to Ollama) plus one vector-index query and one fulltext-index query against Neo4j. That is 2 embedding calls (1 real + 1 cache-hit, since the query string is identical for both) and 4 Neo4j round-trips **per agent**, generated with only 5-way thread parallelism.

**Why it fails:** for a 100-agent simulation this is ~100 embedding HTTP calls and ~400 Neo4j round-trips against the single shared, host-native Ollama instance and single Neo4j container — none of it batched even though `EmbeddingService.embed_batch()` already exists and is used elsewhere in the same file's sibling code path (`neo4j_storage.py:203`). At 100 concurrent simulations × 100 agents, that is up to ~10,000 un-batched embedding calls and ~40,000 Neo4j round-trips for a single "generate all personas" phase, against infrastructure sized for a single-user POC (one Ollama instance, one Neo4j container, both already contended by graph-building traffic from PERF-05).

**Minimal fix:** collect all agents' `comprehensive_query` strings up front and call `embed_batch()` once per simulation instead of per-agent `embed()`.

---

## PERF-07 — MEDIUM — In-memory embedding cache and all simulation-runner state are single-process-only, blocking any horizontal-scale fix

**Files:** `mirofish/backend/app/storage/embedding_service.py:36-39,184-191` (`self._cache`, plain dict, no lock); `mirofish/backend/app/services/simulation_runner.py:218-227` (`_run_states`, `_processes`, `_action_queues`, `_monitor_threads`, `_stdout_files`, `_stderr_files`, `_graph_memory_enabled` — all Python **class-level** dict attributes).

`EmbeddingService._cache` is mutated from multiple threads concurrently (graph-build threads, the profile-generation `ThreadPoolExecutor`) with no lock around the check-evict-set sequence in `_cache_put`. More importantly, both this cache and all of `SimulationRunner`'s process/thread bookkeeping live only in the memory of the one Flask process identified in PERF-01 — the very fix for PERF-01 (running MiroFish with multiple worker processes) is blocked by this: a `/simulation/{id}/stop` or `/interview` request routed to a different worker than the one that called `subprocess.Popen` would find no entry in `_processes`/`_action_queues` for that simulation, and `EmbeddingService`'s cache hit rate silently drops to 1/N-workers with no correctness impact but no scaling benefit either.

**Why it fails:** this is the concrete instance of the "in-memory cache vs multi-worker deployment" risk called out in the audit brief — the codebase cannot be scaled past one process without first externalizing this state (e.g. to Redis or the existing `run_state.json` files, consulted more consistently), which the current design does not do.

**Minimal fix:** back `_processes`/`_action_queues` state with a shared store (or route all simulation-control endpoints through the same fixed worker via sticky routing) before adding worker processes to fix PERF-01; move `EmbeddingService._cache` to a shared cache (Redis) or accept the reduced hit rate explicitly.

---

## PERF-08 — MEDIUM — No CPU/memory resource limits on any container; unbounded Neo4j growth with a static 2 GB heap and an admittedly manual cleanup process

**Files:** `docker-compose.yml:1-97`, `docker-compose.rocm.yml` (no `deploy.resources.limits`/`mem_limit`/`cpus` anywhere in either file — confirmed via full-file grep).

```yaml
# Heap capped at 2 GB. Each MiroFish simulation adds ~10 MB of graph data.
# After ~200 campaigns, consider running: scripts/cleanup_neo4j.sh
```

This comment on the `neo4j` service acknowledges unbounded growth and a **manual** cleanup script as the only mitigation — there is no scheduled job, TTL, or automatic eviction of old campaign graphs. None of the other services (`mirofish`, `litellm`) have any memory/CPU ceiling either, so a single misbehaving simulation (e.g. very large seed content driving heavy NER/embedding load) can consume host resources without a container-level backstop.

**Why it fails:** "~200 campaigns" is explicitly the point at which the current design already expects manual intervention. At the target of 100 concurrent users, each capable of running multiple campaigns per day, that threshold is reached in hours to low-single-digit days rather than the presumably longer timeframe the comment implies, at which point Neo4j either OOMs inside its 2 GB heap (query failures / crash) or, absent any container memory limit anywhere else, a runaway MiroFish/embedding workload can pressure host memory shared by every other service (TRIBE's GPU-bound scorer, vLLM/LiteLLM) with no isolation.

**Minimal fix:** add `deploy.resources.limits` (or `mem_limit`/`cpus` under classic compose) to every service; add a scheduled `neo4j` retention job (delete graphs for campaigns older than N days / beyond a total-graph-count budget) instead of a manual script.

---

## PERF-09 — MEDIUM — Orchestrator's shared httpx connection pools have no explicit `Limits`, defaulting to a 100-connection ceiling that lines up exactly with the target concurrency

**File:** `orchestrator/api/__init__.py:160-161`.

```python
tribe_http = httpx.AsyncClient(base_url=settings.tribe_scorer_url, timeout=300.0)
mirofish_http = httpx.AsyncClient(base_url=settings.mirofish_url, timeout=300.0)
```

No `limits=httpx.Limits(max_connections=..., max_keepalive_connections=...)` is passed, so httpx's default (`max_connections=100`) applies. Each of these clients is a single shared instance for the whole orchestrator process (good — created once in `lifespan`, not per-request), but campaign execution is sequential-per-variant (`orchestrator/clients/mirofish_client.py` design note: "Per D-04: Called sequentially, one variant at a time"), so each of the up-to-100 concurrently running campaigns holds roughly one in-flight connection to MiroFish/TRIBE at a time via its own polling loop.

**Why it fails:** at exactly 100 concurrently running campaigns, the shared pool sits at its default ceiling; a 101st concurrent request queues invisibly behind pool exhaustion (no explicit timeout/monitoring for this specific condition) rather than either being intentionally admission-controlled or given headroom. This compounds — rather than causes — the deeper problem that the single MiroFish Flask process (PERF-01) and single TRIBE GPU worker cannot actually service 100 concurrent heavy requests regardless of the client-side pool size.

**Minimal fix:** set explicit `httpx.Limits(max_connections=N, max_keepalive_connections=M)` sized to the actual number of campaigns the backing services can serve concurrently, and treat exceeding it as a queueing/backpressure signal in campaign scheduling rather than an invisible httpx-level wait.

---

## What breaks first at 100 users × 100 agents

**MiroFish's backend collapses under concurrent HTTP request volume before any individual simulation reaches its agent-round logic.** The entire social-simulation tier — ontology generation, graph building (NER + un-batched Neo4j writes, PERF-05), persona generation (un-batched embedding + Neo4j calls, PERF-06), and simulation-process supervision — runs inside one Flask development-server process (`mirofish/backend/run.py:39`, `app.run(..., threaded=True)`, no WSGI server, no worker processes; PERF-01). At 100 users launching campaigns within the same rough time window, that one process must simultaneously hold ~100 long-lived blocking requests (each minutes long during graph-build/prepare), ~100 unbounded native `threading.Thread`s from `graph_builder.py`'s per-request thread spawn, ~100 monitor threads once simulations start, and (per the UI's own iframe design, PERF-02) a live-view poll storm hitting the JSONL-log endpoints that re-read entire files on every call. All of this shares one GIL and one process with no admission control, no backpressure, and no horizontal scale-out path (state is process-local per PERF-07). Expect this to manifest as: request timeouts and dropped connections on `/api/graph/ontology/generate` and `/api/graph/build` for the majority of the 100 simultaneous campaign launches, well before GPU/TRIBE or Neo4j capacity is even the binding constraint — the orchestrator's own graceful-degradation path (treating MiroFish as unavailable) will trigger broadly, silently degrading most concurrent campaigns to TRIBE-only scoring rather than failing loudly.
