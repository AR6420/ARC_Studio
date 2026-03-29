---
name: Nexus Sim — Project Overview
description: Core architecture, module layout, and key patterns for the Nexus Sim content optimization platform
type: project
---

Nexus Sim is a modular monorepo at C:/Users/adars/Downloads/ARC_Studio. It combines TRIBE v2 (neural scoring, port 8001), MiroFish-Offline (social simulation, port 5000 via Docker), and Claude Opus/Haiku (analysis + generation) into an iterative content optimization feedback loop.

**Why:** Phase 1 POC, single-user, non-commercial. Full campaign (40 agents, 4 iterations) must complete in ≤ 20 minutes.

**How to apply:** All new orchestrator code lives under orchestrator/. Async (FastAPI + httpx) throughout. Pydantic v2 for all schemas. SQLite for storage. .env is at repo root (one level above orchestrator/).

Key service URLs (from .env):
- TRIBE v2: http://localhost:8001
- MiroFish: http://localhost:5000
- LiteLLM proxy: http://localhost:4000/v1
- Orchestrator: port 8000

Claude model assignments:
- Opus (claude-opus-4-6): cross-system analysis, final report generation
- Haiku (claude-haiku-4-5-20251001): variant generation, agent config translation, fast structured tasks
