# AMD Hackathon — Phased Migration Plan

Budget: ~25 GPU-hours on 1× MI300X. Solo. Submission window: May 4-10, 2026.

## Strategy

- **Local prep first** (Phases 0-2). Burn zero cloud hours on work that can be done on the dev box: code refactor, container builds, model downloads-to-cache validation, test suites with mocked vLLM.
- **Cloud-only for ROCm validation and demo** (Phases 3-6). Land on MI300X with image already built and code already passing locally.
- Reserve **~5 hours buffer** for the unknown. Do not exceed budget on validation phases.

## Phase 0 — Local: orchestrator LLM-provider abstraction (0 cloud hrs)

**Goal**: orchestrator can call either Anthropic or any OpenAI-compatible endpoint via env var.

**Files touched**:
- `orchestrator/clients/claude_client.py` — extract interface, keep as Anthropic impl
- new `orchestrator/clients/openai_compat_client.py` — vLLM client mirroring same surface (`call_opus_json`, `call_haiku_json`, `call_opus`, `call_haiku`)
- new `orchestrator/clients/llm_factory.py` — provider selector (`LLM_PROVIDER` env)
- `orchestrator/config.py` — add `llm_provider`, `vllm_base_url`, `vllm_orchestrator_model`, `vllm_agent_model`
- `orchestrator/api/__init__.py` — skip `_refresh_litellm_api_key` when provider is vllm
- All call sites of `ClaudeClient` use factory output (DI already in place per fixtures)
- Tests: extend `mock_claude_client` fixture to cover both impls; add `test_openai_compat_client.py` with mocked httpx

**Validation**:
- `pytest` green (194+ tests)
- Local mock vLLM (a tiny FastAPI mimicking `/v1/chat/completions`) → full campaign smoke run completes against TRIBE-pseudo-mode + MiroFish

**Risk**: low. Pure refactor. Existing tests catch regressions.

## Phase 1 — Local: TRIBE GPU-path un-pinning + ROCm dockerfile (0 cloud hrs)

**Goal**: TRIBE source no longer hard-codes CPU; ROCm container image builds.

**Files touched**:
- `tribe_scorer/vendor/tribev2/tribev2/eventstransforms.py:104-105` — restore device-aware path (parametrize via env, default to model loader's device)
- `tribe_scorer/scoring/model_loader.py:16-25` — keep CPU fallback escape hatch but driven by env, not always-on
- new `tribe_scorer/Dockerfile.rocm` — base on `rocm/pytorch:rocm6.2_ubuntu22.04_py3.11_pytorch_2.5.1`, install requirements, deal with `ctranslate2` (see Risk below)
- new `docker-compose.rocm.yml` — overrides `tribe_scorer` service to use the ROCm image and mount `/dev/kfd` + `/dev/dri`

**Validation**:
- Image builds on local machine (no GPU exec needed yet)
- `pytest tribe_scorer/tests` still passes in CPU mode (existing path preserved)

**Risk**: **MEDIUM** — `ctranslate2` ROCm wheel does not exist publicly. Two paths:
- **Path A (preferred)**: build `ctranslate2` from source in the dockerfile against ROCm. Time-expensive; may not work.
- **Path B (fallback)**: replace whisperx with HF `transformers` Whisper-large-v3 + manual alignment. Loses some perf but pure PyTorch. **Decide on Path A vs B in Phase 0** so this phase doesn't block.

## Phase 2 — Local: vLLM container + model download dry-run (0 cloud hrs)

**Goal**: docker-compose includes a vLLM service stub and model weights are pre-cached on dev box (will rsync to cloud later, or HF-pull on cloud).

**Files touched**:
- `docker-compose.rocm.yml` — add `vllm-orchestrator` and `vllm-agents` services using `rocm/vllm:latest` image (or AMD's vLLM Quick Start image)
- `.env.hackathon` — Qwen model names, HF token, base URL
- `scripts/prefetch_models.sh` — `huggingface-cli download Qwen/Qwen2.5-7B-Instruct` + 32B

**Validation**:
- Compose file parses, image pulls, weights cached locally
- Run vLLM **CPU build** locally (slow, but proves config) for one prompt — OR use `vllm.entrypoints.openai.api_server` mocked test

**Risk**: low. No GPU code yet.

## Phase 3 — Cloud: smoke test on MI300X (~3 cloud hrs)

**Goal**: 1 stimulus → real ROCm-TRIBE → 100 MiroFish agents on Qwen 7B vLLM → Qwen 32B orchestrator → output JSON.

**Steps**:
1. Provision MI300X instance from AMD Quick Start vLLM image
2. Clone repo on `competition/amd-hackathon`, copy `.env.hackathon`
3. Pull MiroFish submodule, build TRIBE ROCm image, spin up compose stack
4. `huggingface-cli download` both Qwen models (Qwen 7B ~15GB, Qwen 32B ~65GB — over network, ~10 min)
5. Start vLLM-orchestrator (32B) and vLLM-agents (7B) on the same GPU with `--gpu-memory-utilization 0.45` each (or sequential vLLM if they collide)
6. Run CLI: `python -m orchestrator.cli --seed-content "..." --max-iterations 1` with **N=100 agents**

**Validation criteria**:
- All 7 TRIBE neural dimensions return real (non-pseudo) values
- TRIBE peak VRAM logged > 0
- 100 MiroFish agents complete
- Composite scorer produces non-None values
- Opus-equivalent (Qwen 32B) produces structured JSON analysis

**Cloud-hour budget**: 3 hrs. If still failing at hour 3, **stop and reassess**. Likely culprits: ctranslate2/whisperx, two vLLMs on one GPU, neuralset compatibility.

**Risk**: **HIGH** — first time anything in this stack runs on AMD silicon. Two genuine unknowns: (1) `neuralset`/`neuraltrain` ROCm behavior, (2) two-vLLM-on-one-GPU memory partition. Fallback if (2) blocks: serve only Qwen 7B from vLLM, keep "orchestrator" tier on Qwen 7B as well for the smoke phase. Demote 32B to Phase 4.

## Phase 4 — Cloud: real campaign at full quality (~6 cloud hrs)

**Goal**: 4-iteration campaign with 40 agents, both Qwen tiers active, completing under 20 min (CLAUDE.md target).

**Files touched**: tuning only — vLLM `--max-num-seqs`, `--max-model-len`, `gpu_memory_utilization`. No source changes if Phase 3 passed.

**Validation**:
- End-to-end campaign matches `<= 20 min` constraint from CLAUDE.md
- All 7 composite scoring formulas produce values within plausible ranges
- Cross-system Opus analysis produces non-trivial output

**Cloud-hour budget**: 6 hrs (mostly tuning + repeat runs).

**Risk**: medium. KV-cache OOM is the most likely hiccup; mitigation is `--max-num-seqs` reduction.

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
