# Application_Technical_Spec.md — System architecture and technical design

## Project: Nexus Sim (Phase 1 POC)
## Architecture: Modular monorepo with Docker service boundaries
## Language: Python (backend), TypeScript (frontend)

---

## 1. Architecture overview

### 1.1 Architecture style
Modular monorepo. NOT microservices (too much infra overhead for a single developer). NOT a monolith (components have fundamentally different runtime requirements). Each module runs as a separate process/container but lives in one Git repo, shares one docker-compose.yml, and deploys together.

### 1.2 System diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  nexus-sim/ (Git repo root)                                    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  ui/ — React + Vite + TypeScript                        │   │
│  │  Port 5173 (dev) → talks ONLY to orchestrator           │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │ HTTP (REST)                           │
│  ┌──────────────────────▼───────────────────────────────────┐   │
│  │  orchestrator/ — FastAPI (Python 3.11+)                  │   │
│  │  Port 8000                                               │   │
│  │  • Campaign runner (engine/campaign_runner.py)           │   │
│  │  • Variant generator (engine/variant_generator.py)       │   │
│  │  • Result analyzer (engine/result_analyzer.py)           │   │
│  │  • Report builder (engine/report_builder.py)             │   │
│  │  • Claude API client (clients/claude_client.py)          │   │
│  │  • MiroFish client (clients/mirofish_client.py)          │   │
│  │  • TRIBE scorer client (clients/tribe_client.py)         │   │
│  └────────┬─────────────────────────────────┬───────────────┘   │
│           │ HTTP                             │ HTTP              │
│  ┌────────▼──────────┐          ┌───────────▼───────────────┐   │
│  │  mirofish/        │          │  tribe_scorer/            │   │
│  │  (Git submodule)  │          │  FastAPI + PyTorch        │   │
│  │  Flask, Port 5000 │          │  Port 8001                │   │
│  │  • Agent sim      │          │  • TRIBE v2 inference     │   │
│  │  • Graph builder  │          │  • Neural scoring         │   │
│  │  • Report agent   │          │  • ROI extraction         │   │
│  │  • Agent chat     │          │  • Local GPU (CUDA)       │   │
│  └──┬─────┬──────────┘          └───────────────────────────┘   │
│     │     │                                                     │
│  ┌──▼──┐ ┌▼────────┐ ┌──────────┐                              │
│  │Neo4j│ │LiteLLM  │ │Ollama    │                              │
│  │7687 │ │4000     │ │11434     │                              │
│  │Graph│ │API proxy │ │Embeddings│                              │
│  └─────┘ └─────────┘ └──────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Communication pattern
All inter-service communication is REST (HTTP/JSON) over localhost. No gRPC. No message queues. No service mesh. At POC scale with all services on one machine, HTTP overhead is negligible and debuggability is maximized.

### 1.4 Data flow for a campaign run

```
1. User submits campaign brief via UI
   → POST /api/campaigns (orchestrator)

2. Orchestrator calls Claude Opus to generate N content variants
   → Claude API (Haiku or Opus based on task)

3. Orchestrator sends each variant to TRIBE v2 for neural scoring
   → POST /api/score (tribe_scorer)
   ← Returns 7 neural dimension scores per variant

4. Orchestrator ranks variants by neural scores, selects top K

5. Orchestrator sends top K variants to MiroFish for social simulation
   → POST /api/simulation/run (mirofish)
   ← Returns simulation metrics per variant

6. Orchestrator calls Claude Opus to analyze combined results
   → Claude API (Opus)
   ← Returns analysis, reasoning chain, recommendations

7. Orchestrator checks if thresholds are met
   → If YES or max iterations reached: proceed to step 8
   → If NO: Opus generates improved variants, return to step 3

8. Orchestrator calls Claude Opus to generate final report (all 4 layers)
   → Claude API (Opus)
   ← Returns verdict, scorecard data, deep analysis, mass psychology

9. Orchestrator saves results and returns to UI
   → Campaign results stored in local SQLite
   → UI renders report with all layers
```

---

## 2. Module specifications

### 2.1 orchestrator/ — The brain

**Technology:** FastAPI, Python 3.11+, httpx (async HTTP client), Pydantic v2, SQLite (campaign storage)

**Why FastAPI:** Async support for concurrent API calls (scoring + simulation can run in parallel for different variants). Pydantic for strict schema validation. Auto-generated OpenAPI docs for debugging. Claude Code works exceptionally well with FastAPI codebases.

**Directory structure:**
```
orchestrator/
├── main.py                    # FastAPI app factory, CORS, lifespan
├── config.py                  # Environment config (Pydantic BaseSettings)
├── api/
│   ├── campaigns.py           # POST /api/campaigns, GET /api/campaigns/{id}
│   ├── status.py              # GET /api/status (system health)
│   └── schemas.py             # All Pydantic request/response models
├── engine/
│   ├── campaign_runner.py     # Main orchestration loop
│   ├── variant_generator.py   # Opus prompt for generating content variants
│   ├── tribe_scorer.py        # Calls tribe_scorer service, processes results
│   ├── mirofish_runner.py     # Calls MiroFish API, processes simulation results
│   ├── result_analyzer.py     # Opus prompt for cross-system analysis
│   ├── report_builder.py      # Opus prompt for generating all 4 output layers
│   ├── composite_scorer.py    # Computes composite scores from raw metrics
│   ├── threshold_checker.py   # Checks if user's threshold targets are met
│   └── time_estimator.py      # Estimates campaign run duration
├── clients/
│   ├── claude_client.py       # Anthropic SDK wrapper (supports Opus + Haiku)
│   ├── tribe_client.py        # HTTP client for tribe_scorer service
│   └── mirofish_client.py     # HTTP client for MiroFish Flask API
├── storage/
│   ├── database.py            # SQLite connection, migrations
│   └── models.py              # Campaign, Iteration, Variant ORM models
├── prompts/
│   ├── variant_generation.py  # System prompt + user prompt templates
│   ├── result_analysis.py     # Analysis prompt templates
│   ├── report_verdict.py      # Layer 1 verdict prompt
│   ├── report_psychology.py   # Layer 4 mass psychology prompts (general + technical)
│   └── demographic_profiles.py # Demographic preset configurations
├── Dockerfile
└── requirements.txt
```

**Key API endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/campaigns | Create and start a new campaign run |
| GET | /api/campaigns/{id} | Get campaign results (status, iterations, report) |
| GET | /api/campaigns/{id}/stream | SSE stream of real-time progress updates |
| GET | /api/campaigns | List all campaigns (paginated) |
| DELETE | /api/campaigns/{id} | Delete a campaign and its data |
| GET | /api/status | System health (checks all downstream services) |
| GET | /api/demographics | List available demographic presets |
| POST | /api/estimate | Return time estimate for a given configuration |

**Campaign request schema (Pydantic):**
```python
class CampaignCreate(BaseModel):
    seed_content: str                          # 100-5000 words
    prediction_question: str                   # What the user wants to know
    demographic: str                           # Preset key or "custom"
    demographic_custom: str | None = None      # Free-text if demographic == "custom"
    agent_count: int = 40                      # 20-200, step 10
    max_iterations: int = 4                    # 1-10
    thresholds: dict[str, float] | None = None # Optional threshold targets
    constraints: str | None = None             # Brand guidelines
    baseline_content: str | None = None        # Comparison baseline
    existing_variants: list[str] | None = None # Pre-made variants to test
```

**Campaign response schema:**
```python
class CampaignResponse(BaseModel):
    campaign_id: str
    status: str                    # "queued" | "running" | "completed" | "failed"
    config: CampaignConfig
    current_iteration: int
    total_iterations: int
    thresholds_met: bool | None
    iterations: list[IterationResult]
    final_report: FinalReport | None
    started_at: str
    completed_at: str | None
    duration_seconds: float | None
```

### 2.2 tribe_scorer/ — Neural scoring service

**Technology:** FastAPI, PyTorch, TRIBE v2 model weights, CUDA

**Why separate service:** TRIBE v2 needs exclusive GPU access. Running it in the same process as the orchestrator would conflict with MiroFish's Ollama embeddings. Separate process = clean GPU resource isolation.

**Why NOT in Docker:** TRIBE v2 needs direct CUDA access. While Docker can do GPU passthrough via NVIDIA Container Toolkit, for a POC on a single machine, running natively avoids an extra layer of GPU driver complexity. Docker is for the services that don't need GPU (Neo4j, LiteLLM, Ollama, MiroFish backend).

**Directory structure:**
```
tribe_scorer/
├── main.py                    # FastAPI app, model loading on startup
├── config.py                  # Model paths, device config
├── scoring/
│   ├── model_loader.py        # Load TRIBE v2 weights, initialize encoders
│   ├── text_scorer.py         # Text stimulus → fMRI prediction → ROI scores
│   ├── roi_extractor.py       # Extract region-of-interest activation values
│   └── normalizer.py          # Raw fMRI values → 0-100 normalized scores
├── Dockerfile                 # Optional, for future cloud deployment
└── requirements.txt
```

**Key API endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/score | Score a text stimulus, return 7 neural dimensions |
| POST | /api/score/batch | Score multiple texts in one call |
| GET | /api/health | Check model loaded, GPU available |

**Score request/response:**
```python
# Request
class ScoreRequest(BaseModel):
    text: str                    # The content to score
    subject_type: str = "group"  # "group" (averaged) or "individual"

# Response
class ScoreResponse(BaseModel):
    attention_capture: float     # 0-100
    emotional_resonance: float   # 0-100
    memory_encoding: float       # 0-100
    reward_response: float       # 0-100
    threat_detection: float      # 0-100
    cognitive_load: float        # 0-100
    social_relevance: float      # 0-100
    raw_voxels: dict | None      # Optional: full voxel map for deep analysis
    inference_time_ms: float
```

**TRIBE v2 ROI mapping (how raw fMRI → actionable scores):**

TRIBE v2 outputs ~70,000 voxel activations across the cortical surface. The ROI extractor maps these to brain regions using standard neuroimaging atlases (Glasser HCP-MMP1.0 or Destrieux). Each of the 7 scoring dimensions corresponds to specific ROI parcels:

- Attention capture: V1, V2, V3, V4, FEF, IPS
- Emotional resonance: Amygdala (bilateral), anterior insula, ACC (area 24)
- Memory encoding: Hippocampus (bilateral), parahippocampal gyrus, entorhinal cortex
- Reward response: Nucleus accumbens, ventral tegmental area, OFC (area 11)
- Threat detection: Amygdala (basolateral nucleus), periaqueductal gray
- Cognitive load: DLPFC (areas 9, 46), anterior PFC (area 10)
- Social relevance: TPJ (bilateral), mPFC (area 32), pSTS

Each ROI's activation is averaged, then normalized to 0-100 using percentile ranking against a baseline distribution (derived from TRIBE v2's training data responses to diverse stimuli).

### 2.3 mirofish/ — Social simulation (fork)

**Technology:** Flask (their code), Neo4j, Ollama (embeddings), LiteLLM → Claude Haiku (agent LLM)

**This is a Git submodule.** We fork MiroFish-Offline, make minimal modifications, and include it as a submodule. This keeps our changes isolated and makes upstream merges possible.

**Modifications to MiroFish-Offline for Nexus Sim:**

1. **LLM endpoint:** Change `.env` to point at LiteLLM proxy (port 4000) instead of local Ollama for the main LLM. Embeddings stay on local Ollama.

2. **Agent persona enhancement:** Add a `cognitive_profile` field to agent persona generation. This field contains TRIBE v2-derived cognitive weights that influence how the agent processes information (e.g., an agent with high threat_sensitivity is more likely to react negatively to fear-based framing).

3. **API additions:** Add two new Flask routes:
   - `POST /api/simulation/run-headless` — Starts a simulation without requiring the Vue frontend. Accepts seed content, agent count, simulation cycles, and agent persona config as JSON. Returns a simulation ID.
   - `GET /api/simulation/{id}/results` — Returns structured simulation results (all 8 metrics from Results.md) as JSON.

4. **Output standardization:** Ensure simulation results include all 8 metrics defined in Results.md in a consistent JSON schema.

**Existing MiroFish API we use (no modifications needed):**
- `POST /api/graph/build` — Build knowledge graph from seed content
- `POST /api/simulation/run` — Run simulation
- `GET /api/simulation/{id}/status` — Check simulation status
- `POST /api/agent/{id}/chat` — Interview a specific agent
- `POST /api/report/generate` — Generate ReportAgent analysis

### 2.4 ui/ — React dashboard

**Technology:** React 18, Vite, TypeScript, Tailwind CSS, Recharts (charts), React Query (data fetching)

**Why React + Vite:** Fast development cycle (HMR), TypeScript for type safety with API schemas, Tailwind for rapid UI styling without custom CSS files, Recharts for the optimization trajectory charts. Claude Code generates excellent React + TypeScript code.

**Directory structure:**
```
ui/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   ├── client.ts              # Axios/fetch wrapper
│   │   ├── campaigns.ts           # Campaign API calls
│   │   └── types.ts               # TypeScript types matching Pydantic schemas
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   └── Layout.tsx
│   │   ├── campaign/
│   │   │   ├── CampaignForm.tsx       # Brief input, config sliders, demographic selector
│   │   │   ├── ConfigPanel.tsx        # Agent count, iterations, thresholds
│   │   │   ├── DemographicSelector.tsx # Preset cards + custom text input
│   │   │   ├── TimeEstimate.tsx       # Live time estimate display
│   │   │   └── ThresholdConfig.tsx    # Threshold toggle + input per metric
│   │   ├── results/
│   │   │   ├── Verdict.tsx            # Layer 1: plain English verdict
│   │   │   ├── Scorecard.tsx          # Layer 2: visual scores + ranking
│   │   │   ├── DeepAnalysis.tsx       # Layer 3: full data breakdown
│   │   │   ├── MassPsychology.tsx     # Layer 4: general/technical toggle
│   │   │   ├── VariantRanking.tsx     # Ranked variant list with score bars
│   │   │   ├── IterationChart.tsx     # Line chart: scores across iterations
│   │   │   └── CompositeScoreCard.tsx # Single score display component
│   │   ├── simulation/
│   │   │   ├── SimulationView.tsx     # Simulation metrics dashboard
│   │   │   ├── AgentGrid.tsx          # Clickable agent cards
│   │   │   ├── AgentChat.tsx          # Interview an agent (proxies to MiroFish)
│   │   │   ├── SentimentTimeline.tsx  # Sentiment trajectory chart
│   │   │   └── CoalitionMap.tsx       # Coalition formation visualization
│   │   └── common/
│   │       ├── ScoreBar.tsx           # Horizontal score bar with color
│   │       ├── StatusBadge.tsx        # Running/completed/failed pill
│   │       ├── LoadingState.tsx       # Skeleton/spinner
│   │       └── ProgressStream.tsx     # Real-time progress from SSE
│   ├── pages/
│   │   ├── NewCampaign.tsx        # Campaign creation page
│   │   ├── CampaignDetail.tsx     # Results page (tabs: Campaign/Simulation/Report)
│   │   └── CampaignList.tsx       # History of all campaign runs
│   ├── hooks/
│   │   ├── useCampaign.ts         # React Query hook for campaign data
│   │   ├── useProgress.ts         # SSE hook for real-time progress
│   │   └── useTimeEstimate.ts     # Debounced time estimate calculator
│   └── utils/
│       ├── colors.ts              # Score → color mapping (green/amber/red)
│       └── formatters.ts          # Number formatting, duration formatting
└── Dockerfile
```

**Three main views (tab navigation on CampaignDetail page):**

1. **Campaign tab** — Variant ranking, composite scores, iteration improvement chart, configuration summary.
2. **Simulation tab** — MiroFish simulation metrics, sentiment timeline, agent grid with interview capability, coalition visualization.
3. **Report tab** — All 4 output layers (verdict, scorecard, deep analysis, mass psychology with toggle).

**UI interaction model:**
- User interacts ONLY with the orchestrator API. Never calls MiroFish or TRIBE v2 directly.
- Agent interview (clicking an agent card in Simulation tab) proxies through orchestrator → MiroFish agent chat API.
- Real-time progress during campaign run uses Server-Sent Events (SSE) from orchestrator.

### 2.5 Infrastructure services

#### Neo4j (Docker)
```yaml
neo4j:
  image: neo4j:5.15-community
  ports:
    - "7474:7474"  # Browser
    - "7687:7687"  # Bolt
  environment:
    NEO4J_AUTH: neo4j/mirofish
  volumes:
    - neo4j_data:/data
```

#### LiteLLM (Docker)
Translates OpenAI-compatible API format (which MiroFish expects) into Anthropic API format.
```yaml
litellm:
  image: ghcr.io/berriai/litellm:main-latest
  ports:
    - "4000:4000"
  environment:
    ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
  command: --model anthropic/claude-haiku-4-5-20251001 --port 4000
```

#### Ollama (Docker)
For local embeddings ONLY. Not used for LLM inference (that goes through LiteLLM → Claude).
```yaml
ollama:
  image: ollama/ollama
  ports:
    - "11434:11434"
  volumes:
    - ollama_data:/root/.ollama
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

**Note on GPU sharing:** Ollama for embeddings uses minimal VRAM (~1GB for nomic-embed-text). TRIBE v2 uses ~8-10GB. Since Ollama embeddings are small and intermittent, they can share the GPU with TRIBE v2 without conflict. If there are VRAM issues, Ollama can fall back to CPU mode for embeddings (slower but functional).

---

## 3. Data schemas

### 3.1 Campaign storage (SQLite)

```sql
CREATE TABLE campaigns (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued',  -- queued | running | completed | failed
    seed_content TEXT NOT NULL,
    prediction_question TEXT NOT NULL,
    demographic TEXT NOT NULL,
    demographic_custom TEXT,
    agent_count INTEGER NOT NULL DEFAULT 40,
    max_iterations INTEGER NOT NULL DEFAULT 4,
    actual_iterations INTEGER DEFAULT 0,
    thresholds TEXT,           -- JSON string
    thresholds_met INTEGER,    -- 0 or 1
    constraints TEXT,
    baseline_content TEXT,
    existing_variants TEXT,    -- JSON string
    final_report TEXT,         -- JSON string (all 4 layers)
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    duration_seconds REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE iterations (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id),
    iteration_number INTEGER NOT NULL,
    variants TEXT NOT NULL,     -- JSON string (array of variant objects)
    opus_analysis TEXT,         -- Claude Opus reasoning for this iteration
    best_composite_score REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 3.2 Inter-service message schemas

**Orchestrator → TRIBE scorer:**
```json
{
  "texts": [
    "Announcing NexaVault: enterprise cloud storage...",
    "Your data, your rules. NexaVault brings zero-knowledge..."
  ]
}
```

**TRIBE scorer → Orchestrator:**
```json
{
  "scores": [
    {
      "text_index": 0,
      "attention_capture": 72.3,
      "emotional_resonance": 65.1,
      "memory_encoding": 58.7,
      "reward_response": 70.2,
      "threat_detection": 15.4,
      "cognitive_load": 42.0,
      "social_relevance": 68.9,
      "inference_time_ms": 1240
    }
  ]
}
```

**Orchestrator → MiroFish:**
```json
{
  "content": "Announcing NexaVault: enterprise cloud storage...",
  "title": "NexaVault Launch",
  "source_type": "product_announcement",
  "agent_count": 40,
  "simulation_hours": 12,
  "platform": "both",
  "agent_config": {
    "demographic": "tech_professionals",
    "cognitive_profiles": [
      { "agent_id": "cto_01", "threat_sensitivity": 0.3, "reward_sensitivity": 0.7 }
    ]
  }
}
```

**MiroFish → Orchestrator:**
```json
{
  "sim_id": "s_xyz789",
  "status": "completed",
  "metrics": {
    "organic_shares": 187,
    "sentiment_trajectory": [0.2, 0.3, 0.45, 0.52, 0.61],
    "counter_narrative_count": 2,
    "peak_virality_cycle": 14,
    "sentiment_drift": 18.5,
    "coalition_formation": {
      "groups": [
        { "name": "early_adopters", "size": 12, "stability": 0.9 },
        { "name": "privacy_skeptics", "size": 5, "stability": 0.7 }
      ]
    },
    "influence_concentration": 34.2,
    "platform_divergence": 22.1
  }
}
```

---

## 4. Claude API usage strategy

### 4.1 Model selection per task

| Task | Model | Reasoning |
|------|-------|-----------|
| Variant generation | Claude Haiku | Fast, cheap. Generating content variants doesn't require deep reasoning. |
| MiroFish agent LLM (via LiteLLM) | Claude Haiku | Agents need to be fast and numerous. Haiku handles persona simulation well. |
| Cross-system analysis | Claude Opus | This is the core reasoning task. Needs to bridge neural + social data. |
| Report generation (verdict, psychology) | Claude Opus | Quality writing and nuanced analysis require Opus. |
| Demographic → agent config translation | Claude Haiku | Structured output task, doesn't need Opus reasoning. |

### 4.2 API credential approach

For Phase 1 POC (personal, non-commercial use), the system uses the existing Claude subscription credentials. Configuration:

```env
# .env
ANTHROPIC_API_KEY=<from ~/.claude/.credentials.json.bak>
CLAUDE_OPUS_MODEL=claude-opus-4-6
CLAUDE_HAIKU_MODEL=claude-haiku-4-5-20251001
```

### 4.3 Rate limit mitigation

- MiroFish agent calls use Haiku (lighter, higher rate limits)
- Agent calls are batched where possible (batch prompt with multiple agent actions per call)
- Orchestrator Opus calls are sequential (4-8 per campaign, well within limits)
- If rate limited, system implements exponential backoff with max 3 retries
- Fallback: If Haiku rate limits are hit during simulation, fall back to local Ollama with qwen2.5:7b
- Configurable via .env: `LLM_FALLBACK_ENABLED=true`, `LLM_FALLBACK_MODEL=qwen2.5:7b`

---

## 5. Environment configuration

### 5.1 Single .env file (repo root)

```env
# ── Claude API ──────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_OPUS_MODEL=claude-opus-4-6
CLAUDE_HAIKU_MODEL=claude-haiku-4-5-20251001

# ── TRIBE v2 ────────────────────────────────────────────────
TRIBE_SCORER_URL=http://localhost:8001
TRIBE_MODEL_PATH=./models/tribev2
TRIBE_DEVICE=cuda
TRIBE_TEXT_ONLY=true    # Start with text-only, add audio/video later

# ── MiroFish ────────────────────────────────────────────────
MIROFISH_URL=http://localhost:5000
MIROFISH_LLM_BASE_URL=http://localhost:4000/v1  # LiteLLM proxy
MIROFISH_LLM_MODEL=claude-haiku-4-5-20251001

# ── Neo4j ───────────────────────────────────────────────────
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=mirofish

# ── Ollama (embeddings only) ────────────────────────────────
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text

# ── Orchestrator ────────────────────────────────────────────
ORCHESTRATOR_PORT=8000
DATABASE_PATH=./data/nexus_sim.db
DEFAULT_AGENT_COUNT=40
DEFAULT_MAX_ITERATIONS=4
DEFAULT_SIMULATION_CYCLES=30

# ── Fallback ────────────────────────────────────────────────
LLM_FALLBACK_ENABLED=true
LLM_FALLBACK_MODEL=qwen2.5:7b
LLM_FALLBACK_BASE_URL=http://localhost:11434/v1

# ── UI ──────────────────────────────────────────────────────
VITE_API_BASE_URL=http://localhost:8000
```

### 5.2 Docker Compose (docker-compose.yml)

```yaml
version: "3.8"

services:
  neo4j:
    image: neo4j:5.15-community
    container_name: nexus-neo4j
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      NEO4J_AUTH: neo4j/mirofish
    volumes:
      - neo4j_data:/data
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "mirofish", "RETURN 1"]
      interval: 10s
      timeout: 5s
      retries: 5

  ollama:
    image: ollama/ollama
    container_name: nexus-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 10s
      timeout: 5s
      retries: 5

  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    container_name: nexus-litellm
    ports:
      - "4000:4000"
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
    command: --model anthropic/${CLAUDE_HAIKU_MODEL} --port 4000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4000/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  mirofish-backend:
    build:
      context: ./mirofish/backend
      dockerfile: Dockerfile
    container_name: nexus-mirofish
    ports:
      - "5000:5000"
    environment:
      LLM_API_KEY: "anything"
      LLM_BASE_URL: http://litellm:4000/v1
      LLM_MODEL_NAME: ${CLAUDE_HAIKU_MODEL}
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: mirofish
      EMBEDDING_MODEL: nomic-embed-text
      EMBEDDING_BASE_URL: http://ollama:11434
    depends_on:
      neo4j:
        condition: service_healthy
      ollama:
        condition: service_healthy
      litellm:
        condition: service_healthy

volumes:
  neo4j_data:
  ollama_data:
```

**Services NOT in Docker (run on host):**
- `tribe_scorer/` — Needs direct CUDA access. Run with: `cd tribe_scorer && uvicorn main:app --port 8001`
- `orchestrator/` — Runs on host for easier debugging. Run with: `cd orchestrator && uvicorn main:app --port 8000 --reload`
- `ui/` — Vite dev server. Run with: `cd ui && npm run dev`

---

## 6. Error handling and resilience

### 6.1 Service health checks
The orchestrator's `GET /api/status` endpoint pings all downstream services and reports:
```json
{
  "orchestrator": "healthy",
  "tribe_scorer": "healthy",
  "mirofish": "healthy",
  "neo4j": "healthy",
  "litellm": "healthy",
  "ollama": "healthy",
  "gpu_available": true,
  "gpu_vram_free_mb": 3200
}
```

### 6.2 Graceful degradation
- **TRIBE v2 fails:** Campaign continues WITHOUT neural scores. MiroFish simulation still runs. Report notes: "Neural scoring unavailable for this run. Results based on social simulation only."
- **MiroFish fails:** Campaign continues WITHOUT social simulation. TRIBE v2 scores are still reported. Report notes: "Social simulation unavailable. Results based on neural scoring only."
- **Both fail:** Campaign fails with a clear error message. No partial results.
- **LiteLLM fails (Claude API):** If Haiku is unavailable, fall back to local Ollama with qwen2.5:7b (if LLM_FALLBACK_ENABLED=true). Log the fallback.
- **Rate limited:** Exponential backoff (1s, 2s, 4s), max 3 retries, then fallback or graceful degradation.

### 6.3 Logging
- All services log to stdout (Docker captures this).
- Orchestrator logs every API call with duration, status code, and token counts.
- Campaign run logs are stored in SQLite alongside results for debugging.

---

## 7. Security considerations (POC scope)

- **No authentication.** Single-user, local machine only. Add auth in Phase 2.
- **No HTTPS.** All traffic is localhost. Add TLS in Phase 2.
- **API key in .env.** Not committed to Git (.gitignore). Load via environment variables.
- **No input sanitization beyond Pydantic validation.** Single trusted user. Add sanitization in Phase 2.
- **SQLite is adequate.** Single-user, no concurrent writes. Migrate to PostgreSQL in Phase 2 if needed.

---

## 8. Hardware allocation summary

| Resource | Allocated to | Amount |
|----------|-------------|--------|
| GPU VRAM (12GB) | TRIBE v2 inference | ~8-10GB |
| GPU VRAM (12GB) | Ollama embeddings | ~1GB |
| GPU VRAM (12GB) | Free headroom | ~1-3GB |
| RAM (32GB) | Neo4j | ~2-4GB |
| RAM (32GB) | Docker containers (MiroFish, LiteLLM, Ollama) | ~4-6GB |
| RAM (32GB) | TRIBE v2 (PyTorch) | ~4-6GB |
| RAM (32GB) | Orchestrator + UI dev server | ~1-2GB |
| RAM (32GB) | OS + other | ~8-10GB |
| Disk (1TB SSD) | Model weights (TRIBE v2 + Ollama) | ~25GB |
| Disk (1TB SSD) | Docker images + volumes | ~15GB |
| Disk (1TB SSD) | Neo4j data | ~2-5GB |
| Disk (1TB SSD) | Project code + data | ~1GB |

---

*This spec is the authoritative reference for how the system is built. All implementation should follow these patterns unless a specific deviation is documented and justified.*
