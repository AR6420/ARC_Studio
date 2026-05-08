# MODELS — vLLM-served Qwen pairs

Two model tiers, two pairs. Picked at deploy time via env vars; no code change needed to swap pairs.

## Primary — Qwen3.5 dense (released April 2026)

| Tier | Model id | bf16 weights | Notes |
|------|----------|--------------|-------|
| Agent (haiku) | `Qwen/Qwen3.5-9B` | ~22 GB incl. vision tower | MiroFish OASIS agents |
| Orchestrator (opus) | `Qwen/Qwen3.5-27B` | ~58 GB incl. vision tower | Cross-system analysis, report synthesis |

Both are tagged `Image-Text-to-Text` (multimodal). ARC_Studio uses them text-only — the vision tower loads but stays idle. Accepted overhead in exchange for the latest-generation text quality.

**VRAM total with TRIBE v2 (~14 GB)**: ~94 GB / 192 GB. Comfortable. Leaves ~98 GB for KV-cache headroom and 1000-agent burst.

## Fallback — Qwen3 dense (released April 2025)

| Tier | Model id | bf16 weights | Notes |
|------|----------|--------------|-------|
| Agent (haiku) | `Qwen/Qwen3-8B` | ~16 GB | Pure text, no vision tower |
| Orchestrator (opus) | `Qwen/Qwen3-32B` | ~64 GB | Pure text, no vision tower |

**VRAM total with TRIBE v2**: ~94 GB / 192 GB. Same headroom class.

## Trigger conditions for falling back

Switch from primary to fallback if **any** of the following happens during Phase 3 smoke:
- vLLM startup fails to recognise the Qwen3.5 architecture (vLLM 0.17.1 in the AMD Quick Start image predates Qwen3.5 by ~6 months — the architecture may not be supported without an in-place vLLM upgrade).
- Model weights fail to download from HuggingFace (gated, missing, or repo not yet public on the cloud VM's HF mirror).
- Quality on a 1-prompt sanity check is obviously broken (gibberish, refusal loops, empty completions).

The fallback is a **pure config change**, no code edits:

```bash
# In .env on the cloud VM
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_ORCHESTRATOR_MODEL=Qwen/Qwen3-32B    # was Qwen/Qwen3.5-27B
VLLM_AGENT_MODEL=Qwen/Qwen3-8B            # was Qwen/Qwen3.5-9B
```

Restart the orchestrator and the two vLLM containers — done.

## Hard rule — no MoE variants

Avoid all `*-A3B`, `*-A10B`, `*-A17B`, `Qwen3.6-*`, `Qwen3-Coder-Next` releases. The 25-hour cloud budget cannot absorb MoE-on-ROCm-vLLM debugging. **Dense models only.**

## Why not 72B

`Qwen2.5-72B-Instruct` bf16 is ~144 GB. With TRIBE (~14 GB) + a 7-9 GB agent model, total ≈ 190 GB / 192 GB — no headroom for KV-cache or any agent concurrency. FP8 (~76 GB) would fit but adds ROCm/vLLM-FP8 setup risk on a tight budget. Promote 72B FP8 only if the 27/32B output quality is insufficient on Phase 4 — not earlier.

## Why bf16 (not FP8)

MI300X has native FP8, and FP8 would roughly double the headroom — but FP8 adds first-time setup risk (vLLM flags, weight conversion, KV-cache type) that we don't want eating Phase 3-4 budget. bf16 is the known-good path; FP8 is the upgrade path if 32B isn't enough.
