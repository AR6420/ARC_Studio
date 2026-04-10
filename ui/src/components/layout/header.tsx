/**
 * Top header bar for the main content area.
 *
 * Keeps it stripped back — just a section title, a monospace breadcrumb
 * slot, and a live health indicator on the right. No backdrop blur,
 * no chrome, no animated glow.
 */

import { useHealth } from '@/hooks/use-health';
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

interface HeaderProps {
  title?: string;
}

type HealthLevel = 'healthy' | 'degraded' | 'down' | 'unknown';

function getHealthLevel(
  data: ReturnType<typeof useHealth>['data'],
): HealthLevel {
  if (!data) return 'unknown';
  const services = [data.tribe_scorer, data.mirofish, data.database];
  const statuses = services.map((s) => s.status);
  const allOk = statuses.every((s) => s === 'ok' || s === 'healthy');
  const allDown = statuses.every((s) => s !== 'ok' && s !== 'healthy');
  if (allOk && data.orchestrator === 'ok') return 'healthy';
  if (allDown) return 'down';
  return 'degraded';
}

const healthDot: Record<HealthLevel, string> = {
  healthy: 'bg-[oklch(0.72_0.15_150)]',
  degraded: 'bg-[oklch(0.80_0.14_75)]',
  down: 'bg-[oklch(0.68_0.20_22)]',
  unknown: 'bg-muted-foreground/40',
};

const healthLabel: Record<HealthLevel, string> = {
  healthy: 'All systems nominal',
  degraded: 'Degraded service',
  down: 'Services offline',
  unknown: 'Checking…',
};

export function Header({ title }: HeaderProps) {
  const { data, isLoading } = useHealth();
  const level = isLoading ? 'unknown' : getHealthLevel(data);

  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-background px-6">
      <div className="flex items-baseline gap-3">
        <h1 className="text-[0.85rem] font-semibold tracking-[-0.005em] text-foreground">
          {title ?? 'Dashboard'}
        </h1>
        <span className="font-mono text-[0.62rem] tracking-[0.12em] text-muted-foreground uppercase">
          /arc
        </span>
      </div>

      <Tooltip>
        <TooltipTrigger className="flex items-center gap-2 rounded-sm px-2 py-1 font-mono text-[0.65rem] tracking-[0.08em] uppercase text-muted-foreground transition-colors hover:bg-foreground/[0.04] hover:text-foreground">
          <span
            className={cn(
              'inline-block size-1.5 rounded-full',
              healthDot[level],
              level === 'healthy' && 'animate-pulse',
            )}
          />
          <span className="hidden sm:inline">system</span>
        </TooltipTrigger>
        <TooltipContent side="bottom">
          <p className="text-[0.72rem]">{healthLabel[level]}</p>
          {data && (
            <div className="mt-1.5 flex flex-col gap-0.5 font-mono text-[0.62rem] text-muted-foreground">
              <span>tribe_scorer · {data.tribe_scorer.status}</span>
              <span>mirofish · {data.mirofish.status}</span>
              <span>database · {data.database.status}</span>
            </div>
          )}
        </TooltipContent>
      </Tooltip>
    </header>
  );
}
