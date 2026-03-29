/**
 * CampaignDetail page — primary results view for a single campaign.
 *
 * Three tabs: Campaign (headline metrics), Simulation (Plan 06), Report (Plan 07).
 * Per D-06: ProgressStream renders inline for running campaigns.
 * Per D-07: Sophisticated analytics dashboard aesthetic.
 */

import { useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Calendar, Users, Repeat } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { StatusBadge } from '@/components/common/status-badge';
import { CampaignDetailSkeleton } from '@/components/common/loading-skeleton';
import { ErrorState } from '@/components/common/error-state';
import { ProgressStream } from '@/components/progress/progress-stream';
import { ScoreCard } from '@/components/results/score-card';
import { VariantRanking } from '@/components/results/variant-ranking';
import { IterationChart } from '@/components/results/iteration-chart';
import { useCampaign } from '@/hooks/use-campaigns';
import { formatDate } from '@/utils/formatters';
import type { IterationRecord, CompositeScores } from '@/api/types';

/** All 7 composite score dimension keys in display order. */
const COMPOSITE_KEYS: (keyof CompositeScores)[] = [
  'attention_score',
  'virality_potential',
  'conversion_potential',
  'audience_fit',
  'memory_durability',
  'backlash_risk',
  'polarization_index',
];

/** Short descriptions for each composite dimension. */
const SCORE_DESCRIPTIONS: Record<string, string> = {
  attention_score: 'Neural attention capture and sustained focus potential',
  virality_potential: 'Likelihood of organic sharing and social amplification',
  backlash_risk: 'Risk of negative reactions or counter-narratives',
  memory_durability: 'Long-term recall and brand memory encoding strength',
  conversion_potential: 'Propensity to drive desired actions or conversions',
  audience_fit: 'Alignment with target demographic values and language',
  polarization_index: 'Degree of opinion splitting within the audience',
};

/**
 * Extract the best composite scores from the latest iteration's top variant.
 * Groups iterations by iteration_number, picks the latest, then finds the
 * variant with the highest average non-null composite score.
 */
function extractBestScores(iterations: IterationRecord[]): CompositeScores | null {
  if (!iterations.length) return null;

  const maxIter = Math.max(...iterations.map((it) => it.iteration_number));
  const latestVariants = iterations.filter((it) => it.iteration_number === maxIter);

  return pickBestVariantScores(latestVariants);
}

/**
 * Pick the composite scores from the variant with the highest average score.
 */
function pickBestVariantScores(variants: IterationRecord[]): CompositeScores | null {
  let bestAvg = -1;
  let bestScores: CompositeScores | null = null;

  for (const v of variants) {
    if (!v.composite_scores) continue;
    const vals = COMPOSITE_KEYS.map((k) => v.composite_scores![k]).filter(
      (n): n is number => n !== null,
    );
    if (!vals.length) continue;
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    if (avg > bestAvg) {
      bestAvg = avg;
      bestScores = v.composite_scores;
    }
  }

  return bestScores;
}

/**
 * Get the latest iteration variants for the variant ranking display.
 */
function getLatestVariants(iterations: IterationRecord[]): IterationRecord[] {
  if (!iterations.length) return [];
  const maxIter = Math.max(...iterations.map((it) => it.iteration_number));
  return iterations.filter((it) => it.iteration_number === maxIter);
}

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: campaign, isLoading, isError, error, refetch } = useCampaign(id ?? '');

  const bestScores = useMemo(
    () => (campaign?.iterations ? extractBestScores(campaign.iterations) : null),
    [campaign?.iterations],
  );

  const latestVariants = useMemo(
    () => (campaign?.iterations ? getLatestVariants(campaign.iterations) : []),
    [campaign?.iterations],
  );

  if (isLoading) {
    return <CampaignDetailSkeleton />;
  }

  if (isError || !campaign) {
    return (
      <ErrorState
        message={
          error instanceof Error
            ? error.message
            : 'Campaign not found. It may have been deleted.'
        }
        onRetry={() => void refetch()}
      />
    );
  }

  const hasResults =
    campaign.status === 'completed' &&
    campaign.iterations &&
    campaign.iterations.length > 0;

  return (
    <div className="flex flex-col gap-6">
      {/* ---- Campaign Header ---- */}
      <div className="flex flex-col gap-4">
        <button
          type="button"
          onClick={() => navigate('/campaigns')}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors w-fit"
        >
          <ArrowLeft className="size-3.5" />
          All campaigns
        </button>

        <div className="flex flex-col gap-2">
          <h1 className="text-xl font-semibold leading-tight text-foreground tracking-tight">
            {campaign.prediction_question}
          </h1>

          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <StatusBadge status={campaign.status} />
            <span className="flex items-center gap-1.5">
              <Users className="size-3.5" />
              {campaign.demographic}
            </span>
            <span className="flex items-center gap-1.5">
              <Repeat className="size-3.5" />
              {campaign.agent_count} agents, {campaign.max_iterations} iterations
            </span>
            <span className="flex items-center gap-1.5">
              <Calendar className="size-3.5" />
              {formatDate(campaign.created_at)}
            </span>
          </div>
        </div>

        {/* D-06: Inline progress for running campaigns */}
        {campaign.status === 'running' && (
          <ProgressStream campaignId={campaign.id} />
        )}

        {/* Failed campaign error display */}
        {campaign.status === 'failed' && campaign.error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3">
            <p className="text-sm text-destructive">{campaign.error}</p>
          </div>
        )}
      </div>

      {/* ---- Tab Navigation ---- */}
      <Tabs defaultValue="campaign">
        <TabsList variant="line" className="border-b border-border pb-px">
          <TabsTrigger value="campaign" className="px-4 py-2 text-sm">
            Campaign
          </TabsTrigger>
          <TabsTrigger value="simulation" className="px-4 py-2 text-sm">
            Simulation
          </TabsTrigger>
          <TabsTrigger value="report" className="px-4 py-2 text-sm">
            Report
          </TabsTrigger>
        </TabsList>

        {/* ---- Campaign Tab ---- */}
        <TabsContent value="campaign" className="pt-6">
          {hasResults ? (
            <div className="flex flex-col gap-8">
              {/* Score Cards Grid */}
              {bestScores && (
                <section>
                  <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-muted-foreground">
                    Composite Scores
                  </h2>
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
                    {COMPOSITE_KEYS.map((key) => (
                      <ScoreCard
                        key={key}
                        name={key}
                        value={bestScores[key]}
                        description={SCORE_DESCRIPTIONS[key]}
                      />
                    ))}
                  </div>
                </section>
              )}

              {/* Variant Ranking */}
              {latestVariants.length > 0 && (
                <section>
                  <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-muted-foreground">
                    Variant Ranking
                  </h2>
                  <VariantRanking variants={latestVariants} />
                </section>
              )}

              {/* Iteration Trajectory Chart */}
              {campaign.iterations && campaign.iterations.length > 0 && (
                <section>
                  <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-muted-foreground">
                    Iteration Trajectory
                  </h2>
                  <IterationChart iterations={campaign.iterations} />
                </section>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <p className="text-sm text-muted-foreground">
                {campaign.status === 'pending'
                  ? 'Campaign has not been started yet.'
                  : campaign.status === 'running'
                    ? 'Results will appear here once the first iteration completes.'
                    : 'No results available for this campaign.'}
              </p>
              {campaign.status === 'pending' && (
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-4"
                  onClick={() => navigate(`/campaigns/${campaign.id}`)}
                >
                  Start Campaign
                </Button>
              )}
            </div>
          )}
        </TabsContent>

        {/* ---- Simulation Tab (Plan 06) ---- */}
        <TabsContent value="simulation" className="pt-6">
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <p className="text-sm text-muted-foreground">
              Social simulation view coming soon.
            </p>
          </div>
        </TabsContent>

        {/* ---- Report Tab (Plan 07) ---- */}
        <TabsContent value="report" className="pt-6">
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <p className="text-sm text-muted-foreground">
              Full report view coming soon.
            </p>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
