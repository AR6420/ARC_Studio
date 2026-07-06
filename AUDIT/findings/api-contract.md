# Track 7 — API & Contract Integrity Audit

Scope: `orchestrator/api/{schemas,campaigns,progress,reports,agents,health}.py`,
`orchestrator/clients/{mirofish_client,tribe_client}.py` vs
`mirofish/backend/app/api/{simulation,graph,report}.py` and `tribe_scorer/main.py`,
`ui/src/api/*.ts` vs orchestrator schemas.

Scaling target audited against: ~100 concurrent users, up to ~100 in-app agents
each (~10,000 concurrent agents), many concurrent campaigns/simulations, local
or cloud hardware.

All line numbers verified against the working tree at audit time.

---

## API-01 — CRITICAL — Agent-chat/interview contract is completely broken end-to-end

**Files:** `orchestrator/clients/mirofish_client.py:572-593`, `orchestrator/api/agents.py:27-55`, `mirofish/backend/app/__init__.py:79-81`, `mirofish/backend/app/api/simulation.py:2137-2263`, `orchestrator/api/schemas.py:110-124`, `orchestrator/engine/mirofish_runner.py:114`, `orchestrator/storage/campaign_store.py:289-323,475-491`

**What's wrong:** `MirofishClient.chat_agent()` POSTs to `f"/api/agent/{agent_id}/chat"`:

```python
resp = await self._client.post(
    f"/api/agent/{agent_id}/chat",
    json={"message": message},
    timeout=30.0,
)
```

That route does not exist anywhere in MiroFish. `app/__init__.py` registers exactly
three blueprints — `graph_bp` (`/api/graph`), `simulation_bp` (`/api/simulation`),
`report_bp` (`/api/report`) — and a full-file grep for `chat` in `app/api/*.py`
turns up only `report_bp.route('/chat', ...)` (a *report* chat-with-analysis-agent
feature, unrelated). The real per-agent interview endpoint is
`POST /api/simulation/interview`, which requires a JSON body of
`{simulation_id, agent_id, prompt, platform?, timeout?}` and additionally requires
the simulation environment to be alive (`SimulationRunner.check_env_alive`).

Compounding root cause: even if the URL were fixed, the orchestrator has nowhere
to get `simulation_id` from. `mirofish_runner.py:114` does capture
`unwrapped["simulation_id"] = raw_results.get("simulation_id")` into the raw
results dict, but `MirofishMetrics` (`schemas.py:110-124`) declares no
`simulation_id` field. `campaign_store.save_iteration()` (`campaign_store.py:289-323`)
stores whatever dict it's given via `json.dumps(mirofish_metrics)` — so the raw
JSON blob in SQLite may still contain it — but every read path
(`campaign_store.py:475-491`) reconstructs via
`MirofishMetrics(**json.loads(mirofish_raw))`, and Pydantic v2's default
`extra="ignore"` silently drops any key not declared on the model. So
`simulation_id` never survives a round-trip through the API layer.

**Why it fails (concrete):** UI calls `POST /api/campaigns/{id}/agents/{agentId}/chat`
(`ui/src/api/campaigns.ts:64-76`) → orchestrator's `agents.py` validates `agent_id`
against a regex, then calls `mirofish.chat_agent(agent_id, message)` with **no**
`campaign_id` or `simulation_id` in the call at all → `chat_agent()` hits MiroFish's
Flask router for `/api/agent/<anything>/chat` → Flask returns 404 (no matching
route) → `resp.status_code == 200` check fails → `chat_agent()` returns `None` →
`agents.py:46-50` raises `HTTPException(502, "MiroFish agent chat unavailable")`.
This happens on **every single call, 100% of the time**, regardless of load —
the "agent interview" feature advertised in `AgentChatRequest`/`AgentChatResponse`
(`schemas.py:411-421`) and wired into the UI is non-functional.

**Fix:** (1) Add `simulation_id: str | None` to `MirofishMetrics` (or a dedicated
lookup table keyed by campaign+iteration+variant) so it survives storage
round-trips. (2) Change `MirofishClient.chat_agent` to call
`POST /api/simulation/interview` with `{simulation_id, agent_id: int(agent_id), prompt: message, timeout}`,
resolving `simulation_id` from the campaign's stored iteration data instead of
being agent_id-only. (3) Pass `campaign_id`/iteration context through
`agents.py` to pick the right simulation, and surface MiroFish's actual
`env_alive`-not-ready case as a distinct error rather than a generic 502.

---

## API-02 — CRITICAL — No user identity anywhere; campaign list/delete is fully unscoped and unbounded

**Files:** `orchestrator/api/schemas.py:18-79` (`CampaignCreateRequest`), `orchestrator/storage/campaign_store.py:101-148,186-228`, `orchestrator/api/campaigns.py:352-460`

**What's wrong:** There is no `user_id`/owner concept anywhere in the API contract.
`CampaignCreateRequest` has no identity field; the `campaigns` table INSERT
(`campaign_store.py:108-131`) writes `(id, status, seed_content, prediction_question,
demographic, demographic_custom, agent_count, max_iterations, thresholds,
constraints, created_at, media_type, media_path)` — no owner column exists.
`list_campaigns()` (`campaign_store.py:186-228`) issues:

```sql
SELECT c.*, (SELECT COUNT(DISTINCT iteration_number) ...) AS iterations_completed
FROM campaigns c
ORDER BY c.created_at DESC
```

with **no `WHERE`, no `LIMIT`, no `OFFSET`**. `GET /api/campaigns`
(`campaigns.py:403-407`) simply returns whatever this query yields, and
`ui/src/api/campaigns.ts:33-35`'s `listCampaigns()` sends no query params at all.
`CampaignListResponse.total` (`schemas.py:253-257`) exists as a field, implying
pagination was planned, but it's just `len(campaigns)` on the full unbounded
result set. `DELETE /api/campaigns/{id}` (`campaigns.py:420-460`) likewise has no
ownership check — any caller who knows (or lists) any campaign id can delete it.

**Why it fails (concrete):** At 100 concurrent users each running campaigns, every
single user's browser (via React Query polling or manual refresh) receives, in
one response, the full `seed_content` (up to 25,000 chars each per
`schemas.py:44`), prediction questions, demographics, and scores for **every
campaign ever created by every other user** — a straightforward cross-tenant
data-disclosure with zero cost to exploit (no auth to bypass; it's already
returned to everyone). Response size and DB scan cost grow linearly with total
campaigns across all users forever, hit on the most frequently polled endpoint
in the system. Any user can also delete any other user's campaign (and its
uploaded media file, per the cascade in `campaigns.py:437-458`) by guessing or
observing an id.

**Fix:** Add an owner/session identifier to `CampaignCreateRequest`/the
`campaigns` table, scope `list_campaigns`/`get_campaign`/`delete_campaign` by
it, and add real `limit`/`offset` (or cursor) query params to `GET /api/campaigns`
enforced with a sane max (e.g. 50), matching the `total` field's implied intent.

---

## API-03 — CRITICAL — `media_path` is a client-supplied arbitrary absolute path with no origin check (file-disclosure primitive)

**Files:** `orchestrator/api/schemas.py:33-40`, `orchestrator/engine/campaign_runner.py:178-191`, `tribe_scorer/main.py:285-324,773-841`, `tribe_scorer/scoring/audio_scorer.py:45-81`

**What's wrong:** `CampaignCreateRequest.media_path` (`schemas.py:33-40`) is a
free-text field; the only validation (`_media_path_required_for_media`,
`schemas.py:68-79`) checks it's non-empty when `media_type` is audio/video —
nothing ties it to having actually come from `POST /api/campaigns/upload`
(the endpoint that writes under `settings.audio_upload_dir_absolute`,
`campaigns.py:195-198`). `campaign_runner.py:178-191` forwards this string
unmodified into `TribeClient.score_audio(media_path)` /
`score_video(media_path)`. On the TRIBE side, `AudioScoreRequest`/
`VideoScoreRequest` (`tribe_scorer/main.py:285-324`) and
`validate_audio_file()` (`audio_scorer.py:45-81`) only check that the path is
absolute, that the file exists, that its extension is in the supported list,
and that duration is within bounds — there is no allowlist/prefix check
requiring the path be under the sanctioned upload directory.

**Why it fails (concrete):** A client can call `POST /api/campaigns` directly
with `media_type: "audio"` and `media_path` pointing at **any** absolute path
on the TRIBE host ending in `.wav/.mp3/.flac/.ogg/.mp4/.webm/.mov` — e.g.
another user's previously-uploaded file (if the UUID filename is known/logged
anywhere, or via directory listing if storage is shared/NFS at cloud scale),
or any other media file reachable by the TRIBE process. TRIBE will transcribe
it via Whisper and the transcript is returned to the caller via
`TribeScores.transcript` (`schemas.py:107`) in the campaign's iteration data —
an arbitrary-file-content-disclosure channel gated only by "is it an audio/video
file under the duration limit."

**Fix:** Validate `media_path` server-side (in `CampaignCreateRequest` or at
campaign-start) against `settings.audio_upload_dir_absolute`/video equivalent
using a resolved-path prefix check (`Path(media_path).resolve().is_relative_to(upload_dir.resolve())`),
reject otherwise with 400.

---

## API-04 — HIGH — `demographic` is unvalidated free text; bad values crash the pipeline after burning GPU/LLM budget

**Files:** `orchestrator/api/schemas.py:46`, `orchestrator/engine/campaign_runner.py:306,663-675`, `orchestrator/prompts/demographic_profiles.py:406-416,437-442`, `orchestrator/api/campaigns.py:383-394`

**What's wrong:** `demographic: str = Field(...)` accepts any non-empty string —
it is never checked against the actual preset keys returned by
`GET /api/demographics` (`health.py:153-166`) nor against the literal string
`"custom"`. `_get_weights()` (`campaign_runner.py:663-675`) special-cases
`"custom"` but otherwise calls `get_cognitive_weights(demographic)` →
`get_profile(key)` (`demographic_profiles.py:406-416`), which **raises
`KeyError`** for any unrecognized key. This call happens at the composite-scoring
step (`campaign_runner.py:306`) — i.e. *after* variant generation (Haiku calls)
and TRIBE neural scoring (30-90s/text, possibly minutes with chunking) have
already run for every variant.

**Why it fails (concrete):** `POST /api/campaigns` with e.g.
`demographic: "tech_proffesionals"` (typo, or a stale UI dropdown value from a
version mismatch) returns `201 Created` immediately — looks successful — then
the background task (`campaigns.py:383-394`) runs the full expensive pipeline
and dies with an uncaught `KeyError`, caught only by the blanket
`except Exception` in `_run_background`, which reports the generic
`"Campaign failed — check server logs"` SSE event. At 100-user scale this is a
trivially-triggerable way to burn significant shared GPU/LLM capacity per bad
request with no fast-fail at request time.

**Fix:** Add a `field_validator` on `demographic` that checks membership in
`{"custom"} | {p["key"] for p in list_profiles()}` and raises a 422 at request
time.

---

## API-05 — HIGH — MiroFish action/simulation lists are unbounded or silently truncated; no pagination on growing collections

**Files:** `mirofish/backend/app/api/simulation.py:1758-1856` (`/run-status/detail`), `simulation.py:1859-1910` (`/actions`), `simulation.py:780-806` (`/list`), `mirofish/backend/app/api/graph.py:538-549` (`/tasks`), `orchestrator/clients/mirofish_client.py:595-631` (`_extract_results`)

**What's wrong:** `/<simulation_id>/run-status/detail` returns `all_actions`,
`twitter_actions`, and `reddit_actions` as the **complete** action log with no
limit at all (`SimulationRunner.get_all_actions` called with no bound,
`simulation.py:1811-1826`) — this is the endpoint used for "real-time" polling.
`/api/graph/tasks` (`graph.py:538-549`) returns every task ever created, no
limit param exists. `/api/simulation/list` (`simulation.py:780-806`) returns
every simulation matching an optional `project_id` filter, no limit/offset.
Separately, the orchestrator's own `_extract_results()`
(`mirofish_client.py:595-631`) calls `GET /api/simulation/{id}/actions` with
**no `limit`/`offset` params at all**, so it silently receives MiroFish's
default `limit=100` (`simulation.py:1881`) — for any simulation with more than
100 actions (the overwhelming majority once agent_count/rounds are realistic),
the data the orchestrator stores and scores against is silently truncated to
the first 100 actions, and nothing in `DataCompleteness` or elsewhere
indicates truncation occurred.

**Why it fails (concrete):** With "tens to hundreds of agents" over 30+ rounds
(per repo description), action counts reach into the thousands per simulation.
Every UI poll of `/run-status/detail` re-transmits the ever-growing full log
(bandwidth/latency degrades continuously through a run); and the orchestrator's
composite scoring / analysis for every campaign with a nontrivial simulation is
silently working from at most the first 100 of possibly thousands of actions,
which will skew `sentiment_trajectory`, `counter_narrative_count`, etc. without
any visible signal that the input was incomplete.

**Fix:** Have `mirofish_client._extract_results` paginate (`limit`+`offset`
loop) until it receives fewer than `limit` results, or explicitly request a
much larger bound; add hard max caps to every `limit` query param on the
MiroFish side (see API-12); add real pagination to `/list` and `/tasks`.

---

## API-06 — HIGH — No admission control / quota enforcement on concurrent campaigns

**Files:** `orchestrator/api/__init__.py:203-204,216-221`, `orchestrator/api/campaigns.py:361-398`, `tribe_scorer/main.py:400` (`_inference_lock`)

**What's wrong:** `app.state.running_tasks` is a plain dict with no size cap
(`__init__.py:203`). `POST /api/campaigns` with `auto_start=True`
(`campaigns.py:361-398`) unconditionally creates a queue and launches an
`asyncio.create_task` for every request — there is no check anywhere in the
contract for "how many campaigns are already running" before accepting a new
one, and no 429/503 admission-control response is defined in `schemas.py`.
Every one of those background tasks eventually serializes on TRIBE's single
process-wide `threading.Lock` (`tribe_scorer/main.py:400`) and drives the one
MiroFish Flask instance.

**Why it fails (concrete):** 100 concurrent users each auto-starting a campaign
(matching the audited scale target) produces 100 concurrent background tasks
that all return `201 Created` immediately, then silently queue behind the
single TRIBE lock and single MiroFish instance — for potentially hours, since
each TRIBE call alone can take up to 90 minutes per `SCORE_TIMEOUT`
(`tribe_client.py:29`). Nothing in the API response — no queue position, no
estimated wait beyond the flat `/api/estimate` formula (see API-16), no
429 — tells a user or the UI that their campaign is 87th in line rather than
progressing.

**Fix:** Add a configurable max-concurrent-campaigns limit; return `429`
(with `Retry-After`) from `POST /api/campaigns` once at capacity, or queue
explicitly and surface queue position via the SSE contract.

---

## API-07 — HIGH — CORS hardcoded to a single localhost origin; not deployable to the stated cloud scale target

**Files:** `orchestrator/api/__init__.py:244-251`

**What's wrong:**

```python
application.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    ...
)
```

This is a hardcoded literal, not sourced from `orchestrator.config.settings` or
any env var — every test file in the repo duplicates the same hardcoded value,
confirming it's never been made configurable.

**Why it fails (concrete):** The scaling target explicitly includes "cloud
hardware." Any real multi-user deployment serving the UI from a non-localhost
origin (e.g. `https://arc-studio.example.com`) will have **every** browser
`fetch`/`EventSource` call blocked by the browser's CORS enforcement, because
the server never sends an `Access-Control-Allow-Origin` matching that origin.
This is a hard, total failure the moment the UI is served from anywhere other
than `localhost:5173` — not a degradation, a wall.

**Fix:** Source `allow_origins` from `settings` (comma-separated env var),
defaulting to the current dev value for local use.

---

## API-08 — HIGH — TRIBE batch-scoring has all-or-nothing failure semantics

**Files:** `tribe_scorer/main.py:525-580` (`_run_batch_score`), `orchestrator/clients/tribe_client.py:247-300` (`score_texts_batch`)

**What's wrong:** `_run_batch_score` loops over every text in the batch inside
one HTTP handler; on the **first** text that raises (`ValueError`/`RuntimeError`
→ 422, anything else → 500), it raises an `HTTPException` that aborts the
*entire* `/api/score/batch` request — the exception is not caught per-item.
`TribeClient.score_texts_batch` (`tribe_client.py:247-300`) treats any non-2xx
response as total failure: `if resp is None: return [None] * len(texts)`.

**Why it fails (concrete):** If any single variant among N in a batch contains
pathological input that triggers a chunking timeout or inference exception
inside TRIBE, **every other, otherwise-healthy variant in that batch** gets
`tribe_scores=None` for the iteration — not just the offending one. The caller
has no way to know which text failed (TRIBE's error body doesn't identify an
index), so there's no retry-without-the-bad-one path either. This silently
degrades data completeness for an entire iteration because of one outlier
variant, which — at 100 concurrent campaigns generating varied LLM-authored
content — is a realistic, not edge-case, occurrence.

**Fix:** Make `_run_batch_score` catch per-item exceptions and return
per-item `is_pseudo_score`/error markers instead of aborting the whole
request; have the client only null out the specific failed index.

---

## API-09 — MEDIUM — `simulation/prepare/status` polling never forwards `task_id`; failed-prep detection delayed up to 10 minutes

**Files:** `orchestrator/clients/mirofish_client.py:460-517`, `mirofish/backend/app/api/simulation.py:230-346,634-744`

**What's wrong:** `_prepare_simulation()`'s polling loop
(`mirofish_client.py:481-513`) posts only `{"simulation_id": simulation_id}` to
`/api/simulation/prepare/status` — it never sends the `task_id` returned by the
initial `/prepare` call. MiroFish's `get_prepare_status()`
(`simulation.py:634-744`) only consults `task_id`-based progress when `task_id`
is present; with only `simulation_id`, it falls back to the file-based
`_check_simulation_prepared()` (`simulation.py:230-346`), which requires
`config_generated=True` even to report a `"failed"` status (line 301-302: the
`"failed"` string is in `prepared_statuses`, but it's AND-ed with
`config_generated`). If preparation fails *before* config generation, this
check returns `is_prepared=False` with no way to distinguish "still working" from
"already failed," and the client sees `status: "not_started"` the entire time.

**Why it fails (concrete):** A prep failure that happens early (e.g. LLM
profile generation error) is invisible to the orchestrator's poll loop — it
just keeps seeing `not_started`/looping — until `SIM_PREPARE_TIMEOUT` (600s)
elapses and the client gives up with a generic timeout, instead of detecting
the real failure within seconds. At 100 concurrent campaigns, each failed
simulation ties up a slot (and the surrounding retry/backoff machinery) for a
full 10 minutes longer than necessary.

**Fix:** Store and forward `task_id` in every subsequent poll to
`/prepare/status` so MiroFish's task-based fast-fail path is used.

---

## API-10 — MEDIUM — `run-status` polling only recognizes `"completed"`/`"failed"`; other `runner_status` values stall for the full timeout

**Files:** `orchestrator/clients/mirofish_client.py:519-570` (`_run_simulation`)

**What's wrong:** The poll loop only branches on
`runner_status == "completed"` and `runner_status == "failed"`; every other
value (e.g. `"stopped"` — reachable via MiroFish's own `POST /stop` endpoint,
or `"idle"`) is treated identically to "still running" and simply looped on.

**Why it fails (concrete):** If a MiroFish simulation the orchestrator is
waiting on gets externally stopped (operator intervention, MiroFish's own
force-restart-via-`force=true` path in `/start`, etc.), the client never
recognizes the terminal `"stopped"` state and keeps polling for the entire
`SIMULATION_RUN_TIMEOUT` (600s) before giving up — a 10-minute stall that
should have been an immediate, correctly-attributed failure.

**Fix:** Enumerate all terminal `runner_status` values from MiroFish's
`RunnerStatus` and branch on the full set, not just two of them.

---

## API-11 — MEDIUM — Unsanitized `simulation_id`/`graph_id` path segments used directly in filesystem joins

**Files:** `mirofish/backend/app/api/simulation.py:249,1056,1159,1999-2005,2075-2080`

**What's wrong:** Route handlers build filesystem paths directly from the URL
path segment with no format/allowlist check, e.g.:

```python
simulation_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
```

(repeated at `/profiles/realtime`, `/config/realtime`, `/posts`, `/comments`).
Flask/Werkzeug's default `<string:...>` route converter only excludes literal
`/` from the captured segment — it does not exclude `..` or (on Windows hosts)
`\`. `os.path.join` on Windows treats `\` as a real separator.

**Why it fails (concrete):** A crafted `simulation_id` such as
`..\..\..\Windows\System32\drivers\etc` (URL-encoded) passes Flask's route
matching (it contains no `/`) and, joined with `Config.OASIS_SIMULATION_DATA_DIR`
on a Windows-hosted deployment, can walk outside the simulation data directory.
Exploitability is bounded (the attacker only controls the directory, not the
final filename — `state.json`, `reddit_profiles.json`, etc. are fixed), but it
is a real defense-in-depth gap explicitly worth closing, especially since these
same MiroFish routes are hit directly by end-user browsers (the UI iframes
MiroFish's live view per `mirofish_client.py:324-333`'s comment), not just
server-to-server.

**Fix:** Validate `simulation_id`/`graph_id`/`report_id` path segments against
an allowlist regex (e.g. `^[A-Za-z0-9_-]+$`) at the top of every handler that
uses them in a filesystem path, rejecting otherwise with 400.

---

## API-12 — MEDIUM — Unbounded `limit`/`offset` params and silent int-coercion failures across MiroFish endpoints

**Files:** `mirofish/backend/app/api/simulation.py:881-885` (`/actions`), `simulation.py:996-997,2072-2073` (`/posts`,`/comments`), `simulation.py:904` (`/history`), `graph.py:67` (`/project/list`), `mirofish/backend/app/api/report.py:180` (`/report/list`), `simulation.py:2546-2547` (`/interview/history`)

**What's wrong:** Every one of these endpoints accepts a client-supplied
`limit` with a *default* but **no upper bound enforced** — `request.args.get('limit', 100, type=int)`
happily accepts `limit=999999999`. Separately, `agent_id = request.args.get('agent_id', type=int)`
(`simulation.py:1884`) silently returns `None` (not a 400) when given a
non-numeric value — a typo'd or malformed `agent_id` filter silently turns into
"no filter" (return all agents' actions) rather than an error. `/interview/history`'s
`limit = data.get('limit', 100)` (`simulation.py:2547`) isn't even passed
through `type=int` — a string value flows straight to downstream query code.

**Why it fails (concrete):** Any of the 100 concurrent browser clients (which
can reach MiroFish directly for the iframed live view) can force an
effectively-unbounded query/response on a shared Flask process backing every
other concurrent user's simulation — a straightforward self-service DoS lever
with no code change required, and no rate limiting anywhere to blunt it (see
also API-06).

**Fix:** Clamp every `limit` to a hard max (e.g. 500) server-side; make
`agent_id`/other typed filters return 400 on unparseable input instead of
silently defaulting to "unfiltered."

---

## API-13 — MEDIUM — SSE `event` field is an unconstrained `str`; UI's hardcoded event allowlist can silently drop new/misspelled events

**Files:** `orchestrator/api/schemas.py:377-389`, `ui/src/hooks/use-progress.ts:19-35`, `orchestrator/engine/campaign_runner.py` (multiple `_emit_step`/`_emit_layer` call sites), `orchestrator/engine/report_generator.py:155-211`

**What's wrong:** `ProgressEvent.event` is typed `str` (`schemas.py:380`), not a
`Literal`/enum — nothing in the API contract enforces that emitted event names
match a known set. The UI's `EventSource` handling
(`use-progress.ts:19-35,89-113`) only wires up `addEventListener` for a fixed,
hand-maintained array of event-type strings; per the `EventSource` spec, a
named SSE event with no matching listener is silently dropped — it does **not**
fall back to `onmessage`. There is no shared source of truth between (a) the
strings the engine actually emits, (b) `schemas.py`'s docstring comment listing
expected values, and (c) the UI's `EVENT_TYPES` array — all three must be kept
in manual lockstep. This drift already exists today: both `schemas.py`'s
comment and `use-progress.ts` reference `convergence_check`, but a repo-wide
search shows the engine never actually emits that event (dead/aspirational),
demonstrating the three lists have already diverged once, harmlessly, and could
diverge again without anyone noticing.

**Why it fails (concrete):** If a future engine change adds or renames an SSE
event (e.g. to report new pipeline stages) and the corresponding entry in
`use-progress.ts`'s `EVENT_TYPES` is forgotten, that event is silently
swallowed by every connected browser — no console error, no failed request,
just a UI that quietly stops updating for that stage. This is exactly the kind
of "silently-ignored unknown field" failure mode that is hard to catch in
review because nothing errors.

**Fix:** Define the event vocabulary once (e.g. a shared `Literal[...]` type in
`schemas.py`, code-generated into the TS types) and have the UI either listen
generically (`es.onmessage` + dispatch on `data.event`) or fail loudly (log a
warning) on an unrecognized `event:` field instead of silently dropping it.

---

## API-14 — LOW — UI TypeScript types drift from backend Pydantic schemas

**Files:** `ui/src/api/types.ts:101-107` (`DataCompleteness`), `types.ts:204-209` (`HealthResponse`), vs `orchestrator/api/schemas.py:142-154,315-324`

**What's wrong:** `DataCompleteness` in `types.ts` is missing `has_audio`,
`has_video`, and `media_type`, all present on the backend model
(`schemas.py:150-154`). `HealthResponse` in `types.ts` is missing `litellm`
and `neo4j`, both present on the backend model (`schemas.py:315-324`,
returned by `GET /api/health`).

**Why it fails (concrete):** Because TypeScript types are erased at runtime,
these fields are still present on the actual JSON payload and accessible via
bracket access or a cast, so nothing crashes — but any UI code written against
the typed interface gets no autocomplete/type-checking for them, and a
refactor of a component consuming these fields could drop them from a render
path with the compiler never flagging it as a regression.

**Fix:** Regenerate/hand-sync `types.ts` from `schemas.py` (or adopt a
schema-to-TS codegen step) so the two never silently diverge.

---

## API-15 — LOW — Neo4j health check hardcodes `localhost:7474` instead of using settings

**Files:** `orchestrator/api/health.py:79-85`, `orchestrator/clients/mirofish_client.py:210-214`

**What's wrong:** `health_check()` calls
`mirofish_client.get_neo4j_stats(neo4j_url="http://localhost:7474", ...)` — a
literal, not sourced from `orchestrator.config.settings`. The client method's
own default parameter repeats the same hardcode.

**Why it fails (concrete):** In any deployment where Neo4j isn't on the same
host as the orchestrator process (the norm for the stated "cloud" scale
target, and already the norm for the Dockerized services described in
CLAUDE.md), this silently fails — `get_neo4j_stats` catches the connection
exception and returns `None` (`mirofish_client.py:279-281`), so `health.py`
just omits `neo4j` from the response with only a `logger.warning`, no signal
in the actual API response indicating misconfiguration versus a genuinely-down
Neo4j.

**Fix:** Read the Neo4j HTTP URL from `settings` (there's already a pattern for
this elsewhere in the codebase, e.g. `settings.neo4j_user`/`neo4j_password`
right next to this call).

---

## API-16 — LOW — `POST /api/estimate` ignores `agent_count` entirely

**Files:** `orchestrator/api/progress.py:117-133`, `orchestrator/api/schemas.py:392-406`

**What's wrong:** `estimate_time()` computes
`variants_per_iteration(hardcoded 2) * max_iterations * 20.0` and never reads
`body.agent_count` in the formula — it's only echoed back unchanged in the
response.

**Why it fails (concrete):** Two requests differing only by
`agent_count=20` vs `agent_count=200` (a 10x difference, both within the
schema's valid `ge=20, le=200` range) get an identical time estimate, actively
misleading users who are trying to plan against the ≤20-minute campaign SLA
described in `CLAUDE.md` — the contract implies agent count matters
(it's a required-ish input) but the implementation silently no-ops on it.

**Fix:** Either fold a per-agent term into the formula or drop `agent_count`
from `EstimateRequest` so the contract doesn't imply a relationship that
doesn't exist.

---

# What breaks first at 100 users x 100 agents

**`POST /api/campaigns` has no admission control (API-06), and its most-polled
sibling `GET /api/campaigns` has no pagination or per-user scoping (API-02) —
together these are what visibly breaks first, before anything crashes.**

At the moment 100 users each launch a campaign (the exact scenario being
audited against), every one of those 100 `POST /api/campaigns` calls succeeds
with `201 Created` — the contract has no capacity signal, no `429`, no queue
position, nothing to indicate admission was throttled — because there is no
concurrency cap anywhere in `campaigns.py`/`campaign_runner.py`. All 100
background tasks are created immediately and start competing for the single
global TRIBE `threading.Lock` (`tribe_scorer/main.py:400`) and the single
MiroFish Flask process. Meanwhile every one of those 100 UIs is simultaneously
polling `GET /api/campaigns` (unscoped, unbounded, `campaign_store.py:186-228`)
to render its dashboard/list view — a query whose result set now contains all
100+ campaigns' full `seed_content`, growing with every additional campaign any
user creates, with no `LIMIT` clause capping the work SQLite does or the bytes
sent back.

The compound, observable failure mode is: within the first minute, every user's
UI is fetching a rapidly-growing, fully cross-tenant campaign list (visibly
slower every time anyone anywhere creates a campaign), while the 100
newly-created campaigns sit in `pending`/`running` status with no forward
progress signal beyond "still running" — because the actual inference work is
serialized behind one lock, but the API contract offers no way to distinguish
"queued behind 87 other campaigns" from "hung." Users will report the product
as "stuck" simultaneously, en masse, and support/logs will show 100
simultaneously-`running` campaign rows with no per-request diagnostic
(no request id, no queue position field in `ProgressEvent`) to tell them apart
— this is a pure API-contract gap (missing admission control + missing
pagination + missing progress-position signaling), not primarily a hardware
capacity problem, and it is the first thing every one of the 100 users will
notice, before any individual request times out or the process OOMs.
