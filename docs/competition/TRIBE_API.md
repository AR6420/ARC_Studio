# TRIBE v2 scorer — API contract (Phase 1+)

Companion to `tribe_scorer/main.py`. Documents the response shapes the orchestrator (and Phase 5 UI) consume. Aggregate scoring behaviour is unchanged from `main`; this doc focuses on the new optional `timeline` field added in Phase 1 of the AMD hackathon migration.

## Scoring endpoints

| Endpoint | Method | Purpose | Timeline emitted |
|----------|--------|---------|:---:|
| `/api/score` | POST | Single text → 7 dimension scores | ✅ |
| `/api/score/batch` | POST | List of texts → list of scores | ❌ |
| `/api/score_audio` | POST | Audio file → 7 dimension scores | ✅ |
| `/api/score_video` | POST | Video file → 7 dimension scores | ✅ |
| `/api/health` | GET | Service + GPU status | n/a |

Batch endpoint omits the timeline because individual texts in a batch share the global normaliser pass; emitting per-window data per item would double the payload without a concrete consumer in Phase 5. If the demo needs per-text timelines, fan out as `len(texts)` single calls.

## Response schema (single endpoints)

All three single-item responses (`ScoreResponse`, `AudioScoreResponse`, `VideoScoreResponse`) share the same Phase 1 additions:

```jsonc
{
  // Aggregated dimension scores (0-100, unchanged from main)
  "attention_capture": 73.4,
  "emotional_resonance": 56.1,
  "memory_encoding": 61.8,
  "reward_response": 49.2,
  "threat_detection": 38.5,
  "cognitive_load": 65.0,
  "social_relevance": 71.7,

  "inference_time_ms": 1842.3,
  "is_pseudo_score": false,

  // === Phase 1 additions ===
  // Optional per-window time-series for the same 7 channels.
  // Same keys as the aggregated scores; values are equal-length lists.
  // Index i corresponds to the i-th TR (window) of the inference run.
  // Null when inference fell back to pseudo or timeline could not be built.
  "timeline": {
    "attention_capture":  [0.041, 0.067, 0.052, ...],
    "emotional_resonance":[0.013, 0.022, 0.019, ...],
    "memory_encoding":    [0.028, 0.031, 0.027, ...],
    "reward_response":    [0.011, 0.015, 0.018, ...],
    "threat_detection":   [0.005, 0.009, 0.012, ...],
    "cognitive_load":     [0.034, 0.041, 0.038, ...],
    "social_relevance":   [0.029, 0.033, 0.035, ...]
  },

  // Seconds per TR. Multiply array index × this value to get
  // wallclock time. Null when timeline is null.
  "tr_seconds": 1.49
}
```

### Notes
- **Values in `timeline` are raw ROI activations**, not the 0-100 normalised aggregate. The aggregate goes through `Normalizer.normalize`; per-window values do not (the normaliser baseline is global per-process). Consumer-side normalisation can be done by the UI if a 0-100 series is desired.
- **Endpoint-specific extras** (audio: `duration_seconds`, `pseudo_reason`; video: same plus `width`, `height`, `peak_vram_mb`) are unchanged.
- **Audio and video** cannot be chunked at this layer — they expose the raw `(n_TRs, 20484)` predictions from a single `model.predict()` call. **Text** with `max_words_per_chunk > 0` and a long input concatenates per-chunk windows along axis 0.

## Backwards compatibility

Both `timeline` and `tr_seconds` are nullable. Older orchestrator builds that don't know about these fields continue to work — Pydantic ignores unknown extras and the orchestrator's `tribe_client._extract_scores` only adds them when present. No version bump required.

## Producer contract (TRIBE side)

Internally:
- `scoring/text_scorer.py:score_text_with_timeline` returns `(avg, is_pseudo, preds_per_window | None)`.
- `scoring/audio_scorer.py:score_audio_with_timeline` mirrors it.
- `scoring/video_scorer.py:score_video_with_timeline` mirrors it (with `peak_vram_mb` insertion).
- `scoring/roi_extractor.py:extract_roi_activations_per_window(preds_2d)` runs the existing ROI ranges across each row of the 2-D predictions and returns `dict[str, list[float]]`.

The legacy `score_text` / `score_audio` / `score_video` 2- or 3-tuple signatures are preserved so existing callers (tests, baseline-seeding) continue to work without changes.

## Consumer contract (orchestrator side)

`orchestrator/clients/tribe_client.py:_extract_scores` passes `timeline` and `tr_seconds` through the score dict when present. The orchestrator engine doesn't currently consume them — they just propagate to whatever downstream layer the UI wires up in Phase 5.

## Future work (out of Phase 1 scope)

- Batch endpoint timelines (would double payload; defer until a consumer exists).
- Per-window normalisation surface for the UI.
- Time-aligned word/phoneme boundaries (whisper_hf already produces word-level timing; could be cross-referenced with TR boundaries for richer demo viz).
