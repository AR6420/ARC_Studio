/**
 * Health polling hook.
 *
 * Polls the /api/health endpoint every 60 seconds to display
 * service status indicators in the UI header.
 */

import { useQuery } from '@tanstack/react-query';
import { getHealth } from '@/api/campaigns';

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 60_000,
  });
}
