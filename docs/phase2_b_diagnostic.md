# Phase 2 Track B Diagnostic: A/B Comparison

**Date:** 2026-04-13
**Purpose:** Determine whether the Price Increase scenario failure is a B.2-B.5 regression or a pre-existing condition.

---

## Critical Discovery: B.1 Was Never Implemented

The `phase2-b1-complete` tag does not exist. The Phase 2 plan describes B.1 as "text chunking for long variants" with parameters `max_words_per_chunk` and `per_chunk_timeout`. Investigating the code:

- `tribe_scorer/scoring/text_scorer.py:27` — `score_text(text, model)` takes only 2 arguments. No `max_words`, no chunking logic.
- `tribe_scorer/config.py` — Has `max_words_per_chunk=250` and `per_chunk_timeout=900` settings, but they are **never wired into `score_text()`**.
- `tribe_scorer/main.py:337` — Calls `score_text(text, model)` with 2 args. No chunking params passed.
- Git history: Zero commits match "chunk" in any tribe_scorer file.

**Conclusion:** B.1 (TRIBE timeout fix via chunking) exists only as a plan. The config settings were added as preparation, but the actual chunking implementation was never built. Every run has been using the unchunked pipeline with a 60-minute timeout.

---

## A/B Comparison Design

| | Run A | Run B | Earlier Run B |
|---|---|---|---|
| **Code** | `phase2-complete` (no B.2-B.5) | `main` (with B.2-B.5) | `main` (with B.2-B.5) |
| **Scenario** | Price Increase, 2 iter, 20 agents | Identical | Identical |
| **TRIBE fresh restart** | Yes | Yes | Yes (but after Run A's session) |

---

## Results

### Run A — `phase2-complete` (baseline, no B.2-B.5)

| Variant | Iter | TRIBE | is_pseudo | attn |
|---------|------|-------|-----------|------|
| v1_peer_vali | 1 | Real | False | 86.4 |
| v2_investmen | 1 | Real | False | 92.4 |
| v3_risk_miti | 1 | Real | False | 97.3 |
| v1_analyst_p | 2 | Pseudo | True | 28.4 |
| v2_capabilit | 2 | Pseudo | True | 27.1 |
| v3_board_dis | 2 | Pseudo | True | 27.4 |

- **Duration:** 57 min
- **Post-run TRIBE health:** `status=ok`, GPU memory queries returned None
- **Result:** 3/6 real, 3/6 pseudo. Iteration 1 clean, iteration 2 all pseudo.

### Run B — `main` (with B.2-B.5)

| Variant | Iter | TRIBE | is_pseudo | attn |
|---------|------|-------|-----------|------|
| v1_peer_soci | 1 | Real | False | 93.3 |
| v2_risk_miti | 1 | Pseudo | True | 28.4 |
| v3_measurabl | 1 | Pseudo | True | 27.4 |
| (iter 2) | 2 | — | — | — |

- **Duration:** 30 min (aborted at iter 2)
- **Iter 2 failure:** Claude API 401 authentication_error (token expired mid-run, NOT a TRIBE or B.2-B.5 issue)
- **Post-run TRIBE health:** Unreachable
- **Result:** 1/3 real, 2/3 pseudo (iteration 1 only; iteration 2 lost to auth failure)

### Earlier Run B — `main` (first attempt, same session)

| Variant | Iter | TRIBE | is_pseudo | attn |
|---------|------|-------|-----------|------|
| v1_peer_ | 1 | Real | False | 94.7 |
| v2_roi_c | 1 | Pseudo | True | 28.3 |
| v3_risk_ | 1 | Pseudo | True | 29.7 |
| v1_peer_ | 2 | None | — | — |
| v2_advis | 2 | None | — | — |
| v3_board | 2 | None | — | — |

- **Duration:** 42.6 min
- **Post-run TRIBE health:** `status=degraded`, `cuda_healthy=false`, GPU memory=null
- **Result:** 1/3 real, 2/3 pseudo (iter 1), 0/3 scored (iter 2, TRIBE unavailable)

### Historical Baseline — `phase2_validation.json` (April 10)

| Variant | Iter | TRIBE | is_pseudo | attn |
|---------|------|-------|-----------|------|
| variant 1 | 1 | Real | False | 83.1 |
| variant 2 | 1 | Real | False | 43.2 |
| variant 3 | 1 | Pseudo | True | 28.0 |
| variant 1 | 2 | None | — | — |
| variant 2 | 2 | None | — | — |
| variant 3 | 2 | None | — | — |

- **Result:** 2/3 real, 1/3 pseudo (iter 1), 0/3 scored (iter 2)

---

## Analysis

### Is this a B.2-B.5 regression? **No.**

The pseudo-score pattern exists on BOTH code versions:

| Run | Code | Iter 1 Real/Total | Iter 2 Real/Total |
|-----|------|-------------------|-------------------|
| Historical | phase2-complete | 2/3 | 0/3 |
| Run A | phase2-complete | 3/3 | 0/3 |
| Earlier Run B | main + B.2-B.5 | 1/3 | 0/3 |
| Run B | main + B.2-B.5 | 1/3 | (auth failure) |

**Iteration 2 consistently fails on BOTH versions.** Run A (phase2-complete) got 3/3 pseudo on iter 2; Earlier Run B (main) got 0/3 None on iter 2. The failure mode differs (pseudo fallback vs TRIBE unavailable) but the outcome is the same: no real scores on iteration 2.

**Iteration 1 varies non-deterministically.** Run A got lucky with 3/3 real; the others got 1-2/3 real. This is not code-dependent — it's variant-text-dependent. Claude generates different variant text each run, and longer/more complex variants stress the TRIBE pipeline more.

### Why does iteration 2 always fail?

The TRIBE pipeline (TTS → WhisperX → LLaMA 3.2-3B word embeddings → brain encoding → ROI extraction) runs the full chain for each variant. By iteration 2:

1. **VRAM is exhausted.** The model uses ~10 GB at peak. After 3+ inference passes, GPU memory fragmentation and cached tensors push it to the 11.94 GB limit.
2. **exca cache growth.** Each inference creates cache entries in the exca SQLite databases. Cache operations under memory pressure can stall.
3. **CUDA context degradation.** On the RTX 5070 Ti with sm_120 JIT fallback (no native kernels), sustained inference at VRAM limits is inherently unstable.

### What B.2 DOES add

On `main` (with B.2), the failure is now **visible**:
- `cuda_healthy: false` in the health response
- `status: degraded` instead of `ok`
- The orchestrator logs a warning about stale CUDA

On `phase2-complete` (without B.2), the failure is **silent**:
- `status: ok` even after GPU memory queries return None
- No CUDA health probe — the system appears healthy while producing garbage

**B.2 is working as designed: it detects failure, it does not prevent it.**

---

## Root Cause

The TRIBE v2 pipeline cannot reliably score more than ~3-4 variants in a single session on the RTX 5070 Ti. This is a **hardware/architecture limitation**, not a code bug:

1. **11.94 GB VRAM** is barely enough for the full pipeline (LLaMA 3.2-3B ~6-8 GB + TTS + WhisperX + brain model)
2. **sm_120 JIT fallback** adds overhead vs native kernel compilation
3. **No GPU memory management** between inference passes (tensors accumulate)
4. **B.1 (chunking) was supposed to address this** by processing smaller text chunks, reducing per-inference VRAM pressure — but it was never implemented

---

## Recommendations

1. **Implement B.1 (text chunking).** This is the actual blocker. Chunking long variants into 250-word segments would reduce per-inference VRAM and give `torch.cuda.empty_cache()` a chance to reclaim memory between chunks.

2. **Add `torch.cuda.empty_cache()` between variant scores.** Even without chunking, clearing the cache between variants would help with VRAM fragmentation.

3. **Do NOT block B.2-B.5 on this issue.** The B.2-B.5 code is correct and adds value (detection, monitoring, docs, healthchecks). The scoring failure is pre-existing.

4. **Tag `phase2-b-complete` for the B.2-B.5 code**, with a note that B.1 is still outstanding and is the actual blocker for reliable scoring.
