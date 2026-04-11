/**
 * Campaign list — dense, scannable table view.
 *
 * Each campaign is a single row: status dot · question · demographic ·
 * best composite score · iteration count · relative timestamp. Hovering
 * a row reveals a one-line preview of the seed content underneath.
 *
 * No card grid. No loading skeletons. Log-style loading indicator.
 */

import { Link, useNavigate } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { StatusDot } from '@/components/common/status-badge';
import { ErrorState } from '@/components/common/error-state';
import { useCampaigns } from '@/hooks/use-campaigns';
import { formatRelative } from '@/utils/formatters';
import { cn } from '@/lib/utils';
import type { CampaignResponse, CompositeScores } from '@/api/types';

const COMPOSITE_KEYS: (keyof CompositeScores)[] = [
  'attention_score',
  'virality_potential',
  'conversion_potential',
  'audience_fit',
  'memory_durability',
  'backlash_risk',
  'polarization_index',
];

/** Best-variant average composite score across the most recent iteration. */
function bestCampaignScore(campaign: CampaignResponse): number | null {
  const iterations = campaign.iterations;
  if (!iterations?.length) return null;
  const maxIterNum = Math.max(...iterations.map((it) => it.iteration_number));
  const latest = iterations.filter((it) => it.iteration_number === maxIterNum);
  let best = -1;
  for (const v of latest) {
    if (!v.composite_scores) continue;
    const vals = COMPOSITE_KEYS.map((k) => v.composite_scores![k]).filter(
      (n): n is number => n !== null,
    );
    if (!vals.length) continue;
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    if (avg > best) best = avg;
  }
  return best >= 0 ? best : null;
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, max).trimEnd() + '…';
}

// Shared grid template for header + row so columns stay aligned.
const COLS =
  'grid-cols-[18px_minmax(0,2.4fr)_minmax(0,1fr)_72px_62px_74px] md:grid-cols-[18px_minmax(0,2.6fr)_minmax(0,0.9fr)_80px_64px_78px]';

function TableHeader() {
  return (
    <div
      className={cn(
        'grid items-center gap-4 px-3 pb-3',
        COLS,
      )}
    >
      <span />
      <span className="font-mono text-[0.62rem] font-medium tracking-[0.14em] text-foreground/60 uppercase">
        Prediction Question
      </span>
      <span className="font-mono text-[0.62rem] font-medium tracking-[0.14em] text-foreground/60 uppercase">
        Demographic
      </span>
      <span className="text-right font-mono text-[0.62rem] font-medium tracking-[0.14em] text-foreground/60 uppercase">
        Score
      </span>
      <span className="text-right font-mono text-[0.62rem] font-medium tracking-[0.14em] text-foreground/60 uppercase">
        Iters
      </span>
      <span className="text-right font-mono text-[0.62rem] font-medium tracking-[0.14em] text-foreground/60 uppercase">
        Created
      </span>
    </div>
  );
}

function CampaignRow({ campaign }: { campaign: CampaignResponse }) {
  const best = bestCampaignScore(campaign);
  // Prefer the server-computed iterations_completed from list/detail response;
  // fall back to derived counts so existing data without the field still works.
  const iterCount =
    campaign.iterations_completed ??
    (campaign.iterations
      ? new Set(campaign.iterations.map((it) => it.iteration_number)).size
      : 0);
  const demographic =
    campaign.demographic === 'custom' && campaign.demographic_custom
      ? truncate(campaign.demographic_custom, 28)
      : campaign.demographic;

  return (
    <Link
      to={`/campaigns/${campaign.id}`}
      className={cn(
        'group relative block border-b border-border transition-colors',
        'hover:bg-foreground/[0.025] focus-visible:bg-foreground/[0.03] focus-visible:outline-none',
      )}
    >
      <div
        className={cn(
          'grid items-center gap-4 px-3 py-2.5',
          COLS,
        )}
      >
        <StatusDot status={campaign.status} />
        <p className="truncate text-[0.82rem] leading-snug text-foreground/90 group-hover:text-foreground">
          {campaign.prediction_question}
        </p>
        <span className="truncate font-mono text-[0.72rem] text-foreground/75">
          {demographic}
        </span>
        <span
          className={cn(
            'text-right font-mono text-[0.82rem] tabular-nums',
            best != null ? 'text-foreground' : 'text-muted-foreground',
          )}
        >
          {best != null ? best.toFixed(1) : '—'}
        </span>
        <span className="text-right font-mono text-[0.72rem] tabular-nums text-foreground/80">
          {iterCount}/{campaign.max_iterations}
        </span>
        <span className="text-right font-mono text-[0.72rem] tabular-nums text-foreground/75">
          {formatRelative(campaign.created_at)}
        </span>
      </div>

      {/* Hover summary — seed content preview, fades in, no layout shift */}
      <div className="max-h-0 overflow-hidden transition-[max-height] duration-150 ease-out group-hover:max-h-10">
        <p className="pb-2.5 pl-[calc(0.75rem+18px+1rem)] pr-3 font-mono text-[0.68rem] leading-tight text-muted-foreground">
          {truncate(campaign.seed_content.replace(/\s+/g, ' '), 180)}
        </p>
      </div>
    </Link>
  );
}

function Loading() {
  return (
    <div className="rounded-sm border border-border bg-surface-1 px-4 py-3 font-mono text-[0.72rem] text-muted-foreground">
      <span className="mr-2 inline-block size-1 rounded-full bg-primary/80 align-middle" />
      loading campaigns…
    </div>
  );
}

function EmptyCampaigns({ onNew }: { onNew: () => void }) {
  return (
    <div className="flex flex-col items-start gap-4 border-y border-border py-10">
      <div className="font-mono text-[0.7rem] tracking-[0.08em] text-muted-foreground uppercase">
        $ arc campaigns list
      </div>
      <p className="max-w-md text-[0.88rem] leading-relaxed text-foreground/85">
        No campaigns in the store yet. Seed content, a prediction question,
        and a target demographic are all you need to run your first
        optimization cycle.
      </p>
      <Button variant="outline" size="sm" onClick={onNew} className="gap-1.5">
        <Plus className="size-3" />
        New Campaign
      </Button>
    </div>
  );
}

export function CampaignList() {
  const { data, isLoading, isError, error, refetch } = useCampaigns();
  const navigate = useNavigate();

  return (
    <div className="flex flex-col gap-8">
      {/* Page heading */}
      <div className="flex items-end justify-between border-b border-border pb-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-[1.15rem] font-semibold tracking-[-0.01em] text-foreground">
            Campaigns
          </h1>
          <p className="font-mono text-[0.68rem] tracking-[0.08em] text-muted-foreground uppercase">
            Neural scoring · social simulation · iterative optimization
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate('/campaigns/new')}
          className="gap-1.5 border-primary/50 text-primary hover:border-primary/80 hover:bg-primary/10 hover:text-primary"
        >
          <Plus className="size-3" />
          New Campaign
        </Button>
      </div>

      {/* Content */}
      {isLoading ? (
        <Loading />
      ) : isError ? (
        <ErrorState
          message={
            error instanceof Error
              ? error.message
              : 'Failed to load campaigns. Check that the orchestrator is running.'
          }
          onRetry={() => void refetch()}
        />
      ) : !data || data.campaigns.length === 0 ? (
        <EmptyCampaigns onNew={() => navigate('/campaigns/new')} />
      ) : (
        <div className="flex flex-col">
          <TableHeader />
          <div className="border-t border-border">
            {data.campaigns.map((c) => (
              <CampaignRow key={c.id} campaign={c} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
