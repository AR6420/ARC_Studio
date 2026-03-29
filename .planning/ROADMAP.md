# Roadmap: Nexus Sim (Phase 1 POC)

## Overview

Nexus Sim Phase 1 POC delivers an end-to-end content optimization platform in 9 phases. The journey begins with environment setup, then brings three independent systems online in parallel (MiroFish social simulation, TRIBE v2 neural scoring, Claude LLM client), integrates them through an orchestrator pipeline, adds iterative optimization and report generation, wraps everything in a React dashboard, and validates the core hypothesis across 5 demo scenarios. The critical path runs through TRIBE v2 setup (HuggingFace gated model dependency) into orchestrator integration, then optimization loop, then validation.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

**Parallelization:**
- Phases 2, 3, 4 can execute in parallel after Phase 1 completes (Sprint 1 tracks)
- Phases 6, 7, 8 can partially overlap after Phase 5 completes (Sprint 3 tracks)

- [ ] **Phase 1: Environment Setup** - All prerequisites installed, verified, and monorepo scaffolded
- [ ] **Phase 2: MiroFish-Offline Setup** - Social simulation running independently with Claude Haiku agents
- [ ] **Phase 3: TRIBE v2 Setup** - Neural scoring service running on local GPU with 7-dimension output
- [ ] **Phase 4: Claude Client Setup** - LLM client with Opus/Haiku methods, prompts, and demographic presets
- [ ] **Phase 5: Orchestrator Integration Pipeline** - All systems wired into single-iteration campaign pipeline
- [ ] **Phase 6: Optimization Loop** - Multi-iteration improvement with convergence detection and progress streaming
- [ ] **Phase 7: Report Generation** - 4-layer report output with JSON and Markdown export
- [ ] **Phase 8: UI Dashboard** - React dashboard with campaign form, results tabs, and real-time progress
- [ ] **Phase 9: Validation and Documentation** - 5 demo scenarios validated, documented, and recorded

## Phase Details

### Phase 1: Environment Setup
**Goal**: Machine is fully ready to build -- every dependency installed, verified, and the monorepo structure exists with all configuration in place
**Depends on**: Nothing (first phase)
**Requirements**: ENV-01, ENV-02, ENV-03, ENV-04, ENV-05, ENV-06, ENV-07, ENV-08, ENV-09
**Success Criteria** (what must be TRUE):
  1. `docker ps` runs successfully and `docker run --gpus all nvidia/cuda:12.0-base nvidia-smi` shows the RTX 5070 Ti
  2. `python -c "import torch; print(torch.cuda.is_available())"` returns True
  3. `docker compose up` brings Neo4j, Ollama, and LiteLLM to healthy state and all respond to health checks
  4. Monorepo directories exist (orchestrator/, tribe_scorer/, mirofish/, ui/, shared/, docs/) with .env populated and .gitignore configured
  5. HuggingFace CLI is logged in with LLaMA 3.2-3B gated model access approved, and Anthropic API key returns a valid response
**Plans**: TBD

### Phase 2: MiroFish-Offline Setup
**Goal**: MiroFish accepts content via API, runs a multi-agent social simulation using Claude Haiku, and returns structured results with all 8 metrics
**Depends on**: Phase 1
**Requirements**: MIRO-01, MIRO-02, MIRO-03, MIRO-04, MIRO-05, MIRO-06, MIRO-07, MIRO-08
**Success Criteria** (what must be TRUE):
  1. MiroFish fork exists as a Git submodule and its backend container starts alongside Neo4j, Ollama, and LiteLLM
  2. LiteLLM proxy successfully routes OpenAI-format chat completion calls to Claude Haiku (verified by curl test)
  3. Submitting content to the graph build API creates a knowledge graph, and running a simulation with 20+ agents produces structured results containing all 8 metrics (shares, sentiment, counter-narratives, virality, drift, coalitions, influence, divergence)
  4. An individual agent can be interviewed post-simulation via the agent chat API
**Plans**: TBD

### Phase 3: TRIBE v2 Setup
**Goal**: TRIBE v2 neural scoring service accepts text via API, runs inference on local GPU, and returns 7 normalized brain-region scores (0-100)
**Depends on**: Phase 1
**Requirements**: TRIBE-01, TRIBE-02, TRIBE-03, TRIBE-04, TRIBE-05, TRIBE-06, TRIBE-07
**Success Criteria** (what must be TRUE):
  1. TRIBE v2 model weights are downloaded and inference runs on the local GPU (nvidia-smi shows VRAM usage during scoring)
  2. FastAPI wrapper responds on port 8001 with /api/score, /api/score/batch, and /api/health endpoints
  3. Submitting a text to /api/score returns 7 normalized scores (attention, emotion, memory, reward, threat, cognitive load, social) each in the 0-100 range
  4. Scores vary meaningfully between different content types (e.g., fear-based vs. reward-based messaging produce different threat/reward scores)
**Plans**: TBD

### Phase 4: Claude Client Setup
**Goal**: Claude client wrapper supports both Opus and Haiku calls with retry logic, prompt templates, and demographic presets ready for orchestrator consumption
**Depends on**: Phase 1
**Requirements**: CLAUDE-01, CLAUDE-02, CLAUDE-03, CLAUDE-04, CLAUDE-05, CLAUDE-06
**Success Criteria** (what must be TRUE):
  1. Claude client can call both Opus and Haiku, including a JSON-mode method that returns parsed dictionaries
  2. Rate limit retry with exponential backoff works without crashing when limits are hit
  3. Prompt templates exist for variant generation, result analysis, and reporting, with placeholders for campaign data
  4. All 6 demographic presets are configured and the cross-system analysis prompt references both TRIBE scores and MiroFish metrics
**Plans**: TBD

### Phase 5: Orchestrator Integration Pipeline
**Goal**: A single campaign brief submitted via API or CLI flows through variant generation, neural scoring, social simulation, composite scoring, and cross-system analysis -- producing complete results in one iteration
**Depends on**: Phase 2, Phase 3, Phase 4
**Requirements**: ORCH-01, ORCH-02, ORCH-03, ORCH-04, ORCH-05, ORCH-06, ORCH-07, ORCH-08, ORCH-09, ORCH-10, ORCH-11, ORCH-12, ORCH-13, ORCH-14
**Success Criteria** (what must be TRUE):
  1. FastAPI orchestrator serves on port 8000 with campaign CRUD endpoints, system health check, and demographics listing
  2. Campaign data persists in SQLite with proper schema for campaigns and iterations
  3. Running a campaign via CLI produces: N content variants, neural scores for each variant, simulation metrics for top variants, 7 composite scores, and a Claude Opus cross-system analysis
  4. The cross-system analysis explicitly references both TRIBE neural scores and MiroFish simulation metrics in its reasoning
  5. The pipeline degrades gracefully when TRIBE or MiroFish is unavailable (runs with partial data and notes the gap)
**Plans**: 7 plans

Plans:
- [x] 05-01-PLAN.md -- Pydantic schemas + SQLite storage layer (ORCH-02, ORCH-03)
- [x] 05-02-PLAN.md -- HTTP clients for TRIBE v2 and MiroFish (ORCH-07)
- [x] 05-03-PLAN.md -- Variant generator + composite scorer (ORCH-08, ORCH-11)
- [x] 05-04-PLAN.md -- TRIBE scoring pipeline + MiroFish simulation runner (ORCH-09, ORCH-10)
- [x] 05-05-PLAN.md -- Result analyzer + campaign runner (ORCH-12, ORCH-13)
- [x] 05-06-PLAN.md -- FastAPI app + CRUD + health + demographics endpoints (ORCH-01, ORCH-04, ORCH-05, ORCH-06)
- [ ] 05-07-PLAN.md -- CLI entry point + end-to-end verification (ORCH-14)

### Phase 6: Optimization Loop
**Goal**: The system iterates on content variants, measurably improving scores across iterations, with automatic convergence detection and real-time progress streaming
**Depends on**: Phase 5
**Requirements**: OPT-01, OPT-02, OPT-03, OPT-04, OPT-05, OPT-06, OPT-07
**Success Criteria** (what must be TRUE):
  1. A multi-iteration campaign passes previous results to variant generation, producing improved variants each round
  2. The system stops early when all user-defined thresholds are met or when improvement is below 5% for 2 consecutive iterations
  3. SSE endpoint streams real-time progress events (iteration number, current step, ETA) during campaign execution
  4. Running a 3-iteration campaign demonstrates measurable score improvement between iteration 1 and the final iteration
**Plans**: TBD

### Phase 7: Report Generation
**Goal**: Campaign results are presented in a 4-layer report (verdict, scorecard, deep analysis, mass psychology) with JSON and Markdown export
**Depends on**: Phase 5
**Requirements**: RPT-01, RPT-02, RPT-03, RPT-04, RPT-05, RPT-06, RPT-07
**Success Criteria** (what must be TRUE):
  1. Layer 1 verdict is plain English (100-400 words, no jargon) with a clear recommendation
  2. Layer 2 scorecard contains composite scores, variant ranking, and iteration trajectory as structured JSON
  3. Layer 4 mass psychology includes both a general narrative (200-600 words) and a technical analysis referencing at least 2 named psychology theories
  4. Full campaign results can be downloaded as JSON and a Markdown summary can be exported
**Plans**: TBD

### Phase 8: UI Dashboard
**Goal**: Users interact with the full system through a React dashboard -- creating campaigns, watching real-time progress, viewing results across three tabs, and interviewing simulated agents
**Depends on**: Phase 5
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08, UI-09, UI-10, UI-11, UI-12, UI-13
**Success Criteria** (what must be TRUE):
  1. NewCampaign page accepts seed content, prediction question, demographic selection (6 presets + custom), configuration (agent count, iterations, thresholds), shows time estimate, and launches a campaign
  2. CampaignDetail page displays three tabs: Campaign (composite scores, variant ranking, iteration chart), Simulation (MiroFish metrics, sentiment timeline, agent grid), and Report (all 4 layers with expandable sections)
  3. Clicking an agent card opens an interview modal that proxies chat through the orchestrator to MiroFish
  4. ProgressStream component shows real-time SSE updates during campaign execution with step tracking and ETA
  5. CampaignList page shows all campaigns with status badges, and the UI handles loading, error, and empty states gracefully
**Plans**: TBD
**UI hint**: yes

### Phase 9: Validation and Documentation
**Goal**: The core hypothesis is proven -- iterative optimization produces measurably better content across diverse scenarios, with full documentation and a demo recording
**Depends on**: Phase 6, Phase 7, Phase 8
**Requirements**: VAL-01, VAL-02, VAL-03, VAL-04, VAL-05, VAL-06, VAL-07
**Success Criteria** (what must be TRUE):
  1. All 5 demo scenarios (product launch, PSA, price increase, policy, Gen Z) run end-to-end and produce complete reports
  2. Iteration improvement occurs in at least 4 out of 5 scenarios (later iterations score higher than earlier ones)
  3. Cross-system reasoning referencing both TRIBE and MiroFish appears in all 5 reports, and changing demographics meaningfully changes scores and simulation dynamics
  4. README with setup instructions and architecture overview exists, and a 5-10 minute demo video is recorded
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order with parallelization: 1 --> (2 | 3 | 4) --> 5 --> (6 | 7 | 8) --> 9.
Decimal phases (if inserted) execute between their surrounding integers.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Environment Setup | 0/? | Not started | - |
| 2. MiroFish-Offline Setup | 0/? | Not started | - |
| 3. TRIBE v2 Setup | 0/? | Not started | - |
| 4. Claude Client Setup | 0/? | Not started | - |
| 5. Orchestrator Integration Pipeline | 1/7 | Executing | - |
| 6. Optimization Loop | 0/? | Not started | - |
| 7. Report Generation | 0/? | Not started | - |
| 8. UI Dashboard | 0/? | Not started | - |
| 9. Validation and Documentation | 0/? | Not started | - |
