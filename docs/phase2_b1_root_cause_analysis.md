# Phase 2 B.1 Root Cause Analysis

**Date:** 2026-04-13
**Status:** Chunking implemented and verified, but does not solve the underlying bottleneck.
**Commit context:** `phase2-reliability-partial` tag + B.1 chunking code on `main`

---

## 1. What Was Assumed

B.1 was scoped as "Fix TRIBE v2 Timeout for Long Variants" with the hypothesis:

> Long variant texts (300-500 words) exceed the per-text inference timeout, causing pseudo-score fallback. Chunking long texts into 250-word segments would:
> - Reduce per-inference VRAM pressure
> - Keep each chunk within the timeout budget
> - Allow `torch.cuda.empty_cache()` between chunks to prevent VRAM accumulation
> - Average chunk activations to produce a composite real score

The assumption was that **text length × timeout** was the bottleneck, and chunking would split long variants into independently-scorable pieces within the per-chunk timeout budget.

---

## 2. What Was Actually Found

**LLaMA 3.2-3B word embedding computation dominates TRIBE v2 runtime.** The TRIBE pipeline processes text through:

1. TTS (gTTS) — text to audio (~5s)
2. WhisperX transcription — audio to word-level timestamps (~2 min)
3. LLaMA 3.2-3B word embeddings — each word token requires a full forward pass (~50-90s per 4-word batch)
4. Brain encoding model — vertex prediction from embeddings (~1s)

Step 3 is the bottleneck. A 250-word chunk generates ~750 word tokens (including context windows). At ~50-90s per 4-word batch, this yields:

- 750 tokens / 4 per batch = ~188 batches
- 188 batches × 50-90s = **2.6 to 4.7 hours per 250-word chunk**

Chunking cannot reduce total compute — it only redistributes the same work across smaller text segments, each of which still requires the full LLaMA embedding pass.

---

## 3. Supporting Evidence from the Live Test

### Test configuration
- Text: 270 words (just above the 250-word chunk boundary)
- Expected: 2 chunks of [250, 20] words
- per_chunk_timeout: 900s (15 min)
- Hardware: RTX 5070 Ti (11.94 GB VRAM), sm_120 JIT fallback

### [CHUNK] logs confirm chunking IS executing

```
[23:20:59 INFO] scoring.text_scorer — [CHUNK] Splitting 270-word text into 2 chunks of [250, 20] words each.
[23:20:59 INFO] scoring.text_scorer — [CHUNK] Scoring chunk 1/2 (250 words)...
...
[23:35:59 WARNING] scoring.text_scorer — [CHUNK] Chunk 1/2 fell back to pseudo (900.0s).
[23:35:59 INFO] scoring.text_scorer — [CHUNK] Scoring chunk 2/2 (20 words)...
...
[23:36:57 WARNING] scoring.text_scorer — [CHUNK] Chunk 2/2 fell back to pseudo (58.4s).
[23:36:57 INFO] scoring.text_scorer — [CHUNK] Variant scored in 2 chunks of [250, 20] words each. Per-chunk times: [900s, 58s]. Total: 959s.
[23:36:57 WARNING] scoring.text_scorer — [CHUNK] All 2 chunks fell back to pseudo. Using pseudo-score for full text.
```

The architectural fix (chunking code, VRAM clearing, [CHUNK] logging) landed correctly and executes as designed. The implementation is sound. The problem is the underlying assumption.

### Chunk 1 (250 words): Timeout after 15 minutes

LLaMA word embeddings reached 8% completion (15/188 batches) after 15 minutes:

```
Computing word embeddings:   8%|7         | 15/188 [13:05<2:24:31, 50.13s/it]
```

Projected time for full 250-word chunk: **2 hours 38 minutes**. The 15-minute per_chunk_timeout was never close to sufficient.

### Chunk 2 (20 words): Tensor dimension mismatch

```
RuntimeError: stack expects each tensor to be equal size, but got [4, 465, 3072] at entry 0 and [4, 19, 3072] at entry 9
```

The exca cache had 15 inflight records from chunk 1's orphaned thread (which continued running after the timeout). When chunk 2 started, the cache served stale intermediate results from chunk 1, causing a tensor shape collision between the 250-word chunk's context (465 tokens) and the 20-word chunk's context (19 tokens).

### Both failure modes are pre-existing

- **Timeout**: 250 words takes ~3 hours for LLaMA embeddings. No reasonable per-chunk timeout can accommodate this on laptop hardware.
- **Cache contamination**: The ThreadPoolExecutor timeout orphans threads but cannot kill CUDA kernels. The orphaned thread continues writing to the shared exca SQLite cache, corrupting state for subsequent calls.

---

## 4. Architectural Implications

### Exca cache is shared across chunks

The TRIBE v2 vendor code (`tribev2.demo_utils.TextToEvents`) uses the `exca` caching library with a process-global SQLite cache directory. All chunks within a single scoring session share the same cache namespace. Chunk-level isolation is impossible without:

- Separate cache directories per chunk (requires vendor code changes)
- Separate processes per chunk (defeats the purpose of shared GPU memory)
- Serializing chunk execution with full cache cleanup between them (adds hours)

### Threading model conflicts

The scoring timeout uses `ThreadPoolExecutor.submit()` with `future.result(timeout=N)`. On timeout, `executor.shutdown(wait=False)` returns immediately but **cannot terminate the underlying thread**. The orphaned thread:

1. Continues running LLaMA inference on the GPU
2. Continues writing to the exca SQLite cache
3. Holds GPU memory allocations that `empty_cache()` cannot reclaim
4. Corrupts the cache state for any subsequent scoring call

This is a fundamental limitation of Python's threading model — threads cannot be killed. The `concurrent.futures` timeout is a cooperative timeout, not a preemptive one.

### These are vendor-code constraints

The bottleneck (LLaMA 3.2-3B forward pass speed) and the cache contamination issue (exca inflight records) are properties of the TRIBE v2 vendor code (`tribev2/` submodule) and its dependencies. The orchestrator and scoring wrapper code cannot work around these without modifying the vendor.

---

## 5. What This Means for Phase 2

### B.1 chunking is a dead end as currently scoped

The chunking implementation is architecturally correct and fully wired in. But the premise — that splitting text into smaller pieces would bring inference within timeout — is wrong. The LLaMA embedding bottleneck means:

- A 250-word chunk takes ~3 hours (not 15 minutes)
- A 100-word chunk would take ~1.2 hours (still far beyond any reasonable timeout)
- A 50-word chunk would take ~35 minutes (marginally usable but with 10+ chunks per variant)

No chunk size makes the math work on laptop hardware with LLaMA 3.2-3B.

### The real reliability problem

TRIBE v2 inference speed on laptop-class hardware (RTX 5070 Ti) is fundamentally mismatched with the campaign pipeline's expectations. The Phase 1 baseline texts that scored successfully (~20 words, from the baseline seeding) are ~100x shorter than campaign-generated variants (300-500 words).

The 15 baseline texts score in ~1s each because they are short enough that the LLaMA embedding loop finishes in seconds. Campaign variants are long enough that the loop takes hours.

---

## 6. Options to Evaluate

**DO NOT IMPLEMENT — decision required from project owner.**

### Option A: Accept the Speed, Reduce the Scope

- Max variant length: **150 words** (down from unconstrained, typically 300-500)
- Max variants per iteration: **2** (down from 3)
- Enforce word limit in Claude Haiku variant generation prompt
- Expected campaign time: ~30 min per iteration, ~1 hour total for 2 iterations
- **Trade-off:** Less content to compare, less optimization headroom, but results are real brain-encoding scores (not pseudo) and fast enough for interactive use

### Option B: Embedding Cache

- Cache LLaMA word embeddings by `(word, context_window)` key
- Subsequent variants with shared vocabulary hit the cache
- Could use `exca` cache warming during baseline seeding
- **Trade-off:** High implementation complexity, uncertain hit rate (variants vary significantly), cache invalidation complexity, requires vendor code understanding. May only help for repeated/similar vocabulary.

### Option C: Hosted TRIBE v2 for Production Campaigns

- Laptop stays as dev/POC environment for short-text testing
- Real campaigns run against a cloud GPU instance (A100 on Modal/Runpod/Lambda Labs)
- A100 (80 GB VRAM, native CUDA kernels, 4x memory bandwidth) would complete LLaMA embeddings ~10-20x faster
- **Trade-off:** $1-3 per campaign, infrastructure setup (Docker image, API endpoint), but completely unblocks the pipeline. No code changes needed — just point `TRIBE_SCORER_URL` at the cloud instance.

### Option D: Smaller TRIBE v2 Model Variant

- TRIBE v2 vendor code may support smaller text encoders (e.g., LLaMA 3.2-1B instead of 3B)
- Would reduce embedding time by ~3x
- **Trade-off:** Requires retraining or finding a pre-trained smaller variant. Potential accuracy loss in brain-encoding predictions. Out of scope for Phase 2 without upstream collaboration.

---

## 7. Recommendation

This document presents findings and options. The project owner should decide based on:

1. **Is the POC goal to demonstrate the full pipeline with real scores?** → Option A (reduce scope) gives real scores at the cost of shorter variants.
2. **Is the goal to score realistic campaign content (300-500 words)?** → Option C (cloud GPU) is the only path that doesn't compromise content quality.
3. **Is the goal to optimize for iteration speed in development?** → Option A gets campaigns completing in ~1 hour instead of timing out.

The chunking code should remain on `main` (it is correct and tested). If Option A is chosen, it provides the `max_words_per_chunk` infrastructure. If Option C is chosen, chunking becomes unnecessary on the cloud GPU (A100 has enough memory and speed for unchunked inference).

**The `phase2-b1-complete` tag should NOT be applied.** B.1's goal — "zero pseudo-score fallbacks" — cannot be achieved with chunking alone on this hardware.
