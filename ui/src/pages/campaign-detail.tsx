/**
 * Campaign detail page with 3-tab structure.
 *
 * Tabs:
 * - Campaign: composite score cards, variant ranking, iteration trajectory (08-05)
 * - Simulation: MiroFish metrics, sentiment timeline, agent grid + interview (08-06)
 * - Report: generated report layers (08-07)
 *
 * Uses React Router useParams to fetch campaign data via useCampaign hook.
 */

import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useCampaign } from '@/hooks/use-campaigns';
import { CampaignDetailSkeleton } from '@/components/common/loading-skeleton';
import { ErrorState } from '@/components/common/error-state';
import { StatusBadge } from '@/components/common/status-badge';
import { ProgressStream } from '@/components/progress/progress-stream';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { MetricsPanel } from '@/components/simulation/metrics-panel';
import { SentimentTimeline } from '@/components/simulation/sentiment-timeline';
import { AgentGrid } from '@/components/simulation/agent-grid';
import { AgentInterview } from '@/components/simulation/agent-interview';
import type { AgentData } from '@/components/simulation/agent-grid';
import type { IterationRecord } from '@/api/types';
import { formatDate } from '@/utils/formatters';

/** Extract the latest iteration's metrics from the campaign data. */
function getLatestIteration(
  iterations: IterationRecord[] | null | undefined,
): IterationRecord | null {
  if (!iterations || iterations.length === 0) return null;
  return iterations.reduce((best, curr) =>
    curr.iteration_number > best.iteration_number ? curr : best,
  );
}

/** Extract agent data from iteration records for display in the grid. */
function extractAgents(
  iterations: IterationRecord[] | null | undefined,
): AgentData[] {
  // Agent data comes from MiroFish simulation results which are stored
  // in the raw simulation data. For now, we synthesize placeholders from
  // available iteration data. When MiroFish agent_stats are available in
  // the campaign response, this will pull real agent profiles.
  if (!iterations || iterations.length === 0) return [];

  // Check if any iteration has mirofish_metrics -- if so, simulation ran
  const hasSimulation = iterations.some((it) => it.mirofish_metrics != null);
  if (!hasSimulation) return [];

  // Generate representative agent set from metrics
  // In production, these come from /api/simulation/{id}/agent-stats
  // For now return empty to show the "no agents" state gracefully
  return [];
}

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: campaign, isLoading, error, refetch } = useCampaign(id ?? '');

  const [interviewAgent, setInterviewAgent] = useState<{
    id: string;
    name: string;
  } | null>(null);

  if (isLoading) return <CampaignDetailSkeleton />;

  if (error) {
    return (
      <ErrorState
        message={error instanceof Error ? error.message : 'Failed to load campaign'}
        onRetry={() => void refetch()}
      />
    );
  }

  if (!campaign) {
    return (
      <ErrorState message="Campaign not found." />
    );
  }

  const latestIteration = getLatestIteration(campaign.iterations);
  const mirofishMetrics = latestIteration?.mirofish_metrics ?? null;
  const sentimentTrajectory = mirofishMetrics?.sentiment_trajectory ?? null;
  const agents = extractAgents(campaign.iterations);

  return (
    <div className="flex flex-col gap-6">
      {/* Campaign header */}
      <div className="flex flex-col gap-2">
        <h1 className="text-xl font-semibold text-foreground">
          {campaign.prediction_question}
        </h1>
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge status={campaign.status} />
          <span className="text-xs text-muted-foreground">
            {campaign.demographic}
          </span>
          <span className="text-xs text-muted-foreground">
            {formatDate(campaign.created_at)}
          </span>
        </div>
      </div>

      {/* Progress stream for running campaigns */}
      {campaign.status === 'running' && id && (
        <ProgressStream campaignId={id} />
      )}

      {/* Error display for failed campaigns */}
      {campaign.status === 'failed' && campaign.error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3">
          <p className="text-sm text-destructive">{campaign.error}</p>
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="campaign">
        <TabsList variant="line">
          <TabsTrigger value="campaign">Campaign</TabsTrigger>
          <TabsTrigger value="simulation">Simulation</TabsTrigger>
          <TabsTrigger value="report">Report</TabsTrigger>
        </TabsList>

        {/* Campaign tab -- placeholder for 08-05 components */}
        <TabsContent value="campaign">
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <p className="text-sm text-muted-foreground">
              Campaign results view loading...
            </p>
          </div>
        </TabsContent>

        {/* Simulation tab -- fully implemented by 08-06 */}
        <TabsContent value="simulation">
          <div className="flex flex-col gap-6 pt-2">
            <MetricsPanel metrics={mirofishMetrics} />
            <SentimentTimeline trajectory={sentimentTrajectory} />
            <AgentGrid
              agents={agents}
              onInterviewAgent={(agentId, agentName) =>
                setInterviewAgent({ id: agentId, name: agentName })
              }
            />
          </div>
        </TabsContent>

        {/* Report tab -- placeholder for 08-07 */}
        <TabsContent value="report">
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <p className="text-sm text-muted-foreground">
              Report view loading...
            </p>
          </div>
        </TabsContent>
      </Tabs>

      {/* Agent interview modal */}
      {interviewAgent && id && (
        <AgentInterview
          campaignId={id}
          agentId={interviewAgent.id}
          agentName={interviewAgent.name}
          open={true}
          onOpenChange={(open) => {
            if (!open) setInterviewAgent(null);
          }}
        />
      )}
    </div>
  );
}
