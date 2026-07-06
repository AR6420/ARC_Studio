# Track 8 — Security Audit

Scope: `orchestrator/api/*.py`, `orchestrator/api/__init__.py`, `orchestrator/clients/*.py`,
`orchestrator/config.py`, `tribe_scorer/config.py`, `mirofish/backend/app/config.py`,
`mirofish/backend/app/api/*.py`, `mirofish/backend/app/storage/*.py`,
`mirofish/backend/app/models/project.py`, `mirofish/backend/app/utils/file_parser.py`,
`mirofish/backend/scripts/*.py`, `docker-compose*.yml`, `scripts/*.sh|*.ps1`,
`.env.hackathon.example`, repo-wide secret grep.

All findings verified by reading the cited code directly. Line numbers refer to the
files as they exist on `competition/amd-hackathon` at audit time.

---

## CRITICAL

### SEC-01 — Cypher injection via unsanitized entity-type label (two independent sinks)
**File:** `mirofish/backend/app/storage/neo4j_storage.py:282-292` and `:440-451`
**Also:** `mirofish/backend/app/storage/ner_extractor.py:152-199`, `mirofish/backend/app/services/report_agent.py:1055-1059`, `mirofish/backend/app/services/graph_tools.py:685-707`

```python
# neo4j_storage.py:284-290 (add_text -> _add_label, called during document ingestion)
def _add_label(tx, _name_lower=ename.lower()):
    tx.run(
        f"MATCH (n:Entity {{graph_id: $gid, name_lower: $nl}}) SET n:`{etype}`",
        gid=graph_id, nl=_name_lower,
    )
```

```python
# neo4j_storage.py:440-448 (get_nodes_by_label)
def get_nodes_by_label(self, graph_id: str, label: str) -> List[Dict[str, Any]]:
    def _read(tx):
        # Dynamic label in query (safe — label comes from ontology, not user input)
        query = f"""
            MATCH (n:Entity:`{label}` {{graph_id: $gid}})
            RETURN n, labels(n) AS labels
        """
```

`etype`/`label` are spliced into the Cypher text as a backtick-quoted label with no
escaping of embedded backticks, and no allowlist against the graph's actual ontology.

- **Sink 1 (ingestion path):** `etype` originates from `NERExtractor.extract()`
  (`ner_extractor.py`), which feeds arbitrary user-uploaded document text (PDF/MD/TXT,
  accepted via `mirofish/backend/app/api/graph.py:129-262 generate_ontology`) to an LLM
  and takes the `"type"` field straight out of the LLM's JSON response.
  `_validate_and_clean` (ner_extractor.py:152-199) strips whitespace but **never**
  validates the value is free of backticks/Cypher metacharacters, and explicitly keeps
  types that aren't even in the ontology ("keeping anyway", line 193). Any uploaded
  document whose content causes the extraction LLM to echo back a `type` value
  containing a backtick (accidentally, or via a crafted/adversarial document —
  classic indirect prompt injection) breaks out of the label and lets the attacker's
  text execute as Cypher against the shared Neo4j instance used by **every** project.
- **Sink 2 (report-agent tool path):** the code comment claims `label` "comes from
  ontology, not user input", but `graph_tools.py:685-707 get_entities_by_type` passes
  `entity_type` straight through to `get_nodes_by_label`, and its only caller,
  `report_agent.py:1055-1059`, takes `entity_type = parameters.get("entity_type", "")`
  directly from an LLM tool-call's arguments — i.e. from whatever the report-generation
  LLM decides to pass, itself conditioned on ingested document/simulation content. The
  in-code safety claim is false for this call path.

**Why it fails:** Neo4j backtick-quoted identifiers are only escaped by doubling an
embedded backtick; a single literal backtick followed by attacker text terminates the
label and the remainder is parsed as Cypher. E.g. an entity type value of
`` Person`}) DETACH DELETE n WITH 1 as x MATCH (m) DETACH DELETE m // `` would (after
Neo4j-side identifier parsing) allow arbitrary read/write/delete across the whole
database that backs every user's project. At 100-user scale this is a single shared
Neo4j instance (`docker-compose.yml` — one `neo4j` service), so one malicious upload
by any one of the 100 users can corrupt or exfiltrate every other user's knowledge
graph.

**Fix:** Never interpolate untrusted strings into Cypher structural positions
(labels). Either (a) map entity types to a small server-side allowlist derived from
the ontology definition *before* interpolation and reject anything not in it, or
(b) avoid dynamic labels entirely and store the type as a property (`n.entity_type =
$etype`, parameterized) with a separate index, matching on the property instead of a
dynamic label.

---

### SEC-02 — Arbitrary destructive directory deletion via `project_id` path traversal
**File:** `mirofish/backend/app/models/project.py:113-115, 222-238`
**Route:** `mirofish/backend/app/api/graph.py:77-93` (`DELETE /api/graph/project/<project_id>`)

```python
@classmethod
def _get_project_dir(cls, project_id: str) -> str:
    return os.path.join(cls.PROJECTS_DIR, project_id)   # no sanitization

@classmethod
def delete_project(cls, project_id: str) -> bool:
    project_dir = cls._get_project_dir(project_id)
    if not os.path.exists(project_dir):
        return False
    shutil.rmtree(project_dir)          # recursive, unauthenticated
    return True
```

**Why it fails:** `project_id` is never validated against the server-generated format
(`proj_<12 hex chars>`, `project.py:145`). Flask's default `<project_id>` URL
converter only rejects a literal `/` in the segment — it does **not** reject `\`. On
the Windows host this stack runs on (per environment), `os.path.join` and
`shutil.rmtree` both honor backslash as a path separator, so a request such as
`DELETE /api/graph/project/..\\..\\..\\some\\other\\folder` is routed as a single
path segment (no `/`, so Werkzeug accepts it), reaches `_get_project_dir` unmangled,
and `shutil.rmtree` recursively deletes whatever directory that resolves to — no
confirmation, no ownership check (there is no ownership concept at all), no auth.
Even without traversal, any of the 100 concurrent users can already delete every
other user's project by simply enumerating IDs off `GET /api/graph/project/list`
(no filtering by requester) — the traversal only makes it worse by extending the
blast radius outside the intended `uploads/projects/` tree entirely.

**Fix:** Validate `project_id` against `^proj_[0-9a-f]{12}$` before any filesystem
use (mirror the `_AGENT_ID_RE` pattern already used in
`orchestrator/api/agents.py:16`); additionally verify the resolved path's realpath is
still inside `PROJECTS_DIR` before calling `rmtree`.

---

### SEC-03 — Arbitrary file read / cross-tenant exfiltration via unrestricted `media_path`
**File:** `orchestrator/api/schemas.py:33-79` (`CampaignCreateRequest.media_path`),
`orchestrator/clients/tribe_client.py:302-347, 349-395`,
`tribe_scorer/main.py:784-841`

```python
media_path: str | None = Field(
    default=None, validate_default=True,
    description="Absolute path on the orchestrator host to an uploaded audio or video file...",
)
@field_validator("media_path")
@classmethod
def _media_path_required_for_media(cls, v, info):
    media_type = info.data.get("media_type", "text")
    if media_type in ("audio", "video") and not v:
        raise ValueError(...)      # only checks non-empty — no path containment/extension check
    return v
```

`POST /api/campaigns` accepts any client-supplied `media_path` string as long as it's
non-empty; nothing checks it resolves inside `settings.audio_upload_dir_absolute`
(the directory `POST /api/campaigns/upload` actually writes into,
`orchestrator/config.py:255-260`), nor that the extension matches an allowed list.
`campaign_runner.py:178-191` forwards this value verbatim to
`TribeClient.score_audio`/`score_video`, which POST `{"audio_path": ...}` /
`{"video_path": ...}` to the TRIBE scorer. TRIBE's own endpoints
(`tribe_scorer/main.py:773-841`) only validate duration/resolution of *whatever file
is at that path* — they never confine the path to an upload directory either.

**Why it fails:** Any of the 100 users can create a campaign with
`media_type="audio"` and `media_path` pointing at a file they don't own — e.g. another
user's UUID-named upload under the shared `AUDIO_UPLOAD_DIR` (guessable/enumerable
since UUIDs may leak via campaign list responses that echo `media_path`, or simply any
other audio/video file readable by the TRIBE process. TRIBE will faithfully run
Whisper transcription on it and return the transcript, which the orchestrator then
stores on the *new* campaign and serves back via `GET /api/campaigns/{id}` and
`GET /api/campaigns/{id}/export/json` (`orchestrator/api/reports.py:37-65`) — turning
the whole pipeline into an arbitrary-file-content-disclosure oracle for any file the
TRIBE process can read, scoped only by "is it decodable as audio/video and under the
duration cap".

**Fix:** In the `media_path` validator (or in `create_campaign`), resolve the path and
reject any value whose resolved parent is not `settings.audio_upload_dir_absolute`;
additionally have TRIBE's `/api/score_audio`/`/api/score_video` reject paths outside
its own configured upload mount rather than trusting the caller.

---

### SEC-04 — Insecure-by-default Flask config: DEBUG defaults True, HOST defaults 0.0.0.0
**File:** `mirofish/backend/app/config.py:25`, `mirofish/backend/run.py:40-45`

```python
# config.py:25
DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'   # defaults to True!
```
```python
# run.py:40-45
host = os.environ.get('FLASK_HOST', '0.0.0.0')   # defaults to ALL interfaces
port = int(os.environ.get('FLASK_PORT', 5001))
debug = Config.DEBUG
app.run(host=host, port=port, debug=debug, threaded=True)
```

**Why it fails:** The only deployment path that is safe today is the documented one —
`docker-compose.yml:81` / `docker-compose.rocm.yml:141` both explicitly set
`FLASK_DEBUG: "false"`. Any other invocation of this Flask app (a developer running
`python backend/run.py` directly for local debugging, a future ops script, a
non-compose cloud deployment of the MI300X node where env wiring is incomplete) gets
`debug=True` bound to `0.0.0.0` by default. Werkzeug's debug mode, on any unhandled
exception, serves an interactive in-browser Python console with **no authentication**
— a textbook unauthenticated remote code execution surface, reachable from any host
that can route to port 5001. Given the number of broad `except Exception` handlers
that *do* return JSON (masking most exceptions from ever reaching Werkzeug), the
realistic trigger is an exception in Flask/Werkzeug internals themselves (e.g. request
parsing, `before_request`/`after_request` hooks) rather than route bodies — but the
default is dangerous regardless of how often it's hit in practice.

**Fix:** Flip the default: `DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() ==
'true'`, and default `FLASK_HOST` to `127.0.0.1` unless explicitly overridden for a
containerized deployment that already restricts the host port binding.

---

## HIGH

### SEC-05 — No authentication/authorization anywhere; full cross-user ID enumeration
**Files:** all of `orchestrator/api/*.py`, all of `mirofish/backend/app/api/*.py`

There is no auth on any endpoint in either service (explicitly by design for Phase 1,
per `CLAUDE.md`), and — more importantly for the 100-user/100-agent scaling target —
there is **no tenant/ownership concept at all**. List endpoints return every record
regardless of caller:
- `GET /api/campaigns` (`orchestrator/api/campaigns.py:403-407`) — all campaigns, all users.
- `GET /api/graph/project/list` (`mirofish/backend/app/api/graph.py:62-74`) — all projects.
- `GET /api/simulation/list` / `/history` (`mirofish/backend/app/api/simulation.py:780-806, 868-979`) — all simulations.

Every mutating/destructive endpoint accepts any ID with zero ownership check:
`DELETE /api/campaigns/{id}`, `POST /api/simulation/stop`, `POST /api/simulation/start
{"force": true}` (kills another user's in-progress run), `DELETE
/api/graph/delete/{graph_id}`, `DELETE /api/graph/project/{id}`.

**Why it fails at 100×100 scale:** with 100 concurrent users on a shared deployment,
any user (or a single compromised browser tab, since CORS/no-auth means any JS running
in that origin has full API access) can read, hijack, stop, or delete every other
user's in-flight campaign/simulation. This isn't a hypothetical privilege-escalation —
it's the default behavior of every list/detail/delete route today. This is the
single biggest gap between "Phase 1 single-user POC" and the stated 100-user target;
it needs to be called out explicitly as a hard scope boundary, not silently
inherited into a multi-user deployment.

**Fix:** Before exposing this to more than one trusted user: add a minimal
per-request identity (API key or session), stamp `campaign`/`project`/`simulation`
rows with an owner id at creation, and filter every list/get/delete query by
`owner_id = current_user`.

---

### SEC-06 — Path traversal into arbitrary SQLite file via `platform` query parameter
**File:** `mirofish/backend/app/api/simulation.py:1982-2039` (`get_simulation_posts`)

```python
platform = request.args.get('platform', 'reddit')     # attacker-controlled, unsanitized
sim_dir = os.path.join(os.path.dirname(__file__), f'../../uploads/simulations/{simulation_id}')
db_file = f"{platform}_simulation.db"
db_path = os.path.join(sim_dir, db_file)
...
conn = sqlite3.connect(db_path)     # creates the file if it doesn't exist
```

**Why it fails:** although the SQL itself is parameterized (`cursor.execute("... LIMIT
? OFFSET ?", (limit, offset))` — good), the *path to the database file* is built from
an unsanitized query parameter. `platform` is not restricted to `{twitter, reddit}`
anywhere before this string is built, so a request like
`GET /api/simulation/<sim_id>/posts?platform=../<other_sim_id>/reddit` resolves
`db_file` to `../<other_sim_id>/reddit_simulation.db`, letting the caller open (and
query) **any other simulation's** SQLite database — a direct cross-tenant read
primitive requiring only knowledge/guessing of another `simulation_id`. Because
`sqlite3.connect()` silently creates the target file if it is missing, a crafted
`platform` value can also plant a new empty `.db` file at an arbitrary path under
`uploads/simulations/`, subject only to OS write permissions.

**Fix:** Restrict `platform` to a literal allowlist (`{"twitter", "reddit"}`) before
building `db_file`, and additionally verify `os.path.realpath(db_path)` is still
inside `sim_dir` before connecting.

---

### SEC-07 — Path traversal via unsanitized `simulation_id` from request body
**File:** `mirofish/backend/app/api/simulation.py:230-346, 390-746` (`/prepare`,
`/prepare/status`), `mirofish/backend/app/services/simulation_runner.py` (repeated
`os.path.join(cls.RUN_STATE_DIR, simulation_id)` at lines 244, 300, 340, 483, 701,
911, 1125, 1149, 1243, 1382, 1400, 1454, 1516, 1573, 1626, 1737)

Unlike routes where `simulation_id` is a URL path segment (Werkzeug's default
converter rejects an embedded `/`), `/api/simulation/prepare` and
`/api/simulation/prepare/status` read `simulation_id` from the **JSON body**
(`data.get('simulation_id')`), which is not restricted at all. That same
unsanitized string is joined into a directory path in over a dozen places in
`simulation_runner.py`, and is subsequently used as the subprocess `cwd` when a
simulation is actually launched (`simulation_runner.py:401-450`,
`cwd=sim_dir`).

**Why it fails:** a caller can pass `simulation_id="../<victim_sim_id>"` to `/prepare`
or `/prepare/status` and operate against another user's simulation directory (probe
its preparation state, or — combined with `force_regenerate`/`force` flags elsewhere
in the same file — potentially disturb another user's in-flight run), entirely
bypassing whatever weak segmentation the URL-based routes provide. This compounds
SEC-05 (no ownership) with a traversal that reaches outside the intended
`uploads/simulations/<id>/` sandbox altogether.

**Fix:** Validate `simulation_id` against `^sim_[0-9a-f]{12}$` (the format it's
actually generated in, `simulation_manager.py:213`) at the top of every route/service
method that accepts it as input, regardless of whether it arrived via URL or JSON
body.

---

### SEC-08 — Real secret committed to a "template" env file's working tree
**File:** `.env.hackathon.example:49` (working tree, uncommitted), vs. `HEAD` (commit
`c45fa26`)

```
# HEAD (committed):           HF_TOKEN=hf_REPLACE_ME
# working tree (uncommitted): HF_TOKEN=hf_<REAL-TOKEN-REDACTED-38-chars>
```

`.env.hackathon.example` is explicitly documented as "the template that IS committed"
(its own header: *"`.env.hackathon` itself is gitignored. Only this template is
committed."*). The current working copy has had the placeholder replaced with what
looks like a real, live-format HuggingFace token (`hf_` + 34 chars) — the same value
present in the gitignored `.env` (`.env:48`) and `.env.hackathon` (`.env.hackathon:49`).
This is one `git add .env.hackathon.example && git commit` away from landing a real
credential permanently in git history, on a branch (`competition/amd-hackathon`) that
is a public hackathon submission.

Also noted (not itself a leak, since correctly gitignored per `.gitignore:6-8`): the
top-level `.env` additionally holds a live-looking Anthropic OAuth token
(`.env:6`, `sk-ant-oat01-...`) and a second HF token (`.env:49`,
`hf_<REDACTED>`) in cleartext.

**Fix:** Revert `.env.hackathon.example` to the placeholder before any commit/push;
add a pre-commit secret-scan (gitleaks/truffleHog) so a real-looking token in a
tracked `*.example`/`*.sample` file fails CI rather than relying on manual review.

---

## MEDIUM

### SEC-09 — Stack traces returned to any caller on error (endemic, 53+ sites)
**Files:** `mirofish/backend/app/api/simulation.py` (49 occurrences),
`mirofish/backend/app/api/report.py` (multiple, e.g. lines 113,161,173,185,207,219,
269,283,300,314,336,349,359,372,382,404,422), `mirofish/backend/app/api/graph.py:261,
573,596`

Pattern repeated on nearly every route:
```python
return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500
```
Every unhandled exception leaks the full Python traceback — internal file paths,
library versions, and sometimes parameter values embedded in the exception message —
to any unauthenticated caller. Combined with SEC-05 (no auth), this is free
reconnaissance for an attacker probing the other findings in this report (e.g. it
will readily confirm whether a Cypher-injection payload actually reached
`neo4j_storage.py` and where).

**Fix:** Log `traceback.format_exc()` server-side only; return a generic error
message (and, if useful for support, an opaque request/error id) to the client.

---

### SEC-10 — Wildcard CORS on the MiroFish Flask API
**File:** `mirofish/backend/app/__init__.py:43`

```python
CORS(app, resources={r"/api/*": {"origins": "*"}})
```
Every `/api/*` route on the MiroFish backend allows cross-origin requests from *any*
origin. Combined with zero authentication (SEC-05), any website open in a victim's
browser can script requests against MiroFish (create/delete projects, stop
simulations, chat with agents) if the port is network-reachable from that browser —
today limited by `docker-compose.yml`'s `127.0.0.1:5001:5001` binding, but that
restriction lives entirely in the compose file, not in the application, so it
silently disappears the moment anyone runs this outside that exact compose
configuration (e.g. `python run.py` directly, per SEC-04's `0.0.0.0` default).

**Fix:** Restrict `origins` to the actual UI/orchestrator origin(s), the same way
`orchestrator/api/__init__.py:244-251` already restricts to `http://localhost:5173`.

---

### SEC-11 — Weak hardcoded Neo4j password default
**Files:** `orchestrator/config.py:85-88`, `mirofish/backend/app/config.py:38`,
`orchestrator/api/health.py:82-84`

```python
neo4j_password: str = Field(default="mirofish", ...)                      # orchestrator/config.py
NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', 'mirofish')             # mirofish/backend/app/config.py
neo4j_password=os.environ.get("NEO4J_PASSWORD", settings.neo4j_password), # health.py — double fallback to the same default
```
`docker-compose.yml:20,71` do force `NEO4J_PASSWORD` to be set
(`${NEO4J_PASSWORD:?NEO4J_PASSWORD must be set in .env}`), so the compose path is
safe as configured. But every Python-level default still falls back to the
well-known literal `"mirofish"` the moment either service is run outside that exact
compose invocation, or if `.env` is ever missing the var. This is a real risk on the
cloud MI300X target if Neo4j's Bolt/HTTP ports are ever bound beyond loopback for
that deployment (nothing in the *application* enforces loopback-only — only the
compose file's port mapping does).

**Fix:** Make `neo4j_password` a required setting with no default (fail closed,
mirroring the compose-level `:?` behavior) rather than silently defaulting to a
guessable string.

---

### SEC-12 — Latent SSRF/credential-relay primitive in `get_neo4j_stats`
**File:** `orchestrator/clients/mirofish_client.py:210-281`

```python
async def get_neo4j_stats(self, neo4j_url: str = "http://localhost:7474",
                           neo4j_user: str = "neo4j", neo4j_password: str = "") -> dict | None:
    ...
    resp = await client.post(f"{neo4j_url}/db/neo4j/tx/commit", json={...},
                              headers={"Authorization": f"Basic {auth_str}", ...})
```
The method will POST Basic-Auth-bearing requests to *any* `neo4j_url` passed in, with
no allowlist of hosts/schemes. It is not currently reachable with attacker-controlled
input — the only caller, `orchestrator/api/health.py:79-85`, hardcodes
`http://localhost:7474` — so this is not exploitable today. Flagging because it is
exactly the shape of primitive ("fetch this URL with these credentials, return the
body") that turns into SSRF the moment any future feature (e.g. a
user-configurable Neo4j endpoint) threads a parameter into it.

**Fix:** If this ever becomes user-configurable, validate `neo4j_url` against an
explicit allowlist of expected hosts before use; until then, no action required
beyond awareness.

---

## LOW

### SEC-13 — Orchestrator CORS hardcoded to `localhost:5173`, blocking (not breaking) the 100-user target
**File:** `orchestrator/api/__init__.py:244-251`

```python
application.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    ...
)
```
Not a live vulnerability (single fixed origin, not a wildcard), but it hard-blocks
any real multi-user/cloud deployment of the UI from a different origin — meaning
whoever adapts this for the 100-user target *will* have to touch this line, and must
not reach for `allow_origins=["*"]` (invalid combined with `allow_credentials=True`
per the CORS spec, and browsers will reject it) or a reflected-origin wildcard, which
would reintroduce the cross-origin risk described in SEC-10. Flagging so the fix is
made deliberately (explicit origin allowlist) rather than by trial-and-error under
deadline pressure.

### SEC-14 — ROCm containers run fully unconfined (seccomp) with `SYS_PTRACE`
**File:** `docker-compose.rocm.yml:56-58, 102-104` (`vllm-orchestrator`, `vllm-agents`),
similarly `tribe_scorer` service (`:176-178`)

```yaml
cap_add: [SYS_PTRACE]
security_opt: [seccomp:unconfined]
ipc: host
```
This is a standard requirement for ROCm GPU containers, not a bug introduced by this
codebase — but it does mean that if the vLLM or TRIBE process is ever compromised
(e.g. a malicious/poisoned model weight, or a dependency CVE in the inference stack),
the container has materially less syscall-level containment than a default Docker
container, and `ipc: host` shares the host IPC namespace across all three GPU
containers. Worth tracking as accepted risk, not something to "fix" blindly (removing
it will likely break ROCm), but should be revisited if this stack is ever exposed
beyond a single trusted operator's cloud VM.

### SEC-15 — Startup process writes live secrets to a plaintext `.env` with no permission hardening
**File:** `orchestrator/api/__init__.py:28-122` (`_refresh_litellm_api_key`)

Every orchestrator startup (when `LLM_PROVIDER=anthropic`) reads the OAuth access
token from `~/.claude/.credentials.json` and rewrites `.env` at the repo root with
the current token in cleartext (`orchestrator/api/__init__.py:79-96`), then shells
out to `docker compose up -d litellm` (`:99-122`). The file is rewritten with the
default `open(..., "w")` mode and no `os.chmod`, so on any multi-user host its
permissions are whatever the umask leaves them at — not obviously wrong for a
single-user Phase-1 POC, but worth tightening (`os.chmod(env_path, 0o600)` after
write) before this pattern is inherited into a shared cloud host serving 100 users
where other local accounts/processes might read the file.

---

## Non-findings worth recording (things that were checked and are fine)

- `orchestrator/storage/campaign_store.py:255-286` builds one dynamic
  `UPDATE campaigns SET {...}` fragment, but the interpolated parts are a fixed,
  code-reviewed whitelist of column fragments (`"status = ?"`, `"started_at = ?"`,
  etc.) with all *values* passed as bound parameters, and the function carries an
  explicit `# SECURITY:` comment warning against ever appending user-supplied
  strings to the list. Not an injection.
- `mirofish/backend/app/api/simulation.py:2024-2032` (`get_simulation_posts`) — the
  SQL itself (`... LIMIT ? OFFSET ?`) is correctly parameterized; the vulnerability
  there (SEC-06) is in the *path* to the db file, not the SQL.
- `mirofish/backend/app/models/project.py:256-262` (`save_file_to_project`) generates
  a random UUID-based filename for uploaded files rather than trusting the client's
  `original_filename` for the on-disk name — no traversal via upload filenames.
- `docker-compose.yml` / `docker-compose.rocm.yml` bind every host port to
  `127.0.0.1` explicitly (no `0.0.0.0` bindings, no `privileged: true`); the
  `NEO4J_PASSWORD`/`ANTHROPIC_API_KEY` values are read from `.env` via variable
  substitution, not hardcoded into the compose files.
- `scripts/refresh-env.sh` passes the extracted token to Python via `argv`, not
  through shell interpolation/`eval` — no command injection.
- `orchestrator/api/agents.py:16,40-41` validates `agent_id` with a strict
  `^[a-zA-Z0-9_-]{1,128}$` regex before using it in any downstream call — a good
  pattern that the mirofish `project_id`/`simulation_id` handling (SEC-02, SEC-07)
  should be brought up to.

---

## What breaks first at 100 users × 100 agents

**The Cypher-injection path (SEC-01) into the single shared Neo4j instance is the
highest-confidence break.** At 100 concurrent users, MiroFish's Neo4j (one
`docker-compose.yml` service, one database, no per-tenant graph isolation beyond a
`graph_id` property) is hammered continuously by ontology/document ingestion across
every user's campaigns. Every ingestion runs entity extraction through an LLM whose
`type` output is trusted verbatim into a Cypher label (`neo4j_storage.py:286`) with
no sanitization — and at that volume of uploaded documents and LLM calls, it does not
even require a deliberately malicious user: an ordinary uploaded document containing
a stray backtick in a phrase the extraction LLM copies into an entity "type" (code
names, quoted slang, markdown inline-code spans like `` `Foo` `` inside a PDF/MD
upload) is enough to produce a malformed/injected Cypher statement that either throws
(caught and logged as a warning, `neo4j_storage.py:291-292` — silently corrupting or
skipping data with no user-visible error) or, worse, executes destructively against
shared graph data belonging to unrelated users' campaigns. Because this shared
Neo4j instance backs every simulation for every one of the 100 users, the failure
mode isn't "one user's simulation breaks" — it's silent, cross-tenant graph
corruption/data loss the very first time a document with the right byte sequence is
ingested, with no auth boundary (SEC-05) to even attribute which user's upload caused
it.
