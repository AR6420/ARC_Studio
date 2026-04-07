"""Normalize raw ROI activation values to 0-100 scores.

Strategy
--------
The normalizer uses z-score normalization with a sigmoid mapping to
convert raw ROI activations into 0-100 scores:

    z = (activation - baseline_mean) / baseline_std
    score = sigmoid(z * spread_factor) * 100

This produces continuous scores across the full 0-100 range regardless
of baseline size.  The ``spread_factor`` (default 1.5) controls how
quickly scores move from 0 toward 100 as activations exceed the baseline
mean.  A factor of 1.5 maps +/-2 std to roughly 5-95.

Baseline management
-------------------
Call :func:`update_baseline` to add raw activation dicts to the baseline
pool.  The pool is kept in memory and is NOT persisted across restarts by
default.  A typical startup routine scores REFERENCE_TEXTS once after
model load to seed the baseline.

All scores are clamped to [0, 100].
"""

import logging
from typing import Sequence

import numpy as np

logger = logging.getLogger(__name__)

# Dimension names in a stable order (matches ScoreResponse field order)
DIMENSIONS = [
    "attention_capture",
    "emotional_resonance",
    "memory_encoding",
    "reward_response",
    "threat_detection",
    "cognitive_load",
    "social_relevance",
]

# Spread factor for z-score -> sigmoid mapping.
# Controls score sensitivity:
#   1.0: +/-3 std maps to ~5-95
#   1.5: +/-2 std maps to ~5-95
#   2.0: +/-1.5 std maps to ~5-95
_SPREAD_FACTOR = 1.5

# Reference texts used to seed the baseline on first startup.
# Covers a diverse range of content types: neutral, emotional, threatening,
# social, reward, cognitive, memory, action, marketing/persuasive, and calm.
# The marketing/persuasive texts ensure the baseline spans the same
# activation range as typical campaign content.
REFERENCE_TEXTS: list[str] = [
    # Neutral / informational
    "The water cycle describes how water evaporates from the surface of the earth, "
    "rises into the atmosphere, cools and condenses into rain or snow, and falls "
    "again as precipitation.",
    # Emotional / narrative
    "She stood at the edge of the cliff as the sun dipped below the horizon, her "
    "heart pounding, tears streaming silently down her face. She had not expected "
    "to feel grief so physically.",
    # Threatening / alarming
    "Warning: all residents in the flood zone must evacuate immediately. Emergency "
    "services report rising waters and structural damage to the bridge. Do not "
    "attempt to cross. Seek higher ground now.",
    # Social / relationship
    "They had not spoken in three years, but when he saw her across the crowded "
    "room his pulse quickened. She smiled, and for a moment nothing else existed.",
    # Reward / anticipation
    "The winning ticket number has been announced. After checking three times, she "
    "realized it matched every digit. She would never have to worry about money again.",
    # Cognitive / abstract
    "Consider a graph G where every vertex has degree at least k. By the handshaking "
    "lemma, the sum of all vertex degrees equals twice the number of edges, implying "
    "a minimum edge count that grows linearly with vertex count.",
    # Memory / autobiographical
    "The smell of fresh bread always brought him back to his grandmother's kitchen: "
    "the worn wooden table, the blue-checked curtains, her humming softly while "
    "flour dusted the air like snow.",
    # Action / high-arousal
    "The car exploded through the barrier at ninety miles per hour. The driver "
    "wrenched the wheel, tyres screaming against asphalt, narrowly avoiding the "
    "truck that had jackknifed across all four lanes.",
    # Reward / social reward combined
    "The crowd erupted when her name was announced as the winner. Her teammates "
    "rushed the stage, lifting her onto their shoulders. She raised the trophy "
    "and the stadium lights blazed gold.",
    # Calm / low-arousal baseline
    "The library was quiet at midday. Dust motes drifted in the pale light "
    "filtering through tall windows. Someone turned a page. Outside, a pigeon "
    "landed on the sill and regarded the readers without curiosity.",
    # Marketing / persuasive (high-activation — matches campaign content)
    "Introducing the revolutionary platform that transforms how enterprises make "
    "decisions. Our AI-powered analytics deliver 10x faster insights with 99.7% "
    "accuracy. Join 500 Fortune 500 companies already seeing results. Start your "
    "free trial today and experience the future of business intelligence.",
    # Policy / PSA (formal persuasion — common campaign type)
    "New research confirms that childhood vaccination reduces hospitalization rates "
    "by 94% and prevents an estimated 4 million deaths annually worldwide. The CDC "
    "recommends all children receive the updated schedule. Talk to your pediatrician "
    "about protecting your family today.",
    # Product launch / tech announcement
    "We are excited to announce the next generation of our flagship product. With "
    "breakthrough performance improvements, seamless integration, and an entirely "
    "redesigned user experience, this release sets a new standard for the industry. "
    "Available now for early access customers.",
    # Crisis communication
    "A critical security vulnerability has been discovered in our authentication "
    "system affecting all users who logged in between March 1 and March 15. We have "
    "patched the issue and are requiring all users to reset their passwords immediately. "
    "No financial data was compromised.",
    # Motivational / inspirational
    "Every great achievement begins with the decision to try. You have within you "
    "right now everything you need to overcome every obstacle, break every record, "
    "and accomplish more than you ever dreamed possible. The only limits are the "
    "ones you accept.",
]


class Normalizer:
    """Maintain a baseline distribution and convert raw activations to 0-100 scores.

    Uses z-score normalization with sigmoid mapping for continuous scoring
    that works well even with small baselines (as few as 5-10 texts).

    Attributes
    ----------
    _baseline : dict[str, list[float]]
        Per-dimension lists of raw activation values from reference texts.
    """

    def __init__(self) -> None:
        self._baseline: dict[str, list[float]] = {dim: [] for dim in DIMENSIONS}

    # ------------------------------------------------------------------
    # Baseline management
    # ------------------------------------------------------------------

    def update_baseline(self, activations: dict[str, float]) -> None:
        """Add one observation to the baseline distribution.

        Parameters
        ----------
        activations:
            Raw ROI activation dict (output of :func:`roi_extractor.extract_roi_activations`).
            Unknown keys are ignored; missing dimensions default to 0.
        """
        for dim in DIMENSIONS:
            value = activations.get(dim, 0.0)
            self._baseline[dim].append(float(value))

    def baseline_size(self) -> int:
        """Return the number of observations in the baseline."""
        sizes = [len(v) for v in self._baseline.values()]
        return min(sizes) if sizes else 0

    def clear_baseline(self) -> None:
        """Remove all baseline observations."""
        for dim in DIMENSIONS:
            self._baseline[dim].clear()

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def normalize(self, activations: dict[str, float]) -> dict[str, float]:
        """Convert raw activations to 0-100 scores.

        Uses z-score normalization with sigmoid mapping when the baseline has
        at least 2 observations, otherwise falls back to within-batch
        min-max — which for a single value defaults to 50.0.

        Parameters
        ----------
        activations:
            Raw ROI activation dict.

        Returns
        -------
        dict[str, float]
            Per-dimension scores clamped to [0.0, 100.0].
        """
        return self._normalize_batch([activations])[0]

    def normalize_batch(self, activations_list: list[dict[str, float]]) -> list[dict[str, float]]:
        """Normalize a batch of raw activation dicts.

        Parameters
        ----------
        activations_list:
            List of raw ROI activation dicts.

        Returns
        -------
        list[dict[str, float]]
            Corresponding list of 0-100 score dicts.
        """
        return self._normalize_batch(activations_list)

    def _normalize_batch(
        self, activations_list: list[dict[str, float]]
    ) -> list[dict[str, float]]:
        """Internal batch normalizer.

        Strategy: z-score normalization with sigmoid mapping.
        For each dimension, compute z = (x - mean) / std from the baseline,
        then map through sigmoid to get a continuous 0-100 score.
        """
        n_items = len(activations_list)
        if n_items == 0:
            return []

        has_baseline = self.baseline_size() >= 2
        results: list[dict[str, float]] = [{} for _ in range(n_items)]

        for dim in DIMENSIONS:
            batch_values = np.array(
                [float(act.get(dim, 0.0)) for act in activations_list], dtype=np.float64
            )

            if has_baseline:
                baseline_arr = np.array(self._baseline[dim], dtype=np.float64)
                scores = _zscore_sigmoid_vectorized(
                    batch_values, baseline_arr, spread=_SPREAD_FACTOR,
                ) * 100.0
            else:
                # Fallback: within-batch min-max when no baseline exists.
                # For a single item this produces 50.0 (midpoint).
                logger.warning(
                    "No baseline available for '%s'; using within-batch min-max.", dim
                )
                batch_min = batch_values.min()
                batch_max = batch_values.max()
                span = batch_max - batch_min
                if span == 0.0:
                    scores = np.full(n_items, 50.0)
                else:
                    scores = (batch_values - batch_min) / span * 100.0

            # Clamp to [0, 100]
            scores = np.clip(scores, 0.0, 100.0)

            for i, score in enumerate(scores):
                results[i][dim] = round(float(score), 1)

        return results


def _zscore_sigmoid_vectorized(
    values: np.ndarray,
    distribution: np.ndarray,
    spread: float = 1.5,
) -> np.ndarray:
    """Map values to [0, 1] via z-score normalization + sigmoid.

    For each value x:
        z = (x - mean(distribution)) / std(distribution)
        score = sigmoid(z * spread)

    This produces continuous scores that work well with any baseline size.
    The sigmoid naturally maps the full real line to (0, 1), so values
    far above or below the baseline still get differentiated (rather than
    clamping to 0 or 100).

    Parameters
    ----------
    values:
        Array of raw activation values to score.
    distribution:
        Baseline distribution (from reference texts).
    spread:
        Controls score sensitivity.  Higher = more sensitive to small
        deviations from the mean.  1.5 maps +/-2 std to ~5-95.

    Returns
    -------
    np.ndarray
        Scores in (0, 1) for each value.
    """
    n = len(distribution)
    if n == 0:
        return np.full(len(values), 0.5)

    mu = np.mean(distribution)
    sigma = np.std(distribution)

    if sigma < 1e-12:
        # All baseline values are identical; fall back to sign-based scoring
        # where values above the baseline get > 0.5 and below get < 0.5.
        sigma = max(abs(mu) * 0.1, 1e-8)

    z = (values - mu) / sigma
    # Sigmoid: 1 / (1 + exp(-z * spread))
    scores = 1.0 / (1.0 + np.exp(-z * spread))
    return scores


# Module-level singleton used by the FastAPI app
_normalizer = Normalizer()


def get_normalizer() -> Normalizer:
    """Return the module-level Normalizer singleton."""
    return _normalizer


def build_baseline_from_model(model, scorer_fn) -> None:
    """Populate the baseline using REFERENCE_TEXTS and the loaded model.

    This is called once after model load.  Failures for individual texts are
    logged and skipped rather than raising, so a partial baseline is always
    better than no baseline.

    Parameters
    ----------
    model:
        Loaded ``TribeModel`` instance.
    scorer_fn:
        Callable ``(text, model) -> np.ndarray`` — typically
        :func:`scoring.text_scorer.score_text`.
    """
    from scoring.roi_extractor import extract_roi_activations  # local import to avoid circular

    normalizer = get_normalizer()
    logger.info(
        "Seeding baseline with %d reference texts...", len(REFERENCE_TEXTS)
    )
    n_ok = 0
    for i, text in enumerate(REFERENCE_TEXTS):
        try:
            vertex_activations = scorer_fn(text, model)
            activations = extract_roi_activations(vertex_activations)
            normalizer.update_baseline(activations)
            n_ok += 1
            logger.debug("Reference text %d/%d scored OK.", i + 1, len(REFERENCE_TEXTS))
        except Exception as exc:
            logger.warning(
                "Failed to score reference text %d/%d: %s -- skipping.",
                i + 1,
                len(REFERENCE_TEXTS),
                exc,
            )
    logger.info(
        "Baseline seeded with %d/%d reference texts.", n_ok, len(REFERENCE_TEXTS)
    )
