# Nexus Sim

## What This Is

Nexus Sim is a content optimization platform that combines neural response prediction (TRIBE v2), multi-agent social simulation (MiroFish-Offline), and LLM-driven iterative optimization (Claude Opus) into a single feedback loop. A user submits content (product launch, PSA, policy draft, etc.), and the system generates variants, scores them neurally, simulates social propagation, analyzes cross-system results, and iterates until thresholds are met. Phase 1 POC — single-user, local machine, non-commercial.

## Core Value

The iterative feedback loop between neural scoring (TRIBE v2) and social simulation (MiroFish) produces measurably better content than single-pass generation, with cross-system reasoning that explains WHY certain neural patterns lead to specific social outcomes.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] End-to-end pipeline: brief -> variant generation -> neural scoring -> simulation -> analysis -> report
- [ ] TRIBE v2 neural scoring service with 7 dimensions (attention, emotion, memory, reward, threat, cognitive load, social)
- [ ] MiroFish social simulation integration (8 metrics: shares, sentiment, counter-narratives, virality, drift, coalitions, influence, divergence)
- [ ] Claude Opus/Haiku client with rate limiting and fallback
- [ ] Iterative optimization loop with convergence detection and threshold checking
- [ ] 7 composite scores (attention, virality, backlash, memory, conversion, audience fit, polarization)
- [ ] 4-layer report output (verdict, scorecard, deep analysis, mass psychology)
- [ ] React + Vite + TypeScript dashboard with campaign form, results tabs, and progress streaming
- [ ] SSE real-time progress during campaign runs
- [ ] 6 demographic presets + custom demographic input
- [ ] Campaign persistence (SQLite) with CRUD operations
- [ ] Agent interview capability (proxy through orchestrator to MiroFish)
- [ ] Graceful degradation when TRIBE or MiroFish is unavailable
- [ ] JSON + Markdown export of results
- [ ] 5 demo scenarios validated against quality standards

### Out of Scope

- Authentication / multi-user — single-user POC, add in Phase 2
- HTTPS / TLS — localhost only, add in Phase 2
- Video/audio stimulus for TRIBE v2 — text-only for Phase 1
- Real-time chat — not core to optimization value
- Mobile app — web-first
- PostgreSQL — SQLite sufficient for single-user
- OAuth login — not needed for POC
- Microservices infrastructure (gRPC, message queues, service mesh) — modular monorepo is appropriate at POC scale

## Context

### Architecture
Modular monorepo with Docker service boundaries. Four main modules:
- **orchestrator/** — FastAPI (Python 3.11+), the brain. Orchestrates all systems, stores campaigns in SQLite.
- **tribe_scorer/** — FastAPI + PyTorch, runs TRIBE v2 inference on local GPU (CUDA). Not in Docker (needs direct GPU access).
- **mirofish/** — Git submodule (forked MiroFish-Offline). Flask + Neo4j + Ollama + LiteLLM -> Claude Haiku.
- **ui/** — React 18 + Vite + TypeScript + Tailwind CSS + Recharts.

### Infrastructure (Docker)
- Neo4j 5.15 (graph DB for MiroFish)
- Ollama (local embeddings only — nomic-embed-text)
- LiteLLM (OpenAI-compatible proxy -> Anthropic API for MiroFish agent LLM)

### Hardware
- GPU: RTX 5070 Ti (12GB VRAM) — TRIBE v2 (~8-10GB) + Ollama embeddings (~1GB)
- RAM: 32GB
- Disk: 1TB SSD

### Key Technical Decisions
- All inter-service communication is REST over localhost
- Claude Haiku for variant generation + MiroFish agents (fast, cheap)
- Claude Opus for cross-system analysis + report generation (quality)
- LiteLLM translates OpenAI format (MiroFish expects) to Anthropic API
- TRIBE v2 ROI mapping uses Glasser HCP-MMP1.0 atlas parcellation
- Composite score formulas defined in Results.md Section 3.2
- Fallback to local Ollama qwen2.5:7b if Haiku rate limited

## Constraints

- **Hardware**: Single RTX 5070 Ti GPU shared between TRIBE v2 and Ollama embeddings
- **API**: Claude API rate limits — Haiku batched, Opus sequential (4-8 calls/campaign)
- **Dependency**: TRIBE v2 requires HuggingFace LLaMA 3.2-3B gated model approval
- **Dependency**: MiroFish-Offline is a fork/submodule — minimal modifications to enable upstream merges
- **Performance**: Full campaign (40 agents, 4 iterations) must complete in <= 20 minutes
- **Scope**: Phase 1 POC only — no auth, no HTTPS, no multi-user

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Modular monorepo (not microservices, not monolith) | Components have different runtime requirements but microservices is too much infra for solo dev | -- Pending |
| TRIBE v2 runs on host (not Docker) | Needs direct CUDA access, Docker GPU passthrough adds complexity for POC | -- Pending |
| SQLite (not PostgreSQL) | Single-user, no concurrent writes, simpler setup | -- Pending |
| LiteLLM proxy for MiroFish | MiroFish expects OpenAI-compatible API, LiteLLM translates to Anthropic | -- Pending |
| Claude Haiku for agents, Opus for analysis | Cost/speed optimization — agents need volume, analysis needs depth | -- Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-28 after initialization*
