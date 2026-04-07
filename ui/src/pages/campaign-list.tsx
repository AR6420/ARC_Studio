/**
 * Campaign list page -- the main landing page of the A.R.C Studio dashboard.
 *
 * Displays all campaigns in a responsive card grid with status badges,
 * prediction questions, demographics, dates, and iteration counts.
 *
 * Handles loading, error, and empty states using shared common components.
 *
 * D-07: Premium card design with hover depth, status-aware borders,
 * and scannable layout. Not a generic list.
 */

import { Link, useNavigate } from 'react-router-dom';
import { FlaskConical } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { StatusBadge } from '@/components/common/status-badge';
import { CampaignListSkeleton } from '@/components/common/loading-skeleton';
import { EmptyState } from '@/components/common/empty-state';
import { ErrorState } from '@/components/common/error-state';
import { useCampaigns } from '@/hooks/use-campaigns';
import { formatDate } from '@/utils/formatters';
import { cn } from '@/lib/utils';
import type { CampaignResponse } from '@/api/types';

function truncateLines(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trimEnd() + '...';
}

function getIterationLabel(campaign: CampaignResponse): string | null {
  if (!campaign.iterations || campaign.iterations.length === 0) return null;
  return `${campaign.iterations.length}/${campaign.max_iterations} iterations`;
}

/** Subtle left-border accent per status for running campaigns */
const statusBorderClass: Record<string, string> = {
  running:
    'ring-[oklch(0.45_0.10_250)]/40 hover:ring-[oklch(0.55_0.14_250)]/50',
  completed:
    'ring-[oklch(0.40_0.08_163)]/30 hover:ring-[oklch(0.50_0.12_163)]/40',
  failed:
    'ring-destructive/20 hover:ring-destructive/30',
  pending: '',
};

function CampaignCard({ campaign }: { campaign: CampaignResponse }) {
  const iterationLabel = getIterationLabel(campaign);

  return (
    <Link to={`/campaigns/${campaign.id}`} className="group outline-none">
      <Card
        className={cn(
          'relative cursor-pointer transition-all duration-200',
          'hover:bg-card/80 hover:shadow-lg hover:shadow-primary/5',
          'focus-within:ring-2 focus-within:ring-primary/40',
          statusBorderClass[campaign.status],
        )}
      >
        <CardContent className="flex flex-col gap-3">
          {/* Top row: demographic + status badge */}
          <div className="flex items-start justify-between gap-3">
            <span className="rounded-md bg-muted/50 px-2 py-0.5 text-[0.7rem] font-medium text-muted-foreground">
              {campaign.demographic}
            </span>
            <StatusBadge status={campaign.status} />
          </div>

          {/* Prediction question */}
          <p className="line-clamp-2 text-sm font-medium leading-relaxed text-foreground/90 group-hover:text-foreground">
            {truncateLines(campaign.prediction_question, 120)}
          </p>

          {/* Bottom row: date + iterations */}
          <div className="flex items-center gap-3 pt-0.5">
            <span className="text-[0.7rem] text-muted-foreground">
              {formatDate(campaign.created_at)}
            </span>
            {iterationLabel && (
              <>
                <span className="text-[0.5rem] text-muted-foreground/40">
                  |
                </span>
                <span className="text-[0.7rem] text-muted-foreground">
                  {iterationLabel}
                </span>
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

export function CampaignList() {
  const { data, isLoading, isError, error, refetch } = useCampaigns();
  const navigate = useNavigate();

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <h2 className="text-lg font-semibold tracking-tight">Campaigns</h2>
        <CampaignListSkeleton />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col gap-6">
        <h2 className="text-lg font-semibold tracking-tight">Campaigns</h2>
        <ErrorState
          message={
            error instanceof Error
              ? error.message
              : 'Failed to load campaigns. Check that the orchestrator is running.'
          }
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  if (!data || data.campaigns.length === 0) {
    return (
      <div className="flex flex-col gap-6">
        <h2 className="text-lg font-semibold tracking-tight">Campaigns</h2>
        <EmptyState
          icon={FlaskConical}
          title="No campaigns yet"
          description="Create your first campaign to start optimizing content with neural scoring and social simulation."
          action={{
            label: 'Create Campaign',
            onClick: () => navigate('/campaigns/new'),
          }}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold tracking-tight">Campaigns</h2>
        <span className="text-xs text-muted-foreground">
          {data.total} campaign{data.total !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
        {data.campaigns.map((campaign) => (
          <CampaignCard key={campaign.id} campaign={campaign} />
        ))}
      </div>
    </div>
  );
}
