/**
 * Report API functions.
 *
 * Maps to orchestrator/api/reports.py endpoints.
 */

import { apiFetch, API_BASE } from './client';
import type { ReportResponse } from './types';

export function getReport(campaignId: string): Promise<ReportResponse> {
  return apiFetch<ReportResponse>(`/api/campaigns/${campaignId}/report`);
}

/**
 * Trigger a file download for campaign export.
 *
 * Uses window.open instead of fetch because the backend sets
 * Content-Disposition headers for file download (per Pitfall 7).
 */
export function downloadExport(
  campaignId: string,
  format: 'json' | 'markdown',
): void {
  window.open(
    `${API_BASE}/api/campaigns/${campaignId}/export/${format}`,
    '_blank',
  );
}
