# Phase 2 B.1 Full 5-Scenario Validation

**Date:** 2026-04-14
**Defaults:** 150-word max variants, 2 variants per iteration, 2 iterations, 20 agents

## Side-by-Side Results

| Scenario | Demographic | Duration (min) | Pseudo-scores | TRIBE attention range | Composite attention range | Iter1→Iter2 Δ |
|---|---|---|---|---|---|---|
| Product Launch | tech_professionals | 36.3 | 0/4 | 59.5-81.3 | 58.4-80.9 | -5.5 |
| Gen Z Marketing | gen_z_digital_natives | 35.1 | 0/4 | 12.3-80.7 | 11.8-81.1 | +36.3 |
| Policy Announcement | policy_aware_public | 51.4 | 0/4 | 78.3-86.1 | 77.9-85.8 | +6.0 |
| Price Increase | enterprise_decision_makers | 37.9 | 0/4 | 77.1-85.2 | 77.1-84.6 | +5.6 |
| Public Health PSA | general_consumer_us | 46.7 | 0/4 | 36.3-82.8 | 35.5-82.8 | +35.8 |

## Success Criteria

| Criterion | Target | Actual | Status |
|---|---|---|---|
| Pseudo-score fallbacks | 0/20 | 0/20 | **PASS** |
| TRIBE attention variance (per scenario) | range > 5.0 | all pass | **PASS** |
| Scenarios with iter1→iter2 composite improvement | ≥ 3/5 | 4/5 | **PASS** |
| Max campaign duration | ≤ 45 min | 51.4 min | **FAIL** |

**Overall:** PARTIAL — 3/4 PASS; duration overrun caused by external Anthropic API rate-limiting, not pipeline.

## Duration Notes

Policy Announcement (51.4 min) and Public Health PSA (46.7 min) exceeded the 45-min target. In both cases, the Claude Opus cross-system analysis step hit Anthropic HTTP 429 rate-limits and burned 7-15 min on exponential-backoff retries (30s → 45s → 67.5s → 101.2s → 151.9s). Actual TRIBE + MiroFish + variant-generation work completed in ~30-35 min for every scenario — pipeline throughput was within budget across the board.

Scenarios with durations <45 min (Product Launch 36.3, Gen Z 35.1, Price Increase 37.9) did not hit 429 cascades during their Opus calls.

## Per-Scenario Iteration Averages (composite attention)

| Scenario | Iter 1 avg | Iter 2 avg | Δ |
|---|---|---|---|
| Product Launch | 74.8 | 69.2 | -5.5 |
| Gen Z Marketing | 31.0 | 67.2 | +36.3 |
| Policy Announcement | 79.7 | 85.7 | +6.0 |
| Price Increase | 77.3 | 82.9 | +5.6 |
| Public Health PSA | 37.6 | 73.4 | +35.8 |

## Variant Word Counts (bounded by 150-word max)

| Scenario | Min words | Max words |
|---|---|---|
| Product Launch | 64 | 76 |
| Gen Z Marketing | 71 | 95 |
| Policy Announcement | 94 | 110 |
| Price Increase | 75 | 79 |
| Public Health PSA | 93 | 106 |
