# 06 — Demo plan (rough draft)

Draft script for the AMD hackathon submission demo. Refined in Phase 6.
Target length: **2 minutes** (max 5). Recorded as a single screen-share
on the cloud MI300X box, with one optional cut to the Apple 1984 ad
playing through the orchestrator's stimulus player.

## Hero claim

> A.R.C Studio predicts how content will land — neurally and socially —
> before you publish, and iterates on it. Running on a single MI300X.

## Demo arc (sections, ~20s each)

### 0:00 — Open on the campaign-detail view, mid-iteration

Pre-recorded campaign already loaded. Apple's 1984 Super Bowl ad is the
seed video. The Stimulus tab is foreground.

**Show**: video playing on the left, 4-channel neural timeline on the
right, playhead tracking. Voice-over: "this is what 60 seconds of TV
looks like inside the brain."

**Why this lands first**: the timeline is the most visually arresting
artifact we produce. It also implicitly explains what TRIBE is doing
without needing a slide.

### 0:15 — Pipeline strip + sidebar collapse (auto)

The moment the campaign moves from configuring to running, the
History sidebar auto-collapses to a 48px icon strip and the Pipeline
header pins to the top of the viewport. Five distinct cards
(Variants → Neural → Social → Composite → Analysis), each with the
backing model label underneath: **Qwen3.5-9B** for the agent tier,
**Qwen3.5-27B** for the orchestrator tier — sourced live from
`/api/config`, never hardcoded.

The active stage card glows amber with an outer shadow; completed
stages show a foreground bar; pending stages stay muted. Page
auto-scrolls each new stage's content into view as `step_start`
fires (suppressed for 2s after any user scroll, debounced at 800ms).

Voice-over: "Five stages, all running on Qwen models on a single
MI300X. The pipeline tells you exactly where the GPU is right now."

### 0:30 — Switch to Composite profile

Click into the iteration with the highest engagement. 7 horizontal bars
(attention / virality / memory / etc.) light up.

Voice-over: "TRIBE's neural readout maps to seven decision-relevant
dimensions. The rightmost bar is engagement composite — half emotional
resonance, three-tenths reward, two-tenths attention."

### 0:45 — Watch the simulation come alive (live MiroFish embed)

While the social-simulation stage is in flight, the campaign-detail
page renders the MiroFish live graph view inline (Phase 5 session 4
iframe embed). Force-directed agents pop in as MiroFish spawns
OASIS personas; ontology relations form edges in real time.
Pipeline stays pinned at top — the Social card glows amber while
this happens, so the viewer always knows which stage they're
watching.

Voice-over: "We drop those variants into a multi-agent social
simulation. Each node is an agent with persona, memory, and feed
dynamics — you're watching the audience materialise around the
content right now."

After ~30 sec on the live graph, switch to the Simulation tab for
the per-cycle sentiment trajectory and a few sample agent posts.

### 1:10 — Iteration loop

Pop the Iteration trajectory chart (already in the Campaign tab).
Three iterations, attention rising 67 → 74 → 79.

Voice-over: "Qwen3.5-27B reads both readouts and writes the next
variant. We loop until thresholds clear or the score curve flattens."

### 1:25 — Report tab — Verdict

The 4-layer report's Verdict block. Short, opinionated.

Voice-over: "End state: a verdict, a scorecard, and a mass-psychology
narrative. Same brief, four iterations later."

### 1:40 — Stack diagram (1 slide)

Overlay the architecture: MI300X / vLLM (Qwen3.5-9B + 27B) / TRIBE
(Whisper + LLaMA brain encoder) / OASIS / orchestrator / React.

Voice-over: "End-to-end on AMD. ROCm 6.x, vLLM 0.17.1, no NVIDIA. One
GPU."

### 2:00 — Close

Single line on screen: "ARC Studio · github.com/[user]/ARC_Studio ·
AMD Hackathon 2026"

## Narration principles

- **No internal jargon**. "TRIBE" appears once with the Meta FAIR
  citation; "MiroFish" once. Otherwise: "neural readout", "social
  simulation", "iteration loop".
- **Show, not tell**. The viz earns the time it takes; talk over it.
- **No live debugging**. The recording uses a pre-cooked campaign
  (Phase 4 artifacts: `phase4_step5.json`).
- **Qwen-first**. Pipeline labels surface Qwen3.5-9B and Qwen3.5-27B
  on every screen — say the model names out loud at least once.

## Pre-recording checklist

- [ ] Cloud MI300X provisioned, snapshot restored, all services up
- [ ] Pre-cooked campaign loaded into orchestrator DB (Phase 4 artifact)
- [ ] Apple 1984 mp4 staged at `ui/public/demo_assets/apple_1984.mp4`
- [ ] Mock toggle OFF (real TRIBE timeline available from Phase 5
      session 2 cloud run)
- [ ] Browser zoom 110% so text reads on a 1080p capture
- [ ] Window pinned to 16:9; close all OS notifications
- [ ] Sidebar starts expanded so the auto-collapse-on-run is visible
      in-recording (clear `arc:sidebar-collapsed` localStorage key)
- [ ] Verify `/api/config` returns Qwen labels (no Anthropic fallback)
- [ ] Trigger a fresh page reload mid-mirofish during the dry run to
      confirm the SSE history-replay reconstructs the active glow
- [ ] Smooth scroll behavior tested at 1080p × 110% — sticky pipeline
      header stays pinned, auto-scroll respects user scroll for 2s

## Risks / fallbacks

- **GPU clock parking** (Phase 4 finding): if throughput is still ~12
  tok/s the iteration loop section runs long. Fallback: show pre-
  recorded iteration loop instead of live.
- **Mock-vs-live timeline**: if cloud-side TRIBE timeline doesn't land
  in time, the mock is plausible enough to ship — disclose in voice-over.
- **MiroFish 1:1 entity→agent constraint** (Phase 4 backlog item 4):
  the 20-agent demo is the honest number; don't claim 1000 unless
  Phase 5 session 2 actually delivers it.
- **Auto-scroll fights the presenter**: if the demo presenter wants
  to manually scroll mid-demo, the 2s suppression window kicks in;
  if you need to override entirely for the recording, comment out
  the `useStageAutoscroll` call in `campaign-detail.tsx`.
