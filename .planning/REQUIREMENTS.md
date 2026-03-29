# Requirements: Nexus Sim

**Defined:** 2026-03-28
**Core Value:** Iterative feedback loop between neural scoring and social simulation produces measurably better content than single-pass generation

## v1 Requirements

Requirements for Phase 1 POC. Each maps to roadmap phases.

### Environment

- [ ] **ENV-01**: Docker Desktop running with GPU support (NVIDIA Container Toolkit)
- [ ] **ENV-02**: NVIDIA drivers + CUDA toolkit installed and verified
- [ ] **ENV-03**: Python 3.11+ with PyTorch CUDA support installed
- [ ] **ENV-04**: Node.js 18+ installed
- [ ] **ENV-05**: HuggingFace CLI installed with LLaMA 3.2-3B gated model access
- [ ] **ENV-06**: Anthropic API key verified working
- [ ] **ENV-07**: Monorepo directory structure created (orchestrator/, tribe_scorer/, mirofish/, ui/, shared/, docs/)
- [ ] **ENV-08**: Docker Compose with Neo4j, Ollama, LiteLLM services configured and healthy
- [ ] **ENV-09**: .env file configured with all service URLs and API keys

### MiroFish Integration

- [ ] **MIRO-01**: MiroFish-Offline forked and added as Git submodule
- [ ] **MIRO-02**: MiroFish backend running in Docker with Neo4j + Ollama + LiteLLM
- [ ] **MIRO-03**: Ollama has nomic-embed-text model pulled
- [ ] **MIRO-04**: LiteLLM proxy routes OpenAI-format calls to Claude Haiku
- [ ] **MIRO-05**: MiroFish graph build API accepts content and creates knowledge graph
- [ ] **MIRO-06**: MiroFish simulation runs with 20+ agents using Claude Haiku
- [ ] **MIRO-07**: MiroFish returns structured results with all 8 metrics (shares, sentiment, counter-narratives, virality, drift, coalitions, influence, divergence)
- [ ] **MIRO-08**: Agent chat API allows interviewing individual agents post-simulation

### TRIBE v2 Neural Scoring

- [ ] **TRIBE-01**: TRIBE v2 cloned with Python dependencies installed
- [ ] **TRIBE-02**: TRIBE v2 model weights downloaded from HuggingFace
- [ ] **TRIBE-03**: TRIBE v2 inference runs on local GPU (CUDA)
- [ ] **TRIBE-04**: FastAPI wrapper serves /api/score, /api/score/batch, /api/health endpoints
- [ ] **TRIBE-05**: ROI extractor maps voxel activations to 7 brain region groups using Glasser atlas
- [ ] **TRIBE-06**: Normalizer converts raw ROI activations to 0-100 scores
- [ ] **TRIBE-07**: Full scoring pipeline: text -> inference -> ROI extraction -> normalization -> 7 scores

### Claude Client

- [ ] **CLAUDE-01**: Anthropic SDK wrapper with separate Opus and Haiku methods
- [ ] **CLAUDE-02**: JSON-mode call support (call_opus_json)
- [ ] **CLAUDE-03**: Retry logic with exponential backoff for rate limits
- [ ] **CLAUDE-04**: Prompt template structure for variant generation, analysis, and reporting
- [ ] **CLAUDE-05**: 6 demographic preset configurations (tech, enterprise, consumer, policy, healthcare, Gen Z)
- [ ] **CLAUDE-06**: Cross-system analysis prompt that references both TRIBE scores and MiroFish metrics

### Orchestrator Pipeline

- [x] **ORCH-01**: FastAPI app with CORS for localhost:5173, lifespan hooks
- [x] **ORCH-02**: SQLite database with campaign and iteration tables
- [x] **ORCH-03**: Pydantic schemas for all request/response models
- [x] **ORCH-04**: Campaign CRUD endpoints (POST, GET, GET list, DELETE)
- [x] **ORCH-05**: System health endpoint pinging all downstream services
- [x] **ORCH-06**: Demographics endpoint returning preset list
- [x] **ORCH-07**: Async HTTP clients for TRIBE scorer and MiroFish
- [x] **ORCH-08**: Variant generator using Claude to create N content variants
- [x] **ORCH-09**: TRIBE scoring pipeline (orchestrator -> tribe_scorer -> composite scores)
- [x] **ORCH-10**: MiroFish simulation pipeline (orchestrator -> graph build -> simulation -> results)
- [x] **ORCH-11**: Composite score calculator implementing all 7 formulas from Results.md
- [x] **ORCH-12**: Result analyzer using Claude Opus for cross-system analysis
- [x] **ORCH-13**: Campaign runner wiring all components into single-iteration pipeline
- [x] **ORCH-14**: End-to-end CLI execution producing variants, scores, metrics, and analysis

### Optimization Loop

- [x] **OPT-01**: Multi-iteration support in campaign runner (pass previous results to variant generation)
- [x] **OPT-02**: Threshold checker comparing composite scores against user targets
- [x] **OPT-03**: Early stopping on threshold achievement or convergence (< 5% improvement for 2 iterations)
- [x] **OPT-04**: Time estimator with formula-based and runtime-refined estimates
- [x] **OPT-05**: POST /api/estimate endpoint
- [x] **OPT-06**: SSE progress streaming (iteration events, step tracking, ETA)
- [x] **OPT-07**: Optimization loop demonstrably improves scores across iterations

### Report Generation

- [x] **RPT-01**: Layer 1 Verdict — plain English recommendation (100-400 words, no jargon)
- [x] **RPT-02**: Layer 2 Scorecard — composite scores, variant ranking, iteration trajectory as structured JSON
- [x] **RPT-03**: Layer 3 Deep Analysis — all raw scores, metrics, reasoning chains, per-iteration data
- [x] **RPT-04**: Layer 4 Mass Psychology General — narrative prose about crowd dynamics (200-600 words)
- [x] **RPT-05**: Layer 4 Mass Psychology Technical — psychology theory references (>= 2 named theories)
- [x] **RPT-06**: JSON export of full campaign results
- [x] **RPT-07**: Markdown summary export

### UI Dashboard

- [x] **UI-01**: React + Vite + TypeScript + Tailwind scaffold with API client
- [x] **UI-02**: TypeScript types matching all Pydantic schemas
- [x] **UI-03**: Layout with sidebar (campaign history) and header
- [ ] **UI-04**: NewCampaign page: seed content input, prediction question, demographic selector (6 presets + custom), config panel (sliders, thresholds), time estimate, Run button
- [ ] **UI-05**: CampaignDetail page with 3 tabs (Campaign, Simulation, Report)
- [ ] **UI-06**: Campaign tab: composite score cards (color-coded), variant ranking, iteration chart
- [x] **UI-07**: Simulation tab: MiroFish metrics, sentiment timeline, coalition map, agent grid
- [x] **UI-08**: Agent interview: click agent card -> chat modal proxied through orchestrator
- [ ] **UI-09**: Report tab: verdict, scorecard, expandable deep analysis, mass psychology toggle
- [x] **UI-10**: ProgressStream component connected to SSE during campaign runs
- [x] **UI-11**: CampaignList page with status badges, click to open detail
- [ ] **UI-12**: JSON and Markdown export buttons on Report tab
- [x] **UI-13**: Loading states, error states, empty states, responsive layout

### Validation

- [ ] **VAL-01**: 5 demo scenario test briefs created (product launch, PSA, price increase, policy, Gen Z)
- [ ] **VAL-02**: All 5 scenarios run end-to-end with results recorded
- [ ] **VAL-03**: Iteration improvement in >= 4/5 scenarios
- [ ] **VAL-04**: Cross-system reasoning (TRIBE + MiroFish) appears in all reports
- [ ] **VAL-05**: Demographic changes meaningfully affect scores/dynamics
- [ ] **VAL-06**: README.md with setup instructions and architecture overview
- [ ] **VAL-07**: Demo video recorded (5-10 minutes)

## v2 Requirements

Deferred to Phase 2. Tracked but not in current roadmap.

### Security & Multi-User

- **SEC-01**: User authentication and session management
- **SEC-02**: HTTPS/TLS for all endpoints
- **SEC-03**: Input sanitization beyond Pydantic validation
- **SEC-04**: Multi-user campaign isolation

### Extended Capabilities

- **EXT-01**: Video/audio stimulus support for TRIBE v2
- **EXT-02**: PostgreSQL migration for concurrent access
- **EXT-03**: OAuth login (Google, GitHub)
- **EXT-04**: Cloud deployment with Docker GPU passthrough

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time chat | High complexity, not core to optimization value |
| Mobile app | Web-first, mobile deferred to Phase 2+ |
| Microservices infra (gRPC, queues, mesh) | Overkill for single-machine POC |
| Multi-language content | English-only for Phase 1, TRIBE v2 is English-trained |
| A/B testing integration | Phase 1 is prediction, not live testing |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENV-01 | Phase 1 | Pending |
| ENV-02 | Phase 1 | Pending |
| ENV-03 | Phase 1 | Pending |
| ENV-04 | Phase 1 | Pending |
| ENV-05 | Phase 1 | Pending |
| ENV-06 | Phase 1 | Pending |
| ENV-07 | Phase 1 | Pending |
| ENV-08 | Phase 1 | Pending |
| ENV-09 | Phase 1 | Pending |
| MIRO-01 | Phase 2 | Pending |
| MIRO-02 | Phase 2 | Pending |
| MIRO-03 | Phase 2 | Pending |
| MIRO-04 | Phase 2 | Pending |
| MIRO-05 | Phase 2 | Pending |
| MIRO-06 | Phase 2 | Pending |
| MIRO-07 | Phase 2 | Pending |
| MIRO-08 | Phase 2 | Pending |
| TRIBE-01 | Phase 3 | Pending |
| TRIBE-02 | Phase 3 | Pending |
| TRIBE-03 | Phase 3 | Pending |
| TRIBE-04 | Phase 3 | Pending |
| TRIBE-05 | Phase 3 | Pending |
| TRIBE-06 | Phase 3 | Pending |
| TRIBE-07 | Phase 3 | Pending |
| CLAUDE-01 | Phase 4 | Pending |
| CLAUDE-02 | Phase 4 | Pending |
| CLAUDE-03 | Phase 4 | Pending |
| CLAUDE-04 | Phase 4 | Pending |
| CLAUDE-05 | Phase 4 | Pending |
| CLAUDE-06 | Phase 4 | Pending |
| ORCH-01 | Phase 5 | Complete |
| ORCH-02 | Phase 5 | Complete |
| ORCH-03 | Phase 5 | Complete |
| ORCH-04 | Phase 5 | Complete |
| ORCH-05 | Phase 5 | Complete |
| ORCH-06 | Phase 5 | Complete |
| ORCH-07 | Phase 5 | Complete |
| ORCH-08 | Phase 5 | Complete |
| ORCH-09 | Phase 5 | Complete |
| ORCH-10 | Phase 5 | Complete |
| ORCH-11 | Phase 5 | Complete |
| ORCH-12 | Phase 5 | Complete |
| ORCH-13 | Phase 5 | Complete |
| ORCH-14 | Phase 5 | Complete |
| OPT-01 | Phase 6 | Complete |
| OPT-02 | Phase 6 | Complete |
| OPT-03 | Phase 6 | Complete |
| OPT-04 | Phase 6 | Complete |
| OPT-05 | Phase 6 | Complete |
| OPT-06 | Phase 6 | Complete |
| OPT-07 | Phase 6 | Complete |
| RPT-01 | Phase 7 | Complete |
| RPT-02 | Phase 7 | Complete |
| RPT-03 | Phase 7 | Complete |
| RPT-04 | Phase 7 | Complete |
| RPT-05 | Phase 7 | Complete |
| RPT-06 | Phase 7 | Complete |
| RPT-07 | Phase 7 | Complete |
| UI-01 | Phase 8 | Complete |
| UI-02 | Phase 8 | Complete |
| UI-03 | Phase 8 | Complete |
| UI-04 | Phase 8 | Pending |
| UI-05 | Phase 8 | Pending |
| UI-06 | Phase 8 | Pending |
| UI-07 | Phase 8 | Complete |
| UI-08 | Phase 8 | Complete |
| UI-09 | Phase 8 | Pending |
| UI-10 | Phase 8 | Complete |
| UI-11 | Phase 8 | Complete |
| UI-12 | Phase 8 | Pending |
| UI-13 | Phase 8 | Complete |
| VAL-01 | Phase 9 | Pending |
| VAL-02 | Phase 9 | Pending |
| VAL-03 | Phase 9 | Pending |
| VAL-04 | Phase 9 | Pending |
| VAL-05 | Phase 9 | Pending |
| VAL-06 | Phase 9 | Pending |
| VAL-07 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 78 total
- Mapped to phases: 78
- Unmapped: 0

**Phase Summary:**
| Phase | Category | Count |
|-------|----------|-------|
| Phase 1 | Environment (ENV) | 9 |
| Phase 2 | MiroFish Integration (MIRO) | 8 |
| Phase 3 | TRIBE v2 Neural Scoring (TRIBE) | 7 |
| Phase 4 | Claude Client (CLAUDE) | 6 |
| Phase 5 | Orchestrator Pipeline (ORCH) | 14 |
| Phase 6 | Optimization Loop (OPT) | 7 |
| Phase 7 | Report Generation (RPT) | 7 |
| Phase 8 | UI Dashboard (UI) | 13 |
| Phase 9 | Validation (VAL) | 7 |
| **Total** | | **78** |

---
*Requirements defined: 2026-03-28*
*Last updated: 2026-03-28 after roadmap creation*
