"""
Phase 2 A.1 — Backend audio upload and campaign routing tests.

Covers:
- POST /api/campaigns/upload validation (extension, size, duration)
- Campaign creation with media_type='audio'
- DELETE cleanup of uploaded audio files
- Regression: text-only campaigns still work with defaults
"""

from __future__ import annotations

import io
import wave
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient

from orchestrator.clients.mirofish_client import MirofishClient
from orchestrator.clients.tribe_client import TribeClient
from orchestrator.config import settings
from orchestrator.storage.campaign_store import CampaignStore
from orchestrator.storage.database import Database


VALID_SEED_CONTENT = (
    "This is a comprehensive product launch announcement for our new AI-powered "
    "content optimization platform that helps marketing teams create better content. "
    "It uses neural response prediction and social simulation to iteratively improve messaging."
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_wav_bytes(duration_seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generate a synthetic mono PCM-16 WAV file as bytes."""
    n_samples = int(duration_seconds * sample_rate)
    # Low-amplitude sine wave — content doesn't matter, only header validity.
    t = np.arange(n_samples, dtype=np.float32) / sample_rate
    audio = (0.1 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    pcm16 = (audio * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())
    return buf.getvalue()


def _create_test_app() -> FastAPI:
    """Create a test app without lifespan (state set up manually by fixture)."""
    from orchestrator.api.campaigns import router as campaigns_router

    application = FastAPI(title="Test orchestrator", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(campaigns_router, prefix="/api")
    return application


@pytest.fixture
def isolated_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the global settings.audio_upload_dir at a temp directory for the test."""
    target = tmp_path / "uploads"
    target.mkdir(parents=True, exist_ok=True)
    # Override the attribute directly on the singleton so both the config
    # property and the endpoint pick it up.
    monkeypatch.setattr(settings, "audio_upload_dir", str(target))
    return target


@pytest.fixture
async def client(tmp_path: Path, isolated_upload_dir: Path):
    """Async test client with manually initialized app state + isolated DB + upload dir."""
    db_path = str(tmp_path / "test_audio.db")

    app = _create_test_app()

    db = Database(db_path)
    await db.connect()

    tribe_http = httpx.AsyncClient(base_url="http://localhost:8001")
    mirofish_http = httpx.AsyncClient(base_url="http://localhost:5000")

    app.state.db = db
    app.state.campaign_store = CampaignStore(db)
    app.state.tribe_client = TribeClient(tribe_http)
    app.state.mirofish_client = MirofishClient(mirofish_http)
    app.state.claude_client = MagicMock()
    app.state.running_tasks = {}
    app.state.progress_queues = {}
    app.state.tribe_http = tribe_http
    app.state.mirofish_http = mirofish_http

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c

    await tribe_http.aclose()
    await mirofish_http.aclose()
    await db.close()


# ── Upload validation tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_valid_wav_returns_media_path(
    client: AsyncClient, isolated_upload_dir: Path
):
    """Valid small WAV upload returns 200 with media_path pointing to a real file on disk."""
    wav_bytes = _make_wav_bytes(duration_seconds=1.0)
    files = {"file": ("seed.wav", wav_bytes, "audio/wav")}

    resp = await client.post("/api/campaigns/upload", files=files)
    assert resp.status_code == 200, resp.text

    payload = resp.json()
    assert "media_path" in payload
    assert "duration_seconds" in payload
    assert "size_bytes" in payload

    assert payload["size_bytes"] == len(wav_bytes)
    assert 0.9 < payload["duration_seconds"] < 1.2

    stored = Path(payload["media_path"])
    assert stored.exists(), "Uploaded file should be persisted on disk"
    assert stored.parent == isolated_upload_dir.resolve()
    assert stored.suffix == ".wav"
    # Filename is UUID4 + original extension — UUID4 canonical format is 36 chars.
    assert len(stored.stem) == 36


@pytest.mark.asyncio
async def test_upload_pdf_returns_400(client: AsyncClient):
    """Unsupported extension (.pdf) should be rejected with 400."""
    files = {"file": ("doc.pdf", b"%PDF-1.4 fake pdf content", "application/pdf")}
    resp = await client.post("/api/campaigns/upload", files=files)
    assert resp.status_code == 400
    assert "extension" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_oversize_file_returns_400(
    client: AsyncClient, isolated_upload_dir: Path
):
    """Files larger than the size cap (default 10 MB) should be rejected.

    We deliberately overshoot the cap — the endpoint streams chunks and bails
    mid-write as soon as the running total exceeds the limit.
    """
    # 15 MB of zeros is sufficient; we never need a valid audio stream because
    # size validation runs before duration measurement.
    oversize = b"\x00" * (15 * 1024 * 1024)
    files = {"file": ("huge.wav", oversize, "audio/wav")}

    resp = await client.post("/api/campaigns/upload", files=files)
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()

    # Ensure no partial file was left behind.
    remaining = list(isolated_upload_dir.iterdir())
    assert remaining == [], f"Oversize upload left residue: {remaining}"


@pytest.mark.asyncio
async def test_upload_too_long_audio_returns_400(
    client: AsyncClient, isolated_upload_dir: Path
):
    """A >60s WAV should fail duration validation."""
    # 61 seconds at 8 kHz mono = 61 * 8000 * 2 = 976 KB — well under the size cap.
    wav_bytes = _make_wav_bytes(duration_seconds=61.0, sample_rate=8000)
    files = {"file": ("long.wav", wav_bytes, "audio/wav")}

    resp = await client.post("/api/campaigns/upload", files=files)
    assert resp.status_code == 400
    assert "too long" in resp.json()["detail"].lower()

    # Ensure the long file was cleaned up.
    remaining = list(isolated_upload_dir.iterdir())
    assert remaining == [], f"Over-duration upload left residue: {remaining}"


# ── Campaign routing tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_campaign_with_audio_stores_media_type(
    client: AsyncClient, isolated_upload_dir: Path
):
    """POSTing a campaign with media_type='audio' persists the media fields."""
    wav_bytes = _make_wav_bytes(duration_seconds=0.5)
    files = {"file": ("voice.wav", wav_bytes, "audio/wav")}
    upload_resp = await client.post("/api/campaigns/upload", files=files)
    assert upload_resp.status_code == 200
    media_path = upload_resp.json()["media_path"]

    body = {
        "seed_content": "",  # empty seed_content is allowed for audio campaigns
        "prediction_question": "How will this audio resonate with listeners?",
        "demographic": "tech_professionals",
        "agent_count": 40,
        "max_iterations": 4,
        "auto_start": False,
        "media_type": "audio",
        "media_path": media_path,
    }

    create_resp = await client.post("/api/campaigns", json=body)
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    assert created["media_type"] == "audio"
    assert created["media_path"] == media_path
    campaign_id = created["id"]

    # Round-trip GET ensures the fields survive SELECT.
    get_resp = await client.get(f"/api/campaigns/{campaign_id}")
    assert get_resp.status_code == 200
    got = get_resp.json()
    assert got["media_type"] == "audio"
    assert got["media_path"] == media_path


@pytest.mark.asyncio
async def test_delete_campaign_removes_audio_file(
    client: AsyncClient, isolated_upload_dir: Path
):
    """Deleting an audio campaign also unlinks its uploaded audio file."""
    wav_bytes = _make_wav_bytes(duration_seconds=0.5)
    files = {"file": ("voice.wav", wav_bytes, "audio/wav")}
    upload_resp = await client.post("/api/campaigns/upload", files=files)
    assert upload_resp.status_code == 200
    media_path = upload_resp.json()["media_path"]
    on_disk = Path(media_path)
    assert on_disk.exists()

    body = {
        "seed_content": "",
        "prediction_question": "How will this audio resonate with listeners?",
        "demographic": "tech_professionals",
        "auto_start": False,
        "media_type": "audio",
        "media_path": media_path,
    }
    create_resp = await client.post("/api/campaigns", json=body)
    assert create_resp.status_code == 201
    campaign_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/campaigns/{campaign_id}")
    assert del_resp.status_code == 204

    assert not on_disk.exists(), "Audio file should be removed after campaign deletion"


@pytest.mark.asyncio
async def test_delete_campaign_with_missing_audio_file_is_non_fatal(
    client: AsyncClient, isolated_upload_dir: Path
):
    """If the audio file is already gone at delete time, DELETE still returns 204."""
    wav_bytes = _make_wav_bytes(duration_seconds=0.5)
    files = {"file": ("voice.wav", wav_bytes, "audio/wav")}
    upload_resp = await client.post("/api/campaigns/upload", files=files)
    media_path = upload_resp.json()["media_path"]

    body = {
        "seed_content": "",
        "prediction_question": "How will this audio resonate with listeners?",
        "demographic": "tech_professionals",
        "auto_start": False,
        "media_type": "audio",
        "media_path": media_path,
    }
    create_resp = await client.post("/api/campaigns", json=body)
    campaign_id = create_resp.json()["id"]

    # Remove the file out-of-band to simulate a missing upload.
    Path(media_path).unlink()
    assert not Path(media_path).exists()

    del_resp = await client.delete(f"/api/campaigns/{campaign_id}")
    assert del_resp.status_code == 204  # still succeeds


# ── Regression: text-only path unchanged ────────────────────────────────────


@pytest.mark.asyncio
async def test_text_only_campaign_still_works(client: AsyncClient):
    """Existing text-only campaigns (no media_type field) must continue to work."""
    body = {
        "seed_content": VALID_SEED_CONTENT,
        "prediction_question": "How will tech professionals respond to this product launch?",
        "demographic": "tech_professionals",
        "agent_count": 40,
        "max_iterations": 4,
        "auto_start": False,
    }
    create_resp = await client.post("/api/campaigns", json=body)
    assert create_resp.status_code == 201
    created = create_resp.json()
    # Defaults preserve backward compatibility.
    assert created["media_type"] == "text"
    assert created["media_path"] is None
    assert created["seed_content"] == VALID_SEED_CONTENT

    get_resp = await client.get(f"/api/campaigns/{created['id']}")
    assert get_resp.status_code == 200
    got = get_resp.json()
    assert got["media_type"] == "text"
    assert got["media_path"] is None
