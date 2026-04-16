# Phase 2 C.1 — Calibration Framework Design

**Date**: 2026-04-15
**Purpose**: Specify exactly how A.R.C Studio's composite predictions will be compared against real-world campaign outcomes, with enough rigor that a third party could execute the calibration experiments by following this document.
**Scope**: Framework design only. Dataset curation is C.2; experiment execution is C.3.

---

## 1. What We're Calibrating

A.R.C Studio produces 7 composite scores per content variant, each blending neural predictions (TRIBE v2 brain-encoding model) and/or multi-agent social simulation data (MiroFish). Not all 7 have equally strong real-world proxies. The framework calibrates the **4 scores with defensible ground-truth proxies** and documents why the remaining 3 are deferred.

### Scores targeted for calibration

| # | Composite Score | Formula | Input Systems | Hypothesis |
|---|---|---|---|---|
| 1 | **attention_score** | `0.6·attention_capture + 0.4·emotional_resonance` | TRIBE only | Higher attention_score predicts higher observed engagement (dwell time, CTR, completion rate) |
| 2 | **virality_potential** | `(emotional_resonance · social_relevance / max(cognitive_load, 10)) · share_rate_norm / 100` | TRIBE + MiroFish | Higher virality_potential predicts higher observed shareability (share count / reach ratio) |
| 3 | **backlash_risk** | `(threat_detection / max(reward_response + social_relevance, 10)) · counter_narrative_factor · 2` | TRIBE + MiroFish | Higher backlash_risk predicts higher observed negative reception (complaint volume, negative sentiment ratio, PR crisis indicators) |
| 4 | **conversion_potential** | `(reward_response · attention_capture / max(threat_detection, 10)) / 10` | TRIBE only | Higher conversion_potential predicts higher observed action-taking (click-through, signup, purchase) when the conversion action is known and measurable |

### Scores deferred from initial calibration

| # | Composite Score | Reason for deferral |
|---|---|---|
| 5 | **memory_durability** | Formula: `memory_encoding · emotional_resonance · sentiment_stability / 100`. Ground truth requires aided/unaided recall studies (typically expensive, proprietary, not publicly documented for specific campaigns). No reliable free proxy exists. Calibrate in Phase 3 if A.R.C Studio is deployed alongside a longitudinal recall study. |
| 6 | **audience_fit** | Formula: demographic-weighted average of TRIBE dimensions. This score is relative by construction (what "fits" changes per demographic). Calibrating it requires matched pairs: same content scored for different demographics with demographic-specific outcome data. The initial 15-20 campaign dataset won't have this structure. |
| 7 | **polarization_index** | Formula: `coalition_count · platform_divergence · (1 - sentiment_stability) · 20`. MiroFish-only score. Ground truth (political polarization metrics, discourse fragmentation indices) exists in academic literature but mapping MiroFish's simulated coalition counts to real-world partisan clustering requires methodological work beyond calibration. |

### TRIBE v2 neural dimensions (inputs, not directly calibrated)

The 7 TRIBE dimensions are intermediate representations derived from brain-region activation patterns predicted by the LLaMA 3.2-3B brain-encoding model. They map to specific cortical ROIs:

| Dimension | Brain Regions | Score Range |
|---|---|---|
| attention_capture | Visual cortex + FEF + IPS | 0–100 |
| emotional_resonance | Amygdala + anterior insula + ACC | 0–100 |
| memory_encoding | Hippocampus + parahippocampal + entorhinal | 0–100 |
| reward_response | Nucleus accumbens / VTA proxy + OFC | 0–100 |
| threat_detection | Basolateral amygdala proxy + ACC / insula | 0–100 |
| cognitive_load | DLPFC + anterior PFC | 0–100 |
| social_relevance | TPJ + mPFC + pSTS | 0–100 |

We calibrate the composite scores (which combine TRIBE + MiroFish), not individual TRIBE dimensions. The dimensions themselves are validated by TRIBE v2's published fMRI correlation benchmarks (see Meta FAIR's original paper). Our job is to validate that the composites built *on top of* TRIBE track real-world outcomes.

### MiroFish simulation metrics (inputs, not directly calibrated)

| Metric | Type | Description |
|---|---|---|
| organic_shares | int | Count of share/repost/create_post agent actions |
| sentiment_trajectory | list[float] | Per-round average sentiment across agents, range [-1, 1] |
| counter_narrative_count | int | Count of COUNTER_NARRATIVE or OPPOSE agent actions |
| peak_virality_cycle | int | Simulation round with highest sharing activity |
| sentiment_drift | float | Final sentiment minus initial sentiment |
| coalition_formation | int | Count of distinct pro/anti/neutral agent groups |
| influence_concentration | float | Gini coefficient of agent influence, range [0, 1] |
| platform_divergence | float | Absolute difference between Twitter and Reddit sharing proportions |

---

## 2. Ground-Truth Proxies

For each calibrated composite score, the proxy must be (a) publicly observable or reconstructible from documented campaign data, (b) measurable on the same content A.R.C Studio scores, and (c) directionally aligned with the hypothesis stated in Section 1.

### attention_score → Engagement Metrics

| Proxy | Source | Strength |
|---|---|---|
| **Video completion rate** | YouTube Analytics, platform reports, press coverage | Strong — directly measures sustained attention |
| **Average dwell time** | Publisher analytics, press coverage of campaign performance | Strong |
| **Click-through rate (CTR)** | Ad platform reports, campaign case studies | Moderate — conflated with placement and targeting |
| **Social media impression-to-engagement ratio** | Platform analytics, third-party tools (Sprout, Hootsuite reports) | Moderate |

**Primary proxy**: video completion rate or dwell time (when available). **Fallback**: CTR or engagement ratio.
**Threshold for inclusion**: at least ONE engagement metric must be documented with a specific number (not "high engagement" — that's not calibratable).

### virality_potential → Shareability Metrics

| Proxy | Source | Strength |
|---|---|---|
| **Share count / reach ratio** | Platform analytics, press reports, viral marketing case studies | Strong — directly measures organic amplification |
| **Earned media multiplier** | PR measurement reports (content reach beyond paid distribution) | Strong |
| **R₀ analogy: secondary shares / primary shares** | Platform cascade data (rare but ideal) | Very strong (but rarely available) |

**Primary proxy**: documented share volume normalized by initial reach or follower count. Raw share counts are misleading without reach context — a post with 10K shares from a 10M-follower account is less viral than 10K shares from a 10K-follower account.
**Threshold for inclusion**: share count AND either reach/impression count or follower base size must be documented.

### backlash_risk → Negative Reception Metrics

| Proxy | Source | Strength |
|---|---|---|
| **Negative sentiment ratio** | Social listening reports, brand monitoring tools | Moderate — sentiment analysis tools have their own accuracy limitations |
| **Formal complaint/response volume** | Regulatory filings, public apology issuance, press corrections | Strong signal when present (binary: backlash happened or didn't) |
| **Content withdrawal or revision** | Documented cases where content was pulled or revised after launch | Strong (clear behavioral signal from the publisher) |
| **Controversy news coverage volume** | News articles specifically about the backlash | Strong |

**Primary proxy**: binary "backlash event occurred" classification (pulled/revised/apologized) plus negative-sentiment ratio if available. Binary classification is more reliable than continuous sentiment measurement at this sample size.
**Threshold for inclusion**: documented public reception (positive OR negative) with enough specificity to classify. "Mixed reception" with no further detail is not sufficient.

### conversion_potential → Action Metrics

| Proxy | Source | Strength |
|---|---|---|
| **Conversion rate** | Campaign case studies with explicit conversion data | Strong — when the conversion action is defined and measured |
| **Revenue uplift** | Earnings reports, campaign ROI case studies | Strong but confounded (many factors beyond content) |
| **Signup/download count** | App store rankings, documented launch metrics | Moderate |

**Primary proxy**: conversion rate on a defined action (purchase, signup, download). If unavailable, revenue/download change within a defined window post-campaign.
**Threshold for inclusion**: conversion metric must be reported as a NUMBER (rate or count), not a qualitative assessment. "Exceeded targets" is not calibratable.

---

## 3. Campaign Eligibility Criteria

### Required (all must be true)

- [ ] **Original content recoverable**: full text, audio, or video of the campaign piece(s) is accessible — either publicly archived, included in case studies, or available via Wayback Machine / media archives. Summaries and excerpts are NOT sufficient; A.R.C Studio must score the actual content.
- [ ] **Documented outcomes**: at least ONE of the ground-truth proxies from Section 2 is reported as a specific, verifiable number — not "performed well" or "went viral."
- [ ] **Stable demographic targeting**: the target audience is identifiable and mappable to one of A.R.C Studio's 6 demographic presets (or a reasonable custom profile). Campaigns targeting "everyone" are acceptable but weaker.
- [ ] **Single-content-piece attribution**: the documented outcome can be attributed primarily to a specific piece of content, not to an entire multi-month campaign where the content's individual contribution is unclear.

### Desirable (strengthen the calibration value)

- [ ] Controversy or pivot point: the campaign had a clear moment where reception shifted (backlash, viral breakout, or strategy reversal) — these are the most informative data points.
- [ ] Multi-platform distribution: the same content appeared across 2+ platforms with separately documented outcomes, enabling within-campaign comparisons.
- [ ] Diverse demographics: the target audience is distinct from other entries in the dataset (avoid 15 campaigns all targeting US general consumers).
- [ ] Temporal proximity: campaigns from 2020–2026 preferred (media landscape relevance); pre-2015 campaigns excluded unless exceptionally well-documented.

### Disqualifying (any one excludes the campaign)

- [ ] **Outcomes only in aggregate**: the campaign is part of a larger initiative and no outcome data is attributable to the specific content piece.
- [ ] **Content only partially recoverable**: only headlines, summaries, or heavily edited versions survive — the actual text/audio/video is lost.
- [ ] **Confounded by non-content factors**: documented outcomes are primarily attributable to paid amplification budgets, celebrity endorsement, platform algorithm changes, or unrelated simultaneous events (e.g., a product launch that coincided with a competitor's scandal).
- [ ] **Outcomes fabricated or disputed**: the metrics are from the campaign creator's unverified claims with no third-party corroboration.

---

## 4. Proposed Dataset Composition

### Target distribution by type

| Category | Target count | Rationale |
|---|---|---|
| Product launches (tech/consumer/enterprise) | 4–5 | Core use case; engagement + conversion data often public |
| Policy announcements / government comms | 2–3 | Tests threat_detection/backlash pathways; high-stakes outcomes |
| Public health PSAs | 2–3 | Tests emotional_resonance/memory pathways; documented reach data |
| Viral successes (organic) | 2–3 | Ground truth for virality_potential is directly available |
| Documented backlash cases | 2–3 | Ground truth for backlash_risk is directly available |
| Documented flops (underperformance) | 1–2 | Prevents survivorship bias — we need campaigns that DIDN'T work |
| Political/advocacy messaging | 1–2 | Tests polarization_index (even though deferred, capture the data) |
| **Total** | **15–20** | |

### Target distribution by modality

| Modality | Target count | Rationale |
|---|---|---|
| Text (article, press release, statement) | 10–14 | Primary modality; real TRIBE scores on laptop hardware |
| Audio (podcast clip, radio spot, speech excerpt) | 3–5 | Real TRIBE scores on laptop hardware (validated in A.1) |
| Video (ad, announcement video) | 1–2 | Aspirational — pseudo-scores on laptop, real on cloud (validated in A.2) |

### Minimum viable set

For initial calibration signal: **5 campaigns** spanning at least 3 categories and 2 modalities. This is enough for directional Spearman correlation (p < 0.05 requires r > 0.9 at n=5, so only very strong effects will be detectable). The 5-campaign set is a smoke test, not a defensible claim.

For defensible claims: **15–20 campaigns**. At n=20, Spearman r > 0.45 is significant at p < 0.05. This allows moderate correlations to be detected.

---

## 5. Comparison Methodology

### Score mapping

A.R.C Studio composite scores are continuous on [0, 100]. Real-world proxies have wildly different scales (share counts in thousands vs sentiment ratios in [0, 1] vs binary backlash yes/no). Three approaches, used per-score:

| Proxy type | Mapping | Example |
|---|---|---|
| **Continuous metric** (CTR, share ratio) | Rank both predicted and observed; compute Spearman ρ | attention_score vs completion rate |
| **Binary event** (backlash occurred yes/no) | ROC-AUC on the predicted score as a classifier | backlash_risk as a predictor of whether backlash occurred |
| **Count metric** (shares, complaints) | Log-transform the count, then Spearman ρ on ranks | virality_potential vs log(shares/reach) |

### Primary statistical measure

**Spearman rank correlation (ρ)** for all continuous-proxy scores. Rationale:
- We care about ranking (does higher predicted score correspond to higher observed outcome?), not absolute calibration (does a score of 75 mean exactly 75% engagement).
- Spearman is robust to non-linear monotonic relationships, which is what we expect (the relationship between neural activation patterns and share counts is unlikely to be linear).
- Small sample sizes (15–20) make parametric assumptions unreliable; rank-based methods are more robust.

**ROC-AUC** for binary-proxy scores (backlash_risk). Rationale:
- Backlash is fundamentally binary at our sample size (it either happened or it didn't; the degree of backlash is too noisy to rank with <20 data points).
- AUC > 0.5 indicates the score discriminates above chance; AUC > 0.75 is operationally useful.

### Bootstrap confidence intervals

- **Resampling**: 10,000 bootstrap iterations per metric (sample with replacement from the N campaigns, recompute ρ or AUC each time).
- **Interval**: 95% bias-corrected accelerated (BCa) confidence interval. Report [lower, upper] alongside the point estimate.
- **Per-demographic vs pooled**: compute BOTH pooled (all campaigns) and per-demographic (when subgroup has ≥ 5 entries). Per-demographic results are exploratory, not confirmatory, at this sample size.

### Multiple comparisons

We are computing 4 primary correlations (one per calibrated score). Apply Holm-Bonferroni correction to maintain family-wise error rate < 0.05. Report both corrected and uncorrected p-values — the correction is conservative at 4 tests and the reader should see both.

---

## 6. Interpretation Thresholds

### Correlation strength (Spearman ρ)

| ρ Range | Label | Interpretation for A.R.C Studio |
|---|---|---|
| **> 0.70** | Strong | Score reliably tracks real-world outcome rank order. Operationally useful for comparative content evaluation. |
| **0.40–0.70** | Moderate | Score captures meaningful signal but substantial noise. Useful for directional guidance, not precise prediction. |
| **0.20–0.40** | Weak | Some signal exists but the score is more wrong than right in head-to-head comparisons. Interpret with caution. |
| **< 0.20** | None | No detectable relationship at this sample size. Score may still have value that a larger dataset would reveal, or may be measuring something that doesn't map to this proxy. |

### Binary classification (ROC-AUC for backlash_risk)

| AUC Range | Label | Interpretation |
|---|---|---|
| **> 0.85** | Excellent | Score reliably flags high-backlash content before launch. |
| **0.75–0.85** | Good | Operationally useful as a screening signal. |
| **0.60–0.75** | Marginal | Better than chance but not reliable for high-stakes decisions. |
| **< 0.60** | Poor | Not distinguishable from random at this sample size. |

### Realistic expectations per score

| Score | Expected strength | Rationale |
|---|---|---|
| attention_score | Moderate to strong (ρ 0.4–0.7) | Direct neural basis (visual cortex + amygdala → engagement); the relationship attention → engagement is one of the best-established in cognitive neuroscience. |
| virality_potential | Moderate (ρ 0.3–0.6) | Virality is inherently noisy (depends on timing, platform, network topology). The score captures content-quality signal but not contextual factors. |
| backlash_risk | Moderate AUC (0.65–0.80) | Threat detection is a strong neural predictor of negative affect, but real-world backlash also depends on political context, brand history, and timing — none of which the score captures. |
| conversion_potential | Weak to moderate (ρ 0.2–0.5) | Conversion is heavily influenced by non-content factors (price, UX, competitive landscape). The score captures the content's motivational properties but not the funnel it sits in. |

---

## 7. Failure Modes and Limitations

### Sample size constraints

At N=15–20, statistical power is limited. A true moderate correlation (ρ=0.5) has only ~60% power to be detected as significant at p<0.05 with N=15. This means:
- Negative results (non-significant correlations) do NOT prove the score is useless — they may reflect insufficient power.
- Positive results (significant correlations) at small N should be interpreted as promising signals, not definitive evidence.
- Pre-register the analysis plan (this document serves as the pre-registration) so that p-hacking is not possible.

### Survivorship bias

Publicly documented campaigns skew toward the notable: viral successes, PR disasters, major product launches. Routine campaigns with middling performance are underrepresented because nobody writes case studies about them. This inflates the variance of observed outcomes, potentially making correlations appear stronger than they would be in a representative sample.

**Mitigation**: explicitly target 1–2 "documented flops" and 2–3 middling campaigns. Acknowledge the bias in reporting.

### Retrospective prediction ≠ prospective prediction

A.R.C Studio is scoring content today that was originally published months or years ago. The system cannot account for the temporal context in which the content appeared (news cycle, competitive landscape, platform algorithm state at launch time).

**Mitigation**: record the temporal gap for each entry; test whether the gap correlates with prediction error. If it does, report it.

### Content-outcome coupling

The observed outcome happened in a specific context: the content was distributed by a specific organization, to a specific audience, via specific channels, at a specific moment. A.R.C Studio scores the *content* in isolation. The calibration measures whether content quality (as scored) correlates with observed outcomes — NOT whether A.R.C Studio can predict outcomes independent of distribution context.

**Explicit framing**: calibration results measure "content quality signal," not "outcome prediction."

### Claude Opus analysis is qualitative

The cross-system analysis (step 5 in the pipeline) uses Claude Opus to explain *why* neural patterns led to social outcomes. This analysis is not calibratable in the statistical sense — it generates plausible narratives, not testable predictions. Calibration covers the composite scores (quantitative), not the narrative analysis (qualitative).

---

## 8. What Calibration Will and Won't Claim

### Will claim (if evidence supports it)

- "The attention_score correlates with observed engagement metrics at ρ=X [95% CI: Y–Z] across N campaigns."
- "Campaigns with backlash_risk > T were M times more likely to experience documented backlash (AUC=A)."
- "The rank ordering produced by virality_potential matches the rank ordering of observed share rates at ρ=X."
- Calibration results with specific numbers, confidence intervals, and sample sizes.

### Will NOT claim

- "A.R.C Studio accurately predicts real-world campaign outcomes." (Too strong — we predict content quality signal, not outcomes.)
- "A composite score of 75 means 75% engagement." (Scores are ordinal, not calibrated to absolute values.)
- "These results generalize to all content types and demographics." (Sample is small and non-representative.)
- "The absence of correlation proves the score is broken." (Power too low for confirmatory null results.)

### Framing

Calibration is an ongoing process, not a one-time certification. The initial C.2/C.3 round establishes a baseline. Each subsequent real-world deployment that generates measurable outcomes contributes to the calibration corpus. The framework is designed to accumulate evidence over time, not to pass/fail on a single run.

---

## 9. Next Steps: Handoff to C.2

### C.2 deliverable

A curated dataset of 15–20 historical campaigns, each conforming to the entry schema below and the eligibility criteria from Section 3. Each entry must include:
1. The actual content (text, audio file, or video file) — not a summary.
2. At least one quantified outcome metric mappable to a ground-truth proxy from Section 2.
3. Source citations for both the content and the outcome data.
4. A brief justification for why this campaign is informative (what signal does it test?).

### Entry schema (YAML)

```yaml
# calibration_dataset/entries/<slug>.yaml
id: <unique-slug>  # e.g., "apple-vision-pro-launch-2024"
metadata:
  title: <campaign/content title>
  organization: <brand, agency, or publisher>
  date_published: <YYYY-MM-DD>
  category: <product_launch | policy | public_health | viral_success | backlash | flop | political>
  demographic_target: <one of: tech_professionals | enterprise_decision_makers | general_consumer_us | policy_aware_public | healthcare_professionals | gen_z_digital_natives | custom:description>
  modality: <text | audio | video>
  platforms: [<list of distribution platforms>]

content:
  # Exactly one of:
  text: |
    <full verbatim text of the content piece>
  audio_path: <relative path to audio file in calibration_dataset/media/>
  video_path: <relative path to video file in calibration_dataset/media/>
  # If the content is very long, include the first 5000 words and note truncation.
  truncated: false
  content_source_url: <URL where the original content can be verified>

outcomes:
  # At minimum ONE of these with a numeric value and a source citation.
  engagement:
    metric_name: <completion_rate | dwell_time_seconds | ctr | engagement_ratio>
    value: <numeric>
    denominator: <what the value is relative to, e.g., "impressions", "viewers">
    source: <URL or citation>
  shareability:
    share_count: <numeric>
    reach_or_followers: <numeric — for normalization>
    platform: <platform where sharing was measured>
    source: <URL or citation>
  backlash:
    occurred: <true | false>
    severity: <none | minor_criticism | content_revised | content_pulled | public_apology | regulatory_action>
    negative_sentiment_ratio: <float, optional>
    source: <URL or citation>
  conversion:
    metric_name: <conversion_rate | signup_count | download_count | revenue_change>
    value: <numeric>
    attribution_window: <e.g., "7 days post-launch">
    source: <URL or citation>

calibration_notes:
  justification: <why this campaign is informative — what signal does it test?>
  confounders: <known non-content factors that may have influenced the outcome>
  confidence: <high | medium | low — how trustworthy is the outcome data?>
```

### Directory structure for C.2

```
calibration_dataset/
  entries/
    apple-vision-pro-launch-2024.yaml
    tide-pod-challenge-backlash-2018.yaml
    ...
  media/
    apple-vision-pro-keynote-clip.mp3
    ...
  README.md  (dataset overview + summary statistics)
```

### Acceptance criteria for C.2

- [ ] ≥ 15 entries conforming to the schema above.
- [ ] Every entry passes the "Required" eligibility criteria from Section 3.
- [ ] At least 3 categories represented.
- [ ] At least 2 modalities represented.
- [ ] At least 1 entry per calibrated composite score has a strong ground-truth proxy.
- [ ] At least 2 entries in the "backlash" or "flop" categories (prevents survivorship bias).
- [ ] All content source URLs are verified accessible or archived.
- [ ] All outcome source citations are verifiable.
