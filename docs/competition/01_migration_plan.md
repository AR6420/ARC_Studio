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

## Phase 4 — Cloud: real campaign at full quality (~6 cloud hrs)

**Goal**: 4-iteration campaign with 40 agents, both Qwen tiers active, completing under 20 min (CLAUDE.md target).

**See**: [`docs/competition/05_phase4_runbook.md`](05_phase4_runbook.md) for the snapshot-restore + validation + tuning runbook.

**Files touched**: tuning only — vLLM `--max-num-seqs`, `--max-model-len`, `gpu_memory_utilization`. No source changes if Phase 3.5 backports stick.

**Validation**:
- End-to-end campaign matches `<= 20 min` constraint from CLAUDE.md
- `mirofish_metrics` non-None on every variant (Phase 3.5 items 2+3 unlock this)
- All 7 composite scoring formulas produce values within plausible ranges
- Cross-system Qwen3.5-27B analysis produces non-trivial output

**Cloud-hour budget**: 6 hrs total (4 hr / session × 1–2 sessions).

**Risk**: medium. KV-cache OOM is the most likely hiccup; mitigation is `--max-num-seqs` reduction. Secondary risk: backport items 2+3 don't fully unlock MiroFish — runbook step 4 has the validation gate that catches this before a real campaign burns budget.

## Phase 5 — Cloud: 1000-agent demo path + viz wiring (~6 cloud hrs)

**Goal**: 1000-agent simulation with live visualization matching MiroFish project-website demo.

**Files touched**:
- `mirofish/frontend/` — already has Vue UI with polling-based "realtime" endpoints (`profiles/realtime`, `config/realtime`, `run-status`). Confirm it stands up and is reachable from outside the cloud VM.
- `docker-compose.rocm.yml` — expose MiroFish frontend port externally
- Possibly `ui/` (orchestrator React UI) — embed MiroFish UI via iframe, or accept that the demo opens MiroFish's own UI directly
- Throughput tuning: MiroFish agent batching (`mirofish/backend/scripts/run_parallel_simulation.py`) to keep Qwen 7B vLLM saturated without OOM

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
