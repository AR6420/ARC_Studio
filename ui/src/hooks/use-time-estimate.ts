/**
 * Debounced time estimate hook.
 *
 * Calls POST /api/estimate with agent_count and max_iterations
 * to get an estimated campaign duration. Only enabled when both
 * parameters are valid (within backend-accepted ranges).
 */

import { useQuery } from '@tanstack/react-query';
import { getEstimate } from '@/api/campaigns';

export function useTimeEstimate(agentCount: number, maxIterations: number) {
  const isValid = agentCount >= 20 && agentCount <= 200
    && maxIterations >= 1 && maxIterations <= 10;

  return useQuery({
    queryKey: ['estimate', agentCount, maxIterations],
    queryFn: () => getEstimate({ agent_count: agentCount, max_iterations: maxIterations }),
    enabled: isValid,
    staleTime: 10_000,
  });
}
