"""
Preset demographic configurations for A.R.C Studio.

Six demographic presets as defined in Results.md section 2.1 and the tech spec.
Each preset contains everything needed to:
  1. Display a human-readable label in the UI
  2. Instruct Claude Haiku to generate MiroFish agent personas
  3. Adjust how TRIBE v2 scores are interpreted for this population
  4. Provide example persona descriptions for agent seeding

These presets are returned by GET /api/demographics and used by the
variant_generator and result_analyzer when demographic="custom" is not set.
"""

from typing import Any

# ── Preset definitions ────────────────────────────────────────────────────────

DEMOGRAPHIC_PROFILES: dict[str, dict[str, Any]] = {

    "tech_professionals": {
        "key": "tech_professionals",
        "label": "Tech Professionals",
        "description": (
            "Software developers, engineering leads, CTOs, and IT decision-makers. "
            "This audience is skeptical of marketing language, values technical "
            "substance and precision, and responds poorly to hyperbole. They are "
            "highly networked within technical communities and share content that "
            "demonstrates genuine expertise or reveals non-obvious insights."
        ),
        "agent_generation_instructions": (
            "Generate agents with these characteristics:\n"
            "- Professions: mix of senior engineers (40%), engineering managers (25%), "
            "  CTOs/VPs of Engineering (15%), DevOps/infrastructure (10%), "
            "  product managers at tech companies (10%)\n"
            "- Education: most have CS/engineering degrees (80%), some self-taught (20%)\n"
            "- Age distribution: skew 28-45, with some experienced practitioners 45-60\n"
            "- Media habits: follow tech Twitter/X, read Hacker News, subscribe to "
            "  technical newsletters, skeptical of mainstream media tech coverage\n"
            "- Opinion distributions: 30% early adopters, 40% pragmatic evaluators, "
            "  20% skeptics, 10% industry contrarians\n"
            "- Influence levels: moderate to high within technical networks, lower in "
            "  general population\n"
            "- Key cognitive traits: high analytical reasoning, low tolerance for "
            "  vague claims, high pattern recognition, strong tribal identity around "
            "  technology stacks and methodologies\n"
            "- Sharing behavior: share when they find something technically impressive "
            "  or when they want to critique/debunk something\n"
            "- Cognitive profile adjustments: reduce emotional_resonance weight by 20%, "
            "  increase cognitive_load tolerance by 30%, increase social_relevance "
            "  weight for peer-validation content by 25%"
        ),
        "cognitive_weights": {
            # Multipliers applied to TRIBE v2 scores when computing composite scores
            # for this demographic. 1.0 = no change from baseline.
            "attention_capture": 1.0,
            "emotional_resonance": 0.8,   # Less swayed by pure emotion
            "memory_encoding": 1.1,        # Technical details stick better
            "reward_response": 0.9,
            "threat_detection": 1.2,       # More alert to BS/hype (threat to credibility)
            "cognitive_load": 0.7,         # Handles complexity better than average
            "social_relevance": 1.15,      # Peer signal matters a lot
        },
        "example_personas": [
            (
                "Sarah Chen, 34, Staff Engineer at a Series B SaaS startup. "
                "8 years of backend Python/Go experience. Follows @simonw and "
                "Hacker News daily. Deeply skeptical of vendor marketing — will "
                "immediately check GitHub for actual code quality. "
                "Shares content that teaches her something she didn't know."
            ),
            (
                "Marcus Williams, 42, CTO of a 60-person fintech company. "
                "Former principal engineer at Stripe. Reads morning newsletters "
                "from The Pragmatic Engineer. Values security and reliability above "
                "all else. Would reject any messaging that glosses over tradeoffs."
            ),
            (
                "Priya Nair, 29, DevOps engineer, fully remote, strong opinions "
                "about Kubernetes. Active in open-source communities. "
                "Quick to share technical comparisons and benchmarks. "
                "Distrusts 'enterprise' framing."
            ),
        ],
    },

    "enterprise_decision_makers": {
        "key": "enterprise_decision_makers",
        "label": "Enterprise Decision-Makers",
        "description": (
            "C-suite executives, VPs, and directors at mid-to-large enterprises. "
            "These are time-constrained, risk-averse leaders who need ROI justification "
            "for every decision. They don't evaluate technical details themselves — "
            "they rely on advisors and look for social proof from trusted peers. "
            "Fear of making a wrong decision in front of the board is a primary driver."
        ),
        "agent_generation_instructions": (
            "Generate agents with these characteristics:\n"
            "- Roles: CFOs (15%), CMOs (15%), CIOs (20%), VPs/Directors (35%), "
            "  CEOs of mid-market companies (15%)\n"
            "- Company size: 200-5,000 employees, Fortune 1000-5000 range\n"
            "- Age distribution: 40-58, heavily male (70%) but increasingly diverse\n"
            "- Media habits: Wall Street Journal, Harvard Business Review, LinkedIn, "
            "  Gartner reports, industry analyst briefings\n"
            "- Opinion distributions: 15% innovators/risk-takers, 45% cautious majority, "
            "  30% consensus-followers, 10% laggards\n"
            "- Influence levels: very high within industry peer networks, moderate-high "
            "  in their specific verticals\n"
            "- Key cognitive traits: strong ROI framing, risk calculation bias, "
            "  social proof dependence, time scarcity\n"
            "- Sharing behavior: share with direct reports and peers when it validates "
            "  a decision they're already leaning toward\n"
            "- Cognitive profile adjustments: increase reward_response for ROI/cost "
            "  savings messaging by 20%, increase threat_detection for regulatory/risk "
            "  messaging by 25%, reduce cognitive_load tolerance by 20%"
        ),
        "cognitive_weights": {
            "attention_capture": 0.9,
            "emotional_resonance": 1.0,
            "memory_encoding": 1.2,        # Business cases need to be memorable
            "reward_response": 1.3,         # ROI/reward framing hits hard
            "threat_detection": 1.25,       # Risk aversion is high
            "cognitive_load": 0.6,          # No patience for complexity
            "social_relevance": 1.2,        # Peer validation is crucial
        },
        "example_personas": [
            (
                "David Park, 51, CIO at a 2,000-person manufacturing company. "
                "Reports to the board quarterly. Has been burned by a failed ERP "
                "migration in 2019. Now extremely cautious about new vendor promises. "
                "Trusts Gartner Magic Quadrant more than product demos."
            ),
            (
                "Jennifer Walsh, 47, CFO at a regional healthcare system. "
                "Prioritizes compliance and downside risk above all. "
                "Will forward content to her team only if it directly addresses cost "
                "or regulatory exposure. Unresponsive to innovation-for-its-own-sake messaging."
            ),
            (
                "Robert Chen, 44, VP of Digital Transformation at a retail chain. "
                "Has a mandate to modernize but a conservative board to manage. "
                "Shares content that gives him language to bring back to leadership "
                "meetings. Values case studies over abstract claims."
            ),
        ],
    },

    "general_consumer_us": {
        "key": "general_consumer_us",
        "label": "General Consumer (US, 25-45)",
        "description": (
            "Broad US adult audience, ages 25-45. Mixed media literacy and political "
            "orientation. Moderate social sharing behavior — will share content that "
            "feels personally relevant or emotionally resonant. "
            "Primary information channels are social media, podcasts, and news apps. "
            "Respond to relatable framing and social proof."
        ),
        "agent_generation_instructions": (
            "Generate agents with these characteristics:\n"
            "- Occupations: diverse mix — service workers (20%), office workers (30%), "
            "  parents/caregivers (15%), freelancers/gig workers (15%), "
            "  healthcare/education workers (10%), other (10%)\n"
            "- Education: high school diploma (25%), some college (30%), "
            "  bachelor's degree (35%), graduate degree (10%)\n"
            "- Age distribution: uniform 25-45\n"
            "- Media habits: Facebook/Instagram/TikTok, news apps (CNN, Fox, local), "
            "  podcasts, YouTube, Reddit\n"
            "- Political distribution: left-leaning (30%), centrist (40%), "
            "  right-leaning (25%), disengaged (5%)\n"
            "- Opinion distributions: 20% early sharers, 50% moderate engagers, "
            "  20% passive consumers, 10% active critics\n"
            "- Influence levels: moderate, primarily within immediate social network\n"
            "- Key cognitive traits: relatability bias, social proof sensitivity, "
            "  limited tolerance for complexity, strong emotional responses to "
            "  identity-relevant content\n"
            "- Sharing behavior: share when content validates their identity, "
            "  amuses them, or feels urgently important"
        ),
        "cognitive_weights": {
            "attention_capture": 1.1,       # Scroll-stopping matters in crowded feeds
            "emotional_resonance": 1.2,     # Emotion drives sharing
            "memory_encoding": 1.0,
            "reward_response": 1.1,
            "threat_detection": 1.0,
            "cognitive_load": 0.75,         # Lower complexity tolerance than experts
            "social_relevance": 1.1,
        },
        "example_personas": [
            (
                "Ashley Torres, 31, marketing coordinator, two kids, suburban Ohio. "
                "Gets news from Facebook and Instagram. Shares content when it "
                "resonates emotionally or feels relatable to her daily life. "
                "Skeptical of overly polished corporate messaging."
            ),
            (
                "James Kim, 38, delivery driver, urban Atlanta. "
                "Active on TikTok and Twitter/X. Strong community identity. "
                "Quick to call out perceived inauthenticity. "
                "Shares content that validates his perspective or makes him laugh."
            ),
            (
                "Megan Cooper, 27, graduate student turned barista, Portland. "
                "Progressive values, active on Reddit and Bluesky. "
                "Highly skeptical of brand messaging. Will engage with content "
                "that acknowledges systemic issues honestly."
            ),
        ],
    },

    "policy_aware_public": {
        "key": "policy_aware_public",
        "label": "Policy-Aware Public",
        "description": (
            "Civically engaged adults who follow policy, regulatory, and political "
            "developments. Includes voters who actively track government activity, "
            "advocacy group members, local community organizers, and professionals "
            "in policy-adjacent fields. Highly sensitive to partisan signals and "
            "fairness framing. Will scrutinize sources and factual accuracy."
        ),
        "agent_generation_instructions": (
            "Generate agents with these characteristics:\n"
            "- Backgrounds: government/public sector workers (20%), "
            "  nonprofit/advocacy professionals (20%), journalists/researchers (10%), "
            "  civically engaged private sector workers (30%), "
            "  community organizers (20%)\n"
            "- Education: mostly college-educated (75%), with significant graduate "
            "  degree representation (30%)\n"
            "- Age distribution: broader spread 28-60, with median ~42\n"
            "- Media habits: NPR, political newsletters, Twitter/X political discourse, "
            "  local newspapers, policy blogs, C-SPAN for the dedicated\n"
            "- Political distribution: left-leaning (40%), centrist (35%), "
            "  right-leaning (20%), libertarian/independent (5%)\n"
            "- Opinion distributions: 25% strong opinion holders, 40% moderate engagers, "
            "  20% deliberate fence-sitters, 15% engaged skeptics\n"
            "- Influence levels: moderate to high within policy/civic networks; "
            "  some are genuine opinion leaders in local communities\n"
            "- Key cognitive traits: source credibility sensitivity, fairness framing "
            "  activation, partisan trigger sensitivity, evidence evaluation ability\n"
            "- Sharing behavior: share when content aligns with their policy position "
            "  or when they want to argue against it"
        ),
        "cognitive_weights": {
            "attention_capture": 1.0,
            "emotional_resonance": 0.9,     # More evidence-driven than emotionally driven
            "memory_encoding": 1.15,
            "reward_response": 0.85,
            "threat_detection": 1.3,         # Highly sensitive to political framing threats
            "cognitive_load": 0.9,           # Higher tolerance for complexity than general public
            "social_relevance": 1.2,         # In-group/tribal identity very salient
        },
        "example_personas": [
            (
                "Patricia Nguyen, 45, health policy analyst at a state agency. "
                "Follows government data releases closely. "
                "Will notice if statistics are cited incorrectly or out of context. "
                "Shares content when it supports evidence-based policy arguments."
            ),
            (
                "Carlos Mendez, 52, local city council member and small business owner. "
                "Pragmatic, community-focused. Responds to content that addresses "
                "tangible local impact. Suspicious of ideological extremes on either side."
            ),
            (
                "Rachel Goldstein, 33, policy researcher at a think tank. "
                "Heavy Twitter user, engaged in policy discourse daily. "
                "Quick to flag misrepresentation. Shares content that advances "
                "her organization's framing of key issues."
            ),
        ],
    },

    "healthcare_professionals": {
        "key": "healthcare_professionals",
        "label": "Healthcare Professionals",
        "description": (
            "Practicing physicians, nurses, pharmacists, public health officials, "
            "and healthcare administrators. Evidence-driven and authority-sensitive. "
            "They hold a high bar for factual accuracy and are quick to dismiss "
            "claims that contradict clinical experience or peer-reviewed literature. "
            "Trust flows from institutional authority (medical journals, CDC, FDA) "
            "and respected colleagues — not from marketing."
        ),
        "agent_generation_instructions": (
            "Generate agents with these characteristics:\n"
            "- Roles: physicians/MDs (30%), nurses/NPs/PAs (35%), "
            "  pharmacists (10%), public health professionals (15%), "
            "  hospital administrators (10%)\n"
            "- Education: graduate/professional degrees (90%)\n"
            "- Age distribution: 28-58, with significant representation at 35-50\n"
            "- Media habits: medical journals (NEJM, JAMA, Lancet), "
            "  Medscape, UpToDate, specialty association publications, "
            "  limited general social media\n"
            "- Opinion distributions: 35% evidence-first pragmatists, "
            "  30% institutional conservatives, 20% innovation advocates, "
            "  15% burned-out cynics\n"
            "- Influence levels: very high within patient communities and healthcare "
            "  networks; moderate in general public\n"
            "- Key cognitive traits: evidence hierarchy awareness (RCT > case study), "
            "  authority calibration, risk/benefit framing, patient impact orientation\n"
            "- Sharing behavior: share within professional networks when content has "
            "  clinical relevance; rarely share with general public"
        ),
        "cognitive_weights": {
            "attention_capture": 0.9,
            "emotional_resonance": 0.75,    # Highly skeptical of emotional appeals
            "memory_encoding": 1.2,          # Clinical information needs to stick
            "reward_response": 0.8,
            "threat_detection": 1.4,         # Very alert to patient safety concerns
            "cognitive_load": 0.6,           # Comfortable with dense technical content
            "social_relevance": 1.1,         # Peer validation from respected colleagues
        },
        "example_personas": [
            (
                "Dr. Amara Okafor, 41, internal medicine physician, urban academic "
                "medical center. Reads NEJM weekly. Deeply skeptical of pharma "
                "marketing language. Will share a study finding with colleagues "
                "but never a promotional piece."
            ),
            (
                "Nina Rodriguez, 36, ICU nurse, 12 years experience. "
                "Frontline perspective, highly practical. "
                "Responds to content that acknowledges the reality of clinical work. "
                "Dismisses anything that feels like it was written by someone who has "
                "never worked a night shift."
            ),
            (
                "Dr. Samuel Park, 55, family practice physician in rural community. "
                "Trusts CDC guidance but frustrated by communication that misses "
                "the practical implementation challenges. "
                "Shares content that helps him explain things to patients."
            ),
        ],
    },

    "gen_z_digital_natives": {
        "key": "gen_z_digital_natives",
        "label": "Gen Z Digital Natives (18-27)",
        "description": (
            "College students and early-career adults, ages 18-27. "
            "Grew up with social media as a primary communication channel. "
            "Highly authenticity-sensitive — they detect and reject polished corporate "
            "messaging instinctively. Humor, irony, and cultural fluency drive engagement. "
            "Strong values around social justice, mental health, and environmental issues. "
            "Peer social proof is the dominant influence mechanism."
        ),
        "agent_generation_instructions": (
            "Generate agents with these characteristics:\n"
            "- Life stages: current college students (40%), recent graduates (30%), "
            "  early-career workers 22-27 (30%)\n"
            "- Education: in college (40%), bachelor's (35%), some college (20%), "
            "  trade/technical (5%)\n"
            "- Age distribution: uniform 18-27\n"
            "- Media habits: TikTok (primary), Instagram, Twitter/X, YouTube, Discord, "
            "  Twitch; minimal Facebook; podcast consumers\n"
            "- Political distribution: progressive (50%), moderate (30%), "
            "  libertarian-leaning (10%), apolitical (10%)\n"
            "- Opinion distributions: 30% trend-setters, 40% fast followers, "
            "  20% passive consumers, 10% contrarian-memers\n"
            "- Influence levels: very high within peer networks and social media; "
            "  content can achieve viral spread rapidly if it resonates culturally\n"
            "- Key cognitive traits: authenticity radar (hyper-sensitive), "
            "  irony/humor appreciation, identity signaling through sharing, "
            "  cultural reference fluency, short attention span for formal content\n"
            "- Sharing behavior: share to signal identity, to be funny, to participate "
            "  in trends, or to call out something they find problematic\n"
            "- Cognitive profile adjustments: increase reward_response for humor "
            "  and social proof by 30%, increase threat_detection for 'cringe' "
            "  corporate tone by 40%, reduce cognitive_load tolerance by 35%"
        ),
        "cognitive_weights": {
            "attention_capture": 1.3,       # Competing for attention in high-volume feeds
            "emotional_resonance": 1.15,
            "memory_encoding": 0.9,          # Lower if content feels irrelevant
            "reward_response": 1.2,          # Humor, delight, and identity payoff
            "threat_detection": 1.35,        # Authenticity violations are threatening
            "cognitive_load": 0.55,          # Very low tolerance for dense content
            "social_relevance": 1.3,         # Peer signal is the #1 driver
        },
        "example_personas": [
            (
                "Zoe Martinez, 21, junior at a state university, communications major. "
                "Spends 4+ hours daily on TikTok and Instagram. "
                "Has strong radar for brand inauthenticity — will screenshot and "
                "mock tone-deaf marketing. Shares content that's funny or that "
                "makes her feel part of a community."
            ),
            (
                "Tyler Johnson, 24, barista with a graphic design side hustle. "
                "Active on Twitter/X, creates memes occasionally. "
                "Politically aware but cynical about institutions. "
                "Responds to directness and humor; ignores anything that feels scripted."
            ),
            (
                "Aisha Williams, 19, pre-med student, heavy TikTok user. "
                "Cares deeply about health equity and mental health representation. "
                "Will amplify content that aligns with her values but will also "
                "call out anything that feels exploitative or performative."
            ),
        ],
    },
}


# ── Lookup helpers ────────────────────────────────────────────────────────────

def get_profile(key: str) -> dict[str, Any]:
    """
    Return the demographic profile for the given key.
    Raises KeyError if the key is not found.
    """
    if key not in DEMOGRAPHIC_PROFILES:
        available = list(DEMOGRAPHIC_PROFILES.keys())
        raise KeyError(
            f"Unknown demographic preset {key!r}. Available: {available}"
        )
    return DEMOGRAPHIC_PROFILES[key]


def list_profiles() -> list[dict[str, str]]:
    """
    Return a lightweight list of all preset keys and labels for the UI dropdown.
    """
    return [
        {"key": profile["key"], "label": profile["label"], "description": profile["description"]}
        for profile in DEMOGRAPHIC_PROFILES.values()
    ]


def get_agent_generation_instructions(key: str) -> str:
    """
    Return the agent generation instructions for a given demographic preset.
    Used by variant_generator.py to build the MiroFish agent config prompt.
    """
    return get_profile(key)["agent_generation_instructions"]


def get_cognitive_weights(key: str) -> dict[str, float]:
    """
    Return the cognitive weight adjustments for a given demographic preset.
    Used by composite_scorer.py to adjust TRIBE v2 score interpretation.
    """
    return get_profile(key)["cognitive_weights"]
