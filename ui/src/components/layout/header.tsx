/**
 * Top header bar for the main content area.
 *
 * Displays a page title / breadcrumb area on the left
 * and a system health indicator on the right.
 *
 * D-07: Pulsing health dot with layered glass-like depth.
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
  const allDown = statuses.every(
    (s) => s !== 'ok' && s !== 'healthy',
  );

  if (allOk && data.orchestrator === 'ok') return 'healthy';
  if (allDown) return 'down';
  return 'degraded';
}

const healthColors: Record<HealthLevel, string> = {
  healthy: 'bg-[oklch(0.72_0.19_163)]',
  degraded: 'bg-[oklch(0.78_0.16_75)]',
  down: 'bg-destructive',
  unknown: 'bg-muted-foreground/40',
};

const healthLabels: Record<HealthLevel, string> = {
  healthy: 'All systems operational',
  degraded: 'Some services degraded',
  down: 'Services unavailable',
  unknown: 'Checking status...',
};

export function Header({ title }: HeaderProps) {
  const { data, isLoading } = useHealth();
  const level = isLoading ? 'unknown' : getHealthLevel(data);

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border/40 bg-background/80 px-6 backdrop-blur-sm">
      <h1 className="text-base font-semibold tracking-tight text-foreground">
        {title ?? 'Dashboard'}
      </h1>

      <Tooltip>
        <TooltipTrigger className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
          <span className="relative flex size-2.5">
            <span
              className={cn(
                'absolute inline-flex size-full rounded-full opacity-60',
                healthColors[level],
                level !== 'unknown' && 'animate-ping',
              )}
            />
            <span
              className={cn(
                'relative inline-flex size-2.5 rounded-full',
                healthColors[level],
              )}
            />
          </span>
          <span className="hidden font-medium sm:inline">System</span>
        </TooltipTrigger>
        <TooltipContent side="bottom">
          <p>{healthLabels[level]}</p>
          {data && (
            <div className="mt-1 flex flex-col gap-0.5 text-[0.65rem] opacity-80">
              <span>TRIBE: {data.tribe_scorer.status}</span>
              <span>MiroFish: {data.mirofish.status}</span>
              <span>Database: {data.database.status}</span>
            </div>
          )}
        </TooltipContent>
      </Tooltip>
    </header>
  );
}
