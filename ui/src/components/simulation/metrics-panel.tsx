/**
 * MiroFish metric strip — a dense horizontal row of stat cells.
 *
 *   ORG SHARES 2,341 · SENT 0.42 ↑ · COUNTER 17 · PEAK R4 ...
 *
 * Each cell has a small-caps label and a monospace value. Mirofish teal
 * is the identity color — a thin rule underneath groups the row.
 */

import type { MirofishMetrics } from '@/api/types';
import { cn } from '@/lib/utils';

interface MetricsPanelProps {
  metrics: MirofishMetrics | null | undefined;
}

interface CellConfig {
  label: string;
  key: keyof MirofishMetrics;
  format: (value: MirofishMetrics[keyof MirofishMetrics]) => string;
  trend?: (value: MirofishMetrics[keyof MirofishMetrics]) => 'up' | 'down' | 'flat';
}

const CELLS: CellConfig[] = [
  {
    label: 'Organic Shares',
    key: 'organic_shares',
    format: (v) => (v == null ? '—' : (v as number).toLocaleString()),
  },
  {
    label: 'Sentiment',
    key: 'sentiment_trajectory',
    format: (v) => {
      const arr = v as number[] | null;
      if (!arr?.length) return '—';
      return arr[arr.length - 1].toFixed(2);
    },
    trend: (v) => {
      const arr = v as number[] | null;
      if (!arr || arr.length < 2) return 'flat';
      const diff = arr[arr.length - 1] - arr[arr.length - 2];
      return diff > 0.01 ? 'up' : diff < -0.01 ? 'down' : 'flat';
    },
  },
  {
    label: 'Counter-narr.',
    key: 'counter_narrative_count',
    format: (v) => (v == null ? '—' : String(v)),
  },
  {
    label: 'Peak Round',
    key: 'peak_virality_cycle',
    format: (v) => (v == null ? '—' : `R${v}`),
  },
  {
    label: 'Drift',
    key: 'sentiment_drift',
    format: (v) =>
      v == null ? '—' : `${((v as number) * 100).toFixed(1)}%`,
  },
  {
    label: 'Coalitions',
    key: 'coalition_formation',
    format: (v) => (v == null ? '—' : String(v)),
  },
  {
    label: 'Gini',
    key: 'influence_concentration',
    format: (v) =>
      v == null ? '—' : `${((v as number) * 100).toFixed(1)}%`,
  },
  {
    label: 'Platform Δ',
    key: 'platform_divergence',
    format: (v) =>
      v == null ? '—' : `${((v as number) * 100).toFixed(1)}%`,
  },
];

const TREND_GLYPH: Record<'up' | 'down' | 'flat', string> = {
  up: '↑',
  down: '↓',
  flat: '·',
};

const TREND_COLOR: Record<'up' | 'down' | 'flat', string> = {
  up: 'text-[oklch(0.72_0.15_150)]',
  down: 'text-[oklch(0.68_0.20_22)]',
  flat: 'text-muted-foreground',
};

export function MetricsPanel({ metrics }: MetricsPanelProps) {
  if (!metrics) {
    return (
      <div className="border border-dashed border-border px-4 py-6 font-mono text-[0.74rem] text-muted-foreground">
        › mirofish metrics unavailable for this iteration
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Top hairline in MiroFish teal signals the owning system */}
      <div className="absolute inset-x-0 top-0 h-px bg-mirofish/50" />
      <div className="grid grid-cols-2 gap-x-6 gap-y-4 border-y border-border px-1 py-4 sm:grid-cols-4 lg:grid-cols-8">
        {CELLS.map((cell) => {
          const raw = metrics[cell.key];
          const value = cell.format(raw);
          const trend = cell.trend ? cell.trend(raw) : null;
          return (
            <div key={cell.key} className="flex flex-col gap-1">
              <span className="font-mono text-[0.6rem] tracking-[0.12em] text-muted-foreground uppercase">
                {cell.label}
              </span>
              <div className="flex items-baseline gap-1.5">
                <span className="font-mono text-[0.94rem] font-semibold tabular-nums tracking-[-0.01em] text-foreground">
                  {value}
                </span>
                {trend && (
                  <span
                    className={cn(
                      'font-mono text-[0.78rem] leading-none',
                      TREND_COLOR[trend],
                    )}
                  >
                    {TREND_GLYPH[trend]}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
