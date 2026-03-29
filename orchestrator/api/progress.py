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
    """Remove queue for a completed/failed campaign. Per Pitfall 2: prevent memory leak."""
    if hasattr(app.state, "progress_queues"):
        app.state.progress_queues.pop(campaign_id, None)


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

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    event_type = event.get("event", "message")
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
            cleanup_queue(request.app, campaign_id)

    return EventSourceResponse(event_generator())


# ── Estimate endpoint ─────────────────────────────────────────────────────

BASELINE_MINUTES_PER_ITERATION = 3.0  # for 40 agents


@router.post("/estimate", response_model=EstimateResponse)
async def estimate_time(body: EstimateRequest):
    """
    Return pre-run time estimate for a campaign configuration.
    Per OPT-05: POST /api/estimate.
    Per D-11: Formula-based estimate.
    Formula: (agent_count / 40) * max_iterations * 3.0 minutes
    """
    estimated = (body.agent_count / 40) * body.max_iterations * BASELINE_MINUTES_PER_ITERATION
    return EstimateResponse(
        estimated_minutes=round(estimated, 1),
        agent_count=body.agent_count,
        max_iterations=body.max_iterations,
        formula=f"({body.agent_count}/40) * {body.max_iterations} * {BASELINE_MINUTES_PER_ITERATION} = {round(estimated, 1)} minutes",
    )
