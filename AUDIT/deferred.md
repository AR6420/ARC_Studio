# Deferred findings — with justification

Items not fixed this phase. Each has a reason. None are CRITICAL/HIGH scale blockers on the contained-fix path; the structural ones live in `architecture-proposals.md`.

## Deferred to architecture proposals (structural — need approval)
- M-06 / CON-03 / PERF-01 / OBS-07 / RES-01 — TRIBE GPU serialization & queue → **P-1**
- M-07 / DATA-01 — campaign heartbeat/resume → **P-2**
- M-31 / OBS-05 / CON-04 / ERR-15 — MiroFish WSGI → **P-3**
- M-33 / CON-01 / CON-02 / CON-08 / DATA-02 / RES-02 / RES-03 / RES-10 — MiroFish execution model, locking, orphan reconciliation → **P-4**
- M-32 / PERF-05 / PERF-06 — MiroFish Neo4j/embedding batching → **P-5**
- SEC-05 / API-02 — auth/tenancy → **P-6**

## Deferred MEDIUM/LOW (contained but out of this phase's risk/scope budget)
| ID | Why deferred |
|---|---|
| ERR-10 circuit breaker | Real, but the admission cap (M-14) + health check already bound the blast radius; a cross-campaign breaker is a new shared-state subsystem better designed alongside P-1's queue. |
| ERR-11 / ERR-13 / ERR-14 mirofish retry gaps | Submodule; the correct fix routes 3 generators through the existing `utils/retry.py` — an upstream-facing refactor, coordinate with P-3/P-4. |
| DATA-05 / DATA-07 transactionality | DATA-07 (orchestrator per-iteration atomicity) is real but low-frequency; safe to pair with P-2's resume work. DATA-05 is submodule. |
| DATA-09 JSONL tail partial-line | Submodule; low per-occurrence impact; pairs with P-4. |
| DATA-10 / DATA-11 / DATA-12 | Submodule Neo4j/sqlite consistency; pair with P-4/P-5. |
| CON-10 / CON-11 / CON-12 / CON-13 | Submodule concurrency niceties (CON-13 CUDA probe outside lock is ours — low probability given allocator's own locking; folded into P-1's inference-lock rework). |
| RES-04 sqlite finally | **Being fixed** in Batch E (M-38) — low-risk additive. |
| RES-05 claude client refresh leak | Low frequency (token rotation); `aclose()` on old client is a nice-to-have; opportunistic. |
| RES-07 / RES-08 IPC/dir cleanup, RES-11 ephemeral httpx, RES-12 exca cache | Disk/conn hygiene; no correctness impact; pair with P-4. |
| PERF-07 / PERF-08 / PERF-09 | PERF-08 (container resource limits) + PERF-09 (httpx Limits) are compose/config tuning to set at deploy; PERF-07 is subsumed by P-3/P-4 state externalization. |
| LOG-08 virality saturation | Real discriminative-power loss; needs a normalization redesign (`agent_count*max_rounds`) validated against real sim output — do with data, not blind. |
| OBS-06 / OBS-08 mirofish logging volume | Submodule logging; pair with P-3. |
| OBS-10 / OBS-11 / OBS-13 / OBS-14 | Deploy/observability tuning (Neo4j thresholds, health URL, vLLM tuning, TRIBE supervisor) — set at deploy time. |
| SEC-09 stack-trace leak | Submodule, 53 sites; endemic pattern — a single error-handler wrapper is the right fix, pair with P-3/P-4. |
| SEC-10 wildcard CORS (mirofish) | Submodule; today bound by `127.0.0.1` compose binding; fix with P-3. |
| SEC-11 / SEC-12 / SEC-15 | Weak Neo4j default / latent SSRF / .env chmod — bind them into the P-6 hardening pass; compose already forces the Neo4j password. |
| SEC-14 | Accepted risk (ROCm requirement). No action. |
| API-01 agent-chat broken | Functional gap, not a scale blocker; needs `/interview` wiring + `simulation_id` plumbing (touches schema + submodule). |
| API-05 / API-09 / API-10 / API-13 | Pagination/poll-status contract gaps; API-05 truncation-to-100 is worth a follow-up (data-quality), the rest are latency/robustness. |
| API-14 / API-15 / OBS-15 / LOG-09 | LOW hygiene; opportunistic. |

## Note
`ui/` ESLint errors (9, incl. 3× `set-state-in-effect`) are pre-existing and out of the correctness/scale scope of this backend audit; logged for a UI pass.
