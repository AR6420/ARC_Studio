/**
 * Runtime config hook — fetches /api/config once per session.
 *
 * Surface the live LLM tier names (Qwen on the AMD hackathon stack,
 * Haiku/Opus on the dev box) to anywhere in the UI that wants to label
 * the orchestrator/agent tier — currently the StageIndicator subtitles.
 */

import { useQuery } from '@tanstack/react-query';
import { getConfig } from '@/api/campaigns';

export function useConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: getConfig,
    staleTime: Infinity,
  });
}
