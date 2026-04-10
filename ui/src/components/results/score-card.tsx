/**
 * Compact score tile — single metric, monospace value, heat-colored.
 *
 * Used for small highlight displays. The main composite profile on
 * campaign-detail uses ScoreBar instead of stacking these.
 */

import { cn } from '@/lib/utils';
import {
  getHeatStop,
  HEAT_TEXT,
  HEAT_VARS,
  INVERTED_SCORES,
} from '@/utils/colors';
import { formatScore, formatMetricLabel } from '@/utils/formatters';

interface ScoreCardProps {
  name: string;
  value: number | null;
  description?: string;
  className?: string;
}

export function ScoreCard({ name, value, description, className }: ScoreCardProps) {
  const hasValue = value !== null && value !== undefined;
  const stop = hasValue ? getHeatStop(name, value) : null;
  const isInverted = INVERTED_SCORES.has(name);

  return (
    <div
      className={cn(
        'group relative flex flex-col gap-1.5 border border-border bg-surface-1 px-3 py-2.5',
        className,
      )}
    >
      {/* Left accent bar — colored hairline, not a whole border */}
      {stop && (
        <span
          className="absolute inset-y-0 left-0 w-px"
          style={{ background: HEAT_VARS[stop] }}
        />
      )}

      <div className="flex items-center justify-between">
        <span className="font-mono text-[0.58rem] tracking-[0.12em] text-muted-foreground/70 uppercase">
          {formatMetricLabel(name)}
        </span>
        {isInverted && (
          <span
            className="font-mono text-[0.55rem] text-muted-foreground/50"
            title="Lower is better"
          >
            ↓
          </span>
        )}
      </div>

      <div
        className={cn(
          'font-mono text-[1.35rem] font-semibold leading-none tabular-nums tracking-[-0.02em]',
          stop ? HEAT_TEXT[stop] : 'text-muted-foreground/30',
        )}
      >
        {hasValue ? formatScore(value) : '—'}
      </div>

      {description && (
        <p className="line-clamp-2 text-[0.64rem] leading-tight text-muted-foreground/55">
          {description}
        </p>
      )}
    </div>
  );
}
