# P-1 — TRIBE GPU scaling: local single-GPU + optional multi-GPU cloud

Status: **IMPLEMENTED** (the contained, testable parts). Supersedes the "propose only" status of P-1 in `architecture-proposals.md`. Approved direction: *design carefully for local single-GPU; multi-GPU is an option for cloud.*

## Design

One TRIBE process owns exactly one GPU and serializes its own inference (the model + exca cache are not thread-safe). Parallelism, when you want it, comes from running **N TRIBE processes, one per GPU**, with the orchestrator load-balancing across them. Nothing about a single process changes between local and cloud — you just run more of them and list them in one env var.

```
LOCAL (default)                         CLOUD (optional, multi-GPU)
┌─────────────┐                         ┌─────────────┐   TRIBE_SCORER_URLS=
│ orchestrator│                         │ orchestrator│   http://gpu0:8001,
└─────┬───────┘                         └─────┬───────┘   http://gpu1:8001,...
      │ 1 endpoint                            │ least-in-flight pool
      ▼                                   ┌───┼───┬───────┐
┌─────────────┐                          ▼    ▼   ▼       ▼
│ TRIBE :8001 │  ← bounded queue,     gpu0  gpu1 gpu2 ... each: 1 GPU,
│  1 GPU      │    503 when full,     each a TRIBE replica,      bounded queue,
└─────────────┘    queue_depth on     CUDA_VISIBLE_DEVICES=k     serialized
                   /health
```

## Local (single shared GPU) — careful backpressure + observability

The RTX 5070 Ti is shared between TRIBE and Ollama embeddings, so the goal is *graceful, visible* saturation, not throughput it can't deliver.

Implemented in `tribe_scorer/main.py`:
- **Bounded admission gate** (`_admission()`): caps concurrent scoring requests at `TRIBE_MAX_INFLIGHT` (default 8). Past that, the endpoint returns **503 + `Retry-After: 5`** instead of letting requests pile up invisibly behind `_inference_lock` for hours. The counter is mutated only on the event-loop thread (check-then-increment with no await between), so it's race-free without a lock.
- **Queue-depth observability**: `/api/health` now returns `queue_depth` + `max_queue_depth`. An operator (or the orchestrator) can see the backlog forming instead of discovering it via a wave of timeouts.
- The client treats 503 as retryable (5xx path) with jittered backoff; sustained 503s → endpoint cooldown → route elsewhere (cloud) or surface unavailable (local).

Tunable per host via `TRIBE_MAX_INFLIGHT`. On the shared local GPU, keep it small (≈ 4–8) — the point is backpressure, not concurrency.

## Cloud (optional multi-GPU) — least-in-flight pool

Implemented in `orchestrator/clients/tribe_client.py` + `config.py`:
- `TRIBE_SCORER_URLS` (comma-separated) → N endpoints. Empty (default) = the single `TRIBE_SCORER_URL` = local.
- The client tracks **in-flight count per endpoint** and routes each request to the **least-in-flight** endpoint (better than round-robin because inference times vary widely: short text vs chunked/audio/video).
- **Per-endpoint health + cooldown**: `health_check()` probes every endpoint; a replica that fails (or reports `cuda_healthy=false`) is put in a 30s cooldown and skipped by the balancer; a recovered probe clears it. `health_check()` returns healthy if *any* endpoint is up, so the pool degrades from N→N-1 replicas without failing the campaign.
- One shared `httpx.AsyncClient` fans out via absolute URLs (its per-host connection pool handles the rest). In-flight leases are released in `finally` on every path (success/failure/exception) — verified by `test_leases_drain_to_zero`.

Admission cap on the orchestrator (`max_concurrent_campaigns`) should scale with endpoint count — roughly `2–4 × len(TRIBE_SCORER_URLS)`.

## Deploy (cloud multi-GPU)

Run one TRIBE service per GPU, each pinned, then list them:

```yaml
# docker-compose.rocm.yml (sketch — one block per GPU)
tribe-gpu0:
  build: { context: ./tribe_scorer, dockerfile: Dockerfile.rocm }
  environment: [ "HIP_VISIBLE_DEVICES=0", "TRIBE_MAX_INFLIGHT=8" ]
  ports: ["127.0.0.1:8001:8001"]
tribe-gpu1:
  environment: [ "HIP_VISIBLE_DEVICES=1", "TRIBE_MAX_INFLIGHT=8" ]
  ports: ["127.0.0.1:8011:8001"]
```
```bash
# orchestrator env
TRIBE_SCORER_URLS=http://tribe-gpu0:8001,http://tribe-gpu1:8001
```
(`HIP_VISIBLE_DEVICES` for ROCm / `CUDA_VISIBLE_DEVICES` for CUDA pins each replica to one GPU.)

## What this does and does NOT solve

**Solved:** unbounded invisible queueing (now 503 + `Retry-After` + `queue_depth`); horizontal throughput on cloud (N GPUs → ~N× scoring throughput, config-only); graceful replica failure.

**Still open (tracked separately):**
- **RES-01** — a per-chunk inference *timeout* still abandons a worker thread that keeps running `model.predict()` on the non-thread-safe model. The bounded queue reduces how often timeouts fire under load, but the zombie-overlap corruption path is inside the chunk executors (`text/audio/video_scorer.py`) and needs a model-level lock or a kill-able subprocess worker. Recommend: hold a model-level lock for the true inference duration + a watchdog that flips `/health` to degraded (→ supervised restart) if a worker exceeds a hard ceiling. **Not done here** — it's a scoring-internals change that can't be runtime-verified without a GPU; do it as a focused follow-up with a GPU in the loop.
- One GPU still cannot meet the ≤20-min SLA for 100 concurrent campaigns — that's the physics the multi-GPU cloud path exists for.

## Verification
- `orchestrator/tests/test_clients.py::TestTribeEndpointPool` — 9 tests: single-endpoint derivation, multi-endpoint parse, least-in-flight pick, cooldown skip, routing to least-busy, lease drain, failure cooldown, config parsing.
- Existing 44 TRIBE-client tests pass unchanged (backward compatible).
- `TRIBE_MAX_INFLIGHT` / `_admission` import-verified in the TRIBE py3.11 venv.
