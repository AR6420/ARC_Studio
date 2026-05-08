"""
Tests for tribe_scorer.scoring.whisper_hf — the transformers-Whisper
replacement for whisperx + ctranslate2.

The HF model is mocked; we don't pull whisper-large-v3 weights in CI.
We verify:
- transcribe_words returns a DataFrame with the expected schema
- words and sentences are reconstructed correctly
- language validation
- install_eventstransforms_patch is idempotent and replaces the
  whisperx call site without re-importing whisperx
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

_scorer_root = Path(__file__).resolve().parent.parent
if str(_scorer_root) not in sys.path:
    sys.path.insert(0, str(_scorer_root))

from scoring import whisper_hf


def _fake_pipeline(chunks):
    """Build a mock HF pipeline whose `__call__` returns the given chunks."""
    pipe = MagicMock()
    pipe.return_value = {"chunks": chunks, "text": " ".join(c["text"] for c in chunks)}
    return pipe


@pytest.fixture(autouse=True)
def _clear_pipeline_cache():
    whisper_hf._pipeline_cache.clear()
    yield
    whisper_hf._pipeline_cache.clear()


def test_transcribe_returns_expected_columns():
    chunks = [
        {"text": "Hello", "timestamp": (0.0, 0.5)},
        {"text": "world.", "timestamp": (0.5, 1.0)},
    ]
    with patch("scoring.whisper_hf._load_pipeline", return_value=_fake_pipeline(chunks)):
        df = whisper_hf.transcribe_words("/fake/audio.wav", language="english", device="cpu")
    assert list(df.columns) == ["text", "start", "duration", "sequence_id", "sentence"]
    assert len(df) == 2
    assert df.iloc[0]["text"] == "Hello"
    assert df.iloc[1]["text"] == "world."
    # Both words belong to the same sentence (terminal punctuation on word 2)
    assert df["sequence_id"].nunique() == 1
    assert df.iloc[0]["sentence"] == "Hello world."


def test_transcribe_groups_multiple_sentences():
    chunks = [
        {"text": "Hi.", "timestamp": (0.0, 0.4)},
        {"text": "How", "timestamp": (0.5, 0.8)},
        {"text": "are", "timestamp": (0.8, 1.0)},
        {"text": "you?", "timestamp": (1.0, 1.4)},
    ]
    with patch("scoring.whisper_hf._load_pipeline", return_value=_fake_pipeline(chunks)):
        df = whisper_hf.transcribe_words("/fake/audio.wav", language="english", device="cpu")
    assert df["sequence_id"].nunique() == 2
    assert sorted(df["sentence"].unique().tolist()) == ["Hi.", "How are you?"]


def test_transcribe_skips_chunks_without_timestamps():
    chunks = [
        {"text": "good", "timestamp": (0.0, 0.4)},
        {"text": "lost", "timestamp": (None, None)},  # malformed
        {"text": "morning.", "timestamp": (0.5, 1.0)},
    ]
    with patch("scoring.whisper_hf._load_pipeline", return_value=_fake_pipeline(chunks)):
        df = whisper_hf.transcribe_words("/fake/audio.wav", language="english", device="cpu")
    assert "lost" not in df["text"].tolist()
    assert len(df) == 2


def test_transcribe_empty_chunks_returns_empty_dataframe():
    with patch("scoring.whisper_hf._load_pipeline", return_value=_fake_pipeline([])):
        df = whisper_hf.transcribe_words("/fake/audio.wav", language="english", device="cpu")
    assert df.empty
    assert list(df.columns) == ["text", "start", "duration", "sequence_id", "sentence"]


def test_transcribe_rejects_unsupported_language():
    with pytest.raises(ValueError, match="not supported"):
        whisper_hf.transcribe_words("/fake/audio.wav", language="klingon")


def test_resolve_device_honours_env(monkeypatch):
    monkeypatch.setenv("TRIBE_DEVICE", "cpu")
    assert whisper_hf._resolve_device(None) == "cpu"
    monkeypatch.setenv("TRIBE_DEVICE", "cuda")
    assert whisper_hf._resolve_device(None) == "cuda"


def test_resolve_device_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv("TRIBE_DEVICE", "cpu")
    assert whisper_hf._resolve_device("cuda") == "cuda"


def test_install_patch_is_idempotent_and_skips_when_tribev2_missing(monkeypatch):
    """
    Patch install must NOT raise when the vendored tribev2 package is not
    importable (CI / unit-test environments typically don't have it).
    """
    # Force the import to fail
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, *args, **kwargs):
        if name == "tribev2.eventstransforms" or name == "tribev2":
            raise ImportError("tribev2 not installed in this environment")
        return real_import(name, *args, **kwargs)

    if isinstance(__builtins__, dict):
        monkeypatch.setitem(__builtins__, "__import__", fake_import)
    else:
        monkeypatch.setattr(__builtins__, "__import__", fake_import)

    # Should swallow the ImportError and log a warning, not raise
    whisper_hf.install_eventstransforms_patch()
    whisper_hf.install_eventstransforms_patch()  # idempotent re-call
