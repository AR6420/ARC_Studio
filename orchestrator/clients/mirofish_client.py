"""
Async HTTP client for the MiroFish social simulation service.

Communicates with the MiroFish Flask backend (default: http://localhost:5000)
via an httpx.AsyncClient passed to the constructor.

Implements the full multi-step async workflow:
  1. POST /api/graph/ontology/generate  (multipart/form-data file upload)
  2. POST /api/graph/build + poll task until complete
  3. POST /api/simulation/create
  4. POST /api/simulation/prepare + poll until ready
  5. POST /api/simulation/start + poll run-status until complete
  6. GET results from multiple endpoints (posts, actions, timeline, agent-stats)

Design decisions:
- Constructor receives httpx.AsyncClient (shared connection pool).
- Polling uses exponential backoff with configurable timeouts.
- Content is sent as multipart/form-data file upload (Pitfall 2 from research).
- Returns None on any failure for graceful degradation (D-05).
"""

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Polling configuration
POLL_INITIAL_INTERVAL = 2.0  # seconds
POLL_MAX_INTERVAL = 10.0  # seconds
POLL_BACKOFF_FACTOR = 1.5
GRAPH_BUILD_TIMEOUT = 300.0  # 5 minutes max for graph build
SIM_PREPARE_TIMEOUT = 300.0  # 5 minutes max for simulation prepare
SIM_RUN_TIMEOUT = 600.0  # 10 minutes max for simulation run


class MirofishClient:
    """
    Async HTTP client for MiroFish social simulation service (port 5000).

    Implements the full multi-step async workflow:
    ontology/generate -> graph/build -> poll -> sim/create -> sim/prepare ->
    poll -> sim/start -> poll -> extract results.
    """

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def health_check(self) -> bool:
        """Check if MiroFish backend is healthy."""
        try:
            resp = await self._client.get("/health", timeout=10.0)
            return resp.status_code == 200
        except Exception as e:
            logger.warning("MiroFish health check failed: %s", e)
            return False

    async def run_simulation(
        self,
        content: str,
        simulation_requirement: str,
        project_name: str,
        max_rounds: int = 30,
    ) -> dict[str, Any] | None:
        """
        Run the full MiroFish simulation workflow for a single content variant.

        Returns raw simulation data dict or None on failure.
        Per D-04: Called sequentially, one variant at a time. Graph is rebuilt
        per variant.

        Steps:
        1. POST /api/graph/ontology/generate (multipart, content as .txt file)
        2. POST /api/graph/build + poll until complete
        3. POST /api/simulation/create
        4. POST /api/simulation/prepare + poll until complete
        5. POST /api/simulation/start + poll until complete
        6. Extract results from multiple endpoints
        """
        try:
            # Step 1: Generate ontology (synchronous response)
            project_id = await self._generate_ontology(
                content, simulation_requirement, project_name
            )
            if not project_id:
                return None

            # Step 2: Build graph (async -- requires polling)
            graph_ok = await self._build_graph(project_id)
            if not graph_ok:
                return None

            # Step 3: Create simulation
            simulation_id = await self._create_simulation(project_id)
            if not simulation_id:
                return None

            # Step 4: Prepare simulation (async -- requires polling)
            prepare_ok = await self._prepare_simulation(simulation_id)
            if not prepare_ok:
                return None

            # Step 5: Start and run simulation (async -- requires polling)
            run_ok = await self._run_simulation(simulation_id, max_rounds)
            if not run_ok:
                return None

            # Step 6: Extract results
            results = await self._extract_results(simulation_id)
            return results

        except Exception as e:
            logger.error("MiroFish simulation failed: %s", e)
            return None

    async def _generate_ontology(
        self, content: str, requirement: str, project_name: str
    ) -> str | None:
        """Step 1: POST /api/graph/ontology/generate with multipart/form-data."""
        try:
            content_bytes = content.encode("utf-8")
            files = {"files": ("content.txt", content_bytes, "text/plain")}
            data = {
                "simulation_requirement": requirement,
                "project_name": project_name,
            }
            resp = await self._client.post(
                "/api/graph/ontology/generate",
                files=files,
                data=data,
                timeout=120.0,
            )
            resp.raise_for_status()
            result = resp.json()
            project_id = result.get("project_id")
            if not project_id:
                logger.error(
                    "MiroFish ontology response missing project_id: %s", result
                )
                return None
            logger.info("MiroFish ontology generated for project %s", project_id)
            return project_id
        except Exception as e:
            logger.error("MiroFish ontology generation failed: %s", e)
            return None

    async def _build_graph(self, project_id: str) -> bool:
        """Step 2: POST /api/graph/build then poll task until complete."""
        try:
            resp = await self._client.post(
                "/api/graph/build",
                json={"project_id": project_id},
                timeout=30.0,
            )
            resp.raise_for_status()
            task_id = resp.json().get("task_id")
            if not task_id:
                logger.error("MiroFish graph build response missing task_id")
                return False
            return await self._poll_task(
                f"/api/graph/task/{task_id}", GRAPH_BUILD_TIMEOUT
            )
        except Exception as e:
            logger.error("MiroFish graph build failed: %s", e)
            return False

    async def _poll_task(self, url: str, timeout: float) -> bool:
        """Poll a MiroFish task URL until status is 'completed' or timeout."""
        elapsed = 0.0
        interval = POLL_INITIAL_INTERVAL
        while elapsed < timeout:
            try:
                resp = await self._client.get(url, timeout=15.0)
                resp.raise_for_status()
                data = resp.json()
                status = data.get("status", "")
                if status == "completed":
                    return True
                if status == "failed":
                    logger.error("MiroFish task failed: %s", data)
                    return False
                logger.debug(
                    "MiroFish task polling: status=%s, progress=%s",
                    status,
                    data.get("progress"),
                )
            except Exception as e:
                logger.warning("MiroFish task poll error: %s", e)
            await asyncio.sleep(interval)
            elapsed += interval
            interval = min(interval * POLL_BACKOFF_FACTOR, POLL_MAX_INTERVAL)
        logger.error("MiroFish task timed out after %.0fs at %s", timeout, url)
        return False

    async def _create_simulation(self, project_id: str) -> str | None:
        """Step 3: POST /api/simulation/create."""
        try:
            resp = await self._client.post(
                "/api/simulation/create",
                json={
                    "project_id": project_id,
                    "enable_twitter": True,
                    "enable_reddit": True,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            sim_id = resp.json().get("simulation_id")
            if not sim_id:
                logger.error(
                    "MiroFish create simulation response missing simulation_id"
                )
                return None
            return sim_id
        except Exception as e:
            logger.error("MiroFish create simulation failed: %s", e)
            return None

    async def _prepare_simulation(self, simulation_id: str) -> bool:
        """Step 4: POST /api/simulation/prepare then poll until ready."""
        try:
            resp = await self._client.post(
                "/api/simulation/prepare",
                json={
                    "simulation_id": simulation_id,
                    "use_llm_for_profiles": True,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("already_prepared"):
                return True
            task_id = data.get("task_id")
            if not task_id:
                logger.error(
                    "MiroFish prepare response missing task_id: %s", data
                )
                return False
            # Poll prepare status via its own endpoint
            elapsed = 0.0
            interval = POLL_INITIAL_INTERVAL
            while elapsed < SIM_PREPARE_TIMEOUT:
                try:
                    status_resp = await self._client.post(
                        "/api/simulation/prepare/status",
                        json={"task_id": task_id},
                        timeout=15.0,
                    )
                    status_resp.raise_for_status()
                    status_data = status_resp.json()
                    if (
                        status_data.get("status") == "completed"
                        or status_data.get("ready")
                    ):
                        return True
                    if status_data.get("status") == "failed":
                        logger.error("MiroFish prepare failed: %s", status_data)
                        return False
                except Exception as e:
                    logger.warning("MiroFish prepare status poll error: %s", e)
                await asyncio.sleep(interval)
                elapsed += interval
                interval = min(interval * POLL_BACKOFF_FACTOR, POLL_MAX_INTERVAL)
            logger.error(
                "MiroFish prepare timed out after %.0fs", SIM_PREPARE_TIMEOUT
            )
            return False
        except Exception as e:
            logger.error("MiroFish prepare simulation failed: %s", e)
            return False

    async def _run_simulation(self, simulation_id: str, max_rounds: int) -> bool:
        """Step 5: POST /api/simulation/start then poll run-status."""
        try:
            resp = await self._client.post(
                "/api/simulation/start",
                json={
                    "simulation_id": simulation_id,
                    "platform": "parallel",
                    "max_rounds": max_rounds,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            # Poll run status
            elapsed = 0.0
            interval = POLL_INITIAL_INTERVAL
            while elapsed < SIM_RUN_TIMEOUT:
                try:
                    status_resp = await self._client.get(
                        f"/api/simulation/{simulation_id}/run-status",
                        timeout=15.0,
                    )
                    status_resp.raise_for_status()
                    data = status_resp.json()
                    runner_status = data.get("runner_status", "")
                    if runner_status == "completed":
                        return True
                    if runner_status == "failed":
                        logger.error("MiroFish simulation run failed: %s", data)
                        return False
                    logger.debug(
                        "MiroFish sim running: round %s/%s (%.0f%%)",
                        data.get("current_round"),
                        data.get("total_rounds"),
                        data.get("progress_percent", 0),
                    )
                except Exception as e:
                    logger.warning("MiroFish run status poll error: %s", e)
                await asyncio.sleep(interval)
                elapsed += interval
                interval = min(interval * POLL_BACKOFF_FACTOR, POLL_MAX_INTERVAL)
            logger.error(
                "MiroFish simulation run timed out after %.0fs", SIM_RUN_TIMEOUT
            )
            return False
        except Exception as e:
            logger.error("MiroFish simulation start failed: %s", e)
            return False

    async def chat_agent(self, agent_id: str, message: str) -> dict[str, Any] | None:
        """
        Send a chat message to a simulated agent via MiroFish API.

        POST /api/agent/{agent_id}/chat
        Returns response dict or None on failure (graceful degradation per D-05).
        """
        try:
            resp = await self._client.post(
                f"/api/agent/{agent_id}/chat",
                json={"message": message},
                timeout=30.0,
            )
            if resp.status_code == 200:
                return resp.json()
            logger.warning(
                "Agent chat failed: %s %s", resp.status_code, resp.text[:200]
            )
            return None
        except Exception as e:
            logger.error("Agent chat error: %s", e)
            return None

    async def _extract_results(self, simulation_id: str) -> dict[str, Any] | None:
        """Step 6: Fetch raw results from multiple MiroFish endpoints."""
        try:
            posts_resp = await self._client.get(
                f"/api/simulation/{simulation_id}/posts", timeout=30.0
            )
            actions_resp = await self._client.get(
                f"/api/simulation/{simulation_id}/actions", timeout=30.0
            )
            timeline_resp = await self._client.get(
                f"/api/simulation/{simulation_id}/timeline", timeout=30.0
            )
            agent_stats_resp = await self._client.get(
                f"/api/simulation/{simulation_id}/agent-stats", timeout=30.0
            )

            results: dict[str, Any] = {
                "simulation_id": simulation_id,
                "posts": (
                    posts_resp.json() if posts_resp.status_code == 200 else []
                ),
                "actions": (
                    actions_resp.json() if actions_resp.status_code == 200 else []
                ),
                "timeline": (
                    timeline_resp.json() if timeline_resp.status_code == 200 else []
                ),
                "agent_stats": (
                    agent_stats_resp.json()
                    if agent_stats_resp.status_code == 200
                    else []
                ),
            }
            return results
        except Exception as e:
            logger.error("MiroFish result extraction failed: %s", e)
            return None
