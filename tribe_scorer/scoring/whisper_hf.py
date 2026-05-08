"""
HuggingFace transformers Whisper-large-v3 transcription + word alignment.

Replaces the whisperx + ctranslate2 + faster-whisper stack used by the
vendored TRIBE source. Pure PyTorch — no native CUDA-only kernels — so
it runs on ROCm without source-build gymnastics.

Alignment quality tradeoff: transformers' `return_timestamps="word"` is
based on Whisper's own decoder cross-attention rather than whisperx's
CTC forced alignment. Word boundaries are typically within ~50-100ms of
ground truth (whisperx is ~20-50ms). For TRIBE's window-level scoring
(2-10s windows) this is well within tolerance.

Public surface:

    transcribe_words(audio_path, language="english", device=None)
        -> pd.DataFrame with columns:
           text, start, duration, sequence_id, sentence

The DataFrame shape matches what the original
`ExtractWordsFromAudio._get_transcript_from_audio` produced, so the
patched call site in eventstransforms.py is a drop-in replacement.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

LANGUAGE_CODES = {
    "english": "en",
    "french": "fr",
    "spanish": "es",
    "dutch": "nl",
    "chinese": "zh",
}

DEFAULT_MODEL_ID = "openai/whisper-large-v3"

_pipeline_cache: dict[tuple[str, str], Any] = {}


def _resolve_device(explicit: str | None) -> str:
    """Pick a device string, honouring TRIBE_DEVICE if set."""
    if explicit:
        return explicit
    env = os.environ.get("TRIBE_DEVICE", "").strip().lower()
    if env in {"cpu", "cuda"}:
        return env
    # Defer to torch availability; ROCm presents AMD GPUs as "cuda".
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _load_pipeline(device: str, model_id: str):
    """Cache one ASR pipeline per (model_id, device) tuple."""
    key = (model_id, device)
    cached = _pipeline_cache.get(key)
    if cached is not None:
        return cached

    # Defer import so module import has no heavy cost.
    import torch
    from transformers import pipeline

    # bf16 on accelerators, fp32 on CPU. fp16 is fine on CUDA too but
    # bf16 matches what the rest of TRIBE expects on MI300X / sm_120.
    torch_dtype = torch.bfloat16 if device == "cuda" else torch.float32
    logger.info(
        "Loading Whisper pipeline (model=%s, device=%s, dtype=%s)",
        model_id, device, torch_dtype,
    )

    pipe = pipeline(
        task="automatic-speech-recognition",
        model=model_id,
        torch_dtype=torch_dtype,
        device=device,
        chunk_length_s=30,
        return_timestamps="word",
    )
    _pipeline_cache[key] = pipe
    return pipe


def transcribe_words(
    audio_path: str | Path,
    language: str = "english",
    device: str | None = None,
    model_id: str = DEFAULT_MODEL_ID,
) -> pd.DataFrame:
    """
    Transcribe one audio file and return word-level timing as a DataFrame.

    Columns: text, start, duration, sequence_id, sentence.
    sequence_id groups words that share an utterance/segment so the
    downstream code can reconstruct sentences.
    """
    if language not in LANGUAGE_CODES:
        raise ValueError(f"Language {language!r} not supported")

    audio_path = str(audio_path)
    device = _resolve_device(device)
    pipe = _load_pipeline(device, model_id)

    logger.info("Transcribing %s (lang=%s, device=%s)", audio_path, language, device)
    result = pipe(
        audio_path,
        generate_kwargs={"language": LANGUAGE_CODES[language], "task": "transcribe"},
    )

    chunks = result.get("chunks") or []
    if not chunks:
        logger.warning("Whisper produced no chunks for %s", audio_path)
        return pd.DataFrame(columns=["text", "start", "duration", "sequence_id", "sentence"])

    # Group consecutive words into sentences using terminal punctuation.
    rows: list[dict[str, Any]] = []
    sentence_buf: list[str] = []
    sequence_id = 0
    pending: list[dict[str, Any]] = []

    def flush():
        nonlocal sequence_id, sentence_buf, pending
        if not pending:
            return
        sentence = " ".join(sentence_buf).strip().replace('"', "")
        for row in pending:
            row["sentence"] = sentence
            row["sequence_id"] = sequence_id
            rows.append(row)
        sequence_id += 1
        sentence_buf = []
        pending = []

    for chunk in chunks:
        ts = chunk.get("timestamp") or (None, None)
        start, end = ts if isinstance(ts, (list, tuple)) else (None, None)
        word = (chunk.get("text") or "").strip()
        if not word or start is None or end is None:
            continue
        clean = word.replace('"', "")
        sentence_buf.append(clean)
        pending.append(
            {
                "text": clean,
                "start": float(start),
                "duration": float(max(end - start, 0.0)),
            }
        )
        if word.endswith((".", "!", "?")):
            flush()
    flush()  # tail

    df = pd.DataFrame(rows, columns=["text", "start", "duration", "sequence_id", "sentence"])
    logger.info("Transcribed %d words across %d sentences from %s", len(df), sequence_id, audio_path)
    return df


def install_eventstransforms_patch() -> None:
    """
    Replace the whisperx-based ``_get_transcript_from_audio`` inside
    the vendored TRIBE source with the transformers-Whisper version.

    Idempotent. Called once at TRIBE service startup so the vendored
    package keeps its upstream Meta source unchanged on disk
    (zero submodule pointer churn) while the running process never
    imports whisperx.
    """
    try:
        from tribev2 import eventstransforms as et  # type: ignore
    except ImportError:
        logger.warning(
            "tribev2 not importable; whisperx patch skipped. "
            "This is expected during unit tests that don't load the model."
        )
        return

    if getattr(et.ExtractWordsFromAudio, "_whisperx_patched", False):
        return

    @staticmethod
    def _patched(wav_filename, language: str) -> pd.DataFrame:
        return transcribe_words(wav_filename, language=language)

    et.ExtractWordsFromAudio._get_transcript_from_audio = _patched
    et.ExtractWordsFromAudio._whisperx_patched = True
    logger.info("Installed transformers-Whisper patch on ExtractWordsFromAudio")
