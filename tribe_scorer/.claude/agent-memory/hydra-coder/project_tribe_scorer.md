---
name: TRIBE v2 FastAPI Scoring Service
description: Architecture, file layout, and conventions for the tribe_scorer FastAPI service wrapping TRIBE v2 brain encoding
type: project
---

## Service layout (C:/Users/adars/Downloads/ARC_Studio/tribe_scorer/)

```
tribe_scorer/
  __init__.py              # empty
  config.py                # Pydantic Settings (env prefix: TRIBE_)
  main.py                  # FastAPI app, lifespan, endpoints, schemas
  requirements.txt
  scoring/
    __init__.py            # empty
    model_loader.py        # load_model(), get_model(), is_model_loaded() singleton
    text_scorer.py         # score_text(text, model) -> np.ndarray (n_vertices,)
    roi_extractor.py       # extract_roi_activations(arr) -> dict[str, float]
    normalizer.py          # Normalizer class + get_normalizer() singleton
  vendor/
    tribev2/               # vendored Meta TRIBE v2 package (git subtree)
```

## Key architectural decisions

- `TribeModel` is imported from `vendor/tribev2/tribev2` (added to sys.path in model_loader.py)
- Model is a singleton loaded once at startup via FastAPI `lifespan`; failures are logged but service starts in degraded mode
- GPU inference is synchronous — all endpoints offload to `loop.run_in_executor(None, ...)`
- Baseline seeded at startup with 10 diverse reference texts (`REFERENCE_TEXTS` in normalizer.py)
- Normalization: percentile-rank against baseline * 100; fallback to within-batch min-max if baseline empty

## TRIBE v2 API (actual, from source)

```python
from tribev2 import TribeModel
model = TribeModel.from_pretrained("facebook/tribev2", cache_folder="./cache", device="cuda")
events = model.get_events_dataframe(text_path="input.txt")   # must be .txt file
preds, segments = model.predict(events, verbose=False)        # preds: (n_segs, ~20484)
avg_pred = preds.mean(axis=0)                                  # (20484,)
```

- `get_events_dataframe` internally does TTS (gTTS) + transcription; needs real internet on first call
- `predict` returns only kept segments (remove_empty_segments=True by default)
- fsaverage5: 10242 vertices per hemisphere; LEFT = indices 0..10241, RIGHT = 10242..20483

## ROI vertex ranges (POC approximations, fsaverage5)

Seven dimensions with approximate index ranges:
1. attention_capture: occipital (0-2000) + parietal IPS (7000-8000) + FEF (4500-5000), both hemis
2. emotional_resonance: ant. medial temporal (2600-3200) + insula (3800-4300) + ACC (5500-6200)
3. memory_encoding: parahippocampal (3200-3900) + fusiform (2000-2600) + entorhinal (3900-4200)
4. reward_response: medial OFC (1000-1500) + lateral OFC (1500-2000) + vmPFC (5200-5600)
5. threat_detection: ant. medial temporal (2400-2700) + ACC (5400-5700) + insula (3700-4100)
6. cognitive_load: DLPFC (6200-7000) + ant. PFC (8000-8600) + IFG (5000-5500)
7. social_relevance: TPJ (8600-9400) + mPFC (9400-9800) + pSTS (9800-10242)

All ranges duplicated for RIGHT hemisphere (+ 10242 offset).

## Endpoints

- `POST /api/score`         ScoreRequest{text} -> ScoreResponse{7 floats + inference_time_ms}
- `POST /api/score/batch`   BatchScoreRequest{texts[]} -> BatchScoreResponse{scores[]}
- `GET  /api/health`        -> HealthResponse{status, model_loaded, gpu_*, baseline_size, startup_error}

**Why:** Phase 3 of ARC_Studio project; serves downstream content scoring via fMRI brain prediction.
**How to apply:** When adding new endpoints or modifying scoring, follow the run_in_executor pattern for all blocking GPU calls. Keep the model singleton pattern in model_loader.py.
