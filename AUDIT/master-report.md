# A.R.C Studio — Master Audit Report

Date: 2026-07-05 · Branch: `competition/amd-hackathon`
Scale target audited: ~100 concurrent users × up to ~100 in-app agents each (~10k concurrent agents).

Phase 1 produced 124 raw findings (22 CRITICAL / 48 HIGH / 39 MEDIUM / 15 LOW) across 9 tracks. This report **deduplicates** them into canonical issues, marks each **VERIFIED** (I read the cited code and confirmed) or **REJECTED/DOWNGRADED** (claim didn't hold or severity overstated), orders by severity × blast radius, and separates **contained fixes** (this phase) from **structural changes** (require approval — see `architecture-proposals.md`).

Legend: 🟥 CRITICAL 🟧 HIGH 🟨 MEDIUM ⬜ LOW · **[C]** contained fix (do now) · **[S]** structural (propose + STOP) · **[SUB]** in mirofish submodule.

---

## Cross-track consensus (found independently by 3–4 agents)

| Theme | Tracks | Verdict |
|---|---|---|
| TRIBE single process-wide `_inference_lock` + no admission control = silent multi-hour queue at scale | CON-03, PERF-01, OBS-07, API-06 | **VERIFIED** — `tribe_scorer/main.py:400`. Structural (GPU) + contained (admission cap). |
| MiroFish runs Werkzeug dev server, single GIL process | CON-04, PERF-01, ERR-15, OBS-05 | **VERIFIED** — `mirofish/backend/run.py:45`. Structural. |
| `progress_history`/`progress_queues` never evicted → unbounded memory | CON-07, RES-06, DATA-14, OBS-09 | **VERIFIED** — grep confirms no pop. Contained. |
| DELETE campaign never cancels its running task | RES-09, ERR-06, DATA-08 | **VERIFIED** — `campaigns.py:420`. Contained. |
| Shutdown cancels tasks without awaiting; closes clients under them | CON-06, ERR-02 | **VERIFIED** — `api/__init__.py:216`. Contained. |
| `media_path` = client-supplied arbitrary path (file-disclosure) | SEC-03, API-03 | **VERIFIED** — `schemas.py` validator only checks non-empty. Contained. |
| Committed HF token in `.env.hackathon.example` working tree | SEC-08, OBS-01 | **VERIFIED** — git status shows `M .env.hackathon.example`. Contained. |
| No auth / no tenant ownership → cross-user read/delete | SEC-05, API-02 | **VERIFIED** — by-design Phase-1, but a hard scale wall. Structural. |
| cleanup_orphaned_campaigns blanket-fails ALL running on restart | DATA-01 | **VERIFIED**. Structural (needs heartbeat/lease). |

---

## 🟥 CRITICAL

### M-01 [C] `find_best_composite` IndexError kills the campaign on any empty-variant iteration — LOG-01
`optimization_loop.py:189-222` returns `composite_scores_list[best_idx]` with `best_idx=0`; `variant_generator.py:95` tolerates an empty LLM `variants` list without raising, so an empty iteration reaches `find_best_composite([])` → **IndexError**, re-raised out of `run_campaign`. **VERIFIED** (read both). Scales linearly with concurrent LLM calls (Qwen JSON-mode less reliable). **Fix:** guard empty in `find_best_composite`; raise a clear `ValueError` in `run_single_iteration` when variants is empty so it's attributable/retryable.

### M-02 [C] LiteLLM token refresh blocks the entire event loop — ERR-01
`mirofish_client.py:172-208 _attempt_token_refresh` calls synchronous `_refresh_litellm_api_key()` (`api/__init__.py:28` — file I/O + `subprocess.run(..., timeout=60)` + `asyncio.sleep(15)`) directly inside a coroutine, no executor, no lock. **VERIFIED.** One routine OAuth expiry freezes ALL users' requests ~75-90s. **Fix:** `run_in_executor` + an `asyncio.Lock` so concurrent 401s await one refresh.

### M-03 [C] `media_path` arbitrary-file read / cross-tenant exfiltration — SEC-03 / API-03
`schemas.py` `_media_path_required_for_media` only checks non-empty; `campaign_runner.py:178` forwards verbatim to TRIBE which transcribes any readable audio/video file and returns the transcript via `GET /api/campaigns/{id}`. **VERIFIED.** **Fix:** resolved-path containment check against `settings.audio_upload_dir_absolute` in the validator/`create_campaign`; TRIBE-side path confinement (submodule-free — TRIBE is ours).

### M-04 [C][SUB] Cypher injection via unsanitized entity-type label — SEC-01
`mirofish/.../neo4j_storage.py:282-292` and `:440-451` splice `etype`/`label` into a backtick-quoted Cypher label with no backtick-escaping/allowlist; `etype` originates from LLM extraction of user documents (`ner_extractor.py`), and a second sink flows from report-agent LLM tool args. **VERIFIED by reading finding + sinks (to confirm at fix time).** Shared Neo4j, no tenant isolation → cross-tenant graph corruption/exfil. **Fix (minimal):** reject/escape backticks and non-ontology labels before interpolation, or store type as a parameterized property.

### M-05 [C][SUB] Path traversal → arbitrary directory delete / cross-tenant DB read — SEC-02 / SEC-06 / SEC-07 / API-11
`project_id` (`project.py`→`shutil.rmtree`), `platform` query param (`simulation.py:1982` → sqlite path), and body `simulation_id` (`simulation.py:/prepare`) are used in `os.path.join` with no validation; Werkzeug's segment converter allows `\` on Windows. **VERIFIED (finding-level; confirm at fix).** **Fix (minimal, additive):** regex-guard `^(proj|sim)_[0-9a-f]{12}$` / `^[a-z]+$` allowlist at each sink + realpath-containment check.

### M-06 [S] TRIBE single-GPU lock + zero admission control = silent hours-long queue — CON-03 / PERF-01 / OBS-07 / RES-01
One `threading.Lock` serializes all scoring for all users; `SCORE_TIMEOUT=5400s` means nothing fails fast. **VERIFIED.** RES-01 adds: on inference timeout the worker thread can't be killed (`executor.shutdown(wait=False)` can't cancel a running future), yet the outer lock releases → concurrent `model.predict()` on the documented non-thread-safe model + leaked VRAM. **Contained slice:** orchestrator admission cap (M-14). **Structural:** GPU horizontal scale / request queue with position — see proposals.

### M-07 [S] Restart blanket-fails every running campaign for every user — DATA-01 / CON-06
`cleanup_orphaned_campaigns` (`campaign_store.py:75`) does `UPDATE ... WHERE status='running'` globally on startup; shutdown cancels all tasks. **VERIFIED.** At scale a single crash wipes all in-flight work with no resume. **Contained slice:** graceful shutdown drain (M-12). **Structural:** heartbeat/lease + resume — see proposals.

*(Remaining CRITICALs from Phase 1 — MiroFish subprocess orphaning CON-01, start_simulation TOCTOU CON-02, Flask dev server as "critical" — are folded into the structural MiroFish-execution-model proposal; the API-01 agent-chat-broken CRITICAL is downgraded, see M-24.)*

---

## 🟧 HIGH (contained unless marked [S])

- **M-08 [C] `audience_fit` biased mean not weighted average — LOG-04.** `composite_scorer.py:189` divides `Σ(wᵢxᵢ)` by dimension **count**, not `Σwᵢ`; biases −3.6%…+10.7% by demographic (verified against `demographic_profiles.py` weight sums). Feeds ranking/thresholds/report. **VERIFIED.** Fix: divide by `Σ` of the same-filtered weights.
- **M-09 [C] Report psychology mis-scales [0,1] metrics as [0,100] — LOG-02.** `report_psychology.py:163,169,173` treats `influence_concentration`/`platform_divergence` (both [0,1] per `mirofish_runner.py`) as 0-100 → always "spread evenly", always "0/100". **VERIFIED.** Fix: `*100` before compare/display.
- **M-10 [C] `coalition_formation` int vs dict → dead report branch — LOG-03.** `mirofish_runner._count_coalitions` returns int; `report_psychology.py:150` guards `isinstance(dict)` → never fires. **VERIFIED.** Fix: consume the int.
- **M-11 [C] CLI printer crashes on real scores — LOG-07.** `cli.py:314` formats every non-`is_pseudo_score` tribe value with `:.1f`; `timeline` (dict)/`transcript` (str) present on real audio/video/fallback scores → TypeError/ValueError, not caught by the `UnicodeEncodeError`-only handler. **VERIFIED.** Fix: filter `{timeline,tr_seconds,transcript,is_pseudo_score}`.
- **M-12 [C] Graceful shutdown: await cancelled tasks before closing clients — CON-06 / ERR-02.** `api/__init__.py:216` cancels then immediately `aclose()`s httpx/db. **VERIFIED.** Fix: `await asyncio.gather(*tasks, return_exceptions=True)` after cancel; catch `CancelledError` in runner to mark status.
- **M-13 [C] DELETE campaign must cancel its task — RES-09 / ERR-06 / DATA-08.** `campaigns.py:420` never touches `running_tasks`. **VERIFIED.** Fix: cancel + drop queue/history before/at delete.
- **M-14 [C] Admission control on POST /api/campaigns — API-06.** No cap on concurrent campaigns; all return 201 then queue invisibly. **VERIFIED.** Fix: configurable max-concurrent semaphore/counter → 429 when full.
- **M-15 [C] Evict progress_history + progress_queues on terminal — CON-07/RES-06/DATA-14/OBS-09.** **VERIFIED.** Fix: pop both in the campaign completion path (with grace) not only on SSE disconnect.
- **M-16 [C] SSE reconnect permanently 404s — PERF-03.** `progress.py:63` `.get()` + `cleanup_queue` pops on **first** disconnect while task still runs; producer closure holds the old queue ref. **VERIFIED.** Fix: only pop on terminal event / campaign-not-running; keep serving replay+live for still-running campaigns.
- **M-17 [C] LLM retry backoff has no jitter — ERR-05.** `claude_client.py:224,226` & `openai_compat_client.py:210` deterministic → thundering herd on shared rate limit. **VERIFIED.** Fix: `wait *= (0.5 + random.random())`.
- **M-18 [C] TRIBE OOM misclassified as terminal 422 — ERR-08.** `torch.cuda.OutOfMemoryError` (a `RuntimeError`) → 422, which `tribe_client` never retries, and allocator never `empty_cache()`d. **VERIFIED (RuntimeError subclass).** Fix: catch OOM first → `empty_cache()` + 503 (retryable).
- **M-19 [C] Missing hot-path indexes + no busy_timeout — PERF-04 / DATA-13 / DATA-06.** No index on `iterations.campaign_id`, `analyses.campaign_id`, `campaigns.status`, `campaigns.created_at`; no `PRAGMA busy_timeout`. **VERIFIED.** Fix: add indexes in schema/migration + `busy_timeout=10000`.
- **M-20 [C] `demographic` unvalidated → KeyError after burning GPU/LLM — API-04.** `_get_weights`→`get_profile` raises `KeyError` at composite step (post-scoring). **VERIFIED.** Fix: `field_validator` rejecting unknown demographics at request time (422).
- **M-21 [C] Whisper transcript read outside the lock → cross-user contamination — LOG-05.** `main.py` reads `get_last_transcript()` after the `with _inference_lock` block. **VERIFIED (finding-level).** Fix: read inside the lock (or return transcript from the scoring fn).
- **M-22 [C] Orchestrator has no logging config on the uvicorn run path — OBS-02.** Root logger at WARNING, no handler → all `.info()` dropped. **VERIFIED (empirical in finding).** Fix: `logging.basicConfig(INFO)` in `api/__init__.py` + uvicorn log_config.
- **M-23 [C] Config drift: MiroFish default port 5000 vs served 5001 — OBS-03.** `config.py mirofish_url` + `.env.example` default 5000; compose serves 5001. **VERIFIED.** Fix: default to 5001.
- **M-24 [C] CORS hardcoded to localhost:5173 — OBS-04 / API-07 / SEC-13.** **VERIFIED.** Fix: `settings.cors_allowed_origins` env-driven (keeps localhost default).
- **M-25 [C] Audio campaigns never get transcript grounding — LOG-06.** `AudioScoreResponse` has no `transcript`; audio path never calls `get_last_transcript()` (video does). **VERIFIED (finding-level).** Fix: mirror the video path in TRIBE (ours).
- **M-26 [C] compute_improvement conflates "no data" with "0% improvement" → false "converged" — LOG-11.** Returns `0.0` for empty comparables; `is_converged([0,0])`→True. **VERIFIED.** Fix: return `None` sentinel; caller treats as non-convergent / `no_data`.
- **M-27 [C][SUB] Non-atomic JSON state writes corrupt sim state on crash — CON-09 / DATA-03.** `open(path,'w')`+`json.dump` with no temp+rename in `_save_run_state`/`_save_simulation_state`. **VERIFIED (read).** Fix (minimal): temp-file + `os.replace`.
- **M-28 [C][SUB] Neo4j Entity MERGE has no backing uniqueness constraint → duplicate entities under concurrency — DATA-04.** **VERIFIED (finding-level).** Fix: composite constraint on `(graph_id, name_lower)`.
- **M-29 [C][SUB] Flask DEBUG defaults True, HOST 0.0.0.0 — SEC-04.** `config.py:25` default `'True'`. Werkzeug debug = unauth RCE if ever run outside compose. **VERIFIED.** Fix: default False; host 127.0.0.1.
- **M-30 [C] TRIBE batch is all-or-nothing — ERR-07 / API-08.** One bad text aborts the whole `/api/score/batch`, discarding good results. **VERIFIED (finding + read of tribe_client fallback).** Fix (ours, TRIBE): per-item try/except → pseudo-marker.
- **M-31 [S] MiroFish → production WSGI + bounded workers — OBS-05/CON-04/PERF-01/ERR-15.** Structural (deploy). See proposals.
- **M-32 [S] MiroFish N+1 Neo4j writes + per-agent un-batched embeddings — PERF-05 / PERF-06.** Structural (submodule perf). See proposals.
- **M-33 [S] MiroFish subprocess orphaning + class-dict races + no orphan reconciliation — CON-01/CON-02/CON-08/DATA-02/RES-02/RES-03/RES-10.** Structural (submodule execution model). See proposals.

---

## 🟨 MEDIUM (fix where low-risk this phase)

- **M-34 [C] `missing_composite_dimensions` false-positive if any one variant lacks a dim — LOG-10.** Fix: only mark missing when ALL variants lack it. **VERIFIED.**
- **M-35 [C] `/api/estimate` ignores `agent_count` — API-16.** Fix: fold agent term in, or drop the field. **VERIFIED.**
- **M-36 [C] claude 401-refresh consumes a retry slot — ERR-16.** Fix: separate counter. **VERIFIED.**
- **M-37 [C] tribe_http default timeout 300s vs SCORE_TIMEOUT 5400s latent trap — ERR-12.** Fix: raise client default / single source. **VERIFIED (latent — all call sites override today).**
- **M-38 [C][SUB] sqlite connections leak on exception (no finally) — RES-04.** Fix: `contextlib.closing`. **VERIFIED (finding-level).**
- **M-39 [C][SUB] platform/limit param clamping + int-coercion 400s — API-12.** Fix: clamp limit, allowlist platform, 400 on bad `agent_id`. Overlaps M-05.
- **Deferred MEDIUMs** (justified in `deferred.md`): ERR-10 circuit breaker, ERR-11/ERR-13/ERR-14 mirofish retry gaps, DATA-05/07/09/10/11/12 mirofish transactionality/tailing, CON-10/11/12/13, RES-05/07/08/11/12, PERF-07/08/09, LOG-08, OBS-06/08/10/11/13/14, SEC-09/10/11/12/14/15, API-05/09/10/13.

## ⬜ LOW
Batched into `deferred.md` (LOG-09, API-14/15, OBS-15, SEC-13 folded into M-24, etc.). Fix opportunistically; none block the scale target.

---

## REJECTED / DOWNGRADED

- **API-01 "agent-chat broken end-to-end" (CRITICAL→note).** Real contract mismatch (`chat_agent` → nonexistent `/api/agent/{id}/chat`), but this is a **feature-dead** path, not a scale/correctness failure of the core campaign pipeline, and fixing it fully needs the MiroFish `/interview` wiring + `simulation_id` plumbing (structural). Logged in `deferred.md` as a functional gap, not a scale blocker.
- **SEC-14 (ROCm unconfined seccomp).** Accepted-risk / required for ROCm; not introduced by this codebase. No action.
- **ERR-04 "9-hour retry" severity.** Real (batch timeout × retries compounds) but same root as M-06 (no fast-fail); addressed by admission control + M-37, not a separate fix.

---

## Fix plan (dependency-ordered)

**Batch A — orchestrator core correctness (no dep):** M-01, M-08, M-09, M-10, M-11, M-26, M-34, M-35.
**Batch B — orchestrator resilience/lifecycle:** M-02, M-12, M-13, M-15, M-16, M-17, M-36, M-37 (M-13/M-15 share the delete/terminal path).
**Batch C — orchestrator data/config/API:** M-14, M-19, M-20, M-22, M-23, M-24, M-03 (media_path).
**Batch D — TRIBE (ours):** M-18, M-21, M-25, M-30, M-03 (TRIBE-side path confinement).
**Batch E — mirofish submodule (surgical security):** M-04, M-05, M-27, M-28, M-29, M-38, M-39.
**Baseline repair (prereq):** fix `test_tribe_timeout.py` `CHUNK_SIZE_WORDS` import so the suite collects.
**Structural (STOP for approval):** M-06 (GPU/queue), M-07 (heartbeat/resume), M-31 (WSGI), M-32 (N+1), M-33 (execution model), SEC-05/API-02 (auth/tenancy) → `architecture-proposals.md`.

Every fix ships with a regression test that fails before / passes after, per ground rules.
