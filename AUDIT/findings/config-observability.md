# Track 9 — Configuration & Observability

Scope: `orchestrator/config.py`, `tribe_scorer/config.py`, `mirofish/backend/app/config.py`,
`docker-compose.yml` + `docker-compose.rocm.yml`, `tribe_scorer/start.sh`, `scripts/*`,
`.env.hackathon.example` / `.env.example`, `pyproject.toml`, `mirofish/backend/app/utils/logger.py`,
orchestrator logging setup, `orchestrator/api/health.py` + MiroFish `/health`.

All findings below were confirmed by reading the cited files (and, where noted, verified empirically
with a throwaway Python check of Python's own logging defaults and uvicorn's shipped `LOGGING_CONFIG`).

---

## OBS-01 — CRITICAL — Live-looking secret committed into a template `.env` file
**File:** `.env.hackathon.example:49`

```
HF_TOKEN=hf_<REAL-TOKEN-REDACTED-38-chars>
```

`.env.hackathon.example` is the tracked, committed template that gets copied to `.env.hackathon` on
the cloud node (see file header, lines 1-6: "Only this template is committed"). `git diff HEAD --
.env.hackathon.example` shows the last **committed** value was the placeholder `HF_TOKEN=hf_REPLACE_ME`,
but the current **working tree** (what a `git add`/`git commit` right now would ship) has overwritten
it with what appears to be a real HuggingFace access token (`hf_` prefix, correct length/shape). This
file is required reading for every hackathon-stack operator and is exactly the kind of file that gets
pasted into issues, forum posts, or forked repos.

**Why it fails:** the moment this working-tree state is committed and pushed (or even just diffed/pasted
somewhere), the token is permanently in git history and publicly retrievable by anyone with repo access
— a live credential leak, not a hypothetical one. This is a config-hygiene process failure: nothing in
the repo (`pre-commit`, `.gitignore`, secret-scanning) prevents a real token from landing in a file
that's explicitly designed to be committed.

**Minimal fix:** revert `HF_TOKEN` to `hf_REPLACE_ME` (or `hf_...` placeholder) before committing;
add a pre-commit secret-scan hook (e.g. `detect-secrets` or `gitleaks`) that blocks commits containing
`hf_[A-Za-z0-9]{30,}`-shaped tokens in any `*.example` file; rotate the token if it was ever pushed.

---

## OBS-02 — CRITICAL — Orchestrator has no logging configuration on its actual run path; almost all application logs are silently dropped
**Files:** `orchestrator/api/__init__.py` (entire file — no `logging.basicConfig`/`dictConfig` call
anywhere), contrast with `orchestrator/cli.py:397-399` (the *CLI* path does call `basicConfig`).

The documented production run command (README / CLAUDE.md) is:
```
python -m uvicorn orchestrator.api:create_app --factory --port 8000
```
Every module in `orchestrator/` obtains its logger via `logging.getLogger(__name__)` (23 call sites
confirmed, e.g. `orchestrator/engine/campaign_runner.py:46`, `orchestrator/api/health.py:26`,
`orchestrator/clients/tribe_client.py:24`) and never configures a level or handler. Uvicorn's own
default `LOGGING_CONFIG` (verified directly from the installed package) only touches the `uvicorn`,
`uvicorn.error`, and `uvicorn.access` loggers — it has **no `"root"` entry** — so it does nothing for
`orchestrator.*` loggers. Empirically verified in this environment:

```
>>> logging.getLogger('orchestrator.engine.campaign_runner').isEnabledFor(logging.INFO)
False
>>> logging.getLogger().level   # root logger, untouched
30   # WARNING
>>> logging.getLogger().handlers
[]
```

**Why it fails:** with the root logger at WARNING and no handlers configured anywhere on the FastAPI
run path, every `logger.info(...)` / `logger.debug(...)` call in the orchestrator — campaign lifecycle
messages (`campaign_runner.py:439` "Campaign %s iteration %d completed successfully", `__init__.py:206`
"Orchestrator started — DB at %s..."), health-check diagnostics, SSE progress emission, LiteLLM
key-refresh status — is filtered out before it ever reaches a handler. Only `.warning()`/`.error()`
calls survive, and they only reach Python's `logging.lastResort` handler (a bare `StreamHandler(stderr)`
at WARNING with no timestamp/name/line formatting). At 100 concurrent users, when a campaign silently
fails, TRIBE degrades, or MiroFish returns partial data, the operator has **no info-level trace at all**
to reconstruct what happened — only sparse, unstructured warnings/errors with no campaign/simulation
correlation.

**Minimal fix:** call `logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")`
(or configure a proper dictConfig, ideally JSON) once at the top of `orchestrator/api/__init__.py` before
`create_app()` runs, exactly as `cli.py` already does — and additionally pass a custom `log_config` to
uvicorn (or set `--log-config`) so this isn't sensitive to how the process is launched.

---

## OBS-03 — CRITICAL — Checked-in `.env.example` ships a wrong MiroFish port; known, self-documented, and still unfixed
**Files:** `.env.example:16`, `orchestrator/config.py:67-70` (`mirofish_url` default), `docker-compose.yml:61-62,79-80`

```
# .env.example
MIROFISH_URL=http://localhost:5000
```
```yaml
# docker-compose.yml
mirofish:
  ports:
    - "127.0.0.1:5001:5001"
  environment:
    FLASK_PORT: "5001"
```
`orchestrator/config.py:67-70` defaults `mirofish_url` to `http://localhost:5000` — same wrong port.
This is not a new discovery: `docs/competition/01_migration_plan.md:143` already documents it verbatim
("mirofish defaults to `localhost:5000` while base compose binds it on 5001 ... backport to template")
— and it has still not been backported into `.env.example`. It was briefly fixed in
`.env.hackathon.example` (explicit `MIROFISH_URL=http://127.0.0.1:5001` override, per `git diff`), but
that fix is **also gone in the current working tree** of `.env.hackathon.example` (reverted back to
relying on the wrong default, with the URL override block deleted entirely).

**Why it fails:** any fresh setup that does `cp .env.example .env` (the documented onboarding path) gets
an orchestrator that tries to reach MiroFish on port 5000, where nothing listens (real MiroFish is on
5001). Per the "graceful degradation" pattern (`CLAUDE.md`), this doesn't crash — `mirofish_client.health_check()`
fails, `/api/health` reports `mirofish: unavailable`, and every campaign silently proceeds with
MiroFish-dependent composite scores as `None`. Unless an operator explicitly checks `/api/health`,
campaigns "complete successfully" with a large silent gap in the output. This is precisely the kind of
config drift the audit was asked to hunt, and it's actively regressing rather than being fixed.

**Minimal fix:** change the default in `.env.example` and `orchestrator/config.py`'s `mirofish_url` Field
to `http://localhost:5001`; restore the explicit `MIROFISH_URL`/`TRIBE_SCORER_URL` override block in
`.env.hackathon.example`; add a startup assertion in `orchestrator/api/__init__.py` lifespan that fails
loudly (not silently degrades) if the configured `mirofish_url` port doesn't match what the health probe
returns for the expected service identity.

---

## OBS-04 — HIGH — CORS origin hardcoded to `localhost:5173`, unconfigurable, breaks any non-local UI
**File:** `orchestrator/api/__init__.py:244-251`

```python
application.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    ...
)
```

This value is a Python literal, not sourced from `settings` or any env var.

**Why it fails:** at the audited scaling target ("local hardware or cloud", 100 concurrent users), any
UI that isn't served from exactly `http://localhost:5173` — a cloud-hosted deployment, the Vercel
landing page already referenced in this repo's own git history (`s7_cloud_landing.png`,
"feat(site): PostHog analytics..." commits), a teammate's LAN IP, a different dev port — gets every
browser request rejected by CORS before it reaches any route. This is a hard, total failure mode for
every user not on the exact literal origin, and there is no environment variable to override it.

**Minimal fix:** add `cors_allowed_origins: list[str]` to `orchestrator/config.py` (comma-separated env
var, default `["http://localhost:5173"]`), and pass `settings.cors_allowed_origins` into
`allow_origins=`.

---

## OBS-05 — HIGH — MiroFish "backend" is Flask's development server, not a production WSGI server
**Files:** `mirofish/backend/run.py:45`, `mirofish/Dockerfile:26-29`, `mirofish/package.json:9-10`

```python
# run.py
app.run(host=host, port=port, debug=debug, threaded=True)
```
```dockerfile
# Dockerfile
CMD ["npm", "run", "dev"]
```
```json
"dev": "concurrently --kill-others -n \"backend,frontend\" ... \"npm run backend\" \"npm run frontend\"",
"backend": "cd backend && uv run python run.py",
```

The container that `docker-compose.yml` builds and runs in "production" (`arc-mirofish`, restart
policy `unless-stopped`, health-checked, depended-on by nothing but itself) launches via `npm run dev`,
which starts Werkzeug's built-in dev server (`threaded=True` just spawns one Python thread per request
under the GIL) *and* a Vite frontend dev server that is never used by the real product (the actual UI
is the separate React app on 5173). `FLASK_DEBUG=false` is set correctly in `docker-compose.yml:81`
(so the interactive debugger/reloader is off), but the underlying server is still Werkzeug's dev
server, which Flask's own docs explicitly say does not scale and is not meant to handle production
traffic.

**Why it fails:** at "many concurrent campaigns/simulations", MiroFish is hit concurrently by (a) the
orchestrator's polling loop per active simulation (`mirofish_client.py` polls every 2-10s per campaign,
`POLL_INITIAL_INTERVAL`/`POLL_MAX_INTERVAL`, lines 32-33), (b) the per-simulation monitor thread's own
disk I/O (see OBS-06), and (c) any concurrent OASIS subprocess spawns. A single-process, GIL-bound dev
server handling all of this concurrently for 100 simultaneous users' simulations is a well-known
throughput and stability bottleneck — connection queueing, dropped keep-alives, and eventual
unresponsiveness, with no worker pool to fall back on.

**Minimal fix:** run under `gunicorn`/`waitress` with multiple workers (`gunicorn -w 4 -k gthread
'app:create_app()'`) behind the container's exposed port; drop the frontend dev server from the
production image entirely (it serves no purpose there).

---

## OBS-06 — HIGH — Per-simulation monitor thread rewrites the entire state file every 2 seconds, growing with every round
**File:** `mirofish/backend/app/services/simulation_runner.py:481-514` (monitor loop),
`:86-97` (`RoundSummary.to_dict` embeds every action of every round), `:298-309` (`_save_run_state`)

```python
while process.poll() is None:  # Process still running
    if os.path.exists(twitter_actions_log):
        twitter_position = cls._read_action_log(...)
    if os.path.exists(reddit_actions_log):
        reddit_position = cls._read_action_log(...)
    cls._save_run_state(state)      # <- full JSON re-serialize + rewrite, every iteration
    time.sleep(2)
```
```python
def _save_run_state(cls, state: SimulationRunState):
    data = state.to_detail_dict()          # includes state.rounds -> RoundSummary.to_dict()
    with open(state_file, 'w', ...) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)   # full rewrite, not append/patch
```
`SimulationRunState.rounds: List[RoundSummary]` is append-only (`simulation_runner.py:129`), and each
`RoundSummary.to_dict()` (lines 86-97) inlines `"actions": [a.to_dict() for a in self.actions]` for
*every round accumulated so far* — there is no cap on `rounds`/`rounds[].actions` (unlike
`recent_actions`, which is explicitly capped at `max_recent_actions=50`, line 133).

**Why it fails:** this is one dedicated OS thread per simulation, running for the simulation's entire
wall-clock duration, unconditionally re-serializing and rewriting a JSON file to disk every 2 seconds
whose size grows monotonically as rounds/actions accumulate — i.e. total I/O for one simulation scales
worse than linearly with its length, not just its instantaneous state size. At "many concurrent
campaigns/simulations" (the audited target), this is N threads × full-file rewrites every 2s
indefinitely, competing for the GIL inside the same single-process Flask dev server (OBS-05) that's
also trying to serve HTTP requests. There is no configurable interval, no delta/patch write, and no
metric anywhere exposing how large these files or how frequent these writes have become.

**Minimal fix:** write only a small "status" JSON on the 2s cadence (round/hour counters, running flags)
and persist the full `rounds`/`actions` history separately on a coarser cadence (e.g. once per round
boundary, or via the JSONL action log which is already append-only); alternatively increase the poll
interval and bound `rounds` the same way `recent_actions` is already bounded.

---

## OBS-07 — HIGH — Zero metrics/tracing anywhere in the stack; health checks give no queue-depth signal for the one true bottleneck
**Files:** whole-repo search (no `prometheus`/`opentelemetry`/`statsd`/`/metrics` hits in any backend
code — the two textual matches found are an unrelated React component and MiroFish's `LICENSE` file);
`tribe_scorer/main.py:400` (`_inference_lock = threading.Lock()`); `orchestrator/clients/tribe_client.py:29-32`
(`SCORE_TIMEOUT = 5400.0`, 90 minutes); `orchestrator/clients/tribe_client.py:109-133` (`health_check`
only reports `status`/`cuda_healthy`, never lock/queue state); `orchestrator/api/health.py:30-122`
(orchestrator `/health` aggregates only up/down + latency of a single ping, nothing about backlog).

There is no counter for active simulations, no gauge for TRIBE's inference queue depth, and no LLM
latency histogram anywhere — this repo has no observability stack at all beyond ad-hoc `logger.info`
calls (which, per OBS-02, mostly don't even emit) and binary up/down health pings.

**Why it fails:** TRIBE v2 serializes literally all scoring calls through one process-wide
`threading.Lock` (by design, documented in `CLAUDE.md`: "TRIBE inference serialization... only one
inference runs at a time"), and the client is willing to wait up to 90 minutes per call
(`SCORE_TIMEOUT`). At 100 concurrent users each running a campaign (`default_variants_per_iteration=2`,
`orchestrator/config.py:157-162`), a single iteration across all users submits on the order of 200
TRIBE-scoring requests that must serialize behind one lock. `/api/health` will report TRIBE `status: ok`
throughout — the lock being held/queued is not part of the health signal at all — so an operator (or an
auto-scaler, or a user waiting on a spinner) has no way to see that the system is backlogged until
requests start timing out at the 90-minute mark, hours after the backlog began. This is the single
biggest blind spot the audit's hunt list called out ("what minimal counters are needed: active sims,
queue depths, LLM latency") and it is completely absent.

**Minimal fix:** expose a `/metrics` endpoint (even a minimal JSON one) with: TRIBE `_inference_lock`
holder/wait-queue-length, count of `running_tasks`, count of live MiroFish simulations, and a rolling
p50/p95 latency for the last N TRIBE/MiroFish/LLM calls; surface `queue_depth` in `/api/health` instead
of a single boolean per service.

---

## OBS-08 — HIGH — MiroFish logging is hardcoded to DEBUG, logs full request/response bodies, has no correlation IDs, and is capped at 50MB total
**Files:** `mirofish/backend/app/utils/logger.py:30` (`level: int = logging.DEBUG`, not env-driven),
`:56-59` (log format has no simulation/campaign ID field), `:66-73` (10MB × 5 backups = 50MB total cap);
`mirofish/backend/app/__init__.py:64-75` (request/response logging middleware)

```python
@app.before_request
def log_request():
    logger.debug(f"Request: {request.method} {request.path}")
    if request.content_type and 'json' in request.content_type:
        logger.debug(f"Request body: {request.get_json(silent=True)}")   # full payload, every call

@app.after_request
def log_response(response):
    logger.debug(f"Response: {response.status_code}")
```

**Why it fails:** the log level is a hardcoded Python literal — there is no `LOG_LEVEL` env var
support anywhere in `mirofish/backend/app/config.py`, so this cannot be turned down for a real
deployment without editing source. Combined with request/response-body logging at DEBUG for *every*
API call (ontology generation payloads, ~500-word content variants, ~40-100 agent configs per
simulation-create call), at "10k concurrent agents" worth of traffic this produces enormous log volume
with a hard 50MB rotation ceiling (`maxBytes=10*1024*1024, backupCount=5`) — meaning under load, useful
history is evicted within minutes, defeating the purpose of having logs at all during an incident. The
log format string (`'[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s'`,
`logger.py:57-58`) also carries no `simulation_id`/`campaign_id` field, so once multiple simulations run
concurrently their DEBUG traces interleave in the same file with no way to filter one simulation's logs
from another's.

**Minimal fix:** read log level from an env var (default INFO in non-debug mode); drop or truncate
request-body logging (or gate it behind an explicit `LOG_REQUEST_BODIES=true` flag); add a
`simulation_id`/`request_id` field via a `logging.Filter`/contextvar so concurrent simulations are
attributable; size the rotation budget (or ship to a log aggregator) based on expected concurrent load
rather than a fixed 50MB.

---

## OBS-09 — HIGH — `app.state.progress_history` grows one entry per campaign forever; no eviction path exists
**Files:** `orchestrator/api/campaigns.py:371-374`, `orchestrator/api/progress.py:37-48`

```python
# campaigns.py — created and populated per auto-started campaign
if not hasattr(request.app.state, "progress_history"):
    request.app.state.progress_history = {}
request.app.state.progress_history[campaign.id] = []
```
```python
# progress.py — cleanup_queue explicitly only pops progress_queues
def cleanup_queue(app, campaign_id: str) -> None:
    if hasattr(app.state, "progress_queues"):
        app.state.progress_queues.pop(campaign_id, None)
    # progress_history is never touched here or anywhere else in the repo
```

Each individual campaign's event list is bounded (`HISTORY_CAP = 500`, `campaigns.py:375-380`), which is
good, but the **outer dict** keyed by `campaign_id` is never pruned by any code path in the repository
(confirmed by grep — the only writes to `progress_history` are these three lines; there is no `.pop()`
anywhere else).

**Why it fails:** the orchestrator is a single long-lived process (`app = create_app()` at
`orchestrator/api/__init__.py:264`, run as one `uvicorn` process per CLAUDE.md). Every campaign that is
ever auto-started over the process's lifetime adds one more permanent key holding up to 500 buffered
event dicts. At "100 concurrent users" running campaigns continuously over days/weeks, this is
unbounded memory growth in the one process that serves everyone — a slow, silent leak with **no metric
anywhere** (per OBS-07) that would tell an operator it's happening until the process OOMs or the host
starts swapping.

**Minimal fix:** evict `progress_history[campaign_id]` in the same `finally:` block that already pops
`running_tasks` (`campaigns.py:393-394`) once the campaign reaches a terminal state and its SSE clients
have had a bounded grace period to reconnect, or store history in the SQLite `campaign_store` instead of
an in-memory dict.

---

## OBS-10 — MEDIUM — Neo4j heap sizing/cleanup thresholds are calibrated to 40 agents, not the 100-agent scaling target
**Files:** `docker-compose.yml:16-23`, `orchestrator/config.py:145-150` (`default_agent_count: int =
40, ge=20, le=200`), `orchestrator/api/health.py:88-93` (50,000-node warning threshold)

The compose comment reasons "Each MiroFish simulation adds ~10 MB of graph data. After ~200 campaigns,
consider running scripts/cleanup_neo4j.sh", and `/api/health` reasons "50000 nodes ≈ 250 campaigns" —
both figures are explicitly anchored to the *default* 40-agent simulation size. The audited scaling
target allows up to 100 agents per simulation (`le=200` even permits more).

**Why it fails:** a 100-agent simulation writes roughly 2.5x the graph data of the 40-agent baseline
these thresholds were calibrated against, so the documented "~200 campaigns before heap pressure"
guidance and the 50,000-node warning both fire far later than they should relative to actual heap
pressure — an operator trusting the documented cadence for `cleanup_neo4j.sh` could hit OOM/GC-thrash on
the 2GB-capped heap well before the warning ever appears.

**Minimal fix:** scale the warning threshold and cleanup cadence dynamically off `default_agent_count`
(or the actual configured agent count per campaign) rather than a hardcoded node count.

---

## OBS-11 — MEDIUM — Neo4j HTTP console URL is hardcoded, independent of `settings.neo4j_uri`
**File:** `orchestrator/api/health.py:76-85`

```python
neo4j_stats = await mirofish_client.get_neo4j_stats(
    neo4j_url="http://localhost:7474",     # literal, not derived from settings.neo4j_uri
    neo4j_user=os.environ.get("NEO4J_USER", settings.neo4j_user),
    neo4j_password=os.environ.get("NEO4J_PASSWORD", settings.neo4j_password),
)
```

`settings.neo4j_uri` (bolt://…:7687, `orchestrator/config.py:77-80`) is never consulted for host — the
HTTP console port/host is a separate literal that happens to match the docker-compose default today.

**Why it fails:** if Neo4j is ever moved off `localhost` (a real multi-node cloud deployment — one of
the two scaling targets named in this audit) or its HTTP console port is changed, this stats check
silently starts failing (caught by the broad `except Exception` at line 100, logged as a warning only)
while the rest of the health check remains green — a config value that can drift out from under the
rest of the settings object with no single source of truth.

**Minimal fix:** derive host from `settings.neo4j_uri` (parse the bolt URI, or add an explicit
`neo4j_http_url` setting) instead of a bare string literal.

---

## OBS-12 — MEDIUM — Silent weak-default fallbacks for two security-relevant values
**Files:** `orchestrator/config.py:85-88` (`neo4j_password: str = Field(default="mirofish", ...)`),
`mirofish/backend/app/config.py:24` (`SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')`)

Both values fall back silently to a well-known, hardcoded string if the corresponding env var is unset.
`docker-compose.yml:20,71` do force `NEO4J_PASSWORD` via `:?NEO4J_PASSWORD must be set in .env`, so the
Docker path is protected — but `orchestrator/config.py`'s own default has no such guard, and nothing
stops the orchestrator (or MiroFish, run outside Docker via `run.py`) from starting up quietly with
these defaults if `.env` doesn't set them.

**Why it fails:** this is exactly the "silent config fallback masking misconfiguration" pattern called
out in the audit brief — a misconfigured deployment doesn't fail loudly, it just quietly uses a
guessable password/secret key. Low current impact given Phase 1's explicit "no auth" scope, but real
risk the moment this graduates toward the stated cloud/100-user target.

**Minimal fix:** make `neo4j_password` and `SECRET_KEY` required (no default, raise at startup if
unset) rather than silently falling back.

---

## OBS-13 — MEDIUM — vLLM tiers have no concurrency/admission-control tuning or shared config file
**Files:** `docker-compose.rocm.yml:62-75` (`vllm-orchestrator`), `:108-114` (`vllm-agents`)

Both vLLM services are launched with `--gpu-memory-utilization=0.40` each (0.80 combined on one MI300X
that also hosts TRIBE + embeddings, per the architecture in `docker-compose.rocm.yml`'s own header
comment) but neither sets `--max-num-seqs` or `--max-num-batched-tokens`; there's also no LiteLLM-style
config file for these tiers (no load balancing, no per-key rate limiting) — the base
`docker-compose.yml`'s `litellm` service is similarly launched with a single hardcoded model and no
config file (`command: --model anthropic/${CLAUDE_HAIKU_MODEL:-...} --port 4000`, line 44).

**Why it fails:** under "100 users × 100 agents" concurrent MiroFish agent traffic hitting
`vllm-agents`/LiteLLM, there is no configured admission control, so behavior under saturation (queueing
vs. OOM vs. silent request drops) is whatever vLLM's untuned defaults happen to do, and there is no
visibility (per OBS-07) into how close to that ceiling the system currently is.

**Minimal fix:** tune `--max-num-seqs` to a value the memory budget can sustain and expose it via
`/v1/models` or a small metrics scrape; for LiteLLM, add a `litellm_config.yaml` with explicit
rate-limit / retry / fallback-model settings instead of the bare CLI single-model invocation.

---

## OBS-14 — MEDIUM — TRIBE has no crash supervisor on its documented local run path
**Files:** `tribe_scorer/start.sh` (whole file — plain `python.exe main.py`, no restart wrapper),
`scripts/start_all.sh:26-40` (starts TRIBE once, waits up to 120s for first health, no ongoing
monitoring), contrast `docker-compose.rocm.yml:181` (`restart: unless-stopped` — only for the
containerized ROCm path)

**Why it fails:** the primary documented local-hardware workflow (`bash tribe_scorer/start.sh`) runs
TRIBE as a bare foreground process. If it crashes — CUDA OOM under concurrent scoring load, the
documented stale-CUDA-context-after-sleep scenario `tribe_client.py` already works around, or any
unhandled exception — nothing restarts it. The only recovery path is a human running
`scripts/restart_tribe.sh`. Given TRIBE is the single serialized bottleneck for the entire pipeline
(OBS-07), an unnoticed crash silently stalls every campaign in-flight and every new one queued behind
it, with `/api/health` correctly reporting `unavailable` but nothing paging anyone.

**Minimal fix:** wrap `tribe_scorer/start.sh` in a restart loop (`while true; do "$VENV_PYTHON" main.py; sleep 2; done`)
or run it under a lightweight supervisor (e.g. `supervisord`, or on Windows a scheduled task with
restart-on-failure) for the native/local path.

---

## OBS-15 — LOW — `orchestrator/api/__init__.py` builds a throwaway `FastAPI` app at import time
**File:** `orchestrator/api/__init__.py:264`

```python
# Module-level app instance for uvicorn
app = create_app()
```

When launched via the documented `uvicorn orchestrator.api:create_app --factory --port 8000`, uvicorn
imports the module to resolve the `create_app` factory — which executes this module-level line and
builds (and immediately discards) one full `FastAPI` app, including its router imports, before uvicorn
then calls `create_app()` again itself to get the app it actually serves. Harmless (no lifespan runs on
the discarded instance) but wasteful, and a footgun for anyone who imports `orchestrator.api` for
tooling/introspection and doesn't expect side effects.

**Minimal fix:** guard the module-level instantiation with `if __name__ == "orchestrator.api":` is not
idiomatic for this use case — simplest is to drop the module-level `app = create_app()` entirely and
have any direct-uvicorn users invoke `orchestrator.api:app` via a one-line separate `asgi.py` shim, or
just accept the factory-only entry point and remove the redundant instance.

---

## What breaks first at 100 users × 100 agents

**TRIBE v2's single process-wide `_inference_lock` (`tribe_scorer/main.py:400`) backs up into an
invisible, multi-hour queue while `/api/health` keeps reporting "ok" the whole time.** TRIBE serializes
*all* scoring calls behind one `threading.Lock` by design (one GPU, one model). With
`default_variants_per_iteration=2` (`orchestrator/config.py:157-162`), 100 concurrent users each running
one campaign submit on the order of 200 simultaneous TRIBE-scoring requests in the very first iteration
alone. The client is willing to wait up to `SCORE_TIMEOUT=5400s` (90 minutes,
`orchestrator/clients/tribe_client.py:29`) per call, so nothing times out fast — every request just
queues silently behind the one lock. There is no queue-depth metric anywhere in the stack (OBS-07), and
the health check TRIBE exposes (`tribe_scorer/main.py:850-909`) reports `status`/`cuda_healthy` but never
whether the lock is currently held or how many callers are waiting on it (`tribe_client.health_check()`,
`orchestrator/clients/tribe_client.py:109-133`, only interprets `status`/`cuda_healthy`). Compounding
this, the orchestrator process itself emits almost no diagnostic logs on this path in production
(OBS-02: `.info()` calls are silently dropped without `logging.basicConfig`), so the operator's first
signal that anything is wrong will be a wave of user-facing timeouts roughly 90 minutes after the
backlog started forming — with nothing in logs, health checks, or metrics to explain why, and no way to
tell whether it's TRIBE, MiroFish's Flask dev server (OBS-05), or the orchestrator itself that's stuck.
