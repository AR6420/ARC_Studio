# Phase 2 Track B Validation Findings

**Date:** 2026-04-13
**Validator:** Claude Code
**Commit:** `9fe6b42` (main, all B.2-B.5 merged)
**Tag:** `phase2-b-complete` — **NOT APPLIED** (Price Increase scenario did not meet pass criteria)

---

## Merge Summary

All four branches merged into main in lowest-risk-first order:

| Order | Branch | Merge | Tests After |
|-------|--------|-------|-------------|
| 1 | `fix/phase2-pytorch-docs` (B.3) | Clean, no conflicts | 205 passed |
| 2 | `fix/phase2-docker-healthchecks` (B.5) | Already on main (agent committed directly) | 205 passed |
| 3 | `fix/phase2-cuda-recovery` (B.2) | Clean, no conflicts | 219 passed (+14 new) |
| 4 | `fix/phase2-neo4j-monitoring` (B.4) | Rebased to drop duplicate B.2 commit, clean merge | 219 passed |

Note: B.4 branch contained a duplicate B.2 commit. Git rebase correctly skipped the already-applied commit before merge.

---

## Validation Results

### Check 1: Unit Tests — PASS

219 tests pass after all merges. 14 new tests from B.2 (test_cuda_recovery.py). Pre-existing `test_tribe_timeout.py` excluded (requires numpy, not in system Python).

### Check 2a: B.2 `cuda_healthy` in TRIBE `/api/health` — PASS

```json
{
  "status": "ok",
  "cuda_healthy": true,
  "gpu_name": "NVIDIA GeForce RTX 5070 Ti Laptop GPU",
  "gpu_memory_used_gb": 2.0,
  "gpu_memory_free_gb": 9.94
}
```

Field present, returns `true` when CUDA is healthy. After the campaign run caused CUDA corruption, the same endpoint correctly returned `cuda_healthy: false` and `status: degraded`.

### Check 2b: B.4 `neo4j` in orchestrator `/api/health` — PASS

```json
{
  "neo4j": {
    "node_count": 1958,
    "relationship_count": 668,
    "heap_max_mb": 2048,
    "warning": null
  }
}
```

Field present throughout the run. Post-campaign: node_count=2014, relationship_count=690 (grew by 56 nodes from the MiroFish simulation).

### Check 3: B.5 Docker Healthchecks — PASS

```
NAME           STATUS
arc-litellm    Up 13 minutes (healthy)
arc-mirofish   Up 13 minutes (healthy)
arc-neo4j      Up 13 minutes (healthy)
```

All three services report healthy. MiroFish's new healthcheck (`curl -sf http://localhost:5001/health`) working correctly with 45s start_period.

### Check 4: B.2 CUDA Stale Recovery Path — DEFERRED

**Rationale:** Cannot safely trigger a stale CUDA context without risking the live GPU session. Forcing `torch.cuda.device_reset()` or similar would corrupt the active TRIBE model.

**Organic validation:** During the Price Increase campaign run, TRIBE's CUDA context degraded. The B.2 health probe correctly detected this:
- `/api/health` returned `cuda_healthy: false`, `status: degraded`
- GPU memory queries returned `null` (CUDA context corrupted)
- This is the exact behavior B.2 was designed to detect

**Deferred to:** Next organic trigger (laptop sleep/wake during a session).

### Check 5: B.4 Neo4j Heap Check Script — PASS

```
=== Neo4j Heap & Graph Status ===
  Nodes:         1958
  Relationships: 668
  Heap:          JMX not available (Community Edition)
  Heap Max:      2048 MB (from docker-compose config)
```

Script runs, queries Neo4j HTTP API, shows node/relationship counts. JMX heap metrics not available in Community Edition (expected). Script handles this gracefully.

### Check 6: Price Increase Scenario — FAIL

**Campaign:** `9b1ad5ed-d694-4c97-921d-618c5f4e318e`
**Duration:** 42.6 minutes (2 iterations)
**Demographic:** enterprise_decision_makers, 20 agents

| Variant | Iteration | TRIBE Score | is_pseudo_score |
|---------|-----------|-------------|-----------------|
| v1_peer | 1 | Real | False |
| v2_roi  | 1 | Pseudo | True |
| v3_risk | 1 | Pseudo | True |
| v1_peer | 2 | None | N/A (TRIBE unavailable) |
| v2_advis | 2 | None | N/A (TRIBE unavailable) |
| v3_board | 2 | None | N/A (TRIBE unavailable) |

**Result:** 2 pseudo-scores + 3 missing scores out of 6 total. Pass criteria was 0/6.

**Root cause:** TRIBE CUDA context degraded during the campaign. After scoring variant 1 of iteration 1 successfully, the CUDA context became unstable. Variants 2-3 fell back to pseudo-scores. By iteration 2, TRIBE was fully unavailable.

Post-campaign TRIBE health:
```json
{"status": "degraded", "cuda_healthy": false, "gpu_memory_used_gb": null}
```

**This is NOT a B.2-B.5 regression.** The same failure pattern exists in the B.1 baseline (`phase2_validation.json`: iter 1 had 1 pseudo, iter 2 had all Nones). The CUDA instability is a pre-existing issue that B.2 now correctly **detects** but cannot yet **prevent**.

**data_completeness:** Not populated in any variant row. This may be a serialization issue in the API response (the field exists in the iteration-level data but is null in the per-variant rows returned by the campaigns endpoint).

---

## B.2-B.5 New Behavior Confirmed

Despite the campaign not meeting the scoring pass criteria, all B.2-B.5 additions functioned correctly:

1. **B.2 CUDA probe:** Correctly detected stale CUDA context post-campaign (cuda_healthy=false, status=degraded)
2. **B.3 PyTorch docs:** `docs/pytorch_upgrade_path.md` exists with complete upgrade plan
3. **B.4 Neo4j monitoring:** Health endpoint showed neo4j metrics throughout the run; node count increased from 1958→2014 after campaign
4. **B.5 Docker healthchecks:** All three services maintained healthy status throughout

---

## Recommendation

The `phase2-b-complete` tag should NOT be applied until the TRIBE CUDA stability issue is resolved. The B.2-B.5 code changes are correct and should remain on main. The blocking issue is TRIBE CUDA context degradation during sustained inference, which is:

1. A pre-existing problem (same pattern in B.1 baseline)
2. Now correctly detected by B.2 (improvement over silent pseudo-score fallback)
3. Likely related to RTX 5070 Ti sm_120 JIT fallback stress under sustained GPU load

**Next steps:**
- Investigate whether the CUDA degradation is caused by VRAM pressure (11.94 GB used of 11.94 GB total during inference)
- Consider reducing TRIBE batch concurrency or adding VRAM pre-checks before each variant
- The `scripts/restart_tribe.sh` from B.2 can be used for manual recovery
- Re-run the Price Increase scenario after TRIBE recovery to confirm the scoring works clean
