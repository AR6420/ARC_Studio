"""
Progress streaming and time estimation endpoints.

SSE endpoint (D-09): GET /api/campaigns/{id}/progress
Estimate endpoint (OPT-05): POST /api/estimate
Queue management: asyncio.Queue per campaign on app.state.progress_queues
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException
from sse_starlette import EventSourceResponse

from orchestrator.api.schemas import EstimateRequest, EstimateResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["progress"])

# ── Queue management ──────────────────────────────────────────────────────

TERMINAL_EVENTS = {"campaign_complete", "campaign_error"}


def get_or_create_queue(app, campaign_id: str) -> asyncio.Queue:
    """Get or create an asyncio.Queue for campaign progress events.
    Per Pitfall 4: Queue must be created BEFORE launching background task."""
    if not hasattr(app.state, "progress_queues"):
        app.state.progress_queues = {}
    if campaign_id not in app.state.progress_queues:
        app.state.progress_queues[campaign_id] = asyncio.Queue()
    return app.state.progress_queues[campaign_id]


def cleanup_queue(app, campaign_id: str) -> None:
    """Evict a campaign's live progress queue AND its history buffer.

    Called once from the background-task completion path (authoritative) and,
    defensively, from the SSE generator's finally ONLY when the campaign is no
    longer running. It must NOT run on an ordinary mid-run SSE disconnect (tab
    refresh, network blip) — doing so orphaned the queue while the producer
    kept writing to it, and every later reconnect 404'd for the rest of the run.

    Evicting the history here too (previously left forever) closes the
    unbounded progress_history leak: one entry per campaign that never shrank.
    """
    if hasattr(app.state, "progress_queues"):
        app.state.progress_queues.pop(campaign_id, None)
    if hasattr(app.state, "progress_history"):
        app.state.progress_history.pop(campaign_id, None)


# ── SSE endpoint ──────────────────────────────────────────────────────────


@router.get("/campaigns/{campaign_id}/progress")
async def campaign_progress(request: Request, campaign_id: str):
    """
    SSE endpoint for real-time campaign progress.
    Per D-09: GET /api/campaigns/{id}/progress.
    Per D-10: Per-step events within each iteration.
    """
    queues = getattr(request.app.state, "progress_queues", {})
    queue = queues.get(campaign_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="No active campaign run")

    # Phase 5 session 6: replay buffered history first so a mid-run
    # connect (refresh, late tab open) sees the stages that already
    # fired. The history is appended-to alongside every queue.put in
    # api/campaigns.py.
    history = getattr(request.app.state, "progress_history", {}).get(
        campaign_id, []
    )
    # Snapshot at connect time — copy() so subsequent appends during
    # iteration don't mutate what we yield.
    replay = list(history)

    async def event_generator():
        try:
            for event in replay:
                event_type = event.get("event", "message")
                if not event.get("timestamp"):
                    event["timestamp"] = datetime.now(timezone.utc).isoformat()
                yield {
                    "event": event_type,
                    "data": json.dumps(event),
                }
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    event_type = event.get("event", "message")
                    # Stamp wallclock at emission so the UI's
                    # formatEventTime() has a parseable ISO timestamp.
                    # The campaign_runner payloads omit timestamp; without
                    # this the UI renders "Invalid Date" on every row.
                    if not event.get("timestamp"):
                        event["timestamp"] = datetime.now(timezone.utc).isoformat()
                    yield {
                        "event": event_type,
                        "data": json.dumps(event),
                    }
                    if event_type in TERMINAL_EVENTS:
                        break
                except asyncio.TimeoutError:
                    yield {"comment": "keepalive"}
        except asyncio.CancelledError:
            pass
        finally:
            # Only evict if the campaign is no longer running. A mid-run
            # disconnect (refresh/blip) must leave the queue intact so a
            # reconnect keeps working (the background task is still producing
            # into it). The authoritative eviction happens in the campaign's
            # background-task completion path.
            running = getattr(request.app.state, "running_tasks", {})
            task = running.get(campaign_id)
            if task is None or task.done():
                cleanup_queue(request.app, campaign_id)

    return EventSourceResponse(event_generator())


# ── Estimate endpoint ─────────────────────────────────────────────────────

BASELINE_MINUTES_PER_VARIANT = 20.0  # ~20 min per variant on RTX 5070 Ti (TRIBE + MiroFish)


@router.post("/estimate", response_model=EstimateResponse)
async def estimate_time(body: EstimateRequest):
    """
    Return pre-run time estimate for a campaign configuration.

    Formula: variants_per_iteration * max_iterations * per-variant minutes,
    where the per-variant cost scales with agent_count (the MiroFish simulation
    is the agent-count-sensitive step). The BASELINE_MINUTES_PER_VARIANT figure
    is calibrated for the 40-agent default; a 200-agent campaign takes
    materially longer, so agent_count MUST feed the estimate (previously it was
    accepted and silently ignored, giving identical ETAs for 20 vs 200 agents).
    """
    variants_per_iteration = 2  # B.1 default
    agent_scale = max(body.agent_count, 1) / 40.0  # 40 agents = baseline
    per_variant = BASELINE_MINUTES_PER_VARIANT * agent_scale
    estimated = variants_per_iteration * body.max_iterations * per_variant
    return EstimateResponse(
        estimated_minutes=round(estimated, 1),
        agent_count=body.agent_count,
        max_iterations=body.max_iterations,
        formula=(
            f"{variants_per_iteration} variants * {body.max_iterations} iters * "
            f"{BASELINE_MINUTES_PER_VARIANT} min * (agents {body.agent_count}/40) "
            f"= {round(estimated, 1)} min"
        ),
    )
