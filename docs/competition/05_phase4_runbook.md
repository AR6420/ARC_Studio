# Phase 4 runbook — first real campaign on MI300X

Restore from the Phase 3 snapshot, validate that the 7 backport commits actually fix the MiroFish skip, then drive the CLAUDE.md target: 40 agents × 4 iterations under 20 min.

> Cost: ~$1.99/hr. Budget: **6 cloud hours total**, expected to split across 1–2 sessions. Hard stop **4:00 wallclock per session**.

## 0. Local prep (5 min, BEFORE provisioning)

- [ ] `git log --oneline competition/amd-hackathon ^main | head -12` shows 12 commits, most recent ending `f53f702 backport(phase3): items 7+8`. The 5 backport commits are on origin.
- [ ] AMD Developer Cloud UI → Snapshots → confirm Phase 3 snapshot exists. Record snapshot ID: `_______________`
- [ ] `.env.hackathon` still filled locally with current `HF_TOKEN` + `NEO4J_PASSWORD`. If `HF_TOKEN` rotated, regenerate.
- [ ] SSH key sanity: `ls ~/.ssh/amd_dev ~/.ssh/amd_dev.pub`
- [ ] **4-hour timer on phone**. When it goes off, snapshot+destroy regardless of state.
- [ ] Open this runbook + `04_phase3_runbook.md` (failure-mode table is reusable) in browser tabs.

## 1. Restore from snapshot (5 min)

- [ ] AMD Cloud UI → **Restore from snapshot** (not "new instance"). Use the Phase 3 snapshot.
- [ ] SSH in: `ssh -i ~/.ssh/amd_dev root@<new-ip>` (note: snapshot may use `root` not `ubuntu` — verify).
- [ ] Confirm GPU: `rocm-smi --showmeminfo vram | grep VRAM` → `205822885888` (191.7 GB).
- [ ] Confirm HF cache survived snapshot: `du -sh /root/.cache/huggingface 2>/dev/null || du -sh ~/.cache/huggingface` → expect **~80–135 GB** (Qwen3.5-9B + Qwen3.5-27B + en_core_web_lg + facebook/tribev2 + whisper-large-v3).
- [ ] Confirm tribe_scorer image present: `docker images | grep tribe_scorer` → expect `arc_studio-tribe_scorer:latest` ~36 GB.
- [ ] Confirm vLLM image present: `docker images | grep vllm` → expect `vllm/vllm-openai-rocm:v0.17.1` ~34 GB.

If the HF cache is missing or the tribe_scorer image is missing, the snapshot didn't capture the docker volumes / image layers. **STOP** and decide whether to rebuild from scratch (re-run Phase 3 build steps, ~40 min) or escalate.

## 2. Sync repo to latest backport state (3 min)

The snapshot has the Phase 3 source tree, which is **before** the 5 backport commits + 2 stoppage-fix commits land. Pull them now.

```bash
cd ~/ARC_Studio
git fetch origin
git checkout competition/amd-hackathon
git pull origin competition/amd-hackathon
git log --oneline -7
```

- [ ] Most recent commit ends `f53f702`. The seven commits since Phase 3 smoke are visible:
  ```
  f53f702 backport(phase3): items 7+8 — Dockerfile + --enforce-eager
  d9208a3 backport(phase3): items 2+3 — mirofish LiteLLM skip
  ad4309c backport(phase3): item 4 — strip <think> blocks
  8dc6dd2 backport(phase3): item 1 — dual base URL
  c45fa26 backport(phase3): items 5+6+9 — multipart, env, runbook
  88aeb51 phase3: cloud smoke test PASSED
  3132f57 phase3: runbook fixes
  ```

If the orchestrator-side patches the Phase 3 droplet had locally are now in the repo, the on-disk versions on the snapshot are stale. The pull should overwrite them; if there are merge conflicts, **the repo wins** (force the pull):

```bash
git reset --hard origin/competition/amd-hackathon
```

Re-create the env symlink + source (the snapshot may not have preserved it):

```bash
ls -l .env || ln -s .env.hackathon .env
set -a; source .env.hackathon; set +a
echo "$LLM_PROVIDER  $VLLM_IMAGE  ${HF_TOKEN:0:8}"
```

If `.env.hackathon` content has drifted locally (you edited the template after Phase 3), scp the fresh copy:

```bash
# From your laptop
scp -i ~/.ssh/amd_dev .env.hackathon root@<new-ip>:~/ARC_Studio/.env.hackathon
```

- [ ] `echo $LLM_PROVIDER` → `vllm`
- [ ] `echo $VLLM_IMAGE` → `vllm/vllm-openai-rocm:v0.17.1`
- [ ] `ls -l .env` → symlink to `.env.hackathon`

Refresh the venv (the orchestrator added `python-multipart` and config additions need import re-checking):

```bash
.venv/bin/pip install -q -r orchestrator/requirements.txt
.venv/bin/python -c "import openai, fastapi, multipart; print('deps OK')"
```

## 3. Bring up the stack (~10 min)

```bash
cd ~/ARC_Studio
set -a; source .env.hackathon; set +a
docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d vllm-agents
```

Wait for /v1/models on agent tier — should be **fast** (~1 min) because weights are cached:

```bash
until curl -sf -m 3 http://127.0.0.1:18001/v1/models > /dev/null; do
  sleep 5
  docker ps --format '{{.Names}}\t{{.Status}}' | grep vllm-agents
done
echo "agents up"
```

- [ ] `arc-vllm-agents` healthy. /v1/models returns Qwen/Qwen3.5-9B.

Now orchestrator tier (with `--enforce-eager` baked in via item 8 backport):

```bash
docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d vllm-orchestrator
until curl -sf -m 3 http://127.0.0.1:18000/v1/models > /dev/null; do
  sleep 5
  docker ps --format '{{.Names}}\t{{.Status}}' | grep vllm-orchestrator
done
echo "orchestrator up"
```

- [ ] `arc-vllm-orchestrator` healthy. /v1/models returns Qwen/Qwen3.5-27B.
- [ ] `rocm-smi --showmeminfo vram | grep 'Total Used'` < 130 GB. Headroom for KV-cache burst confirmed.

The remaining services:

```bash
docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d neo4j tribe_scorer mirofish
docker compose ps
```

> **Reminder from Phase 3**: tribe_scorer's lifespan runs the 15-text baseline synchronously before yielding to uvicorn. Health doesn't pass for ~3–5 min after start. `Empty reply from server` during this window is normal. Watch `docker logs -f arc-tribe-scorer` for `Baseline ready. Service is up.`

- [ ] All 5 services healthy: `tribe_scorer`, `vllm-agents`, `vllm-orchestrator`, `mirofish`, `neo4j`.
- [ ] `curl http://127.0.0.1:8001/api/health | jq '.baseline_size'` → 15.
- [ ] `curl http://127.0.0.1:5001/health` → `{"status":"ok"}`.

Native orchestrator on host (port 8002 to dodge the Quick Start jupyter on :8000):

```bash
setsid nohup .venv/bin/python -m uvicorn orchestrator.api:create_app \
  --factory --host 0.0.0.0 --port 8002 < /dev/null > /tmp/orch.log 2>&1 &
sleep 6
curl http://127.0.0.1:8002/api/health | jq
```

- [ ] Health response: every service shows `status: ok`. **mirofish must show `ok`, not `unavailable`** — that's the visible signal that item 2 (health_check skip) landed.
- [ ] `/tmp/orch.log` shows three startup lines:
  - `LLM provider: vllm (OpenAICompatClient -> http://127.0.0.1:18000/v1)`
  - `Separate agent-tier endpoint: http://127.0.0.1:18001/v1`
  - `OpenAICompatClient initialised: base_url=..., orchestrator=Qwen/Qwen3.5-27B, agent=Qwen/Qwen3.5-9B`

If any of those three lines is missing, **STOP** — the dual-base-URL backport (item 1) is not active. Pull again, restart orchestrator.

## 4. Validation smoke — N=20, 1 iteration (~10 min)

This is the gate. Same campaign as Phase 3, but the bar is higher:

```bash
.venv/bin/python -m orchestrator.cli \
  --seed-content "Free shipping on every order over fifty dollars this weekend only at our online store. Limited time offer ends Sunday at midnight. Sign up for our newsletter to unlock exclusive discounts." \
  --prediction-question "Will users find this offer compelling?" \
  --demographic tech_professionals \
  --agent-count 20 \
  --max-iterations 1 \
  --output /tmp/smoke_phase4.json
```

### Validation gate — every box must check

- [ ] CLI exits 0
- [ ] TRIBE: `is_pseudo_score=false` on both variants (Phase 3 result holds)
- [ ] **MiroFish: `mirofish_metrics` is NOT `None`** for any variant (Phase 4 new bar — items 2+3 unlock this)
- [ ] All 7 composite scores non-null on both variants. The Phase 3 smoke had `virality_potential / backlash_risk / memory_durability / polarization_index = None`; those should now be populated
- [ ] Qwen3.5-27B "Opus" cross-system analysis returned 3+ insights and a non-trivial verdict
- [ ] All 4 report layers generated (verdict, scorecard, mass-psych-general, mass-psych-technical)
- [ ] Total wallclock: `_______________` s (Phase 3 was ~9 min for the same campaign WITHOUT mirofish; expect 13–17 min with mirofish enabled)
- [ ] VRAM headroom after warmup: `rocm-smi --showmeminfo vram | grep 'Total Used'` → record GB used: `_______________`

### If `mirofish_metrics` is None on any variant — **STOP**

Items 2+3 didn't fully fix the blocker. Don't run further campaigns.

```bash
# Diagnostics to capture before destroying the droplet:
cat /tmp/orch.log | grep -iE 'mirofish|litellm|verify_llm_token' | tail -50
docker logs arc-mirofish 2>&1 | tail -100
docker logs arc-vllm-agents 2>&1 | grep -iE 'error|400|500|qwen' | tail -30
.venv/bin/python -c "import json; r=json.load(open('/tmp/smoke_phase4.json'))['iterations'][-1]; print('mirofish_metrics:', r.get('mirofish_metrics')); print('warnings:', r.get('warnings'))"
```

Decide on the spot: re-derive a fix locally on the droplet (commit + push from droplet, then continue) OR snapshot+destroy and fix in a dev session.

## 5. First real campaign — N=40, 4 iterations (~20 min target)

The CLAUDE.md performance constraint: **40 agents, 4 iterations, ≤ 20 min**. This is Phase 4's primary success criterion.

```bash
.venv/bin/python -m orchestrator.cli \
  --seed-content "Free shipping on every order over fifty dollars this weekend only at our online store. Limited time offer ends Sunday at midnight. Sign up for our newsletter to unlock exclusive discounts." \
  --prediction-question "Will users find this offer compelling?" \
  --demographic tech_professionals \
  --agent-count 40 \
  --max-iterations 4 \
  --output /tmp/campaign_p4.json \
  2>&1 | tee /tmp/campaign_p4.log
```

- [ ] CLI exits 0 OR exits with `stop_reason in {convergence, threshold, max_iterations}` (any of those is a clean stop)
- [ ] Total wallclock: `_______________` min  (target ≤ 20 min)
- [ ] All 4 iterations have non-None TRIBE + MiroFish metrics
- [ ] `best_scores_history` shows monotonic-or-slight-improvement across iterations (not flatline, not regression)
- [ ] Final report layers all generated
- [ ] No `pseudo_reason` strings in any iteration

### Bottleneck identification (only if > 20 min)

Pull per-stage timings from log:

```bash
grep -E 'Step [0-9]:|completed|inference|seconds' /tmp/campaign_p4.log | tail -50
```

Heuristic on culprit:
- TRIBE batch step (`/api/score/batch`) > 5 min/iteration → TRIBE bottleneck
- MiroFish step > 8 min/iteration → MiroFish/vLLM-agent bottleneck
- Opus analysis step > 3 min/iteration → vllm-orchestrator bottleneck

## 6. Tuning iteration — only if step 5 was > 20 min (~30 min budget)

**Hard rule: max 3 attempts, then stop.** Don't fall down the tuning hole on the meter.

Try in this order. After each change, **recreate the affected service** and re-run step 5.

### Attempt 1 — reduce vllm-agents `--max-num-seqs`

KV-cache pressure is the most common culprit. Add a flag:

```bash
# Edit docker-compose.rocm.yml on the droplet (not committed; one-shot tune)
sed -i '/--served-model-name=\${VLLM_AGENT_MODEL/a\      - --max-num-seqs=15' docker-compose.rocm.yml
docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d --force-recreate --no-deps vllm-agents
# wait for healthy, then re-run step 5
```

OASIS internal semaphore is `30` per platform per Phase 0 audit. Reducing `--max-num-seqs` to 15 forces vLLM to queue rather than overcommit KV-cache.

### Attempt 2 — reduce vllm-agents `--max-model-len`

If KV-cache reservation is the issue, drop max-model-len 16384 → 8192:

```bash
# In .env.hackathon
sed -i 's/VLLM_AGENT_MAX_MODEL_LEN=16384/VLLM_AGENT_MAX_MODEL_LEN=8192/' .env.hackathon
set -a; source .env.hackathon; set +a
docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d --force-recreate --no-deps vllm-agents
```

(Reverses the Phase 3 droplet bump from 8192→16384 made for variant generation. If short prompts work, 8192 fits and KV-cache doubles.)

### Attempt 3 — reduce orchestrator `--gpu-memory-utilization`

If memory pressure is in the orchestrator tier (sequential calls but big context):

```bash
sed -i 's/VLLM_ORCHESTRATOR_MEM_UTIL=0.40/VLLM_ORCHESTRATOR_MEM_UTIL=0.30/' .env.hackathon
set -a; source .env.hackathon; set +a
docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d --force-recreate --no-deps vllm-orchestrator
```

If 3 attempts fail to hit ≤ 20 min, **stop tuning**. Document the floor wallclock + bottleneck. Decide post-session whether the answer is hardware (more GPU), quantisation (FP8), or pipeline (drop iteration count).

## 7. Quality validation (~10 min)

Inspect the campaign output. The 7 composite scores should be in plausible ranges and the Qwen analysis should be substantive (not boilerplate).

```bash
.venv/bin/python - << 'PY'
import json
r = json.load(open('/tmp/campaign_p4.json'))
print('stop_reason:', r.get('stop_reason'))
print('iterations:', r.get('iterations_completed'))
print('best_scores_history:')
for i, s in enumerate(r.get('best_scores_history', [])):
    print(' ', i+1, s)
last = (r.get('iterations') or [{}])[-1]
print()
print('--- last iteration analysis ---')
a = last.get('analysis', {})
print('ranking:', a.get('ranking'))
print('insights:')
for ins in a.get('cross_system_insights', []):
    print('  -', ins[:200])
print('recommendations:')
for rec in a.get('recommendations_for_next_iteration', []):
    print('  -', rec[:200])
PY
```

- [ ] Composite scores within [0, 100] and varying meaningfully across variants
- [ ] Insights non-trivial — record one-line gist: `_______________`
- [ ] Recommendations actionable, not generic — record gist: `_______________`

If the orchestrator output looks shallow / boilerplate ("the campaign appears effective", "consider revising the messaging"), flag for **post-Phase-4 quality decision** about Qwen3.5-72B-FP8 promotion. **Do NOT switch models in this session.**

## 8. Snapshot + destroy (5 min)

```bash
docker compose -f docker-compose.yml -f docker-compose.rocm.yml stop
pkill -f 'uvicorn orchestrator' || true
```

Locally, scp the campaign artifact for the record:

```bash
# From laptop
scp -i ~/.ssh/amd_dev root@<ip>:/tmp/campaign_p4.json \
    docs/competition/phase4_campaign.json
scp -i ~/.ssh/amd_dev root@<ip>:/tmp/campaign_p4.log \
    docs/competition/phase4_campaign.log
```

- [ ] AMD Cloud UI → snapshot (Phase 4) — preserves any tuning knobs and built layers.
- [ ] **Destroy droplet** — meter stops.

Update locally:

```bash
# Edit docs/competition/01_migration_plan.md Phase 4 section with:
# - actual cloud hours used
# - whether tuning was needed (which attempt landed)
# - quality verdict (good / shallow / promote-72B)
# - any new failure modes encountered
git add docs/competition/01_migration_plan.md docs/competition/phase4_*
git commit -m "phase4: ..." && git push origin competition/amd-hackathon
```

## Hour budget

Snapshot-restore eliminates the Phase 3 build/download overhead (~40 min). New budget:

| Step | Budget | Cumulative |
|------|--------|-----------|
| 0–1  | 10 min | 0:10 |
| 2    | 5 min  | 0:15 |
| 3    | 10 min | 0:25 | (cached weights → fast vLLM startup; tribe baseline ~5 min still applies)
| 4    | 15 min | 0:40 |
| 5    | 25 min | 1:05 |
| 6 (if needed) | 30 min | 1:35 |
| 7    | 10 min | 1:45 |
| 8    | 5 min  | 1:50 |
| Slack| 2:10   | 4:00 |

**If you hit 4:00 with step 5 still running, snapshot+destroy.** The 4-hour wallclock is hard.

## Failure-mode matrix

Carry-overs from Phase 3 (still apply): vLLM unrecognized-architecture, OOM, neuralset import, semaphore stalls, docker missing, env var unset, clone 404. New for Phase 4:

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| `mirofish_metrics: None` after Phase 4 backports | items 2+3 didn't fully fix the blocker; runner has another preflight we missed | Capture diagnostics in step 4. Do NOT continue. Snapshot+destroy after diagnosis if the fix needs a dev session |
| Snapshot restore SSH refuses connection | UI shows restore complete but droplet is still booting | Wait 60s, retry. If > 5 min, escalate via AMD UI |
| HF cache empty after restore | snapshot didn't capture the docker named volume `vllm_hf_cache` | Re-run `scripts/prefetch_models.sh`; absorbs ~30 min |
| `tribe_scorer` image missing after restore | image was in local docker storage, not preserved by snapshot | Re-run `docker compose ... build tribe_scorer`; absorbs ~15 min |
| Campaign > 30 min wallclock | bottleneck at one stage | Use `grep -E 'Step|inference' /tmp/campaign_p4.log` heuristic in step 5; tune in step 6 |
| Qwen orchestrator output is generic / shallow | 27B may be undersized for nuanced analysis | Flag for post-Phase-4 quality call. Do NOT switch to 72B in-session |
| `git pull` fails with merge conflict | snapshot's working copy diverged from origin | `git reset --hard origin/competition/amd-hackathon` (origin wins) |
| `python-multipart` ImportError on orchestrator boot | venv on snapshot pre-dates item 5 backport | `.venv/bin/pip install -r orchestrator/requirements.txt` |

## Out-of-scope for Phase 4

- 1000-agent demo (Phase 5)
- UI integration (Phase 5)
- Demo content sourcing (Phase 6)
- Qwen3.5-72B-FP8 promotion — flag concerns from step 7, decide post-session
- Source code changes beyond .env / compose tuning — if a real bug surfaces, snapshot+destroy and fix locally
