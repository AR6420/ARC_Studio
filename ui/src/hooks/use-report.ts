/**
 * React Query hook for fetching campaign report data.
 *
 * Wraps getReport API call with caching and error handling.
 * Only fetches when a valid campaignId is provided.
 */

import { useQuery } from '@tanstack/react-query';
import { getReport } from '@/api/reports';

export function useReport(campaignId: string) {
  return useQuery({
    queryKey: ['report', campaignId],
    queryFn: () => getReport(campaignId),
    retry: 1,
    enabled: !!campaignId,
  });
}
