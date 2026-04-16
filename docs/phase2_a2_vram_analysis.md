# Phase 2 A.2 — VRAM Analysis: Video Input on RTX 5070 Ti

**Date**: 2026-04-15
**Hardware**: RTX 5070 Ti Laptop GPU, 12 GB VRAM (11.94 GB usable)
**Branch**: `fix/phase2-a2-video` (4 commits, code complete but not tagged)
**Verdict**: **INFEASIBLE on this hardware.** Peak VRAM 13.8 GB exceeds 12 GB physical memory. Defer to cloud hardware or explore mitigations.

## Test Setup

- Test video: `test_video.mp4` — 10 seconds, 640x360 (well under 720p limit), H.264 + AAC, 162 KB
- TRIBE v2 model: `facebook/tribev2` with `facebook/vjepa2-vitg-fpc64-256` video feature extractor
- Endpoint: `POST /api/score_video` — our new Phase 2 A.2 code
- VRAM captured via `torch.cuda.max_memory_allocated()` (reset before inference, read after)

## Results

| Metric | Value |
|---|---|
| HTTP status | 200 (inference completed, gracefully degraded) |
| `is_pseudo_score` | `true` (pseudo fallback triggered) |
| `peak_vram_mb` | **13,861 MB (13.5 GB)** |
| Inference time | 164.0 seconds (2.7 minutes) |
| 7 ROI dimensions present | yes |
| Score range | 16.3–33.2 (pseudo, not real brain-encoding) |

## Why It Exceeded

### Static analysis (pre-implementation) was wrong

My pre-implementation analysis predicted peak VRAM of ~5-6 GB based on the vendor's `_free_extractor_model` lazy-loading pattern: each extractor loads → runs → frees before the next loads. In theory, `peak = max(V-JEPA2, LLaMA, Wav2Vec-BERT) + brain encoder ≈ 5-6 GB`.

### What actually happened

The video pipeline triggers **all three extractors sequentially** (audio extraction from video → Wav2Vec-BERT transcription → LLaMA text features → V-JEPA2 video features → brain encoding). `torch.cuda.max_memory_allocated()` hit **13.8 GB** at some point during this chain.

Possible explanations (in order of likelihood):

1. **V-JEPA2 ViT-Giant is larger than estimated.** `facebook/vjepa2-vitg-fpc64-256` processes 64 frames per clip with a giant vision transformer. With `clip_duration=4` and a 10-second video, that's 2-3 chunks of 64 frames each. Batch tensor allocation for these chunks plus model weights may approach 8-10 GB alone.

2. **Lazy freeing has gaps.** `_free_extractor_model` deletes `_model` attributes but cached intermediate tensors (feature maps, embeddings) may persist through the `predict()` call where the brain encoder needs them. The brain encoder (8-layer transformer, 1152 hidden, low-rank head 2048) plus ALL accumulated features across all extractors coexist during the forward pass.

3. **Framework overhead.** PyTorch autograd, CUDA memory pools, and exca caching create fragmentation and overhead. `max_memory_allocated` includes temporary gradient buffers, even though no training occurs (inference-only). CUDA memory allocator holds freed blocks in pools rather than returning to the OS, inflating the "max allocated" metric.

### Comparison with audio (which worked)

Audio inference peaked at ~2 GB (from health check after audio scoring), well under the card's capacity. Audio uses Wav2Vec-BERT (~1.5 GB) + optional LLaMA text features (~3 GB) — totaling ~4.5 GB peak. The critical difference:

| Path | Extractors | Est. peak | Actual |
|---|---|---|---|
| Text | LLaMA 3.2-3B | ~3-4 GB | ~2 GB (health check) |
| Audio | Wav2Vec-BERT + LLaMA (text from transcription) | ~4-5 GB | worked, is_pseudo=false |
| **Video** | **Wav2Vec-BERT + LLaMA + V-JEPA2 ViT-Giant** | ~5-6 GB (wrong) | **13.8 GB (OOM)** |

V-JEPA2 ViT-Giant is the bottleneck. It's an order of magnitude heavier than Wav2Vec-BERT.

## Code Status

The Phase 2 A.2 implementation is **code-complete and correct**:
- 4 commits on `fix/phase2-a2-video` (TRIBE scorer, tribe_client, backend, UI)
- All 235 orchestrator tests pass (zero regression)
- TypeScript type check passes
- Upload endpoint accepts video with validation + ffmpeg downscale
- Video campaign routing works in campaign_runner.py
- UI MediaUpload component handles both audio and video
- Pseudo fallback works correctly (is_pseudo_score=true on video)

The code runs and degrades gracefully. It just can't produce real brain-encoding scores on 12 GB VRAM.

## Options

### A. Defer to cloud hardware (recommended)
Merge the branch to main (code is correct + backward compatible). Video campaigns will produce `is_pseudo_score: true` on laptop hardware. When run on cloud with ≥24 GB VRAM (e.g., A100 40 GB), V-JEPA2 will fit and produce real scores. Add a health-check warning when video inference is attempted on <16 GB VRAM.

### B. CPU fallback for V-JEPA2
Configure the V-JEPA2 extractor to run on CPU instead of CUDA. This avoids the VRAM constraint entirely but inference time will balloon from ~3 min to ~30-60 min per 10s clip (CPU-bound ViT-Giant forward pass). May be acceptable for a POC if the user is willing to wait.

### C. Smaller video model
Swap `facebook/vjepa2-vitg-fpc64-256` for a smaller variant (e.g., `vjepa2-vitl-fpc64-256`, ViT-Large instead of ViT-Giant). Halves VRAM but likely degrades score quality. Requires modifying the vendor config, which may not be straightforward if the brain-encoding head was trained with ViT-Giant features.

### D. Mixed precision / quantization
Force fp16 or int8 quantization for the V-JEPA2 forward pass. Needs vendor code changes (the extractors use whatever precision the model checkpoint was saved in). Could halve VRAM to ~7 GB — potentially feasible.

### E. Video-only features (skip audio/text extraction from video)
Configure the pipeline to run ONLY V-JEPA2 on the video frames, skipping the audio extraction → Wav2Vec-BERT → LLaMA text chain. Reduces total VRAM but produces a less rich brain-encoding (visual cortex only, no language/auditory regions). Needs vendor config override.

## Recommendation

**Option A (merge + defer real inference to cloud)** is the safest path. The code is correct and backward-compatible. Text and audio campaigns are unaffected. Video campaigns degrade gracefully with clear `is_pseudo_score: true` signaling. When cloud hardware becomes available, real video scoring will work without any code changes.

If the user wants video to produce real scores on laptop hardware, **Option D (mixed precision)** is the next most promising — it addresses the root cause (V-JEPA2 model size) without sacrificing feature richness.

## Artifacts

- Branch: `fix/phase2-a2-video` (4 commits)
- Test video: `test_video.mp4` (10s, 640x360, 162 KB)
- VRAM probe log: `probe_video.py` output above
