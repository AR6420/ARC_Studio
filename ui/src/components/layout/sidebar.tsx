/**
 * Fixed left sidebar with app branding, new campaign button, and campaign history.
 *
 * Uses the useCampaigns() hook for data, shadcn ScrollArea for overflow,
 * and highlights the active campaign based on the current route.
 *
 * D-07: Subtle depth via layered background, not flat gray.
 */

import { Link, useParams, useNavigate } from 'react-router-dom';
import { Plus, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { StatusBadge } from '@/components/common/status-badge';
import { SidebarSkeleton } from '@/components/common/loading-skeleton';
import { useCampaigns } from '@/hooks/use-campaigns';
import { formatDate } from '@/utils/formatters';
import { cn } from '@/lib/utils';

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trimEnd() + '...';
}

export function Sidebar() {
  const { id: activeId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data, isLoading, isError } = useCampaigns();

  return (
    <aside className="flex h-screen w-72 flex-col border-r border-border/50 bg-sidebar">
      {/* Branding */}
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex size-8 items-center justify-center rounded-lg bg-primary/15">
          <Zap className="size-4 text-primary" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-bold tracking-tight text-foreground">
            A.R.C Studio
          </span>
          <span className="text-[0.65rem] font-medium tracking-wider uppercase text-muted-foreground">
            Content Lab
          </span>
        </div>
      </div>

      <Separator className="mx-4 w-auto opacity-40" />

      {/* New Campaign CTA */}
      <div className="px-4 pt-4 pb-2">
        <Button
          className="w-full gap-2 font-semibold"
          size="lg"
          onClick={() => navigate('/campaigns/new')}
        >
          <Plus className="size-4" />
          New Campaign
        </Button>
      </div>

      {/* Campaign history label */}
      <div className="px-5 pt-4 pb-2">
        <span className="text-[0.65rem] font-semibold tracking-wider uppercase text-muted-foreground/70">
          Campaign History
        </span>
      </div>

      {/* Campaign list */}
      <ScrollArea className="flex-1 px-2 pb-4">
        {isLoading ? (
          <SidebarSkeleton />
        ) : isError ? (
          <p className="px-3 py-4 text-xs text-muted-foreground">
            Failed to load campaigns
          </p>
        ) : !data || data.campaigns.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-muted-foreground/70">
            No campaigns yet.{' '}
            <br />
            Create one to get started.
          </p>
        ) : (
          <div className="flex flex-col gap-0.5">
            {data.campaigns.map((campaign) => {
              const isActive = campaign.id === activeId;
              return (
                <Link
                  key={campaign.id}
                  to={`/campaigns/${campaign.id}`}
                  className={cn(
                    'group flex flex-col gap-1.5 rounded-lg px-3 py-2.5 transition-colors',
                    isActive
                      ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                      : 'text-sidebar-foreground/80 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground',
                  )}
                >
                  <span className="text-[0.8rem] font-medium leading-snug">
                    {truncate(campaign.prediction_question, 60)}
                  </span>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={campaign.status} className="h-4 text-[0.6rem]" />
                    <span className="text-[0.65rem] text-muted-foreground">
                      {formatDate(campaign.created_at)}
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </ScrollArea>
    </aside>
  );
}
