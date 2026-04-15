"""
Campaign CRUD endpoints for the A.R.C Studio API.

Provides POST/GET/DELETE operations for campaigns via the CampaignStore.
Phase 2 A.1 adds POST /campaigns/upload for audio seed files.
"""

import asyncio
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from orchestrator.api.progress import get_or_create_queue
from orchestrator.api.schemas import (
    AudioUploadResponse,
    CampaignCreateRequest,
    CampaignListResponse,
    CampaignResponse,
)
from orchestrator.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["campaigns"])


# Read-ahead chunk size when streaming the upload to disk / counting bytes.
_UPLOAD_CHUNK_BYTES = 1 * 1024 * 1024  # 1 MiB


def _measure_audio_duration_seconds(path: Path) -> float:
    """Measure actual audio duration using soundfile (libsndfile).

    Per Phase 2 A.1 requirements: duration MUST be measured, not inferred
    from metadata. soundfile reads the file header and validates frame
    counts against the real data, so it is a reliable measurement for
    WAV/FLAC/OGG. For MP3 the scipy-bundled libsndfile falls back to
    mutagen-style header inspection -- still vastly more reliable than
    trusting client-reported metadata.

    Raises ValueError if the file cannot be decoded or duration is non-positive.
    """
    import soundfile as sf

    try:
        info = sf.info(str(path))
    except Exception as exc:  # noqa: BLE001 -- any libsndfile error is a bad file
        raise ValueError(f"Unable to decode audio file: {exc}") from exc

    if info.samplerate <= 0 or info.frames <= 0:
        raise ValueError("Audio file has zero duration")

    duration = float(info.frames) / float(info.samplerate)
    if duration <= 0:
        raise ValueError("Audio file has zero duration")
    return duration


@router.post("/campaigns/upload", response_model=AudioUploadResponse)
async def upload_audio(
    request: Request,
    file: UploadFile = File(...),
) -> AudioUploadResponse:
    """
    Accept an audio seed file for Phase 2 A.1 audio campaigns.

    Validations (server-side):
    - Extension must be one of the configured allowed types (default: wav/mp3/flac/ogg).
    - File size <= AUDIO_MAX_BYTES (default 10 MB).
    - Measured duration <= AUDIO_MAX_DURATION_SECONDS (default 60s).

    Stores the file as `<AUDIO_UPLOAD_DIR>/<uuid4><ext>` and returns the absolute
    path the UI can then pass to POST /api/campaigns as `media_path`.
    """
    # ── Extension check (case-insensitive) ──────────────────────────────────
    original_name = file.filename or ""
    ext = Path(original_name).suffix.lower()
    allowed = tuple(e.lower() for e in settings.audio_allowed_extensions)
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file extension '{ext or '(none)'}'. "
                f"Allowed: {', '.join(allowed)}"
            ),
        )

    upload_dir = settings.audio_upload_dir_absolute
    upload_dir.mkdir(parents=True, exist_ok=True)

    dest_path = upload_dir / f"{uuid.uuid4()}{ext}"
    size_limit = settings.audio_max_bytes
    total_bytes = 0

    try:
        # Stream to disk so we don't buffer huge uploads in memory and can
        # enforce the size limit cheaply.
        with dest_path.open("wb") as out:
            while True:
                chunk = await file.read(_UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > size_limit:
                    # Stop reading and reject.
                    out.close()
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"File too large: exceeds {size_limit} bytes "
                            f"({size_limit // (1024 * 1024)} MB) limit"
                        ),
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        # Best-effort cleanup on unexpected I/O failure.
        dest_path.unlink(missing_ok=True)
        logger.exception("Upload write failed")
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    if total_bytes == 0:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Empty file")

    # ── Duration check (measured, per spec) ─────────────────────────────────
    try:
        duration = _measure_audio_duration_seconds(dest_path)
    except ValueError as exc:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400, detail=f"Invalid audio file: {exc}"
        ) from exc

    max_duration = settings.audio_max_duration_seconds
    if duration > max_duration:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Audio too long: {duration:.2f}s exceeds "
                f"{max_duration:.0f}s limit"
            ),
        )

    logger.info(
        "Accepted audio upload: %s (%.2fs, %d bytes) -> %s",
        original_name, duration, total_bytes, dest_path,
    )

    return AudioUploadResponse(
        media_path=str(dest_path.resolve()),
        duration_seconds=duration,
        size_bytes=total_bytes,
    )


@router.post("/campaigns", response_model=CampaignResponse, status_code=201)
async def create_campaign(request: Request, body: CampaignCreateRequest):
    """
    Create a new campaign. Per D-10: single POST with all config.
    If auto_start=True, launches campaign execution in background.
    """
    store = request.app.state.campaign_store
    campaign = await store.create_campaign(body)

    if body.auto_start:
        # Per Pitfall 4: Create queue BEFORE launching background task
        queue = get_or_create_queue(request.app, campaign.id)

        async def progress_callback(event: dict):
            await queue.put(event)

        async def _run_background(app, cid: str):
            runner = app.state.campaign_runner
            try:
                await runner.run_campaign(
                    campaign_id=cid,
                    progress_callback=progress_callback,
                )
            except Exception as e:
                logger.error("Background campaign %s failed: %s", cid, e)
                await queue.put({"event": "campaign_error", "campaign_id": cid, "error": "Campaign failed — check server logs"})
            finally:
                app.state.running_tasks.pop(cid, None)

        task = asyncio.create_task(_run_background(request.app, campaign.id))
        request.app.state.running_tasks[campaign.id] = task
        logger.info("Campaign %s launched as background task", campaign.id)

    return campaign


@router.get("/campaigns", response_model=CampaignListResponse)
async def list_campaigns(request: Request):
    """List all campaigns ordered by creation date (newest first)."""
    store = request.app.state.campaign_store
    return await store.list_campaigns()


@router.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(request: Request, campaign_id: str):
    """Get a campaign with all iterations and analyses."""
    store = request.app.state.campaign_store
    campaign = await store.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
    return campaign


@router.delete("/campaigns/{campaign_id}", status_code=204)
async def delete_campaign(request: Request, campaign_id: str):
    """Delete a campaign and all associated data (cascade).

    Phase 2 A.1: when the campaign was created with `media_type='audio'`,
    also unlink the uploaded audio file. Missing files are logged, not
    crashed on -- the DB delete still proceeds.
    """
    store = request.app.state.campaign_store

    # Look up media info BEFORE deleting (cascade wipes the row).
    media = await store.get_campaign_media(campaign_id)

    deleted = await store.delete_campaign(campaign_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    # Best-effort cleanup of the audio file. Non-fatal on failure.
    if media is not None:
        media_type, media_path = media
        if media_type == "audio" and media_path:
            try:
                p = Path(media_path)
                if p.exists():
                    p.unlink()
                    logger.info("Deleted audio file for campaign %s: %s", campaign_id, p)
                else:
                    logger.warning(
                        "Audio file for campaign %s not found on disk (already removed?): %s",
                        campaign_id, media_path,
                    )
            except OSError as exc:
                logger.warning(
                    "Failed to delete audio file %s for campaign %s: %s",
                    media_path, campaign_id, exc,
                )

    return None
