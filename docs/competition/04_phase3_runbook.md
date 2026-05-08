# Phase 3 runbook — first MI300X session

The script you follow at hour 22 of the hackathon. **Read every line before SSH.** Time-box: 3 cloud hours (Phase 3 budget). Hard stop at 4 hours — escalate if not done.

> Cost: ~$1.99/hr while the droplet is up. Snapshot before destroying.

## 0. Local prep (5 min, do BEFORE provisioning)

- [ ] Confirm latest commits pushed: `git log --oneline competition/amd-hackathon ^main` shows Phase 0 + 1 + 2 commits.
- [ ] Confirm HF_TOKEN you'll use is in your password manager. **Do not commit it.**
- [ ] Confirm you've requested access to `Qwen/Qwen3.5-9B`, `Qwen/Qwen3.5-27B`, `Qwen/Qwen3-8B`, `Qwen/Qwen3-32B`, AND `facebook/tribev2` on huggingface.co — gate-approval can take hours.
- [ ] Confirm SSH key exists: `ls ~/.ssh/amd_dev` (private) and `~/.ssh/amd_dev.pub` (public, already added to AMD Cloud).
- [ ] Open this runbook in a browser tab on your laptop.

## 1. Provision MI300X droplet (~5 min wallclock)

- [ ] AMD Developer Cloud → New instance → MI300X 1× → vLLM Quick Start image
- [ ] Note the **vLLM image tag/version** the Quick Start uses. Write it here: `_______________`
- [ ] SSH in: `ssh -i ~/.ssh/amd_dev ubuntu@<droplet-ip>`
- [ ] Confirm GPU visible: `rocm-smi` should list 1× MI300X 192GB.

> **Note on the Quick Start image**: the AMD vLLM Quick Start ships with vLLM pre-installed at the host OS level. We don't use that. Our compose stack runs vLLM from `rocm/vllm:latest` containers instead. The Quick Start image is functioning here as "ROCm + Docker + GPU passthrough, ready to go." Don't try to mix host-vLLM with container-vLLM — pick one. (We pick container.)

## 2. Clone repo + env (~5 min)

**Local (before SSH)** — prepare the env file with secrets so you don't type them on the meter:

```bash
cp .env.hackathon.example .env.hackathon
$EDITOR .env.hackathon                # paste HF_TOKEN, set NEO4J_PASSWORD
scp -i ~/.ssh/amd_dev .env.hackathon ubuntu@<droplet-ip>:~/.env.hackathon
```

**On droplet (after SSH)**:

```bash
git clone -b competition/amd-hackathon https://github.com/AR6420/ARC_Studio.git
cd ARC_Studio
git submodule update --init --recursive
mv ~/.env.hackathon .env.hackathon
ln -s .env.hackathon .env             # so docker compose's default discovery works
set -a; source .env.hackathon; set +a # so the shell has the vars for ad-hoc curl/echo
```

The symlink is so `docker compose` picks the file up automatically (compose looks for `.env` by default, not `.env.hackathon`, so without the link `${VAR}` substitutions in the compose files would silently fall back to defaults). The `source` line is so the shell has the same vars for ad-hoc commands.

- [ ] `echo $LLM_PROVIDER` prints `vllm`
- [ ] `echo $HF_TOKEN | head -c 10` prints `hf_xxxxx` (not the literal placeholder)
- [ ] `ls -l .env` shows `.env -> .env.hackathon`

## 3. Pre-flight: vLLM version (2 min)

```bash
docker run --rm ${VLLM_IMAGE:-rocm/vllm:latest} vllm --version 2>&1 | tee /tmp/vllm-version.log
```

- [ ] Record version here: `vllm _______________`
- [ ] **Decision gate**: if version ≥ 0.18 OR explicit Qwen3.5 support is documented, proceed with primary models. If 0.17.x and Qwen3.5 support unverified, expect step 5 to potentially fail; have the fallback edit ready.

## 4. Pre-pull weights (~20-40 min — biggest variable)

```bash
bash scripts/prefetch_models.sh 2>&1 | tee /tmp/prefetch.log
```

- [ ] All four models downloaded without error
- [ ] HF cache size: `_______________` GB (expect ~120-160 GB)
- [ ] If a model 401s: HF gate-approval not granted. Skip that model; you'll fall back to whichever pair is fully cached.

## 5. First model startup — agent tier ONLY (10-20 min)

Start the smaller model alone first. If this works, the larger one likely works too. If it doesn't, debug here, not after spinning up two services.

```bash
docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d vllm-agents
docker compose logs -f vllm-agents
```

Watch for one of:
- ✅ `Uvicorn running on http://0.0.0.0:8001` — proceed to step 6.
- ❌ `Unrecognized model architecture` / `qwen3_5` not found / NotImplementedError — **flip to fallback**:
  ```bash
  # In .env.hackathon, change:
  VLLM_AGENT_MODEL=Qwen/Qwen3-8B
  VLLM_ORCHESTRATOR_MODEL=Qwen/Qwen3-32B
  set -a; source .env.hackathon; set +a
  docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d --force-recreate vllm-agents
  ```
  Re-watch logs. If still failing, escalate. Do NOT spend > 30 min on this gate.
- ❌ `out of memory` — reduce `VLLM_AGENT_MEM_UTIL` to 0.30, `--force-recreate`, retry.

Once `/v1/models` responds:

```bash
curl http://127.0.0.1:18001/v1/models | jq
curl http://127.0.0.1:18001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"'"$VLLM_AGENT_MODEL"'","messages":[{"role":"user","content":"Reply with the single word PONG."}],"max_tokens":20}' | jq -r .choices[0].message.content
```

- [ ] Returns a sensible response (contains `PONG` or close). Record which path was taken: **primary / fallback** ☐ ☐
- [ ] Record agent VRAM after warmup: `rocm-smi --showmemuse` → `_______________` GB

## 6. Second model startup — orchestrator tier (10-20 min)

```bash
docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d vllm-orchestrator
docker compose logs -f vllm-orchestrator
```

- [ ] Same `/v1/models` + chat smoke as step 5, on port 18000
- [ ] **VRAM check**: `rocm-smi --showmemuse` total used should be < 130 GB. If it's higher, you have no headroom for KV-cache burst — reduce one of the `MEM_UTIL` settings and recreate.

## 7. Bring up the rest of the stack (~5 min)

```bash
docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d \
  neo4j tribe_scorer mirofish
docker compose ps
```

- [ ] All services `healthy` (may take ~3 min for tribe_scorer + mirofish to clear `start_period`)
- [ ] `curl http://127.0.0.1:8001/api/health | jq` → TRIBE shows `gpu_available=true`
- [ ] `curl http://127.0.0.1:5001/health` → MiroFish OK

## 8. Native orchestrator on host (3 min)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r orchestrator/requirements.txt
python -m uvicorn orchestrator.api:create_app --factory --port 8000 &
sleep 5
curl http://127.0.0.1:8000/api/health | jq
```

- [ ] Health response shows `tribe_available=true` and `mirofish_available=true`
- [ ] Orchestrator log line `LLM provider: vllm (OpenAICompatClient -> http://127.0.0.1:18000/v1)`

## 9. Smoke campaign — N=10 agents (~5 min)

```bash
python -m orchestrator.cli \
  --seed-content "Free shipping on orders over fifty dollars this weekend only." \
  --prediction-question "Will users find this offer compelling?" \
  --demographic tech_professionals \
  --agent-count 10 \
  --max-iterations 1 \
  --output /tmp/smoke.json
```

- [ ] CLI exits 0
- [ ] `/tmp/smoke.json` contains non-pseudo TRIBE scores (`is_pseudo_score: false`)
- [ ] Composite scores are non-null
- [ ] Cross-system Opus-equivalent analysis (Qwen) returned structured JSON
- [ ] Total wallclock: `_______________` s (target: < 5 min for N=10)

## 10. Snapshot + tear down (5 min)

- [ ] `docker compose down` — graceful stop
- [ ] AMD Developer Cloud UI → snapshot the droplet (preserves HF cache + image pulls)
- [ ] **Destroy droplet** — meter stops
- [ ] Update `01_migration_plan.md` Phase 3 section with actual hours consumed and which model pair was used

## Hour budget

| Step | Budget | Cumulative |
|------|--------|-----------|
| 0–4  | 35 min | 0:35 |
| 5    | 30 min | 1:05 | <- includes ~5–10 min `rocm/vllm:latest` first pull
| 6    | 15 min | 1:20 | <- second tier reuses the pulled image
| 7    | 20 min | 1:40 | <- includes ~10–15 min local build of `tribe_scorer/Dockerfile.rocm`
| 8    | 5 min  | 1:45 |
| 9    | 10 min | 1:55 |
| 10   | 5 min  | 2:00 |
| Slack| 0:55   | 2:55 |

First-time overhead is real and visible: the first `docker compose up vllm-agents` blocks on a `rocm/vllm:latest` pull (~10 GB), and `tribe_scorer` builds locally on the droplet because the image isn't in any registry. Net effect: slack drops from ~1:30 (Phase 2 estimate) to ~0:55. If a step blows its budget, **don't reach into slack until you've decided whether the failure is a known issue from the failure-mode table below**.

**If you hit 2:55 with step 9 still failing, snapshot and destroy.** Diagnose offline; come back with a fixed plan, not on the meter.

## What can go wrong (and what to do)

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| `vllm --version` errors | wrong image tag | Try `rocm/vllm:rocm6.2_vllm_0.8.5` or whatever AMD docs list; update `.env.hackathon`'s `VLLM_IMAGE` |
| `Unrecognized model architecture` | Qwen3.5 too new for shipped vLLM | Flip to Qwen3 fallback (step 5) |
| `out of memory` on second vLLM start | both tiers + cache > 192 GB | Reduce `VLLM_*_MEM_UTIL` to 0.35 each |
| TRIBE startup hangs > 5 min | first-time HF download of `facebook/tribev2` | Wait; first weight pull is slow on cloud-to-HF network. If > 15 min, check `docker compose logs tribe_scorer` for actual error |
| `neuralset` import error | Meta-internal lib not ROCm-compatible | Out-of-budget for Phase 3; mark TRIBE as pseudo-only for the demo and proceed |
| MiroFish 30-agent semaphore stalls | KV-cache exhaustion on Qwen3.5-9B | Reduce `--max-num-seqs` (add `command:` arg `--max-num-seqs=15`) |
| `git clone` 404 / auth prompt | Repo not public, or wrong URL | Verify URL via `git remote get-url origin` on local box; if private, generate GitHub PAT and clone over HTTPS with token |
| `docker compose` errors with "variable is not set" | `.env` symlink missing or .env.hackathon not sourced | Confirm `ls -l .env` shows symlink to `.env.hackathon`; re-run `set -a; source .env.hackathon; set +a` |
| `docker: command not found` | Quick Start image somehow without Docker (rare) | `sudo systemctl start docker` first; if missing, install per AMD docs (out of Phase 3 budget — escalate) |

## Out-of-scope for Phase 3

- 1000-agent demo (Phase 5)
- UI integration (Phase 5)
- Performance tuning beyond MEM_UTIL (Phase 4)
- vLLM image source-build (escalate; not a Phase 3 task)
