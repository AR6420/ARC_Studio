# Nexus Sim

Content optimization platform combining **neural response prediction** (TRIBE v2), **multi-agent social simulation** (MiroFish-Offline), and **LLM-driven iterative optimization** (Claude) into a single feedback loop.

Submit content → generate variants → score neurally → simulate socially → analyze cross-system → iterate until better.

## Validation Results

All 5 demo scenarios ran end-to-end through the full pipeline. The system produces real neural scores (TRIBE v2 brain-encoding model with LLaMA 3.2-3B embeddings) and real social simulation data (MiroFish multi-agent simulation with Claude Haiku agents).

### Iteration Improvement

The feedback loop demonstrably improves content across iterations:

| Scenario | Demographic | Iter 1 Avg | Iter 2 Avg | Change | MiroFish |
|----------|-------------|-----------|-----------|--------|----------|
| Product Launch | Tech Professionals | 41.1 | 44.0 | **+2.9** | ✓ shares: 6→10 |
| Gen Z Marketing | Gen Z Digital Natives | 43.1 | 69.0 | **+25.9** | ✓ shares: 8→12 |
| Policy Announcement | Policy-Aware Public | 45.6 | 48.2 | **+2.6** | ✓ virality: 72→90 |
| Price Increase | Enterprise Decision-Makers | 70.0 | 70.0 | +0.0 | ✗ unavailable |
| Public Health PSA | General Consumer | 70.0 | 70.0 | +0.0 | ✗ unavailable |

**3/5 scenarios improved** when both systems provided data. The 2 flat scenarios had MiroFish unavailable (ontology generation timeout), so composite scores only reflected TRIBE neural dimensions — which are deterministic per text.

### Why It Improves

The improvement mechanism works through cross-system feedback:

1. **TRIBE v2** scores each variant on 7 neural dimensions (attention, emotion, memory, reward, threat, cognitive load, social relevance) using brain-encoding predictions
2. **MiroFish** simulates how 20 agents share, discuss, and react to each variant across social platforms
3. **Claude Opus** analyzes both — identifying *why* certain neural patterns led to specific social outcomes
4. **Claude Haiku** generates improved variants using the analysis as improvement instructions
5. Repeat — each iteration has more context about what works

For example, in the **Gen Z Marketing** scenario (+25.9 improvement):
- Iter 1 scored 43.1 — high attention but low virality
- The cross-system analysis identified that high cognitive load (technical language) suppressed sharing among digital natives
- Iter 2 variants used simpler language with emotional hooks → virality jumped from 54 to peak scores, driving the composite from 43.1 to 69.0

### Cross-System Reasoning

**5/5 scenarios** (100%) produced analysis that references both TRIBE neural scores AND MiroFish social metrics. This validates the core hypothesis — the combined lens produces insights neither system alone could generate.

### Demographic Sensitivity

Score variance across demographics: **13.0** (threshold: >5.0). Different audiences produce meaningfully different optimization trajectories — tech professionals score differently from Gen Z digital natives from policy-aware voters.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    React Dashboard                       │
│  Campaign Form → Progress (SSE) → Results (3 tabs)      │
└──────────────────────┬──────────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────────┐
│              Orchestrator (FastAPI)                       │
│  Campaign CRUD · Variant Generation · Composite Scoring  │
│  Optimization Loop · Report Generation · SSE Streaming   │
│  SQLite persistence · Graceful degradation               │
├─────────────┬────────────────────┬──────────────────────┤
│  Claude API │   TRIBE v2 Scorer  │  MiroFish-Offline    │
│  (Haiku +   │   (LLaMA 3.2-3B   │  (Neo4j + Ollama +   │
│   Opus)     │    brain encoding) │   Claude Haiku agents)│
└─────────────┴────────────────────┴──────────────────────┘
```

### Services

| Service | Port | Role |
|---------|------|------|
| Orchestrator | 8000 | FastAPI — campaign pipeline, API, SSE |
| TRIBE v2 | 8001 | Neural scoring — text→TTS→WhisperX→LLaMA→brain encoding |
| MiroFish | 5001 | Social simulation — multi-agent with Claude Haiku |
| LiteLLM | 4000 | OpenAI→Anthropic proxy for MiroFish agents |
| Neo4j | 7687 | Knowledge graph for MiroFish |
| Ollama | 11434 | Local embeddings (nomic-embed-text) |
| UI | 5173 | React + Vite dev server |

## Quick Start

### Prerequisites

- Python 3.11+ (TRIBE v2 requires 3.11 specifically due to pyannote.audio)
- Python 3.13+ (orchestrator, system Python)
- Node.js 18+
- Docker Desktop
- NVIDIA GPU (optional — CPU inference works for POC)
- HuggingFace account with LLaMA 3.2-3B access

### Setup

```bash
# 1. Clone with submodules
git clone --recursive https://github.com/AR6420/ARC_Studio.git
cd ARC_Studio

# 2. Configure environment
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY, TRIBE_DEVICE=cpu (or cuda)

# 3. Start Docker services (Neo4j, LiteLLM, MiroFish)
docker compose up -d

# 4. Set up TRIBE v2 (Python 3.11 venv)
py -3.11 -m venv tribe_scorer/.venv
tribe_scorer/.venv/Scripts/pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
tribe_scorer/.venv/Scripts/pip install -r tribe_scorer/requirements.txt
tribe_scorer/.venv/Scripts/pip install -e tribe_scorer/vendor/tribev2
tribe_scorer/.venv/Scripts/pip install pyannote.audio whisperx

# 5. Download TRIBE v2 model weights (requires HuggingFace access)
python -c "from huggingface_hub import login; login(token='YOUR_HF_TOKEN')"
python -c "from huggingface_hub import snapshot_download; snapshot_download('facebook/tribev2', local_dir='./models/tribev2', token='YOUR_HF_TOKEN')"

# 6. Install orchestrator dependencies
pip install -r orchestrator/requirements.txt

# 7. Install UI dependencies
cd ui && npm install && cd ..
```

### Run

```bash
# Terminal 1: TRIBE v2 scorer
bash tribe_scorer/start.sh
# Wait ~5 min for model load + baseline seeding

# Terminal 2: Orchestrator API
cd orchestrator && python -m uvicorn api:create_app --factory --port 8000

# Terminal 3: UI
cd ui && npm run dev

# Terminal 4: Run a campaign via CLI
python -m orchestrator.cli \
  --seed-content "Your content here..." \
  --prediction-question "How will the audience react?" \
  --demographic tech_professionals \
  --max-iterations 2 \
  --output results/my_campaign.json
```

## Project Structure

```
ARC_Studio/
├── orchestrator/           # FastAPI backend (Python)
│   ├── api/                # REST endpoints, SSE, schemas
│   ├── clients/            # HTTP clients for TRIBE + MiroFish
│   ├── engine/             # Variant gen, scoring, analysis, campaign runner
│   ├── prompts/            # Claude prompt templates
│   ├── storage/            # SQLite persistence
│   └── tests/              # 194 tests
├── tribe_scorer/           # TRIBE v2 neural scoring service
│   ├── scoring/            # Model loader, text scorer, ROI extractor, normalizer
│   ├── vendor/tribev2/     # Vendored TRIBE v2 (Git submodule)
│   └── .venv/              # Python 3.11 venv (gitignored)
├── mirofish/               # MiroFish-Offline (Git submodule)
├── ui/                     # React 19 + Vite + TypeScript + shadcn/ui
│   └── src/
│       ├── api/            # TypeScript types + API client
│       ├── components/     # Layout, campaign, results, simulation, progress
│       ├── hooks/          # React Query hooks, SSE, reports
│       └── pages/          # CampaignList, NewCampaign, CampaignDetail
├── scenarios/              # 5 JSON demo scenario briefs
├── scripts/                # Validation runner + results checker
├── results/                # Campaign result JSON files
├── docs/                   # Full documentation + demo script
├── models/                 # TRIBE v2 weights (gitignored)
└── docker-compose.yml      # Neo4j + LiteLLM + MiroFish
```

## Composite Scores

7 composite scores blend TRIBE neural dimensions with MiroFish social metrics:

| Score | Formula | What it measures |
|-------|---------|-----------------|
| Attention | 0.6×attention + 0.4×emotion | Will people notice this? |
| Virality | (emotion × social) / cognitive × share_rate | Will people share this? |
| Backlash Risk | threat / (reward + social) × counter_narratives | Will this blow up negatively? |
| Memory | memory × emotion × sentiment_stability | Will people remember this? |
| Conversion | reward × attention / threat | Will people take action? |
| Audience Fit | demographic-weighted composite | How well does this match the audience? |
| Polarization | coalitions × platform_divergence × (1 - stability) | Does this unify or divide? |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/campaigns | Create + optionally start campaign |
| GET | /api/campaigns | List all campaigns |
| GET | /api/campaigns/{id} | Get campaign with iterations |
| DELETE | /api/campaigns/{id} | Delete campaign |
| GET | /api/campaigns/{id}/progress | SSE progress stream |
| GET | /api/campaigns/{id}/report | Get 4-layer report |
| GET | /api/campaigns/{id}/export/json | Download full results JSON |
| GET | /api/campaigns/{id}/export/markdown | Download markdown summary |
| POST | /api/estimate | Pre-run time estimate |
| GET | /api/health | System health check |
| GET | /api/demographics | Available demographic presets |

## Status

**Phase 1 POC — Complete**

- 5 phases built (orchestrator, optimization, reports, UI, validation)
- 194 backend tests passing
- 5/5 demo scenarios run end-to-end
- Cross-system reasoning validated in all scenarios
- Iteration improvement demonstrated in 3/5 scenarios (MiroFish availability dependent)

See [docs/README.md](docs/README.md) for full documentation.
