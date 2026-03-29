# Phase 5: Orchestrator Integration Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 05-orchestrator-integration-pipeline
**Areas discussed:** Variant-to-simulation flow, Graceful degradation, Campaign data model

---

## Variant-to-Simulation Flow

### Q1: How many content variants per iteration?

| Option | Description | Selected |
|--------|-------------|----------|
| 3 variants (Recommended) | Fast iteration, still enough diversity. Each gets TRIBE-scored and best go to MiroFish. Good for 20-min budget. | ✓ |
| 5 variants | More strategic diversity, but longer TRIBE scoring and more Haiku API calls per iteration. | |
| You decide | Claude picks based on campaign complexity and time budget. | |

**User's choice:** 3 variants (Recommended)
**Notes:** None

### Q2: How many variants go to MiroFish simulation?

| Option | Description | Selected |
|--------|-------------|----------|
| Top 2 by composite score (Recommended) | Cuts MiroFish time by ~33%. The worst variant is dropped early. Fastest path within 20-min budget. | |
| All 3 variants | Every variant gets full simulation data. More complete comparison but ~50% longer MiroFish phase. | ✓ |
| Top 1 only | Only the neural winner gets simulated. Fastest, but no simulation-based comparison between variants. | |

**User's choice:** All 3 variants
**Notes:** User prioritized completeness over speed — all variants get full simulation data.

### Q3: TRIBE scoring parallelism?

| Option | Description | Selected |
|--------|-------------|----------|
| Sequential (Recommended) | One variant at a time through TRIBE. Simpler, avoids GPU contention on the single RTX 5070 Ti. | ✓ |
| Parallel | Batch all 3 to TRIBE simultaneously. Faster if TRIBE's batch endpoint handles it, but risks VRAM pressure. | |
| You decide | Claude picks based on what TRIBE's batch API supports and GPU constraints. | |

**User's choice:** Sequential (Recommended)
**Notes:** None

### Q4: MiroFish simulation parallelism?

| Option | Description | Selected |
|--------|-------------|----------|
| Sequential (Recommended) | One simulation at a time. Neo4j graph gets rebuilt per variant. Simplest, avoids graph DB conflicts. | ✓ |
| Parallel with separate graphs | Run multiple simulations concurrently with isolated Neo4j databases/namespaces. Complex but faster. | |
| You decide | Claude picks based on MiroFish's architecture constraints. | |

**User's choice:** Sequential (Recommended)
**Notes:** None

---

## Graceful Degradation

### Q1: When TRIBE v2 is unavailable?

| Option | Description | Selected |
|--------|-------------|----------|
| Skip TRIBE, run MiroFish only (Recommended) | Generate variants, skip neural scoring, still simulate all 3. Composites needing TRIBE show N/A. | |
| Block the campaign | Refuse to run — tell user TRIBE must be online. No partial results. | (initially selected) |
| Use placeholder scores | Fill TRIBE scores with neutral defaults (50/100). Flag as synthetic. | |

**User's choice:** Initially selected "Block the campaign"
**Notes:** Conflict flagged with requirement ORCH SC-5 which explicitly requires graceful degradation.

### Q2: When MiroFish is unavailable?

| Option | Description | Selected |
|--------|-------------|----------|
| Block the campaign (Recommended) | Same logic — both systems are core to value prop. Refuse to run. | (initially selected) |
| Skip MiroFish, run TRIBE only | Generate variants, score neurally, skip simulation. Missing composites show N/A. | |
| Use placeholder metrics | Fill MiroFish metrics with neutral defaults. Flag as synthetic. | |

**User's choice:** Initially selected "Block the campaign (Recommended)"
**Notes:** Same conflict with ORCH SC-5.

### Q3: Requirement conflict resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Block by default, --force for partial (Recommended) | Default blocks. A --force flag allows partial runs with gap warnings. Satisfies requirement + user preference. | |
| Block always, update the requirement | Hard block — deviates from original success criteria. | |
| Follow the requirement as-is | Graceful degradation with partial data, as originally specified. | ✓ |

**User's choice:** Follow the requirement as-is
**Notes:** User reversed initial preference to align with the original requirement specification.

### Q4: Health detection approach

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-flight health check (Recommended) | Before starting, ping /health on TRIBE and MiroFish. If down, warn upfront. | |
| Fail on first call | Discover unavailability when the actual call fails. Simpler but slower feedback. | |
| You decide | Claude picks. | ✓ |

**User's choice:** You decide
**Notes:** Deferred to Claude's discretion.

---

## Campaign Data Model

### Q1: Persistence granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Full persistence (Recommended) | Store everything: config, variants, raw scores, metrics, composites, analysis, per iteration. | ✓ |
| Summary only | Config, final composites, final analysis. Raw data only for winning variant. | |
| Config + JSON blob | Structured config columns, JSON blob per iteration. Simple but hard to query. | |

**User's choice:** Full persistence (Recommended)
**Notes:** None

### Q2: Schema style for structured scores

| Option | Description | Selected |
|--------|-------------|----------|
| JSON columns (Recommended) | TRIBE scores, MiroFish metrics, composites as JSON text columns. Flexible, queryable via json_extract(). | ✓ |
| Fully normalized columns | Each score dimension gets its own column. Easier to query but rigid schema. | |
| You decide | Claude picks. | |

**User's choice:** JSON columns (Recommended)
**Notes:** None

### Q3: Campaign status tracking

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, with status column (Recommended) | Explicit status field (pending, running, completed, failed). Enables UI badges and resume logic. | ✓ |
| No, infer from data | No explicit status — infer from presence of iterations. Simpler but fragile. | |
| You decide | Claude picks. | |

**User's choice:** Yes, with status column (Recommended)
**Notes:** None

### Q4: API shape for campaign creation

| Option | Description | Selected |
|--------|-------------|----------|
| Single POST with all config (Recommended) | POST /api/campaigns with all config in one call. Creates and optionally starts. | ✓ |
| Create then configure | POST creates blank, PATCH adds config. More flexible but more calls. | |
| You decide | Claude picks. | |

**User's choice:** Single POST with all config (Recommended)
**Notes:** None

---

## Claude's Discretion

- Health check implementation approach (pre-flight vs fail-on-first-call)
- CLI execution interface design (not discussed — CLI area was not selected)

## Deferred Ideas

None — discussion stayed within phase scope.
