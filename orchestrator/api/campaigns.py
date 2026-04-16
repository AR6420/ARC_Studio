"""
Campaign CRUD endpoints for the A.R.C Studio API.

Provides POST/GET/DELETE operations for campaigns via the CampaignStore.
Phase 2 A.1 adds POST /campaigns/upload for audio seed files.
Phase 2 A.2 extends that endpoint to also accept video seed files
(.mp4/.webm/.mov, ≤15s, ≤25 MB, ≤720p — auto-downscaled via ffmpeg if higher).
"""

import asyncio
import logging
import os
import shutil
import subprocess
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


def _ffprobe_video_metadata(path: Path) -> dict:
    """Return ``{'duration': float, 'width': int, 'height': int}`` for a video.

    Raises ValueError if ffprobe is unavailable, the file isn't parseable,
    or there's no video stream. Mirrors tribe_scorer/scoring/video_scorer.py
    so server-side and orchestrator-side validation use the same probe.
    """
    if shutil.which("ffprobe") is None:
        raise ValueError(
            "ffprobe not found on PATH; install ffmpeg/ffprobe to enable video uploads."
        )
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,duration",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1",
                str(path),
            ],
            capture_output=True, text=True, timeout=15, check=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"ffprobe timed out: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            f"ffprobe failed: {exc.stderr.strip()[:200]}"
        ) from exc

    md: dict = {}
    for line in out.stdout.splitlines():
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if not val or val == "N/A":
            continue
        if key in ("width", "height"):
            try:
                md[key] = int(val)
            except ValueError:
                pass
        elif key == "duration":
            try:
                d = float(val)
                if d > 0:
                    md["duration"] = d
            except ValueError:
                pass

    if "width" not in md or "height" not in md:
        raise ValueError("No video stream found (ffprobe returned no width/height)")
    if "duration" not in md or md["duration"] <= 0:
        raise ValueError("Could not determine duration (ffprobe returned no value)")
    return md


def _ffmpeg_downscale_to_height(src: Path, dest: Path, target_height: int) -> None:
    """Use ffmpeg to scale *src* down to *target_height* (preserving aspect ratio).

    Output codec H.264 + AAC for broad compatibility. Width is auto-computed
    via -2 to keep the value even (libx264 requires even dimensions).
    Raises ValueError if ffmpeg fails.
    """
    if shutil.which("ffmpeg") is None:
        raise ValueError(
            "ffmpeg not found on PATH; cannot downscale oversize video."
        )
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(src),
                "-vf", f"scale=-2:{target_height}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                str(dest),
            ],
            capture_output=True, text=True, timeout=120, check=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"ffmpeg downscale timed out: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            f"ffmpeg downscale failed: {exc.stderr.strip()[:300]}"
        ) from exc


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
async def upload_media(
    request: Request,
    file: UploadFile = File(...),
) -> AudioUploadResponse:
    """
    Accept an audio (Phase 2 A.1) or video (Phase 2 A.2) seed file.

    Dispatch is by extension (case-insensitive):
    - Audio (.wav/.mp3/.flac/.ogg): ≤AUDIO_MAX_BYTES, ≤AUDIO_MAX_DURATION_SECONDS
    - Video (.mp4/.webm/.mov):      ≤VIDEO_MAX_BYTES, ≤VIDEO_MAX_DURATION_SECONDS,
                                    height ≤VIDEO_MAX_RESOLUTION_HEIGHT
                                    (auto-downscaled via ffmpeg if higher)

    Stores the file under AUDIO_UPLOAD_DIR (shared with audio — UUID filenames
    keep them distinct) and returns the absolute path the UI passes to
    POST /api/campaigns as `media_path`. The response carries `media_type`
    so the UI knows what to render.
    """
    # ── Extension check (case-insensitive) ──────────────────────────────────
    original_name = file.filename or ""
    ext = Path(original_name).suffix.lower()
    audio_allowed = tuple(e.lower() for e in settings.audio_allowed_extensions)
    video_allowed = tuple(e.lower() for e in settings.video_allowed_extensions)

    if ext in audio_allowed:
        media_type: str = "audio"
        size_limit = settings.audio_max_bytes
    elif ext in video_allowed:
        media_type = "video"
        size_limit = settings.video_max_bytes
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file extension '{ext or '(none)'}'. "
                f"Allowed: {', '.join(audio_allowed + video_allowed)}"
            ),
        )

    upload_dir = settings.audio_upload_dir_absolute
    upload_dir.mkdir(parents=True, exist_ok=True)

    dest_path = upload_dir / f"{uuid.uuid4()}{ext}"
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
        dest_path.unlink(missing_ok=True)
        logger.exception("Upload write failed")
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    if total_bytes == 0:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Empty file")

    if media_type == "audio":
        return await _finalize_audio_upload(dest_path, original_name, total_bytes)
    return await _finalize_video_upload(dest_path, original_name, total_bytes)


async def _finalize_audio_upload(
    dest_path: Path, original_name: str, total_bytes: int
) -> AudioUploadResponse:
    """Validate measured duration and return the response for an audio upload."""
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
        media_type="audio",
    )


async def _finalize_video_upload(
    dest_path: Path, original_name: str, total_bytes: int
) -> AudioUploadResponse:
    """Validate duration + resolution, downscale to ≤720p height when needed."""
    try:
        meta = _ffprobe_video_metadata(dest_path)
    except ValueError as exc:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400, detail=f"Invalid video file: {exc}"
        ) from exc

    duration = float(meta["duration"])
    width = int(meta["width"])
    height = int(meta["height"])

    max_duration = settings.video_max_duration_seconds
    if duration > max_duration:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Video too long: {duration:.2f}s exceeds "
                f"{max_duration:.0f}s limit"
            ),
        )

    target_h = settings.video_max_resolution_height
    downscaled = False
    final_size = total_bytes

    if height > target_h:
        # Downscale via ffmpeg to fit the height limit. We always re-encode to
        # .mp4 (libx264) for downstream decoder compatibility; the original
        # extension is preserved on disk.
        scaled_path = dest_path.with_suffix(dest_path.suffix + ".scaled.mp4")
        try:
            _ffmpeg_downscale_to_height(dest_path, scaled_path, target_h)
        except ValueError as exc:
            dest_path.unlink(missing_ok=True)
            scaled_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Video resolution {width}x{height} exceeds {target_h}p "
                    f"and downscale failed: {exc}"
                ),
            ) from exc

        # Replace original with downscaled output and re-probe for accurate metadata.
        try:
            os.replace(scaled_path, dest_path)
            meta = _ffprobe_video_metadata(dest_path)
            width = int(meta["width"])
            height = int(meta["height"])
            duration = float(meta["duration"])
            final_size = dest_path.stat().st_size
            downscaled = True
        except Exception as exc:  # noqa: BLE001
            dest_path.unlink(missing_ok=True)
            scaled_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=500, detail=f"Downscale post-processing failed: {exc}"
            ) from exc

    logger.info(
        "Accepted video upload: %s (%.2fs, %dx%d, %d bytes, downscaled=%s) -> %s",
        original_name, duration, width, height, final_size, downscaled, dest_path,
    )
    return AudioUploadResponse(
        media_path=str(dest_path.resolve()),
        duration_seconds=duration,
        size_bytes=final_size,
        media_type="video",
        width=width,
        height=height,
        downscaled=downscaled,
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

    # Best-effort cleanup of the uploaded media file. Non-fatal on failure.
    if media is not None:
        media_type, media_path = media
        if media_type in ("audio", "video") and media_path:
            try:
                p = Path(media_path)
                if p.exists():
                    p.unlink()
                    logger.info(
                        "Deleted %s file for campaign %s: %s",
                        media_type, campaign_id, p,
                    )
                else:
                    logger.warning(
                        "%s file for campaign %s not found on disk (already removed?): %s",
                        media_type.capitalize(), campaign_id, media_path,
                    )
            except OSError as exc:
                logger.warning(
                    "Failed to delete %s file %s for campaign %s: %s",
                    media_type, media_path, campaign_id, exc,
                )

    return None
