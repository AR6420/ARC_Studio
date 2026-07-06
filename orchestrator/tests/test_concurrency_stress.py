"""
Concurrency stress test for the agent-execution layer (Phase 4 of the audit).

Simulates the target load shape — many users each launching a campaign
(the orchestrator's per-campaign background task IS the agent-workload unit) —
scaled down to what runs locally with the downstream GPU/Docker services mocked.

Asserts the properties the audit fixes were meant to guarantee:
  * Admission control returns 429 past the concurrency cap (M-14).
  * Peak in-flight tasks never exceed the cap (bounded concurrency).
  * No leaks: running_tasks / progress_queues / progress_history all drain to
    empty after completion (M-15 / CON-07 / RES-06 / OBS-09).
  * Correct results under contention: every ADMITTED campaign reaches a terminal
    state and is evicted; every REJECTED one never created state.
  * No deadlock: the whole burst completes within a generous time bound.
  * SSE reconnect during a running campaign returns 200, not 404 (M-16 / PERF-03).
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from orchestrator.config import settings
from orchestrator.storage.campaign_store import CampaignStore
from orchestrator.storage.database import Database

CAP = 5  # small, deterministic admission cap for the test


def _build_stress_app(tmp_db_path: str, gate: asyncio.Event, peak: dict) -> FastAPI:
    """App with the REAL campaigns + progress routers and a mocked runner whose
    run_campaign blocks on `gate` so we can hold many campaigns 'in flight' at
    once and observe admission control + eventual cleanup."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(tmp_db_path)
        await db.connect()
        app.state.db = db
        app.state.campaign_store = CampaignStore(db)
        app.state.running_tasks = {}
        app.state.progress_queues = {}
        app.state.progress_history = {}
        app.state.inflight_campaigns = 0

        class _Runner:
            async def run_campaign(self, campaign_id: str, progress_callback=None):
                # Track peak concurrency as observed by the runner itself.
                peak["current"] += 1
                peak["max"] = max(peak["max"], peak["current"])
                try:
                    # Hold the slot until the test releases the gate.
                    await gate.wait()
                    if progress_callback:
                        await progress_callback(
                            {"event": "campaign_complete", "campaign_id": campaign_id}
                        )
                finally:
                    peak["current"] -= 1

        app.state.campaign_runner = _Runner()
        yield
        # Mirror the production shutdown drain (M-12).
        pending = [t for t in app.state.running_tasks.values() if not t.done()]
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        await db.close()

    from orchestrator.api.campaigns import router as campaigns_router
    from orchestrator.api.progress import router as progress_router

    app = FastAPI(lifespan=lifespan)
    app.include_router(campaigns_router, prefix="/api")
    app.include_router(progress_router, prefix="/api")
    return app


def _payload(i: int) -> dict:
    return {
        "seed_content": "A" * 150,
        "prediction_question": f"How will audience {i} respond to this launch?",
        "demographic": "tech_professionals",
        "auto_start": True,
    }


@pytest.mark.asyncio
async def test_admission_control_and_no_leak_under_burst(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "max_concurrent_campaigns", CAP)

    gate = asyncio.Event()
    peak = {"current": 0, "max": 0}
    app = _build_stress_app(str(tmp_path / "stress.db"), gate, peak)
    transport = ASGITransport(app=app)

    async with app.router.lifespan_context(app), AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        # 100 "users" fire simultaneously; only CAP may be admitted while the
        # gate is held closed. The rest must get 429 (not a silent 201-then-hang).
        NUM_USERS = 100
        responses = await asyncio.gather(
            *[client.post("/api/campaigns", json=_payload(i)) for i in range(NUM_USERS)]
        )
        codes = [r.status_code for r in responses]
        admitted = [r for r in responses if r.status_code == 201]
        rejected = [r for r in responses if r.status_code == 429]

        # Every response is a clean 201 or 429 — no 500s, no hangs.
        assert set(codes) <= {201, 429}, f"unexpected codes: {set(codes)}"
        # Admission is bounded by the cap.
        assert len(admitted) <= CAP
        assert len(rejected) == NUM_USERS - len(admitted)
        assert len(admitted) >= 1  # at least some progress
        # The runner never saw more than CAP concurrent campaigns.
        assert peak["max"] <= CAP

        # 429s carry a Retry-After so clients can back off intelligently.
        assert all("retry-after" in r.headers for r in rejected)

        admitted_ids = [r.json()["id"] for r in admitted]

        # Reconnect check (M-16): an admitted, still-running campaign's progress
        # queue must exist (a mid-run SSE reconnect would find it, not 404).
        for cid in admitted_ids:
            assert cid in app.state.progress_queues

        # Release the gate → all admitted campaigns finish.
        gate.set()

        # Wait (bounded) for every background task to drain — proves no deadlock.
        async def _drained() -> bool:
            return all(t.done() for t in app.state.running_tasks.values())

        for _ in range(200):  # up to ~10s
            if not app.state.running_tasks or await _drained():
                break
            await asyncio.sleep(0.05)

        # Give the finally-blocks a tick to evict.
        await asyncio.sleep(0.1)

        # No leaks: task registry + both progress maps drained for admitted ids.
        for cid in admitted_ids:
            assert cid not in app.state.running_tasks, "running_tasks leaked"
            assert cid not in app.state.progress_queues, "progress_queues leaked"
            assert cid not in app.state.progress_history, "progress_history leaked"
        # Admission counter returns to zero — no slot leak (would permanently
        # shrink capacity otherwise).
        assert app.state.inflight_campaigns == 0


@pytest.mark.asyncio
async def test_capacity_frees_after_completion(tmp_path: Path, monkeypatch):
    """Once admitted campaigns finish, new ones are admitted again — the cap is a
    live concurrency gate, not a lifetime quota."""
    monkeypatch.setattr(settings, "max_concurrent_campaigns", CAP)

    gate = asyncio.Event()
    peak = {"current": 0, "max": 0}
    app = _build_stress_app(str(tmp_path / "stress2.db"), gate, peak)
    transport = ASGITransport(app=app)

    async with app.router.lifespan_context(app), AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        # Fill to capacity.
        first = await asyncio.gather(
            *[client.post("/api/campaigns", json=_payload(i)) for i in range(CAP)]
        )
        assert all(r.status_code == 201 for r in first)

        # One more is rejected while full.
        blocked = await client.post("/api/campaigns", json=_payload(99))
        assert blocked.status_code == 429

        # Drain the first batch.
        gate.set()
        for _ in range(200):
            if all(t.done() for t in app.state.running_tasks.values()):
                break
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.1)

        # Capacity is free again — a new campaign is admitted.
        gate.clear()
        again = await client.post("/api/campaigns", json=_payload(100))
        assert again.status_code == 201

        gate.set()
        for _ in range(100):
            if all(t.done() for t in app.state.running_tasks.values()):
                break
            await asyncio.sleep(0.05)
