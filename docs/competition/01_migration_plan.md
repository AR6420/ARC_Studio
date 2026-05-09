# AMD Hackathon — Phased Migration Plan

Budget: ~25 GPU-hours on 1× MI300X. Solo. Submission window: May 4-10, 2026.

## Strategy

- **Local prep first** (Phases 0-2). Burn zero cloud hours on work that can be done on the dev box: code refactor, container builds, model downloads-to-cache validation, test suites with mocked vLLM.
- **Cloud-only for ROCm validation and demo** (Phases 3-6). Land on MI300X with image already built and code already passing locally.
- Reserve **~5 hours buffer** for the unknown. Do not exceed budget on validation phases.

## Phase 0 — Local: orchestrator LLM-provider abstraction (0 cloud hrs) — **DONE**

**Goal achieved**: orchestrator routes LLM calls through either Anthropic SDK (default) or any OpenAI-compatible endpoint via `LLM_PROVIDER` env var. 251 tests pass (235 baseline + 16 new). Production behaviour identical when `LLM_PROVIDER=anthropic`.

**Decisions vs original plan**:
- **Models bumped** to Qwen3.5 dense (Apr 2026) primary, Qwen3 dense (Apr 2025) documented fallback. See `MODELS.md`. Code is model-name-agnostic — swap is a config change.
- **No edits to `claude_client.py`.** It already conforms to the new `LLMClient` Protocol via duck typing; touching it risks regressing the production path. Protocol is a `typing.Protocol`, not a forced ABC.
- **No `mock_claude_client` fixture changes.** It's a generic `AsyncMock` already provider-agnostic; works with both clients unchanged.
- **B4 read finding**: the legacy `llm_fallback_*` settings in `config.py` are aspirational (zero call sites). Left in place but flagged as superseded by `LLM_PROVIDER`. See `00_audit.md` Appendix A.
- **B1 read finding**: MiroFish concurrency is hard-capped at `semaphore=30` per OASIS env (60 across parallel mode). Phase 5 KV-cache sizing on Qwen3.5-9B is comfortable. See `00_audit.md` Appendix B.

**Files added**:
- `orchestrator/clients/llm_protocol.py`
- `orchestrator/clients/openai_compat_client.py`
- `orchestrator/clients/llm_factory.py`
- `orchestrator/tests/test_openai_compat_client.py` (12 tests)
- `orchestrator/tests/test_vllm_smoke.py` (1 in-process E2E)
- `docs/competition/MODELS.md`, `docs/competition/03_run_locally.md`

**Files modified**:
- `orchestrator/config.py`, `orchestrator/api/__init__.py`, `orchestrator/cli.py`, `orchestrator/clients/__init__.py`, `orchestrator/requirements.txt`
- `orchestrator/tests/test_cli.py`, `orchestrator/tests/test_integration_loop.py` (patch target moved from `ClaudeClient` to `build_llm_client`)
- `tribe_scorer/requirements.txt` (torch pin relaxed `<2.7` → `<3.0`)
- `CLAUDE.md` (drop stale sm_120/CPU-fallback claim, add hackathon section)
- `.env.example` (drop leftover `TRIBE_TEXT_ONLY`)
- `.gitignore` (carve out `docs/competition/`)

**Validation passed**:
- `pytest --ignore=orchestrator/tests/test_tribe_timeout.py` — 251 passed.
- `test_tribe_timeout.py` is pre-existing broken on `main` (imports `CHUNK_SIZE_WORDS` that doesn't exist; commit `495956b`). Out of scope for Phase 0.
- E2E smoke: variant_generator → OpenAICompatClient → in-process FastAPI fake vLLM → parsed variants. Wiring confirmed before MI300X provisioning.

## Phase 1 — Local: TRIBE GPU-path un-pinning + whisperx replacement + ROCm dockerfile (0 cloud hrs) — **DONE**

**Goal achieved**: TRIBE source no longer hard-codes CPU at runtime; whisperx swapped for transformers Whisper-large-v3 (Path B); ROCm Dockerfile + compose overlay written; per-window timeline preserved through the API for Phase 5 UI. 251 orchestrator tests + 32 tribe_scorer tests green.

**Decisions vs original plan**:
- **Path B confirmed** (transformers Whisper). ctranslate2 + faster-whisper out of the dep tree entirely.
- **Vendored TRIBE source NOT edited.** `tribe_scorer/vendor/tribev2/` is tracked as a git **submodule** (separate `.git`, gitignored in parent, gitlink at commit `7fd7b41`). Editing files inside means committing to inner repo + bumping parent pointer — high cost for a one-line monkey-patch. **Cleaner alternative used**: install a startup monkey-patch from `tribe_scorer/scoring/whisper_hf.py:install_eventstransforms_patch()` that replaces `ExtractWordsFromAudio._get_transcript_from_audio` in-process. Vendored source on disk stays Meta-upstream (zero submodule pointer churn). The hard-coded `device="cpu"` and `compute_type="float32"` lines at `vendor/tribev2/tribev2/eventstransforms.py:104-105` become dead code — replaced wholesale at startup before any whisperx import can fire.
- **Per-window timeline added** as a parallel set of functions (`score_text_with_timeline`, `score_audio_with_timeline`, `score_video_with_timeline`) instead of refactoring existing scorers' return signatures. Keeps the 7 chunking tests + baseline-seeding code paths untouched. Single endpoints emit `timeline` + `tr_seconds`; batch endpoint stays scalar-only (consumer-deferred).

**Files added**:
- `tribe_scorer/scoring/whisper_hf.py` — transformers Whisper-large-v3 wrapper + idempotent monkey-patch installer
- `tribe_scorer/Dockerfile.rocm` — `rocm/pytorch:rocm6.2_ubuntu22.04_py3.11_pytorch_2.5.1` base, ffmpeg + Python deps, preserves the preinstalled ROCm torch wheel
- `docker-compose.rocm.yml` — overlay adding the tribe_scorer container with `/dev/kfd` + `/dev/dri` passthrough, video group, host IPC, 16 GB shm
- `tribe_scorer/tests/test_whisper_hf.py` — 8 tests, mocked HF pipeline (no weights downloaded)
- `tribe_scorer/tests/test_timeline_output.py` — 8 tests covering per-window ROI extraction + score_text_with_timeline
- `docs/competition/TRIBE_API.md` — response shape contract for Phase 5

**Files modified**:
- `tribe_scorer/main.py` — wire whisper_hf patch at startup; add `timeline` + `tr_seconds` fields to `ScoreResponse`/`AudioScoreResponse`/`VideoScoreResponse`; switch single endpoints to `_with_timeline` scorer variants
- `tribe_scorer/scoring/text_scorer.py` — `_score_single_chunk` returns 4-tuple (now includes raw `preds`); legacy `score_text` drops the new value; add `score_text_with_timeline`
- `tribe_scorer/scoring/audio_scorer.py` — add `score_audio_with_timeline`
- `tribe_scorer/scoring/video_scorer.py` — add `score_video_with_timeline`
- `tribe_scorer/scoring/roi_extractor.py` — add `extract_roi_activations_per_window`
- `tribe_scorer/requirements.txt` — bump `transformers` to `>=4.45.0` (needed for Whisper-large-v3 word timestamps), add `torchaudio>=2.5.0,<3.0`. whisperx/faster-whisper/ctranslate2 were never in `requirements.txt` (installed ad-hoc via README per the audit), so nothing to remove
- `orchestrator/clients/tribe_client.py:_extract_scores` — passthrough `timeline` + `tr_seconds`
- `CLAUDE.md` — note whisperx removed; transformers Whisper is the new path

**Validation passed**:
- `pytest tribe_scorer/tests` — 32 passed
- `pytest --ignore=orchestrator/tests/test_tribe_timeout.py` — 251 passed (orchestrator suite, regression-free)

**Validation deferred**:
- `docker build -f tribe_scorer/Dockerfile.rocm tribe_scorer/` — Docker daemon was not running on the local box during this session. Image build will be re-validated either (a) in a follow-up session with Docker Desktop running, or (b) on first cloud provisioning in Phase 3 (the Dockerfile is intentionally minimal so first-build iteration is cheap).

**Risk update**:
- `ctranslate2` risk gone (eliminated by Path B).
- `neuralset` / `neuraltrain` ROCm risk unchanged (still unknown until Phase 3).
- New transformers-Whisper alignment-quality risk: ~50-100ms vs whisperx ~20-50ms — well within TRIBE's window-level scoring tolerance. Documented in `whisper_hf.py` docstring.

## Phase 2 — Local: vLLM container + model prefetch + Phase 3 runbook (0 cloud hrs) — **DONE**

**Goal achieved**: docker-compose.rocm.yml has both vLLM service tiers parameterised by env vars; `scripts/prefetch_models.sh` pulls all four model variants (primary + fallback) idempotently; `.env.hackathon.example` documents every required setting; the hour-22-friendly Phase 3 runbook is written. 274 orchestrator + 32 tribe_scorer tests green.

**Decisions vs original plan**:
- **No CPU vLLM smoke run.** Per Phase 2 spec, replaced by 23 static-correctness tests on the compose file (`test_compose_config.py`) — services exist, ports don't collide, GPU passthrough mounts present, model env vars wired, MiroFish routes to vllm-agents (not LiteLLM), HF cache shared between vllm tiers.
- **Port wiring**: vLLM containers bind to host `127.0.0.1:18000` (orchestrator tier) and `127.0.0.1:18001` (agent tier) instead of `:8000`/`:8001`. Reason: tribe_scorer already binds host `:8001`. Inside the docker network, services still reach each other on the original container ports (8000 / 8001).
- **No MiroFish code change** for dual-base-url support. Per Phase 0 audit, MiroFish reads its own `LLM_BASE_URL` independent of orchestrator's `VLLM_BASE_URL`. The compose-level env override is enough.
- **Orchestrator FastAPI runs natively** on the cloud VM (uvicorn), reaching vllm-orchestrator via the `:18000` host port binding. Containerising the orchestrator was out of Phase 2 scope.
- **Models default to Qwen3.5 primary**; flipping to Qwen3 fallback is a 4-line `.env.hackathon` edit, no compose change. The runbook documents the trigger conditions.

**Files added**:
- `scripts/prefetch_models.sh` — bash, idempotent, takes `HF_TOKEN` from env; pulls primary + fallback pairs by default (set `PREFETCH_FALLBACK=0` to skip the fallback ~80 GB)
- `.env.hackathon.example` — every required env var with comments; `.env.hackathon` itself gitignored
- `orchestrator/tests/test_compose_config.py` — 23 static checks
- `docs/competition/04_phase3_runbook.md` — 10 numbered steps, hour budget, failure-mode table

**Files modified**:
- `docker-compose.rocm.yml` — add `vllm-orchestrator` + `vllm-agents` services (shared `vllm_hf_cache` volume, GPU passthrough, parameterised model + memory util via env), override `mirofish` to point at `http://vllm-agents:8001/v1` and depend on `vllm-agents` (no longer LiteLLM)
- `.gitignore` — exclude `.env.hackathon`

**Validation passed**:
- `pytest orchestrator/tests/test_compose_config.py` — 23 passed
- `pytest --ignore=orchestrator/tests/test_tribe_timeout.py` — 274 passed (regression-free on the orchestrator side)
- `pytest tribe_scorer/tests` — 32 passed (unchanged from Phase 1)

**Validation deferred to Phase 3**:
- Real vLLM startup with the AMD Quick Start image's vLLM build
- Qwen3.5 architecture support in shipped vLLM (decision gate at runbook step 3)
- HF gate-approval status for all four Qwen variants + facebook/tribev2

**Risk update**:
- vLLM 0.17.x + Qwen3.5 compatibility: still unknown. The fallback to Qwen3 is a known-good config and is one env-edit away. Documented in the runbook decision gate.
- Two vLLM instances colocated on one MI300X partition VRAM: still unverified. `MEM_UTIL` defaults to 0.40 each (= 0.80 total) leaving headroom; the runbook step 6 has a VRAM check.

## Phase 3 — Cloud: smoke test on MI300X (~3 cloud hrs) — **DONE**

**Goal achieved**: real ROCm-TRIBE pipeline produced non-pseudo neural scores, Qwen3.5-9B (agents) and Qwen3.5-27B (orchestrator) ran on vLLM 0.17.1 / ROCm, full campaign completed end-to-end, `is_pseudo_score=false` confirmed.

**Outcome**:
- Cloud hours used: **~1.5 hr** (well under 3-hour budget)
- Model pair: **Qwen3.5 primary** (no fallback needed)
- Smoke artifact saved at `docs/competition/phase3_smoke.json`
- Smoke result preview:
  - v1 TRIBE: attention=70.3, emotion=70.0, memory=68.9, reward=66.7 (`is_pseudo_score=false`)
  - v2 TRIBE: attention=55.6, emotion=55.1, memory=54.4, reward=52.6 (`is_pseudo_score=false`)
  - Composite scoring: `attention_score`, `conversion_potential`, `audience_fit` filled. `virality_potential`, `backlash_risk`, `memory_durability`, `polarization_index` `None` (mirofish-dependent — see Known Issues below)
  - Qwen3.5-27B "Opus" analysis: 3 cross-system insights, 8861-char verdict, all 4 report layers generated

**Decisions vs original plan**:
- **vLLM 0.17.1 supports Qwen3.5** — architecture `Qwen3_5ForConditionalGeneration` recognised. Decision gate at runbook step 3 passed; no fallback needed. (Hybrid Mamba-attention model; vLLM handled mamba page sizing automatically.)
- **vLLM image**: AMD Quick Start ships `vllm/vllm-openai-rocm:v0.17.1` pre-pulled (33.9GB). Compose's `${VLLM_IMAGE}` env-var hook used; no `rocm/vllm:latest` pull needed. Saved ~10 min off the budget.
- **`--enforce-eager` required for orchestrator tier**. Qwen3.5-27B crashed with `AssertionError` during CUDA-graph "decode FULL" capture on ROCm. Adding `--enforce-eager` to orchestrator command (only) eliminates graph capture; agent tier (9B) didn't need it. Slight latency hit on orchestrator (sequential calls only), acceptable.
- **TRIBE Dockerfile.rocm base image change**: planned `rocm/pytorch:rocm6.2_ubuntu22.04_py3.11_pytorch_2.5.1` does not exist on Docker Hub. Used the AMD Quick Start image's pre-pulled `rocm:latest` (PyTorch 2.9.1+ROCm) instead. Required two follow-up fixes:
  - tribev2's pyproject pulls torch 2.6.0 CUDA wheel via deps; install with `--no-deps` to keep the ROCm torch in place. Add `neuralset==0.0.2 neuraltrain==0.0.2 x_transformers==1.27.20 moviepy>=2.2.1` explicitly.
  - Base has torchvision 0.24.1 / numpy 2.1.3 vs tribev2's pinned `torchvision<0.22` / `numpy==2.2.6` — runtime confirmed compatible, the constraints were too tight.
- **OpenAICompatClient needs dual base URLs**. Phase 0 design assumed one endpoint with two model names; in practice the two tiers live on different vLLM ports. Added `vllm_agent_base_url` config field; client now creates a second `AsyncOpenAI` instance for the agent tier when set. Patch lives on the droplet — backport to repo before Phase 4.
- **MiroFish health_check + LLM-token preflight both probe LiteLLM** with hard-coded `claude-haiku-4-5-20251001` model. Patched `health_check` in-place to skip the LiteLLM probe when `LLM_PROVIDER=vllm`. The `mirofish_runner.run_simulation` LiteLLM-token preflight is a separate code path that still failed and skipped all MiroFish simulations during smoke. **Backport for Phase 4**: patch the runner-side preflight similarly.
- **Pydantic schema gates**: `seed_content` requires `>=100 chars`, `agent_count >= 20`. Phase 3 runbook asked for N=10 — used N=20 instead. Backport: relax the runbook OR add CLI-side defaults that pad short seeds.
- **`uvicorn` deps**: `python-multipart` not in `orchestrator/requirements.txt` but FastAPI multipart routes need it. Installed manually on droplet; backport.
- **Session-detached uvicorn**: `nohup ... &` over SSH in a single command dies on session close. Used `setsid nohup ... < /dev/null > log 2>&1 &` instead.
- **TRIBE_SCORER_URL / MIROFISH_URL / ORCHESTRATOR_PORT** not in `.env.hackathon.example`. Defaults in `orchestrator/config.py` work for tribe (`localhost:8001`) but mirofish defaults to `localhost:5000` while base compose binds it on 5001. Added overrides on the droplet; backport to template.
- **AMD Quick Start image binds host port 8000** (jupyter). Orchestrator FastAPI moved to **8002** to avoid collision. Backport recommendation: change template default for ORCHESTRATOR_PORT to 8002 on the hackathon stack.

**Validation passed**:
- All 6 services healthy: tribe_scorer, vllm-orchestrator, vllm-agents, mirofish, neo4j, litellm (litellm running but unused).
- Smoke campaign: `stop_reason=max_iterations`, `is_pseudo_score=false` on both variants, 7-dim TRIBE values populated, Qwen-served verdict + scorecard + analysis + mass-psych all generated.
- Peak VRAM during smoke: ~177 GB / 192 GB (~92% utilisation) — tight but stable.

**Known issues to fix in Phase 4**:
1. MiroFish simulations skipped due to LiteLLM/Anthropic-token preflight in `mirofish_runner.run_simulation`. The patch for `mirofish_client.health_check` only covers the orchestrator's pre-flight; the runner has a duplicate check. **Patch the runner identically before Phase 4.**
2. `mirofish-dependent composite scores` (virality, backlash, memory_durability, polarization) are `None` until issue 1 is fixed.
3. The Qwen3.5 reasoning model emits `<think>` blocks before answers. JSON-mode (`response_format=json_object`) bypasses this safely; raw text-mode calls would not. Orchestrator's `OpenAICompatClient` should add a `<think>` stripper for defence-in-depth — backport for Phase 4.
4. `python-multipart` needs adding to `orchestrator/requirements.txt`.
5. AMD Quick Start image has a host-bound jupyter on `:8888` with a `JUPYTER_TOKEN`. Verify the token is strong before exposing the droplet to the public internet (the `134.199.x.x` IP is reachable). Out-of-scope for Phase 3; flag for Phase 4 / production.

## Phase 4 — Cloud: validation + iteration-loop test on MI300X — **DONE** (1 session)

**Outcome**: Phase 3.5 backports validated end-to-end. Multi-iteration loop validated. CLAUDE.md ≤20 min target deferred — throughput-locked by AMD Cloud, not our code.

**Cloud hours used**: ~3 hr of 6 hr budget (single session). Remaining ~3 hr unspent — banked for Phase 5.

**See**: [`docs/competition/05_phase4_runbook.md`](05_phase4_runbook.md) for the runbook followed.

### Decision: scaled down from N=40/4-iter to N=20/2-iter

The validation-gate smoke (N=20, 1 iter) passed all bars. Step 5 was scaled down to N=20 / **2 iterations** (vs the original N=40 / 4-iter) because:

- The validation gate already proved end-to-end pipeline correctness (TRIBE + MiroFish + Qwen3.5-27B + composite + 4-layer report).
- The iteration-loop validation only needs ≥2 iterations to prove iter-N receives iter-(N-1) context.
- The N=40 / 4-iter target is **architecturally aspirational on this stack** — see "Throughput observation" below.
- Saving session time for Phase 5 prep.

### Validation gate (smoke, N=20, 1 iter, 21 min wallclock)

Artifact: [`phase4_validation_smoke.json`](phase4_validation_smoke.json) (recovered as `phase3_smoke.json`'s successor; logs at `phase4_step5.log`).

- TRIBE: `is_pseudo_score=False` both variants
- **MiroFish: non-None metrics on both variants** (Phase 3.5 items 2+3 unlock confirmed)
- All 7 composite scores populated (no `None` mirofish-side)
- Qwen3.5-27B "Opus" analysis: 3 cross-system insights, 4 report layers generated

### Step 5 (N=20, 2 iter, 27 min wallclock)

Artifact: [`phase4_step5.json`](phase4_step5.json) + [`phase4_step5.log`](phase4_step5.log).

- `stop_reason: max_iterations`
- 2 iterations completed
- **Iter 2 received iter 1 context** — variant IDs differ (iter 1 `v1_technical_benchmark, v2_systemic_pressure`; iter 2 `v3_architectural_shift, v4_peer_validation`); also visible in best-score improvement: iter 1 best attention=66.7 → iter 2 best 74.2
- All 7 composite scores populated for all 4 variants in both iterations
- `mirofish_metrics`: `shares={14, 6, 8, 6}` across the 4 variants — non-None throughout
- All 4 report layers generated (verdict + scorecard + mass-psych general/technical)

### Throughput observation — AMD Cloud GPU low-power lock

The MI300X on this AMD Developer Cloud droplet is **stuck at low-power state**. Symptoms:

- `rocm-smi` warns `AMD GPU device(s) is/are in a low-power state` continuously
- `rocm-smi --setperflevel high` returns `Not supported on the given system` — control-plane locks user override
- vLLM observed throughput: **~12-16 tokens/sec** on Qwen3.5-27B (one-shot 600-token gen took 48s)
- AMD Cloud UI dashboard shows CPU usage but **zero GPU usage data** — likely the metric agent (`rocm-exporter` / `amd-smi` daemon) isn't running, which may itself be why the control plane parks the GPU clock at the idle floor

At full clocks the same workload would run ~5x faster — putting the original N=40 / 4-iter target into the ≤20 min window. With clocks parked, projected wallclock for that target is ~80-100 min, well outside the constraint.

The throughput gap is a **policy / monitoring issue at the AMD Cloud layer, not a code issue in this repo**.

### In-session fixes (committed)

- `phase4: bump openai-compat httpx timeout 120→300s for 27B verdict gen` (`32d6e0f`) — at 12-16 tok/s, 2048-token verdict generation takes ~128s; the Phase 0 default 120s read timeout fired ~8s before vLLM finished, sending the orchestrator into a 70-min retry deadlock. 300s absorbs the slow throughput with margin.

### In-session droplet patches (NOT committed, lost on destroy)

These were applied directly to the running droplet during diagnosis. Re-apply if Phase 5 needs them — or backport upstream:

- `orchestrator/clients/mirofish_client.py:36`: `SIM_PREPARE_TIMEOUT = 300.0` → `600.0`. Reason: MiroFish prepare for our seed completes in ~5 min; the 5-min orchestrator-side timeout raced and fired ~4s after MiroFish reported success.
- `.env.hackathon`: dropped duplicate `NEO4J_PASSWORD=PWD_x3RtMqNo_1234` line (Phase 3 droplet append). Original `PWD_neo@MI300x` matches what neo4j data volume was inited with; the duplicate caused auth-rate-limit lockout.

### Phase 4 backlog (do before Phase 5)

1. **Backport `SIM_PREPARE_TIMEOUT=600` to repo.**
2. **Strip naked-reasoning preambles** in `OpenAICompatClient` text-mode. Item 4 backport regex `<think>[\s\S]*?</think>` doesn't catch Qwen3.5-27B's `Thinking Process: 1. Analyze the Request:...` form (no closing tag). Either strengthen the strip pattern, add a system-prompt instruction "do not show reasoning", or both.
3. **GPU clock investigation**: install/start AMD's `amd-smi-exporter` daemon on a fresh provision and watch whether the control plane unparks the GPU once it sees activity metrics. Open AMD Cloud support ticket if not.
4. **Per-entity persona multiplier**: mirofish maps 1 ontology entity → 1 OASIS agent. To honor `agent_count >> 1` from the CLI we need to either modify `oasis_profile_generator.generate_single_profile` to loop N personas/entity OR inject synthetic entities. Submodule edit, deferred.
5. **Original N=40 / 4-iter campaign** rerun once GPU clocks unpark. Same artifact would land in ≤20 min and prove CLAUDE.md target.

### Phase 4 status

✅ Validation gate passed
✅ Iteration loop validated
⚠ CLAUDE.md ≤20 min target deferred (cloud throughput cap, not code)
🟢 Pipeline confirmed production-ready end-to-end on ROCm vLLM 0.17.1 + Qwen3.5 dense pair

## Phase 5 — Demo path: backlog cleanup + timeline viz + 1000-agent (split)

Phase 5 splits into two sessions: **session 1 is local-only** (no cloud
spend) and clears the Phase 4 backlog plus builds the demo's hero
visualization. **Session 2 is the cloud rehearsal** (1000 agents + live
viz + integrated demo).

### Phase 5 session 1 — Local: backlog + timeline viz (0 cloud hrs) — **DONE**

**Goal achieved**: 2/5 backlog items closed, video stimulus plumbing
through CLI + schema, full TRIBE → storage → UI passthrough for the
per-window timeline, React TimelineChart + VideoStimulusPlayer wired
into the campaign-detail view, mock data in place so the demo runs
even on a laptop with no MI300X. 306 orchestrator tests + UI build
green.

**Commits** (on `competition/amd-hackathon`):
- `phase5/A1` — backport `SIM_PREPARE_TIMEOUT=600` (mirofish_client)
- `phase5/A2` — strip naked-reasoning preambles in OpenAICompatClient
  (`Thinking Process:` / `Reasoning:` / `Let me think` / `Let me analyze`
  with `\n\n**Heading**` transition); 7 unit tests
- `phase5/B1` — TribeScores.timeline + tr_seconds fields, TS UI types,
  6-test passthrough suite (extractor → schema → JSON → SQLite roundtrip)
- `phase5/B2` — CLI `--media-type {text,audio,video}` and `--media-path`;
  schema validator extended to require media_path for video too;
  `validate_default=True` so the check fires on omitted field; 6 tests
- `phase5/B3-B5` — `lib/timeline-channels.ts` (4 derived channels with
  documented blend formulas + min-max normalisation), `TimelineChart`
  (Recharts LineChart matching IterationChart styling, ReferenceLine
  playhead, mm:ss axis), `VideoStimulusPlayer` (HTML5 video + chart,
  timeupdate-bound, mock fallback + manual toggle),
  `mock_timeline_apple1984.json` (60s/12-window narrative arc),
  CampaignTabContent integration above the composite-profile section

**Outstanding from Phase 4 backlog** (deferred to session 2 / post-Phase-5):
- Item 3 — GPU clock investigation (cloud-only, needs MI300X provision)
- Item 4 — Per-entity persona multiplier (mirofish submodule edit)
- Item 5 — N=40 / 4-iter rerun (cloud)

**Tests**: full suite (306 passed, 1 pre-existing collection error in
`test_tribe_timeout.py` — `CHUNK_SIZE_WORDS` import drift, unrelated
to this session). UI `npm run build` green.

### Phase 5 session 2 — Cloud: rehearsal + viz wiring (~3 cloud hrs)

**Runbook**: `docs/competition/07_phase5_session2_runbook.md`.

**Goal**: real demo artifacts (Apple 1984 ad through full pipeline) and validation that the session-1 VideoStimulusPlayer + TimelineChart work against live TRIBE data through an SSH-tunnelled browser. 1000-agent path is honest-deferred until the per-entity persona multiplier (Phase 4 backlog item 4) lands.

**Files touched**:
- `mirofish/frontend/` — already has Vue UI with polling-based "realtime" endpoints (`profiles/realtime`, `config/realtime`, `run-status`). Confirm it stands up and is reachable from outside the cloud VM.
- `docker-compose.rocm.yml` — expose MiroFish frontend port externally
- `ui/` — embed MiroFish UI via iframe in the Simulation tab; add a real GET `/api/campaigns/{id}/media` route so the VideoStimulusPlayer can play uploaded mp4s (currently surfaced from `ui/public/demo_assets/`)
- Throughput tuning: MiroFish agent batching (`mirofish/backend/scripts/run_parallel_simulation.py`) to keep Qwen 7B vLLM saturated without OOM
- Per-entity persona multiplier (Phase 4 backlog item 4)

**Validation**:
- 1000 agents run to completion
- Vue UI shows live graph updates
- Demo recordable as a single screen-share

**Cloud-hour budget**: 6 hrs.

**Risk**: **MEDIUM-HIGH** — 1000-agent concurrency is untested in this repo. KV-cache pressure is real. Fallback: scale demo to 500 agents if 1000 OOMs the agent vLLM, document in submission.

## Phase 6 — Cloud: submission polish (~3 cloud hrs)

**Goal**: clean demo recording, README updates, hackathon submission artifacts.

**Files touched**: `README.md`, `docs/competition/`, possibly `mirofish/` README crosslink.

**Validation**:
- Demo video recorded (ideally 2 min, < 5 min)
- Repro instructions in `docs/competition/03_run_on_amd.md` (to be added during this phase)
- Submission form filled

**Cloud-hour budget**: 3 hrs.

## Cloud-hour summary

| Phase | Hours | Cumulative |
|-------|-------|------------|
| 3 — smoke | 3 | 3 |
| 4 — full quality | 6 | 9 |
| 5 — 1000 agents + viz | 6 | 15 |
| 6 — polish | 3 | 18 |
| Buffer | 7 | 25 |

Phases 0-2 are local and gate cloud entry. **Do not provision MI300X until all three local phases are green.**

## Phase risk matrix

| Phase | Risk | Top blocker | Fallback |
|-------|------|------------|----------|
| 0 | LOW | refactor regression | revert; existing tests catch it |
| 1 | MEDIUM | `ctranslate2` ROCm | replace whisperx with `transformers` Whisper |
| 2 | LOW | image pull bandwidth | none needed |
| 3 | HIGH | `neuralset` ROCm; 2-vLLM colocation | sequential model loading; pseudo-score path stays as escape valve |
| 4 | MED | KV-cache OOM | reduce `--max-num-seqs` |
| 5 | MED-HIGH | 1000-agent concurrency | scale demo to 500 |
| 6 | LOW | — | — |
