"""
Health check and demographics endpoints for the Nexus Sim API.

Provides system health monitoring (pings TRIBE, MiroFish, database)
and demographic preset listing for the UI.
"""

import logging
import time

from fastapi import APIRouter, Request
from orchestrator.api.schemas import (
    HealthResponse,
    ServiceHealth,
    DemographicsResponse,
    DemographicInfo,
)
from orchestrator.prompts.demographic_profiles import list_profiles

logger = logging.getLogger(__name__)
router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """
    Check health of all downstream services.
    Per ORCH-05: pings TRIBE v2, MiroFish, and database.
    """
    tribe_client = request.app.state.tribe_client
    mirofish_client = request.app.state.mirofish_client
    db = request.app.state.db

    # Check TRIBE v2
    tribe_start = time.monotonic()
    tribe_ok = await tribe_client.health_check()
    tribe_latency = (time.monotonic() - tribe_start) * 1000

    # Check MiroFish
    mirofish_start = time.monotonic()
    mirofish_ok = await mirofish_client.health_check()
    mirofish_latency = (time.monotonic() - mirofish_start) * 1000

    # Check Database
    db_start = time.monotonic()
    try:
        await db.conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    db_latency = (time.monotonic() - db_start) * 1000

    return HealthResponse(
        orchestrator="ok",
        tribe_scorer=ServiceHealth(
            status="ok" if tribe_ok else "unavailable",
            latency_ms=round(tribe_latency, 1) if tribe_ok else None,
        ),
        mirofish=ServiceHealth(
            status="ok" if mirofish_ok else "unavailable",
            latency_ms=round(mirofish_latency, 1) if mirofish_ok else None,
        ),
        database=ServiceHealth(
            status="ok" if db_ok else "unavailable",
            latency_ms=round(db_latency, 1) if db_ok else None,
        ),
    )


@router.get("/demographics", response_model=DemographicsResponse)
async def get_demographics():
    """
    Return all demographic presets for the UI dropdown.
    Per ORCH-06: returns preset list from demographic_profiles.py.
    """
    profiles = list_profiles()
    return DemographicsResponse(
        presets=[
            DemographicInfo(key=p["key"], label=p["label"], description=p["description"])
            for p in profiles
        ],
        supports_custom=True,
    )
