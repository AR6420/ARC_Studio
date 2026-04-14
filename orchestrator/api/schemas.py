"""
Pydantic v2 schemas for the A.R.C Studio orchestrator API.

Defines all request/response contracts for campaigns, iterations, analyses,
health checks, and demographics. Score models (TribeScores, MirofishMetrics,
CompositeScores) are serialized as JSON text columns in SQLite (per D-08).
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# -- Request models --


class CampaignCreateRequest(BaseModel):
    """Single POST request to create (and optionally start) a campaign (D-10)."""

    seed_content: str = Field(..., min_length=100, max_length=25000)
    prediction_question: str = Field(..., min_length=10)
    demographic: str = Field(...)  # preset key or "custom"
    demographic_custom: str | None = None
    agent_count: int = Field(default=40, ge=20, le=200)
    max_iterations: int = Field(default=4, ge=1, le=10)
    variant_count: int = Field(default=2, ge=1, le=5)
    thresholds: dict[str, float] | None = None
    constraints: str | None = None
    auto_start: bool = Field(default=True)


# -- Score/metric models (for JSON column storage, D-08) --


class TribeScores(BaseModel):
    """7-dimension neural response scores from TRIBE v2."""

    attention_capture: float
    emotional_resonance: float
    memory_encoding: float
    reward_response: float
    threat_detection: float
    cognitive_load: float
    social_relevance: float
    is_pseudo_score: bool = False


class MirofishMetrics(BaseModel):
    """8 metrics from MiroFish social simulation."""

    organic_shares: int
    sentiment_trajectory: list[float]  # per-round sentiment values
    counter_narrative_count: int
    peak_virality_cycle: int
    sentiment_drift: float
    coalition_formation: int  # number of distinct coalitions
    influence_concentration: float  # gini coefficient 0-1
    platform_divergence: float  # divergence score 0-1


class CompositeScores(BaseModel):
    """7 composite scores computed from TRIBE + MiroFish data."""

    attention_score: float | None = None
    virality_potential: float | None = None
    backlash_risk: float | None = None
    memory_durability: float | None = None
    conversion_potential: float | None = None
    audience_fit: float | None = None
    polarization_index: float | None = None


# -- Data completeness tracking (Landmine 5) --


class DataCompleteness(BaseModel):
    """Tracks which systems contributed data to a campaign iteration."""

    tribe_available: bool = True
    mirofish_available: bool = True
    tribe_real_score_count: int = 0
    tribe_pseudo_score_count: int = 0
    missing_composite_dimensions: list[str] = []


# -- Iteration record --


class IterationRecord(BaseModel):
    """One variant's scores within a campaign iteration."""

    id: str
    campaign_id: str
    iteration_number: int
    variant_id: str
    variant_content: str
    variant_strategy: str | None = None
    tribe_scores: TribeScores | None = None
    mirofish_metrics: MirofishMetrics | None = None
    composite_scores: CompositeScores | None = None
    data_completeness: DataCompleteness | None = None
    created_at: str


# -- Analysis record --


class AnalysisRecord(BaseModel):
    """Claude cross-system analysis for one iteration."""

    id: str
    campaign_id: str
    iteration_number: int
    analysis_json: dict[str, Any]
    system_availability: dict[str, bool] | None = None
    created_at: str


# -- Campaign response --


class CampaignResponse(BaseModel):
    """Full campaign response with optional nested iterations and analyses (D-07, D-09)."""

    id: str
    status: str  # pending, running, completed, failed
    seed_content: str
    prediction_question: str
    demographic: str
    demographic_custom: str | None = None
    agent_count: int
    max_iterations: int
    iterations_completed: int = 0  # distinct iteration_numbers stored so far
    thresholds: dict[str, float] | None = None
    constraints: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    iterations: list[IterationRecord] | None = None
    analyses: list[AnalysisRecord] | None = None


class CampaignListResponse(BaseModel):
    """Paginated campaign list (lightweight, no nested iterations)."""

    campaigns: list[CampaignResponse]
    total: int


# -- Report models (Layer 2 scorecard + full report response) --


class ScorecardVariant(BaseModel):
    """A single variant's ranking entry within the scorecard."""

    variant_id: str
    rank: int
    strategy: str
    composite_scores: dict[str, float | None]
    color_coding: dict[str, str]


class ScorecardData(BaseModel):
    """Layer 2 scorecard: structured ranking data with iteration trajectory."""

    winning_variant_id: str
    variants: list[ScorecardVariant]
    iteration_trajectory: list[dict[str, Any]]
    thresholds_status: dict[str, Any]
    summary: str


class ReportResponse(BaseModel):
    """Full report with all 4 layers stored as separate fields (per D-01)."""

    id: str
    campaign_id: str
    verdict: str | None = None
    scorecard: ScorecardData | None = None
    deep_analysis: dict[str, Any] | None = None
    mass_psychology_general: str | None = None
    mass_psychology_technical: str | None = None
    created_at: str


# -- Health response --


class ServiceHealth(BaseModel):
    """Health status of an individual downstream service."""

    status: str  # ok, unavailable
    latency_ms: float | None = None


class Neo4jHealth(BaseModel):
    """Neo4j graph database health metrics for monitoring heap and data growth."""

    node_count: int | None = None
    relationship_count: int | None = None
    heap_max_mb: int | None = None
    warning: str | None = None


class HealthResponse(BaseModel):
    """Aggregated health status of all services."""

    orchestrator: str  # always "ok"
    tribe_scorer: ServiceHealth
    mirofish: ServiceHealth
    litellm: ServiceHealth | None = None  # LLM proxy used by MiroFish
    database: ServiceHealth
    neo4j: Neo4jHealth | None = None


# -- Demographics response --


class DemographicInfo(BaseModel):
    """Single demographic preset for UI display."""

    key: str
    label: str
    description: str


class DemographicsResponse(BaseModel):
    """All available demographic presets."""

    presets: list[DemographicInfo]
    supports_custom: bool = True


# -- System availability (used by engine for graceful degradation, D-05) --


class SystemAvailability(BaseModel):
    """Tracks which downstream systems are available for the current run."""

    tribe_available: bool = False
    mirofish_available: bool = False
    warnings: list[str] = Field(default_factory=list)


# -- Progress/estimate models (SSE streaming, D-09/D-10/OPT-05) --


class ProgressEvent(BaseModel):
    """SSE event payload for campaign progress. Per D-09, D-10."""

    event: str  # iteration_start, step_start, step_complete, iteration_complete, threshold_check, convergence_check, campaign_complete, campaign_error
    campaign_id: str
    iteration: int = 0
    max_iterations: int = 0
    step: str | None = None  # generating, scoring, simulating, analyzing, checking
    step_index: int | None = None  # 1-based
    total_steps: int | None = None
    eta_seconds: float | None = None
    data: dict[str, Any] | None = None  # step-specific payload (scores summary, threshold status, etc.)
    timestamp: str = ""  # ISO 8601, will be set on creation


class EstimateRequest(BaseModel):
    """Request body for POST /api/estimate. Per OPT-05."""

    agent_count: int = Field(default=40, ge=20, le=200)
    max_iterations: int = Field(default=4, ge=1, le=10)


class EstimateResponse(BaseModel):
    """Response from POST /api/estimate. Per OPT-05."""

    estimated_minutes: float
    agent_count: int
    max_iterations: int
    formula: str  # human-readable formula explanation


# -- Agent interview models (UI-08) --


class AgentChatRequest(BaseModel):
    """Request to chat with a simulated agent."""

    message: str = Field(..., min_length=1, max_length=2000)


class AgentChatResponse(BaseModel):
    """Response from agent interview."""

    agent_id: str
    response: str
