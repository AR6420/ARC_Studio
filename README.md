# Nexus Sim

Content optimization platform combining neural response prediction (TRIBE v2), multi-agent social simulation (MiroFish), and LLM-driven iterative optimization (Claude Opus).

## Architecture

```
UI (React/Vite) --> Orchestrator (FastAPI) --> TRIBE v2 (neural scoring)
                                           --> MiroFish (social simulation)
                                           --> Claude API (analysis + generation)
```

## Quick Start

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# 2. Start infrastructure services
docker compose up -d

# 3. Start TRIBE v2 scorer (requires CUDA GPU)
cd tribe_scorer && uvicorn main:app --port 8001

# 4. Start orchestrator
cd orchestrator && uvicorn main:app --port 8000 --reload

# 5. Start UI dev server
cd ui && npm run dev
```

## Project Structure

```
ARC_Studio/
├── orchestrator/    # FastAPI backend - campaign orchestration
├── tribe_scorer/    # TRIBE v2 neural scoring service
├── mirofish/        # MiroFish-Offline (Git submodule)
├── ui/              # React + Vite + TypeScript dashboard
├── shared/          # Shared utilities
├── docs/            # Project documentation
├── data/            # SQLite database (gitignored)
└── docker-compose.yml
```

## Status

Phase 1 POC - In Development
