# A.R.C Studio

**Audience Response Cortex Studio** — predict how content will land, neurally and socially, before you publish. Then iterate on it. Running on a single AMD MI300X.

> **AMD Developer Hackathon 2026 submission.**
> Landing page + demo video: **https://arc-studio-three.vercel.app/**

![A.R.C Studio architecture](assets/architecture.png)

> Branch: `competition/amd-hackathon`. `main` is the original Anthropic/CUDA build; everything in this README describes the AMD migration.

---

## Elevator pitch

A.R.C Studio is a content-optimization loop. You hand it a stimulus — a video, an audio clip, or text — plus a prediction question and a target demographic. It generates strategic variants, predicts the neural response of each one with Meta FAIR's TRIBE v2 brain encoder, simulates how a thousand demographic-tuned agents share and argue about each one in MiroFish, then has a larger Qwen orchestrator read both signals together and write the next round of variants. The loop converges on content that does well on both axes simultaneously — neural attention *and* social spread — and explains why. The whole stack runs on one MI300X with zero NVIDIA in the inference path.

## What's running on AMD

| Layer | Model / runtime | Where it runs |
|------|------------------|---------------|
| Variant generation (agent tier) | Qwen3.5-9B, vLLM 0.17.1, max_model_len=16384 | MI300X — ~42 GB VRAM |
| Cross-system orchestrator | Qwen3.5-27B, vLLM 0.17.1, max_model_len=16384 | MI300X — ~102 GB VRAM |
| Neural encoder | Meta FAIR TRIBE v2 (LLaMA 3.2-3B + Whisper-large-v3 + V-JEPA2-Giant) | MI300X — ROCm PyTorch |
| Social simulation | MiroFish (CAMEL-AI / OASIS), Qwen3.5-9B agents via vLLM | MI300X — shares the agent tier |
| Embeddings | Ollama nomic-embed-text | host CPU — does not touch the GPU |

- **Hardware**: 1× AMD MI300X 192 GB HBM3, AMD Developer Cloud
- **Stack**: ROCm 7.2 + vLLM 0.17.1 (rocm/vllm container), pure PyTorch (no CTranslate2, no Triton-CUDA paths)
- **Zero NVIDIA in the inference path.** The Anthropic API client and CUDA Whisper backend that `main` uses were both pulled out — see `docs/competition/00_audit.md` for the swap inventory and `01_migration_plan.md` for what got rewritten.

## How it works

Stimulus in → Qwen3.5-9B drafts N strategic variants → for each variant TRIBE v2 produces a 7-channel per-window neural timeline (TTS → Whisper → LLaMA word embeddings → brain-encoding → ROI extraction) and MiroFish runs a multi-round simulation of demographically-tuned agents → composite scorer blends the two into 7 outcome dimensions → Qwen3.5-27B reads the joint TRIBE+MiroFish signal and writes the iteration's analysis + next-round directives → loop. Three iterations is enough for the optimizer to find a meaningfully different strategy and explain it.

## Reproducing the demo

You will need an MI300X. The full provisioning + first-campaign sequence lives in **[`docs/competition/04_phase3_runbook.md`](docs/competition/04_phase3_runbook.md)** — that's the authoritative path, not this section.

The short version:

1. AMD Developer Cloud → 1× MI300X with the **vLLM Quick Start** image.
2. Clone this branch: `git clone --branch competition/amd-hackathon --recursive https://github.com/AR6420/ARC_Studio.git`
3. Follow `04_phase3_runbook.md` (env file, vLLM containers up, TRIBE weights, orchestrator + UI).
4. Run a campaign: `docs/competition/05_phase4_runbook.md`.

Expect ~30–60 minutes from a clean droplet to first completed campaign. A campaign with N=100 agents and 3 iterations on the Apple 1984 ad finishes in roughly 60 minutes wall-clock.

## Repository tour

| Path | What it is |
|------|------------|
| `orchestrator/` | FastAPI service that drives the loop: variant generation, TRIBE/MiroFish clients, composite scoring, optimization loop, report generation, SSE progress stream |
| `tribe_scorer/` | ROCm-PyTorch wrapper around TRIBE v2 (HTTP service on :8001). In-process Whisper, V-JEPA2 video, LLaMA-3.2-3B text, brain-encoding head |
| `mirofish/` | Vendored MiroFish (Git submodule). OASIS-based agent simulation, Neo4j-backed knowledge graph, NER prompt softened for the Qwen agent tier |
| `ui/` | React 19 + Vite + TS + shadcn/ui frontend. Includes the playback-synced neural timeline chart, simulation tab, and 4-layer report view |
| `docker-compose.rocm.yml` | The MI300X-side stack — vLLM agent + orchestrator containers, MiroFish, Neo4j, LiteLLM, orchestrator |
| `docs/competition/` | Audit, migration plan, runbooks, demo plan, measured artifacts. This is where the work is documented |

## Submission artifacts

These are the actual files judges should look at if they want to verify the work:

| File | What it is |
|------|------------|
| [`docs/competition/00_audit.md`](docs/competition/00_audit.md) | Pre-migration repo audit — every Anthropic call site, CUDA assumption, and ROCm risk inventoried |
| [`docs/competition/01_migration_plan.md`](docs/competition/01_migration_plan.md) | Phased migration plan with actuals filled in as phases landed |
| [`docs/competition/04_phase3_runbook.md`](docs/competition/04_phase3_runbook.md) | First MI300X provisioning runbook — line-by-line, time-boxed |
| [`docs/competition/05_phase4_runbook.md`](docs/competition/05_phase4_runbook.md) | First end-to-end campaign run on MI300X |
| [`docs/competition/07_phase5_session2_runbook.md`](docs/competition/07_phase5_session2_runbook.md) | Demo capture session runbook |
| [`docs/competition/06_demo_plan.md`](docs/competition/06_demo_plan.md) | Demo narrative — what the recorded video shows and why |
| [`docs/competition/MODELS.md`](docs/competition/MODELS.md) | Qwen model selection — primary/fallback pairs, VRAM math, why these specific sizes |
| [`docs/competition/TRIBE_API.md`](docs/competition/TRIBE_API.md) | TRIBE response contract |
| [`docs/competition/phase3_smoke.json`](docs/competition/phase3_smoke.json) | First successful end-to-end campaign on MI300X |
| [`docs/competition/phase4_step5.json`](docs/competition/phase4_step5.json) | Phase 4 measured campaign output |
| [`docs/competition/phase5_apple_n20_video.json`](docs/competition/phase5_apple_n20_video.json) | Apple 1984 ad, N=20 agents — measured |
| [`docs/competition/phase5_apple_n100_video.json`](docs/competition/phase5_apple_n100_video.json) | Apple 1984 ad, N=100 agents — measured |

## Honest scope

Six days, one engineer, one MI300X. Nothing in this repo claims production-readiness — this is a hackathon submission. What's working end-to-end on AMD: video stimulus ingestion, real TRIBE neural scores, real MiroFish simulations with Qwen agents, Qwen3.5-27B cross-system analysis, and a final report generated from both signals. What's not in scope: multi-user, auth, HTTPS, persistence beyond SQLite, fine-tuned domain models. The original `main` branch documents the broader project; this branch documents the AMD migration of it.

## Acknowledgments

- **Meta FAIR** — [TRIBE v2](https://github.com/facebookresearch/tribe), the trimodal brain encoder this whole stack is built around.
- **CAMEL-AI / OASIS** team — the multi-agent simulation framework MiroFish builds on.
- **AMD** — MI300X access via AMD Developer Cloud.
- **lablab.ai** — for organizing the AMD Developer Hackathon 2026.

## License

[AGPL-3.0](LICENSE), inherited from MiroFish-Offline. TRIBE v2 model weights are **CC-BY-NC** — see the [TRIBE v2 model card](https://huggingface.co/facebook/tribev2) for the upstream terms; non-commercial use only.
