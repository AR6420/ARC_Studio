/**
 * Campaign detail page — three tabs: Campaign, Simulation, Report.
 *
 * Header is a dense monospace metadata strip (status, demographic,
 * counts, created). Data completeness and pseudo-score indicators
 * appear as small eyebrow lines at the top of each tab so the reader
 * knows whether they're looking at real or fallback data.
 */

import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { StatusBadge } from '@/components/common/status-badge';
import { ErrorState } from '@/components/common/error-state';
import { useCampaign } from '@/hooks/use-campaigns';
import { useReport } from '@/hooks/use-report';
import { VerdictDisplay } from '@/components/results/verdict-display';
import { ScorecardTable } from '@/components/results/scorecard-table';
import { DeepAnalysis } from '@/components/results/deep-analysis';
import { MassPsychology } from '@/components/results/mass-psychology';
import { ExportButtons } from '@/components/results/export-buttons';
import { ScoreBar } from '@/components/results/score-bar';
import { VariantRanking } from '@/components/results/variant-ranking';
import { IterationChart } from '@/components/results/iteration-chart';
import { MetricsPanel } from '@/components/simulation/metrics-panel';
import { SentimentTimeline } from '@/components/simulation/sentiment-timeline';
import { AgentGrid } from '@/components/simulation/agent-grid';
import { AgentInterview } from '@/components/simulation/agent-interview';
import { ProgressStream } from '@/components/progress/progress-stream';
import { formatRelative } from '@/utils/formatters';
import type { AgentData } from '@/components/simulation/agent-grid';
import type {
  CampaignResponse,
  CompositeScores,
  IterationRecord,
  DataCompleteness,
} from '@/api/types';

const COMPOSITE_KEYS: (keyof CompositeScores)[] = [
  'attention_score',
  'virality_potential',
  'conversion_potential',
  'audience_fit',
  'memory_durability',
  'backlash_risk',
  'polarization_index',
];

// ─── Data completeness status line ──────────────────────────────────────

function DataCompletenessLine({
  completeness,
  pseudo,
}: {
  completeness: DataCompleteness | null;
  pseudo: boolean;
}) {
  if (!completeness && !pseudo) return null;

  const tribeAvail = completeness?.tribe_available ?? true;
  const mfAvail = completeness?.mirofish_available ?? true;
  const real = completeness?.tribe_real_score_count ?? 0;
  const ps = completeness?.tribe_pseudo_score_count ?? 0;
  const total = real + ps;
  const missing = completeness?.missing_composite_dimensions ?? [];

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 font-mono text-[0.68rem] text-muted-foreground/80">
      <span className="flex items-center gap-1.5">
        <span className="tracking-[0.1em] text-muted-foreground/55 uppercase">
          tribe
        </span>
        <span
          className={tribeAvail ? 'text-tribe' : 'text-muted-foreground/40'}
        >
          {total > 0 ? `${real}/${total} real` : tribeAvail ? 'ok' : 'down'}
        </span>
      </span>
      <span className="flex items-center gap-1.5">
        <span className="tracking-[0.1em] text-muted-foreground/55 uppercase">
          mirofish
        </span>
        <span
          className={mfAvail ? 'text-mirofish' : 'text-muted-foreground/40'}
        >
          {mfAvail ? 'ok' : 'down'}
        </span>
      </span>
      {missing.length > 0 && (
        <span className="flex items-center gap-1.5">
          <span className="tracking-[0.1em] text-muted-foreground/55 uppercase">
            missing
          </span>
          <span className="text-heat-mid">
            {missing.length} dim{missing.length !== 1 ? 's' : ''}
          </span>
        </span>
      )}
      {pseudo && (
        <span className="tracking-[0.1em] text-heat-mid/80 uppercase">
          · pseudo scores in use
        </span>
      )}
    </div>
  );
}

// ─── Campaign tab ───────────────────────────────────────────────────────

function findBestVariant(variants: IterationRecord[]): IterationRecord | null {
  let best: IterationRecord | null = null;
  let bestAvg = -1;
  for (const variant of variants) {
    if (!variant.composite_scores) continue;
    const vals = COMPOSITE_KEYS.map(
      (k) => variant.composite_scores![k],
    ).filter((v): v is number => v !== null);
    if (!vals.length) continue;
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    if (avg > bestAvg) {
      bestAvg = avg;
      best = variant;
    }
  }
  return best;
}

function CampaignTabContent({ campaign }: { campaign: CampaignResponse }) {
  const iterations = campaign.iterations ?? [];

  const { latestIterations, bestVariant, completeness, hasPseudo } =
    useMemo(() => {
      if (iterations.length === 0) {
        return {
          latestIterations: [],
          bestVariant: null,
          completeness: null,
          hasPseudo: false,
        };
      }
      const maxIterNum = Math.max(...iterations.map((it) => it.iteration_number));
      const latest = iterations.filter((it) => it.iteration_number === maxIterNum);
      const best = findBestVariant(latest);
      const completeness = best?.data_completeness ?? null;
      const hasPseudo = latest.some(
        (v) => v.tribe_scores?.is_pseudo_score === true,
      );
      return {
        latestIterations: latest,
        bestVariant: best,
        completeness,
        hasPseudo,
      };
    }, [iterations]);

  if (iterations.length === 0) {
    return (
      <p className="font-mono text-[0.72rem] text-muted-foreground/55">
        › no iteration data available yet
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <DataCompletenessLine completeness={completeness} pseudo={hasPseudo} />

      {/* Composite profile — 7 horizontal bars */}
      <section className="flex flex-col gap-4">
        <div className="flex items-baseline justify-between border-b border-border pb-2">
          <div className="flex items-baseline gap-3">
            <span className="font-mono text-[0.6rem] font-semibold tracking-[0.18em] text-foreground/90 uppercase">
              Composite Profile
            </span>
            <span className="font-mono text-[0.58rem] tracking-[0.12em] text-muted-foreground/50 uppercase">
              best variant · latest iteration
            </span>
          </div>
          {bestVariant && (
            <span className="font-mono text-[0.62rem] tabular-nums text-muted-foreground/60">
              {bestVariant.variant_id.slice(0, 8)}
            </span>
          )}
        </div>
        <div className="grid grid-cols-1 gap-y-2 sm:grid-cols-2 sm:gap-x-10">
          {COMPOSITE_KEYS.map((key) => (
            <ScoreBar
              key={key}
              name={key}
              value={bestVariant?.composite_scores?.[key] ?? null}
            />
          ))}
        </div>
      </section>

      {/* Variant ranking */}
      <section className="flex flex-col gap-4">
        <div className="flex items-baseline justify-between border-b border-border pb-2">
          <span className="font-mono text-[0.6rem] font-semibold tracking-[0.18em] text-foreground/90 uppercase">
            Variant Ranking
          </span>
          <span className="font-mono text-[0.58rem] tracking-[0.12em] text-muted-foreground/50 uppercase">
            {latestIterations.length} variant{latestIterations.length !== 1 ? 's' : ''}
          </span>
        </div>
        <VariantRanking variants={latestIterations} />
      </section>

      {/* Iteration trajectory */}
      <section className="flex flex-col gap-4">
        <div className="flex items-baseline justify-between border-b border-border pb-2">
          <span className="font-mono text-[0.6rem] font-semibold tracking-[0.18em] text-foreground/90 uppercase">
            Iteration Trajectory
          </span>
          <span className="font-mono text-[0.58rem] tracking-[0.12em] text-muted-foreground/50 uppercase">
            best score per iteration
          </span>
        </div>
        <IterationChart iterations={iterations} />
      </section>
    </div>
  );
}

// ─── Simulation tab ─────────────────────────────────────────────────────

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
      <p className="font-mono text-[0.72rem] text-muted-foreground/55">
        › no simulation data available yet
      </p>
    );
  }

  const maxIterNum = Math.max(...iterations.map((it) => it.iteration_number));
  const latestIteration = iterations.find(
    (it) => it.iteration_number === maxIterNum,
  );
  const metrics = latestIteration?.mirofish_metrics ?? null;
  const trajectory = metrics?.sentiment_trajectory ?? null;
  const completeness = latestIteration?.data_completeness ?? null;
  const agents: AgentData[] = [];

  return (
    <div className="flex flex-col gap-8">
      <DataCompletenessLine completeness={completeness} pseudo={false} />
      <MetricsPanel metrics={metrics} />
      <SentimentTimeline trajectory={trajectory} />
      <AgentGrid agents={agents} onInterviewAgent={onInterviewAgent} />
    </div>
  );
}

// ─── Report tab ─────────────────────────────────────────────────────────

function ReportTabContent({ campaign }: { campaign: CampaignResponse }) {
  const {
    data: report,
    isLoading,
    isError,
    error,
    refetch,
  } = useReport(campaign.id);

  if (campaign.status !== 'completed' && campaign.status !== 'failed') {
    return (
      <div className="flex flex-col gap-3">
        <p className="font-mono text-[0.72rem] text-muted-foreground/55">
          › report generates after campaign completes
        </p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="border border-border bg-surface-1 px-4 py-3 font-mono text-[0.7rem] text-muted-foreground/70">
        <span className="mr-2 inline-block size-1 rounded-full bg-primary/80 align-middle" />
        loading report…
      </div>
    );
  }

  if (isError) {
    const message =
      error instanceof Error ? error.message : 'Failed to load report';
    if (message.includes('404') || message.includes('not found')) {
      return (
        <p className="font-mono text-[0.72rem] text-muted-foreground/55">
          › report not yet generated — check back shortly
        </p>
      );
    }
    return <ErrorState message={message} onRetry={() => void refetch()} />;
  }

  if (!report) {
    return (
      <p className="font-mono text-[0.72rem] text-muted-foreground/55">
        › no report data available
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-10">
      <div className="flex justify-end">
        <ExportButtons campaignId={campaign.id} />
      </div>
      <VerdictDisplay verdict={report.verdict ?? null} />
      <ScorecardTable scorecard={report.scorecard ?? null} />
      <DeepAnalysis
        deepAnalysis={
          (report.deep_analysis as Record<string, unknown>) ?? null
        }
      />
      <MassPsychology
        general={report.mass_psychology_general ?? null}
        technical={report.mass_psychology_technical ?? null}
      />
    </div>
  );
}

// ─── Main component ─────────────────────────────────────────────────────

function CampaignHeader({ campaign }: { campaign: CampaignResponse }) {
  return (
    <div className="flex flex-col gap-3 border-b border-border pb-5">
      <div className="flex flex-col gap-1">
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-[0.6rem] tracking-[0.14em] text-muted-foreground/60 uppercase">
            campaign · {campaign.id.slice(0, 8)}
          </span>
          <StatusBadge status={campaign.status} />
        </div>
        <h1 className="text-[1.15rem] font-semibold leading-tight tracking-[-0.01em] text-foreground">
          {campaign.prediction_question}
        </h1>
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 font-mono text-[0.68rem] tabular-nums text-muted-foreground">
        <span className="flex items-baseline gap-1.5">
          <span className="tracking-[0.1em] text-muted-foreground/55 uppercase">
            demographic
          </span>
          <span className="text-foreground/85">{campaign.demographic}</span>
        </span>
        <span className="flex items-baseline gap-1.5">
          <span className="tracking-[0.1em] text-muted-foreground/55 uppercase">
            agents
          </span>
          <span className="text-foreground/85">{campaign.agent_count}</span>
        </span>
        <span className="flex items-baseline gap-1.5">
          <span className="tracking-[0.1em] text-muted-foreground/55 uppercase">
            iters
          </span>
          <span className="text-foreground/85">
            {campaign.iterations?.length ?? 0}/{campaign.max_iterations}
          </span>
        </span>
        <span className="flex items-baseline gap-1.5">
          <span className="tracking-[0.1em] text-muted-foreground/55 uppercase">
            created
          </span>
          <span className="text-foreground/85">
            {formatRelative(campaign.created_at)}
          </span>
        </span>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="border border-border bg-surface-1 px-4 py-3 font-mono text-[0.7rem] text-muted-foreground/70">
      <span className="mr-2 inline-block size-1 rounded-full bg-primary/80 align-middle" />
      loading campaign…
    </div>
  );
}

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: campaign, isLoading, isError, error, refetch } = useCampaign(id!);
  const [interviewAgent, setInterviewAgent] = useState<{
    id: string;
    name: string;
  } | null>(null);

  const handleInterviewAgent = (agentId: string, agentName: string) =>
    setInterviewAgent({ id: agentId, name: agentName });

  if (isLoading) return <LoadingState />;

  if (isError || !campaign) {
    return (
      <ErrorState
        message={
          error instanceof Error ? error.message : 'Failed to load campaign'
        }
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <CampaignHeader campaign={campaign} />

      {campaign.status === 'running' && <ProgressStream campaignId={id!} />}

      <Tabs defaultValue="campaign" className="gap-6">
        <TabsList variant="line">
          <TabsTrigger value="campaign">Campaign</TabsTrigger>
          <TabsTrigger value="simulation">Simulation</TabsTrigger>
          <TabsTrigger value="report">Report</TabsTrigger>
        </TabsList>

        <TabsContent value="campaign" className="pt-4">
          <CampaignTabContent campaign={campaign} />
        </TabsContent>

        <TabsContent value="simulation" className="pt-4">
          <SimulationTabContent
            campaign={campaign}
            onInterviewAgent={handleInterviewAgent}
          />
        </TabsContent>

        <TabsContent value="report" className="pt-4">
          <ReportTabContent campaign={campaign} />
        </TabsContent>
      </Tabs>

      <AgentInterview
        campaignId={campaign.id}
        agentId={interviewAgent?.id ?? ''}
        agentName={interviewAgent?.name ?? ''}
        open={interviewAgent !== null}
        onOpenChange={(open) => {
          if (!open) setInterviewAgent(null);
        }}
      />
    </div>
  );
}
