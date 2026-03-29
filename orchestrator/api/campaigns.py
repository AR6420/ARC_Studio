"""
Campaign CRUD endpoints for the Nexus Sim API.

Provides POST/GET/DELETE operations for campaigns via the CampaignStore.
"""

import logging

from fastapi import APIRouter, Request, HTTPException
from orchestrator.api.schemas import (
    CampaignCreateRequest,
    CampaignResponse,
    CampaignListResponse,
)

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
        # Background execution will be wired when campaign_runner is available on app.state
        # For now, just create the campaign; execution is triggered separately
        logger.info(
            "Campaign %s created with auto_start=True (execution wired in Plan 07)",
            campaign.id,
        )

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
