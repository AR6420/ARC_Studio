# Phase 2 Plan: Multimodal Inputs, Reliability, and Calibration

**Author:** Adarsh Balanolla + Claude Code
**Date:** 2026-04-13
**Baseline:** `phase2-complete` tag (commit `64107ce` on `main`)
**Status:** Draft - awaiting review before implementation

---

## Table of Contents

1. [Context and Motivation](#1-context-and-motivation)
2. [Dependency Graph](#2-dependency-graph)
3. [Track B: Reliability and Performance Foundations](#3-track-b-reliability-and-performance-foundations)
4. [Track A: Multimodal Input Support](#4-track-a-multimodal-input-support)
5. [Track C: Calibration Against Real-World Data](#5-track-c-calibration-against-real-world-data)
6. [Critical Path Analysis](#6-critical-path-analysis)
7. [Risk Analysis](#7-risk-analysis)
8. [Minimum Viable Phase 2](#8-minimum-viable-phase-2)
9. [Out-of-Scope: Phase 3 Deferrals](#9-out-of-scope-phase-3-deferrals)
10. [Appendix: Technical Reference](#appendix-technical-reference)

---

## 1. Context and Motivation

Phase 1 hardening (Phases 0-2 of the fix plan) delivered a **stable POC** with:
- Silent failure elimination (`is_pseudo_score` flag end-to-end)
- 2.8x runtime improvement (~4 hours to ~85 minutes)
- `data_completeness` reporting per iteration
- 205 tests passing, 5/5 demo scenarios validated

Phase 2 has three goals:
1. **Solve the remaining reliability problems** that make the system fragile on laptop hardware
2. **Unlock the full TRIBE v2 trimodal pipeline** (text + audio + video) that currently sits unused in the vendor code
3. **Begin calibrating predictions against real-world outcomes** to transition from "interesting POC" to "scientifically validated tool"

### What We Know From Phase 1

From `docs/session_issues_retrospective.md` (17 issues, 5 landmines):
- **TRIBE timeout** is the #1 blocking issue. The pipeline takes 5-40+ minutes per text variant. Multimodal inputs (audio: Wav2Vec-BERT, video: V-JEPA2) will take longer. The timeout must be solved before adding new modalities.
- **CUDA sleep corruption** (Issue 6) causes silent pseudo-score fallbacks after laptop sleep. Phase 1 deferred it. Phase 2 must fix it.
- **Neo4j heap** (Landmine 3) will eventually exhaust at 2 GB limit under sustained use.
- **Docker health checks** are incomplete: MiroFish has no healthcheck, no explicit restart policy.

From `tribe_scorer/vendor/tribev2/` source analysis:
- TRIBE v2 **already supports** `audio_path` and `video_path` in `get_events_dataframe()`. The model was trained with all three modalities (LLaMA 3.2-3B for text, Wav2Vec-BERT for audio, V-JEPA2 for video). The inference pipeline, chunking, and brain-encoding model are all multimodal-ready.
- Audio feature extraction uses ~2-3 GB VRAM. Video (V-JEPA2-ViTg) uses ~4-6 GB. Combined with text (LLaMA 3.2-3B at ~6 GB), the system needs ~8-10 GB for any single modality.
- Video has 2x longer default job timeout (24h vs 12h) in TRIBE v2 defaults, confirming it is significantly more compute-intensive.

---

## 2. Dependency Graph

```
                        TRACK B: RELIABILITY
                        ====================

    B.3 (PyTorch docs)     B.4 (Neo4j)     B.5 (Docker)
         |                      |                |
         v                      v                v
    [standalone]           [standalone]      [standalone]
                                             
    B.2 (CUDA recovery)                      
         |                                   
         v                                   
    [standalone - can parallel with B.1]     

    B.1 (TRIBE timeout)  <-- CRITICAL PATH START
         |
         v
                        TRACK A: MULTIMODAL
                        ===================
         |
    A.1 (Audio input)
         |
         v
    A.2 (Video input)
         |
         v
    A.3 (Unified playback)
         |
         v
                        TRACK C: CALIBRATION
                        ====================
         |
    C.1 (Framework design)
         |
         v
    C.2 (Dataset curation)  <-- needs A.1 minimum, ideally A.2
         |
         v
    C.3 (Experiments)
         |
         v
    C.4 (Report)  <-- CRITICAL PATH END
```

**Critical path:** B.1 --> A.1 --> A.2 --> C.2 --> C.3 --> C.4

**Parallelizable clusters:**
- B.2, B.3, B.4, B.5 can all run in parallel with each other and with B.1
- C.1 (framework design) can start in parallel with A.1 (no code dependency, just design)
- A.3 can overlap with C.1 if A.2 is done

---

## 3. Track B: Reliability and Performance Foundations

### B.1: Fix TRIBE v2 Timeout for Long Variants

**Goal:** Re-run the Price Increase and PSA scenarios from Phase 1 validation with zero pseudo-score fallbacks under chunking.
**Priority:** P0 - blocks all of Track A.
**Tag:** `phase2-b1-complete`

#### Problem Statement

The current TRIBE v2 text pipeline for a single variant:
1. Text --> gTTS (text-to-speech) --> audio file (~5-15s)
2. Audio --> WhisperX (word alignment) --> word events (~10-30s)
3. Word events --> LLaMA 3.2-3B (embedding per word) --> feature vectors (~9-80s per word)
4. Feature vectors --> FmriEncoder (brain-encoding) --> cortical predictions (~10-30s)

For a 250-word variant with ~40 word embeddings, step 3 takes ~6-16 minutes. For a 500-word variant with ~80 word embeddings, step 3 takes ~12-32 minutes. Under GPU memory pressure (Ollama running, <1 GB free), per-embedding time jumps from ~9s to ~80s, pushing a 500-word variant past the 3600s timeout.

**Root cause:** The pipeline is monolithic. A single function call runs all 4 steps sequentially with no progress reporting, no ability to interrupt cleanly, and no way to budget time per step.

#### Approach: Text Chunking + Per-Chunk Progress

Split long texts into ~250-word chunks, score each chunk independently, merge results. This is architecturally aligned with how TRIBE v2 already handles long audio/video (ChunkEvents with 30-60s max).

**Why chunking over async queues:** Chunking solves the actual problem (single-variant inference time) without adding infrastructure complexity (message queues, job tables, polling). It also directly enables Track A, where audio/video chunking is already built into TRIBE v2.

#### Scope

| File | Change |
|------|--------|
| `tribe_scorer/scoring/text_scorer.py` | Add `_chunk_text()` to split on sentence boundaries; score each chunk; merge predictions via weighted average |
| `tribe_scorer/scoring/text_scorer.py` | Add per-chunk timeout (15 min per chunk) instead of per-variant timeout |
| `tribe_scorer/scoring/text_scorer.py` | Add progress logging per chunk: `"Chunk 2/4 scored in 8.2 min"` |
| `tribe_scorer/main.py` | Add configurable `max_words_per_chunk` setting (default 250) |
| `tribe_scorer/config.py` | Add `MAX_WORDS_PER_CHUNK` and `PER_CHUNK_TIMEOUT` settings |
| `orchestrator/clients/tribe_client.py` | Adjust timeout calculation: `per_chunk_timeout * ceil(word_count / chunk_size)` per text |
| `orchestrator/tests/test_tribe_timeout.py` | New test: verify chunking logic, merge behavior, timeout per chunk |

#### Chunking Algorithm

```
1. Split text on sentence boundaries (period, question mark, exclamation)
2. Greedily pack sentences into chunks of <= MAX_WORDS_PER_CHUNK words
3. If a single sentence exceeds limit, split on clause boundaries (comma, semicolon)
4. Score each chunk through the full TTS -> WhisperX -> LLaMA -> brain pipeline
5. Merge: weighted average of chunk predictions, weight = chunk word count
6. Return merged (n_vertices,) array as if it were a single prediction
```

**Why weighted average:** Longer chunks produce more word embeddings and therefore more stable brain-encoding predictions. Weighting by word count preserves the statistical reliability of longer chunks.

#### Success Criteria

1. Re-run the Price Increase and PSA scenarios from Phase 1 validation (`scenarios/price_increase.json`, `scenarios/public_health_psa.json`, same parameters: 20 agents, 2 iterations). Both scenarios previously produced 2/6 pseudo-score fallbacks at the 3600s timeout on long iteration 2 variants (see `results/phase2_validation.json`). Success: **0/6 pseudo-score fallbacks** on these same scenarios with chunking enabled.
2. Chunking is transparent: downstream composite scoring and reports see identical output format
3. Per-chunk progress logs appear in TRIBE scorer logs
4. `is_pseudo_score` is True only if ALL chunks fail, not if one chunk fails (partial scoring is still real scoring)
5. Existing 205 tests still pass (no regression)

#### Validation Strategy

1. Run both Price Increase and PSA scenarios end-to-end with chunking enabled, compare against `results/phase2_validation.json` as baseline
2. Verify 0/6 pseudo-score fallbacks (down from 2/6 in Phase 1 baseline)
3. Compare chunk-merged scores to monolithic scores on the same 250-word text to ensure merge does not distort results significantly (correlation > 0.95)

#### Rollback Plan

Revert chunking; restore monolithic `score_text()`. The `_INFERENCE_TIMEOUT` of 3600s remains as the safety net. Risk: long variants fall back to pseudo-scores as before.

---

### B.2: CUDA State Recovery After Laptop Sleep

**Goal:** Detect stale CUDA context from sleep/wake cycle and auto-restart the TRIBE scorer.
**Priority:** P1 - affects every laptop session.
**Tag:** `phase2-b2-complete`

#### Problem Statement

Issue 6 from the retrospective: When the laptop sleeps and wakes, the CUDA driver context becomes corrupted. The TRIBE model appears loaded (health check passes), but inference fails with `torch.AcceleratorError: CUDA error: unknown error`. The current behavior: silent fallback to pseudo-scores. The desired behavior: detect corruption, restart the scorer process, retry inference.

#### Approach: CUDA Health Probe + Self-Restart

Add a lightweight CUDA health probe that runs:
1. Before each inference request (in `_run_single_score` and `_run_batch_score`)
2. In the `/api/health` endpoint

The probe allocates a tiny tensor on CUDA and synchronizes. If it raises, the CUDA context is dead.

```python
def _check_cuda_health() -> bool:
    """Return True if CUDA context is alive. Takes <1ms."""
    if not torch.cuda.is_available():
        return False
    try:
        torch.cuda.synchronize()
        t = torch.zeros(1, dtype=torch.float32, device='cuda')
        del t
        return True
    except (RuntimeError, OSError):
        return False
```

When the probe fails:
1. Log `WARNING: CUDA context is stale (likely sleep/wake). Attempting recovery.`
2. Call `torch.cuda.empty_cache()` then attempt `torch.cuda.synchronize()` again
3. If recovery fails, return HTTP 503 with `"cuda_stale": true` in the health response
4. The orchestrator's TRIBE client detects 503 + `cuda_stale` and can optionally trigger a process restart via `scripts/restart_tribe.sh`

#### Scope

| File | Change |
|------|--------|
| `tribe_scorer/main.py` | Add `_check_cuda_health()` function; call before inference; add `cuda_healthy` field to HealthResponse |
| `tribe_scorer/main.py` | In `/api/health`: probe CUDA and report `cuda_healthy: bool` |
| `scripts/restart_tribe.sh` | New script: kill TRIBE process, wait, restart. Called by orchestrator on detected CUDA failure |
| `orchestrator/clients/tribe_client.py` | Detect `cuda_stale` in health check response; log warning; optionally trigger restart |
| `orchestrator/tests/test_cuda_recovery.py` | New test: mock CUDA failure, verify probe detects it, verify 503 response |

#### Success Criteria

1. After laptop sleep/wake, the TRIBE scorer's `/api/health` reports `cuda_healthy: false`
2. Inference requests return 503 (not pseudo-scores) when CUDA is stale
3. `restart_tribe.sh` successfully restarts the scorer and CUDA health returns to `true`
4. The orchestrator logs a clear warning when CUDA staleness is detected

#### Validation Strategy

Manual test: run a scoring request, put laptop to sleep for 30s, wake, call `/api/health`, verify `cuda_healthy: false`.

#### Rollback Plan

Remove the health probe. Behavior reverts to silent pseudo-score fallback. No regression risk.

---

### B.3: PyTorch sm_120 Compatibility Documentation

**Goal:** Document the upgrade path from PyTorch 2.6 to 2.8+ for RTX 5070 Ti (Blackwell, sm_120) native support.
**Priority:** P2 - preparation only, no code changes.
**Tag:** `phase2-b3-complete`

#### Scope

| File | Change |
|------|--------|
| `docs/pytorch_upgrade_path.md` | New document: current state (PyTorch 2.6 + CUDA 12.6), target state (2.8+ with native sm_120), migration steps, dependency impact (pyannote.audio, WhisperX, torchvision, torchaudio), testing plan |
| `tribe_scorer/requirements.txt` | Add comment documenting current version pins and why |

#### Content of `pytorch_upgrade_path.md`

1. Current PyTorch version and why it was chosen (2.6 is the last version before sm_120 support)
2. Which TRIBE v2 dependencies pin PyTorch (pyannote.audio requires specific torch versions)
3. Step-by-step upgrade procedure when PyTorch 2.8 is stable
4. Expected performance improvements (native kernel compilation vs JIT fallback)
5. Risk: pyannote.audio and WhisperX may not support PyTorch 2.8 immediately
6. Decision criteria: when to pull the trigger (stable release + all deps compatible)

#### Success Criteria

1. Document exists and is accurate
2. No code changes needed
3. A developer reading the document can execute the upgrade when the time comes

#### Validation Strategy

Peer review of the document.

#### Rollback Plan

Delete the document. No code impact.

---

### B.4: Neo4j Heap Monitoring and Cleanup

**Goal:** Prevent Neo4j heap exhaustion under sustained use; add cleanup strategy for old simulation data.
**Priority:** P2 - Landmine 3, not yet triggered but inevitable.
**Tag:** `phase2-b4-complete`

#### Problem Statement

Neo4j heap is capped at 2 GB (`docker-compose.yml`). Each MiroFish simulation adds ~10 MB of graph data (agents, ontology nodes, conversation history). After ~200 campaigns, heap usage becomes significant. After ~1000, Neo4j will OOM or become unresponsive.

#### Approach

1. **Monitoring:** Add Neo4j heap metrics to the orchestrator's `/api/health` endpoint. Query Neo4j's `dbms.queryJmx` or `CALL dbms.listConfig()` to report heap usage.
2. **Cleanup Cypher query:** A parameterized Cypher script that deletes simulation data older than N days, preserving campaign metadata.
3. **Manual cleanup script:** `scripts/cleanup_neo4j.sh` that runs the Cypher query via `cypher-shell`.

#### Scope

| File | Change |
|------|--------|
| `orchestrator/api/health.py` | Add Neo4j heap metrics to health response (heap_used_mb, heap_max_mb, node_count) |
| `orchestrator/clients/mirofish_client.py` | Add `get_neo4j_stats()` method that queries Neo4j metrics |
| `scripts/cleanup_neo4j.sh` | New script: delete simulation nodes older than N days (default 30) |
| `docker-compose.yml` | Comment documenting the 2 GB limit and when to increase it |

#### Success Criteria

1. `/api/health` shows Neo4j heap usage in the response
2. `cleanup_neo4j.sh` successfully removes old simulation data without affecting active campaigns
3. After cleanup, Neo4j heap usage decreases

#### Validation Strategy

1. Run 5+ campaigns, check `/api/health` shows increasing node count
2. Run cleanup script with `--days 0` (delete all), verify node count drops
3. Verify no active campaign data is affected

#### Rollback Plan

Remove the health metrics and cleanup script. Neo4j continues as before. Risk: eventual heap exhaustion under sustained use, but not imminent.

---

### B.5: Docker Compose Health Checks and Auto-Restart

**Goal:** All Docker services have health checks and auto-restart policies.
**Priority:** P1 - reduces manual restart frequency from Issue 17.
**Tag:** `phase2-b5-complete`

#### Current State

| Service | Health Check | Restart Policy |
|---------|-------------|----------------|
| neo4j | wget http://localhost:7474 | unless-stopped |
| litellm | Python urllib http://localhost:4000/health | unless-stopped |
| mirofish | **NONE** | unless-stopped (already set) |

#### Scope

| File | Change |
|------|--------|
| `docker-compose.yml` | Add healthcheck to mirofish: `curl -f http://localhost:5001/health` |
| `docker-compose.yml` | Add comment explaining health check strategy |

#### MiroFish Health Check

MiroFish already exposes `GET /health` on port 5001 returning `{"status": "ok", "service": "MiroFish-Offline Backend"}`. The healthcheck should use `curl` (verify it's available in the MiroFish Docker image) or `wget`.

```yaml
mirofish:
  ...
  restart: unless-stopped
  healthcheck:
    test: ["CMD-SHELL", "curl -sf http://localhost:5001/health || exit 1"]
    interval: 15s
    timeout: 10s
    retries: 5
    start_period: 45s
```

**Note:** `start_period: 45s` is longer than neo4j/litellm (30s) because MiroFish waits for both of its dependencies to be healthy before starting, then needs time to initialize Flask + Neo4j storage.

#### Success Criteria

1. `docker compose up -d` starts all services with health checks
2. `docker ps` shows HEALTHY for all three services
3. Killing the mirofish process inside the container triggers automatic restart
4. MiroFish `depends_on` with `condition: service_healthy` for neo4j and litellm continues to work

#### Validation Strategy

1. `docker compose up -d`, wait, `docker ps` -- all healthy
2. `docker exec arc-mirofish kill 1` -- verify container restarts and returns to healthy
3. Run a campaign end-to-end after the change to verify no regression

#### Rollback Plan

Revert `docker-compose.yml` to remove healthcheck and restart policy for mirofish. Other services are unchanged.

---

## 4. Track A: Multimodal Input Support

### A.1: Audio Input Support

**Goal:** Users can upload an audio file, route it to TRIBE v2's Wav2Vec-BERT pipeline, and see audio-specific scoring results.
**Priority:** P0 - first multimodal modality.
**Blocked on:** B.1 (timeout fix must land first -- audio inference will be slower than text TTS).
**Tag:** `phase2-a1-complete`

#### What Already Exists

TRIBE v2's `get_events_dataframe(audio_path=...)` already works. The pipeline:
1. Audio file --> ChunkEvents (30-60s segments)
2. Chunks --> WhisperX (word-level transcription)
3. Words --> Wav2Vec-BERT features (2 Hz, layers 0.75 and 1.0)
4. Features + words --> LLaMA 3.2-3B word embeddings
5. All features --> FmriEncoder --> cortical predictions

Wav2Vec-BERT uses ~2-3 GB VRAM. Combined with the brain model, total is ~8-10 GB -- within the RTX 5070 Ti's 12 GB budget as long as Ollama is stopped.

#### What Needs to Be Built

**TRIBE Scorer Layer:**

| File | Change |
|------|--------|
| `tribe_scorer/scoring/text_scorer.py` | Rename to `media_scorer.py`; add `score_audio(audio_path, model)` function. Uses `model.get_events_dataframe(audio_path=path)` instead of TextToEvents. Same predict/merge flow. |
| `tribe_scorer/scoring/media_scorer.py` | Add `_pseudo_score_from_audio(audio_path)` fallback -- duration-based heuristics (longer audio = more cognitive load, faster speech rate = higher attention) |
| `tribe_scorer/main.py` | Add `POST /api/score/audio` endpoint accepting multipart file upload. Saves to temp dir, calls `score_audio()`, returns same `ScoreResponse` |
| `tribe_scorer/main.py` | Add `AudioScoreRequest` schema with file upload (UploadFile) |
| `tribe_scorer/config.py` | Add `AUDIO_FORMATS` (.wav, .mp3, .flac, .ogg) and `AUDIO_MAX_DURATION_S` (300s = 5 min) |

**Orchestrator Layer:**

| File | Change |
|------|--------|
| `orchestrator/api/schemas.py` | Add `media_type` field (Literal["text", "audio", "video"], default "text"), `media_file_id` (optional), `generate_variants` (bool, default True) |
| `orchestrator/api/campaigns.py` | Add file upload endpoint: `POST /api/campaigns/upload` returns `file_id` + metadata |
| `orchestrator/clients/tribe_client.py` | Add `score_audio(file_path)` method posting multipart to `/api/score/audio` |
| `orchestrator/engine/tribe_scorer.py` | Add `score_audio_file(file_path)` that calls the TRIBE client's audio method |
| `orchestrator/engine/campaign_runner.py` | Branch: if `media_type == "audio"`, skip variant generation, score the uploaded file directly |
| `orchestrator/storage/campaign_store.py` | Add `media_type`, `media_file_id`, `media_duration_seconds` columns |
| `orchestrator/storage/database.py` | Migration: ALTER TABLE campaigns ADD COLUMN media_type, media_file_id, media_duration_seconds |

**UI Layer:**

| File | Change |
|------|--------|
| `ui/src/api/types.ts` | Add `media_type`, `media_file_id`, `generate_variants` to `CampaignCreateRequest` |
| `ui/src/api/client.ts` | Add `uploadMediaFile(file: File)` function using FormData |
| `ui/src/components/campaign/campaign-form.tsx` | Add media type toggle (Text / Audio), file upload dropzone for audio, file metadata display (duration, size, format) |
| `ui/src/components/campaign/campaign-form.tsx` | Conditional: hide seed_content textarea when media_type is audio; show upload area instead |
| `ui/src/components/results/` | Audio playback component: `<audio>` element with waveform visualization alongside scoring data |

**File Storage:**

Local filesystem at `uploads/` directory (no S3 for POC). Files stored as `{campaign_id}/{file_id}.{ext}`. Served via a static file endpoint for UI playback.

| File | Change |
|------|--------|
| `orchestrator/storage/file_store.py` | New module: `save_upload(file, campaign_id) -> file_id`, `get_file_path(file_id) -> Path`, `delete_file(file_id)` |
| `orchestrator/api/campaigns.py` | `GET /api/campaigns/{id}/media` endpoint serving the uploaded file |

#### Execution Order (within A.1)

1. **Sequential:** Database migration (media columns) -- must land first
2. **Sequential:** File storage module
3. **Parallel:** TRIBE scorer `score_audio()` + orchestrator client `score_audio()` -- independent code paths
4. **Sequential:** Campaign runner branching (depends on both above)
5. **Sequential:** API schema + upload endpoint (depends on file store + campaign runner)
6. **Parallel:** UI form changes + UI audio playback component -- independent of backend
7. **Sequential:** Wire UI to backend, end-to-end test

#### Success Criteria

1. Upload a 60-second WAV file via UI, campaign runs, produces 7 neural dimension scores
2. `is_pseudo_score` is False for the audio file (real Wav2Vec-BERT inference)
3. Audio playback works in the results view
4. MiroFish simulation runs on a text transcript extracted during TRIBE processing (or skips if transcript unavailable)
5. `data_completeness` correctly reports the audio campaign's system availability
6. All 205 existing tests still pass

#### Validation Strategy

1. Upload a known audio file (podcast excerpt, 60s WAV)
2. Run campaign with audio input, verify scores returned
3. Compare audio scores to text scores of the transcript -- they should differ meaningfully (audio captures prosody, pacing, tone that text lacks)
4. Test with unsupported format (e.g., .aac) -- verify clear error message

#### Rollback Plan

Revert all A.1 changes. Database migration must be backward-compatible (new columns are nullable). Text campaigns continue to work exactly as before.

---

### A.2: Video Input Support

**Goal:** Users can upload a video file, route it to TRIBE v2's V-JEPA2 pipeline, and see video-specific scoring results.
**Priority:** P1 - second multimodal modality.
**Blocked on:** A.1 (shares file upload infrastructure, media type schema, campaign runner branching).
**Tag:** `phase2-a2-complete`

#### What Already Exists

TRIBE v2's `get_events_dataframe(video_path=...)` already works. The pipeline:
1. Video file --> ExtractAudioFromVideo (moviepy --> .wav)
2. Audio + Video --> ChunkEvents (30-60s segments each)
3. Audio chunks --> WhisperX (word transcription)
4. Video chunks --> V-JEPA2-ViTg (4s clip features at 2 Hz, layers 0.75 and 1.0)
5. All features --> FmriEncoder --> cortical predictions

**VRAM concern:** V-JEPA2-ViTg uses ~4-6 GB. Combined with LLaMA 3.2-3B (~6 GB) and the brain model, total is ~10-12 GB. This is at the limit of the RTX 5070 Ti (12.2 GB). GPU memory management from B.1 and B.2 is critical.

#### What Needs to Be Built

| File | Change |
|------|--------|
| `tribe_scorer/scoring/media_scorer.py` | Add `score_video(video_path, model)` function. Uses `get_events_dataframe(video_path=path)`. Same predict/merge as audio |
| `tribe_scorer/scoring/media_scorer.py` | Add `_pseudo_score_from_video(video_path)` -- duration + motion heuristics (ffprobe for metadata, frame diff for motion estimate) |
| `tribe_scorer/main.py` | Add `POST /api/score/video` endpoint. Larger timeout (60 min default). Max file size limit (500 MB) |
| `tribe_scorer/config.py` | Add `VIDEO_FORMATS` (.mp4, .avi, .mkv, .mov, .webm) and `VIDEO_MAX_DURATION_S` (180s = 3 min for POC) |
| `orchestrator/clients/tribe_client.py` | Add `score_video(file_path)` method with extended timeout |
| `orchestrator/engine/tribe_scorer.py` | Add `score_video_file(file_path)` |
| `orchestrator/engine/campaign_runner.py` | Extend branching: `media_type == "video"` routes to video scoring |
| `ui/src/components/campaign/campaign-form.tsx` | Extend media toggle: Text / Audio / Video. Video upload dropzone with preview thumbnail |
| `ui/src/components/results/` | Video playback component: `<video>` element with frame-by-frame scrubbing aligned to score timeline |

#### VRAM Budget Decision Point

The RTX 5070 Ti has 12.2 GB VRAM. Combined text + audio + video inference exceeds this budget: LLaMA 3.2-3B (~6-8 GB) + Wav2Vec-BERT (~2-3 GB) + V-JEPA2-ViTg (~4-6 GB) = ~12-17 GB. Running all three simultaneously is not feasible.

**Before starting A.2 implementation, decide between three strategies:**

**(a) Sequential modality loading.** Unload the text/audio model before loading V-JEPA2 for video inference. Pro: full V-JEPA2 quality. Con: adds model load/unload time (~30-60s per swap), complicates the inference lock, and the TRIBE v2 vendor code may not support dynamic model swapping without process restart.

**(b) CPU fallback for video inference specifically.** Run V-JEPA2 on CPU while text/audio stay on GPU. Pro: no VRAM contention. Con: V-JEPA2 on CPU will be extremely slow (likely 10-100x slower than GPU), making video campaigns impractically long on laptop hardware.

**(c) Keyframe extraction + DINOv2 image fallback.** Extract keyframes from the video, score them using the `image_feature` config (DINOv2-large, ~1-2 GB VRAM) instead of full V-JEPA2 temporal analysis. Pro: fits in VRAM, reasonably fast. Con: loses temporal/motion information that V-JEPA2 captures -- the brain encoding will reflect static visual features only, not how motion and pacing affect neural response.

**This decision is deferred until A.2 kickoff** because it depends on what we learn during A.1 (audio): actual VRAM usage during Wav2Vec-BERT inference, whether model unloading is feasible in practice, and whether the TRIBE v2 vendor code supports partial model loading. Measure first, decide second.

#### GPU Memory Management for Video

V-JEPA2 + LLaMA is tight on 12 GB. Mitigation (applies regardless of VRAM strategy chosen above):
1. TRIBE scorer checks free VRAM before video inference (reuse B.2 health probe)
2. If <8 GB free, return 503 with clear message: "Insufficient GPU memory for video inference. Stop Ollama and retry."
3. Video scoring is sequential (inference lock prevents overlapping), so no concurrent VRAM pressure from parallel requests

#### Success Criteria

1. Upload a 60-second MP4 file via UI, campaign runs, produces 7 neural dimension scores
2. `is_pseudo_score` is False for the video file (real V-JEPA2 + Wav2Vec inference)
3. Video playback works in results view
4. Audio track is extracted and also scored (video includes both modalities)
5. V-JEPA2 VRAM usage stays within budget (verify with nvidia-smi during inference)
6. All existing tests still pass + A.1 tests still pass

#### Validation Strategy

1. Upload a known video file (30-60s clip with speech)
2. Run campaign, verify video and audio scores both returned
3. Test with a silent video (no audio track) -- verify graceful handling
4. Test with a video exceeding duration limit -- verify clear error
5. Monitor GPU memory during inference: `nvidia-smi -l 1`

#### Rollback Plan

Revert A.2 changes. Audio (A.1) and text campaigns continue to work. Video scoring endpoint removed.

---

### A.3: Unified Media Playback in Results

**Goal:** Audio and video play inline with scoring data in the Simulation and Report tabs.
**Priority:** P2 - UX improvement, not functionally blocking.
**Blocked on:** A.2 (needs both audio and video support in place).
**Tag:** `phase2-a3-complete`

#### Scope

| File | Change |
|------|--------|
| `ui/src/components/results/score-card.tsx` | Add media player alongside score visualization. Player syncs to score timeline. |
| `ui/src/components/results/iteration-chart.tsx` | For media campaigns: replace iteration comparison with single-media deep analysis (no iterations for media input) |
| `ui/src/components/simulation/` | MiroFish simulation results rendered alongside media player. Agent reactions shown on a timeline synchronized to media playback position |
| `ui/src/components/report/` | Report layers reference specific timestamps in the media where neural activation peaks occur |

#### Success Criteria

1. Audio campaigns show waveform + playback in results view
2. Video campaigns show video player + playback in results view
3. Scrolling through scoring timeline highlights corresponding position in media player
4. Report mentions specific timestamps (e.g., "attention peaks at 0:23-0:31")

#### Validation Strategy

Manual UI testing with both audio and video campaigns. Verify playback controls work, timeline sync is responsive.

#### Rollback Plan

Remove UI components. Scoring data still displays without inline playback.

---

## 5. Track C: Calibration Against Real-World Data

### C.1: Design Calibration Framework

**Goal:** Define what "accurate prediction" means, what metrics compare, and how experiments are structured.
**Priority:** P1 - design work, no code changes.
**Blocked on:** Nothing (can start in parallel with A.1).
**Tag:** `phase2-c1-complete`

#### Deliverable

`docs/calibration_framework.md` containing:

1. **Prediction-outcome mapping:** Which TRIBE dimensions map to which real-world outcomes?
   - `attention_capture` --> view-through rate, time-on-page
   - `emotional_resonance` --> comment sentiment, engagement rate
   - `memory_encoding` --> brand recall (survey data), repeat visits
   - `virality_potential` (composite) --> share rate, organic reach
   - `backlash_risk` (composite) --> negative coverage, crisis response

2. **Ground truth sources:** What counts as "real outcome data"?
   - Public metrics: view counts, share counts, engagement rates (from social platforms)
   - Media coverage: sentiment of press coverage (positive/negative/neutral)
   - Market impact: stock price movement for public companies (for product launches)
   - Survey data: if available from published research

3. **Experiment protocol:**
   - Input: historical content + known outcome
   - Process: run through A.R.C Studio, record predictions
   - Compare: predicted composite scores vs actual outcomes
   - Metric: Spearman rank correlation between predicted and actual for each dimension
   - Threshold: rho > 0.3 is "directionally accurate", rho > 0.5 is "predictively useful"

4. **Statistical considerations:**
   - Sample size: 15-20 campaigns minimum for meaningful correlation
   - Confidence intervals via bootstrap
   - Multiple testing correction (7 dimensions)

#### Success Criteria

1. Framework document is complete and peer-reviewed
2. Another developer could execute calibration experiments by following the document
3. Statistical methodology is sound (not p-hacking or cherry-picking)

#### Validation Strategy

Self-review against published methodology for prediction validation (e.g., Tetlock's superforecasting framework). Verify that the experiment protocol section is concrete enough that a second developer could execute it without additional guidance.

#### Rollback Plan

Delete the document. No code impact.

---

### C.2: Curate Calibration Dataset

**Goal:** 15-20 historical campaigns with known outcomes, across text, audio, and video modalities.
**Priority:** P1 - the dataset.
**Blocked on:** A.1 at minimum (need audio support to include audio campaigns), ideally A.2 (video).
**Tag:** `phase2-c2-complete`
**Estimated effort:** 7-14 days.

**Why this takes longer than it sounds:** Curating real historical campaigns with documented outcomes AND reconstructable original stimuli is significantly harder than finding case studies. Most viral campaign analyses describe outcomes in aggregate ("X million views") without preserving the exact content that caused them. The original ad may be pulled, re-edited, or only available as a reaction video. Outcome data may be self-reported by the brand (unreliable), reported by different outlets with conflicting numbers, or measured on metrics that don't map cleanly to TRIBE dimensions. For each of the 15-20 entries, expect to spend time: (1) finding the original content in a usable format, (2) cross-referencing outcome data across multiple sources, (3) verifying legal usability, and (4) structuring everything into the required JSON format. Budget accordingly.

#### Dataset Requirements

Each entry needs:
1. **Input content:** The original campaign material (text, audio clip, video clip)
2. **Context:** Target audience, platform, date, campaign objectives
3. **Outcome data:** Measurable real-world results (views, shares, engagement, sentiment, market impact)
4. **Category tags:** success/failure, modality, industry, controversy level

#### Candidate Categories (3-4 per category)

| Category | Example | Outcome Signal |
|----------|---------|----------------|
| **Viral successes** | Dove "Real Beauty" (video), ALS Ice Bucket Challenge (video), Spotify Wrapped (mixed) | View count, share rate, media coverage |
| **Documented flops** | Pepsi Kendall Jenner ad (video), Bud Light partnership controversy | Negative sentiment, boycott metrics, stock impact |
| **PSAs** | "This is your brain on drugs" (video), COVID vaccination campaigns | Behavior change metrics, recall surveys |
| **Product launches** | Apple iPhone reveals (text+video), Tesla Cybertruck reveal (video) | Pre-order numbers, stock movement, media sentiment |
| **Political/Policy** | Campaign ads with documented polling impact | Polling movement, engagement metrics |

#### Deliverable

`scenarios/calibration/` directory with:
- `index.json` -- metadata for all entries
- `{category}/{name}/input.{txt,wav,mp4}` -- the content
- `{category}/{name}/outcome.json` -- ground truth metrics
- `{category}/{name}/context.json` -- audience, platform, date

#### Success Criteria

1. 15+ entries with complete input + outcome data
2. Mix of modalities: at least 5 text, 3 audio, 5 video
3. Mix of outcomes: at least 5 successes, 5 failures, 5 mixed/neutral
4. All content is legally usable (public domain, fair use for research, or Creative Commons)

#### Validation Strategy

1. Spot-check 3 entries across different categories: verify input file plays/reads correctly, outcome.json has non-empty metrics, context.json has all required fields
2. Verify legal usability: each entry has a source URL and a license/fair-use justification documented in `context.json`
3. Cross-check outcome data against at least one independent public source per entry

#### Rollback Plan

Delete the `scenarios/calibration/` directory. No code impact -- calibration scripts (C.3) do not exist yet.

---

### C.3: Run Calibration Experiments

**Goal:** Feed each historical campaign into A.R.C Studio, compare predictions against ground truth.
**Priority:** P2 - requires everything above.
**Blocked on:** C.2 + A.1 (minimum), A.2 (full coverage).
**Tag:** `phase2-c3-complete`

#### Scope

| File | Change |
|------|--------|
| `scripts/run_calibration.py` | New script: iterates over calibration dataset, runs each through the pipeline, collects predictions |
| `scripts/analyze_calibration.py` | New script: compares predictions to ground truth, computes correlations, generates report |
| `results/calibration/` | Output directory for prediction results and analysis |

#### Process

1. For each calibration entry: run A.R.C Studio campaign (1 iteration, no variant generation for media, text variant generation for text)
2. Extract: 7 TRIBE dimensions + 7 composite scores + MiroFish metrics
3. Compare: predicted scores vs actual outcomes using prediction-outcome mapping from C.1
4. Compute: Spearman rank correlation per dimension, with 95% CI via bootstrap
5. Generate: correlation matrix, scatter plots, summary statistics

#### Success Criteria

1. All 15+ calibration entries run successfully
2. Results are reproducible (same entry, same scores)
3. At least 3/7 composite dimensions show rho > 0.3 (directionally accurate)
4. Any dimension with rho < 0.1 is flagged for investigation

#### Validation Strategy

1. Re-run 2 calibration entries from scratch, confirm scores match prior run within tolerance (correlation > 0.99 for deterministic pipeline, > 0.90 for stochastic elements)
2. Verify statistical output: check that bootstrap CIs are computed correctly by comparing one dimension's CI to a manual calculation
3. Run a random-baseline comparison: generate random scores for each entry, compute correlation -- verify real scores outperform random

#### Rollback Plan

Delete `results/calibration/` and `scripts/run_calibration.py`, `scripts/analyze_calibration.py`. Dataset (C.2) is unaffected. No impact on production code.

---

### C.4: Publish Calibration Report

**Goal:** Add calibration results to the README as scientific validation evidence.
**Priority:** P2 - the payoff.
**Blocked on:** C.3.
**Tag:** `phase2-c4-complete`

#### Scope

| File | Change |
|------|--------|
| `README.md` | Add "Calibration Results" section with correlation table, methodology summary, and limitations |
| `docs/calibration_report.md` | Full report: methodology, results per dimension, scatter plots, confidence intervals, discussion of failures, comparison to random baseline |

#### Success Criteria

1. README calibration section is honest (reports failures alongside successes)
2. Methodology is reproducible (another team could replicate with the same dataset)
3. Results include confidence intervals, not just point estimates
4. Limitations section acknowledges small sample size, selection bias, and modality coverage gaps

#### Validation Strategy

1. Independent review: have someone unfamiliar with the project read the README calibration section and flag any claims that seem unsupported by the data
2. Verify every number in the README matches the full report in `docs/calibration_report.md`
3. Confirm confidence intervals and correlation values trace back to `results/calibration/` raw output

#### Rollback Plan

Revert README changes (remove calibration section). Delete `docs/calibration_report.md`. Calibration data and experiment results (C.2, C.3) are unaffected.

---

## 6. Critical Path Analysis

**Critical path duration estimate (total):**

| Sub-phase | Dependency | Estimated Effort | Cumulative |
|-----------|-----------|-----------------|------------|
| B.1 | None | 3-4 days | 3-4 days |
| A.1 | B.1 | 5-7 days | 8-11 days |
| A.2 | A.1 | 3-4 days | 11-15 days |
| C.2 | A.1 + A.2 | 7-14 days | 18-29 days |
| C.3 | C.2 | 2-3 days | 20-32 days |
| C.4 | C.3 | 1-2 days | 21-34 days |

**Parallel work (off critical path):**

| Sub-phase | Can start | Estimated Effort |
|-----------|----------|-----------------|
| B.2 | Immediately | 1-2 days |
| B.3 | Immediately | 0.5 days |
| B.4 | Immediately | 1-2 days |
| B.5 | Immediately | 0.5 days |
| A.3 | After A.2 | 2-3 days |
| C.1 | Immediately | 1-2 days |

**Recommended execution sequence:**

```
Week 1:  B.1 (timeout fix) || B.2 + B.3 + B.4 + B.5 + C.1 (all parallel)
Week 2:  A.1 (audio - TRIBE scorer + orchestrator backend)
Week 3:  A.1 (audio - UI + integration) || C.2 start (dataset curation)
Week 4:  A.2 (video input) || C.2 continues
Week 5:  A.3 (media playback) || C.2 continues
Week 6:  C.2 continues (dataset curation is the long pole)
Week 7:  C.2 finish || C.3 start (experiments)
Week 8:  C.3 finish || C.4 (report)
```

---

## 7. Risk Analysis

### Risk 1: V-JEPA2 VRAM Exceeds Budget

**Probability:** Medium
**Impact:** High -- video scoring fails on RTX 5070 Ti
**Detection:** `nvidia-smi` during first video inference test
**Mitigation:**
- Test V-JEPA2 VRAM usage early (during B.1 or A.1 implementation)
- If too large: use the `image_feature` config (DINOv2-large, ~1-2 GB) as a lighter video alternative
- Fallback: video scoring available only on GPUs with >16 GB VRAM, documented clearly

### Risk 2: WhisperX Compatibility with Audio Inputs

**Probability:** Low (already works for TTS-generated audio in text pipeline)
**Impact:** Medium -- audio scoring degrades to pseudo-scores
**Detection:** First audio scoring test
**Mitigation:**
- Test with diverse audio formats (.wav, .mp3) early
- If codec issues: require WAV format, add FFmpeg conversion step

### Risk 3: Chunking Distorts Brain-Encoding Predictions

**Probability:** Low (TRIBE v2 already chunks audio/video internally)
**Impact:** Medium -- text scoring accuracy decreases
**Detection:** Correlation test between chunked and monolithic scores (B.1 validation)
**Mitigation:**
- If correlation < 0.90: increase chunk overlap (e.g., 50-word overlap between chunks)
- If still poor: abandon text chunking for B.1, increase timeout and accept longer runtimes

### Risk 4: Calibration Dataset Selection Bias

**Probability:** High (inevitable with hand-curated datasets)
**Impact:** Medium -- calibration results are misleading
**Detection:** Review by domain expert
**Mitigation:**
- Transparent methodology: document selection criteria and acknowledge bias
- Include failure cases (not just successes)
- Use rank correlation (Spearman, not Pearson) which is robust to outliers

### Risk 5: MiroFish Doesn't Handle Audio/Video Content

**Probability:** Medium
**Impact:** Low (MiroFish can work with transcript text extracted by WhisperX)
**Detection:** First multimodal campaign test
**Mitigation:**
- Extract transcript from WhisperX step, feed to MiroFish as text content
- If no transcript (silent video): skip MiroFish, report `mirofish_available: false` in `data_completeness`

### Risk 6: Phase 1 Regression

**Probability:** Low (strong test suite, 205 tests)
**Impact:** High -- working system breaks
**Detection:** CI test suite after every sub-phase
**Mitigation:**
- Run full test suite before every tagged commit
- Run canonical Price Increase scenario after each sub-phase checkpoint
- Database migrations are additive (new nullable columns), never destructive
- Each sub-phase has explicit rollback plan

---

## 8. Minimum Viable Phase 2

**Your hypothesis:** B.1 (fixes core reliability) + A.1 (unlocks audio use cases) + C.1-C.2 (calibration framework even without full experiments).

**My assessment: Validated, with one modification.**

The hypothesis is correct. Here's why:

| Sub-phase | Value | Cost | Verdict |
|-----------|-------|------|---------|
| **B.1** (TRIBE timeout) | Eliminates #1 reliability issue, unblocks Track A | 3-4 days | Must-have |
| **A.1** (Audio input) | First multimodal capability, concrete use cases (podcast ads, voiceovers, PSAs) | 5-7 days | Must-have |
| **C.1** (Calibration framework) | Design work, no code dependency | 1-2 days | Must-have |
| **C.2** (Calibration dataset) | The dataset has value even without running experiments | 7-14 days | Must-have |

**Modification: Add B.5 (Docker health checks) to the MVP.**

B.5 is a 0.5-day change (add 6 lines to `docker-compose.yml`) that eliminates the MiroFish restart problem (Issue 17 -- 17 restarts per 4-hour session). The ROI is extremely high: 30 minutes of work saves hours of manual restarts across every future session. Excluding it from MVP would be false economy.

**MVP scope: B.1 + B.5 + A.1 + C.1 + C.2**

**MVP estimated effort: 17-28 days**

**What this MVP delivers:**
- Zero pseudo-score fallbacks on standard text variants (B.1)
- Docker services auto-restart on failure (B.5)
- Audio input support end-to-end (A.1)
- Calibration framework designed and dataset curated (C.1 + C.2)
- All Phase 1 functionality preserved

**What this MVP defers:**
- B.2 (CUDA recovery) -- still a bandaid (manual restart), but now loudly flagged
- B.3 (PyTorch docs) -- documentation, can happen anytime
- B.4 (Neo4j monitoring) -- not triggered yet
- A.2 (Video input) -- higher VRAM risk, harder to validate
- A.3 (Media playback) -- UX polish
- C.3-C.4 (Experiments + report) -- need more data first

---

## 9. Out-of-Scope: Phase 3 Deferrals

| Item | Reason for Deferral |
|------|-------------------|
| **Multi-user support / authentication** | Phase 1 POC scope. Single-user is explicitly in scope. Adding auth is a separate architectural decision. |
| **Hosted deployment (cloud)** | Requires infrastructure decisions (AWS/GCP, GPU instance types, S3, managed Neo4j). Solo developer can't maintain cloud infra alongside feature work. |
| **Concurrent campaign execution** | Landmine 4 (Neo4j D-04 constraint). Requires campaign-level locking, queue management, and Neo4j schema changes. POC is single-campaign-at-a-time. |
| **Real-time streaming for multimodal** | Live audio/video input (microphone, webcam) is a fundamentally different architecture. Phase 2 is file upload only. |
| **Extended demographic presets** | Current 6 presets are sufficient for POC + calibration. More presets after calibration validates the existing ones work. |
| **Expanded MiroFish agent count** | 100+ agents produce richer simulations but proportionally longer runtimes. Optimize performance first (B.1), then scale. |
| **Process supervisor (PM2/systemd)** | B.5 Docker health checks cover the Docker services. TRIBE scorer and orchestrator are bare processes -- adding a full process supervisor is a Phase 3 operational maturity item. |
| **GPU memory auto-management** | Automatically stopping/starting Ollama based on TRIBE needs is fragile. For POC: document the requirement (stop Ollama before TRIBE), add GPU pre-flight check. |
| **SQLite to PostgreSQL migration** | SQLite is fine for single-user. Migrate only if concurrent campaigns are needed (Phase 3). |
| **CI/CD pipeline** | Solo developer running locally. CI adds value when there are contributors or deployments to manage. |

---

## Appendix: Technical Reference

### TRIBE v2 Multimodal Feature Extractors

| Modality | Model | VRAM | Default Timeout | Event Type |
|----------|-------|------|----------------|------------|
| Text | LLaMA 3.2-3B (HuggingFace) | ~6-8 GB | 12h (training) | Word |
| Audio | Wav2Vec-BERT | ~2-3 GB | 12h (training) | Audio |
| Video | V-JEPA2-ViTg-fpc64-256 | ~4-6 GB | 24h (training) | Video |
| Image | DINOv2-large | ~1-2 GB | 12h (training) | Video (fallback) |

### File Format Support

| Format | Modality | Supported | Notes |
|--------|----------|-----------|-------|
| .txt | Text | Yes (existing) | UTF-8 encoded |
| .wav | Audio | Phase 2 A.1 | Preferred -- no transcoding needed |
| .mp3 | Audio | Phase 2 A.1 | Requires FFmpeg for WhisperX |
| .flac | Audio | Phase 2 A.1 | Lossless, larger files |
| .ogg | Audio | Phase 2 A.1 | Vorbis codec |
| .mp4 | Video | Phase 2 A.2 | H.264/H.265 |
| .avi | Video | Phase 2 A.2 | Legacy format |
| .mkv | Video | Phase 2 A.2 | Matroska container |
| .mov | Video | Phase 2 A.2 | QuickTime |
| .webm | Video | Phase 2 A.2 | VP9 codec |

### Key File Paths

| Component | Path | Role |
|-----------|------|------|
| TRIBE text scorer | `tribe_scorer/scoring/text_scorer.py` | Current entry point, becomes `media_scorer.py` |
| TRIBE FastAPI service | `tribe_scorer/main.py` | Endpoints, inference lock, health check |
| TRIBE vendor code | `tribe_scorer/vendor/tribev2/tribev2/demo_utils.py` | `get_events_dataframe()`, `TribeModel` |
| TRIBE defaults | `tribe_scorer/vendor/tribev2/tribev2/grids/defaults.py` | Model configs per modality |
| Orchestrator TRIBE client | `orchestrator/clients/tribe_client.py` | HTTP client, timeout, retry |
| Campaign runner | `orchestrator/engine/campaign_runner.py` | Pipeline orchestration |
| API schemas | `orchestrator/api/schemas.py` | Request/response models |
| Docker compose | `docker-compose.yml` | Service definitions |
| UI campaign form | `ui/src/components/campaign/campaign-form.tsx` | Campaign creation |
| UI types | `ui/src/api/types.ts` | TypeScript interfaces |

### Phase 1 Hardening Artifacts to Preserve

| Artifact | Location | Phase 2 Impact |
|----------|----------|---------------|
| `is_pseudo_score` flag | End-to-end (TRIBE -> orchestrator -> UI) | Must work for audio/video too |
| `data_completeness` | `orchestrator/engine/campaign_runner.py`, `orchestrator/api/schemas.py` | Extend with `media_type` info |
| `organic_shares` regression test | `orchestrator/tests/test_composite_scorer.py` | No change needed |
| GPU pre-flight check | `tribe_scorer/main.py` | Extended by B.2 CUDA probe |
| ThreadPool non-blocking shutdown | `tribe_scorer/scoring/text_scorer.py` | Preserved in chunking implementation |
| MiroFish polling timeout (600s) | `orchestrator/clients/mirofish_client.py` | No change needed |
| Stale campaign cleanup | `orchestrator/storage/campaign_store.py` | No change needed |

### Checkpoint Tags

| Tag | Gate | Validation |
|-----|------|-----------|
| `phase2-b1-complete` | TRIBE timeout fix | 500-word text scores without pseudo-fallback |
| `phase2-b2-complete` | CUDA recovery | Health probe detects sleep/wake corruption |
| `phase2-b3-complete` | PyTorch docs | Document exists and is accurate |
| `phase2-b4-complete` | Neo4j monitoring | Health endpoint shows heap metrics |
| `phase2-b5-complete` | Docker health checks | All services auto-restart on failure |
| `phase2-a1-complete` | Audio input | 60s WAV file scores end-to-end |
| `phase2-a2-complete` | Video input | 60s MP4 file scores end-to-end |
| `phase2-a3-complete` | Media playback | Audio/video play inline with results |
| `phase2-c1-complete` | Calibration framework | Framework document complete |
| `phase2-c2-complete` | Calibration dataset | 15+ entries curated |
| `phase2-c3-complete` | Calibration experiments | All entries run, correlations computed |
| `phase2-c4-complete` | Calibration report | README updated with results |
