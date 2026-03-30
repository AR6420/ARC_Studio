# Nexus Sim Demo Recording Script

**Target duration:** 7-8 minutes
**Format:** Screen recording with voiceover narration
**Prerequisites before recording:**
- All services running (Docker containers, TRIBE v2, orchestrator, UI)
- At least 1 completed campaign already in the system (for results walkthrough)
- A second campaign with a different demographic also completed (for comparison in Scene 7)
- Browser open to http://localhost:5173
- Terminal window ready for CLI demo

---

## Demo Script

### Scene 1: Introduction (0:00 - 0:30)

**Screen:** Dashboard landing page at http://localhost:5173 showing the sidebar with existing campaigns.

**Talking points:**

- "This is Nexus Sim, a content optimization platform that uses three AI systems working together."
- "The core idea: instead of asking one AI to generate content, we run a feedback loop between neural response prediction, multi-agent social simulation, and LLM-driven analysis."
- "The system generates content variants, scores them neurally using a brain prediction model, simulates how real audiences would react in a social environment, analyzes the combined data, and iterates until the content is measurably better."
- "Let me show you how it works."

**Duration:** 30 seconds

---

### Scene 2: Creating a Campaign (0:30 - 2:00)

**Screen:** Click "New Campaign" in the sidebar to open the campaign creation form.

**Action sequence:**

1. Click "New Campaign" in the sidebar
2. Paste seed content into the text area

**Suggested seed content (Scenario 1):**
> "Announcing NexaVault: enterprise cloud storage with zero-knowledge encryption and real-time collaborative editing. Your data never leaves your control."

3. Type the prediction question:
> "How will CTOs and engineering leaders react to this launch announcement?"

4. Select "Tech Professionals" from the demographic preset dropdown

**Talking points while filling the form:**

- "We start by pasting the content we want to test -- in this case, a product launch announcement for an enterprise cloud storage product."
- "The prediction question tells the system what specific aspect of audience reaction we care about."
- "We select a demographic preset. Each preset configures 40+ simulated agents with realistic personas, media habits, and cognitive profiles. The system has 6 presets, plus a custom option."

5. Show the configuration panel:
   - Point to the agent count slider (set to 40)
   - Point to the iteration slider (set to 3 or 4)
   - Note the time estimate updating as you adjust sliders

**Talking points for configuration:**

- "We can adjust how many agents participate in the simulation and how many optimization iterations to run."
- "Notice the time estimate updates in real-time -- this campaign should take about 12 minutes with these settings."

6. Click "Run Campaign"

**Duration:** 1.5 minutes

---

### Scene 3: Real-Time Progress (2:00 - 3:00)

**Screen:** The progress view showing real-time SSE updates.

**Action sequence:**

1. Watch the progress stream as it starts
2. Point out key elements as they appear

**Talking points:**

- "The campaign is now running. We can see real-time progress streaming from the server."
- "Each iteration goes through four steps: variant generation, where Claude creates content alternatives; neural scoring, where TRIBE v2 predicts brain activation patterns; social simulation, where MiroFish runs 40 AI agents interacting with the content; and cross-system analysis, where Claude Opus combines both data sources."
- "The iteration counter shows which pass we are on, and the ETA tells us roughly how much time is remaining."
- "This is all happening in real-time -- TRIBE v2 is running neural inference on the GPU while MiroFish agents are discussing and sharing the content in a simulated social environment."

**Note to recorder:** If you have a pre-completed campaign, you can cut to the results at this point to save recording time. The progress stream is most interesting for the first 20-30 seconds.

**Duration:** 1 minute

---

### Scene 4: Campaign Results -- Campaign Tab (3:00 - 4:30)

**Screen:** Campaign detail page, Campaign tab selected (this is the default tab).

**Action sequence:**

1. Campaign completes -- the results page loads automatically
2. Walk through the composite score cards at the top
3. Scroll to the variant ranking section
4. Show the iteration chart

**Talking points:**

- "The campaign is complete. Let's look at the results."
- "At the top, we see the 7 composite scores displayed as color-coded cards. Green means strong performance, amber is moderate, and red needs attention."
- "These scores combine data from both the neural model and the social simulation. For example, Virality Potential factors in emotional resonance and social relevance from the brain model, multiplied by actual sharing behavior from the simulation."
- "Below that, we see the variant ranking. The system generated and tested multiple content variants across several iterations. Each variant shows a score breakdown bar so you can compare at a glance."
- [Click to expand a variant] "Expanding a variant shows the full content text, so you can see exactly what each version says."
- [Point to iteration chart] "This chart shows how scores improved across iterations. Notice the upward trend -- each iteration produced better-scoring content because the system learned from the previous round's neural and social data."
- "This is the key insight: iterative optimization with real feedback from two independent systems produces measurably better content than a single generation pass."

**Duration:** 1.5 minutes

---

### Scene 5: Campaign Results -- Simulation Tab (4:30 - 5:30)

**Screen:** Switch to the Simulation tab.

**Action sequence:**

1. Click the "Simulation" tab
2. Walk through the MiroFish metrics panel
3. Show the sentiment timeline chart
4. Point out the agent grid (if data is present)

**Talking points:**

- "The Simulation tab shows results from the MiroFish social simulation."
- "These metrics tell us what happened when 40 AI agents -- each with a distinct persona, profession, media habits, and opinions -- encountered the content in a simulated social environment."
- "The organic share count shows how many agents voluntarily shared the content. Counter-narratives show how many distinct opposing arguments emerged."
- [Point to sentiment timeline] "The sentiment timeline shows how the audience's feeling about the content evolved over the simulation. You can see where opinion shifted and when it stabilized."
- "Peak virality cycle tells us when sharing activity peaked. Influence concentration indicates whether the outcome was driven by a few influential agents or was broadly distributed."
- "These are not hypothetical numbers -- they come from actual agent-to-agent interactions simulated over multiple cycles."

**Duration:** 1 minute

---

### Scene 6: Campaign Results -- Report Tab (5:30 - 6:30)

**Screen:** Switch to the Report tab.

**Action sequence:**

1. Click the "Report" tab
2. Show the Layer 1 verdict section
3. Scroll to or expand Layer 4 mass psychology
4. Toggle between general and technical modes
5. Show the JSON/Markdown export buttons

**Talking points:**

- "The Report tab is where the system delivers its analysis across four layers, each designed for a different audience."
- [Point to verdict] "Layer 1 is the verdict -- plain English that anyone can read. It tells you which variant won, why, and what to do about it. No jargon, no scores -- just a clear recommendation."
- [Scroll to mass psychology section] "Layer 4 is the mass psychology analysis. It has two modes."
- [Show general mode] "The general mode explains crowd dynamics in everyday language -- how opinion formed, shifted, and stabilized during the simulation."
- [Toggle to technical mode] "The technical mode reframes the same data using social psychology terminology -- referencing models like Granovetter's threshold theory, spiral of silence, and emotional contagion. This mode is designed for behavioral scientists."
- "Notice how the report references BOTH neural scores AND simulation metrics. The system explains why certain brain activation patterns led to specific social outcomes. This cross-system reasoning is something a single AI system cannot produce on its own."
- [Point to export buttons] "You can export the full results as JSON for integration with other tools, or as Markdown for sharing."

**Duration:** 1 minute

---

### Scene 7: Demographic Comparison (6:30 - 7:00)

**Screen:** Sidebar showing multiple completed campaigns with different demographics.

**Action sequence:**

1. Point to the sidebar listing campaigns with different demographic labels
2. Click between two campaigns to compare scores

**Talking points:**

- "Here's something powerful: we ran the same content through different demographic presets."
- "This campaign tested the NexaVault announcement with Tech Professionals, and this one tested it with Gen Z Digital Natives."
- [Switch between the two campaigns] "Notice how the scores differ significantly. The tech audience responded well to the security messaging, but the Gen Z audience found it less engaging -- they scored higher on cognitive load and lower on virality."
- "This confirms that the system produces meaningfully different results for different audiences, which is exactly what you need for targeted content strategy."

**Duration:** 30 seconds

---

### Scene 8: CLI Demo (7:00 - 7:30)

**Screen:** Switch to a terminal window.

**Action sequence:**

1. Type out (or paste) a CLI command:

```bash
python -m orchestrator.cli \
  --seed-content "Announcing NexaVault..." \
  --prediction-question "How will CTOs react?" \
  --demographic tech_professionals \
  --max-iterations 2 \
  --output results.json
```

2. Show the output briefly

**Talking points:**

- "For automation and integration, you can also run campaigns from the command line without the web UI."
- "This command runs the full pipeline -- variant generation, neural scoring, social simulation, analysis -- and writes the results to a JSON file."
- "The CLI is useful for batch testing, CI/CD integration, or scripting comparisons across multiple demographics."

**Duration:** 30 seconds

---

### Scene 9: Wrap-Up (7:30 - 8:00)

**Screen:** Return to the dashboard showing completed campaigns.

**Talking points:**

- "To recap: Nexus Sim combines three AI systems -- neural response prediction with TRIBE v2, multi-agent social simulation with MiroFish, and cross-system analysis with Claude Opus -- into an iterative feedback loop."
- "Each iteration produces measurably better content, and the system explains why certain neural patterns lead to specific social outcomes."
- "This is a Phase 1 proof of concept. The core thesis -- that iterative feedback between neural and social systems produces better content than single-pass generation -- is what we set out to validate."
- "Thank you for watching."

**Duration:** 30 seconds

---

## Recording Tips

- **Resolution:** Record at 1920x1080 or higher.
- **Browser zoom:** Set browser zoom to 110-125% so UI elements are clearly visible in the recording.
- **Terminal font size:** Increase terminal font to 16pt+ for CLI demo readability.
- **Pre-load data:** Have at least 2-3 completed campaigns in the system before recording so the sidebar looks populated and you can show demographic comparison without waiting.
- **Narration pace:** Aim for conversational speed. Pause briefly when changing screens to let the viewer orient.
- **Editing:** You can cut the progress waiting time (Scene 3) to keep the demo under 8 minutes. Show the start of progress streaming, then cut to completed results.
- **Fallback:** If a service is unavailable during recording, the graceful degradation message makes for a good bonus talking point about system resilience.
