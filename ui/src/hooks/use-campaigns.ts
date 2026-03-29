/**
 * React Query hooks for campaign data fetching.
 *
 * Per RESEARCH.md Pattern 4:
 * - useCampaign polls every 3s while status='running', else stops
 * - useCampaigns fetches the list without polling
 * - useCreateCampaign / useDeleteCampaign invalidate the campaigns list on success
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import {
  createCampaign,
  deleteCampaign,
  getCampaign,
  listCampaigns,
} from '@/api/campaigns';
import type { CampaignCreateRequest } from '@/api/types';

export function useCampaign(id: string) {
  return useQuery({
    queryKey: ['campaign', id],
    queryFn: () => getCampaign(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'running' ? 3000 : false;
    },
  });
}

export function useCampaigns() {
  return useQuery({
    queryKey: ['campaigns'],
    queryFn: listCampaigns,
  });
}

export function useCreateCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CampaignCreateRequest) => createCampaign(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    },
  });
}

export function useDeleteCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteCampaign(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    },
  });
}
