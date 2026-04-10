/**
 * Left sidebar — narrow, dense, log-style campaign history.
 *
 *  ┌─────────────────────────────┐
 *  │  A.R.C Studio         [+]   │
 *  │  Content optimization lab   │
 *  ├─────────────────────────────┤
 *  │  HISTORY              N     │
 *  │  · question preview    2h   │
 *  │  · question preview    3h   │
 *  │  ...                        │
 *  └─────────────────────────────┘
 *
 * No icons, no skeletons, no chrome. Status comes from a 6px dot.
 */

import { Link, useParams, useNavigate } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { StatusDot } from '@/components/common/status-badge';
import { useCampaigns } from '@/hooks/use-campaigns';
import { formatRelative } from '@/utils/formatters';
import { cn } from '@/lib/utils';

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trimEnd() + '…';
}

export function Sidebar() {
  const { id: activeId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data, isLoading, isError } = useCampaigns();

  return (
    <aside className="flex h-screen w-[252px] shrink-0 flex-col border-r border-border bg-sidebar">
      {/* Brand row */}
      <div className="flex items-start justify-between px-5 pt-5 pb-4">
        <Link to="/" className="group block">
          <span className="block text-[0.88rem] font-semibold tracking-[-0.01em] text-foreground transition-colors group-hover:text-primary">
            A.R.C Studio
          </span>
          <span className="mt-1 block font-mono text-[0.55rem] tracking-[0.16em] text-muted-foreground/60 uppercase">
            Content · Optimization · Lab
          </span>
        </Link>
        <button
          type="button"
          onClick={() => navigate('/campaigns/new')}
          className="mt-0.5 flex size-6 items-center justify-center rounded-sm border border-border text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary"
          aria-label="New campaign"
          title="New campaign"
        >
          <Plus className="size-3" />
        </button>
      </div>

      <div className="h-px w-full bg-border" />

      {/* History label */}
      <div className="flex items-center justify-between px-5 pt-4 pb-1">
        <span className="font-mono text-[0.58rem] tracking-[0.18em] text-muted-foreground/70 uppercase">
          History
        </span>
        {data && data.campaigns.length > 0 && (
          <span className="font-mono text-[0.58rem] tabular-nums text-muted-foreground/50">
            {data.campaigns.length.toString().padStart(3, '0')}
          </span>
        )}
      </div>

      {/* Campaign list */}
      <ScrollArea className="flex-1 px-2 pt-2 pb-3">
        {isLoading ? (
          <p className="px-3 py-2 font-mono text-[0.68rem] text-muted-foreground/50">
            loading…
          </p>
        ) : isError ? (
          <p className="px-3 py-2 font-mono text-[0.68rem] text-[oklch(0.68_0.20_22)]/80">
            fetch failed
          </p>
        ) : !data || data.campaigns.length === 0 ? (
          <p className="px-3 py-2 font-mono text-[0.68rem] text-muted-foreground/50">
            no campaigns yet
          </p>
        ) : (
          <ul className="flex flex-col gap-px">
            {data.campaigns.map((campaign) => {
              const isActive = campaign.id === activeId;
              return (
                <li key={campaign.id}>
                  <Link
                    to={`/campaigns/${campaign.id}`}
                    className={cn(
                      'group relative flex items-start gap-2.5 rounded-sm px-3 py-1.5 transition-colors',
                      isActive
                        ? 'bg-foreground/[0.06] text-foreground'
                        : 'text-foreground/65 hover:bg-foreground/[0.035] hover:text-foreground/90',
                    )}
                  >
                    {isActive && (
                      <span className="absolute inset-y-1 left-0 w-px bg-primary" />
                    )}
                    <StatusDot status={campaign.status} className="mt-[7px]" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[0.76rem] leading-snug">
                        {truncate(campaign.prediction_question, 56)}
                      </p>
                      <p className="mt-0.5 font-mono text-[0.58rem] tabular-nums text-muted-foreground/50">
                        {formatRelative(campaign.created_at)}
                      </p>
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </ScrollArea>

      {/* Bottom meta — build signature */}
      <div className="border-t border-border px-5 py-3">
        <p className="font-mono text-[0.55rem] tracking-[0.12em] text-muted-foreground/40 uppercase">
          phase 1 · poc
        </p>
      </div>
    </aside>
  );
}
