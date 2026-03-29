/**
 * Campaign API functions.
 *
 * Maps to orchestrator/api/campaigns.py and orchestrator/api/health.py endpoints.
 */

import { apiFetch } from './client';
import type {
  CampaignCreateRequest,
  CampaignListResponse,
  CampaignResponse,
  DemographicsResponse,
  EstimateRequest,
  EstimateResponse,
  HealthResponse,
} from './types';

export function createCampaign(
  body: CampaignCreateRequest,
): Promise<CampaignResponse> {
  return apiFetch<CampaignResponse>('/api/campaigns', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function getCampaign(id: string): Promise<CampaignResponse> {
  return apiFetch<CampaignResponse>(`/api/campaigns/${id}`);
}

export function listCampaigns(): Promise<CampaignListResponse> {
  return apiFetch<CampaignListResponse>('/api/campaigns');
}

export function deleteCampaign(id: string): Promise<void> {
  return apiFetch<void>(`/api/campaigns/${id}`, {
    method: 'DELETE',
  });
}

export function getDemographics(): Promise<DemographicsResponse> {
  return apiFetch<DemographicsResponse>('/api/demographics');
}

export function getEstimate(
  body: EstimateRequest,
): Promise<EstimateResponse> {
  return apiFetch<EstimateResponse>('/api/estimate', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/api/health');
}
