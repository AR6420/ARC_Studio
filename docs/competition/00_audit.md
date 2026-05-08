# AMD Hackathon — Pre-Migration Audit

Branch: `competition/amd-hackathon`. Read-only findings. No code changed.

## 1. Repo state — known-bug verification

### (a) WhisperX subprocess/uvx bug — **FIXED in main**
- WhisperX is invoked as direct in-process import.
- `tribe_scorer/vendor/tribev2/tribev2/eventstransforms.py:96` `import whisperx`
- `eventstransforms.py:107` log "Running whisperx in-process (device=%s)"
- `eventstransforms.py:108,114,118,121` — `load_model`, `load_audio`, `load_align_model`, `align`
- No `uvx` references anywhere in repo. Subprocess calls in `tribe_scorer/` are for ffmpeg/ffprobe only (`scoring/video_scorer.py:26,64`, `scoring/audio_scorer.py:132`).

### (b) MiroFish nested `data` envelope — **FIXED in main**
- Helper `_get_field` at `orchestrator/clients/mirofish_client.py:41-46` checks top-level then `data.{field}`.
- Used at lines 362, 382, 414, 440, 459 (task/sim IDs and statuses).
- `_unwrap` inside `_extract_results` at `mirofish_client.py:576-584` handles `{"data": ..., "success": true}` for posts/actions/timeline/agent_stats.

No patches needed for these two bugs.

## 2. Claude API swap points

**Orchestrator hits Anthropic directly. MiroFish hits LiteLLM (or Ollama).** Two distinct backends to migrate.

### Anthropic SDK (orchestrator-only)
- `orchestrator/clients/claude_client.py:19-20` SDK import
- `claude_client.py:117,152,164` `AsyncAnthropic(api_key=...)` instantiation
- `claude_client.py:187` only call site: `self._client.messages.create(...)`
- `claude_client.py:195-198` Anthropic-shaped response parsing (`block.text`)
- Public surface: `call_opus` (259), `call_haiku` (314), `call_opus_json` (336), `call_haiku_json` (358), `_call_json` (380)
- Sticky Opus→Haiku fallback on 400/429: `claude_client.py:277,298-311`

### Credential / key reads
- `claude_client.py:25` default path `~/.claude/.credentials.json`
- `claude_client.py:36-58` `_load_api_key_from_credentials` (OAuth `accessToken`)
- `claude_client.py:120-147` `_resolve_api_key` (env > file)
- `orchestrator/config.py:42` `anthropic_api_key`
- `orchestrator/api/__init__.py:31-93` `_refresh_litellm_api_key()` rewrites `.env` and restarts LiteLLM

### Hard-coded `claude-*` model strings
- `orchestrator/config.py:54` default `"claude-opus-4-6"`
- `orchestrator/config.py:58` default `"claude-haiku-4-5-20251001"`
- `claude_client.py:111,114` env defaults same
- `mirofish_client.py:91,128,164` LiteLLM token-verification pings hard-code Haiku model name

### Haiku call sites
- `orchestrator/engine/variant_generator.py` (variant generation)
- `orchestrator/prompts/variant_generation.py`, `prompts/demographic_profiles.py:7`

### Opus call sites
- `orchestrator/engine/result_analyzer.py` (cross-system analysis)
- `orchestrator/engine/report_generator.py` (verdict + scorecard)
- `orchestrator/engine/campaign_runner.py:252-253` step-6 invocation
- `orchestrator/prompts/result_analysis.py`, `prompts/report_verdict.py`, `prompts/report_scorecard.py`

### Notable: orchestrator already mentions Ollama fallback
- `orchestrator/config.py:179` comment "fall back to a local Ollama model if Claude Haiku..." — plumbing for an OpenAI-compatible alt path may already exist. **Worth investigating** before writing fresh adapter.

## 3. CUDA / NVIDIA assumptions

### tribe_scorer service
- `tribe_scorer/config.py:35` `tribe_device: str = "cuda"` default
- `tribe_scorer/main.py:18-21` startup monkey-patches `torch.cuda.is_available=False` when `TRIBE_DEVICE=cpu`
- `main.py:120-144` GPU pre-flight, `torch.cuda.mem_get_info(0)`
- `main.py:303` peak VRAM via `torch.cuda.max_memory_allocated()` — **ROCm-PyTorch supports this API**
- `main.py:316,356-386` `_check_cuda_health` / `_require_cuda_healthy` — `torch.cuda.synchronize`, allocates on `device="cuda"`
- `main.py:744-786` `/health` — `is_available`, `get_device_name`, `mem_get_info`, `empty_cache`, `synchronize`
- `scoring/model_loader.py:16-25,62-67,107` device-coercion logic
- `scoring/text_scorer.py:101-102,118` `cuda.is_available` + `empty_cache`
- `scoring/audio_scorer.py:243` "CUDA OOM" comment
- `scoring/video_scorer.py:202-205,257-261` `reset_peak_memory_stats`, `max_memory_allocated`
- `tribe_scorer/requirements.txt:13-17` `torch>=2.5.1,<2.7` with sm_120 commentary

### Vendored TRIBE
- `vendor/tribev2/tribev2/eventstransforms.py:104` **hard-coded** `device = "cpu"` for WhisperX (sm_120 workaround); 105 `compute_type = "float32"`. **MUST be reverted/parametrized for MI300X.**
- `vendor/tribev2/tribev2/main.py:78-79` `cuda.empty_cache()` guard
- `vendor/tribev2/tribev2/demo_utils.py:192-193` standard `cuda if available`

### sm_120 references — comments only, no executable logic
- `requirements.txt:13-15`, `eventstransforms.py:104`, `model_loader.py:20`, `docs/pytorch_upgrade_path.md`

### dtype / autocast / kernel libs
- **No flash-attn, no xformers, no triton, no bitsandbytes, no deepspeed, no apex** anywhere in `tribe_scorer/`. Confirmed via grep.
- `x_transformers==1.27.20` uses deprecated `torch.cuda.amp.autocast` — should run on ROCm but **needs validation**.
- No explicit fp16/bf16 in TRIBE source; `compute_type="float32"` only.

## 4. MiroFish backend pluggability

**Already OpenAI-compatible. Migration is an env-var change.**

- `mirofish/backend/app/utils/llm_client.py:11` `from openai import OpenAI`
- `llm_client.py:33-37` `OpenAI(api_key=..., base_url=..., timeout=...)` — single client wrapper
- `mirofish/backend/app/config.py:31-33` reads `LLM_API_KEY`, `LLM_BASE_URL` (default Ollama `:11434/v1`), `LLM_MODEL_NAME` (default `qwen2.5:32b` — **already Qwen**)
- Ollama `num_ctx` shim at `llm_client.py:43-45,77-80` (only when base_url contains `:11434`) — harmless on vLLM
- `<think>` stripping for reasoning models at `llm_client.py:84-85`
- CAMEL/OASIS uses `ModelPlatformType.OPENAI` (`run_parallel_simulation.py:162,1035`; `run_reddit_simulation.py:120,465`; `run_twitter_simulation.py:120,458`) reading same env vars
- All MiroFish service consumers (`oasis_profile_generator.py:190`, `simulation_config_generator.py:232`) go through the wrapper. **Single swap point.**

**To repoint MiroFish at vLLM**: set `LLM_BASE_URL=http://<vllm-host>:8000/v1`, `LLM_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct`, `LLM_API_KEY=anything`. No code change.

## 5. Orchestrator Opus pluggability

**Anthropic SDK is inlined.** Response parsing is Anthropic-shaped (`block.text`). No abstraction layer.

Minimum refactor (prose):
- New `OpenAICompatClient` wrapper that exposes the same public surface as `ClaudeClient` (`call_opus_json`, `call_haiku_json`, `call_opus`, `call_haiku`).
- Internally uses `openai.AsyncOpenAI(base_url=<vllm>, api_key="x")`.
- Map: `call_opus*` → orchestrator-tier Qwen model, `call_haiku*` → agent-tier Qwen model. Two model names, one base URL.
- Drop the OAuth/`.credentials.json` path entirely (no auth on vLLM in dev).
- Drop the sticky Opus→Haiku fallback logic — replace with vLLM error retry only.
- Replace JSON-parsing path (`_call_json` at line 380) — vLLM supports `response_format={"type":"json_object"}` and guided decoding via `extra_body={"guided_json": schema}`. Cleaner than current Anthropic-text-then-parse approach.
- Provider toggle via `LLM_PROVIDER=anthropic|vllm` env var, fall back to existing `ClaudeClient` on `anthropic`.

Touched files: `claude_client.py` (or new `llm_client.py` + factory), `config.py` (model/url settings), `api/__init__.py` (drop `_refresh_litellm_api_key` from startup if `LLM_PROVIDER=vllm`).

## 6. TRIBE v2 dependency audit

### Hard pins
- `torch>=2.5.1,<2.7` (`tribe_scorer/requirements.txt:13`, `vendor/tribev2/pyproject.toml`)
- `numpy==2.2.6` (vendored TRIBE pyproject — hard pin)
- `torchvision>=0.20,<0.22`
- `transformers>=4.40.0`, `huggingface_hub>=0.23.0`
- `x_transformers==1.27.20`
- `neuralset==0.0.2`, `neuraltrain==0.0.2` — **Meta internal libs, opaque, may contain CUDA assumptions**
- `pyannote.audio` (transitive via whisperx) — pins Python 3.11

### Runtime-installed (per README:168)
- `whisperx`, `faster-whisper`, `ctranslate2`

### ROCm risk ranking
| Dep | Risk | Notes |
|-----|------|-------|
| `ctranslate2` (whisperx backend) | **HIGH** | Default wheels are CUDA-only. ROCm support: unknown. May need community fork or replacement (e.g. `transformers`-native Whisper). |
| `neuralset` / `neuraltrain` (Meta) | **HIGH** | Opaque internal libs, can't audit. May call CUDA APIs. |
| `pyannote.audio` | MEDIUM | Pure PyTorch; should run on ROCm but not validated. Pins Python 3.11. |
| `x_transformers` 1.27.20 | LOW-MED | Uses deprecated `torch.cuda.amp.autocast` — works on ROCm in practice but needs smoke test. |
| `torch 2.5.1-2.6.x` ROCm wheel | LOW | ROCm 6.2 has `torch==2.5.1+rocm6.2`. Available. |
| LLaMA 3.2-3B via `transformers` | LOW | Default attention impl, no flash-attn. |

### Minimum changes to run TRIBE on ROCm
1. Install ROCm-flavored PyTorch wheel matching the `<2.7` constraint (`torch==2.5.1+rocm6.2`).
2. Revert `vendor/tribev2/tribev2/eventstransforms.py:104-105` from hard-coded `device="cpu"` / `compute_type="float32"` back to GPU + fp16/bf16 path.
3. Resolve `ctranslate2` ROCm story (build from source against ROCm, OR swap whisperx for HF `transformers` Whisper). **Decide before Phase 1.**
4. Set `TRIBE_DEVICE=cuda` (ROCm PyTorch presents AMD as `"cuda"` device — no string change needed).
5. Validate `neuralset`/`neuraltrain` actually load on ROCm. **Unknown until tested.**

### Custom CUDA kernels
None in TRIBE source. No `.cu` files, no extension build in `setup.py`.

## 7. VRAM sizing — single MI300X (192GB HBM3)

Estimates assume bf16 weights (vLLM default on MI300X), reasonable KV-cache, vLLM `gpu_memory_utilization=0.9` per instance. Two vLLM instances (one per model tier) on the same GPU is supported but partitions VRAM.

| Component | bf16 weights | KV-cache budget assumption | Subtotal |
|-----------|--------------|----------------------------|----------|
| TRIBE v2 (LLaMA 3.2-3B + WhisperX large-v3 + brain encoder + activations) | ~10 GB | ~4 GB activation peak | **~14 GB** |
| Qwen 2.5 **7B**-Instruct (agents) | ~14 GB | 16k ctx × ~50 concurrent ≈ ~12 GB | **~26 GB** |
| Qwen 2.5 **32B**-Instruct (orchestrator) | ~64 GB | 32k ctx × few concurrent ≈ ~10 GB | **~74 GB** |
| Qwen 2.5 **72B**-Instruct (orchestrator alt) | ~144 GB | minimum ≈ ~6 GB | **~150 GB** |

**Config A — TRIBE + 7B + 32B (bf16)**: 14 + 26 + 74 ≈ **114 GB / 192 GB**. Comfortable. Leaves ~78 GB headroom for KV-cache expansion and 1000-agent burst. ✅ **Recommended.**

**Config B — TRIBE + 7B + 72B (bf16)**: 14 + 26 + 150 ≈ **190 GB / 192 GB**. **Not safe.** Will OOM under any agent concurrency. Mitigations:
- 72B in **FP8** (MI300X has native FP8): ~76 GB weights. Total ≈ 116 GB. Workable. vLLM supports FP8 KV cache + weights on MI300X.
- 72B in **AWQ 4-bit**: ~40 GB. Total ≈ 80 GB. Very comfortable but quality regression on long-form synthesis.
- Sequential serve (load 7B, swap to 72B) — adds load latency to every campaign. Hostile to demo flow.

**Recommendation**: start with **Config A (32B orchestrator, bf16)**. Promote to 72B FP8 only if 32B output quality is insufficient on a smoke test. The Qwen 2.5 72B FP8 path is concrete on MI300X, but adds setup risk on a tight 25-hour budget.

### Open sizing assumptions (for §02_open_questions)
- bf16 used throughout. Could go FP8 across the board for ~2× headroom.
- 1000-agent demo concurrency unknown — if MiroFish issues 1000 simultaneous prompts to Qwen 7B, KV burst >> 12 GB. Need to know batching/throttle behavior in MiroFish.
- TRIBE inference is currently serialized via `_inference_lock` — single-stream, low VRAM volatility. Confirmed safe to share GPU.

---

## Appendix A — B4: Ollama-fallback plumbing (Phase 0 read)

**Finding: aspirational, not implemented. Fresh wrapper warranted.**

- `orchestrator/config.py:175-190` defines `llm_fallback_enabled`, `llm_fallback_model` (`qwen2.5:7b`), `llm_fallback_base_url` (`http://localhost:11434/v1`).
- `.env.example:37-40` exposes the same three vars.
- **Zero references** anywhere else in `orchestrator/` (grep confirmed). The fallback is configured but no code reads or routes to it. The existing `ClaudeClient` has only an internal Opus→Haiku sticky fallback; it never touches Ollama.

**Implication for Phase 0 abstraction**:
- The new `OpenAICompatClient` does **not** need to extend or align with anything pre-existing. Naming convention should match: keep `llm_*` env-var prefix consistent with the existing `llm_fallback_*` style.
- The new vars `llm_provider` / `vllm_base_url` / `vllm_orchestrator_model` / `vllm_agent_model` are additive; the legacy `llm_fallback_*` settings are left untouched (out-of-scope for Phase 0; orphaned config, can be cleaned up later).

## Appendix B — B1: MiroFish concurrency model (Phase 0 read)

**Finding: hard-capped at 30 concurrent LLM calls per platform via OASIS semaphore. 1000-agent fanout is gated.**

Source: `mirofish/backend/scripts/run_parallel_simulation.py` (and sibling `run_twitter_simulation.py`, `run_reddit_simulation.py`).

### Concurrency knob
- Hard-coded `semaphore=30` passed to `oasis.make()`:
  - Twitter env: `run_parallel_simulation.py:1159`
  - Reddit env: `run_parallel_simulation.py:1350`
  - Single-platform: `run_twitter_simulation.py:596`, `run_reddit_simulation.py:581`
- **Not env-driven, not config-driven.** Code change required to tune.
- Comment: "Limit maximum concurrent LLM requests to prevent API overload"

### Per-tick call pattern
- Per round (lines 1228-1254 Twitter, 1427-1453 Reddit):
  1. `get_active_agents_for_round()` selects N active agents stochastically — `target_count = uniform(agents_per_hour_min, agents_per_hour_max) * peak_multiplier` (defaults 5-20, peak ×1.5 → typical 7-30 agents/round)
  2. `actions = {agent: LLMAction() for _, agent in active_agents}` — dict built all-at-once (line 1253)
  3. Single `await result.env.step(actions)` call hands the whole dict to OASIS (line 1254)
- The script does no `asyncio.gather` chunking, no semaphore, no manual batching. All fan-out delegated to OASIS-internal `semaphore=30`.

### Dual-LLM routing
- `LLM_BOOST_API_KEY` / `LLM_BOOST_BASE_URL` / `LLM_BOOST_MODEL_NAME` env vars (lines 999-1001) let Reddit (`use_boost=True`, line 1322) hit a **different provider** than Twitter (`use_boost=False`, line 1130). Useful for Phase 5: route Reddit and Twitter to the same vLLM agent endpoint or split across two endpoints.

### Peak simultaneous /v1/chat/completions
- Per platform env: capped at **30** in-flight.
- Parallel mode: **60** total (30 Twitter + 30 Reddit) hitting one or two upstreams depending on `LLM_BOOST_*`.
- N=1000 agents is **never** reached per round (stochastic activity gating + OASIS semaphore).

### KV-cache implication for Phase 5
- vLLM-served Qwen3.5-9B at peak ≤30 concurrent prompts is comfortable. Each agent has its own system prompt / memory → KV reuse is per-agent across rounds, not within a round.
- Phase 5 tuning lever (if needed): change `semaphore=30` to `semaphore=60` or `semaphore=15` directly in the OASIS instantiation. There is no env-var override path today.

