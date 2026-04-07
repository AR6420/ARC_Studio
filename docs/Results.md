# Results.md — Objectives, expected outputs, and success criteria

## Project: A.R.C Studio (Phase 1 POC)
## Stack: Claude Opus + MiroFish-Offline + TRIBE v2
## Scope: Non-commercial, single-user, private repo

---

## 1. Core objectives

### Primary objective
Demonstrate that combining neural response prediction (TRIBE v2) with multi-agent social simulation (MiroFish) and LLM-driven iterative optimization (Claude Opus) produces measurably better content than single-pass generation.

### Secondary objectives
- Prove that the three-system feedback loop converges: each iteration produces higher composite scores than the previous one.
- Demonstrate that TRIBE v2 neural scores correlate meaningfully with MiroFish social propagation outcomes (the cognitive-social bridge hypothesis).
- Show that the system generates actionable insights a human couldn't produce manually — specifically, cross-system reasoning that explains WHY certain neural patterns lead to specific social outcomes.
- Produce a working demo that can be shown to potential stakeholders, collaborators, or investors in under 10 minutes.

---

## 2. User inputs — what goes IN

### 2.1 Required inputs

#### Seed content
- **What:** The content being tested — a product launch announcement, policy draft, ad campaign concept, PSA, press release, or any text-based communication intended for a human audience.
- **Format:** Free-text input (textarea) OR file upload (PDF, .md, .txt, .docx).
- **Length:** 100 to 5,000 words. System should warn if content is too short for meaningful analysis or too long for efficient processing.
- **Examples:** "We're launching NexaVault, a privacy-first cloud storage product with zero-knowledge encryption and collaborative editing, targeting enterprise teams at Series B+ startups."

#### Prediction question
- **What:** The specific question the user wants answered about how the content will be received.
- **Format:** Free-text input.
- **Examples:**
  - "How will enterprise CTOs react to this announcement?"
  - "Will this PSA drive vaccine uptake or create backlash?"
  - "Which framing generates the least polarization?"
  - "How should we announce this price increase to minimize churn?"

#### Target demographic
- **What:** The intended audience for the content.
- **Format:** Selection from preset options OR free-text description.
- **Preset options (Phase 1):**
  1. **Tech professionals** — developers, CTOs, IT leaders. Skeptical of marketing, responsive to technical substance.
  2. **Enterprise decision-makers** — C-suite, VPs, directors. Time-constrained, ROI-focused, risk-averse.
  3. **General consumer (US, 25-45)** — Broadest default. Mixed media literacy, moderate social sharing behavior.
  4. **Policy-aware public** — Voters, civically engaged adults. Responsive to fairness framing, sensitive to partisan signals.
  5. **Healthcare professionals** — Doctors, nurses, public health workers. Evidence-driven, authority-sensitive.
  6. **Gen Z digital natives (18-27)** — High social media engagement, authenticity-sensitive, meme-literate.
- **Custom option:** Free-text field where user describes their audience in natural language. Example: "Mid-career finance professionals in Southeast Asia who are wary of crypto but interested in digital payments."
- **How it's used:** Claude Opus translates the demographic selection into (a) MiroFish agent persona configurations (education, profession, media habits, opinion distributions, influence levels) and (b) TRIBE v2 interpretation weights (cognitive load tolerance, emotional sensitivity, social sharing propensity).

### 2.2 Configuration inputs

#### Agent count
- **Widget:** Slider, range 20-200, step 10, default 40.
- **Guidance text:** "More agents = richer simulation, slower execution. 40 is recommended for most campaigns."

#### Maximum optimization iterations
- **Widget:** Slider, range 1-10, step 1, default 4.
- **Guidance text:** "Each iteration generates improved variants based on previous results. 3-5 iterations is typical."

#### Threshold targets (optional)
- **What:** User sets minimum scores they want to achieve. The system runs iterations until ALL thresholds are met or max iterations is reached.
- **Widget:** For each composite score, a toggle (enabled/disabled) + numeric input (0-100):
  - Attention score: [toggle] [input, default 70]
  - Virality potential: [toggle] [input, default 60]
  - Backlash risk (inverted — user sets MAXIMUM): [toggle] [input, default 25]
  - Memory durability: [toggle] [input, default 60]
  - Conversion potential: [toggle] [input, default 55]
  - Polarization index (maximum): [toggle] [input, default 30]
- **Behavior:** If thresholds are met before max iterations, system stops early and reports success. If not met after max iterations, system outputs the best-performing variant with a note indicating which thresholds were not achieved.

#### Time estimate display
- **What:** Before the user clicks "Run optimization," the system displays an estimated time based on their configuration.
- **Formula:** `estimated_minutes = (agent_count / 40) * max_iterations * 3` (baseline: 40 agents, 1 iteration ≈ 3 minutes).
- **Display:** "Estimated time: ~12 minutes" shown next to the Run button.
- **Caveat text:** "Actual time depends on LLM response speed and simulation complexity."

### 2.3 Optional inputs

#### Existing variants
- **What:** If the user already has 2-5 content versions they want to compare (instead of having Opus generate variants).
- **Format:** Multiple text inputs or file uploads, each labeled "Variant 1," "Variant 2," etc.
- **Behavior:** When provided, Opus skips variant generation in iteration 1 and directly scores/simulates the user's variants. Subsequent iterations still generate new variants based on analysis.

#### Constraints / brand guidelines
- **What:** Rules that Opus must follow when generating variants.
- **Format:** Free-text input.
- **Examples:** "Never use fear-based messaging," "Must include the tagline 'Built for teams,'" "Tone: warm and conversational, not corporate."

#### Comparison baseline
- **What:** A competitor's content or a previous version of the user's own content, used as a reference point.
- **Format:** Text input or file upload.
- **Behavior:** System scores the baseline alongside the generated variants, enabling relative comparison ("Your best variant scored 34% higher on virality potential than the baseline").

---

## 3. Expected outputs — what comes OUT

### 3.1 Output layers

The system produces four layers of output for every campaign run. All four are generated every time; the UI reveals them progressively.

#### Layer 1: The verdict (for everyone)
- **Audience:** Anyone. No technical knowledge required.
- **Format:** 2-4 paragraphs of plain English written by Claude Opus.
- **Content:** Which variant won and why, in everyday language. What the user should do. What to avoid. Any surprising findings.
- **Example:** "Version A is your strongest option. It grabs attention without triggering defensiveness, and people in your target audience are likely to share it with colleagues. The phrase 'zero-knowledge encryption' resonated strongly with technical audiences but confused non-technical decision-makers — consider using 'private by design' for executive-facing channels. Avoid Version C entirely: while it's attention-grabbing, it caused significant pushback in simulation, with people actively arguing against it rather than sharing it."
- **Quality standard:** A non-technical person should be able to read this and make a decision without looking at any other output.

#### Layer 2: The scorecard (for marketing managers and strategists)
- **Audience:** Content strategists, marketing managers, campaign leads.
- **Format:** Visual dashboard with composite scores, variant ranking, and comparison bars.
- **Content:**
  - Composite scores per variant (0-100, color-coded green/amber/red)
  - Variant ranking table with score breakdowns
  - Iteration improvement trajectory (line chart showing scores across iterations)
  - Threshold achievement status (which targets were met, which weren't)
  - Demographic fit indicator
- **Quality standard:** A marketing manager should be able to compare variants at a glance and justify their choice to leadership using these numbers.

#### Layer 3: The deep analysis (for analysts and researchers)
- **Audience:** Data analysts, research teams, power users.
- **Format:** Expandable/collapsible sections within the Report tab.
- **Content:**
  - Full TRIBE v2 neural score breakdown (all 7 dimensions per variant)
  - Full MiroFish simulation metrics (all 8 metrics per variant)
  - Claude Opus reasoning chain (step-by-step logic explaining each decision)
  - Iteration changelog (what changed between each iteration and why)
  - Raw data export option (JSON download of all scores and metrics)
- **Quality standard:** An analyst should be able to reconstruct exactly how the system arrived at its conclusions.

#### Layer 4: Mass psychology view
- **Audience:** Two sub-audiences with a toggle switch.
- **Toggle: General mode**
  - Written for educated non-specialists.
  - Narrative explanation of crowd dynamics: how opinion formed, shifted, and stabilized.
  - Visual timeline showing sentiment waves, opinion cluster formation, narrative mutation.
  - Key moments identified: "The tipping point occurred at cycle 14 when early-adopter agents began sharing, creating a trust cascade that shifted the moderate majority."
  - Accessible language. No jargon. Any literate adult can understand this.
- **Toggle: Pure technical mode (for psychologists)**
  - Same data, reframed in social psychology terminology.
  - References established theories: Granovetter's threshold model, Noelle-Neumann's spiral of silence, Cialdini's influence principles, emotional contagion theory, Overton window dynamics.
  - Includes: social proof cascade rates, in-group/out-group formation indices, cognitive dissonance resolution patterns, herd behavior coefficients, opinion leader influence network graphs, threshold activation curves.
  - Quality standard: A behavioral scientist should be able to use this output in a research context or presentation.

### 3.2 Full parameter set

#### TRIBE v2 neural scores (per variant, 0-100 normalized)

| Parameter | Brain region(s) | What it measures | Content relevance |
|-----------|----------------|------------------|-------------------|
| Attention capture | Visual cortex (V1-V4), FEF | Does the content grab attention? | First impression, scroll-stopping power |
| Emotional resonance | Amygdala, insula, ACC | Does it trigger emotion? | Memorability, sharing motivation |
| Memory encoding | Hippocampus, MTL | Will people remember it? | Brand recall, message retention |
| Reward response | Ventral striatum, OFC | Does it feel rewarding? | Engagement, repeat exposure desire |
| Threat detection | Amygdala (fear circuit) | Does it trigger defensiveness? | Backlash risk, avoidance behavior |
| Cognitive load | Prefrontal cortex, DLPFC | Is it too complex? | Comprehension, accessibility |
| Social relevance | TPJ, mPFC, STS | Does it activate social processing? | Shareability, discussion potential |

#### MiroFish simulation metrics (per variant)

| Parameter | What it measures | Type |
|-----------|------------------|------|
| Organic share count | How many agents voluntarily shared the content | Integer |
| Sentiment trajectory | How sentiment shifted over simulation timeline | Time series (array of floats per cycle) |
| Counter-narrative count | How many distinct opposing narratives emerged | Integer |
| Peak virality cycle | When sharing peaked | Integer (cycle number) |
| Sentiment drift | Net change in population sentiment start → end | Float (-100 to +100) |
| Coalition formation | Did distinct pro/anti groups form? Size and stability | Object: { groups: [{name, size, stability}] } |
| Influence concentration | Were outcomes driven by few agents or distributed? | Float (0 = distributed, 100 = concentrated) |
| Platform divergence | Did Twitter-like and Reddit-like produce different outcomes? | Float (0 = identical, 100 = completely divergent) |

#### Composite scores (displayed prominently, 0-100)

| Score | Formula | Interpretation |
|-------|---------|---------------|
| Attention score | `0.6 * attention_capture + 0.4 * emotional_resonance` | Will people notice this? |
| Virality potential | `(emotional_resonance * social_relevance) / max(cognitive_load, 10) * mirofish_share_rate_normalized` | Will people share this? |
| Backlash risk | `threat_detection / max(reward_response + social_relevance, 10) * mirofish_counter_narrative_factor` | Will this blow up negatively? |
| Memory durability | `memory_encoding * emotional_resonance * mirofish_sentiment_stability` | Will people remember this next week? |
| Conversion potential | `reward_response * attention_capture / max(threat_detection, 10)` | Will people take the desired action? |
| Audience fit | `demographic_weight_adjusted_composite` | How well does this match the target audience? |
| Polarization index | `mirofish_coalition_count * mirofish_platform_divergence * (1 - sentiment_stability)` | Does this unify or divide the audience? |

---

## 4. Quality standards — minimum bar for success

### 4.1 System-level standards

- **End-to-end pipeline:** The system must complete a full campaign run (brief → variant generation → neural scoring → simulation → analysis → report) without manual intervention.
- **Iteration improvement:** Across a campaign run with 4 iterations, the top variant's composite score in iteration N+1 must be higher than iteration N in at least 3 out of 4 iterations. Random or flat performance fails this test.
- **Cross-system insight:** Claude Opus's analysis must reference BOTH TRIBE v2 neural scores AND MiroFish simulation metrics in its reasoning chain. An analysis that ignores one system's output fails this test.
- **Reproducibility:** Running the same campaign brief twice should produce qualitatively similar results (same winning strategy, similar score ranges). Exact numerical match is not required due to LLM stochasticity.

### 4.2 Output quality standards

- **Verdict (Layer 1):** Must be understandable by a non-technical adult. No jargon. Must contain a clear recommendation. Must be 100-400 words.
- **Scorecard (Layer 2):** All composite scores must be 0-100 integers. Color coding must be consistent (green ≥ 70, amber 40-69, red < 40, inverted for backlash risk and polarization index). Variant ranking must be unambiguous.
- **Deep analysis (Layer 3):** Must contain all 7 neural scores and all 8 simulation metrics for every variant. Reasoning chain must have at least 3 logical steps. JSON export must be valid JSON.
- **Mass psychology (Layer 4, General):** Must be narrative prose, not bullet points. Must reference specific simulation cycles. Must be 200-600 words.
- **Mass psychology (Layer 4, Technical):** Must reference at least 2 named psychological theories or models. Must include quantitative metrics alongside theoretical framing.

### 4.3 Performance standards

- **Time per iteration:** ≤ 5 minutes for 40 agents, 30 simulation cycles. (TRIBE v2 inference + MiroFish simulation + Opus analysis combined.)
- **Full campaign run (4 iterations):** ≤ 20 minutes for default configuration (40 agents, 4 iterations).
- **Time estimate accuracy:** Displayed estimate should be within ±30% of actual execution time.
- **Error recovery:** If any single component fails (TRIBE v2 inference error, MiroFish simulation crash, API timeout), the system should retry once, then gracefully degrade (skip that component's scores, note the gap in the report) rather than crashing the entire pipeline.

---

## 5. Demo scenarios — pre-defined test campaigns

These 5 scenarios will be used to validate the POC. Each represents a different use case and audience type.

### Scenario 1: Product launch (tech audience)
- **Seed:** "Announcing NexaVault: enterprise cloud storage with zero-knowledge encryption and real-time collaborative editing. Your data never leaves your control."
- **Question:** "How will CTOs and engineering leaders react to this launch announcement?"
- **Demographic:** Tech professionals
- **Expected insight:** The system should identify tension between security messaging (which activates trust) and collaboration messaging (which activates different neural pathways). Should recommend optimal balance.

### Scenario 2: Public health PSA (general population)
- **Seed:** Draft PSA about a new respiratory virus vaccine, emphasizing safety data from clinical trials and community protection benefits.
- **Question:** "Will this PSA drive vaccine uptake or create anti-vaccine backlash?"
- **Demographic:** General consumer (US, 25-45)
- **Expected insight:** The system should detect that clinical trial statistics trigger cognitive load in non-scientific audiences, and that community protection framing activates social relevance more than personal protection framing.

### Scenario 3: Price increase announcement (enterprise customers)
- **Seed:** "Starting Q3, NexaVault pricing will increase by 18% to support expanded infrastructure and new security features."
- **Question:** "How should we frame this price increase to minimize churn and negative sentiment?"
- **Demographic:** Enterprise decision-makers
- **Expected insight:** The system should find that leading with value addition (new features) before mentioning price scores better on reward response and lower on threat detection than leading with the price change.

### Scenario 4: Policy announcement (civic audience)
- **Seed:** Draft announcement of a new data privacy regulation requiring companies to delete user data within 30 days of request.
- **Question:** "How will different political constituencies react to this regulation?"
- **Demographic:** Policy-aware public
- **Expected insight:** The system should detect coalition formation along predictable lines (pro-privacy vs. pro-business) and identify framing strategies that minimize polarization.

### Scenario 5: Gen Z product marketing (young digital audience)
- **Seed:** Launch copy for a new AI-powered study tool targeting college students.
- **Question:** "What messaging approach will drive organic sharing among college students?"
- **Demographic:** Gen Z digital natives (18-27)
- **Expected insight:** The system should find that authenticity and peer proof outperform polished marketing language for this demographic, and that humor/relatability drive sharing more than feature lists.

---

## 6. Failure criteria — what would invalidate the approach

### Hard failures (POC is invalid)
- **No iteration improvement:** If the optimization loop shows no measurable improvement across iterations in 4+ out of 5 test scenarios, the iterative approach doesn't work.
- **No cognitive-social correlation:** If TRIBE v2 neural scores show zero correlation with MiroFish social propagation outcomes across all 5 test scenarios, the cross-system bridge hypothesis is wrong.
- **Worse than single-pass:** If Claude Opus generating content in a single pass (without TRIBE v2 or MiroFish feedback) consistently produces equal or better results than the full pipeline, the added complexity isn't justified.

### Soft failures (POC needs refinement, not abandonment)
- **Inconsistent improvement:** Iteration improvement in only 2-3 out of 5 scenarios suggests the approach works for some content types but not others. This narrows the product scope but doesn't kill it.
- **Demographic insensitivity:** If changing the demographic preset doesn't meaningfully change the scores or simulation dynamics, the personalization layer needs work.
- **Mass psychology output is generic:** If the psychology narrative reads the same regardless of what content was tested, the analysis layer needs better grounding in simulation specifics.

---

## 7. Output file format

### Campaign run output structure (JSON)

```json
{
  "campaign_id": "uuid",
  "timestamp": "ISO 8601",
  "config": {
    "agent_count": 40,
    "max_iterations": 4,
    "actual_iterations": 3,
    "thresholds": { "attention_score": 70, "backlash_risk_max": 25 },
    "thresholds_met": true,
    "demographic": "tech_professionals",
    "demographic_custom": null
  },
  "input": {
    "seed_content": "...",
    "prediction_question": "...",
    "constraints": "...",
    "baseline": null
  },
  "iterations": [
    {
      "iteration": 1,
      "variants": [
        {
          "variant_id": "v1_trust_first",
          "content": "...",
          "tribe_scores": {
            "attention_capture": 72,
            "emotional_resonance": 65,
            "memory_encoding": 58,
            "reward_response": 70,
            "threat_detection": 15,
            "cognitive_load": 42,
            "social_relevance": 68
          },
          "mirofish_metrics": {
            "organic_shares": 187,
            "sentiment_trajectory": [0.2, 0.3, 0.45, ...],
            "counter_narrative_count": 2,
            "peak_virality_cycle": 14,
            "sentiment_drift": 18.5,
            "coalition_formation": { "groups": [...] },
            "influence_concentration": 34,
            "platform_divergence": 22
          },
          "composite_scores": {
            "attention_score": 69,
            "virality_potential": 62,
            "backlash_risk": 14,
            "memory_durability": 55,
            "conversion_potential": 67,
            "audience_fit": 78,
            "polarization_index": 18
          }
        }
      ],
      "opus_analysis": "...",
      "iteration_improvement_notes": "..."
    }
  ],
  "final_output": {
    "winning_variant_id": "v3_trust_evolved",
    "verdict": "...",
    "scorecard": { ... },
    "deep_analysis": { ... },
    "mass_psychology_general": "...",
    "mass_psychology_technical": "..."
  }
}
```

### Export formats
- **Full report:** JSON (machine-readable, for integration)
- **Summary report:** Markdown (human-readable, for sharing)
- **Verdict only:** Plain text (for quick copy-paste)

---

*This document is the north star. Every architectural decision, task priority, and feature question should be checked against these objectives and success criteria.*
