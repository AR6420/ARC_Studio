/**
 * TypeScript interfaces mirroring orchestrator/api/schemas.py Pydantic models.
 *
 * Source of truth: orchestrator/api/schemas.py
 * Every field name, type, and nullability must match the Pydantic model exactly.
 */

// -- Status type alias --

export type CampaignStatus = 'pending' | 'running' | 'completed' | 'failed';

// -- Request models --

export interface CampaignCreateRequest {
  seed_content: string;
  prediction_question: string;
  demographic: string;
  demographic_custom?: string | null;
  agent_count?: number;
  max_iterations?: number;
  variant_count?: number;
  thresholds?: Record<string, number> | null;
  constraints?: string | null;
  auto_start?: boolean;
  // Phase 2 A.1 / A.2 — audio + video input support
  media_type?: 'text' | 'audio' | 'video';
  media_path?: string | null;
}

// -- Media upload (Phase 2 A.1 + A.2) --

export interface MediaUploadResponse {
  media_path: string;
  duration_seconds: number;
  size_bytes: number;
  media_type: 'audio' | 'video';
  // Video-only fields. Reflect post-downscale dimensions when the orchestrator
  // had to fit MAX_VIDEO_RESOLUTION_HEIGHT.
  width?: number | null;
  height?: number | null;
  downscaled?: boolean;
}

// -- Score / metric models (JSON column storage, D-08) --

export interface TribeScores {
  attention_capture: number;
  emotional_resonance: number;
  memory_encoding: number;
  reward_response: number;
  threat_detection: number;
  cognitive_load: number;
  social_relevance: number;
  is_pseudo_score?: boolean;
}

export interface MirofishMetrics {
  organic_shares: number;
  sentiment_trajectory: number[];
  counter_narrative_count: number;
  peak_virality_cycle: number;
  sentiment_drift: number;
  coalition_formation: number;
  influence_concentration: number;
  platform_divergence: number;
}

export interface CompositeScores {
  attention_score: number | null;
  virality_potential: number | null;
  backlash_risk: number | null;
  memory_durability: number | null;
  conversion_potential: number | null;
  audience_fit: number | null;
  polarization_index: number | null;
}

// -- Data completeness tracking (Landmine 5) --

export interface DataCompleteness {
  tribe_available: boolean;
  mirofish_available: boolean;
  tribe_real_score_count: number;
  tribe_pseudo_score_count: number;
  missing_composite_dimensions: string[];
}

// -- Iteration record --

export interface IterationRecord {
  id: string;
  campaign_id: string;
  iteration_number: number;
  variant_id: string;
  variant_content: string;
  variant_strategy?: string | null;
  tribe_scores?: TribeScores | null;
  mirofish_metrics?: MirofishMetrics | null;
  composite_scores?: CompositeScores | null;
  data_completeness?: DataCompleteness | null;
  created_at: string;
}

// -- Analysis record --

export interface AnalysisRecord {
  id: string;
  campaign_id: string;
  iteration_number: number;
  analysis_json: Record<string, unknown>;
  system_availability?: Record<string, boolean> | null;
  created_at: string;
}

// -- Campaign response --

export interface CampaignResponse {
  id: string;
  status: CampaignStatus;
  seed_content: string;
  prediction_question: string;
  demographic: string;
  demographic_custom?: string | null;
  agent_count: number;
  max_iterations: number;
  iterations_completed?: number;
  thresholds?: Record<string, number> | null;
  constraints?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  iterations?: IterationRecord[] | null;
  analyses?: AnalysisRecord[] | null;
}

export interface CampaignListResponse {
  campaigns: CampaignResponse[];
  total: number;
}

// -- Report models (Layer 2 scorecard + full report response) --

export interface ScorecardVariant {
  variant_id: string;
  rank: number;
  strategy: string;
  composite_scores: Record<string, number | null>;
  color_coding: Record<string, string>;
}

export interface ScorecardData {
  winning_variant_id: string;
  variants: ScorecardVariant[];
  iteration_trajectory: Record<string, unknown>[];
  thresholds_status: Record<string, unknown>;
  summary: string;
}

export interface ReportResponse {
  id: string;
  campaign_id: string;
  verdict?: string | null;
  scorecard?: ScorecardData | null;
  deep_analysis?: Record<string, unknown> | null;
  mass_psychology_general?: string | null;
  mass_psychology_technical?: string | null;
  created_at: string;
}

// -- Health response --

export interface ServiceHealth {
  status: string;
  latency_ms: number | null;
}

export interface HealthResponse {
  orchestrator: string;
  tribe_scorer: ServiceHealth;
  mirofish: ServiceHealth;
  database: ServiceHealth;
}

// -- Demographics response --

export interface DemographicInfo {
  key: string;
  label: string;
  description: string;
}

export interface DemographicsResponse {
  presets: DemographicInfo[];
  supports_custom: boolean;
}

// -- Progress / estimate models (SSE streaming, D-09/D-10/OPT-05) --

export interface ProgressEvent {
  event: string;
  campaign_id: string;
  iteration: number;
  max_iterations: number;
  step?: string | null;
  step_index?: number | null;
  total_steps?: number | null;
  eta_seconds?: number | null;
  data?: Record<string, unknown> | null;
  timestamp: string;
}

export interface EstimateRequest {
  agent_count: number;
  max_iterations: number;
}

export interface EstimateResponse {
  estimated_minutes: number;
  agent_count: number;
  max_iterations: number;
  formula: string;
}

// -- Agent interview models (UI-08) --

export interface AgentChatRequest {
  message: string;
}

export interface AgentChatResponse {
  agent_id: string;
  response: string;
}
