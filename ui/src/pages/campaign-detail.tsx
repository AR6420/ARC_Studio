/**
 * Campaign detail page with 3 tabs: Campaign, Simulation, Report.
 *
 * Uses React Router useParams for campaign ID, fetches data via
 * useCampaign hook, and renders tab-specific content. All three tabs
 * fully wired: Campaign (score cards, variant ranking, iteration chart),
 * Simulation (metrics, sentiment, agent grid, interview modal),
 * Report (4 layers + export).
 */

import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { FileBarChart, Activity, FileText, Clock } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusBadge } from '@/components/common/status-badge';
import { ErrorState } from '@/components/common/error-state';
import { CampaignDetailSkeleton } from '@/components/common/loading-skeleton';
import { useCampaign } from '@/hooks/use-campaigns';
import { useReport } from '@/hooks/use-report';
import { VerdictDisplay } from '@/components/results/verdict-display';
import { ScorecardTable } from '@/components/results/scorecard-table';
import { DeepAnalysis } from '@/components/results/deep-analysis';
import { MassPsychology } from '@/components/results/mass-psychology';
import { ExportButtons } from '@/components/results/export-buttons';
import { ScoreCard } from '@/components/results/score-card';
import { VariantRanking } from '@/components/results/variant-ranking';
import { IterationChart } from '@/components/results/iteration-chart';
import { MetricsPanel } from '@/components/simulation/metrics-panel';
import { SentimentTimeline } from '@/components/simulation/sentiment-timeline';
import { AgentGrid } from '@/components/simulation/agent-grid';
import { AgentInterview } from '@/components/simulation/agent-interview';
import { ProgressStream } from '@/components/progress/progress-stream';
import { formatDate } from '@/utils/formatters';
import type { AgentData } from '@/components/simulation/agent-grid';
import type { CampaignResponse, CompositeScores } from '@/api/types';

// -- Constants for composite score display --

const COMPOSITE_KEYS: (keyof CompositeScores)[] = [
  'attention_score',
  'virality_potential',
  'conversion_potential',
  'audience_fit',
  'memory_durability',
  'backlash_risk',
  'polarization_index',
];

const SCORE_DESCRIPTIONS: Record<string, string> = {
  attention_score: 'How strongly the content captures and holds attention',
  virality_potential: 'Likelihood of organic sharing and spread',
  conversion_potential: 'Ability to drive desired action',
  audience_fit: 'Resonance with the target demographic',
  memory_durability: 'How well content sticks in long-term memory',
  backlash_risk: 'Risk of negative backlash (lower is better)',
  polarization_index: 'Degree of opinion polarization (lower is better)',
};

// -- Campaign tab content --

function CampaignTabContent({ campaign }: { campaign: CampaignResponse }) {
  const iterations = campaign.iterations ?? [];

  if (iterations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <p className="text-sm text-muted-foreground">
          No iteration data available yet.
        </p>
      </div>
    );
  }

  // Find the latest iteration number
  const maxIterNum = Math.max(...iterations.map((it) => it.iteration_number));

  // Get all variants from the latest iteration
  const latestIterations = iterations.filter(
    (it) => it.iteration_number === maxIterNum,
  );

  // Find the best variant by average non-null composite score
  let bestScores: CompositeScores | null = null;
  let bestAvg = -1;

  for (const variant of latestIterations) {
    if (!variant.composite_scores) continue;
    const vals = COMPOSITE_KEYS.map((k) => variant.composite_scores![k]).filter(
      (v): v is number => v !== null,
    );
    if (vals.length === 0) continue;
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    if (avg > bestAvg) {
      bestAvg = avg;
      bestScores = variant.composite_scores;
    }
  }

  return (
    <div className="space-y-8">
      {/* Composite Scores */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-foreground">
          Composite Scores
        </h3>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {COMPOSITE_KEYS.map((key) => (
            <ScoreCard
              key={key}
              name={key}
              value={bestScores?.[key] ?? null}
              description={SCORE_DESCRIPTIONS[key]}
            />
          ))}
        </div>
      </div>

      {/* Variant Ranking */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-foreground">
          Variant Ranking
        </h3>
        <VariantRanking variants={latestIterations} />
      </div>

      {/* Score Trajectory */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-foreground">
          Score Trajectory
        </h3>
        <IterationChart iterations={iterations} />
      </div>
    </div>
  );
}

// -- Simulation tab content --

function SimulationTabContent({
  campaign,
  onInterviewAgent,
}: {
  campaign: CampaignResponse;
  onInterviewAgent: (agentId: string, agentName: string) => void;
}) {
  const iterations = campaign.iterations ?? [];

  if (iterations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <p className="text-sm text-muted-foreground">
          No simulation data available yet.
        </p>
      </div>
    );
  }

  // Find the latest iteration (single record with max iteration_number)
  const maxIterNum = Math.max(...iterations.map((it) => it.iteration_number));
  const latestIteration = iterations.find(
    (it) => it.iteration_number === maxIterNum,
  );

  const metrics = latestIteration?.mirofish_metrics ?? null;
  const trajectory = metrics?.sentiment_trajectory ?? null;

  // Agent data not available in API response (known limitation from 08-06)
  const agents: AgentData[] = [];

  return (
    <div className="space-y-8">
      <MetricsPanel metrics={metrics} />
      <SentimentTimeline trajectory={trajectory} />
      <AgentGrid agents={agents} onInterviewAgent={onInterviewAgent} />
    </div>
  );
}

// -- Report tab helpers --

/** Report tab skeleton for loading state. */
function ReportSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-6 w-48" />
      <div className="space-y-3">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-4/6" />
      </div>
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}

/** Report tab content with all 4 layers + export buttons. */
function ReportTabContent({ campaign }: { campaign: CampaignResponse }) {
  const {
    data: report,
    isLoading,
    isError,
    error,
    refetch,
  } = useReport(campaign.id);

  if (campaign.status !== 'completed') {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <div className="flex size-12 items-center justify-center rounded-xl bg-muted/50">
          <Clock className="size-6 text-muted-foreground/60" />
        </div>
        <p className="text-sm font-medium text-foreground/80">
          Campaign must complete before report is available
        </p>
        <p className="text-xs text-muted-foreground">
          The report will be generated once all iterations finish.
        </p>
      </div>
    );
  }

  if (isLoading) {
    return <ReportSkeleton />;
  }

  if (isError) {
    const message =
      error instanceof Error ? error.message : 'Failed to load report';
    // 404 means report not yet generated
    if (message.includes('404') || message.includes('not found')) {
      return (
        <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
          <div className="flex size-12 items-center justify-center rounded-xl bg-muted/50">
            <FileText className="size-6 text-muted-foreground/60" />
          </div>
          <p className="text-sm font-medium text-foreground/80">
            Report not yet generated
          </p>
          <p className="text-xs text-muted-foreground">
            The report generation may still be in progress.
          </p>
        </div>
      );
    }
    return (
      <ErrorState
        message={message}
        onRetry={() => void refetch()}
      />
    );
  }

  if (!report) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <div className="flex size-12 items-center justify-center rounded-xl bg-muted/50">
          <FileText className="size-6 text-muted-foreground/60" />
        </div>
        <p className="text-sm text-muted-foreground">
          No report data available
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Export buttons - top right */}
      <div className="flex justify-end">
        <ExportButtons campaignId={campaign.id} />
      </div>

      {/* Layer 1: Verdict */}
      <VerdictDisplay verdict={report.verdict ?? null} />

      <Separator className="opacity-40" />

      {/* Layer 2: Scorecard */}
      <ScorecardTable scorecard={report.scorecard ?? null} />

      <Separator className="opacity-40" />

      {/* Layer 3: Deep Analysis (collapsed by default) */}
      <DeepAnalysis
        deepAnalysis={
          (report.deep_analysis as Record<string, unknown>) ?? null
        }
      />

      <Separator className="opacity-40" />

      {/* Layer 4: Mass Psychology */}
      <MassPsychology
        general={report.mass_psychology_general ?? null}
        technical={report.mass_psychology_technical ?? null}
      />
    </div>
  );
}

// -- Main component --

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: campaign, isLoading, isError, error, refetch } = useCampaign(id!);
  const [interviewAgent, setInterviewAgent] = useState<{ id: string; name: string } | null>(null);

  const handleInterviewAgent = (agentId: string, agentName: string) =>
    setInterviewAgent({ id: agentId, name: agentName });

  if (isLoading) {
    return <CampaignDetailSkeleton />;
  }

  if (isError || !campaign) {
    return (
      <ErrorState
        message={
          error instanceof Error
            ? error.message
            : 'Failed to load campaign'
        }
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Campaign header */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-foreground">
            {campaign.prediction_question}
          </h1>
          <StatusBadge status={campaign.status} />
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>{campaign.demographic}</span>
          <span className="text-foreground/20">&middot;</span>
          <span>
            {campaign.agent_count} agents, {campaign.max_iterations} iterations
          </span>
          <span className="text-foreground/20">&middot;</span>
          <span>{formatDate(campaign.created_at)}</span>
        </div>
      </div>

      {/* Real-time progress for running campaigns */}
      {campaign.status === 'running' && <ProgressStream campaignId={id!} />}

      {/* Tabs */}
      <Tabs defaultValue="campaign">
        <TabsList variant="line" className="gap-0">
          <TabsTrigger value="campaign" className="gap-1.5">
            <FileBarChart className="size-3.5" />
            Campaign
          </TabsTrigger>
          <TabsTrigger value="simulation" className="gap-1.5">
            <Activity className="size-3.5" />
            Simulation
          </TabsTrigger>
          <TabsTrigger value="report" className="gap-1.5">
            <FileText className="size-3.5" />
            Report
          </TabsTrigger>
        </TabsList>

        <TabsContent value="campaign" className="pt-6">
          <CampaignTabContent campaign={campaign} />
        </TabsContent>

        <TabsContent value="simulation" className="pt-6">
          <SimulationTabContent campaign={campaign} onInterviewAgent={handleInterviewAgent} />
        </TabsContent>

        <TabsContent value="report" className="pt-6">
          <ReportTabContent campaign={campaign} />
        </TabsContent>
      </Tabs>

      {/* Agent interview modal */}
      <AgentInterview
        campaignId={campaign.id}
        agentId={interviewAgent?.id ?? ''}
        agentName={interviewAgent?.name ?? ''}
        open={interviewAgent !== null}
        onOpenChange={(open) => { if (!open) setInterviewAgent(null); }}
      />
    </div>
  );
}
