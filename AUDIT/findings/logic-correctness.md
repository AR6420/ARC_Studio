# Track 1 — Logic & Correctness Audit

Scope: `orchestrator/engine/{campaign_runner,composite_scorer,optimization_loop,report_generator,result_analyzer,tribe_scorer,variant_generator,mirofish_runner}.py`, `orchestrator/prompts/*.py`, `orchestrator/cli.py`, `tribe_scorer/scoring/{normalizer,roi_extractor,text_scorer,audio_scorer,video_scorer,whisper_hf,model_loader}.py`, `tribe_scorer/main.py` (scoring/endpoint logic).

All findings below were verified by reading the cited files in full (not skimmed). Ordered most-severe first.

---

## LOG-01 — CRITICAL — `find_best_composite` crashes with `IndexError` when a variant-generation round returns zero variants

**Files:** `orchestrator/engine/optimization_loop.py:189-222` (definition), triggered from `orchestrator/engine/campaign_runner.py:528`

```python
def find_best_composite(composite_scores_list):
    best_idx = 0
    best_avg = -float("inf")
    for i, scores in enumerate(composite_scores_list):
        ...
    return composite_scores_list[best_idx]   # <-- IndexError if list is empty
```

`run_campaign()` calls this every iteration:
```python
best_composite = find_best_composite(result["composite_scores"])
```

**Why it fails:** `variant_generator.generate_variants()` (orchestrator/engine/variant_generator.py:95-101) explicitly tolerates the LLM returning fewer (including zero) variants than requested:
```python
variants = result.get("variants", [])
if len(variants) != num_variants:
    logger.warning(...)  # does NOT raise
```
If Haiku/Qwen returns JSON without a `"variants"` key (malformed schema, empty completion, truncated JSON under a tight `max_tokens`, or a JSON-mode failure from the vLLM/Qwen backend introduced by the AMD-hackathon migration), `variants = []`. Every downstream step in `run_single_iteration` tolerates an empty variants list (`TribeScoringPipeline.score_variants([])` → `[]`, `MirofishRunner.simulate_variants([])` → `[]`, the per-variant `for` loops in `campaign_runner.py` all iterate zero times), so `run_single_iteration` **returns successfully** with `composite_scores == []`. The very next line in `run_campaign()`, `find_best_composite([])`, then executes the `for` loop zero times, leaves `best_idx = 0`, and indexes into the empty list — an unhandled `IndexError`.

This is caught by `run_campaign`'s outer `except Exception` (campaign_runner.py:576), which sets `stop_reason = "error"`, marks the campaign `"failed"`, and then **re-raises** `loop_error` (campaign_runner.py:640) after report generation — so the exception still propagates to whatever manages the background task.

**At 100 users × 100 agents:** many more concurrent Haiku/Qwen variant-generation calls run per unit time; the absolute count of malformed/empty completions rises proportionally. Any single one silently kills that user's *entire* multi-iteration campaign with an unhandled exception instead of a graceful retry — a preventable, load-scaling failure mode.

**Minimal fix:** guard the empty case in `find_best_composite` (return an all-`None` dict, or raise a clear domain error caught one level up in `run_campaign`), and/or make `run_single_iteration` raise a clear `ValueError` when `variants` comes back empty so the failure is attributable and retryable instead of being an `IndexError` two calls downstream.

---

## LOG-02 — HIGH — `influence_concentration` / `platform_divergence` are [0,1] fractions but the mass-psychology prompts treat them as already 0-100

**Files:** `orchestrator/prompts/report_psychology.py:161-169,171-173` (general mode), `:278-280,282-284` (technical mode); root data from `orchestrator/engine/mirofish_runner.py:172,175,185-186`

`mirofish_runner.compute_metrics` produces:
```python
"influence_concentration": round(influence_concentration, 3),   # Gini coeff, clamped to [0, 1]
"platform_divergence": round(platform_divergence, 3),            # abs(prop diff), in [0, 1]
```
(confirmed: `_compute_influence_gini` returns `max(0.0, min(1.0, numerator/denominator))`; `_compute_platform_divergence` returns `abs(twitter_prop - reddit_prop)`, also in [0,1].)

`report_psychology.py` (general mode) then does:
```python
influence = simulation_summary.get("influence_concentration")
if influence is not None:
    if influence < 30:
        influence_label = "spread evenly across many participants"
    elif influence < 60:
        influence_label = "moderately concentrated in key individuals"
    else:
        influence_label = "highly concentrated in a small number of influencers"
    lines.append(f"Influence distribution: {influence:.0f}/100 ({influence_label})")
...
lines.append(f"Platform divergence (Twitter-like vs. Reddit-like): {divergence:.0f}/100")
```
and the technical mode does the analogous `f"{influence:.1f}/100"` / `f"{divergence:.1f}/100"`.

**Why it fails:** since `influence` and `divergence` are real-world values in `[0, 1]` (e.g. `0.42`), the comparison `influence < 30` is **always true** — every campaign, regardless of actual concentration, is narrated as "spread evenly across many participants," and the displayed figure is always `"0/100"` (or `"1/100"`) instead of the intended `"42/100"`. This silently corrupts the Influence/Divergence narrative of the Layer-4 Mass Psychology report (both general and technical modes) for every single campaign — it never reflects the true concentration/divergence level. Contrast with `composite_scorer.py`'s `polarization_index` formula, which correctly treats `platform_divergence_val` as `[0,1]` (comment: "divergence(0-1)") — confirming the bug is isolated to the report-prompt code, not a project-wide convention.

**Fix:** scale by `* 100` before comparison/display in both prompt builders (`influence * 100`, `divergence * 100`), matching the `[0,1]` semantics documented in `mirofish_runner.py`.

---

## LOG-03 — HIGH — `coalition_formation` type mismatch silently drops all "opinion groups" narrative from every report

**Files:** `orchestrator/engine/mirofish_runner.py:170,184` vs `orchestrator/prompts/report_psychology.py:150-159` (general), `:286-295` (technical)

`mirofish_runner._count_coalitions` returns an **int** (count of pro/anti/neutral coalitions, e.g. `1`, `2`, `3`), and `compute_metrics` stores it verbatim: `"coalition_formation": coalition_formation`.

`report_psychology.py` expects a **dict** with a `"groups"` sub-list of `{name, size, stability}` objects:
```python
coalition = simulation_summary.get("coalition_formation", {})
if coalition and isinstance(coalition, dict):
    groups = coalition.get("groups", [])
    ...
```

**Why it fails:** since `coalition_formation` is always an `int` in the real data flow, `isinstance(coalition, dict)` is **always `False`**, so this branch is unreachable dead code in every single campaign — the "Opinion groups that formed" (general mode) and "Coalition count" + per-group breakdown (technical mode) sections never render, regardless of how many coalitions actually formed. No dict-shaped `coalition_formation` (with `groups`/`name`/`size`/`stability`) is produced anywhere in the codebase, so this isn't an edge case — it is 100% dead code, guaranteed to never fire. The technical-mode system prompt explicitly promises "in-group/out-group formation indices (derived from coalition formation data)" as a required quantitative element (report_psychology.py:72-74) that can never actually be supplied.

**Fix:** either change `_count_coalitions` to return the richer dict shape the prompts expect, or change the prompts to consume the actual `int` (e.g. "N distinct coalitions formed").

---

## LOG-04 — HIGH — `audience_fit` computes a biased mean, not the documented "weighted average"

**File:** `orchestrator/engine/composite_scorer.py:176-194`; weight tables in `orchestrator/prompts/demographic_profiles.py`

```python
weighted_scores = []
for dim, score in tribe.items():
    ...
    weight = cognitive_weights.get(dim, 1.0)
    weighted_scores.append(score * weight)
if weighted_scores:
    raw = sum(weighted_scores) / len(weighted_scores)   # <-- divides by COUNT, not sum(weights)
    scores["audience_fit"] = round(_clamp(raw), 1)
```

The module docstring (line 73-75) and `result_analysis.py`/other docs describe this as "weighted average of TRIBE scores using demographic cognitive_weights." A weighted average is `Σ(w_i·x_i) / Σ(w_i)`; this code computes `Σ(w_i·x_i) / n` (n = 7 dimensions), which only equals a true weighted average when the weights happen to sum to exactly `n`.

**Why it fails / concrete numbers:** computing `Σweights` for each of the 6 presets in `demographic_profiles.py`:
- `tech_professionals`: Σw = 6.85 → avg weight 0.979 (audience_fit biased **≈ -2.1%**)
- `enterprise_decision_makers`: Σw = 7.45 → avg 1.064 (**≈ +6.4%**)
- `general_consumer_us`: Σw = 7.25 → avg 1.036 (**≈ +3.6%**)
- `policy_aware_public`: Σw = 7.30 → avg 1.043 (**≈ +4.3%**)
- `healthcare_professionals`: Σw = 6.75 → avg 0.964 (**≈ -3.6%**)
- `gen_z_digital_natives`: Σw = 7.75 → avg 1.107 (**≈ +10.7%**)

So a `gen_z_digital_natives` campaign gets an automatic ~11% `audience_fit` inflation relative to a `healthcare_professionals` campaign with *identical underlying TRIBE scores*, purely from this arithmetic bug — not from any genuine difference in fit. This feeds directly into `find_best_composite` (variant ranking), threshold checks, and the final report scorecard, so the bias is load-bearing, not cosmetic.

**Fix:** `raw = sum(weighted_scores) / sum(cognitive_weights.get(dim, 1.0) for dim in tribe if <same filter>)`.

---

## LOG-05 — HIGH — Whisper transcript race condition: `_LAST_TRANSCRIPT` global is read outside the lock that the code comments claim protects it

**Files:** `tribe_scorer/scoring/whisper_hf.py:170-180`; `tribe_scorer/main.py:608-649` (`_run_single_video_score`)

```python
# whisper_hf.py:170-174
# Phase 5 session 2: Whisper transcript surfacing for variant generation.
# TRIBE inference is serialised by `_inference_lock` in main.py, so storing
# the most recent transcript on a module-global is safe — the next inference
# overwrites it.
_LAST_TRANSCRIPT: str | None = None
```

```python
# main.py:608-627
with _inference_lock:
    try:
        vertex_activations, is_pseudo, peak_vram_mb, preds_per_window = (
            score_video_with_timeline(video_path, model, timeout=...)
        )
    except Exception as exc:
        ...
        peak_vram_mb = _read_peak_vram_mb()
# <-- lock released here (dedent) -->
elapsed_ms = (time.perf_counter() - t_start) * 1000.0
raw_activations = extract_roi_activations(vertex_activations)
scores = get_normalizer().normalize(raw_activations)
...
# main.py:640-649
# Surface Whisper transcript captured by the patched ExtractWordsFromAudio.
# ... Safe under the _inference_lock — only one inference at a time touches the global.
transcript: str | None = None
if not is_pseudo:
    try:
        from scoring.whisper_hf import get_last_transcript
        transcript = get_last_transcript()   # <-- executes AFTER the lock is released
    except Exception as exc:
        ...
```

**Why it fails:** the `with _inference_lock:` block only wraps the model-inference call; `get_last_transcript()` is invoked several lines *after* the block exits (post-processing: ROI extraction, normalization, timeline extraction all happen between lock-release and the transcript read). Under concurrent load — two `/api/score_video` (or one video + the `score_audio`/`score_text` paths sharing the same `_inference_lock`) requests queued on the single GPU — request B can acquire `_inference_lock`, run its own video pipeline (which overwrites `_LAST_TRANSCRIPT` early via the patched `ExtractWordsFromAudio._get_transcript_from_audio`), and finish before request A reaches its own (lock-free) `get_last_transcript()` call. Request A then returns **request B's transcript** as its own. This is silent cross-contamination of user data between concurrent campaigns — one user's variant generation gets grounded in a different user's uploaded video content, with no error or log signal.

At the audit's target scale (many concurrent users/campaigns, some submitting audio/video), this is a realistic, load-triggered correctness/data-integrity bug, directly contradicting the safety guarantee asserted in the comment itself.

**Fix:** move the `transcript = get_last_transcript()` read inside the same `with _inference_lock:` block that runs the inference (or better, have `score_video_with_timeline` return the transcript directly instead of stashing it in a global).

---

## LOG-06 — HIGH — Audio campaigns never receive Whisper-transcript grounding despite being treated identically to video in the orchestrator

**Files:** `tribe_scorer/main.py:296-312` (`AudioScoreResponse`, no `transcript` field) vs `:326-357` (`VideoScoreResponse`, has `transcript` field at 352-356); `tribe_scorer/scoring/audio_scorer.py` (whole file — no `whisper_hf` import or `get_last_transcript()` call anywhere, unlike `video_scorer`'s sibling code in `main.py`); `orchestrator/engine/campaign_runner.py:182-198`

`campaign_runner.run_single_iteration` treats audio and video symmetrically:
```python
if availability.tribe_available and media_type in ("audio", "video") and media_path:
    if media_type == "audio":
        media_score = await self._tribe_client.score_audio(media_path)
    else:
        media_score = await self._tribe_client.score_video(media_path)
    if media_score:
        media_transcript = media_score.get("transcript")
        if media_transcript:
            logger.info("Captured %s transcript ...", media_type, ...)
```

**Why it fails:** `AudioScoreResponse` (tribe_scorer/main.py) simply has no `transcript` field, and `_run_single_audio_score` never calls `whisper_hf.get_last_transcript()` (contrast with `_run_single_video_score`, which does). So `media_score.get("transcript")` is **always `None`** for audio campaigns — the `if media_transcript:` branch never executes, and the "ground variants in the actual stimulus transcript" feature (explicitly implemented for video) simply doesn't exist for audio, despite identical code paths and comments implying parity ("Phase 5 session 2: for audio/video campaigns we score the stimulus FIRST so the Whisper transcript surfaced by TRIBE can ground variant generation"). Audio campaigns silently fall back to hallucinating variants from an empty/short seed brief.

**Fix:** add a `transcript` field to `AudioScoreResponse` and call `get_last_transcript()` in `_run_single_audio_score`, mirroring the video path.

---

## LOG-07 — HIGH — CLI summary printer crashes with `TypeError`/`ValueError` on real (non-pseudo) TRIBE scores

**File:** `orchestrator/cli.py:307-317` (`_print_single_iteration`), guarded only by `except UnicodeEncodeError` at `:218-221`

```python
tribe = tribe_scores[i] if i < len(tribe_scores) and tribe_scores[i] else None
if tribe:
    ...
    for dim, score in tribe.items():
        if dim == "is_pseudo_score":
            continue
        print(f"    {dim}: {score:.1f}")   # assumes every value is numeric
```

**Why it fails:** `tribe_client._extract_scores()` (orchestrator/clients/tribe_client.py:61-92) adds non-numeric keys to the same dict whenever real (non-pseudo) TRIBE inference succeeds and a timeline/transcript is present:
```python
if timeline is not None:
    scores["timeline"] = timeline        # a dict of per-dimension lists
    scores["tr_seconds"] = data.get("tr_seconds")
transcript = data.get("transcript")
if transcript:
    scores["transcript"] = transcript    # a string
```
This happens for **every** audio/video campaign with successful real inference (`score_audio`/`score_video` always populate `timeline` when not pseudo; video also adds `transcript`), and for text campaigns whenever the TRIBE batch endpoint fails entirely and `TribeScoringPipeline` falls back to the sequential `/api/score` path (`tribe_scorer.py:100-132`), which also returns `timeline`/`tr_seconds`.

`composite_scorer.py:182` and `result_analysis.py:164` both explicitly filter out `{"is_pseudo_score", "timeline", "tr_seconds", "transcript"}` before formatting/using these dicts — but `cli.py`'s printer only skips `"is_pseudo_score"`. Formatting `timeline` (a `dict`) with `{score:.1f}` raises `TypeError: unsupported format string passed to dict.__format__`; formatting `transcript` (a `str`) raises `ValueError: Unknown format code 'f' for object of type 'str'`. Neither is a `UnicodeEncodeError`, so the crash is **not** caught by the existing `try/except` at cli.py:218-221 and propagates, killing the CLI process right after a successful campaign run (data is already written to the output file first, so no data loss, but the process exits with an unhandled traceback instead of a clean summary).

**Fix:** apply the same filter set (`{"is_pseudo_score", "timeline", "tr_seconds", "transcript"}`) used in `composite_scorer.py`/`result_analysis.py` before the `:.1f` formatting loop in `cli.py`.

---

## LOG-08 — MEDIUM — `virality_potential` / `backlash_risk` saturate at the clamp ceiling under realistic MiroFish activity, destroying discriminative power

**File:** `orchestrator/engine/composite_scorer.py:102-147`; contributing factor `orchestrator/engine/mirofish_runner.py:195-206` (`_count_shares`)

```python
share_rate_normalized = organic_shares / max(agent_count, 1) * 100.0
counter_narrative_factor = mirofish.get("counter_narrative_count", 0) / max(agent_count, 1) * 100.0
```
Both are named/commented as if they were percentages bounded to `[0, 100]` ("Divide by 100 for 0-100 range"), but `organic_shares` (and `counter_narrative_count`) are **raw counts across the whole simulation** (default `max_rounds=5`, per `campaign_runner.py:294`), not per-round or per-agent-capped counts. `_count_shares` even counts `CREATE_POST` as a "share" (mirofish_runner.py:197), further inflating the count. With `agent_count=40` (the CLI/engine default) and even one post per agent per round, `organic_shares ≈ 200`, giving `share_rate_normalized = 500` — 5x the value the formula's own scaling comments assume.

**Why it fails:** plugging typical mid-range TRIBE scores (`emotional_resonance=50, social_relevance=50, cognitive_load=50`) into `virality_potential`:
```
raw = (50*50) / max(50,10) * 500 = 2500/50*500 = 25000
scores["virality_potential"] = clamp(25000/100) = clamp(250) = 100.0
```
The score clamps to exactly `100.0` for a very wide range of realistic emotional/social inputs, meaning most variants in a default 40-agent/5-round campaign will tie at the ceiling regardless of actual content-quality differences — the metric loses its ability to differentiate variants, which directly undermines the optimization loop's ranking (`find_best_composite`) and the report scorecard for this dimension.

**Fix:** normalize by `agent_count * max_rounds` (or cap the ratio at 100 before use) so the formula's assumed `[0,100]` input range actually holds under realistic simulation parameters.

---

## LOG-09 — LOW — Layer-2 Scorecard's Opus narrative path (`build_report_scorecard_prompt`) is dead code

**Files:** `orchestrator/engine/report_generator.py:36-39` (imported), `:252-305` (`_assemble_scorecard`, never calls it); `orchestrator/prompts/report_scorecard.py` (defines `REPORT_SCORECARD_SYSTEM` / `build_report_scorecard_prompt`, unused anywhere else in the repo)

`_assemble_scorecard` only ever produces a hardcoded template string:
```python
summary = (
    f"Variant {winner_id} ranked first. "
    f"Campaign completed after {len(best_scores_history)} iteration(s) "
    f"(stop reason: {stop_reason})."
)
```
The dedicated prompt module documents this as "Per Open Question #2 in RESEARCH.md: the scorecard data is assembled from DB data; Opus adds only the narrative summary" and defines a `"ranking_rationale"` field that is never produced or persisted anywhere. Not a crash, but a real functionality gap versus the documented design — the scorecard's promised Opus rationale simply doesn't exist in any report ever generated.

**Fix:** either wire `build_report_scorecard_prompt`/`call_opus_json` into `_assemble_scorecard`, or delete the unused prompt module to avoid the false impression that this narrative exists.

---

## LOG-10 — LOW — `missing_composite_dimensions` reports a dimension as globally missing if any single variant lacks it

**File:** `orchestrator/engine/campaign_runner.py:400-407`

```python
missing: set[str] = set()
for comp in composite_scores_list:
    if comp:
        for key, val in comp.items():
            if val is None:
                missing.add(key)
```
If variant A has a valid `virality_potential` but variant B's is `None` (e.g. B's MiroFish sim failed independently), `missing_composite_dimensions` reports `virality_potential` as missing for the whole iteration even though it's present and usable for variant A. This is surfaced in `DataCompleteness` to the UI, so it can misleadingly suggest an entire dimension is unavailable when only one variant's data is missing.

**Fix:** compute completeness per-variant, or only add to `missing` when *all* variants lack the dimension.

---

## LOG-11 — HIGH — False "converged" signal when TRIBE/MiroFish are unavailable across consecutive iterations

**File:** `orchestrator/engine/optimization_loop.py:63-96` (`compute_improvement`), `:98-121` (`is_converged`); triggered via `orchestrator/engine/campaign_runner.py:532-536,571-574`

```python
def compute_improvement(current_scores, previous_scores):
    improvements = []
    for key in current_scores:
        curr = current_scores.get(key)
        prev = previous_scores.get(key)
        if curr is None or prev is None or prev == 0:
            continue
        ...
    return sum(improvements) / len(improvements) if improvements else 0.0
```

**Why it fails:** when both TRIBE and MiroFish are unavailable (D-05 graceful-degradation path), `compute_composite_scores` returns all-`None` composite dicts every iteration (`composite_scorer.py`). `find_best_composite` then returns an all-`None` dict as the "best" variant (its internal `values` list is empty, so it trivially "wins" with `avg=0.0`). Feeding two such all-`None` dicts into `compute_improvement` skips every key (`curr is None or prev is None`), leaving `improvements = []`, so the function returns **`0.0`** — the exact same value it would return for a genuinely-converged campaign with real, comparable scores.

`is_converged([0.0, 0.0])` (after 2 iterations) evaluates `all(imp < 5.0 for imp in [0.0, 0.0])` → `True`, so `run_campaign` sets `stop_reason = "converged"` and terminates the optimization loop — reporting to the user that the campaign "converged on an optimal variant" when in reality **no scoring data was ever available** to compare, because the downstream systems were down. This conflates "no data" with "no improvement," producing a misleading stop reason and truncating a campaign that should instead surface a clear "insufficient data" / retry signal.

**Fix:** have `compute_improvement` return a sentinel (e.g. `None`) when `improvements` is empty, and have the caller in `run_campaign` treat "no comparable data" distinctly from "0% improvement" (e.g. don't count it toward convergence, or downgrade `stop_reason` to something like `"no_data"`).

---

# What breaks first at 100 users × 100 agents

**`find_best_composite`'s unguarded `composite_scores_list[0]` (LOG-01) is the first thing to take down individual campaigns at scale.** At 100 concurrent users each running a multi-iteration campaign, the number of concurrent Claude Haiku / Qwen variant-generation calls scales directly with load. `variant_generator.py` already defensively codes for the LLM returning fewer variants than requested (`result.get("variants", [])`, logged but not raised) — which means the authors anticipated malformed/empty completions as a real possibility, especially plausible given the in-flight migration to a vLLM/Qwen backend (per `docs/competition/` — local models are typically less reliable at strict JSON-schema conformance than Anthropic's native JSON mode, and JSON-mode reliability itself tends to degrade under high concurrent request rates as the serving stack queues and truncates). The moment any single iteration's variant generation returns zero variants, `run_single_iteration` completes "successfully" with an empty `composite_scores` list, and the immediate next line in `run_campaign()` — `find_best_composite(result["composite_scores"])` — raises an unhandled `IndexError`. This doesn't just skip a feature or degrade a score; it crashes that user's entire campaign loop with a raw exception that propagates out of `run_campaign()` (it's explicitly re-raised after report generation), which very likely surfaces as an unhandled exception in whatever asyncio task/background-task machinery is tracking it (`app.state.running_tasks` per the system description). At 100 concurrent campaigns, this is not a tail-risk edge case — it is a per-unit-time failure rate that scales linearly with the number of concurrent LLM calls, and it will be the first "campaign just died with a stack trace" report during any real load test.
