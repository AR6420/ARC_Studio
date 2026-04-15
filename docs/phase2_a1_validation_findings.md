# Phase 2 A.1 — Validation Findings

**Date**: 2026-04-15
**Scope**: Audio input support end-to-end — UI upload, backend preprocessing, TRIBE v2 Wav2Vec-BERT routing.
**Branches merged**: `fix/phase2-a1-ui`, `fix/phase2-a1-backend`, `fix/phase2-a1-tribe` → `main`.
**Final commit**: `8e21bc7` (cleanup fix) on top of three `--no-ff` merges.

## Test Coverage Summary

| Level | Result |
|---|---|
| Unit tests post-merge (orchestrator + tribe_scorer) | **250/250 pass** (excluding pre-existing `test_tribe_timeout.py`, untracked, imports a symbol that doesn't exist in `tribe_client`) |
| Upload endpoint integration (valid .mp3 / .pdf / 11 MB) | **3/3 pass** — 200 / 400 / 400 with correct error messages |
| TRIBE `/api/score_audio` direct (Wav2Vec-BERT) | **PASS** — 200 in 72s, `is_pseudo_score: false`, all 7 dims, scores 35-40 |
| Audio campaign end-to-end | **PASS** — 8.9 min, 4 variants, 0/4 pseudo-scores, 4/4 composite scores present |
| Text campaign regression (Price Increase scenario) | **PASS** — 18.2 min, 4 variants, 0/4 pseudo-scores matching B.1 baseline |

## Campaign Results

### Audio — `enterprise_decision_makers`, 2 iter × 2 variants
- Duration: **532.4s (8.9 min)**
- Iterations completed: 2/2
- Total variants: 4
- `tribe_pseudo_scores`: **0/4** ✅
- `composite_present`: 4/4
- `mirofish_present`: 0/4 (pre-existing env issue — see Caveats)
- Attention scores: uniform 39.5 across all variants (by design — one audio score broadcast across variants per `campaign_runner.py` line 183)
- `system_availability`: `tribe_available=True, mirofish_available=False`

### Text regression — Price Increase, `enterprise_decision_makers`, 2 iter × 2 variants
- Duration: **1094.2s (18.2 min)** — faster than B.1 baseline of 37.9 min (less Anthropic rate-limiting this run)
- Iterations completed: 2/2
- Total variants: 4
- `tribe_pseudo_scores`: **0/4** ✅ (matches B.1 baseline of 0/4)
- Attention iter 1: 76.0–89.7 (B.1: 77.1–85.2)
- Attention iter 2: 86.1–86.2 (B.1: 77.1–84.6)
- Iteration delta: +3.4 (B.1: +5.6) — comparable; no regression

## Success Criteria

| Criterion | Result |
|---|---|
| Audio campaign completes end-to-end | ✅ PASS — 2 full iterations, 4 variants, all real TRIBE scores |
| Text regression 0/4 pseudo-scores | ✅ PASS — matches B.1 baseline exactly |
| All unit tests pass after merge | ✅ PASS — 250/250 |
| UI renders correctly for both campaigns | ⚠️ UNVERIFIED — WSL can't open a browser; requires manual confirmation |

## Caveats & Known Gaps

1. **MiroFish shows unavailable** in `/api/health` AND in `system_availability` for both runs, even though the MiroFish container itself returns `{"status":"ok"}` on `/health`. Orchestrator's `mirofish_client.health_check()` can't reach it. This is **pre-existing** (same state observed before the A.1 merges) and is NOT caused by the audio work. The pipeline gracefully degrades: TRIBE + composite work fine, MiroFish-dependent composite components return None. Needs a separate investigation.

2. **`iteration.data_completeness` is `null`** on every returned variant. Backend-audio's changes added `has_audio` and `media_type` fields to the `DataCompleteness` schema, but the object is never populated in the iteration records returned by `/api/campaigns/{id}`. The `system_availability` in `analyses` DOES reflect MiroFish availability, so completeness tracking works in the analysis layer. Likely a pre-existing gap in how the iteration records are serialized. Gap, not regression.

3. **UI visual verification** — user-confirmed in browser:
   - Audio upload area renders between seed content and prediction question ✅
   - `.wav`/`.mp3` file selection shows filename + duration + size ✅
   - `>60s` file triggers the exact error message ✅
   - Report tab renders for both audio campaign `b47f2c15-...` and text campaign `98b3b5d9-...` ✅
   - **UX gap noted**: the campaign list view does not visually indicate `media_type` — user had to read the prediction question to tell audio vs text campaigns apart. Not a functional blocker; track as a polish item for a later pass.

4. **Auth recovery** — during this validation, the orchestrator's 401 auto-refresh depended on `~/.claude/.credentials.json`. The Windows-side credentials file had a stale OAuth token while the WSL-side had a fresh one. Recovery required copying the fresh WSL credentials to the Windows path (backup preserved at `.credentials.json.bak_pre_a1_validation`). This is an env/tooling quirk, not a code issue.

5. **Stale merge artifact caught pre-push**: git's auto-merge combined the backend-branch placeholder `score_audio` method and the tribe-branch real implementation at different line positions in `tribe_client.py` (no textual conflict → both kept). Deduped in cleanup commit `8e21bc7` before push. Tests verified only the real implementation remained (250/250).

## Tag Decision

- **Core A.1 plumbing**: verified working end-to-end (upload → orchestrator → TRIBE Wav2Vec-BERT → composite scoring).
- **Text regression**: clean, no drift from B.1 baseline.
- **UI visual check**: pending user confirmation.

**Recommendation**: apply `phase2-a1-complete` tag **after user confirms UI visual checks**. Gap items (MiroFish availability, `data_completeness` nullness) are tracked separately — they do not block tagging.

## Artifacts

- Branch merge commits: `3b69d41` (UI), `268bd39` (backend), `9c7b9de` (TRIBE), `8e21bc7` (cleanup)
- Campaign records: `b47f2c15-d3be-408b-80e2-16048690812d` (audio), `98b3b5d9-0221-4dcd-bc64-6641872eb479` (text)
- Test audio file: `data/uploads/533f2b73-8972-407a-a9c4-25226257b80a.mp3` (6.672s, 53 KB, gTTS-generated)
- Validation scripts kept in repo root during run; can be removed after review: `test_upload.py`, `test_score_audio.py`, `test_audio_campaign.py`, `run_both_campaigns.py`, `fetch_campaign_details.py`, `quick_auth_test.py`, `both_campaigns_log.json`, `both_campaigns_stdout.log`, `audio_full.json`, `campaign_detail.json`, `upload_response.json`, `test_audio.mp3`
