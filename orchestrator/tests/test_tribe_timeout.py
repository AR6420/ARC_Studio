"""
Tests for Phase 2 B.1: TRIBE v2 text chunking and timeout improvements.

Covers:
- _chunk_text() sentence-boundary splitting, clause splitting, hard splitting
- score_text() merge behavior via weighted average
- is_pseudo_score semantics (True only when ALL chunks fail)
- Orchestrator-side chunk-aware timeout calculation
"""

import math
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from orchestrator.clients.tribe_client import (
    CHUNK_SIZE_WORDS,
    PER_CHUNK_TIMEOUT_BUDGET,
    SCORE_TIMEOUT_FLOOR,
    TIMEOUT_OVERHEAD,
    _timeout_for_batch,
    _timeout_for_text,
)

# Import TRIBE scorer chunking logic.  These live in a separate venv
# (Python 3.11), so we import carefully and skip if unavailable.
try:
    from tribe_scorer.scoring.text_scorer import (
        FSAVERAGE5_N_VERTICES,
        _chunk_text,
        _split_long_sentence,
        score_text,
    )

    HAS_TRIBE_SCORER = True
except ImportError:
    HAS_TRIBE_SCORER = False

needs_tribe = pytest.mark.skipif(
    not HAS_TRIBE_SCORER,
    reason="tribe_scorer package not available in this Python environment",
)


# ---------------------------------------------------------------------------
# _chunk_text() tests
# ---------------------------------------------------------------------------


@needs_tribe
class TestChunkText:
    """Tests for sentence-boundary text chunking."""

    def test_short_text_no_chunking(self):
        """A text with fewer words than max_words returns a single chunk."""
        text = "This is a short sentence. It has very few words."
        chunks = _chunk_text(text, max_words=250)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_exact_boundary_no_chunking(self):
        """A text with exactly max_words returns a single chunk."""
        words = ["word"] * 50
        text = " ".join(words) + "."
        chunks = _chunk_text(text, max_words=50)
        assert len(chunks) == 1

    def test_splits_on_sentence_boundaries(self):
        """Long text splits on sentence-ending punctuation."""
        s1 = "First sentence has several words in it."
        s2 = "Second sentence also has several words."
        s3 = "Third sentence completes the text here."
        text = f"{s1} {s2} {s3}"
        # Each sentence is ~7-8 words; set max_words=10 to force splits.
        chunks = _chunk_text(text, max_words=10)
        assert len(chunks) >= 2
        # All original words must be present across chunks.
        all_words = " ".join(chunks).split()
        assert len(all_words) == len(text.split())

    def test_greedy_packing(self):
        """Sentences that fit together are packed into one chunk."""
        s1 = "Short."
        s2 = "Also short."
        s3 = "This is a much longer sentence with many more words in it."
        text = f"{s1} {s2} {s3}"
        # s1 + s2 = 3 words, fits in 15.  s3 = 11 words, fits in 15.
        # But s1+s2+s3 = 14, also fits in 15.
        chunks = _chunk_text(text, max_words=15)
        assert len(chunks) == 1

    def test_question_marks_are_sentence_boundaries(self):
        """Question marks are treated as sentence boundaries."""
        text = "Is this a question? Yes it is. Another question here?"
        chunks = _chunk_text(text, max_words=5)
        assert len(chunks) >= 2

    def test_exclamation_marks_are_sentence_boundaries(self):
        """Exclamation marks are treated as sentence boundaries."""
        text = "Wow! That is amazing! I cannot believe it!"
        chunks = _chunk_text(text, max_words=4)
        assert len(chunks) >= 2

    def test_oversized_sentence_splits_on_clauses(self):
        """A sentence exceeding max_words splits on comma/semicolon."""
        text = (
            "This is a very long sentence with a first clause, "
            "followed by a second clause, "
            "and then a third clause that keeps going."
        )
        chunks = _chunk_text(text, max_words=8)
        assert len(chunks) >= 2
        # All words preserved.
        all_words = " ".join(chunks).split()
        assert len(all_words) == len(text.split())

    def test_hard_split_on_word_boundaries(self):
        """A clause with no internal punctuation is hard-split on words."""
        # 20 words with no punctuation at all.
        text = " ".join(f"word{i}" for i in range(20)) + "."
        chunks = _chunk_text(text, max_words=7)
        assert len(chunks) >= 2
        all_words = " ".join(chunks).split()
        # Should contain all 20 words (the period is attached to last word).
        assert len(all_words) >= 20

    def test_empty_string_returns_single_chunk(self):
        """Edge case: whitespace-only text after strip would be caught by
        score_text, but _chunk_text itself returns the input."""
        chunks = _chunk_text("Hello.", max_words=250)
        assert len(chunks) == 1

    def test_preserves_all_content(self):
        """Chunking must not lose any words."""
        text = (
            "The quick brown fox jumps over the lazy dog. "
            "Pack my box with five dozen liquor jugs. "
            "How vexingly quick daft zebras jump. "
            "The five boxing wizards jump quickly."
        )
        chunks = _chunk_text(text, max_words=12)
        reassembled_words = " ".join(chunks).split()
        original_words = text.split()
        assert len(reassembled_words) == len(original_words)


# ---------------------------------------------------------------------------
# _split_long_sentence() tests
# ---------------------------------------------------------------------------


@needs_tribe
class TestSplitLongSentence:
    def test_splits_on_commas(self):
        sentence = "one two three, four five six, seven eight nine"
        result = _split_long_sentence(sentence, max_words=4)
        assert len(result) >= 2

    def test_hard_split_no_punctuation(self):
        sentence = " ".join(f"w{i}" for i in range(15))
        result = _split_long_sentence(sentence, max_words=5)
        assert len(result) == 3
        for chunk in result:
            assert len(chunk.split()) <= 5


# ---------------------------------------------------------------------------
# score_text() chunked scoring and merge tests
# ---------------------------------------------------------------------------


@needs_tribe
class TestScoreTextChunking:
    """Tests for chunked scoring with mocked TRIBE model."""

    def _make_mock_model(self, *, fail_chunks=None):
        """Return a mock TribeModel that produces deterministic predictions.

        Parameters
        ----------
        fail_chunks : set[int] | None
            Zero-based chunk indices that should raise an exception.
        """
        fail_chunks = fail_chunks or set()
        call_count = {"n": 0}

        model = MagicMock()

        def fake_get_events(text_path=None, **kw):
            import pandas as pd

            return pd.DataFrame(
                [{"type": "Word", "start": 0, "duration": 1, "timeline": "default"}]
            )

        def fake_predict(events, verbose=False):
            idx = call_count["n"]
            call_count["n"] += 1
            if idx in fail_chunks:
                raise RuntimeError(f"Simulated failure on chunk {idx}")
            # Return (n_segments, n_vertices) with a distinct pattern per chunk
            # so we can verify the weighted merge.
            preds = np.full(
                (1, FSAVERAGE5_N_VERTICES), fill_value=float(idx + 1), dtype=np.float32
            )
            return preds, None

        model.get_events_dataframe = fake_get_events
        model.predict = fake_predict
        return model

    def test_short_text_single_chunk(self):
        """Texts under max_words score as a single chunk."""
        model = self._make_mock_model()
        text = "A short text with a few words."
        result, is_pseudo = score_text(text, model, max_words=250, per_chunk_timeout=60)
        assert not is_pseudo
        assert result.shape == (FSAVERAGE5_N_VERTICES,)
        # Single chunk idx=0 → fill_value=1.0
        np.testing.assert_allclose(result, 1.0, atol=1e-6)

    def test_multi_chunk_weighted_merge(self):
        """Multi-chunk texts produce a word-count-weighted average."""
        model = self._make_mock_model()
        # Two sentences, each ~5 words → 2 chunks at max_words=6.
        text = "First chunk has five words. Second chunk has five words."
        result, is_pseudo = score_text(text, model, max_words=6, per_chunk_timeout=60)
        assert not is_pseudo
        assert result.shape == (FSAVERAGE5_N_VERTICES,)
        # Chunk 0 → 1.0, chunk 1 → 2.0.  Equal word counts → mean = 1.5.
        np.testing.assert_allclose(result, 1.5, atol=0.2)

    def test_all_chunks_fail_returns_pseudo(self):
        """When ALL chunks fail, is_pseudo is True."""
        model = self._make_mock_model(fail_chunks={0, 1})
        text = "First sentence here. Second sentence here."
        result, is_pseudo = score_text(text, model, max_words=4, per_chunk_timeout=60)
        assert is_pseudo
        assert result.shape == (FSAVERAGE5_N_VERTICES,)

    def test_partial_failure_returns_real(self):
        """When some chunks fail but at least one succeeds, is_pseudo is False."""
        model = self._make_mock_model(fail_chunks={0})
        text = "First sentence fails. Second sentence succeeds."
        result, is_pseudo = score_text(text, model, max_words=4, per_chunk_timeout=60)
        assert not is_pseudo
        assert result.shape == (FSAVERAGE5_N_VERTICES,)

    def test_is_pseudo_false_when_one_of_three_fails(self):
        """Partial scoring: 2/3 succeed → is_pseudo is False."""
        model = self._make_mock_model(fail_chunks={1})
        text = "Chunk one works. Chunk two fails. Chunk three works."
        result, is_pseudo = score_text(text, model, max_words=4, per_chunk_timeout=60)
        assert not is_pseudo

    def test_empty_text_raises(self):
        """Empty text raises ValueError."""
        model = self._make_mock_model()
        with pytest.raises(ValueError, match="non-empty"):
            score_text("", model, max_words=250, per_chunk_timeout=60)

    def test_whitespace_only_raises(self):
        """Whitespace-only text raises ValueError."""
        model = self._make_mock_model()
        with pytest.raises(ValueError, match="non-empty"):
            score_text("   \n  ", model, max_words=250, per_chunk_timeout=60)


# ---------------------------------------------------------------------------
# Orchestrator timeout calculation tests
# ---------------------------------------------------------------------------


class TestTimeoutCalculation:
    """Tests for chunk-aware HTTP timeout in tribe_client.py."""

    def test_short_text_gets_floor_timeout(self):
        """A 100-word text (1 chunk) gets at least the floor timeout."""
        text = " ".join(["word"] * 100)
        timeout = _timeout_for_text(text)
        assert timeout >= SCORE_TIMEOUT_FLOOR

    def test_long_text_scales_with_chunks(self):
        """A 600-word text (3 chunks at 250) gets a larger timeout."""
        text = " ".join(["word"] * 600)
        timeout = _timeout_for_text(text)
        expected_chunks = math.ceil(600 / CHUNK_SIZE_WORDS)
        expected = expected_chunks * PER_CHUNK_TIMEOUT_BUDGET + TIMEOUT_OVERHEAD
        # Should be at least the chunk-based budget (may be higher due to floor).
        assert timeout >= expected

    def test_very_long_text_exceeds_floor(self):
        """A 2000-word text produces a timeout above the floor."""
        text = " ".join(["word"] * 2000)
        timeout = _timeout_for_text(text)
        expected_chunks = math.ceil(2000 / CHUNK_SIZE_WORDS)
        chunk_budget = expected_chunks * PER_CHUNK_TIMEOUT_BUDGET + TIMEOUT_OVERHEAD
        assert timeout == chunk_budget
        assert timeout > SCORE_TIMEOUT_FLOOR

    def test_batch_timeout_sums_per_text(self):
        """Batch timeout is the sum of individual text timeouts."""
        texts = [
            " ".join(["word"] * 100),
            " ".join(["word"] * 500),
        ]
        batch_t = _timeout_for_batch(texts)
        individual_sum = sum(_timeout_for_text(t) for t in texts)
        assert batch_t == individual_sum

    def test_empty_batch(self):
        """Empty batch returns zero timeout."""
        assert _timeout_for_batch([]) == 0.0

    def test_single_word_text(self):
        """A single-word text still gets a valid timeout."""
        timeout = _timeout_for_text("hello")
        assert timeout >= SCORE_TIMEOUT_FLOOR
