# Demo assets

Stimulus media + mock data for the Phase 5 / 6 demo. Large media files
are gitignored; check them in via direct download as documented below.

## Files

| File | Tracked | Source / how to obtain |
|------|---------|------------------------|
| `apple_1984.mp4` | ❌ (gitignored) | Apple's 1984 Super Bowl ad, 60s. Download from the Internet Archive search "Apple 1984 Macintosh commercial". Re-encode to ~5 Mbit H.264 / 1080p / 25fps if needed. |
| `mock_timeline_apple1984.json` | ✅ | Synthetic TRIBE timeline shaped to match the ad's narrative arc. Used by the React UI when running in dev/mock mode (no MI300X). |

## Mock timeline shape

`mock_timeline_apple1984.json` mirrors the live `/api/score_video`
response — same keys (`timeline`, `tr_seconds`) and the same 7-channel
dimension breakdown emitted by TRIBE v2. Replace it with a real
response when running against MI300X.

```jsonc
{
  "tr_seconds": 5.0,                 // seconds per window; idx × tr_seconds = wallclock
  "duration_seconds": 60.0,
  "timeline": {
    "attention_capture":   [...],    // length-12 list of raw ROI activations
    "emotional_resonance": [...],
    "memory_encoding":     [...],
    "reward_response":     [...],
    "threat_detection":    [...],
    "cognitive_load":      [...],
    "social_relevance":    [...]
  }
}
```

## Display channel formulas (UI)

The React TimelineChart shows 4 derived channels rather than the raw 7
TRIBE dimensions, mapping functional dimensions onto more recognisable
anatomical labels for the demo audience. The blends are documented and
applied client-side in `ui/src/lib/timeline-channels.ts`:

| Display channel | Formula |
|-----------------|---------|
| Visual cortex | `attention_capture` |
| Auditory cortex | `(social_relevance + cognitive_load) / 2` |
| Language regions | `(cognitive_load + memory_encoding) / 2` |
| Engagement composite | `0.5 × emotional_resonance + 0.3 × reward_response + 0.2 × attention_capture` |

All four are min-max normalised across the timeline before rendering so
the chart's 0–1 axis stays comparable across stimuli.
