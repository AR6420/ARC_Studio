"""
FastAPI application factory for the A.R.C Studio Orchestrator.

Creates the app with lifespan resource management (database, HTTP clients),
CORS middleware for the Vite dev server, and router mounting.

Usage:
    # Via uvicorn (uses module-level app instance):
    uvicorn orchestrator.api:app --port 8000

    # Programmatic:
    from orchestrator.api import create_app
    app = create_app()
"""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from orchestrator.config import settings

logger = logging.getLogger(__name__)


def _refresh_litellm_api_key() -> None:
    """
    Read the current OAuth token from Claude credentials and update the .env
    ANTHROPIC_API_KEY so LiteLLM can authenticate with Anthropic.

    MiroFish uses LiteLLM as its LLM proxy. LiteLLM reads ANTHROPIC_API_KEY
    from its environment at container startup. If the key is empty or expired,
    ALL MiroFish simulations silently fail (ontology generation returns 401).

    This runs at orchestrator startup to keep the key fresh. After updating
    .env, the LiteLLM container must be recreated to pick up the new value.
    """
    import json
    import os
    import subprocess
    from pathlib import Path

    cred_path = os.path.expanduser(settings.claude_credentials_path)
    env_path = Path(__file__).parent.parent.parent / ".env"

    # Step 1: Read current OAuth token
    try:
        with open(cred_path) as f:
            creds = json.load(f)
        token = creds.get("claudeAiOauth", {}).get("accessToken", "")
    except Exception as e:
        logger.warning("Could not read Claude credentials for LiteLLM refresh: %s", e)
        return

    if not token:
        logger.warning(
            "No OAuth token in %s -- LiteLLM will not have a valid API key. "
            "MiroFish simulations will fail.",
            cred_path,
        )
        return

    # Step 2: Check if .env already has this token (avoid unnecessary restarts)
    try:
        current_key = ""
        with open(env_path) as f:
            for line in f:
                if line.startswith("ANTHROPIC_API_KEY="):
                    current_key = line.strip().split("=", 1)[1]
                    break
        if current_key == token:
            logger.info("LiteLLM API key is already current -- no refresh needed")
            return
    except Exception:
        pass  # .env may not exist yet

    # Step 3: Update .env
    try:
        with open(env_path) as f:
            lines = f.readlines()
        found = False
        with open(env_path, "w") as f:
            for line in lines:
                if line.startswith("ANTHROPIC_API_KEY="):
                    f.write(f"ANTHROPIC_API_KEY={token}\n")
                    found = True
                else:
                    f.write(line)
            if not found:
                f.write(f"ANTHROPIC_API_KEY={token}\n")
        logger.info("Updated ANTHROPIC_API_KEY in .env")
    except Exception as e:
        logger.warning("Could not update .env with fresh API key: %s", e)
        return

    # Step 4: Recreate LiteLLM container to pick up the new key
    try:
        compose_dir = str(Path(__file__).parent.parent.parent)
        result = subprocess.run(
            ["docker", "compose", "up", "-d", "litellm"],
            cwd=compose_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger.info("LiteLLM container recreated with fresh API key")
        else:
            logger.warning(
                "docker compose up -d litellm failed (rc=%d): %s",
                result.returncode,
                result.stderr[:200],
            )
    except FileNotFoundError:
        logger.warning(
            "docker command not found -- cannot auto-refresh LiteLLM. "
            "Run scripts/refresh-env.sh --restart manually."
        )
    except Exception as e:
        logger.warning("Could not restart LiteLLM container: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage shared resources: database, HTTP clients, Claude client.
    Per FastAPI best practices: use lifespan instead of deprecated on_event.

    Imports are deferred to avoid circular imports (campaign_store -> schemas
    -> orchestrator.api package).
    """
    # Deferred imports to break circular dependency
    from orchestrator.storage.database import Database
    from orchestrator.storage.campaign_store import CampaignStore
    from orchestrator.clients.tribe_client import TribeClient
    from orchestrator.clients.mirofish_client import MirofishClient
    from orchestrator.clients.claude_client import ClaudeClient
    from orchestrator.engine.variant_generator import VariantGenerator
    from orchestrator.engine.tribe_scorer import TribeScoringPipeline
    from orchestrator.engine.mirofish_runner import MirofishRunner
    from orchestrator.engine.result_analyzer import ResultAnalyzer
    from orchestrator.engine.campaign_runner import CampaignRunner
    from orchestrator.engine.report_generator import ReportGenerator

    # Startup -- refresh LiteLLM API key from Claude credentials
    _refresh_litellm_api_key()

    db = Database(str(settings.database_path_absolute))
    await db.connect()

    tribe_http = httpx.AsyncClient(base_url=settings.tribe_scorer_url, timeout=300.0)
    mirofish_http = httpx.AsyncClient(base_url=settings.mirofish_url, timeout=300.0)

    app.state.db = db
    app.state.campaign_store = CampaignStore(db)
    app.state.tribe_client = TribeClient(tribe_http)
    app.state.mirofish_client = MirofishClient(
        mirofish_http, litellm_url=settings.litellm_url
    )
    app.state.claude_client = ClaudeClient()
    app.state.tribe_http = tribe_http
    app.state.mirofish_http = mirofish_http

    # Construct engine components for CampaignRunner
    variant_gen = VariantGenerator(app.state.claude_client)
    tribe_scoring = TribeScoringPipeline(app.state.tribe_client)
    mirofish_runner_instance = MirofishRunner(app.state.mirofish_client)
    result_analyzer = ResultAnalyzer(app.state.claude_client)
    report_generator = ReportGenerator(app.state.claude_client)

    app.state.campaign_runner = CampaignRunner(
        variant_generator=variant_gen,
        tribe_scoring=tribe_scoring,
        mirofish_runner=mirofish_runner_instance,
        result_analyzer=result_analyzer,
        campaign_store=app.state.campaign_store,
        tribe_client=app.state.tribe_client,
        mirofish_client=app.state.mirofish_client,
        report_generator=report_generator,
    )

    # Initialize background task tracking and progress queues
    app.state.running_tasks = {}
    app.state.progress_queues = {}

    logger.info(
        "Orchestrator started — DB at %s, TRIBE at %s, MiroFish at %s",
        settings.database_path_absolute,
        settings.tribe_scorer_url,
        settings.mirofish_url,
    )

    yield

    # Shutdown -- cancel any running campaign tasks first
    for task_id, task in app.state.running_tasks.items():
        if not task.done():
            task.cancel()
            logger.info("Cancelled running task for campaign %s", task_id)
    app.state.running_tasks.clear()
    app.state.progress_queues.clear()

    await tribe_http.aclose()
    await mirofish_http.aclose()
    await db.close()
    logger.info("Orchestrator shutdown complete")


def create_app() -> FastAPI:
    """Factory function to create the FastAPI app."""
    from orchestrator.api.agents import router as agents_router
    from orchestrator.api.campaigns import router as campaigns_router
    from orchestrator.api.health import router as health_router
    from orchestrator.api.progress import router as progress_router
    from orchestrator.api.reports import router as reports_router

    application = FastAPI(
        title="A.R.C Studio Orchestrator",
        description="Content optimization pipeline orchestrating TRIBE v2, MiroFish, and Claude",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS for Vite dev server (per ORCH-01)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )

    # Mount routers
    application.include_router(agents_router, prefix="/api")
    application.include_router(campaigns_router, prefix="/api")
    application.include_router(health_router, prefix="/api")
    application.include_router(progress_router, prefix="/api")
    application.include_router(reports_router, prefix="/api")

    return application


# Module-level app instance for uvicorn
app = create_app()
