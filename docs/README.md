# Nexus Sim

Nexus Sim is a content optimization platform that combines neural response prediction (TRIBE v2), multi-agent social simulation (MiroFish-Offline), and LLM-driven iterative optimization (Claude Opus) into a single feedback loop. A user submits content -- a product launch, PSA, policy draft, or any text-based communication -- and the system generates variants, scores them neurally, simulates social propagation, analyzes cross-system results, and iterates until quality thresholds are met.

**Core value proposition:** The iterative feedback loop between neural scoring and social simulation produces measurably better content than single-pass generation, with cross-system reasoning that explains WHY certain neural patterns lead to specific social outcomes.

**Status:** Phase 1 POC -- single-user, local machine, non-commercial.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Setup Instructions](#setup-instructions)
4. [Quick Start](#quick-start)
5. [API Reference](#api-reference)
6. [Project Structure](#project-structure)
7. [Configuration](#configuration)
8. [Demographic Presets](#demographic-presets)
9. [Composite Scores](#composite-scores)
10. [Running Tests](#running-tests)
11. [Demo Scenarios](#demo-scenarios)

---

## Architecture Overview

Nexus Sim is a modular monorepo with four main modules communicating over REST on localhost.

### Three-System Feedback Loop

```
User Input
    |
    v
Claude Opus (variant generation)
    |
    +------------------+------------------+
    |                                     |
    v                                     v
TRIBE v2                             MiroFish
(neural response prediction)    (multi-agent social sim)
7 brain-region scores            8 social metrics
    |                                     |
    +------------------+------------------+
                       |
                       v
               Claude Opus (cross-system analysis)
                       |
                       v
                Iterate or Stop
                       |
                       v
                  Final Report
```

### System Components

**TRIBE v2 (Neural Scoring)**
Uses a fine-tuned LLaMA 3.2-3B model to predict brain activation patterns from text stimuli. Maps approximately 70,000 voxel activations to 7 actionable dimensions using the Glasser HCP-MMP1.0 atlas parcellation:

| Dimension | Brain Regions | What It Measures |
|-----------|--------------|------------------|
| Attention Capture | Visual cortex (V1-V4), FEF | Does the content grab attention? |
| Emotional Resonance | Amygdala, insula, ACC | Does it trigger emotion? |
| Memory Encoding | Hippocampus, MTL | Will people remember it? |
| Reward Response | Ventral striatum, OFC | Does it feel rewarding? |
| Threat Detection | Amygdala (fear circuit) | Does it trigger defensiveness? |
| Cognitive Load | Prefrontal cortex, DLPFC | Is it too complex? |
| Social Relevance | TPJ, mPFC, STS | Does it activate social processing? |

**MiroFish-Offline (Social Simulation)**
Multi-agent social simulation engine where AI agents (powered by Claude Haiku via LiteLLM) interact with content in a simulated social environment. Produces 8 metrics:

- Organic share count
- Sentiment trajectory (time series)
- Counter-narrative count
- Peak virality cycle
- Sentiment drift
- Coalition formation (group size and stability)
- Influence concentration
- Platform divergence

**Claude Opus (Analysis and Generation)**
Handles variant generation (Haiku for speed), cross-system analysis bridging neural and social data (Opus for depth), and final report generation across 4 output layers (verdict, scorecard, deep analysis, mass psychology).

### 7 Composite Scores

These are computed from the raw TRIBE v2 and MiroFish data:

| Score | Interpretation |
|-------|---------------|
| Attention Score | Will people notice this? |
| Virality Potential | Will people share this? |
| Backlash Risk | Will this blow up negatively? (lower is better) |
| Memory Durability | Will people remember this next week? |
| Conversion Potential | Will people take the desired action? |
| Audience Fit | How well does this match the target audience? |
| Polarization Index | Does this unify or divide? (lower is better) |

### Iterative Optimization

Each campaign run consists of multiple iterations (default: 4). In each iteration:

1. Claude generates content variants (or uses user-supplied variants in iteration 1)
2. TRIBE v2 scores each variant neurally
3. Top variants go through MiroFish social simulation
4. Claude Opus analyzes combined neural + social results
5. If thresholds are met or max iterations reached, stop; otherwise, generate improved variants and repeat

---

## Prerequisites

### Hardware

- NVIDIA GPU with CUDA support (developed and tested on RTX 5070 Ti with 12GB VRAM)
- 32GB RAM recommended
- 1TB SSD recommended (model weights ~25GB)

### Software

- Python 3.11+
- Node.js 18+
- Docker Desktop with NVIDIA Container Toolkit (for Neo4j, LiteLLM, MiroFish containers)
- Git (with submodule support)

### API Keys and Access

- **Anthropic API key** -- for Claude Opus and Haiku calls
- **HuggingFace token** -- for downloading the gated LLaMA 3.2-3B model used by TRIBE v2. Request access at [meta-llama/Llama-3.2-3B](https://huggingface.co/meta-llama/Llama-3.2-3B) (approval can take 1-24 hours)

---

## Setup Instructions

### 1. Clone the Repository

```bash
git clone --recurse-submodules <repo-url>
cd ARC_Studio
```

If you already cloned without submodules, initialize them:

```bash
git submodule update --init --recursive
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your API keys:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

Alternatively, leave `ANTHROPIC_API_KEY` empty and set `CLAUDE_CREDENTIALS_PATH` to point to your Claude credentials file (OAuth token fallback for Claude Code users).

See the [Configuration](#configuration) section for a full list of environment variables.

### 3. Start Infrastructure Services

Start Neo4j (graph database), LiteLLM (API proxy), and MiroFish (social simulation) via Docker Compose:

```bash
docker compose up -d
```

Verify containers are running:

```bash
docker compose ps
```

You should see three healthy services: `nexus-neo4j`, `nexus-litellm`, and `nexus-mirofish`.

### 4. Start TRIBE v2 Neural Scorer

TRIBE v2 runs on the host (not in Docker) for direct CUDA GPU access:

```bash
cd tribe_scorer
pip install -r requirements.txt
uvicorn main:app --port 8001
```

First launch will download model weights from HuggingFace (~6GB). Subsequent launches load from cache.

Verify: `curl http://localhost:8001/api/health`

### 5. Start the Orchestrator

```bash
cd orchestrator
pip install -r requirements.txt
uvicorn main:app --port 8000 --reload
```

Verify: `curl http://localhost:8000/api/health`

The health endpoint checks connectivity to TRIBE v2, MiroFish, Neo4j, and LiteLLM.

### 6. Start the UI

```bash
cd ui
npm install
npm run dev
```

The UI dev server starts at [http://localhost:5173](http://localhost:5173).

### 7. Pull Ollama Embedding Model

If Ollama is not already running on the host (it runs inside Docker via the MiroFish container, but you may also want it locally):

```bash
ollama pull nomic-embed-text
```

---

## Quick Start

### Via the Web UI

1. Open [http://localhost:5173](http://localhost:5173) in your browser
2. Click **New Campaign** in the sidebar
3. Paste your seed content (e.g., a product launch announcement)
4. Enter a prediction question (e.g., "How will CTOs react to this announcement?")
5. Select a demographic preset (e.g., Tech Professionals)
6. Adjust agent count and iteration sliders if desired
7. Review the time estimate displayed next to the Run button
8. Click **Run Campaign**
9. Watch real-time progress via the SSE progress stream
10. View results across three tabs: Campaign, Simulation, and Report

### Via the CLI

Run a campaign without the web server:

```bash
python -m orchestrator.cli \
  --seed-content "Announcing NexaVault: enterprise cloud storage with zero-knowledge encryption." \
  --prediction-question "How will CTOs react to this launch?" \
  --demographic tech_professionals
```

With all options:

```bash
python -m orchestrator.cli \
  --seed-content "Your content here..." \
  --prediction-question "Your question here..." \
  --demographic tech_professionals \
  --agent-count 40 \
  --max-iterations 4 \
  --thresholds '{"attention_score": 70.0, "backlash_risk": 25.0}' \
  --constraints "Never use fear-based messaging" \
  --output results.json \
  --verbose
```

Using a file as input:

```bash
python -m orchestrator.cli \
  --seed-file content.txt \
  --prediction-question "How will the audience react?" \
  --demographic general_consumer_us \
  --output results.json
```

CLI arguments:

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--seed-content` | Yes* | -- | Inline seed content text |
| `--seed-file` | Yes* | -- | Path to a text file with seed content |
| `--prediction-question` | Yes | -- | What you want to know about audience response |
| `--demographic` | Yes | -- | Demographic preset key or "custom" |
| `--demographic-custom` | No | None | Custom demographic description |
| `--agent-count` | No | 40 | Number of MiroFish agents (20-200) |
| `--max-iterations` | No | 4 | Max optimization iterations (1-10) |
| `--thresholds` | No | None | JSON thresholds object |
| `--constraints` | No | None | Brand guidelines or constraints |
| `--output` | No | stdout | Path to write JSON results |
| `--verbose` / `-v` | No | false | Enable verbose logging |

*One of `--seed-content` or `--seed-file` is required (mutually exclusive).

---

## API Reference

All endpoints are prefixed with `/api`. The orchestrator runs on port 8000 by default.

### Campaigns

#### POST /api/campaigns

Create and start a new campaign.

**Request body:**

```json
{
  "seed_content": "Your content here (100-5000 words)",
  "prediction_question": "How will the audience react?",
  "demographic": "tech_professionals",
  "demographic_custom": null,
  "agent_count": 40,
  "max_iterations": 4,
  "thresholds": {"attention_score": 70.0},
  "constraints": "Never use fear-based messaging",
  "auto_start": true
}
```

**Response:** `201 Created` with `CampaignResponse` object.

#### GET /api/campaigns

List all campaigns.

**Response:** `200 OK` with `CampaignListResponse` containing an array of campaign summaries.

#### GET /api/campaigns/{campaign_id}

Get full campaign detail including iterations, variants, scores, and report.

**Response:** `200 OK` with `CampaignResponse`.

#### DELETE /api/campaigns/{campaign_id}

Delete a campaign and all associated data.

**Response:** `204 No Content`.

### Progress and Estimation

#### GET /api/campaigns/{campaign_id}/progress

Server-Sent Events (SSE) stream for real-time campaign progress.

**Event types:**

| Event | Description |
|-------|-------------|
| `iteration_start` | New iteration beginning, includes ETA |
| `step` | Pipeline step progress (variant generation, scoring, simulation, analysis) |
| `iteration_complete` | Iteration finished |
| `threshold_check` | Threshold evaluation result |
| `convergence_check` | Convergence detection result |
| `report_generating` | Report generation started |
| `report_complete` | Report generation finished |
| `campaign_complete` | Campaign finished with stop reason |

#### POST /api/estimate

Get a time estimate for a campaign configuration.

**Request body:**

```json
{
  "agent_count": 40,
  "max_iterations": 4
}
```

**Response:** `200 OK` with `EstimateResponse` containing estimated minutes.

### Reports and Export

#### GET /api/campaigns/{campaign_id}/report

Get the generated report for a completed campaign.

**Response:** `200 OK` with `ReportResponse` containing:
- `verdict` -- Layer 1: plain English recommendation
- `scorecard` -- Layer 2: composite scores, variant ranking, summary
- `deep_analysis` -- Layer 3: full data breakdown
- `mass_psychology_general` -- Layer 4: general audience narrative
- `mass_psychology_technical` -- Layer 4: social psychology terminology

#### GET /api/campaigns/{campaign_id}/export/json

Export full campaign results as JSON.

**Response:** `200 OK` with JSON attachment download.

#### GET /api/campaigns/{campaign_id}/export/markdown

Export campaign report as Markdown.

**Response:** `200 OK` with Markdown attachment download.

### System

#### GET /api/health

System health check. Pings all downstream services and reports status.

**Response:**

```json
{
  "orchestrator": "healthy",
  "tribe_scorer": "healthy",
  "mirofish": "healthy",
  "neo4j": "healthy",
  "litellm": "healthy"
}
```

#### GET /api/demographics

List available demographic presets.

**Response:** Array of preset objects with `key`, `label`, and `description`.

### Agent Interview

#### POST /api/campaigns/{campaign_id}/agents/{agent_id}/chat

Proxy a chat message to a MiroFish simulated agent.

**Request body:**

```json
{
  "message": "Why did you share this content?"
}
```

**Response:** `200 OK` with `AgentChatResponse` containing the agent's response.

---

## Project Structure

```
ARC_Studio/
|-- orchestrator/              # FastAPI backend -- campaign orchestration
|   |-- main.py                # FastAPI app factory, CORS, lifespan
|   |-- config.py              # Environment config (Pydantic BaseSettings)
|   |-- cli.py                 # CLI entry point for server-free campaigns
|   |-- api/
|   |   |-- campaigns.py       # CRUD endpoints for campaigns
|   |   |-- reports.py         # Report retrieval and export endpoints
|   |   |-- progress.py        # SSE progress stream and time estimates
|   |   |-- health.py          # Health check and demographics endpoints
|   |   |-- agents.py          # Agent interview proxy endpoint
|   |   |-- schemas.py         # All Pydantic request/response models
|   |-- engine/
|   |   |-- campaign_runner.py # Main orchestration loop (multi-iteration)
|   |   |-- variant_generator.py  # Claude Haiku variant generation
|   |   |-- tribe_scorer.py    # TRIBE v2 scoring pipeline
|   |   |-- mirofish_runner.py # MiroFish simulation runner
|   |   |-- result_analyzer.py # Claude Opus cross-system analysis
|   |   |-- report_generator.py   # 4-layer report generation
|   |   |-- composite_scorer.py   # Composite score computation
|   |   |-- threshold_checker.py  # Threshold evaluation
|   |   |-- time_estimator.py  # Campaign duration estimation
|   |-- clients/
|   |   |-- claude_client.py   # Anthropic SDK wrapper (Opus + Haiku)
|   |   |-- tribe_client.py    # HTTP client for TRIBE v2 service
|   |   |-- mirofish_client.py # HTTP client for MiroFish API
|   |-- storage/
|   |   |-- database.py        # SQLite connection and migrations
|   |   |-- campaign_store.py  # Campaign CRUD operations
|   |-- prompts/
|   |   |-- variant_generation.py   # Variant generation prompt templates
|   |   |-- result_analysis.py      # Analysis prompt templates
|   |   |-- report_verdict.py       # Layer 1 verdict prompt
|   |   |-- report_psychology.py    # Layer 4 mass psychology prompts
|   |   |-- demographic_profiles.py # 6 demographic preset configurations
|   |-- tests/                 # pytest test suite
|   |-- requirements.txt
|
|-- tribe_scorer/              # TRIBE v2 neural scoring service
|   |-- main.py                # FastAPI app, model loading on startup
|   |-- config.py              # Model paths, device config
|   |-- scoring/
|   |   |-- model_loader.py    # Load TRIBE v2 weights, initialize encoders
|   |   |-- text_scorer.py     # Text -> fMRI prediction -> ROI scores
|   |   |-- roi_extractor.py   # Region-of-interest activation extraction
|   |   |-- normalizer.py      # Raw fMRI values -> 0-100 normalized scores
|
|-- mirofish/                  # MiroFish-Offline (Git submodule)
|   |-- backend/               # Flask app, Neo4j integration, agent simulation
|   |-- frontend/              # Vue.js frontend (not used by Nexus Sim)
|
|-- ui/                        # React + Vite + TypeScript dashboard
|   |-- src/
|   |   |-- api/               # API client (apiFetch wrapper) and types
|   |   |-- components/        # Reusable UI components
|   |   |-- pages/             # Route pages (NewCampaign, CampaignDetail)
|   |   |-- hooks/             # React Query hooks and SSE hooks
|   |   |-- utils/             # Score colors, formatters
|   |-- index.html
|   |-- vite.config.ts
|   |-- tailwind.config.ts
|
|-- docs/                      # Project documentation
|   |-- Application_Technical_Spec.md
|   |-- Results.md
|   |-- README.md (this file)
|
|-- docker-compose.yml         # Neo4j, LiteLLM, MiroFish containers
|-- .env.example               # Environment variable template
|-- scripts/
|   |-- refresh-env.sh         # Environment refresh utility
```

---

## Configuration

All configuration is managed through a single `.env` file at the repository root. The orchestrator loads settings via Pydantic BaseSettings (`orchestrator/config.py`).

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (empty) | Anthropic API key. If empty, falls back to OAuth token from `CLAUDE_CREDENTIALS_PATH`. |
| `CLAUDE_CREDENTIALS_PATH` | `~/.claude/.credentials.json` | Path to Claude credentials file (OAuth token fallback). |
| `CLAUDE_OPUS_MODEL` | `claude-opus-4-6` | Model ID for Claude Opus (deep analysis). |
| `CLAUDE_HAIKU_MODEL` | `claude-haiku-4-5-20251001` | Model ID for Claude Haiku (fast structured tasks). |
| `TRIBE_SCORER_URL` | `http://localhost:8001` | Base URL for the TRIBE v2 scoring service. |
| `TRIBE_MODEL_PATH` | `./models/tribev2` | Path to TRIBE v2 model weights directory. |
| `TRIBE_DEVICE` | `cuda` | PyTorch device for TRIBE v2 inference (`cuda` or `cpu`). |
| `TRIBE_TEXT_ONLY` | `true` | Restrict TRIBE v2 to text-only stimuli (Phase 1). |
| `MIROFISH_URL` | `http://localhost:5000` | Base URL for the MiroFish API. |
| `MIROFISH_LLM_BASE_URL` | `http://localhost:4000/v1` | LiteLLM proxy URL for MiroFish agent LLM. |
| `MIROFISH_LLM_MODEL` | `claude-haiku-4-5-20251001` | LLM model name for MiroFish agents. |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt connection URI. |
| `NEO4J_USER` | `neo4j` | Neo4j username. |
| `NEO4J_PASSWORD` | `mirofish` | Neo4j password. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama base URL (embeddings only). |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Ollama embedding model name. |
| `ORCHESTRATOR_PORT` | `8000` | Port the orchestrator listens on. |
| `DATABASE_PATH` | `./data/nexus_sim.db` | Path to the SQLite database file. |
| `DEFAULT_AGENT_COUNT` | `40` | Default number of MiroFish agents (20-200, multiples of 10). |
| `DEFAULT_MAX_ITERATIONS` | `4` | Default max optimization iterations (1-10). |
| `DEFAULT_SIMULATION_CYCLES` | `30` | Default number of MiroFish simulation cycles. |
| `LLM_FALLBACK_ENABLED` | `true` | Enable fallback to local Ollama if Claude Haiku is rate-limited. |
| `LLM_FALLBACK_MODEL` | `qwen2.5:7b` | Ollama model name for LLM fallback. |
| `LLM_FALLBACK_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible URL for fallback LLM. |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Orchestrator URL used by the UI dev server. |

---

## Demographic Presets

Six demographic presets are available, each providing tailored agent personas and cognitive weight adjustments for TRIBE v2 score interpretation.

| Key | Label | Description |
|-----|-------|-------------|
| `tech_professionals` | Tech Professionals | Developers, CTOs, IT leaders. Skeptical of marketing, responsive to technical substance. |
| `enterprise_decision_makers` | Enterprise Decision-Makers | C-suite, VPs, directors. Time-constrained, ROI-focused, risk-averse. |
| `general_consumer_us` | General Consumer (US, 25-45) | Broad US adult audience. Mixed media literacy, moderate social sharing. |
| `policy_aware_public` | Policy-Aware Public | Civically engaged adults. Sensitive to partisan signals and fairness framing. |
| `healthcare_professionals` | Healthcare Professionals | Doctors, nurses, public health workers. Evidence-driven, authority-sensitive. |
| `gen_z_digital_natives` | Gen Z Digital Natives (18-27) | High social media engagement, authenticity-sensitive, meme-literate. |

A **custom** demographic option allows free-text description of any target audience. Claude translates custom descriptions into MiroFish agent persona configurations and TRIBE v2 cognitive weight adjustments.

---

## Composite Scores

The 7 composite scores are derived from raw TRIBE v2 neural scores and MiroFish simulation metrics. Each is normalized to 0-100.

| Score | Formula | Color Coding |
|-------|---------|-------------|
| Attention Score | `0.6 * attention_capture + 0.4 * emotional_resonance` | Green >= 70, Amber 40-69, Red < 40 |
| Virality Potential | `(emotional_resonance * social_relevance) / max(cognitive_load, 10) * share_rate_normalized` | Green >= 70, Amber 40-69, Red < 40 |
| Backlash Risk | `threat_detection / max(reward_response + social_relevance, 10) * counter_narrative_factor` | Green < 25, Amber 25-50, Red > 50 (inverted) |
| Memory Durability | `memory_encoding * emotional_resonance * sentiment_stability` | Green >= 70, Amber 40-69, Red < 40 |
| Conversion Potential | `reward_response * attention_capture / max(threat_detection, 10)` | Green >= 70, Amber 40-69, Red < 40 |
| Audience Fit | `demographic_weight_adjusted_composite` | Green >= 70, Amber 40-69, Red < 40 |
| Polarization Index | `coalition_count * platform_divergence * (1 - sentiment_stability)` | Green < 25, Amber 25-50, Red > 50 (inverted) |

Note: Backlash Risk and Polarization Index use inverted color coding -- lower values are better.

---

## Running Tests

### Backend (Orchestrator)

```bash
cd orchestrator
pip install -r requirements.txt
python -m pytest
```

For verbose output:

```bash
python -m pytest -v
```

### Frontend (UI)

```bash
cd ui
npm install
npm test
```

---

## Demo Scenarios

Five pre-defined scenarios are provided for validation and demonstration. Each covers a different use case and audience type.

### Scenario 1: Product Launch (Tech Audience)

- **Content:** NexaVault enterprise cloud storage launch announcement
- **Question:** "How will CTOs and engineering leaders react to this launch announcement?"
- **Demographic:** Tech Professionals
- **Expected insight:** Tension between security and collaboration messaging

### Scenario 2: Public Health PSA (General Population)

- **Content:** Respiratory virus vaccine PSA emphasizing safety data and community protection
- **Question:** "Will this PSA drive vaccine uptake or create anti-vaccine backlash?"
- **Demographic:** General Consumer (US, 25-45)
- **Expected insight:** Clinical trial statistics trigger cognitive load; community protection framing activates social relevance

### Scenario 3: Price Increase (Enterprise Customers)

- **Content:** NexaVault 18% price increase announcement
- **Question:** "How should we frame this price increase to minimize churn and negative sentiment?"
- **Demographic:** Enterprise Decision-Makers
- **Expected insight:** Leading with value addition before price scores better on reward response

### Scenario 4: Policy Announcement (Civic Audience)

- **Content:** Data privacy regulation requiring 30-day user data deletion
- **Question:** "How will different political constituencies react to this regulation?"
- **Demographic:** Policy-Aware Public
- **Expected insight:** Coalition formation along pro-privacy vs. pro-business lines

### Scenario 5: Gen Z Product Marketing (Young Digital Audience)

- **Content:** AI-powered study tool launch for college students
- **Question:** "What messaging approach will drive organic sharing among college students?"
- **Demographic:** Gen Z Digital Natives (18-27)
- **Expected insight:** Authenticity and peer proof outperform polished marketing

---

## Error Handling and Graceful Degradation

The system is designed to continue operating when individual components are unavailable:

- **TRIBE v2 unavailable:** Campaign continues without neural scores. Report notes the gap. Results are based on social simulation only.
- **MiroFish unavailable:** Campaign continues without social simulation. Results are based on neural scoring only.
- **Both unavailable:** Campaign fails with a clear error message.
- **Claude API rate limited:** Exponential backoff (1s, 2s, 4s), max 3 retries. If LLM_FALLBACK_ENABLED=true, falls back to local Ollama with qwen2.5:7b.

---

## Hardware Allocation

| Resource | Allocated To | Amount |
|----------|-------------|--------|
| GPU VRAM (12GB) | TRIBE v2 inference | ~8-10GB |
| GPU VRAM (12GB) | Ollama embeddings | ~1GB |
| RAM (32GB) | Neo4j + Docker containers | ~6-10GB |
| RAM (32GB) | TRIBE v2 (PyTorch) | ~4-6GB |
| RAM (32GB) | Orchestrator + UI | ~1-2GB |
| Disk (1TB SSD) | Model weights (TRIBE v2 + Ollama) | ~25GB |
| Disk (1TB SSD) | Docker images + volumes | ~15GB |

---

## Security Notes (Phase 1 POC)

- No authentication -- single-user, localhost only
- No HTTPS -- all traffic is localhost
- API keys stored in `.env` (gitignored, never committed)
- No input sanitization beyond Pydantic validation -- single trusted user
- SQLite is adequate for single-user with no concurrent writes

These constraints will be addressed in Phase 2.

---

## License

Phase 1 POC -- private, non-commercial use.
