# Track 5 — Error Handling & Resilience Audit

Scope: `orchestrator/clients/{claude_client,openai_compat_client,llm_factory,llm_protocol,tribe_client,mirofish_client}.py`,
`orchestrator/engine/{campaign_runner,optimization_loop}.py`, `orchestrator/api/{campaigns,progress}.py`,
`mirofish/backend/app/utils/{retry,llm_client}.py`,
`mirofish/backend/app/services/{ontology_generator,simulation_config_generator,oasis_profile_generator}.py`,
`tribe_scorer/main.py`.

Scale target audited against: ~100 concurrent users x ~100 agents each (~10,000 concurrent agents, many
concurrent campaigns/simulations), single shared GPU + single MiroFish/Neo4j/LiteLLM stack.

Findings are ordered most-severe first. Each cites exact `file:line`.

---

## CRITICAL

### ERR-01 — Synchronous subprocess/file-I/O call blocks the entire orchestrator event loop on every LiteLLM token refresh
**File:** `orchestrator/clients/mirofish_client.py:172-208` (`_attempt_token_refresh`), calling into
`orchestrator/api/__init__.py:28-122` (`_refresh_litellm_api_key`, `subprocess.run(["docker","compose","up","-d","litellm"], ..., timeout=60)` at lines 101-107).

**What's wrong:** `MirofishClient.verify_llm_token()` is awaited from `MirofishRunner.simulate_variants()`
(`orchestrator/engine/mirofish_runner.py:55`) once per campaign iteration. On a 401 it calls
`await self._attempt_token_refresh()`, which calls `_refresh_litellm_api_key()` **directly, not via
`run_in_executor`** — a plain synchronous function that opens/reads/writes `.env` and shells out to
`docker compose up -d litellm` with a 60s timeout, then `await asyncio.sleep(15)`.

**Why it fails:** The orchestrator is a single-process asyncio app (`uvicorn` with the default event loop).
A synchronous, blocking call anywhere in a coroutine freezes the *entire* event loop — every other
in-flight request (SSE progress polling for other users' campaigns, new `POST /api/campaigns`, `/api/health`,
everything) stalls for the full duration of the blocking call. Claude/LiteLLM OAuth tokens expire routinely
(this is exactly why `scripts/refresh-env.sh` and the startup-time refresh exist per CLAUDE.md) — this is not
a rare edge case, it is a scheduled, guaranteed-to-recur event. At 100 concurrent users, many campaigns will be
mid-iteration when the token rolls over; the first one to hit the 401 freezes the process for up to
`60s (subprocess) + 15s (sleep) + probe latency ≈ 75-90s`, during which *every other user's* request hangs.
There is also no lock guarding concurrent invocations — if two campaigns detect the 401 in the same tick,
both will attempt the refresh sequentially (each blocking in turn), doubling the outage window.

**Fix:** Wrap `_refresh_litellm_api_key()` in `await loop.run_in_executor(None, _refresh_litellm_api_key)`;
add an `asyncio.Lock` (or a "refresh in progress" flag) so concurrent 401s await the same in-flight refresh
instead of re-running it.

---

### ERR-02 — Shutdown cancels campaign tasks without draining them, then closes shared clients/queues under them; MiroFish subprocesses are never told to stop
**File:** `orchestrator/api/__init__.py:213-226`

**What's wrong:**
```python
yield
for task_id, task in app.state.running_tasks.items():
    if not task.done():
        task.cancel()
        ...
app.state.running_tasks.clear()
app.state.progress_queues.clear()
await tribe_http.aclose()
await mirofish_http.aclose()
await db.close()
```
`task.cancel()` only *schedules* a `CancelledError` to be raised at the task's next `await` point — it does
not wait for the task to actually unwind. The code immediately proceeds to clear the queues and close the
shared `httpx.AsyncClient`s and the DB connection.

**Why it fails:** A cancelled campaign task may be mid-`await` inside `MirofishClient.run_simulation()` or
`TribeClient.score_text()` when cancellation is delivered; as it unwinds, any `except Exception` cleanup code
that tries to use `self._client` (the just-closed httpx client) or `self._store` (the just-closed DB) raises
a second, unretrieved exception ("Task exception was never retrieved"). More importantly, none of this
reaches the **MiroFish side**: cancelling the orchestrator's asyncio task does not cancel MiroFish's own
OS subprocess running the OASIS simulation (per the system description, MiroFish spawns one subprocess per
simulation). On an orchestrator restart/redeploy — which will happen periodically at 100-user scale for
deploys/config changes — every in-flight MiroFish simulation keeps running as an orphaned subprocess with
no owner, continuing to burn GPU/LLM budget and leaving Neo4j / `state.json` in a partially-written state
that the next orchestrator process has no record of.

**Fix:** `await asyncio.gather(*tasks, return_exceptions=True)` after cancelling, *before* closing shared
resources. Add a MiroFish-side "abort simulation" call (or at minimum a best-effort DELETE/stop call per
in-flight `simulation_id`) during shutdown.

---

### ERR-03 — Campaigns can get stuck in their pre-run status forever, with no way for the user to cancel or recover them
**File:** `orchestrator/engine/campaign_runner.py:474-482` (code before the `try:` at line 497), `orchestrator/api/campaigns.py:383-397` (`_run_background`), `orchestrator/storage/campaign_store.py:75-90` (`cleanup_orphaned_campaigns`, only invoked once at `orchestrator/api/__init__.py:167`).

**What's wrong:** `run_campaign()`'s error handling only starts at its `try:` on line 497. Everything before
it — `get_campaign()`, reading `max_iterations`/`thresholds`, and the initial
`update_campaign_status(campaign_id, "running")` (lines 474-482) — is **not** inside that try block. If any
of these raise (most plausibly a `sqlite3.OperationalError: database is locked` from `aiosqlite` under
concurrent writes from many simultaneous campaigns, or any other store hiccup), the exception propagates
straight up to `_run_background()`'s `except Exception as e:` in `api/campaigns.py:390-392`, which only logs
and pushes an SSE `campaign_error` event — **it never calls `update_campaign_status(..., "failed")`**. The
campaign row is left at whatever status it had (e.g., the initial `"pending"`/created status forever).
Orphan cleanup (`cleanup_orphaned_campaigns`, which force-fails anything stuck in `"running"`) only runs once,
at process startup (`orchestrator/api/__init__.py:167`) — a long-lived production server serving 100
concurrent users will not restart for days, so this campaign is stuck indefinitely. There is also **no
cancel/stop endpoint** in `orchestrator/api/campaigns.py` (only `POST`, `GET` (list/one), `DELETE`) — the user
cannot even manually unstick it short of a direct DB edit.

**Why it fails (concrete):** 100 concurrent users each running campaigns hammer the single SQLite file via
`aiosqlite`. Under write contention, `get_campaign()`/`update_campaign_status()` calls occasionally raise
"database is locked" (SQLite's default busy-timeout is easy to exceed under sustained concurrent writers).
Any campaign whose `run_campaign()` call hits this exact race in its unprotected preamble is now permanently
un-actionable in the UI — indistinguishable from "about to start" — with no operator-visible signal beyond a
transient SSE event that may not even have a connected listener yet.

**Fix:** Wrap the entire body of `run_campaign()` (including the preamble) in the try/except, or add a
narrower try/except around the preamble that also calls `update_campaign_status(..., "failed", error=...)`.
Add a `POST /api/campaigns/{id}/cancel` endpoint. Consider a periodic (not just startup-time) sweep for
`"running"` campaigns whose task is no longer in `app.state.running_tasks`.

---

### ERR-04 — TRIBE per-call timeout x retry-count x batch-multiplier can pin one task for hours, 13x+ the stated campaign SLA
**File:** `orchestrator/clients/tribe_client.py:29` (`SCORE_TIMEOUT = 5400.0`), `:47` (`MAX_RETRIES = 2`), `:231` (`_retry_loop("scoring", _request, SCORE_TIMEOUT)`), `:263` (`batch_timeout = max(SCORE_TIMEOUT, len(texts) * BATCH_PER_TEXT_TIMEOUT)`).

**What's wrong:** Every TRIBE call retries up to `MAX_RETRIES=2` times (3 total attempts), and **each attempt
gets the full timeout again** — `_retry_loop` passes the same `timeout` value to every attempt
(`tribe_client.py:150-168`). For `score_text`, that's up to `3 x 5400s ≈ 4.5 hours` for one text if TRIBE
hangs (rather than crashing outright — e.g. GPU contention, a stuck CUDA kernel, or lock starvation under the
single `_inference_lock` in `tribe_scorer/main.py:400`). For `score_texts_batch` with just 2 variants, the
per-attempt timeout is already `max(5400, 2*5400) = 10800s`, so the worst case is `3 x 10800s ≈ 9 hours` for
one batch call.

**Why it fails:** CLAUDE.md states the hard performance constraint "Full campaign (40 agents, 4 iterations)
must complete in <= 20 minutes." A single hung-but-not-crashed TRIBE request breaches that budget by more
than an order of magnitude while the client faithfully keeps retrying and waiting. At 100 concurrent
campaigns each potentially hitting this path, that is up to 100 asyncio tasks and 100 held httpx connections
parked for hours apiece — consuming orchestrator memory/FD/connection-pool headroom that never gets reclaimed
until the (very long) timeout finally expires, degrading service for every other concurrent user long before
any individual request "fails" in the traditional sense.

**Fix:** Do not repeat the full timeout on each retry attempt for a request that has already consumed most of
a shared serialization lock's time; consider a much shorter per-attempt timeout with a slow-request health
signal from TRIBE (e.g., a request-ID based polling/streaming endpoint) instead of one giant synchronous
call. At minimum, cap the total wall-clock budget across all attempts (e.g. `min(SCORE_TIMEOUT, remaining_campaign_budget)`) rather than compounding it.

---

## HIGH

### ERR-05 — Retry backoff has no jitter in either LLM client, causing synchronized thundering-herd retries under shared rate limits
**File:** `orchestrator/clients/claude_client.py:216-233` (`wait = RATE_LIMIT_BACKOFF * (1.5 ** attempt)` / `wait = BACKOFF_BASE * (2 ** attempt)`), `orchestrator/clients/openai_compat_client.py:210-221` (identical formulas).

**What's wrong:** Both the Anthropic and vLLM/OpenAI-compatible clients back off on a purely deterministic
schedule with no random jitter component (contrast with `mirofish/backend/app/utils/retry.py:59-61`, which
correctly does `current_delay * (0.5 + random.random())`).

**Why it fails:** All 100 concurrent users' orchestrator processes/tasks share the same upstream rate limit
(one Anthropic account, or one vLLM instance). When that limit is hit, every concurrently-retrying call backs
off for *exactly* `30 * 1.5^attempt` seconds (429) or `2 * 2^attempt` seconds (5xx/connection), so all of them
retry at the same instant, regenerating the exact same 429 burst, and repeat in lock-step — this is the
textbook thundering-herd failure mode retries-with-jitter exist to prevent. At high concurrency this can turn
a brief rate-limit blip into a sustained oscillation instead of smoothly spreading retries out.

**Fix:** Multiply each computed `wait` by a jitter factor (e.g. `wait * (0.5 + random.random())`), matching
the pattern already implemented correctly in `mirofish/backend/app/utils/retry.py`.

---

### ERR-06 — `DELETE /api/campaigns/{id}` never checks/cancels the campaign's running background task
**File:** `orchestrator/api/campaigns.py:420-460` (`delete_campaign`) vs. `:383-397` (`app.state.running_tasks[campaign.id] = task`).

**What's wrong:** `delete_campaign()` deletes the campaign row (cascading iterations/analyses) and
best-effort-deletes the uploaded media file, but never looks at `request.app.state.running_tasks`. If the
campaign's `run_campaign()` background task is still executing, it is left running.

**Why it fails:** A user deletes a campaign that appears "stuck" (e.g. hit by ERR-03, or just slow). The
background task keeps calling `self._store.save_iteration(campaign_id=...)`,
`update_campaign_status(campaign_id, ...)`, etc. against a `campaign_id` whose row no longer exists —
depending on the schema's FK enforcement this either silently no-ops/orphans rows or raises further
unhandled `sqlite3.IntegrityError`s deep inside `run_campaign()`'s try/except (which will then try to
`update_campaign_status` on a nonexistent campaign again). Meanwhile the task keeps consuming TRIBE/MiroFish/
LLM resources for a campaign the user believes is gone — wasted spend and console noise at best, corrupted
DB state at worst.

**Fix:** In `delete_campaign()`, look up `app.state.running_tasks.get(campaign_id)` and `task.cancel()` (and
ideally await it) before/while deleting the DB row.

---

### ERR-07 — One poison variant in a TRIBE batch call discards already-computed results and forces three full-timeout retries before the sequential fallback engages
**File:** `tribe_scorer/main.py:525-580` (`_run_batch_score`) and `orchestrator/engine/tribe_scorer.py:76-104` (batch-then-fallback logic).

**What's wrong:** `_run_batch_score` loops over all texts in a single request and appends
`(raw_activations, elapsed_ms, is_pseudo)` per text (line 559) — but if any text raises inside the loop
(lines 541-554), the `HTTPException` propagates immediately, discarding whatever was already computed for
earlier texts in the same batch, and failing the whole `/api/score/batch` HTTP call. `TribeClient._retry_loop`
sees this as a `>=400` client error (`tribe_client.py:170-176`) and returns `None` for the whole batch without
retrying the HTTP call itself — but `TribeScoringPipeline.score_variants` (`orchestrator/engine/tribe_scorer.py:100-104`)
only falls back to per-text sequential scoring *after* the batch attempt is fully exhausted, and the batch
attempt itself was already subject to TRIBE_CLIENT's retry-on-timeout/connection-error path (ERR-04) before
reaching the surface-level 4xx. Net effect: one bad variant (e.g. one that reliably OOMs) forces the whole
batch to be paid for in full before the orchestrator falls back to scoring the *other, perfectly fine*
variant(s) one at a time — throwing away the server-side work already done on them.

**Fix:** In `_run_batch_score`, catch per-text exceptions individually and continue the loop (returning a
pseudo-score or `None`-marker for the failed text, consistent with the audio/video pseudo-score pattern
already used elsewhere in the same file), so one bad text doesn't sink the whole batch response.

---

### ERR-08 — `torch.cuda.OutOfMemoryError` (a `RuntimeError` subclass) is misclassified as a non-retryable 422 client error, and the CUDA allocator is never reset
**File:** `tribe_scorer/main.py:503-513` (`_run_single_score`), `:541-554` (`_run_batch_score`); `orchestrator/clients/tribe_client.py:170-176` (4xx short-circuits `_retry_loop` with no retry).

**What's wrong:** Both inference entry points catch `(ValueError, RuntimeError)` and turn it into an HTTP 422
"Inference failed" — but PyTorch's `torch.cuda.OutOfMemoryError` **is** a `RuntimeError` subclass, so a
transient VRAM-exhaustion event (e.g. temporary fragmentation, another process briefly holding VRAM) is
reported identically to "your input text is malformed." `TribeClient._retry_loop` treats any `>=400` response
as terminal and returns `None` immediately (no retry) — even though an OOM is often exactly the kind of
transient condition a short backoff-and-retry (with `torch.cuda.empty_cache()` in between) would resolve.
Neither the 422 path nor the health check calls `torch.cuda.empty_cache()`, so a fragmented allocator state
persists into the next request.

**Why it fails:** Under the target scale, TRIBE's single GPU is under sustained pressure from many queued
scoring requests; transient near-OOM conditions become likely, not rare. Each one permanently gives up on
that variant (no retry) and leaves the allocator no better off for the next request, compounding over time
into a service that silently degrades (more and more requests OOM) with no automatic recovery path and no
signal distinguishing "your content was unscoreable" from "the GPU is out of memory right now."

**Fix:** Catch `torch.cuda.OutOfMemoryError` explicitly *before* the generic `RuntimeError` branch, call
`torch.cuda.empty_cache()`, and surface a `503` (retryable) instead of `422` (terminal) so `TribeClient`'s
retry-on-5xx path actually engages.

---

### ERR-09 — TRIBE's `/api/health` CUDA check never exercises real model memory usage; health can report "ok" while actual inference is failing
**File:** `tribe_scorer/main.py:403-417` (`_check_cuda_health`), `:850-915` (`/api/health` endpoint).

**What's wrong:** `_check_cuda_health()` allocates a single `torch.zeros(1, dtype=torch.float32, device="cuda")`
and calls `torch.cuda.synchronize()` — this only proves the CUDA *context* is alive, not that the ~6-8GB
LLaMA-3.2-3B working set the real inference path needs is actually available or that a forward pass succeeds.

**Why it fails:** The orchestrator's `CampaignRunner.check_system_availability()`
(`orchestrator/engine/campaign_runner.py:79-109`) trusts this health check as its sole pre-flight signal
before deciding to send real scoring work for an entire campaign iteration. Under the target load (many
concurrent scoring requests fighting for a single GPU's VRAM), the GPU can be in a state where a 4-byte
allocation trivially succeeds but the actual model's forward pass OOMs — health reports `"ok"`/`cuda_healthy: true`,
the orchestrator proceeds, and the real scoring call then fails or silently falls back to pseudo-scores
(`is_pseudo_score: true`), which the user may not notice unless they inspect `data_completeness` in the
report. This is exactly the "does /health lie?" failure mode.

**Fix:** Periodically (not on every request, to avoid extra GPU churn) exercise a minimal real forward pass
through the loaded model as part of health, or at minimum track a rolling "last N inference outcomes" signal
and factor recent OOM/pseudo-score rates into the reported health status.

---

### ERR-10 — No circuit breaker/cooldown: a down TRIBE or MiroFish is re-probed and re-hammered on every single iteration of every campaign
**File:** `orchestrator/engine/campaign_runner.py:79-109` (`check_system_availability`), called at the top of every `run_single_iteration` (`campaign_runner.py:171`).

**What's wrong:** There is no shared, cross-campaign state that remembers "TRIBE/MiroFish has failed N times
recently, back off for a cooldown period." Every iteration of every campaign independently calls
`health_check()` fresh, and if it happens to pass (even a flapping/borderline service), immediately proceeds
to send full-cost scoring/simulation calls (subject to ERR-04's multi-hour worst case).

**Why it fails:** If TRIBE goes down (crash, OOM lockup, restart needed) while 100 campaigns are mid-flight,
all 100 keep re-probing it every iteration with no coordination, and any flaky "half-up" period causes many of
them to simultaneously re-attempt expensive scoring calls that are likely to fail again — wasted GPU time,
wasted wall-clock, and noisy logs, right when the system is already degraded and least able to absorb it.

**Fix:** Add a lightweight shared circuit-breaker (in `app.state`, keyed per downstream service) recording
recent failure counts/timestamps; when a service has failed repeatedly within a short window, skip the
per-iteration health probe and short-circuit straight to "unavailable" for a cooldown period.

---

### ERR-11 — MiroFish's ontology generator has zero retry/exception handling, unlike every other LLM-calling step in the pipeline
**File:** `mirofish/backend/app/services/ontology_generator.py:167-206` (`OntologyGenerator.generate`) vs. `mirofish/backend/app/services/simulation_config_generator.py:433-480` (`_call_llm_with_retry`, 3 attempts) and `mirofish/backend/app/services/oasis_profile_generator.py:468-525` (3-attempt retry with exponential-ish backoff).

**What's wrong:** `OntologyGenerator.generate()` calls `self.llm_client.chat_json(...)` (`ontology_generator.py:197-201`)
directly with no try/except and no retry loop at all. `LLMClient.chat_json` (`mirofish/backend/app/utils/llm_client.py:88-120`)
raises `ValueError` on any JSON parse failure and lets any underlying `openai` SDK exception propagate
unmodified. Contrast this with `simulation_config_generator.py` and `oasis_profile_generator.py`, both of
which wrap their LLM calls in a 3-attempt retry with JSON-repair fallback logic.

**Why it fails:** Ontology generation is **Step 1** of the entire MiroFish pipeline
(`mirofish/backend/app/api/graph.py`'s `/api/graph/ontology/generate` route, called from
`MirofishClient._generate_ontology` at `orchestrator/clients/mirofish_client.py:353-386`). A single transient
network blip, a momentary 429 from the shared LLM backend, or one malformed-JSON generation — none of which
are unusual under concurrent load from 100 users' worth of simulations hitting the same LLM endpoint — kills
the *entire* variant's MiroFish simulation instantly (the Flask route's broad `except Exception` at
`graph.py:257-262` turns it into an HTTP 500, which `MirofishClient._generate_ontology`'s own broad except
turns into `None`, which `MirofishRunner` treats as "simulation failed for this variant"). Every downstream
step tolerates exactly this class of failure via retry; the very first, most foundational step does not.

**Fix:** Wrap `OntologyGenerator.generate()`'s LLM call in the same retry pattern already used two files over
in `simulation_config_generator.py` (or better, route all three generators through the already-correct,
currently-unused `mirofish/backend/app/utils/retry.py:retry_with_backoff`).

---

### ERR-12 — Shared httpx client's default timeout (300s) is inconsistent with, and eighteen times shorter than, TRIBE's documented SCORE_TIMEOUT contract (5400s)
**File:** `orchestrator/api/__init__.py:160-161` (`httpx.AsyncClient(base_url=settings.tribe_scorer_url, timeout=300.0)`) vs. `orchestrator/clients/tribe_client.py:29` (`SCORE_TIMEOUT = 5400.0`).

**What's wrong:** Every current call site in `TribeClient` explicitly overrides the per-request `timeout=`
argument, so this 300s client-level default is currently latent/unused — but it exists as a silent trap: the
"canonical" scoring timeout is documented in one file (`tribe_client.py`) as 5400s while the shared HTTP
client used to reach TRIBE is configured with a completely different, much shorter default in another file.

**Why it fails:** Any future call added against `app.state.tribe_http` (a debug endpoint, a new score
variant, a quick health-adjacent probe) that forgets to pass an explicit `timeout=` will silently inherit
300s and get killed mid-inference on anything that takes TRIBE's normal 30-90s-per-text (or longer, chunked)
processing time plus queueing behind the single `_inference_lock` under concurrent load — a confusing,
hard-to-diagnose failure that looks like "TRIBE hung" when it's actually "the client gave up too early."

**Fix:** Either raise the client-level default to match `SCORE_TIMEOUT` (so an omitted override fails safe,
i.e., too patient rather than too eager to give up), or centralize the timeout constant so both files read
from one source of truth.

---

## MEDIUM

### ERR-13 — Failed ontology generation leaks orphaned project directories/files on disk
**File:** `mirofish/backend/app/api/graph.py` — generic `except Exception` around ontology generation (surrounding the route body up to line 257) does not call `ProjectManager.delete_project`, unlike the explicit cleanup at line 211 for the "no documents processed" branch.

**What's wrong:** `ProjectManager.create_project()` and the subsequent file-save/text-extraction steps happen
*before* `generator.generate()` is called. If `generate()` raises (see ERR-11 — this is disproportionately
likely given zero retry there), the route's outer `except Exception` returns a 500 but never deletes the
project directory that was already created and populated with uploaded file bytes.

**Why it fails:** At 100 concurrent users retrying failed campaigns (a natural user reaction to a failure),
each failed attempt leaves a permanent, never-garbage-collected directory + files on the MiroFish host's
disk. There is no TTL/GC job evident in scope. Over time this is unbounded disk growth purely from transient
failures that have nothing to do with the content itself.

**Fix:** Add a `finally`/`except`-path cleanup that deletes the just-created project on any ontology
generation failure, mirroring the existing "no documents" cleanup.

---

### ERR-14 — A single transient variant-generation or analysis LLM failure aborts the entire iteration/campaign; no iteration-level retry exists
**File:** `orchestrator/engine/campaign_runner.py:169-446` (single top-level `try/except` wrapping variant generation, TRIBE scoring, MiroFish, composite scoring, and Opus analysis together); `orchestrator/engine/variant_generator.py` (single LLM call producing all N variants).

**What's wrong:** TRIBE and MiroFish calls have real per-variant graceful degradation (return `None`, campaign
continues). Variant generation and cross-system analysis do not: each is a single Claude/vLLM call (with only
the built-in 2-attempt JSON-repair retry inside `_call_json`), and if it ultimately raises, the *entire*
`run_single_iteration()` call fails via the catch-all at line 442, which marks the whole campaign `"failed"`
if this is iteration 1 (nothing yet persisted to fall back to).

**Why it fails:** A single JSON-parse failure that survives both of `_call_json`'s attempts (plausible under
load — LLM providers are more likely to truncate/rate-limit under concurrent traffic from 100 users), or a
single exhausted-retries HTTP failure from the LLM client, takes down an otherwise entirely healthy
TRIBE+MiroFish pipeline for that campaign. There is no iteration-level "retry this iteration once more" logic
above the intra-call retry.

**Fix:** Wrap the variant-generation and analysis calls in their own narrower try/except with a small
iteration-level retry (e.g. 1-2 extra attempts with backoff) before letting the failure propagate and fail
the whole campaign.

---

### ERR-15 — MiroFish's Flask backend runs on Werkzeug's threaded development server, not a production WSGI server
**File:** `mirofish/backend/run.py:45` (`app.run(host=host, port=port, debug=debug, threaded=True)`).

**What's wrong:** Flask/Werkzeug explicitly document their built-in `run()` server as unsuitable for
production — it lacks the worker-process isolation, connection-queue backpressure, and crash containment of a
real WSGI server (gunicorn/uwsgi behind a reverse proxy).

**Why it fails:** The system design already routes up to ~100 concurrent, long-running (many-minute)
simulation request flows through this single process. A single unhandled exception or resource exhaustion
condition in one request's thread is more likely to destabilize the whole process than it would be under a
proper worker-pool model, and there is no external supervisor evident in scope to detect/restart it if it
does, leaving every in-flight campaign's MiroFish calls hanging until a human notices.

**Fix:** Run behind gunicorn/uwsgi (or equivalent) with multiple workers and a supervisor/health-checked
restart policy, matching the resilience level the rest of the stack (uvicorn for the orchestrator) already has.

---

### ERR-16 — claude_client.py's 401-refresh handling silently consumes one of `MAX_RETRIES`'s slots, contradicting its own comment
**File:** `orchestrator/clients/claude_client.py:205-212`.

**What's wrong:** The comment at line 212 says `continue  # Don't count this as a backoff attempt`, but the
`continue` re-enters the `for attempt in range(MAX_RETRIES + 1)` loop at its next value — there is no separate
counter for the credential-refresh retry, so it does consume one of the loop's iterations.

**Why it fails:** After a 401-triggered credential refresh, only `MAX_RETRIES - 1` (effectively) genuine
retry attempts remain for subsequent transient errors on the same call, one fewer than intended/documented.
Low impact in isolation, but under a burst of concurrent 401s right after an OAuth rotation (100 users' worth
of in-flight Claude calls all discovering the stale token around the same time), every one of them loses this
same retry budget simultaneously.

**Fix:** Track the credential-refresh retry with its own counter/flag so it doesn't consume an iteration of
the main retry loop, matching the documented intent.

---

## LOW

### ERR-17 — A correct, jittered retry/backoff utility exists but is unused by the services that need it most
**File:** `mirofish/backend/app/utils/retry.py` (whole file — `retry_with_backoff`, `retry_with_backoff_async`, `RetryableAPIClient` all implement proper exponential backoff + jitter) — only referenced from `mirofish/backend/app/storage/neo4j_storage.py`; `ontology_generator.py`, `simulation_config_generator.py`, and `oasis_profile_generator.py` all hand-roll their own (absent, or jitter-less linear) retry logic instead.

**Fix:** Route all three generators' LLM calls through `retry_with_backoff`/`RetryableAPIClient`; this alone
would resolve ERR-05 (mirofish side) and ERR-11 with no new code.

### ERR-18 — MirofishClient creates a brand-new, unpooled `httpx.AsyncClient()` on every health/token-verify call
**File:** `orchestrator/clients/mirofish_client.py:101` (`get_neo4j_stats`), `:147` (`verify_llm_token`), `:183` (`_attempt_token_refresh`) — each opens `async with httpx.AsyncClient() as check_client:` instead of reusing the shared, pooled client already passed into the constructor.

**Why it matters:** At the call frequency of "once per iteration per campaign," across 100 concurrent
campaigns this repeatedly pays full TCP/TLS-negotiation cost instead of reusing a warm connection pool —
wasteful, though not incorrect, and it compounds the blocking behavior in ERR-01 since none of these ephemeral
clients benefit from any connection warm-up either.

**Fix:** Accept/reuse a shared `httpx.AsyncClient` for these calls the same way the constructor already does
for the main simulation workflow.

---

## What breaks first at 100 users x 100 agents

**The orchestrator itself freezes for every user, repeatedly, the first time a Claude/LiteLLM OAuth token
expires while campaigns are in flight (ERR-01).** `MirofishClient._attempt_token_refresh()` calls
`_refresh_litellm_api_key()` — a synchronous function that does blocking file I/O and a `subprocess.run(...,
timeout=60)` shelling out to `docker compose up -d litellm` — directly inside an `async def`, with no
`run_in_executor` and no lock against concurrent callers. Because the orchestrator is a single-process,
single-event-loop asyncio server, this one blocking call stalls *every* concurrent user's SSE progress stream,
every new campaign creation, and `/api/health` itself, for up to ~75-90 seconds per occurrence — not just the
campaign whose token happened to expire. Unlike the GPU/serialization bottlenecks elsewhere in this system
(which are known, load-proportional, and at least fail somewhat gracefully via long queues), this failure mode
requires no unusual load at all: it is triggered purely by the passage of time on a routinely-expiring OAuth
token, which is guaranteed to happen within hours of continuous operation, and it produces a full,
whole-system stall visible to all 100 concurrent users simultaneously — the closest thing in this codebase to
a scheduled, self-inflicted denial of service. It will very likely be the first "is the whole app down?"
report an operator receives once real concurrent traffic starts.
