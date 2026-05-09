# Phase 5 session 2 runbook — cloud rehearsal: real demo artifacts on Apple 1984

Restore from the Phase 4 snapshot, sync session-1 commits + the demo
mp4, prove the new VideoStimulusPlayer + TimelineChart work end-to-end
against **real TRIBE timeline data** through an SSH-tunnelled browser,
then capture the artifacts the Phase 6 demo recording will use.

> Cost: ~$1.99/hr. Budget: **6 cloud hours total** for the rest of
> Phase 5; remaining ~3 hr after sessions 1+2 prep. Hard stop **4:00
> wallclock per session**.

This is **interactive** — Reddy drives the browser + ssh shell, Claude
co-pilots commands and diagnoses errors. No autonomous long-running
operations without checkpoint.

## 0. Local prep (5 min, BEFORE provisioning)

- [ ] Most recent commit on `competition/amd-hackathon` is the
  `phase5: bump video upload limits` commit (`2a05bab`) plus any
  follow-ups. `git log --oneline competition/amd-hackathon ^main | head -10`
  shows the Phase 5 session-1 commits + the limit bump.
- [ ] All session-1 commits pushed to origin:
  `git ls-remote origin competition/amd-hackathon` matches local
  `git rev-parse competition/amd-hackathon`.
- [ ] AMD Developer Cloud UI → Snapshots → confirm Phase 4 snapshot
  exists. Record snapshot ID: `_______________`
- [ ] `demo_assets/apple_1984.mp4` exists locally. Confirm:
  - size: `ls -lh demo_assets/apple_1984.mp4` → ~41 MB
  - duration: `ffprobe -v error -show_entries format=duration -of csv=p=0 demo_assets/apple_1984.mp4` → ~60 s
  - both within the new 50 MB / 120 s upload limits.
- [ ] `.env.hackathon` filled with current `HF_TOKEN` + `NEO4J_PASSWORD`.
  If `HF_TOKEN` rotated since Phase 4, regenerate.
- [ ] SSH key sanity: `ls ~/.ssh/amd_dev ~/.ssh/amd_dev.pub`
- [ ] **4-hour timer on phone**. Snapshot+destroy when it goes off.
- [ ] Open this runbook + `05_phase4_runbook.md` (failure-mode table is
  largely reusable) + `06_demo_plan.md` (so you know which artifacts
  the demo needs).

## 1. Restore from snapshot + SSH with port forwarding (5 min)

- [ ] AMD Cloud UI → **Restore from snapshot** (not "new instance").
  Use the Phase 4 snapshot.
- [ ] Note the new public IP: `_______________`
- [ ] **SSH with -L flags so the local browser can hit the cloud UI
  through the tunnel.** Easy to forget — without these the rehearsal
  is impossible to drive interactively.

  ```bash
  ssh -i ~/.ssh/amd_dev \
      -L 8002:localhost:8002 \
      -L 5173:localhost:5173 \
      -L 8001:localhost:8001 \
      -L 5001:localhost:5001 \
      root@<droplet-ip>
  ```

  - `8002` orchestrator FastAPI
  - `5173` vite dev server (or whatever the UI lands on)
  - `8001` tribe_scorer (handy for direct API checks)
  - `5001` mirofish (handy for direct API checks)

  Verify locally before continuing: `curl -fsS http://127.0.0.1:8002/api/health`
  will fail (orchestrator not started yet) but the connection itself
  should not refuse — that proves the tunnel is live.

- [ ] On the droplet: `rocm-smi --showmeminfo vram | grep VRAM`
  → `205822885888` (191.7 GB).
- [ ] HF cache survived snapshot:
  `du -sh /root/.cache/huggingface 2>/dev/null || du -sh ~/.cache/huggingface`
  → expect ~80–135 GB.
- [ ] tribe_scorer + vllm images present:
  `docker images | grep -E 'tribe_scorer|vllm'`.

If HF cache or tribe_scorer image is missing, the snapshot lost docker
volumes / image layers. **STOP** and decide rebuild-vs-escalate before
spending more meter.

## 2. Sync repo + scp the demo mp4 (5 min)

```bash
cd ~/ARC_Studio
git fetch origin
git checkout competition/amd-hackathon
git reset --hard origin/competition/amd-hackathon   # repo wins over snapshot working copy
git log --oneline -10
```

- [ ] Top of log shows the Phase 5 session-1 commits ending at the
  `phase5: bump video upload limits` commit.

Re-create the env symlink + source vars:

```bash
ls -l .env || ln -s .env.hackathon .env
set -a; source .env.hackathon; set +a
echo "$LLM_PROVIDER  ${HF_TOKEN:0:8}"
```

Refresh the venv (session-1 added no new requirements but be defensive):

```bash
.venv/bin/pip install -q -r orchestrator/requirements.txt
.venv/bin/python -c "import openai, fastapi, multipart; print('deps OK')"
```

scp the demo mp4 from your laptop into the droplet (the file is
gitignored at 41 MB):

```bash
# From your laptop, NOT the droplet
scp -i ~/.ssh/amd_dev demo_assets/apple_1984.mp4 \
    root@<droplet-ip>:~/ARC_Studio/demo_assets/

# Mirror it into ui/public/ so the Vite dev server can serve it as
# /demo_assets/apple_1984.mp4 — VideoStimulusPlayer expects that path.
ssh -i ~/.ssh/amd_dev root@<droplet-ip> \
    "mkdir -p ~/ARC_Studio/ui/public/demo_assets && \
     cp ~/ARC_Studio/demo_assets/apple_1984.mp4 \
        ~/ARC_Studio/ui/public/demo_assets/"
```

- [ ] Both copies in place: `ls -lh demo_assets/apple_1984.mp4 ui/public/demo_assets/apple_1984.mp4`.

## 3. GPU clock check (2 min, defensive)

The Phase 4 finding: AMD Cloud control plane parks the GPU at a low
perf level and `setperflevel` is denied. Don't waste time fighting it —
log the state and move on.

```bash
rocm-smi --showperflevel
sudo rocm-smi --setperflevel high 2>&1 | head -3   # expected: "Not supported on the given system"
```

- [ ] Recorded perf level: `_______________`
- [ ] If still locked, accept Phase-4-tier throughput (~12–16 tok/s).
  Don't escalate in this session; the AMD support ticket is the lever.

## 4. Bring up the stack + serve the UI (8–10 min)

Same Phase 4 sequence: agents → orchestrator → tribe + mirofish + neo4j.

```bash
cd ~/ARC_Studio
set -a; source .env.hackathon; set +a

docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d vllm-agents
until curl -sf -m 3 http://127.0.0.1:18001/v1/models > /dev/null; do
  sleep 5; docker ps --format '{{.Names}}\t{{.Status}}' | grep vllm-agents
done
echo "agents up"

docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d vllm-orchestrator
until curl -sf -m 3 http://127.0.0.1:18000/v1/models > /dev/null; do
  sleep 5; docker ps --format '{{.Names}}\t{{.Status}}' | grep vllm-orchestrator
done
echo "orchestrator up"

docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d neo4j tribe_scorer mirofish
docker compose ps
```

> Reminder from Phase 3/4: tribe_scorer's lifespan runs the 15-text
> baseline before yielding. ~3–5 min where `Empty reply from server`
> is normal. Watch `docker logs -f arc-tribe-scorer` for `Baseline
> ready. Service is up.`

- [ ] All 5 services healthy.
- [ ] `curl http://127.0.0.1:8001/api/health | jq '.baseline_size'` → 15.
- [ ] `curl http://127.0.0.1:5001/health` → `{"status":"ok"}`.

Native orchestrator on host (port 8002):

```bash
setsid nohup .venv/bin/python -m uvicorn orchestrator.api:create_app \
  --factory --host 0.0.0.0 --port 8002 < /dev/null > /tmp/orch.log 2>&1 &
sleep 6
curl http://127.0.0.1:8002/api/health | jq
```

- [ ] Health response: every service `ok`. mirofish `ok` (not
  `unavailable`) — same Phase 4 gate.
- [ ] `/tmp/orch.log` shows `LLM provider: vllm` + `Separate agent-tier
  endpoint:` lines.

### UI: vite dev server (decision: dev mode)

The repo already builds cleanly with `npm run build`. **Pick vite dev**
(`npm run dev --host 0.0.0.0`) for this session — hot reload makes
diagnosis faster and the production-build path is identical to what
session 1 already verified locally. Document if the cloud box doesn't
have node installed.

```bash
which node || (apt-get update && apt-get install -y nodejs npm)
cd ~/ARC_Studio/ui
npm install --no-fund --no-audit
nohup npm run dev -- --host 0.0.0.0 --port 5173 < /dev/null \
  > /tmp/ui.log 2>&1 &
sleep 8
tail /tmp/ui.log
```

Configure the UI's API base URL to hit the orchestrator on :8002:

```bash
# If the UI already reads VITE_API_BASE from env, set it; otherwise check
# ui/src/api/client.ts for the base URL constant.
grep -n "API_BASE\|VITE_API\|baseURL" ui/src/api/*.ts | head -5
```

- [ ] Open http://localhost:5173 in your **local** browser (the
  tunnel forwards it). UI loads, no failed-to-fetch banners.
- [ ] Open the campaign-list page; existing Phase 4 campaign still
  visible (snapshot preserved the SQLite db).

## 5. Cold smoke — validate real TRIBE timeline renders in browser (~10–15 min)

This is the gate for the rehearsal. Tiny campaign, but it must prove:
**video upload → TRIBE trimodal scoring → results land in API → UI
renders the real timeline (not the mock fallback) in
VideoStimulusPlayer**.

Use the CLI flags wired in session 1:

```bash
.venv/bin/python -m orchestrator.cli \
  --media-type video \
  --media-path ~/ARC_Studio/demo_assets/apple_1984.mp4 \
  --prediction-question "Will viewers find this ad memorable and emotionally compelling?" \
  --demographic tech_professionals \
  --agent-count 20 \
  --max-iterations 1 \
  --variant-count 1 \
  --output /tmp/smoke_p5.json
```

(`--variant-count 1` keeps the smoke fast; if the CLI doesn't yet
expose that flag, drop it and accept 2 variants.)

### Gate: every box must check

- [ ] CLI exits 0
- [ ] TRIBE: `is_pseudo_score=false` on the variant
- [ ] **TRIBE response carries `timeline` and `tr_seconds`** —
  inspect: `jq '.iterations[-1].variants[0].tribe_scores | {tr_seconds, timeline_keys: (.timeline|keys)}' /tmp/smoke_p5.json`
  → expect `tr_seconds` numeric, 7 channel keys.
- [ ] mirofish_metrics non-null
- [ ] All 7 composite scores non-null

**Now switch to the browser** (still tunnelled):

- [ ] Navigate to the smoke campaign's detail page.
- [ ] Stimulus Playback section visible above Composite profile.
- [ ] Header chip says **"using live · switch to mock"** (not "mock
  data") — that proves the real timeline made it to the UI.
- [ ] Click play on the video. The vertical playhead in the chart
  tracks the video's currentTime. All 4 channels render lines.
- [ ] Channel curves are NOT identical to the mock — they're driven by
  the real TRIBE response.

If the chart renders but says "mock data" instead of "using live":
**STOP** before any larger run. The most likely cause is API contract
drift between session 1's TribeScores schema and the real TRIBE
response — diagnose now while the campaign is small.

```bash
# Diagnostics
curl -s http://127.0.0.1:8002/api/campaigns | jq '.campaigns[-1].id'
CID=$(curl -s http://127.0.0.1:8002/api/campaigns | jq -r '.campaigns[-1].id')
curl -s http://127.0.0.1:8002/api/campaigns/$CID | jq '.iterations[-1].variants[0].tribe_scores | keys'
# Expect: ["attention_capture", ..., "is_pseudo_score", "timeline", "tr_seconds"]
```

## 6. Run A — Rehearsal campaign (~30–40 min)

The "real" rehearsal artifact. Single iteration, single variant, but
N=100 to look like a credible demo.

```bash
.venv/bin/python -m orchestrator.cli \
  --media-type video \
  --media-path ~/ARC_Studio/demo_assets/apple_1984.mp4 \
  --prediction-question "Will viewers find this ad memorable and emotionally compelling?" \
  --demographic tech_professionals \
  --agent-count 100 \
  --max-iterations 1 \
  --variant-count 1 \
  --output /tmp/phase5_apple_n100.json \
  2>&1 | tee /tmp/phase5_apple_n100.log
```

**During the run**, in the local browser:
- [ ] Campaign-detail page open in another tab. ProgressStream (SSE)
  shows iteration steps advancing without freezing.
- [ ] Simulation tab visible at some point — agent count climbing
  during MiroFish phase, not stuck at 0.
- [ ] No "Failed to fetch" banners. F12 Network tab shows the
  EventSource connection alive (status "pending").

**After exit (CLI 0):**
- [ ] Total wallclock recorded: `_______________` min
- [ ] Stimulus Playback shows real timeline driven by Apple 1984
  TRIBE response.
- [ ] Composite profile bars populated.
- [ ] Simulation tab has agent grid + sentiment trajectory.
- [ ] Report tab has all 4 layers.

scp the artifacts back to your laptop for the docs/ directory:

```bash
# From laptop
scp -i ~/.ssh/amd_dev \
    root@<droplet-ip>:/tmp/phase5_apple_n100.json \
    docs/competition/phase5_apple_n100.json
scp -i ~/.ssh/amd_dev \
    root@<droplet-ip>:/tmp/phase5_apple_n100.log \
    docs/competition/phase5_apple_n100.log
```

If the API exposes the timeline separately (it currently doesn't —
it's nested in `tribe_scores` per session 1), pull it out for
inspection:

```bash
jq '.iterations[-1].variants[0].tribe_scores.timeline' \
    docs/competition/phase5_apple_n100.json \
    > docs/competition/phase5_apple_n100_timeline.json
```

**Screen capture during the run**: use OBS (or QuickTime / your
preferred local recorder) on **your laptop** — the SSH tunnel renders
the cloud UI in your local browser, so local capture works without
involving the droplet. Save the recording locally; do NOT try to
record on the droplet.

**Browser screenshots** to capture (drop into `docs/competition/screens/`):
- [ ] Campaign-detail with Stimulus Playback visible (video + timeline).
- [ ] Composite profile bars.
- [ ] Simulation tab with agent grid.
- [ ] Verdict panel.

### Decision gate

- Artifacts demo-quality? Real-time UI worked? → **proceed to Run B**
- Either failed? → **stop**. Diagnose, don't start Run B on the meter.

## 7. Run B — Scale validation (~75–90 min, OPTIONAL)

Only if Run A is clean and the 4-hour timer has > 90 min left.

```bash
.venv/bin/python -m orchestrator.cli \
  --media-type video \
  --media-path ~/ARC_Studio/demo_assets/apple_1984.mp4 \
  --prediction-question "Will viewers find this ad memorable and emotionally compelling?" \
  --demographic tech_professionals \
  --agent-count 500 \
  --max-iterations 1 \
  --variant-count 1 \
  --output /tmp/phase5_apple_n500.json \
  2>&1 | tee /tmp/phase5_apple_n500.log
```

Watch for:
- MiroFish OOM or per-cycle timeout
- vllm-agents queue depth instability (`docker logs -f arc-vllm-agents`)
- UI responsiveness with many agents in the agent-grid view

**If anything breaks past agent ~150**: kill the run, snapshot whatever
state landed, surface logs. Don't iterate at scale on the meter.

```bash
pkill -f 'orchestrator.cli' || true
docker logs --tail 200 arc-mirofish > /tmp/mirofish_n500.log
docker logs --tail 200 arc-vllm-agents > /tmp/agents_n500.log
```

If clean, scp `phase5_apple_n500.json` + `.log` back to your laptop
the same way as Run A.

## 8. Snapshot + destroy (5 min)

```bash
# On droplet
docker compose -f docker-compose.yml -f docker-compose.rocm.yml stop
pkill -f 'uvicorn orchestrator' || true
pkill -f 'npm run dev' || true
```

- [ ] AMD Cloud UI → snapshot (Phase 5 session 2). Preserves the
  cloud's npm install + any compose tweaks.
- [ ] **Destroy droplet** — meter stops.

Update locally:

```bash
# Edit docs/competition/01_migration_plan.md Phase 5 session 2 section:
# - actual cloud hours used
# - which runs landed (A only? A+B?)
# - real-time UI behavior summary (one-liner)
# - any new failure modes
git add docs/competition/01_migration_plan.md docs/competition/phase5_apple_*
git commit -m "phase5/session2: cloud rehearsal — Apple 1984 N=100 [+N=500]"
git push origin competition/amd-hackathon
```

## Hour budget

| Step | Budget | Cumulative |
|------|--------|-----------|
| 0–1  | 10 min | 0:10 |
| 2    | 5 min  | 0:15 |
| 3    | 2 min  | 0:17 |
| 4    | 10 min | 0:27 |
| 5    | 15 min | 0:42 |
| 6    | 40 min | 1:22 |
| 7 (optional) | 90 min | 2:52 |
| 8    | 5 min  | 2:57 |
| Slack | 1:03 | 4:00 |

**Without Run B**: 1:25. **With Run B**: 3:35. **Hard ceiling 4:00**.

## Failure-mode matrix

Carry-over from Phase 3/4 still applies (vLLM unrecognized-architecture,
OOM, neuralset import, semaphore stalls, mirofish_metrics None,
snapshot SSH refused, HF cache missing, multipart import error,
generic-shallow Qwen output). New for session 2:

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| Local browser "Failed to fetch" against http://localhost:5173 or :8002 | SSH tunnel not active or orchestrator/UI not running | Confirm `-L 8002:localhost:8002 -L 5173:localhost:5173` flags are on the active ssh session. Re-ssh if needed. Confirm `lsof -i :8002` and `lsof -i :5173` on the droplet. |
| TimelineChart renders but VideoStimulusPlayer header says "mock data" | Real TRIBE response missing `timeline`/`tr_seconds`, OR API drops the field, OR UI types disagree | Inspect `jq '.iterations[-1].variants[0].tribe_scores | keys'` of the campaign result. If `timeline` absent: TRIBE-side regression. If present: orchestrator schema/serialisation drift. Compare against `docs/competition/TRIBE_API.md`. |
| Real-time updates frozen mid-run | SSE connection dropped or polling broken | F12 Network tab; look for failed EventSource or 5xx. `docker logs --tail 50 arc-mirofish` for stalls. |
| Video upload rejected at the API | size/duration past the new 50 MB / 120 s limits, or `media_path` resolution issue | Confirm Apple 1984 mp4 is 41 MB / 60 s. Check FastAPI multipart limits in `orchestrator/api/campaigns.py`. |
| Video plays but currentTime never updates the chart playhead | `onTimeUpdate` not firing — usually a missing `controls` attr or a CORS/source-load failure | F12 Console for HTMLMediaElement errors. Confirm `/demo_assets/apple_1984.mp4` returns 200 from the vite dev server. |
| `npm install` fails on droplet (no node, package-lock conflict) | snapshot didn't include node, or session-1 added deps | `apt-get install -y nodejs npm` then retry. If lockfile conflict: `rm -rf node_modules && npm install`. |
| MiroFish OOM at high N (Run B) | Agent state accumulation past KV-cache headroom on agent-tier | Drop N to ≤150. Surface OASIS logs. Backlog item — don't tune live. |
| 4-hour timer fires mid-Run-B | Hard cap | Snapshot+destroy regardless of state. Whatever artifact lands is what session 2 produced. |

## Out-of-scope for session 2

- 8× MI300X experiments (separate session)
- 4-iteration full campaign at scale (uses too much budget; session
  1's N=20×2-iter loop already proved iteration evolution in Phase 4)
- UI polish (post-demo-recording, Phase 6)
- Demo recording itself (separate session, after all artifacts captured)
- 1000-agent run (deferred until per-entity persona multiplier from
  Phase 4 backlog item 4 lands — current MiroFish 1:1 entity→agent
  caps the honest agent count regardless of N flag)
- Source code changes — if a real bug surfaces, snapshot+destroy and
  fix locally; do not patch on the droplet
