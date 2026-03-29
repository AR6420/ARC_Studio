# Phase 6: Optimization Loop - Research

**Researched:** 2026-03-29
**Domain:** Multi-iteration optimization, convergence detection, SSE progress streaming, background task management
**Confidence:** HIGH

## Summary

Phase 6 transforms the existing single-iteration campaign pipeline into a multi-iteration optimization loop. The current `CampaignRunner.run_single_iteration()` already accepts `previous_iteration_results` and `previous_analysis` parameters -- these are wired but never called in a loop. The variant generation prompt (`build_variant_generation_prompt`) already handles previous results injection with improvement directives. The composite scorer produces the exact score dictionary format needed for threshold comparison. The database schema already supports multiple iterations per campaign via the `(campaign_id, iteration_number, variant_id)` unique constraint.

The primary engineering work is: (1) a `run_campaign()` method that loops `run_single_iteration()`, extracting results and feeding them forward; (2) a threshold checker comparing top-variant composite scores against user targets; (3) convergence detection (<5% improvement for 2 consecutive iterations); (4) an SSE endpoint using `sse-starlette` (already installed at v3.3.3) with `asyncio.Queue` for per-campaign progress broadcasting; (5) background task management using `asyncio.create_task` with lifecycle tracked on `app.state`; and (6) a time estimation endpoint.

**Primary recommendation:** Extend `CampaignRunner` with a `run_campaign()` orchestration method that wraps the existing `run_single_iteration()` in a loop with threshold/convergence checks, emitting progress events to an `asyncio.Queue` that the SSE endpoint consumes. Use `asyncio.create_task` for background execution (no Celery needed -- this is single-user POC).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Pass full previous iteration results (all scores + Claude Opus analysis) to variant generation prompt
- **D-02:** Generate 3 new variants each iteration (consistent with Phase 5 D-01)
- **D-03:** Replace all variants each iteration -- do not carry forward best variants
- **D-04:** Claude Haiku prompt includes specific improvement instructions extracted from Opus analysis
- **D-05:** Convergence threshold: <5% improvement for 2 consecutive iterations (per spec OPT-03)
- **D-06:** Threshold comparison: compare top variant's composite scores against user-defined targets (not average)
- **D-07:** Early stop requires all user-enabled thresholds to be met (not just any single one)
- **D-08:** Max iterations is a hard cap from campaign config (default 4)
- **D-09:** SSE endpoint at GET /api/campaigns/{id}/progress -- server-sent events, not WebSocket
- **D-10:** Event granularity: per-step within each iteration (generating, scoring, simulating, analyzing)
- **D-11:** ETA calculation: formula-based, refined at runtime as actual durations are observed
- **D-12:** Time estimate endpoint: POST /api/estimate returns pre-run prediction (per OPT-05)

### Claude's Discretion
- SSE event format (JSON structure, event types naming)
- Background task management for async campaign execution
- How to wire SSE into existing FastAPI app (asyncio.Queue, or broadcast pattern)

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OPT-01 | Multi-iteration support in campaign runner (pass previous results to variant generation) | CampaignRunner.run_single_iteration() already accepts previous_iteration_results and previous_analysis params. Wrap in loop, extract and forward. |
| OPT-02 | Threshold checker comparing composite scores against user targets | compute_composite_scores() returns dict ready for comparison. Thresholds stored in campaign.thresholds (JSON column). D-06: compare top variant only. D-07: all enabled thresholds must be met. |
| OPT-03 | Early stopping on threshold achievement or convergence (<5% improvement for 2 iterations) | Track best composite score per iteration, compute improvement percentage. Two consecutive iterations below 5% triggers stop. |
| OPT-04 | Time estimator with formula-based and runtime-refined estimates | Formula from Results.md: estimated_minutes = (agent_count / 40) * max_iterations * 3. Refine with moving average of actual step durations. |
| OPT-05 | POST /api/estimate endpoint | New endpoint accepting campaign config, returning time estimate without creating campaign. |
| OPT-06 | SSE progress streaming (iteration events, step tracking, ETA) | sse-starlette 3.3.3 installed. asyncio.Queue per campaign for event delivery. EventSourceResponse wraps async generator. |
| OPT-07 | Optimization loop demonstrably improves scores across iterations | Opus analysis includes recommendations_for_next_iteration. Variant generation prompt already injects improvement directives. Test with mock data showing improvement. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Hardware**: Single RTX 5070 Ti GPU -- TRIBE and MiroFish scoring are sequential (no parallel GPU access)
- **Performance**: Full campaign (40 agents, 4 iterations) must complete in <= 20 minutes, meaning ~5 minutes per iteration
- **API rate limits**: Claude Opus calls are sequential (4-8 per campaign = one per iteration fits 4 iterations)
- **Scope**: Phase 1 POC -- single-user, no auth, no multi-user
- **GSD Workflow**: All changes through GSD workflow

## Standard Stack

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.128.1 | API framework | Already in use, SSE via sse-starlette |
| sse-starlette | 3.3.3 | SSE streaming | W3C-compliant SSE for FastAPI, already installed |
| asyncio (stdlib) | Python 3.14 | Background tasks, Queue | Built-in, no additional deps for single-user POC |
| pydantic | 2.12.5 | Schema validation | Already in use for all request/response models |
| aiosqlite | (installed) | Async SQLite | Already in use for campaign persistence |

### Supporting (Already Installed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.28.1 | HTTP client | Already used for TRIBE/MiroFish clients |
| httpx-sse | 0.4.3 | SSE test client | Testing SSE endpoints in pytest |
| pytest | 9.0.2 | Test framework | Unit tests for all new modules |
| pytest-asyncio | 1.3.0 | Async test support | Async test fixtures and assertions |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncio.Queue | Redis pub/sub | Redis would add infrastructure; Queue is sufficient for single-user POC |
| asyncio.create_task | Celery | Celery is overkill for single-user, single-machine; adds broker dependency |
| sse-starlette | FastAPI built-in SSE | Built-in SSE requires FastAPI >= 0.115+; sse-starlette already installed and battle-tested |

**Installation:** No new packages required. All dependencies already installed.

## Architecture Patterns

### Recommended Project Structure
```
orchestrator/
  engine/
    campaign_runner.py       # EXTEND: add run_campaign() method
    optimization_loop.py     # NEW: ThresholdChecker, ConvergenceDetector, TimeEstimator
    composite_scorer.py      # EXISTING: no changes
  api/
    __init__.py              # EXTEND: mount progress router
    campaigns.py             # EXTEND: background task launch on auto_start
    progress.py              # NEW: SSE endpoint + estimate endpoint
    schemas.py               # EXTEND: add ProgressEvent, EstimateRequest/Response schemas
  prompts/
    variant_generation.py    # EXISTING: already handles previous_iteration_results
```

### Pattern 1: Optimization Loop as CampaignRunner Extension
**What:** Add `run_campaign()` to the existing `CampaignRunner` class that wraps `run_single_iteration()` in a loop with convergence/threshold checks.
**When to use:** Always -- this is the core pattern for the phase.
**Example:**
```python
# orchestrator/engine/campaign_runner.py
async def run_campaign(
    self,
    campaign_id: str,
    progress_callback: Callable[[dict], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """
    Multi-iteration optimization loop.
    Calls run_single_iteration() in a loop, passing previous results forward.
    Checks thresholds and convergence after each iteration.
    """
    campaign = await self._store.get_campaign(campaign_id)
    max_iterations = campaign.max_iterations
    thresholds = campaign.thresholds

    previous_results = None
    previous_analysis = None
    best_scores_history: list[dict[str, float | None]] = []

    for iteration in range(1, max_iterations + 1):
        if progress_callback:
            await progress_callback({
                "event": "iteration_start",
                "iteration": iteration,
                "max_iterations": max_iterations,
            })

        result = await self.run_single_iteration(
            campaign_id=campaign_id,
            iteration_number=iteration,
            previous_iteration_results=previous_results,
            previous_analysis=previous_analysis,
        )

        # Extract best variant scores for threshold/convergence checks
        best_composite = _find_best_composite(result["composite_scores"])
        best_scores_history.append(best_composite)

        # Build feedback for next iteration
        previous_results = _build_iteration_feedback(result)
        previous_analysis = result["analysis"]

        # Check thresholds
        if thresholds and _all_thresholds_met(best_composite, thresholds):
            # Early stop: all thresholds met
            break

        # Check convergence (need at least 2 iterations)
        if len(best_scores_history) >= 3:
            if _is_converged(best_scores_history[-3:]):
                break

    return final_result
```

### Pattern 2: asyncio.Queue-Based SSE Broadcasting
**What:** Each running campaign gets an `asyncio.Queue` stored on `app.state`. The campaign runner pushes progress events to the queue. The SSE endpoint reads from the queue via an async generator.
**When to use:** For SSE progress streaming (D-09, D-10).
**Example:**
```python
# orchestrator/api/progress.py
from sse_starlette import EventSourceResponse
import asyncio
import json

@router.get("/campaigns/{campaign_id}/progress")
async def campaign_progress(request: Request, campaign_id: str):
    """SSE endpoint for real-time campaign progress."""
    queue: asyncio.Queue = _get_or_create_queue(request.app, campaign_id)

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield {
                    "event": event["event"],
                    "data": json.dumps(event),
                }
                if event["event"] == "campaign_complete":
                    break
            except asyncio.TimeoutError:
                yield {"comment": "keepalive"}

    return EventSourceResponse(event_generator())
```

### Pattern 3: Background Task with Lifecycle Management
**What:** When `auto_start=True`, create an `asyncio.Task` for the campaign, store it in a dict on `app.state`, and clean up on completion.
**When to use:** For non-blocking campaign execution from the API.
**Example:**
```python
# orchestrator/api/campaigns.py
async def _launch_campaign_background(app, campaign_id: str):
    """Launch campaign as background asyncio task."""
    runner = _build_campaign_runner(app)
    queue = _get_or_create_queue(app, campaign_id)

    async def progress_callback(event: dict):
        await queue.put(event)

    try:
        result = await runner.run_campaign(
            campaign_id=campaign_id,
            progress_callback=progress_callback,
        )
        await queue.put({"event": "campaign_complete", "result": "success"})
    except Exception as e:
        await queue.put({"event": "campaign_error", "error": str(e)})
    finally:
        # Cleanup task reference
        app.state.running_tasks.pop(campaign_id, None)

# In the POST endpoint:
task = asyncio.create_task(_launch_campaign_background(request.app, campaign.id))
request.app.state.running_tasks[campaign.id] = task
```

### Pattern 4: Threshold Checking Logic
**What:** Compare top variant's composite scores against user-defined thresholds. Backlash risk and polarization index are inverted (user sets maximum).
**When to use:** After each iteration to determine early stop.
**Example:**
```python
# orchestrator/engine/optimization_loop.py
INVERTED_SCORES = {"backlash_risk", "polarization_index"}

def check_thresholds(
    best_scores: dict[str, float | None],
    thresholds: dict[str, float],
) -> tuple[bool, dict[str, bool]]:
    """
    Check if all user-enabled thresholds are met.
    Returns (all_met, per_threshold_status).
    Per D-06: compare top variant only.
    Per D-07: ALL enabled thresholds must be met.
    """
    status = {}
    for metric, target in thresholds.items():
        actual = best_scores.get(metric)
        if actual is None:
            status[metric] = False
            continue
        if metric in INVERTED_SCORES:
            status[metric] = actual <= target  # lower is better
        else:
            status[metric] = actual >= target  # higher is better

    all_met = all(status.values()) if status else False
    return all_met, status
```

### Pattern 5: Convergence Detection
**What:** Track improvement percentage between iterations. If <5% for 2 consecutive iterations, stop.
**When to use:** After each iteration, starting from iteration 2.
**Example:**
```python
def compute_improvement(
    current_scores: dict[str, float | None],
    previous_scores: dict[str, float | None],
) -> float:
    """
    Compute average improvement percentage across non-None composite scores.
    Returns percentage (e.g., 3.5 means 3.5% improvement).
    """
    improvements = []
    for key in current_scores:
        curr = current_scores.get(key)
        prev = previous_scores.get(key)
        if curr is not None and prev is not None and prev != 0:
            pct_change = ((curr - prev) / abs(prev)) * 100
            improvements.append(pct_change)
    return sum(improvements) / len(improvements) if improvements else 0.0

def is_converged(
    improvement_history: list[float],
    threshold_pct: float = 5.0,
    consecutive_count: int = 2,
) -> bool:
    """Per D-05: <5% improvement for 2 consecutive iterations."""
    if len(improvement_history) < consecutive_count:
        return False
    recent = improvement_history[-consecutive_count:]
    return all(imp < threshold_pct for imp in recent)
```

### Pattern 6: Time Estimation
**What:** Formula-based pre-run estimate, refined at runtime with actual step durations.
**When to use:** POST /api/estimate for pre-run, and within SSE events during execution.
**Example:**
```python
class TimeEstimator:
    """
    Pre-run formula: estimated_minutes = (agent_count / 40) * max_iterations * 3
    Runtime: refine based on moving average of observed step durations.
    """
    BASELINE_MINUTES_PER_ITERATION = 3.0  # for 40 agents

    def estimate_pre_run(self, agent_count: int, max_iterations: int) -> float:
        """Returns estimated minutes (per Results.md formula)."""
        return (agent_count / 40) * max_iterations * self.BASELINE_MINUTES_PER_ITERATION

    def estimate_remaining(
        self,
        current_iteration: int,
        current_step: int,
        total_steps_per_iteration: int,
        max_iterations: int,
        observed_step_durations: list[float],
    ) -> float:
        """Refine estimate using actual observed step durations."""
        if not observed_step_durations:
            # Fall back to formula
            remaining_iterations = max_iterations - current_iteration
            return remaining_iterations * self.BASELINE_MINUTES_PER_ITERATION

        avg_step_seconds = sum(observed_step_durations) / len(observed_step_durations)
        remaining_steps_this_iter = total_steps_per_iteration - current_step
        remaining_full_iterations = max_iterations - current_iteration
        total_remaining_steps = (
            remaining_steps_this_iter
            + remaining_full_iterations * total_steps_per_iteration
        )
        return (total_remaining_steps * avg_step_seconds) / 60.0
```

### SSE Event Schema (Claude's Discretion)
```python
# Recommended SSE event types and JSON structure
class ProgressEvent(BaseModel):
    """SSE event payload for campaign progress."""
    event: str  # "iteration_start", "step_start", "step_complete", "iteration_complete", "campaign_complete", "campaign_error"
    campaign_id: str
    iteration: int
    max_iterations: int
    step: str | None = None  # "generating", "scoring", "simulating", "analyzing", "checking"
    step_index: int | None = None  # 1-based, out of total steps
    total_steps: int | None = None
    eta_seconds: float | None = None
    data: dict | None = None  # step-specific data (e.g., scores summary)
    timestamp: str  # ISO 8601

# SSE event type names:
# - "iteration_start": New iteration begins
# - "step_start": Pipeline step begins (generating, scoring, simulating, analyzing)
# - "step_complete": Pipeline step finished
# - "iteration_complete": Iteration finished with scores summary
# - "threshold_check": Threshold comparison result
# - "convergence_check": Convergence detection result
# - "campaign_complete": Campaign finished (success or converged)
# - "campaign_error": Campaign failed with error
```

### Anti-Patterns to Avoid
- **Storing Queue references globally**: Use `app.state` for queue storage so it is tied to the application lifecycle and cleaned up on shutdown.
- **Blocking the event loop in run_campaign**: All pipeline steps are already async. Do not add `time.sleep()` or synchronous calls.
- **Setting status to "completed" inside run_single_iteration during multi-iteration**: The loop wrapper must manage status transitions, not the per-iteration method. The current `run_single_iteration` sets status to "completed" -- this must be conditional or moved to the loop wrapper.
- **Creating a new CampaignRunner per request**: Reuse the runner instance from `app.state` (dependency injection pattern already established).
- **Comparing average variant scores for thresholds**: D-06 explicitly says compare top variant's scores, not average.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE streaming | Custom StreamingResponse with manual event formatting | sse-starlette EventSourceResponse | W3C compliance, ping keepalive, disconnect detection, already installed |
| Background task lifecycle | Manual thread management or ProcessPoolExecutor | asyncio.create_task + app.state dict | Single-user POC; asyncio tasks are sufficient, no broker needed |
| Event bus / pub-sub | Custom observer pattern or Redis pub/sub | asyncio.Queue per campaign | One producer (runner), one consumer (SSE endpoint), Queue is perfect fit |
| JSON serialization in SSE | Manual json.dumps with escaping | Pydantic model .model_dump_json() + sse-starlette data field | Type safety, validation, consistent serialization |

**Key insight:** The existing codebase is already async throughout and uses dependency injection. The optimization loop is primarily about wiring existing components in a loop with control flow logic. No new external services or complex infrastructure are needed.

## Common Pitfalls

### Pitfall 1: run_single_iteration Sets "completed" Status Prematurely
**What goes wrong:** The current `run_single_iteration()` always sets campaign status to "completed" at the end (line 232). In a multi-iteration loop, this happens after iteration 1, making the campaign appear "completed" when it is not.
**Why it happens:** The method was designed for single-iteration use. Multi-iteration was deferred to Phase 6.
**How to avoid:** Modify `run_single_iteration()` to NOT set status to "completed" or "running" -- move status management to the `run_campaign()` wrapper. Alternatively, add a parameter like `manage_status=True` (default) that the loop wrapper sets to False.
**Warning signs:** Campaign status shows "completed" after first iteration while SSE is still streaming.

### Pitfall 2: SSE Queue Memory Leak on Client Disconnect
**What goes wrong:** If a client connects to SSE, then disconnects without consuming the queue, events pile up in memory. If the campaign runs 4 iterations producing ~30 events, this is small. But if the queue is never cleaned up, references persist.
**Why it happens:** asyncio.Queue has no automatic cleanup on consumer disconnect.
**How to avoid:** Clean up the queue when: (a) campaign completes, (b) SSE client disconnects (detected via `request.is_disconnected()`), or (c) on app shutdown. Use a dict on `app.state` with campaign_id keys, remove entries on completion.
**Warning signs:** `app.state.progress_queues` dict growing without bound.

### Pitfall 3: Improvement Calculation on None Scores
**What goes wrong:** When TRIBE or MiroFish is unavailable, some composite scores are None. Computing improvement percentage against None causes TypeError or misleading results.
**Why it happens:** Graceful degradation (D-05) means some scores can legitimately be None.
**How to avoid:** Filter to only non-None scores when computing improvement. If all scores are None, skip convergence check for that iteration.
**Warning signs:** TypeError in convergence detection, or convergence triggered falsely because only 1-2 scores are being compared.

### Pitfall 4: Race Condition Between SSE Connect and Campaign Start
**What goes wrong:** If the client POSTs to create a campaign with auto_start=True, then immediately GETs the SSE endpoint, the queue might not exist yet because the background task hasn't started.
**Why it happens:** asyncio.create_task schedules the task but doesn't run it until the current coroutine yields.
**How to avoid:** Create the queue BEFORE launching the background task, in the POST handler. The SSE endpoint finds the queue immediately.
**Warning signs:** Client connects to SSE and gets no events, or 404 because queue doesn't exist.

### Pitfall 5: Opus Analysis JSON Structure Not Extracting Improvement Instructions
**What goes wrong:** D-04 requires extracting specific improvement instructions from Opus analysis and injecting them into the Haiku variant generation prompt. The Opus analysis JSON has `recommendations_for_next_iteration` as an array, but the existing prompt template only handles the structured `previous_iteration_results` format (variant scores + composite scores + iteration_note).
**Why it happens:** The existing prompt template (`build_variant_generation_prompt`) expects a `list[dict]` with specific keys. The Opus analysis structure is different.
**How to avoid:** Build the `previous_iteration_results` list from the iteration results (variants + scores + composites) and add the Opus `recommendations_for_next_iteration` as `iteration_note` entries. The prompt template already has an `opus_note` / `iteration_note` field handler.
**Warning signs:** Variants in iteration 2+ don't show meaningful improvement because they lack the Opus-directed improvement instructions.

### Pitfall 6: Convergence Check Off-By-One
**What goes wrong:** D-05 says "<5% improvement for 2 consecutive iterations." If you check after iteration 2, you only have 1 improvement data point (iter 1 -> iter 2). You need at least 3 iterations to have 2 consecutive improvement measurements.
**Why it happens:** Confusing "2 consecutive iterations" with "2 data points". You need improvements from iter1->iter2 AND iter2->iter3, which requires 3 completed iterations.
**How to avoid:** Only check convergence when `len(improvement_history) >= 2`, which requires at least 3 completed iterations.
**Warning signs:** Campaign stops after iteration 2 even though only one improvement measurement exists.

## Code Examples

### Building Iteration Feedback for Variant Generation
```python
# Source: Based on existing variant_generation.py prompt template expectations
def build_iteration_feedback(
    result: dict[str, Any],
    analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Transform a single-iteration result into the format expected by
    build_variant_generation_prompt(previous_iteration_results=...).

    Per D-01: Pass full results (scores + analysis).
    Per D-04: Include Opus improvement instructions as iteration_note.
    """
    feedback = []
    variants = result["variants"]
    tribe_scores = result["tribe_scores"]
    mirofish_metrics = result["mirofish_metrics"]
    composite_scores = result["composite_scores"]

    # Get Opus recommendations
    recommendations = analysis.get("recommendations_for_next_iteration", [])
    recs_text = " | ".join(recommendations) if recommendations else ""

    # Per-variant assessments from Opus
    assessments = {
        a["variant_id"]: a.get("composite_assessment", "")
        for a in analysis.get("per_variant_assessment", [])
    }

    for i, variant in enumerate(variants):
        vid = variant["id"]
        entry = {
            "variant_id": vid,
            "strategy": variant.get("strategy", ""),
            "composite_scores": composite_scores[i] if i < len(composite_scores) else {},
            "tribe_scores": tribe_scores[i] if i < len(tribe_scores) else {},
            "mirofish_metrics": mirofish_metrics[i] if i < len(mirofish_metrics) else {},
            "iteration_note": f"{assessments.get(vid, '')} Recommendations: {recs_text}",
        }
        feedback.append(entry)

    return feedback
```

### Finding Best Variant Composite Scores
```python
def find_best_composite(
    composite_scores_list: list[dict[str, float | None]],
) -> dict[str, float | None]:
    """
    Find the best variant's composite scores for threshold checking.
    Per D-06: compare top variant (not average).

    "Best" = highest average of non-None, non-inverted scores.
    """
    INVERTED = {"backlash_risk", "polarization_index"}
    best_idx = 0
    best_avg = -float("inf")

    for i, scores in enumerate(composite_scores_list):
        values = []
        for key, val in scores.items():
            if val is None:
                continue
            if key in INVERTED:
                values.append(100.0 - val)  # invert for ranking
            else:
                values.append(val)
        avg = sum(values) / len(values) if values else 0.0
        if avg > best_avg:
            best_avg = avg
            best_idx = i

    return composite_scores_list[best_idx]
```

### SSE Endpoint with sse-starlette
```python
# Source: sse-starlette 3.3.3 API (verified installed)
from fastapi import APIRouter, Request, HTTPException
from sse_starlette import EventSourceResponse
import asyncio
import json

router = APIRouter(tags=["progress"])

@router.get("/campaigns/{campaign_id}/progress")
async def campaign_progress(request: Request, campaign_id: str):
    """
    SSE endpoint for real-time campaign progress.
    Per D-09: GET /api/campaigns/{id}/progress
    Per D-10: Per-step events within each iteration.
    """
    queues: dict = getattr(request.app.state, "progress_queues", {})
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
                    yield {
                        "event": event.get("event", "message"),
                        "data": json.dumps(event),
                    }
                    if event.get("event") in ("campaign_complete", "campaign_error"):
                        break
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield {"comment": "keepalive"}
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())
```

### Testing SSE with httpx-sse
```python
# Source: httpx-sse 0.4.3 (verified installed)
import httpx
from httpx_sse import aconnect_sse

async def test_sse_progress_stream():
    """Test SSE endpoint delivers progress events."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # Create and start campaign first
        # ...

        async with aconnect_sse(
            client, "GET", f"/api/campaigns/{campaign_id}/progress"
        ) as event_source:
            events = []
            async for sse in event_source.aiter_sse():
                events.append(sse)
                if sse.event == "campaign_complete":
                    break

            assert len(events) > 0
            assert events[0].event == "iteration_start"
            assert events[-1].event == "campaign_complete"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FastAPI BackgroundTasks | asyncio.create_task for long-running | Always (BackgroundTasks for quick tasks only) | Proper lifecycle management for multi-minute campaigns |
| Custom SSE with StreamingResponse | sse-starlette EventSourceResponse | sse-starlette 3.x (2024+) | W3C compliant, keepalive, disconnect detection |
| FastAPI built-in SSE (fastapi.sse) | Only in FastAPI 0.115+ | 2025+ | Not available in 0.128.1 -- wait, version numbering suggests it might be newer than 0.115 but the module doesn't exist; use sse-starlette |

**Note on FastAPI version:** FastAPI 0.128.1 is installed but does NOT have `fastapi.sse`. The built-in SSE support was added later in a different version track. `sse-starlette` 3.3.3 is the correct choice and is already installed.

## Open Questions

1. **Status management refactoring**
   - What we know: `run_single_iteration()` currently manages campaign status (sets "running" and "completed"). For multi-iteration, the loop wrapper needs to manage status instead.
   - What's unclear: Whether to add a parameter to disable status management in `run_single_iteration()`, or refactor it out entirely.
   - Recommendation: Add a `manage_status: bool = True` parameter. When the loop wrapper calls it, pass `manage_status=False`. This preserves backward compatibility for single-iteration use.

2. **CampaignRunner construction in API context**
   - What we know: The API lifespan creates all clients and stores on `app.state`. The CampaignRunner needs all of them but is NOT currently constructed during lifespan.
   - What's unclear: Whether to build the runner once during lifespan or build it per-request.
   - Recommendation: Build once during lifespan and store on `app.state.campaign_runner`. This is consistent with the DI pattern and avoids repeated construction.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| FastAPI | API endpoints | Yes | 0.128.1 | -- |
| sse-starlette | SSE streaming | Yes | 3.3.3 | -- |
| httpx-sse | SSE testing | Yes | 0.4.3 | -- |
| asyncio | Background tasks, Queue | Yes | stdlib (Python 3.14) | -- |
| pytest | Test runner | Yes | 9.0.2 | -- |
| pytest-asyncio | Async tests | Yes | 1.3.0 | -- |
| aiosqlite | Database | Yes | (installed) | -- |

**Missing dependencies with no fallback:** None
**Missing dependencies with fallback:** None

All required dependencies are already installed. No new packages needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` |
| Quick run command | `pytest orchestrator/tests/ -x -q` |
| Full suite command | `pytest orchestrator/tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OPT-01 | run_campaign loops iterations, passes previous results | unit | `pytest orchestrator/tests/test_optimization_loop.py::test_multi_iteration_passes_previous_results -x` | No -- Wave 0 |
| OPT-02 | Threshold checker compares top variant scores against targets | unit | `pytest orchestrator/tests/test_optimization_loop.py::test_threshold_checker -x` | No -- Wave 0 |
| OPT-03 | Early stop on convergence (<5% for 2 consecutive) | unit | `pytest orchestrator/tests/test_optimization_loop.py::test_convergence_detection -x` | No -- Wave 0 |
| OPT-04 | Time estimator formula and runtime refinement | unit | `pytest orchestrator/tests/test_optimization_loop.py::test_time_estimator -x` | No -- Wave 0 |
| OPT-05 | POST /api/estimate returns time prediction | unit | `pytest orchestrator/tests/test_progress.py::test_estimate_endpoint -x` | No -- Wave 0 |
| OPT-06 | SSE streams progress events during campaign | integration | `pytest orchestrator/tests/test_progress.py::test_sse_progress_stream -x` | No -- Wave 0 |
| OPT-07 | Scores improve across iterations (with mocked pipeline) | unit | `pytest orchestrator/tests/test_optimization_loop.py::test_scores_improve_across_iterations -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest orchestrator/tests/ -x -q`
- **Per wave merge:** `pytest orchestrator/tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `orchestrator/tests/test_optimization_loop.py` -- covers OPT-01, OPT-02, OPT-03, OPT-04, OPT-07
- [ ] `orchestrator/tests/test_progress.py` -- covers OPT-05, OPT-06
- [ ] No new framework install needed -- pytest and pytest-asyncio already configured

## Sources

### Primary (HIGH confidence)
- **Existing codebase** (read directly): `campaign_runner.py`, `variant_generator.py`, `variant_generation.py`, `composite_scorer.py`, `result_analyzer.py`, `result_analysis.py`, `campaign_store.py`, `database.py`, `schemas.py`, `config.py`, `cli.py`, `api/__init__.py`, `api/campaigns.py`
- **sse-starlette 3.3.3** (verified installed via `pip show`)
- **httpx-sse 0.4.3** (verified installed via `pip show`)
- **FastAPI 0.128.1** (verified installed, confirmed `fastapi.sse` NOT available)

### Secondary (MEDIUM confidence)
- [FastAPI SSE tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/) - Confirmed built-in SSE pattern (requires newer FastAPI)
- [sse-starlette GitHub](https://github.com/sysid/sse-starlette) - EventSourceResponse API, ping, disconnect handling
- [FastAPI Background Tasks docs](https://fastapi.tiangolo.com/tutorial/background-tasks/) - Confirmed BackgroundTasks not suitable for long-running; asyncio.create_task preferred

### Tertiary (LOW confidence)
- None -- all findings verified against installed packages and official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages verified installed with `pip show`
- Architecture: HIGH -- patterns derived from reading actual codebase, understanding existing DI pattern, and confirmed sse-starlette API
- Pitfalls: HIGH -- identified by reading the actual `run_single_iteration()` code and tracing data flow through the existing pipeline

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable -- all libraries installed, no version changes expected)
