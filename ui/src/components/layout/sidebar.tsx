/**
 * Left sidebar — narrow dense log-style campaign history.
 *
 * Phase 5 session 5 — C2: collapsible. The expanded form takes ~252px;
 * the collapsed form is a 48px icon strip showing just the brand glyph,
 * the new-campaign button, and a vertical "history N" caption. Toggle
 * lives at the top edge; clicking either form is a 200ms cubic-bezier
 * width transition (no horizontal slide-in of contents — opacity only,
 * to keep the typography snap that Linear-style chrome relies on).
 *
 * State lives in `useSidebar()` so the campaign-detail page can flip
 * `collapsed=true` automatically when a run starts.
 */

import { Link, useParams, useNavigate } from 'react-router-dom';
import { Plus, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { StatusDot, STATUS_HOVER_BG } from '@/components/common/status-badge';
import { useCampaigns } from '@/hooks/use-campaigns';
import { useSidebar } from '@/hooks/use-sidebar';
import { formatRelative } from '@/utils/formatters';
import { cn } from '@/lib/utils';

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trimEnd() + '…';
}

const TRANSITION = 'transition-[width,opacity] duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]';

export function Sidebar() {
  const { id: activeId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data, isLoading, isError } = useCampaigns();
  const { collapsed, toggle } = useSidebar();

  return (
    <aside
      className={cn(
        'relative flex h-screen shrink-0 flex-col border-r border-border bg-sidebar overflow-hidden',
        TRANSITION,
        collapsed ? 'w-[48px]' : 'w-[252px]',
      )}
      aria-expanded={!collapsed}
    >
      {/* Brand row */}
      <div
        className={cn(
          'flex items-start justify-between pt-5 pb-4',
          collapsed ? 'px-2.5' : 'px-5',
        )}
      >
        {collapsed ? (
          <Link
            to="/"
            className="mx-auto flex size-7 items-center justify-center rounded-sm border border-border font-mono text-[0.7rem] font-semibold tracking-[-0.02em] text-foreground hover:border-foreground/40"
            title="A.R.C Studio"
            aria-label="A.R.C Studio — home"
          >
            A
          </Link>
        ) : (
          <>
            <Link to="/" className="group block">
              <span className="block text-[0.88rem] font-semibold tracking-[-0.01em] text-foreground">
                A.R.C Studio
              </span>
              <span className="mt-1 block font-mono text-[0.58rem] tracking-[0.14em] text-muted-foreground uppercase">
                Content · Optimization Lab
              </span>
            </Link>
            <button
              type="button"
              onClick={() => navigate('/campaigns/new')}
              className="mt-0.5 flex size-6 items-center justify-center rounded-sm border border-border text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground"
              aria-label="New campaign"
              title="New campaign"
            >
              <Plus className="size-3" />
            </button>
          </>
        )}
      </div>

      {/* Collapsed-only "+" affordance below the brand glyph so users
          can still spawn a new campaign without expanding. */}
      {collapsed && (
        <div className="flex justify-center pb-2">
          <button
            type="button"
            onClick={() => navigate('/campaigns/new')}
            className="flex size-7 items-center justify-center rounded-sm border border-border text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground"
            aria-label="New campaign"
            title="New campaign"
          >
            <Plus className="size-3" />
          </button>
        </div>
      )}

      <div className="h-px w-full bg-border" />

      {/* Expanded body — full history list. Collapsed body — vertical
          counter only. Either way the panel never scrolls horizontally. */}
      {!collapsed ? (
        <>
          <div className="flex items-center justify-between px-5 pt-4 pb-1">
            <span className="text-[0.78rem] font-medium text-foreground/85">
              History
            </span>
            {data && data.campaigns.length > 0 && (
              <span className="font-mono text-[0.62rem] tabular-nums text-muted-foreground">
                {data.campaigns.length.toString().padStart(3, '0')}
              </span>
            )}
          </div>

          <ScrollArea className="flex-1 px-2 pt-2 pb-3">
            {isLoading ? (
              <p className="px-3 py-2 font-mono text-[0.68rem] text-muted-foreground">
                loading…
              </p>
            ) : isError ? (
              <p className="px-3 py-2 font-mono text-[0.68rem] text-muted-foreground/55">
                —
              </p>
            ) : !data || data.campaigns.length === 0 ? (
              <p className="px-3 py-2 font-mono text-[0.68rem] text-muted-foreground">
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
                          'group relative flex items-start gap-2.5 rounded-sm px-3 py-2 transition-colors',
                          isActive
                            ? 'bg-foreground/[0.06] text-foreground'
                            : cn(
                                'text-foreground/75 hover:text-foreground',
                                STATUS_HOVER_BG[campaign.status],
                              ),
                        )}
                      >
                        {isActive && (
                          <span className="absolute inset-y-1 left-0 w-px bg-primary" />
                        )}
                        <StatusDot status={campaign.status} className="mt-[5px]" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[0.78rem] leading-snug">
                            {truncate(campaign.prediction_question, 56)}
                          </p>
                          <p className="mt-0.5 font-mono text-[0.6rem] tabular-nums text-muted-foreground">
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
        </>
      ) : (
        // Collapsed: stack of status dots so "5 active runs" remains
        // glanceable without expanding. Keeps the icon-strip useful
        // beyond just the brand glyph.
        <div className="flex flex-1 flex-col items-center gap-1.5 px-1 pt-3">
          {data?.campaigns.slice(0, 12).map((campaign) => {
            const isActive = campaign.id === activeId;
            return (
              <Link
                key={campaign.id}
                to={`/campaigns/${campaign.id}`}
                className={cn(
                  'relative flex size-6 items-center justify-center rounded-sm transition-colors',
                  isActive
                    ? 'bg-foreground/[0.06]'
                    : 'hover:bg-foreground/[0.04]',
                )}
                title={truncate(campaign.prediction_question, 80)}
              >
                {isActive && (
                  <span className="absolute inset-y-1 left-0 w-px bg-primary" />
                )}
                <StatusDot status={campaign.status} />
              </Link>
            );
          })}
        </div>
      )}

      {/* Bottom meta — build signature when expanded; toggle button
          always pinned bottom-right (or centered when collapsed). */}
      <div
        className={cn(
          'flex items-center border-t border-border py-3',
          collapsed ? 'justify-center px-1' : 'justify-between px-5',
        )}
      >
        {!collapsed && (
          <p className="font-mono text-[0.58rem] tracking-[0.12em] text-muted-foreground uppercase">
            phase 1 · poc
          </p>
        )}
        <button
          type="button"
          onClick={toggle}
          className="flex size-6 items-center justify-center rounded-sm border border-transparent text-muted-foreground transition-colors hover:border-border hover:text-foreground"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <PanelLeftOpen className="size-3.5" />
          ) : (
            <PanelLeftClose className="size-3.5" />
          )}
        </button>
      </div>
    </aside>
  );
}
