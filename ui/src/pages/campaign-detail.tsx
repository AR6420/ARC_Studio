/**
 * Campaign detail page — three tabs: Campaign, Simulation, Report.
 *
 * Iteration selection is lifted to this page so the Campaign tab and
 * the Report tab's Scorecard share the same active iteration. Clicking
 * an i1/i2/i3 button anywhere updates composite profile, variant
 * ranking, and (when possible) the scorecard variants.
 */

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { StatusBadge } from '@/components/common/status-badge';
import { ErrorState } from '@/components/common/error-state';
import { cn } from '@/lib/utils';
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
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 font-mono text-[0.7rem] text-foreground/80">
      <span className="flex items-center gap-1.5">
        <span className="tracking-[0.1em] text-muted-foreground uppercase">
          tribe
        </span>
        <span className={tribeAvail ? 'text-tribe' : 'text-muted-foreground'}>
          {total > 0 ? `${real}/${total} real` : tribeAvail ? 'ok' : 'down'}
        </span>
      </span>
      <span className="flex items-center gap-1.5">
        <span className="tracking-[0.1em] text-muted-foreground uppercase">
          mirofish
        </span>
        <span className={mfAvail ? 'text-mirofish' : 'text-muted-foreground'}>
          {mfAvail ? 'ok' : 'down'}
        </span>
      </span>
      {missing.length > 0 && (
        <span className="flex items-center gap-1.5">
          <span className="tracking-[0.1em] text-muted-foreground uppercase">
            missing
          </span>
          <span className="text-heat-mid">
            {missing.length} dim{missing.length !== 1 ? 's' : ''}
          </span>
        </span>
      )}
      {pseudo && (
        <span className="tracking-[0.1em] text-heat-mid uppercase">
          · pseudo scores in use
        </span>
      )}
    </div>
  );
}

// ─── Iteration selector pills ───────────────────────────────────────────

function IterationPills({
  available,
  selected,
  onSelect,
}: {
  available: number[];
  selected: number;
  onSelect: (i: number) => void;
}) {
  if (available.length <= 1) return null;
  return (
    <div className="flex items-center gap-1">
      {available.map((i) => {
        const isActive = i === selected;
        return (
          <button
            key={i}
            type="button"
            onClick={() => {
              if (!isActive) onSelect(i);
            }}
            aria-pressed={isActive}
            className={cn(
              'inline-flex items-center rounded-sm border px-2 py-0.5 font-mono text-[0.7rem] tabular-nums transition-colors',
              isActive
                ? 'border-primary/60 bg-primary/15 text-primary cursor-default'
                : 'border-border bg-transparent text-muted-foreground hover:border-foreground/30 hover:text-foreground',
            )}
          >
            i{i}
          </button>
        );
      })}
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

function CampaignTabContent({
  campaign,
  selectedIteration,
  availableIterations,
  onSelectIteration,
}: {
  campaign: CampaignResponse;
  selectedIteration: number;
  availableIterations: number[];
  onSelectIteration: (i: number) => void;
}) {
  const iterations = campaign.iterations ?? [];

  const { iterationVariants, bestVariant, completeness, hasPseudo, missingDims } =
    useMemo(() => {
      if (iterations.length === 0) {
        return {
          iterationVariants: [] as IterationRecord[],
          bestVariant: null as IterationRecord | null,
          completeness: null as DataCompleteness | null,
          hasPseudo: false,
          missingDims: [] as (keyof CompositeScores)[],
        };
      }
      const scoped = iterations.filter(
        (it) => it.iteration_number === selectedIteration,
      );
      const best = findBestVariant(scoped);
      const completeness = best?.data_completeness ?? null;
      const hasPseudo = scoped.some(
        (v) => v.tribe_scores?.is_pseudo_score === true,
      );
      const missing: (keyof CompositeScores)[] = best?.composite_scores
        ? COMPOSITE_KEYS.filter(
            (k) => best.composite_scores![k] == null,
          )
        : [];
      return {
        iterationVariants: scoped,
        bestVariant: best,
        completeness,
        hasPseudo,
        missingDims: missing,
      };
    }, [iterations, selectedIteration]);

  if (iterations.length === 0) {
    return (
      <p className="font-mono text-[0.74rem] text-muted-foreground">
        › no iteration data available yet
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <DataCompletenessLine completeness={completeness} pseudo={hasPseudo} />

      {/* Composite profile — 7 horizontal bars */}
      <section className="flex flex-col gap-4">
        <div className="flex items-baseline justify-between gap-4 border-b border-border pb-2">
          <div className="flex items-baseline gap-3">
            <h2 className="text-[1rem] font-medium tracking-[-0.005em] text-foreground">
              Composite profile
            </h2>
            <span className="font-mono text-[0.62rem] tracking-[0.1em] text-muted-foreground uppercase">
              best variant · iter {selectedIteration}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <IterationPills
              available={availableIterations}
              selected={selectedIteration}
              onSelect={onSelectIteration}
            />
            {bestVariant && (
              <span className="font-mono text-[0.64rem] tabular-nums text-muted-foreground">
                {bestVariant.variant_id.slice(0, 8)}
              </span>
            )}
          </div>
        </div>

        {missingDims.length > 0 && (
          <p className="font-mono text-[0.68rem] text-muted-foreground">
            › some dimensions unavailable — see data completeness above
          </p>
        )}

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
          <div className="flex items-baseline gap-3">
            <h2 className="text-[1rem] font-medium tracking-[-0.005em] text-foreground">
              Variant ranking
            </h2>
            <span className="font-mono text-[0.62rem] tracking-[0.1em] text-muted-foreground uppercase">
              iter {selectedIteration}
            </span>
          </div>
          <span className="font-mono text-[0.64rem] tabular-nums text-muted-foreground">
            {iterationVariants.length.toString().padStart(2, '0')} variant
            {iterationVariants.length !== 1 ? 's' : ''}
          </span>
        </div>
        <VariantRanking variants={iterationVariants} />
      </section>

      {/* Iteration trajectory */}
      <section className="flex flex-col gap-4">
        <div className="flex items-baseline justify-between border-b border-border pb-2">
          <h2 className="text-[1rem] font-medium tracking-[-0.005em] text-foreground">
            Iteration trajectory
          </h2>
          <span className="font-mono text-[0.62rem] tracking-[0.1em] text-muted-foreground uppercase">
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
  selectedIteration,
  onInterviewAgent,
}: {
  campaign: CampaignResponse;
  selectedIteration: number;
  onInterviewAgent: (agentId: string, agentName: string) => void;
}) {
  const iterations = campaign.iterations ?? [];

  if (iterations.length === 0) {
    return (
      <p className="font-mono text-[0.74rem] text-muted-foreground">
        › no simulation data available yet
      </p>
    );
  }

  const scopedIteration = iterations.find(
    (it) => it.iteration_number === selectedIteration,
  );
  const metrics = scopedIteration?.mirofish_metrics ?? null;
  const trajectory = metrics?.sentiment_trajectory ?? null;
  const completeness = scopedIteration?.data_completeness ?? null;
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

function ReportTabContent({
  campaign,
  selectedIteration,
  availableIterations,
  variantIterationMap,
  onSelectIteration,
}: {
  campaign: CampaignResponse;
  selectedIteration: number;
  availableIterations: number[];
  variantIterationMap: Map<string, number>;
  onSelectIteration: (i: number) => void;
}) {
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
        <p className="font-mono text-[0.74rem] text-muted-foreground">
          › report generates after campaign completes
        </p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="border border-border bg-surface-1 px-4 py-3 font-mono text-[0.72rem] text-muted-foreground">
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
        <p className="font-mono text-[0.74rem] text-muted-foreground">
          › report not yet generated — check back shortly
        </p>
      );
    }
    return <ErrorState message={message} onRetry={() => void refetch()} />;
  }

  if (!report) {
    return (
      <p className="font-mono text-[0.74rem] text-muted-foreground">
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
      <ScorecardTable
        scorecard={report.scorecard ?? null}
        selectedIteration={selectedIteration}
        onSelectIteration={onSelectIteration}
        variantIterationMap={variantIterationMap}
        availableIterations={availableIterations}
      />
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
          <span className="font-mono text-[0.62rem] tracking-[0.12em] text-muted-foreground uppercase">
            campaign · {campaign.id.slice(0, 8)}
          </span>
          <StatusBadge status={campaign.status} />
        </div>
        <h1 className="text-[1.15rem] font-semibold leading-tight tracking-[-0.01em] text-foreground">
          {campaign.prediction_question}
        </h1>
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 font-mono text-[0.7rem] tabular-nums text-foreground/85">
        <span className="flex items-baseline gap-1.5">
          <span className="tracking-[0.1em] text-muted-foreground uppercase">
            demographic
          </span>
          <span className="text-foreground">{campaign.demographic}</span>
        </span>
        <span className="flex items-baseline gap-1.5">
          <span className="tracking-[0.1em] text-muted-foreground uppercase">
            agents
          </span>
          <span className="text-foreground">{campaign.agent_count}</span>
        </span>
        <span className="flex items-baseline gap-1.5">
          <span className="tracking-[0.1em] text-muted-foreground uppercase">
            iters
          </span>
          <span className="text-foreground">
            {campaign.iterations?.length ?? 0}/{campaign.max_iterations}
          </span>
        </span>
        <span className="flex items-baseline gap-1.5">
          <span className="tracking-[0.1em] text-muted-foreground uppercase">
            created
          </span>
          <span className="text-foreground">
            {formatRelative(campaign.created_at)}
          </span>
        </span>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="border border-border bg-surface-1 px-4 py-3 font-mono text-[0.72rem] text-muted-foreground">
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

  // Iteration selection, lifted so Campaign tab and Report tab stay in sync.
  const availableIterations = useMemo(() => {
    const set = new Set<number>();
    for (const it of campaign?.iterations ?? []) set.add(it.iteration_number);
    return [...set].sort((a, b) => a - b);
  }, [campaign?.iterations]);

  const latestIteration =
    availableIterations.length > 0
      ? availableIterations[availableIterations.length - 1]
      : 1;

  const [selectedIteration, setSelectedIteration] = useState<number>(latestIteration);

  // When new iterations arrive, jump to the latest (runs that add iterations).
  useEffect(() => {
    if (
      availableIterations.length > 0 &&
      !availableIterations.includes(selectedIteration)
    ) {
      setSelectedIteration(latestIteration);
    }
  }, [availableIterations, latestIteration, selectedIteration]);

  // variant_id → iteration_number map for scorecard filtering.
  const variantIterationMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const it of campaign?.iterations ?? []) {
      map.set(it.variant_id, it.iteration_number);
    }
    return map;
  }, [campaign?.iterations]);

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
          <CampaignTabContent
            campaign={campaign}
            selectedIteration={selectedIteration}
            availableIterations={availableIterations}
            onSelectIteration={setSelectedIteration}
          />
        </TabsContent>

        <TabsContent value="simulation" className="pt-4">
          <SimulationTabContent
            campaign={campaign}
            selectedIteration={selectedIteration}
            onInterviewAgent={handleInterviewAgent}
          />
        </TabsContent>

        <TabsContent value="report" className="pt-4">
          <ReportTabContent
            campaign={campaign}
            selectedIteration={selectedIteration}
            availableIterations={availableIterations}
            variantIterationMap={variantIterationMap}
            onSelectIteration={setSelectedIteration}
          />
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
