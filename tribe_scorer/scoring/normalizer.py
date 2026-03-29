"""Normalize raw ROI activation values to 0-100 scores.

Strategy
--------
The normalizer uses percentile-rank normalization against a baseline
distribution built from diverse reference texts.  For each dimension:

    score = percentile_rank(activation, baseline) * 100

where ``percentile_rank(x, dist)`` is the fraction of baseline values
strictly less than ``x``, multiplied by 100.

If no baseline has been populated yet the normalizer falls back to
within-batch min-max scaling so that every call still returns a useful
range rather than a constant.

Baseline management
-------------------
Call :func:`update_baseline` to add raw activation dicts to the baseline
pool.  The pool is kept in memory and is NOT persisted across restarts by
default.  A typical startup routine would call :func:`score_reference_texts`
once after model load to seed the baseline with 10 diverse texts.

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

# 10 diverse reference texts used to seed the baseline on first startup.
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
]


class Normalizer:
    """Maintain a baseline distribution and convert raw activations to 0-100 scores.

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

        Uses percentile-rank normalization when the baseline has at least one
        observation, otherwise falls back to within-batch (single-item)
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
        """Internal batch normalizer."""
        n_items = len(activations_list)
        if n_items == 0:
            return []

        has_baseline = self.baseline_size() > 0
        results: list[dict[str, float]] = [{} for _ in range(n_items)]

        for dim in DIMENSIONS:
            batch_values = np.array(
                [float(act.get(dim, 0.0)) for act in activations_list], dtype=np.float64
            )

            if has_baseline:
                baseline_arr = np.array(self._baseline[dim], dtype=np.float64)
                scores = _percentile_rank_vectorized(batch_values, baseline_arr) * 100.0
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
                results[i][dim] = float(score)

        return results


def _percentile_rank_vectorized(
    values: np.ndarray, distribution: np.ndarray
) -> np.ndarray:
    """Compute percentile rank for each value in *values* against *distribution*.

    Returns a float array in [0, 1] where:
        0.0 → value is at or below all baseline values
        1.0 → value exceeds all baseline values

    Uses the formula: rank = (# baseline values strictly < x) / n_baseline
    """
    n = len(distribution)
    if n == 0:
        return np.full(len(values), 0.5)
    sorted_dist = np.sort(distribution)
    # searchsorted with side='left' gives the count of elements < x
    ranks = np.searchsorted(sorted_dist, values, side="left").astype(np.float64) / n
    return ranks


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
        "Seeding baseline with %d reference texts…", len(REFERENCE_TEXTS)
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
                "Failed to score reference text %d/%d: %s — skipping.",
                i + 1,
                len(REFERENCE_TEXTS),
                exc,
            )
    logger.info(
        "Baseline seeded with %d/%d reference texts.", n_ok, len(REFERENCE_TEXTS)
    )
