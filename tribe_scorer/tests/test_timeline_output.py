"""
Tests for the per-window timeline preservation added in Phase 1.

Covers:
- roi_extractor.extract_roi_activations_per_window: shape + content
- text_scorer.score_text_with_timeline: returns the unreduced preds
  alongside the aggregated activations
- legacy score_text path is not regressed (still 2-tuple return)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

_scorer_root = Path(__file__).resolve().parent.parent
if str(_scorer_root) not in sys.path:
    sys.path.insert(0, str(_scorer_root))

from scoring.roi_extractor import (
    N_VERTICES_TOTAL,
    extract_roi_activations,
    extract_roi_activations_per_window,
)
from scoring.text_scorer import (
    FSAVERAGE5_N_VERTICES,
    score_text,
    score_text_with_timeline,
)


ROI_NAMES = {
    "attention_capture",
    "emotional_resonance",
    "memory_encoding",
    "reward_response",
    "threat_detection",
    "cognitive_load",
    "social_relevance",
}


def _fake_preds(n_windows: int) -> np.ndarray:
    """Deterministic per-window 2-D predictions of shape (n_windows, 20484)."""
    rng = np.random.default_rng(42)
    return rng.normal(0.0, 0.05, size=(n_windows, N_VERTICES_TOTAL)).astype(np.float32)


def _make_mock_model(n_windows: int = 5):
    model = MagicMock()
    model.get_events_dataframe.return_value = MagicMock()
    model.predict.return_value = (_fake_preds(n_windows), MagicMock())
    return model


# ── extract_roi_activations_per_window ──────────────────────────────────────


class TestPerWindowExtraction:
    def test_returns_seven_channels(self):
        preds = _fake_preds(10)
        timeline = extract_roi_activations_per_window(preds)
        assert set(timeline.keys()) == ROI_NAMES

    def test_each_channel_length_matches_n_windows(self):
        preds = _fake_preds(7)
        timeline = extract_roi_activations_per_window(preds)
        for name, series in timeline.items():
            assert len(series) == 7, f"{name}: got len={len(series)}"

    def test_per_window_mean_matches_full_aggregate(self):
        """The mean of the per-window series should equal the aggregate."""
        preds = _fake_preds(4)
        timeline = extract_roi_activations_per_window(preds)
        aggregate = extract_roi_activations(preds.mean(axis=0))
        for name in ROI_NAMES:
            np.testing.assert_allclose(
                np.mean(timeline[name]),
                aggregate[name],
                rtol=1e-4,
                err_msg=f"channel {name} per-window mean != aggregate",
            )

    def test_rejects_1d_input(self):
        with pytest.raises(ValueError, match="2-D"):
            extract_roi_activations_per_window(np.zeros(N_VERTICES_TOTAL, dtype=np.float32))

    def test_rejects_too_few_vertices(self):
        with pytest.raises(ValueError, match="vertices"):
            extract_roi_activations_per_window(np.zeros((3, 100), dtype=np.float32))


# ── score_text_with_timeline ────────────────────────────────────────────────


class TestScoreTextWithTimeline:
    def test_returns_three_tuple_with_preds(self):
        model = _make_mock_model(n_windows=4)
        avg, is_pseudo, preds = score_text_with_timeline(
            "hello world", model, max_words_per_chunk=0, per_chunk_timeout=60,
        )
        assert avg.shape == (FSAVERAGE5_N_VERTICES,)
        assert is_pseudo is False
        assert preds is not None
        assert preds.shape == (4, FSAVERAGE5_N_VERTICES)

    def test_chunked_path_concatenates_preds(self):
        model = _make_mock_model(n_windows=3)
        long_text = " ".join(["word"] * 600)  # 3 chunks at 250-word limit
        avg, is_pseudo, preds = score_text_with_timeline(
            long_text, model, max_words_per_chunk=250, per_chunk_timeout=60,
        )
        assert is_pseudo is False
        # 3 chunks × 3 windows each = 9 rows concatenated
        assert preds.shape == (9, FSAVERAGE5_N_VERTICES)

    def test_pseudo_path_returns_none_for_preds(self):
        model = MagicMock()
        model.get_events_dataframe.return_value = MagicMock()
        model.predict.side_effect = Exception("CUDA OOM")
        avg, is_pseudo, preds = score_text_with_timeline(
            "hello", model, max_words_per_chunk=0, per_chunk_timeout=60,
        )
        assert is_pseudo is True
        assert avg.shape == (FSAVERAGE5_N_VERTICES,)
        assert preds is None


# ── legacy score_text not regressed ─────────────────────────────────────────


class TestLegacyScoreText:
    def test_still_returns_two_tuple(self):
        model = _make_mock_model(n_windows=3)
        result = score_text("hello world", model, max_words_per_chunk=0, per_chunk_timeout=60)
        assert isinstance(result, tuple)
        assert len(result) == 2
