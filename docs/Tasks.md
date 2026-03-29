# Tasks.md — Actionable task checklist

## Project: Nexus Sim (Phase 1 POC)
## Instructions: Each task is sized for one Claude Code session (30-90 min). Check off as completed. Add notes in the Notes column for anything Claude Code should know for dependent tasks.

---

## Sprint 0: Environment setup

| # | Task | Status | Notes |
|---|------|--------|-------|
| 0.1 | Verify Docker Desktop is running: `docker ps` | [ ] | |
| 0.2 | Verify NVIDIA drivers: `nvidia-smi` — confirm RTX 5070 Ti detected | [ ] | |
| 0.3 | Install NVIDIA Container Toolkit if not present. Verify: `docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi` | [ ] | |
| 0.4 | Verify Python 3.11+: `python --version`. Install if needed. | [ ] | |
| 0.5 | Verify Node.js 18+: `node --version`. Install if needed. | [ ] | |
| 0.6 | Install PyTorch with CUDA: `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124`. Verify: `python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"` | [ ] | |
| 0.7 | Create HuggingFace account. Request access to gated LLaMA 3.2-3B model. Install CLI: `pip install huggingface_hub`. Login: `huggingface-cli login` | [ ] | Access approval can take 1-24 hours. Do this FIRST. |
| 0.8 | Verify Anthropic API key works: `curl https://api.anthropic.com/v1/messages -H "x-api-key: $KEY" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" -d '{"model":"claude-haiku-4-5-20251001","max_tokens":100,"messages":[{"role":"user","content":"Hi"}]}'` | [ ] | Use key from ~/.claude/.credentials.json.bak. Note any rate limit headers in response. |
| 0.9 | Initialize Git repo with monorepo structure. Create directories: orchestrator/, tribe_scorer/, mirofish/ (empty), ui/, shared/, docs/. Create .gitignore, .env.example, README.md | [ ] | |
| 0.10 | Copy Results.md, Application_Technical_Spec.md, Planning.md, Tasks.md into docs/ directory | [ ] | |
| 0.11 | Create .env file from template in Application_Technical_Spec.md Section 5.1. Fill in ANTHROPIC_API_KEY. | [ ] | Do NOT commit .env to Git. |

---

## Sprint 1, Track A: MiroFish-Offline setup

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.A.1 | Fork MiroFish-Offline (github.com/nikmcfly/MiroFish-Offline). Add as Git submodule: `git submodule add <fork-url> mirofish` | [ ] | Fork to your own GitHub first, then add as submodule. |
| 1.A.2 | Create docker-compose.yml in repo root with Neo4j, Ollama, and LiteLLM services (use spec from Application_Technical_Spec.md Section 5.2) | [ ] | |
| 1.A.3 | Start infrastructure services: `docker compose up -d neo4j ollama litellm` | [ ] | |
| 1.A.4 | Pull embedding model into Ollama: `docker exec nexus-ollama ollama pull nomic-embed-text` | [ ] | ~274MB download |
| 1.A.5 | Verify Neo4j is running: open http://localhost:7474, login with neo4j/mirofish | [ ] | |
| 1.A.6 | Verify LiteLLM proxy is running: `curl http://localhost:4000/health` | [ ] | |
| 1.A.7 | Test LiteLLM → Claude Haiku: `curl http://localhost:4000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"claude-haiku-4-5-20251001","messages":[{"role":"user","content":"Hello"}]}'` | [ ] | This confirms the OpenAI-compatible proxy correctly routes to Anthropic. If this fails, MiroFish won't work. |
| 1.A.8 | Configure MiroFish .env: set LLM_BASE_URL=http://litellm:4000/v1, NEO4J_URI=bolt://neo4j:7687, EMBEDDING_BASE_URL=http://ollama:11434 | [ ] | Use Docker service names (not localhost) for inter-container communication. |
| 1.A.9 | Add MiroFish backend to docker-compose.yml. Build and start: `docker compose up -d mirofish-backend` | [ ] | May need Dockerfile adjustments. Check requirements.txt compatibility. |
| 1.A.10 | Test MiroFish graph build: `curl -X POST http://localhost:5000/api/graph/build -H "Content-Type: application/json" -d '{"content":"Acme Corp announces new AI product...","title":"Test","source_type":"press_release"}'` | [ ] | Should return graph_id with entity count. If it fails, check LiteLLM + Neo4j connectivity. |
| 1.A.11 | Test MiroFish simulation run (small): 20 agents, 10 cycles. Use the graph_id from previous step. | [ ] | First simulation will be slow. Monitor Docker logs: `docker logs nexus-mirofish -f` |
| 1.A.12 | Test agent chat: after simulation completes, pick an agent ID from results and send a chat message via API | [ ] | |
| 1.A.13 | Document MiroFish API endpoints, request/response formats, and any quirks discovered during testing | [ ] | Add to Notes column for Sprint 2 reference. |

---

## Sprint 1, Track B: TRIBE v2 setup

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.B.1 | Clone TRIBE v2: `git clone https://github.com/facebookresearch/tribev2.git` into tribe_scorer/vendor/ | [ ] | |
| 1.B.2 | Install TRIBE v2 Python dependencies: `pip install -r requirements.txt` (from tribev2 repo) | [ ] | Likely needs: torch, transformers, huggingface_hub, nilearn, pyvista, tqdm, scipy, numpy |
| 1.B.3 | Download TRIBE v2 model weights from HuggingFace: `python -c "from demo_utils import TribeModel; m = TribeModel()"` | [ ] | BLOCKED by HuggingFace LLaMA 3.2-3B approval (task 0.7). Weights may be several GB. |
| 1.B.4 | Run TRIBE v2 test inference: use the test_run.py or demo_utils to process a sample text | [ ] | Verify GPU is used (check nvidia-smi during inference). Note VRAM usage. |
| 1.B.5 | Create tribe_scorer/main.py: FastAPI app with /api/score, /api/score/batch, /api/health endpoints | [ ] | |
| 1.B.6 | Create tribe_scorer/scoring/model_loader.py: Load TRIBE v2 model on app startup, keep in memory | [ ] | Use FastAPI lifespan context manager to load model once. |
| 1.B.7 | Create tribe_scorer/scoring/text_scorer.py: Accept text input → run TRIBE v2 inference → return raw voxel activations | [ ] | Text-only mode for Phase 1 (no video/audio). |
| 1.B.8 | Create tribe_scorer/scoring/roi_extractor.py: Map raw voxel activations to 7 brain region groups (attention, emotion, memory, reward, threat, cognitive load, social). Use Glasser atlas parcellation. | [ ] | This is the novel IP. See Results.md Section 3.2 for ROI → dimension mapping. |
| 1.B.9 | Create tribe_scorer/scoring/normalizer.py: Convert raw ROI activations to 0-100 normalized scores | [ ] | Use percentile normalization against a baseline distribution. For POC, the baseline can be the range of scores from 10-20 diverse test texts. |
| 1.B.10 | Test full scoring pipeline: text → model inference → ROI extraction → normalization → 7 scores | [ ] | Run 5-10 diverse texts, verify scores are in 0-100 range and vary meaningfully between different content types. |
| 1.B.11 | Start tribe_scorer service: `cd tribe_scorer && uvicorn main:app --port 8001`. Verify /api/health returns GPU status. | [ ] | |

---

## Sprint 1, Track C: Claude client setup

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.C.1 | Create orchestrator/clients/claude_client.py: wrapper around Anthropic SDK. Methods: `call_opus(system, user) → str`, `call_haiku(system, user) → str`, `call_opus_json(system, user) → dict` (with JSON parsing) | [ ] | Include retry logic with exponential backoff. |
| 1.C.2 | Test Opus call: generate 3 content variants from a test campaign brief | [ ] | Verify response quality. Adjust system prompt if needed. |
| 1.C.3 | Test Haiku call: generate a simple agent persona from a demographic description | [ ] | |
| 1.C.4 | Create orchestrator/prompts/ directory with template files. Create variant_generation.py with system prompt and user prompt template. | [ ] | Use f-strings or Jinja2. Include placeholders for: campaign brief, demographic, constraints, previous iteration results. |
| 1.C.5 | Create orchestrator/prompts/demographic_profiles.py: dictionary of preset demographic configurations (all 6 presets from Results.md Section 2.1) | [ ] | Each preset should contain: description, agent generation instructions, cognitive weight adjustments, example personas. |
| 1.C.6 | Create orchestrator/prompts/result_analysis.py: Opus prompt template for cross-system analysis. Accepts: neural scores, simulation metrics, variant content. Must reference BOTH data sources. | [ ] | Include examples of good cross-system reasoning in the prompt. |

---

## Sprint 2: Integration — orchestrator pipeline

| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | Create orchestrator/main.py: FastAPI app with CORS (allow localhost:5173), lifespan hook for DB init | [ ] | |
| 2.2 | Create orchestrator/config.py: Pydantic BaseSettings loading from .env | [ ] | |
| 2.3 | Create orchestrator/storage/database.py: SQLite setup with campaign and iteration tables (schema from Tech Spec Section 3.1) | [ ] | Use aiosqlite for async compatibility with FastAPI. |
| 2.4 | Create orchestrator/storage/models.py: Campaign and Iteration dataclasses/Pydantic models | [ ] | |
| 2.5 | Create orchestrator/api/schemas.py: All Pydantic request/response models (CampaignCreate, CampaignResponse, IterationResult, etc.) | [ ] | Match schemas exactly with Tech Spec Section 2.1 and Results.md Section 7. |
| 2.6 | Create orchestrator/api/campaigns.py: POST /api/campaigns (creates campaign, starts background task), GET /api/campaigns/{id}, GET /api/campaigns, DELETE /api/campaigns/{id} | [ ] | Use FastAPI BackgroundTasks for async campaign execution. |
| 2.7 | Create orchestrator/api/status.py: GET /api/status — ping tribe_scorer, mirofish, neo4j, litellm, ollama. Return health object. | [ ] | |
| 2.8 | Create orchestrator/api/demographics.py: GET /api/demographics — return list of preset demographics | [ ] | |
| 2.9 | Create orchestrator/clients/tribe_client.py: async HTTP client for tribe_scorer. Methods: `score_text(text) → ScoreResponse`, `score_batch(texts) → list[ScoreResponse]` | [ ] | Use httpx.AsyncClient. Handle timeouts (TRIBE inference can take 5-10 seconds). |
| 2.10 | Create orchestrator/clients/mirofish_client.py: async HTTP client for MiroFish. Methods: `build_graph(content, title)`, `run_simulation(graph_id, agent_count, config)`, `get_results(sim_id)`, `chat_with_agent(agent_id, message)` | [ ] | Handle MiroFish's async simulation (poll status until complete). |
| 2.11 | Create orchestrator/engine/variant_generator.py: Uses claude_client to generate N content variants from campaign brief + demographic + constraints. Returns list of variant strings. | [ ] | N = 5 for default. Include the user's seed content as the base. |
| 2.12 | Create orchestrator/engine/tribe_scorer.py: Sends variants to tribe_client, collects scores, returns structured results | [ ] | Handle tribe_scorer being unavailable (graceful degradation). |
| 2.13 | Create orchestrator/engine/composite_scorer.py: Implements all composite score formulas from Results.md Section 3.2 | [ ] | All formulas must match Results.md exactly. Unit test these. |
| 2.14 | Create orchestrator/engine/mirofish_runner.py: Sends top-K variants to MiroFish for simulation. Handles graph build → simulation run → result collection. | [ ] | K = top 3 variants by neural score. Handle MiroFish being unavailable (graceful degradation). |
| 2.15 | Create orchestrator/engine/result_analyzer.py: Uses claude_client (Opus) to analyze combined neural + simulation results. Produces cross-system reasoning. | [ ] | The prompt MUST instruct Opus to reference both TRIBE scores and MiroFish metrics specifically. |
| 2.16 | Create orchestrator/engine/campaign_runner.py: Main orchestration function. Wire together: variant generation → TRIBE scoring → composite scoring → MiroFish simulation → result analysis. Single iteration only (no loop yet). | [ ] | |
| 2.17 | Add CLI entry point: `python -m orchestrator.engine.campaign_runner --brief "test brief" --demographic tech_professionals` | [ ] | |
| 2.18 | Run first end-to-end test via CLI. Verify output contains: variants with neural scores, simulation metrics, composite scores, Opus analysis. | [ ] | THIS IS MILESTONE 2. Do not proceed to Sprint 3 until this works. |

---

## Sprint 3, Track A: Optimization loop

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.A.1 | Modify campaign_runner.py to support multiple iterations. After analysis, generate improved variants and re-run scoring + simulation. | [ ] | Pass previous iteration's results to Opus in the variant generation prompt. |
| 3.A.2 | Create orchestrator/engine/threshold_checker.py: Compare composite scores against user thresholds. Return bool (all met) + dict (which met, which not). | [ ] | |
| 3.A.3 | Add early stopping: if all thresholds met, stop iterating. If improvement < 5% for 2 consecutive iterations, stop (convergence). | [ ] | |
| 3.A.4 | Create orchestrator/engine/time_estimator.py: Formula-based estimate. Also track actual execution time per iteration to refine estimates mid-run. | [ ] | Formula: estimated_minutes = (agent_count / 40) * iterations * 3 |
| 3.A.5 | Add POST /api/estimate endpoint: accepts config, returns time estimate | [ ] | |
| 3.A.6 | Add SSE endpoint: GET /api/campaigns/{id}/stream. Emit events: iteration_started, tribe_scoring, mirofish_simulation, analysis_complete, iteration_complete, campaign_complete. Each with progress data. | [ ] | Use FastAPI's StreamingResponse with text/event-stream. |
| 3.A.7 | Test optimization loop: run a campaign with 3 iterations. Verify scores improve between iterations. | [ ] | THIS IS MILESTONE 3. If scores don't improve, debug Opus prompts before proceeding. |

---

## Sprint 3, Track B: Report generation

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.B.1 | Create orchestrator/prompts/report_verdict.py: Opus prompt for Layer 1 verdict. Must produce 100-400 words of plain English. No jargon. Clear recommendation. | [ ] | Test with multiple campaign types. Verify non-technical readability. |
| 3.B.2 | Create orchestrator/engine/report_builder.py: Assembles Layer 2 scorecard data (composite scores, ranking, iteration trajectory) as structured JSON | [ ] | No Opus call needed for Layer 2 — it's data assembly. |
| 3.B.3 | Add Layer 3 deep analysis to report_builder: package all raw scores, metrics, reasoning chains | [ ] | Include per-iteration data so the UI can show the improvement trajectory. |
| 3.B.4 | Create orchestrator/prompts/report_psychology.py: TWO Opus prompts. (1) General mode: narrative prose about crowd dynamics, 200-600 words, no jargon. (2) Technical mode: same data framed with psychology theory references (Granovetter, Noelle-Neumann, Cialdini, etc.). | [ ] | Test both modes. General should be readable by any adult. Technical should reference ≥2 named theories. |
| 3.B.5 | Add export functionality: JSON download (full results) and Markdown summary download | [ ] | |
| 3.B.6 | Integrate report generation into campaign_runner.py: after final iteration, generate all 4 layers | [ ] | |

---

## Sprint 3, Track C: UI development

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.C.1 | Scaffold React + Vite + TypeScript project in ui/. Install dependencies: tailwindcss, recharts, react-query, axios | [ ] | |
| 3.C.2 | Create ui/src/api/client.ts: Axios instance pointing at VITE_API_BASE_URL. Create api/campaigns.ts with all API call functions. | [ ] | |
| 3.C.3 | Create ui/src/api/types.ts: TypeScript types matching ALL Pydantic schemas from orchestrator | [ ] | Keep in sync with orchestrator/api/schemas.py. |
| 3.C.4 | Create layout components: Sidebar (campaign history list), Header (Nexus Sim title), Layout (sidebar + main content) | [ ] | |
| 3.C.5 | Create NewCampaign page: seed content textarea with file upload, prediction question input, demographic selector (6 preset cards + custom text), config panel (agent slider, iteration slider, threshold toggles + inputs), time estimate display, Run button | [ ] | |
| 3.C.6 | Create DemographicSelector component: 6 cards with preset name + short description. "Custom" card expands to textarea. | [ ] | |
| 3.C.7 | Create ConfigPanel component: agent count slider (20-200, step 10), max iterations slider (1-10), threshold toggle + input for each of 7 composite scores, time estimate (calls /api/estimate on change) | [ ] | |
| 3.C.8 | Create CampaignDetail page shell: 3 tabs (Campaign, Simulation, Report). Tab routing. | [ ] | |
| 3.C.9 | Create Campaign tab: CompositeScoreCard grid (7 scores with color coding), VariantRanking list (ranked variants with score bars), IterationChart (Recharts line chart showing score trajectory across iterations) | [ ] | Color coding: green ≥70, amber 40-69, red <40. Inverted for backlash risk and polarization index. |
| 3.C.10 | Create Simulation tab: MiroFish metrics cards, SentimentTimeline (Recharts line chart), CoalitionMap (simple visualization of group formation), AgentGrid (clickable cards showing agent name + stance) | [ ] | |
| 3.C.11 | Create AgentChat component: modal or slide-out panel. Text input → sends to orchestrator → proxies to MiroFish agent chat API. Shows conversation history. | [ ] | |
| 3.C.12 | Create Report tab: Verdict section (rendered markdown), Scorecard section (visual metrics), DeepAnalysis section (expandable/collapsible), MassPsychology section (General/Technical toggle switch) | [ ] | |
| 3.C.13 | Create ProgressStream component: connects to SSE endpoint during campaign run. Shows current step, iteration progress, estimated time remaining. | [ ] | |
| 3.C.14 | Create CampaignList page: table/list of all campaigns with status badges, creation date, demographic, top score. Click to open CampaignDetail. | [ ] | |
| 3.C.15 | Add JSON export button to Report tab: downloads full campaign results as .json file | [ ] | |
| 3.C.16 | Add Markdown export button: downloads summary report as .md file | [ ] | |
| 3.C.17 | UI polish: loading states, error states, empty states, responsive layout | [ ] | |

---

## Sprint 4: Validation and documentation

| # | Task | Status | Notes |
|---|------|--------|-------|
| 4.1 | Create test briefs for all 5 demo scenarios (from Results.md Section 5) as JSON files in tests/scenarios/ | [ ] | |
| 4.2 | Run Scenario 1 (product launch, tech audience). Record: iteration scores, final report, execution time. | [ ] | |
| 4.3 | Run Scenario 2 (public health PSA, general consumer). Record results. | [ ] | |
| 4.4 | Run Scenario 3 (price increase, enterprise decision-makers). Record results. | [ ] | |
| 4.5 | Run Scenario 4 (policy announcement, policy-aware public). Record results. | [ ] | |
| 4.6 | Run Scenario 5 (Gen Z marketing, digital natives). Record results. | [ ] | |
| 4.7 | Analyze results against success criteria (Results.md Section 4): Does iteration improvement occur in ≥4/5 scenarios? Does cross-system reasoning appear? Are demographics differentiated? | [ ] | Document findings in results/validation_report.md |
| 4.8 | Fix bugs discovered during validation runs | [ ] | |
| 4.9 | Tune Opus prompts if results are generic or don't meet quality standards | [ ] | |
| 4.10 | Tune composite score formulas if metrics don't behave as expected | [ ] | |
| 4.11 | Write README.md: project overview, architecture diagram, setup instructions (step-by-step), running instructions, demo instructions | [ ] | |
| 4.12 | Write SETUP.md: detailed environment setup guide for reproducing the project on a fresh machine | [ ] | |
| 4.13 | Record demo video (5-10 min): show a full campaign run from brief input to report output | [ ] | |
| 4.14 | Create one-pager: single-page summary of what the POC demonstrates, with real results data | [ ] | |
| 4.15 | Final code cleanup: remove debug prints, add docstrings to key functions, organize imports | [ ] | |
| 4.16 | Final Git commit with all documentation, test results, and clean codebase | [ ] | |

---

## Quick reference: task counts

| Sprint | Tasks | Estimated hours |
|--------|-------|----------------|
| Sprint 0 | 11 | 4-6 hours |
| Sprint 1A | 13 | 12-16 hours |
| Sprint 1B | 11 | 12-16 hours |
| Sprint 1C | 6 | 4-6 hours |
| Sprint 2 | 18 | 16-24 hours |
| Sprint 3A | 7 | 8-12 hours |
| Sprint 3B | 6 | 6-10 hours |
| Sprint 3C | 17 | 16-24 hours |
| Sprint 4 | 16 | 16-24 hours |
| **Total** | **105** | **~95-140 hours** |

At 4-6 productive hours/day with Claude Code, this is approximately **4-6 weeks** of focused development.

---

*Update this file as tasks are completed. Add notes for anything the next Claude Code session needs to know. This is the living checklist.*
