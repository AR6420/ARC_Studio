# Planning.md — Sprint breakdown, dependencies, and milestones

## Project: A.R.C Studio (Phase 1 POC)
## Timeline: 8 weeks (flexible — solo developer with Claude Code)
## Build tool: Claude Code with GSD skill

---

## 1. Sprint overview

| Sprint | Weeks | Focus | Deliverable |
|--------|-------|-------|-------------|
| Sprint 0 | Pre-work (1-2 days) | Environment setup | All prerequisites installed, verified |
| Sprint 1 | Week 1-2 | Foundation | All 3 systems running independently |
| Sprint 2 | Week 3-4 | Integration | Orchestrator wires all systems together |
| Sprint 3 | Week 5-6 | Optimization loop + UI | Iterative improvement working, dashboard functional |
| Sprint 4 | Week 7-8 | Polish + validation | 5 demo scenarios tested, results documented |

---

## 2. Dependency graph

```
Sprint 0: Environment
    │
    ├─→ [0.1] Docker Desktop verified
    ├─→ [0.2] NVIDIA + CUDA verified
    ├─→ [0.3] Python 3.11+ verified
    ├─→ [0.4] Node.js 18+ verified
    ├─→ [0.5] HuggingFace access (LLaMA 3.2-3B gated model)
    ├─→ [0.6] Anthropic API key verified
    └─→ [0.7] Git repo initialized with monorepo structure

Sprint 1: Foundation (all can be parallel after Sprint 0)
    │
    ├─→ [1.A] MiroFish-Offline setup ─────────────────┐
    │     ├─→ [1.A.1] Clone + Docker compose           │
    │     ├─→ [1.A.2] LiteLLM proxy setup              │
    │     ├─→ [1.A.3] First simulation with Haiku       │
    │     └─→ [1.A.4] API endpoint verification         │
    │                                                    │
    ├─→ [1.B] TRIBE v2 setup ─────────────────────────┐ │
    │     ├─→ [1.B.1] Clone + install dependencies     │ │
    │     ├─→ [1.B.2] Download model weights           │ │
    │     ├─→ [1.B.3] First text inference              │ │
    │     └─→ [1.B.4] Scoring wrapper (FastAPI)         │ │
    │                                                    │ │
    └─→ [1.C] Claude client setup ────────────────────┐ │ │
          ├─→ [1.C.1] API key test                     │ │ │
          ├─→ [1.C.2] Opus + Haiku client wrapper      │ │ │
          └─→ [1.C.3] Prompt template structure        │ │ │
                                                       │ │ │
Sprint 2: Integration (requires ALL of Sprint 1)     ◄─┘─┘─┘
    │
    ├─→ [2.1] Orchestrator skeleton (FastAPI app)
    ├─→ [2.2] Campaign data model (SQLite + schemas)
    ├─→ [2.3] Variant generator (Opus prompt → N variants)
    ├─→ [2.4] TRIBE scoring pipeline (orchestrator → tribe_scorer)
    ├─→ [2.5] MiroFish pipeline (orchestrator → mirofish)
    ├─→ [2.6] Composite score calculator
    ├─→ [2.7] Result analyzer (Opus cross-system analysis)
    ├─→ [2.8] First end-to-end run (CLI, no UI)
    │
Sprint 3: Optimization loop + UI (requires Sprint 2)
    │
    ├─→ [3.A] Optimization loop ──────────────────────┐
    │     ├─→ [3.A.1] Iteration logic                  │
    │     ├─→ [3.A.2] Threshold checker                 │
    │     ├─→ [3.A.3] Convergence detection             │
    │     └─→ [3.A.4] Time estimator                    │
    │                                                    │
    ├─→ [3.B] Report generation ──────────────────────┐ │
    │     ├─→ [3.B.1] Layer 1: Verdict prompt           │ │
    │     ├─→ [3.B.2] Layer 2: Scorecard assembly       │ │
    │     ├─→ [3.B.3] Layer 3: Deep analysis builder    │ │
    │     ├─→ [3.B.4] Layer 4: Mass psychology prompts  │ │
    │     └─→ [3.B.5] JSON + Markdown export            │ │
    │                                                    │ │
    └─→ [3.C] UI development ────────────────────────┐ │ │
          ├─→ [3.C.1] React + Vite scaffold            │ │ │
          ├─→ [3.C.2] Campaign form page               │ │ │
          ├─→ [3.C.3] Campaign tab (scores + ranking)  │ │ │
          ├─→ [3.C.4] Simulation tab (metrics + agents)│ │ │
          ├─→ [3.C.5] Report tab (all 4 layers)        │ │ │
          ├─→ [3.C.6] Progress streaming (SSE)          │ │ │
          └─→ [3.C.7] Campaign history page             │ │ │
                                                       │ │ │
Sprint 4: Validation (requires Sprint 3)             ◄─┘─┘─┘
    │
    ├─→ [4.1] Run demo scenario 1 (product launch)
    ├─→ [4.2] Run demo scenario 2 (public health PSA)
    ├─→ [4.3] Run demo scenario 3 (price increase)
    ├─→ [4.4] Run demo scenario 4 (policy announcement)
    ├─→ [4.5] Run demo scenario 5 (Gen Z marketing)
    ├─→ [4.6] Collect and analyze results
    ├─→ [4.7] Bug fixes and refinements
    ├─→ [4.8] Record demo video
    └─→ [4.9] Write README + technical documentation
```

---

## 3. Sprint details

### Sprint 0: Environment setup (1-2 days)

**Goal:** Every prerequisite installed and verified. Zero ambiguity about whether the machine is ready.

**Checklist:**
- [ ] Docker Desktop running (verify: `docker ps`)
- [ ] NVIDIA drivers installed (verify: `nvidia-smi`)
- [ ] NVIDIA Container Toolkit installed (verify: `docker run --gpus all nvidia/cuda:12.0-base nvidia-smi`)
- [ ] CUDA toolkit installed (verify: `nvcc --version`)
- [ ] Python 3.11+ installed (verify: `python --version`)
- [ ] pip / uv package manager available
- [ ] Node.js 18+ installed (verify: `node --version`)
- [ ] npm available (verify: `npm --version`)
- [ ] Git configured with SSH key
- [ ] HuggingFace account created
- [ ] LLaMA 3.2-3B access requested (gated model — may take hours for approval)
- [ ] HuggingFace CLI installed and logged in (`huggingface-cli login`)
- [ ] Anthropic API key available and tested (`curl` test to API)
- [ ] PyTorch with CUDA support installed (`python -c "import torch; print(torch.cuda.is_available())"`)
- [ ] Monorepo structure created:
  ```
  nexus-sim/
  ├── orchestrator/
  ├── tribe_scorer/
  ├── mirofish/  (empty, will be submodule)
  ├── ui/
  ├── shared/
  ├── docker-compose.yml
  ├── .env
  ├── .gitignore
  ├── Results.md
  ├── Application_Technical_Spec.md
  ├── Planning.md
  └── Tasks.md
  ```

**Blockers:**
- HuggingFace LLaMA 3.2-3B access approval can take 1-24 hours. Request this FIRST.
- NVIDIA Container Toolkit install can be tricky on some systems. If it fails, Ollama can run on CPU (slower embeddings but functional).

---

### Sprint 1: Foundation (Week 1-2)

**Goal:** All three systems running independently. Each one accepts input and produces output. No integration yet.

**Track A — MiroFish-Offline (3-4 days)**

Priority: HIGH. This is the most complex setup with the most moving parts (Neo4j, Ollama, LiteLLM, Flask, Vue).

1. Fork MiroFish-Offline → add as Git submodule
2. Set up docker-compose with Neo4j + Ollama + LiteLLM
3. Pull nomic-embed-text model into Ollama container
4. Configure MiroFish .env to point at LiteLLM (→ Claude Haiku)
5. Run first simulation: upload a test document, generate agents, run simulation
6. Verify API endpoints work: graph/build, simulation/run, simulation/{id}/results
7. Test agent chat endpoint: interview a post-simulation agent

**Success criteria:** MiroFish accepts a document via API, runs a simulation with 20+ agents using Claude Haiku, and returns structured results including sentiment trajectory and agent posts.

**Track B — TRIBE v2 (3-4 days)**

Priority: HIGH. This involves model weight downloads (potentially large) and GPU inference setup.

1. Clone tribev2 repo
2. Install Python dependencies (PyTorch, transformers, etc.)
3. Request and download model weights from HuggingFace
4. Run the test_run.py to verify inference works
5. Build the tribe_scorer FastAPI wrapper:
   - POST /api/score endpoint
   - POST /api/score/batch endpoint
   - GET /api/health endpoint
6. Implement ROI extractor (fMRI voxels → 7 dimension scores)
7. Implement normalizer (raw activations → 0-100 scores)
8. Test: submit a text, get back 7 normalized scores

**Success criteria:** tribe_scorer accepts a text via API, runs TRIBE v2 inference on local GPU, and returns 7 normalized neural dimension scores (0-100).

**Track C — Claude client (1-2 days)**

Priority: MEDIUM. Simpler than A and B, but needed before Sprint 2.

1. Create claude_client.py with Anthropic SDK
2. Implement separate methods for Opus and Haiku calls
3. Create prompt template structure (Jinja2 or f-string based)
4. Test: generate 3 content variants from a campaign brief using Opus
5. Test: rate limit handling (exponential backoff)

**Success criteria:** Claude client can call both Opus and Haiku, generate structured responses, and handle rate limits gracefully.

---

### Sprint 2: Integration (Week 3-4)

**Goal:** The orchestrator connects all three systems into a single pipeline. One campaign brief goes in, one set of scored and analyzed results comes out.

**Dependencies:** ALL of Sprint 1 must be complete.

**Day-by-day plan:**

**Days 1-2: Orchestrator skeleton**
- FastAPI app factory with CORS, lifespan hooks
- SQLite database setup with campaign + iteration tables
- Pydantic schemas for all request/response models
- Health check endpoint (pings all services)
- Basic campaign CRUD (create, read, list, delete)

**Days 3-4: Variant generation + TRIBE scoring**
- Variant generator: Opus prompt that takes campaign brief → generates N variants
- TRIBE scoring pipeline: send each variant to tribe_scorer, collect scores
- Composite score calculator: raw scores → composite scores (formulas from Results.md)

**Days 5-6: MiroFish integration**
- MiroFish pipeline: send top-K variants to MiroFish for simulation
- Simulation result parser: extract all 8 metrics from MiroFish output
- Update composite scores with MiroFish data (virality, backlash risk adjustments)

**Days 7-8: Result analysis + first end-to-end run**
- Result analyzer: Opus prompt that takes neural scores + simulation metrics → cross-system analysis
- Wire everything together in campaign_runner.py
- First end-to-end run via CLI: `python -m orchestrator.engine.campaign_runner --brief "test brief"`
- Verify the full data flow produces valid output

**Success criteria:** Running a campaign from CLI produces: N variants with neural scores, simulation metrics for top variants, composite scores, and an Opus analysis that references both TRIBE and MiroFish data.

---

### Sprint 3: Optimization loop + UI (Week 5-6)

**Goal:** The system iterates and improves. Users interact through a visual dashboard.

**Track A — Optimization loop (Days 1-4)**

1. **Iteration logic:** After analysis, Opus generates improved variants based on what worked/failed. Feed back into scoring + simulation. Repeat.
2. **Threshold checker:** Compare composite scores against user-defined thresholds. Stop early if all met.
3. **Convergence detection:** If improvement between iterations is < 5% for 2 consecutive iterations, stop early (diminishing returns).
4. **Time estimator:** Formula-based estimate + real-time updating based on actual execution speed.
5. **SSE progress streaming:** Emit progress events during campaign run (current step, iteration number, estimated time remaining).

**Track B — Report generation (Days 3-6)**

1. **Layer 1 — Verdict:** Opus prompt that produces plain-English recommendation (100-400 words, no jargon).
2. **Layer 2 — Scorecard:** Assemble composite scores, variant ranking, iteration trajectory data into structured JSON for UI rendering.
3. **Layer 3 — Deep analysis:** Package all raw scores, metrics, and Opus reasoning chains into expandable sections.
4. **Layer 4 — Mass psychology:** Two Opus prompts — one for general audience (narrative prose), one for psychologists (theory-referenced technical analysis).
5. **Export:** JSON download of full results. Markdown summary generation.

**Track C — UI development (Days 3-10)**

1. **Scaffold:** React + Vite + TypeScript + Tailwind. API client setup.
2. **Campaign form (NewCampaign page):**
   - Seed content textarea + file upload
   - Prediction question input
   - Demographic selector (preset cards + custom text)
   - Configuration panel: agent count slider, iteration slider, threshold toggles
   - Time estimate display
   - Run button
3. **Campaign detail page (CampaignDetail — 3 tabs):**
   - Campaign tab: variant ranking, composite score cards, iteration improvement line chart
   - Simulation tab: MiroFish metrics, sentiment timeline chart, agent grid with click-to-interview
   - Report tab: verdict (Layer 1), scorecard (Layer 2), expandable deep analysis (Layer 3), mass psychology toggle (Layer 4)
4. **Progress streaming:** SSE connection showing real-time progress during campaign run.
5. **Campaign list page:** History of all runs with status badges.

**Success criteria:** User can create a campaign through the UI, watch real-time progress, and view all 4 report layers when complete. Optimization loop demonstrably improves scores across iterations.

---

### Sprint 4: Validation + polish (Week 7-8)

**Goal:** Run all 5 demo scenarios, collect results, fix bugs, document everything.

**Days 1-4: Run demo scenarios**
- Execute all 5 scenarios from Results.md (product launch, PSA, price increase, policy, Gen Z)
- For each scenario: record iteration improvement trajectory, final scores, final report
- Identify any failures: scenarios where iteration doesn't improve, analysis is generic, or system errors occur
- Fix bugs as they surface

**Days 5-6: Analysis and refinement**
- Analyze results against success criteria from Results.md
- Check: does iteration improvement occur in ≥4/5 scenarios?
- Check: does cross-system reasoning appear in all reports?
- Check: are composite scores meaningfully different between variants?
- Tune prompt templates if results are generic or unsatisfactory
- Tune composite score formulas if metrics don't behave as expected

**Days 7-8: Documentation and demo**
- Write comprehensive README.md (setup instructions, architecture overview, demo instructions)
- Record a 5-10 minute demo video showing a full campaign run
- Create a one-pager summarizing the POC results with real data
- Final code cleanup and commit

**Success criteria:** All criteria from Results.md Section 4 (Quality Standards) are met. Demo video is recorded. Documentation is complete.

---

## 4. Critical path

The longest dependency chain (items that cannot be parallelized):

```
Sprint 0 (2 days)
  → Sprint 1 Track B: TRIBE v2 setup (4 days) — HuggingFace approval may delay this
    → Sprint 2: Integration (8 days)
      → Sprint 3 Track A: Optimization loop (4 days)
        → Sprint 4: Validation (8 days)
```

**Total critical path: ~26 working days (5-6 weeks)**

Sprint 1 Tracks A, B, C can run in parallel (2 weeks). Sprint 3 Tracks A, B, C can partially overlap.

**Biggest risk to timeline:** HuggingFace LLaMA 3.2-3B access approval. If delayed, TRIBE v2 setup stalls. Mitigation: submit access request on Day 0, before anything else.

---

## 5. Milestones and go/no-go checkpoints

### Milestone 1: "It runs" (end of Sprint 1)
- All three systems produce output independently
- **Go/no-go:** If any system fails to produce output, diagnose before proceeding. Do NOT start integration with a broken component.

### Milestone 2: "It connects" (end of Sprint 2)
- One campaign brief produces scored, analyzed results end-to-end
- **Go/no-go:** If the pipeline doesn't complete end-to-end, fix the broken link. Don't start optimization or UI work until the basic pipeline works.

### Milestone 3: "It improves" (mid Sprint 3)
- The optimization loop shows measurable improvement between iterations
- **Go/no-go:** If iteration scores are flat or random after 3 test runs, re-examine the Opus analysis prompts and composite score formulas. This is the core hypothesis of the project.

### Milestone 4: "It's usable" (end of Sprint 3)
- UI is functional. A non-developer could use it with guidance.
- **Go/no-go:** Not a hard gate. UI polish is nice-to-have; the core value is in the pipeline.

### Milestone 5: "It's proven" (end of Sprint 4)
- 5 demo scenarios run, results documented, success criteria met
- **This is the final deliverable.** Everything after this is Phase 2.

---

## 6. Claude Code session strategy

### How to structure Claude Code sessions for maximum efficiency

Each Claude Code session should:
1. **Start** by reading the relevant spec docs (this Planning.md + Application_Technical_Spec.md + Tasks.md)
2. **Focus** on one task group (e.g., "Complete tasks 1.A.1 through 1.A.4")
3. **End** by updating Tasks.md with completion status and any notes

### Recommended session boundaries

- **Session 1:** Sprint 0 — environment setup and repo scaffolding
- **Session 2:** Sprint 1 Track A — MiroFish-Offline Docker setup
- **Session 3:** Sprint 1 Track A — MiroFish LiteLLM integration and first simulation
- **Session 4:** Sprint 1 Track B — TRIBE v2 clone, install, first inference
- **Session 5:** Sprint 1 Track B — tribe_scorer FastAPI wrapper
- **Session 6:** Sprint 1 Track C — Claude client + prompt templates
- **Session 7:** Sprint 2 — Orchestrator skeleton + schemas + database
- **Session 8:** Sprint 2 — Variant generation + TRIBE scoring pipeline
- **Session 9:** Sprint 2 — MiroFish integration pipeline
- **Session 10:** Sprint 2 — Result analyzer + first end-to-end run
- **Session 11:** Sprint 3 — Optimization loop (iteration, thresholds, convergence)
- **Session 12:** Sprint 3 — Report generation (all 4 layers)
- **Session 13:** Sprint 3 — UI scaffold + campaign form
- **Session 14:** Sprint 3 — UI campaign detail page (3 tabs)
- **Session 15:** Sprint 3 — UI progress streaming + campaign history
- **Session 16-20:** Sprint 4 — Demo scenarios, fixes, documentation

---

*This plan is a guide, not a contract. Adjust timelines based on actual progress. The critical thing is the dependency order — don't skip ahead.*
