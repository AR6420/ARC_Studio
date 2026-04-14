"""Tests for B.1 text chunking in the TRIBE v2 scoring pipeline.

These tests verify the ACTUAL chunking execution path — not just config loading.
They mock the TRIBE model to avoid GPU dependency, but exercise the real
_chunk_text(), _score_single_chunk(), and score_text() code paths.
"""

import logging
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# The text_scorer module lives inside tribe_scorer/scoring/ which is outside
# the normal orchestrator test path.  We import it directly.
import sys
from pathlib import Path

_scorer_root = Path(__file__).resolve().parent.parent
if str(_scorer_root) not in sys.path:
    sys.path.insert(0, str(_scorer_root))

from scoring.text_scorer import (
    FSAVERAGE5_N_VERTICES,
    _chunk_text,
    _pseudo_score_from_text,
    score_text,
)


# ---------------------------------------------------------------------------
# _chunk_text unit tests
# ---------------------------------------------------------------------------


class TestChunkText:
    def test_short_text_not_chunked(self):
        text = "This is a short text with only ten words in it."
        chunks = _chunk_text(text, max_words=250)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_exact_boundary(self):
        words = ["word"] * 250
        text = " ".join(words)
        chunks = _chunk_text(text, max_words=250)
        assert len(chunks) == 1

    def test_one_word_over_boundary(self):
        words = ["word"] * 251
        text = " ".join(words)
        chunks = _chunk_text(text, max_words=250)
        assert len(chunks) == 2
        assert len(chunks[0].split()) == 250
        assert len(chunks[1].split()) == 1

    def test_large_text_multiple_chunks(self):
        words = ["word"] * 800
        text = " ".join(words)
        chunks = _chunk_text(text, max_words=250)
        assert len(chunks) == 4
        # First 3 chunks should be exactly 250 words
        for c in chunks[:3]:
            assert len(c.split()) == 250
        # Last chunk gets the remainder
        assert len(chunks[3].split()) == 50

    def test_preserves_all_words(self):
        words = [f"w{i}" for i in range(573)]
        text = " ".join(words)
        chunks = _chunk_text(text, max_words=200)
        reconstructed = " ".join(chunks)
        assert reconstructed == text

    def test_empty_text(self):
        chunks = _chunk_text("", max_words=250)
        assert len(chunks) == 1
        assert chunks[0] == ""


# ---------------------------------------------------------------------------
# score_text chunking integration tests (mocked model)
# ---------------------------------------------------------------------------


def _make_fake_preds(n_segments=10):
    """Return a (n_segments, n_vertices) array mimicking TRIBE output."""
    return np.random.default_rng(42).normal(size=(n_segments, FSAVERAGE5_N_VERTICES)).astype(np.float32)


def _make_mock_model():
    """Create a mock TribeModel whose predict() returns valid activations."""
    model = MagicMock()
    model.get_events_dataframe.return_value = MagicMock()
    model.predict.return_value = (_make_fake_preds(), MagicMock())
    return model


class TestScoreTextChunking:
    def test_short_text_no_chunking(self):
        """Text under the chunk limit should NOT trigger chunking."""
        model = _make_mock_model()
        short = " ".join(["hello"] * 50)

        result, is_pseudo = score_text(short, model, max_words_per_chunk=250, per_chunk_timeout=60)

        assert not is_pseudo
        assert result.shape == (FSAVERAGE5_N_VERTICES,)
        # Model should be called exactly once (no chunking)
        assert model.get_events_dataframe.call_count == 1

    def test_long_text_triggers_chunking(self):
        """Text over the chunk limit MUST trigger chunking with multiple model calls."""
        model = _make_mock_model()
        long_text = " ".join(["hello"] * 600)  # 600 words > 250 chunk limit

        result, is_pseudo = score_text(long_text, model, max_words_per_chunk=250, per_chunk_timeout=60)

        assert not is_pseudo
        assert result.shape == (FSAVERAGE5_N_VERTICES,)
        # 600 words / 250 per chunk = 3 chunks → 3 model calls
        assert model.get_events_dataframe.call_count == 3

    def test_chunking_logs_chunk_marker(self, caplog):
        """The [CHUNK] log marker MUST appear for chunked texts."""
        model = _make_mock_model()
        long_text = " ".join(["word"] * 500)

        with caplog.at_level(logging.INFO, logger="scoring.text_scorer"):
            score_text(long_text, model, max_words_per_chunk=250, per_chunk_timeout=60)

        chunk_logs = [r for r in caplog.records if "[CHUNK]" in r.message]
        assert len(chunk_logs) >= 3, (
            f"Expected at least 3 [CHUNK] log lines for a 500-word text chunked at 250, "
            f"got {len(chunk_logs)}: {[r.message for r in chunk_logs]}"
        )

    def test_chunking_log_contains_word_counts(self, caplog):
        """The summary [CHUNK] log must contain word counts and times."""
        model = _make_mock_model()
        long_text = " ".join(["word"] * 500)

        with caplog.at_level(logging.INFO, logger="scoring.text_scorer"):
            score_text(long_text, model, max_words_per_chunk=250, per_chunk_timeout=60)

        summary_logs = [r for r in caplog.records if "Variant scored in" in r.message]
        assert len(summary_logs) == 1, f"Expected exactly 1 summary log, got {len(summary_logs)}"
        msg = summary_logs[0].message
        assert "2 chunks" in msg
        assert "[250, 250]" in msg

    def test_no_chunk_marker_for_short_text(self, caplog):
        """Short text must NOT produce [CHUNK] logs."""
        model = _make_mock_model()
        short = " ".join(["hello"] * 50)

        with caplog.at_level(logging.INFO, logger="scoring.text_scorer"):
            score_text(short, model, max_words_per_chunk=250, per_chunk_timeout=60)

        chunk_logs = [r for r in caplog.records if "[CHUNK]" in r.message]
        assert len(chunk_logs) == 0, f"Short text should not produce [CHUNK] logs: {[r.message for r in chunk_logs]}"

    def test_chunking_disabled_when_zero(self):
        """max_words_per_chunk=0 should disable chunking even for long text."""
        model = _make_mock_model()
        long_text = " ".join(["hello"] * 600)

        result, is_pseudo = score_text(long_text, model, max_words_per_chunk=0, per_chunk_timeout=60)

        assert not is_pseudo
        # Should be a single model call (no chunking)
        assert model.get_events_dataframe.call_count == 1

    def test_partial_chunk_failure_still_returns_real(self):
        """If some chunks fail but at least one succeeds, return real (not pseudo)."""
        model = MagicMock()
        model.get_events_dataframe.return_value = MagicMock()
        # First call succeeds, second raises
        model.predict.side_effect = [
            (_make_fake_preds(), MagicMock()),
            Exception("CUDA OOM"),
            (_make_fake_preds(), MagicMock()),
        ]
        long_text = " ".join(["word"] * 750)  # 3 chunks

        result, is_pseudo = score_text(long_text, model, max_words_per_chunk=250, per_chunk_timeout=60)

        assert not is_pseudo  # At least 2 chunks succeeded
        assert result.shape == (FSAVERAGE5_N_VERTICES,)

    def test_all_chunks_fail_returns_pseudo(self):
        """If ALL chunks fail, fall back to pseudo-score."""
        model = MagicMock()
        model.get_events_dataframe.return_value = MagicMock()
        model.predict.side_effect = Exception("CUDA OOM")
        long_text = " ".join(["word"] * 500)  # 2 chunks

        result, is_pseudo = score_text(long_text, model, max_words_per_chunk=250, per_chunk_timeout=60)

        assert is_pseudo
        assert result.shape == (FSAVERAGE5_N_VERTICES,)

    def test_vram_freed_between_chunks(self):
        """torch.cuda.empty_cache() should be called between chunks."""
        model = _make_mock_model()
        long_text = " ".join(["word"] * 500)  # 2 chunks

        with patch("scoring.text_scorer._try_free_vram") as mock_free:
            score_text(long_text, model, max_words_per_chunk=250, per_chunk_timeout=60)
            # Should be called once per chunk (before each)
            assert mock_free.call_count == 2
