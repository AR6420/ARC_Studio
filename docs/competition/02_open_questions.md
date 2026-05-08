# AMD Hackathon — Open Questions

Things I assumed in the audit/plan that I want you to confirm before Phase 0 begins. Grouped by impact.

## A. Blocking — answer before Phase 0

### A1. Qwen variant choice
- I assumed **`Qwen/Qwen2.5-7B-Instruct`** for agents and **`Qwen/Qwen2.5-32B-Instruct`** for orchestrator (bf16, both bf16-native).
- 72B in bf16 does **not fit** alongside TRIBE + 7B (~190/192 GB, no headroom). 72B-FP8 fits but adds setup risk.
- Alternatives worth flagging:
  - **`Qwen2.5-Coder-32B`** for orchestrator if structured-JSON synthesis dominates output (the report-generator and result-analyzer both need structured outputs)
  - **`Qwen3-*`** family if you'd prefer the newer generation — but I have not validated vLLM ROCm support for Qwen3 specifically. Unknown.
- **Decision needed**: 7B / 32B / 72B-FP8, and Coder vs Instruct for orchestrator.

### A2. `ctranslate2` on ROCm
- Whisperx depends on `ctranslate2`, which ships CUDA-only wheels.
- Path A: build from source against ROCm. May fail; consumes Phase 1 time.
- Path B: replace whisperx with HF `transformers` Whisper-large-v3 + a manual alignment routine. Slightly less accurate alignment but pure PyTorch.
- **Decision needed**: A or B. I lean B for time-safety; you may have a strong preference for keeping whisperx.

### A3. `neuralset` / `neuraltrain` on ROCm
- These are Meta-internal pinned at `0.0.2` in `vendor/tribev2/pyproject.toml`. I cannot inspect their CUDA assumptions without running them.
- **Question**: do you know if anyone has run TRIBE v2 on AMD? Is there a community fork or a known-bad list? If unknown, we accept the risk and find out in Phase 3.

## B. Should-answer — affect Phase 1-2

### B1. MiroFish 1000-agent concurrency model
- I haven't traced how `run_parallel_simulation.py` batches LLM calls. If it fires 1000 concurrent prompts, KV-cache on Qwen 7B will OOM.
- **Question**: should I trace and document this in Phase 0, or do you already know the worker/concurrency knob?

### B2. Visualization parity with MiroFish project website
- MiroFish has a Vue 3 SPA with polling-based "realtime" endpoints (`/api/simulation/{id}/profiles/realtime`, `/run-status`). No WebSocket.
- The demo on miroFish.ai may use a different/richer viz than what's checked into the submodule.
- **Question**: is the existing Vue UI in `mirofish/frontend/` the same one shown on the project site, or do I need to wire something different?

### B3. Orchestrator UI integration
- `ui/` (React) and `mirofish/frontend/` (Vue) are independent today. The React UI consumes only the metric numbers.
- Demo options:
  1. Open both UIs side-by-side in browser tabs (zero work, ugly demo)
  2. Embed MiroFish Vue UI as iframe in React app (1-2 hr, looks unified)
  3. Build a new graph view in React that consumes MiroFish's polling endpoints (4-6 hr, polished but eats Phase 5 budget)
- **Question**: which option for the demo?

### B4. Existing Ollama-fallback plumbing
- `orchestrator/config.py:179` mentions an Ollama fallback for Haiku. I haven't read whether this is implemented or aspirational.
- **Question**: should I extend the existing Ollama path to be the OpenAI-compatible client, or write a fresh wrapper? Reading the existing code first will save effort if it's real.

## C. Nice-to-know — won't block but informs decisions

### C1. Observability preservation
- No Prometheus/OpenTelemetry/Sentry in the repo. Only stdlib logging + SSE progress stream + per-inference VRAM logging.
- I assumed we keep this exactly as-is and just rename "CUDA" labels to "GPU" where appropriate (`torch.cuda.max_memory_allocated()` works on ROCm but the field name is misleading).
- **Question**: any observability tooling you want added for the hackathon submission (e.g. Grafana panel for live demo)?

### C2. Submission artifact expectations
- Hackathon may want: code repo link, demo video, written writeup, AMD-specific perf numbers.
- I assumed Phase 6 produces a 2-5 min demo video + repro instructions in `docs/competition/03_run_on_amd.md`.
- **Question**: does AMD's submission form require anything specific (model card, perf benchmark vs CPU baseline, etc.)?

### C3. LiteLLM in the cloud stack
- LiteLLM is currently the proxy MiroFish hits. On the MI300X, MiroFish would point directly at vLLM (also OpenAI-compatible).
- I assumed **drop LiteLLM entirely** in the hackathon stack — it's redundant.
- **Question**: confirm we can drop it (it adds an extra container with no purpose once Anthropic isn't in the loop).

### C4. Branch hygiene
- I created `competition/amd-hackathon`. The submodule pointers (`mirofish`, `tribe_scorer/vendor/tribev2`) are dirty on main per `git status`. I have not changed them.
- **Question**: should I commit submodule pointer fixes to main first, or carry them on the competition branch?

## D. Things I do not know and did not guess

- Whether `neuralset` actually loads on ROCm (Phase 3 will reveal)
- Whether two vLLM instances colocated on one MI300X partition VRAM cleanly (likely yes per AMD docs, but unverified by me)
- Whether the AMD vLLM Quick Start image is recent enough for Qwen 2.5 — I assumed yes; verify when provisioning
- Whether HF Hub bandwidth from AMD Cloud → HF is fast enough to download 80 GB of Qwen weights inside Phase 3's 3-hour budget. May need to pre-stage weights.
- Whether `x_transformers==1.27.20` actually runs on ROCm without modifications (deprecated `cuda.amp.autocast` usage — should be fine but unverified)
