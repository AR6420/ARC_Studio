"""
MiroFish social simulation runner for the A.R.C Studio orchestrator.

Orchestrates sequential MiroFish simulations for content variants and computes
8 structured metrics from raw simulation output (posts, actions, timeline,
agent_stats).

Per D-04: Simulations run SEQUENTIALLY to avoid Neo4j graph DB conflicts.
Per Pitfall 6 (research): MiroFish does NOT return structured metrics --
they must be computed from raw data.

Returns None per variant on failure without crashing the overall campaign (D-05).
"""

import logging
import math
from typing import Any

from orchestrator.clients.mirofish_client import MirofishClient

logger = logging.getLogger(__name__)


class MirofishRunner:
    """
    Orchestrates MiroFish social simulations for content variants and
    computes 8 structured metrics from raw simulation output.
    Per D-04: Simulations run SEQUENTIALLY to avoid Neo4j graph DB conflicts.
    """

    def __init__(self, mirofish_client: MirofishClient):
        self._client = mirofish_client

    async def simulate_variants(
        self,
        variants: list[dict[str, Any]],
        prediction_question: str,
        campaign_id: str,
        agent_count: int = 40,
        max_rounds: int = 30,
    ) -> list[dict[str, Any] | None]:
        """
        Run MiroFish simulation for each variant and compute 8 metrics.

        Per D-04: Simulations are sequential. Graph is rebuilt per variant.

        Returns list of metric dicts or None per variant.
        """
        results: list[dict[str, Any] | None] = []

        # Pre-check LiteLLM token before starting any simulations.
        # Catches expired OAuth tokens early instead of failing silently per-variant.
        token_ok = await self._client.verify_llm_token()
        if not token_ok:
            logger.error(
                "MiroFish LLM token is invalid and auto-refresh failed. "
                "ALL MiroFish simulations will be skipped. "
                "Run: scripts/refresh-env.sh --restart"
            )
            return [None] * len(variants)

        for i, variant in enumerate(variants):
            variant_id = variant.get("id", f"variant_{i}")
            content = variant.get("content", "")

            if not content.strip():
                logger.warning("Variant %s has empty content, skipping MiroFish", variant_id)
                results.append(None)
                continue

            logger.info("Running MiroFish simulation for variant %s (%d/%d)", variant_id, i + 1, len(variants))

            # Run the full simulation workflow
            raw_results = await self._client.run_simulation(
                content=content,
                simulation_requirement=prediction_question,
                project_name=f"{campaign_id}_{variant_id}",
                max_rounds=max_rounds,
            )

            if not raw_results:
                logger.warning("MiroFish simulation returned None for variant %s", variant_id)
                results.append(None)
                continue

            # Unwrap nested MiroFish response format:
            # MiroFish returns {"posts": {"posts": [...], "count": N}, ...}
            # compute_metrics expects {"posts": [...], "actions": [...], ...}
            unwrapped = {}
            for key in ("posts", "actions", "timeline", "agent_stats"):
                val = raw_results.get(key, [])
                if isinstance(val, dict):
                    # Extract the inner list: {"posts": [...]} or {"actions": [...]}
                    inner = val.get(key) or val.get("stats") or val.get("timeline") or []
                    unwrapped[key] = inner
                else:
                    unwrapped[key] = val
            unwrapped["simulation_id"] = raw_results.get("simulation_id")

            # Compute 8 structured metrics from raw data
            metrics = compute_metrics(unwrapped, agent_count)
            logger.info(
                "MiroFish metrics for %s: shares=%d, counter_narratives=%d, drift=%.2f",
                variant_id,
                metrics.get("organic_shares", 0),
                metrics.get("counter_narrative_count", 0),
                metrics.get("sentiment_drift", 0),
            )
            results.append(metrics)

        simulated_count = sum(1 for r in results if r is not None)
        logger.info("MiroFish simulation complete: %d/%d variants simulated", simulated_count, len(variants))

        return results


def compute_metrics(raw: dict[str, Any], agent_count: int) -> dict[str, Any]:
    """
    Compute 8 structured metrics from raw MiroFish simulation output.

    Input `raw` has keys: posts, actions, timeline, agent_stats.

    Returns dict with:
    - organic_shares (int): Count of share/repost actions
    - sentiment_trajectory (list[float]): Per-round average sentiment [-1 to 1]
    - counter_narrative_count (int): Count of distinct opposing narratives
    - peak_virality_cycle (int): Round with most sharing activity
    - sentiment_drift (float): Delta between first and last round sentiment
    - coalition_formation (int): Number of distinct pro/anti coalitions
    - influence_concentration (float): Gini coefficient of per-agent action counts [0-1]
    - platform_divergence (float): Divergence between platform metrics [0-1]
    """
    posts = raw.get("posts", [])
    actions = raw.get("actions", [])
    timeline = raw.get("timeline", [])
    agent_stats = raw.get("agent_stats", [])

    # 1. organic_shares: count share/repost actions
    organic_shares = _count_shares(actions, posts)

    # 2. sentiment_trajectory: per-round sentiment from timeline
    sentiment_trajectory = _compute_sentiment_trajectory(timeline, actions)

    # 3. counter_narrative_count: count distinct opposing narratives
    counter_narrative_count = _count_counter_narratives(actions, posts)

    # 4. peak_virality_cycle: round with most sharing
    peak_virality_cycle = _find_peak_virality(timeline, actions)

    # 5. sentiment_drift: delta between first and last round
    sentiment_drift = _compute_sentiment_drift(sentiment_trajectory)

    # 6. coalition_formation: number of distinct groups
    coalition_formation = _count_coalitions(agent_stats, actions)

    # 7. influence_concentration: gini coefficient of action counts
    influence_concentration = _compute_influence_gini(agent_stats, actions, agent_count)

    # 8. platform_divergence: twitter vs reddit metric difference
    platform_divergence = _compute_platform_divergence(actions, posts)

    return {
        "organic_shares": organic_shares,
        "sentiment_trajectory": sentiment_trajectory,
        "counter_narrative_count": counter_narrative_count,
        "peak_virality_cycle": peak_virality_cycle,
        "sentiment_drift": sentiment_drift,
        "coalition_formation": coalition_formation,
        "influence_concentration": round(influence_concentration, 3),
        "platform_divergence": round(platform_divergence, 3),
    }


def _count_shares(actions: list, posts: list) -> int:
    """Count CREATE_POST and REPOST/SHARE actions."""
    share_types = {"CREATE_POST", "REPOST", "SHARE", "RETWEET", "share", "repost", "retweet"}
    count = 0
    for action in actions:
        action_type = action.get("action_type", "") or action.get("type", "")
        if action_type.upper() in {t.upper() for t in share_types}:
            count += 1
    # Also count posts as shares if actions don't cover it
    if count == 0:
        count = len(posts)
    return count


def _compute_sentiment_trajectory(timeline: list, actions: list) -> list[float]:
    """
    Compute per-round sentiment values.
    Uses timeline data if available, otherwise derives from actions.
    Returns list of sentiment values in [-1, 1] range.
    """
    if timeline:
        trajectory = []
        for entry in timeline:
            # Timeline entries may have sentiment, avg_sentiment, or similar
            sent = entry.get("sentiment", entry.get("avg_sentiment", entry.get("average_sentiment")))
            if sent is not None:
                trajectory.append(float(sent))
            else:
                # Try to compute from round data
                trajectory.append(0.0)
        if trajectory:
            return trajectory

    # Fallback: group actions by round and estimate sentiment
    if not actions:
        return [0.0]

    rounds: dict[int, list[float]] = {}
    for action in actions:
        round_num = action.get("round", action.get("cycle", 0))
        # Simple heuristic: positive actions (share, like) = +0.5, negative (counter, oppose) = -0.5, neutral = 0
        action_type = (action.get("action_type", "") or action.get("type", "")).lower()
        if any(kw in action_type for kw in ["share", "like", "repost", "support"]):
            sentiment = 0.5
        elif any(kw in action_type for kw in ["counter", "oppose", "criticize", "negative"]):
            sentiment = -0.5
        else:
            sentiment = 0.0
        rounds.setdefault(round_num, []).append(sentiment)

    trajectory = []
    for r in sorted(rounds.keys()):
        vals = rounds[r]
        trajectory.append(sum(vals) / len(vals) if vals else 0.0)

    return trajectory if trajectory else [0.0]


def _count_counter_narratives(actions: list, posts: list) -> int:
    """Count distinct opposing/counter narratives."""
    counter_types = {"COUNTER_NARRATIVE", "OPPOSE", "COUNTER", "counter_narrative", "counter_post"}
    count = 0
    for action in actions:
        action_type = (action.get("action_type", "") or action.get("type", "")).upper()
        if any(ct.upper() in action_type for ct in counter_types):
            count += 1
    # Also check posts for counter-narrative indicators
    for post in posts:
        if post.get("is_counter_narrative") or post.get("stance") in ("against", "opposing", "counter"):
            count += 1
    return count


def _find_peak_virality(timeline: list, actions: list) -> int:
    """Find the round with most sharing activity."""
    if timeline:
        best_round = 0
        best_activity = 0
        for i, entry in enumerate(timeline):
            activity = entry.get("shares", entry.get("total_actions", entry.get("activity", 0)))
            if activity is not None and activity > best_activity:
                best_activity = activity
                best_round = i + 1
        if best_round > 0:
            return best_round

    # Fallback: count actions per round
    round_counts: dict[int, int] = {}
    for action in actions:
        r = action.get("round", action.get("cycle", 0))
        round_counts[r] = round_counts.get(r, 0) + 1

    if round_counts:
        return max(round_counts, key=round_counts.get)  # type: ignore[arg-type]
    return 1


def _compute_sentiment_drift(trajectory: list[float]) -> float:
    """Delta between first and last sentiment values."""
    if not trajectory or len(trajectory) < 2:
        return 0.0
    return round(trajectory[-1] - trajectory[0], 3)


def _count_coalitions(agent_stats: list, actions: list) -> int:
    """
    Count distinct coalitions based on agent behavior clustering.
    Simple approach: agents who share = pro coalition, agents who counter = anti coalition,
    inactive agents = neutral. Count non-empty groups.
    """
    pro = set()
    anti = set()

    for action in actions:
        agent_id = action.get("agent_id", action.get("agent", ""))
        action_type = (action.get("action_type", "") or action.get("type", "")).lower()
        if any(kw in action_type for kw in ["share", "repost", "like", "support", "create_post"]):
            pro.add(agent_id)
        elif any(kw in action_type for kw in ["counter", "oppose", "criticize"]):
            anti.add(agent_id)

    # Also check agent_stats for explicit stances
    for stat in agent_stats:
        agent_id = stat.get("agent_id", stat.get("id", ""))
        stance = (stat.get("stance", "") or "").lower()
        if stance in ("pro", "supporter", "advocate"):
            pro.add(agent_id)
        elif stance in ("anti", "opponent", "critic"):
            anti.add(agent_id)

    coalitions = 0
    if pro:
        coalitions += 1
    if anti:
        coalitions += 1
    # If there are agents in neither group, that's a neutral coalition
    all_agents = pro | anti
    if agent_stats and len(all_agents) < len(agent_stats):
        coalitions += 1

    return max(coalitions, 1)  # At least 1


def _compute_influence_gini(agent_stats: list, actions: list, agent_count: int) -> float:
    """
    Compute Gini coefficient of per-agent action counts.
    0 = perfectly equal, 1 = one agent dominates.
    """
    # Collect action counts per agent
    counts: dict[str, int] = {}
    for action in actions:
        agent_id = action.get("agent_id", action.get("agent", "unknown"))
        counts[agent_id] = counts.get(agent_id, 0) + 1

    # If we have agent_stats with action counts, use those
    if agent_stats and not counts:
        for stat in agent_stats:
            agent_id = stat.get("agent_id", stat.get("id", ""))
            count = stat.get("action_count", stat.get("total_actions", 0))
            counts[agent_id] = count

    if not counts:
        return 0.0

    # Pad with zeros for agents with no actions
    values = list(counts.values())
    while len(values) < agent_count:
        values.append(0)

    values.sort()
    n = len(values)
    if n == 0 or sum(values) == 0:
        return 0.0

    # Gini coefficient formula
    numerator = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(values))
    denominator = n * sum(values)
    return max(0.0, min(1.0, numerator / denominator))


def _compute_platform_divergence(actions: list, posts: list) -> float:
    """
    Compute divergence between Twitter and Reddit activity.
    Returns value in [0, 1] where 0 = identical, 1 = completely different.
    """
    twitter_count = 0
    reddit_count = 0

    for item in actions + posts:
        platform = (item.get("platform", "") or "").lower()
        if "twitter" in platform or "x" in platform:
            twitter_count += 1
        elif "reddit" in platform:
            reddit_count += 1

    total = twitter_count + reddit_count
    if total == 0:
        return 0.0

    # Divergence as absolute difference in proportions
    twitter_prop = twitter_count / total
    reddit_prop = reddit_count / total
    divergence = abs(twitter_prop - reddit_prop)
    return round(divergence, 3)
