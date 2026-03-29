"""
Campaign CRUD endpoints for the Nexus Sim API.

Provides POST/GET/DELETE operations for campaigns via the CampaignStore.
"""

import asyncio
import logging

from fastapi import APIRouter, Request, HTTPException
from orchestrator.api.schemas import (
    CampaignCreateRequest,
    CampaignResponse,
    CampaignListResponse,
)
from orchestrator.api.progress import get_or_create_queue

logger = logging.getLogger(__name__)
router = APIRouter(tags=["campaigns"])


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
                await queue.put({"event": "campaign_error", "campaign_id": cid, "error": str(e)})
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
    """Delete a campaign and all associated data (cascade)."""
    store = request.app.state.campaign_store
    deleted = await store.delete_campaign(campaign_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
    return None
