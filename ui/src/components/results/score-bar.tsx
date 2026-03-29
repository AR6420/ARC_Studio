/**
 * Horizontal bar visualization for a single composite score.
 *
 * Used within VariantRanking for per-metric breakdowns.
 * Bar width proportional to value/100, color from getScoreColor.
 * Smooth width animation on mount and value changes.
 */

import { cn } from '@/lib/utils';
import { getScoreColor, SCORE_COLORS } from '@/utils/colors';
import { formatMetricLabel, formatScore } from '@/utils/formatters';

interface ScoreBarProps {
  name: string;
  value: number | null;
  maxValue?: number;
}

export function ScoreBar({ name, value, maxValue = 100 }: ScoreBarProps) {
  const hasValue = value !== null && value !== undefined;
  const color = hasValue ? getScoreColor(name, value) : null;
  const widthPercent = hasValue ? Math.min(Math.max((value / maxValue) * 100, 0), 100) : 0;

  // Map score color to Tailwind bg classes
  const BAR_BG: Record<string, string> = {
    green: 'bg-emerald-400/80',
    amber: 'bg-amber-400/80',
    red: 'bg-red-400/80',
  };

  return (
    <div className="flex items-center gap-3">
      <span className="w-28 shrink-0 truncate text-xs text-muted-foreground">
        {formatMetricLabel(name)}
      </span>
      <div className="relative flex-1 h-2 rounded-full bg-muted/60 overflow-hidden">
        {hasValue && color && (
          <div
            className={cn(
              'absolute inset-y-0 left-0 rounded-full transition-[width] duration-700 ease-out',
              BAR_BG[color],
            )}
            style={{ width: `${widthPercent}%` }}
          />
        )}
      </div>
      <span
        className={cn(
          'w-10 shrink-0 text-right text-xs font-medium tabular-nums',
          color ? SCORE_COLORS[color] : 'text-muted-foreground/40',
        )}
      >
        {formatScore(value)}
      </span>
    </div>
  );
}
