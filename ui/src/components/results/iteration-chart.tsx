/**
 * Iteration trajectory chart -- Recharts line chart showing composite score
 * evolution across iterations.
 *
 * Uses the shadcn/ui ChartContainer + ChartTooltip pattern for dark-themed
 * Recharts integration with CSS variable-driven colors.
 *
 * Per D-07: Dark background, subtle grid, monotone curves, styled tooltip.
 */

import { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid } from 'recharts';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
} from '@/components/ui/chart';
import type { ChartConfig } from '@/components/ui/chart';
import type { IterationRecord, CompositeScores } from '@/api/types';

const COMPOSITE_KEYS: (keyof CompositeScores)[] = [
  'attention_score',
  'virality_potential',
  'conversion_potential',
  'audience_fit',
  'memory_durability',
  'backlash_risk',
  'polarization_index',
];

/** Chart colors -- mapped to CSS variables from the theme. */
const LINE_COLORS: Record<string, string> = {
  attention_score: 'var(--chart-1)',
  virality_potential: 'var(--chart-2)',
  conversion_potential: 'var(--chart-3)',
  backlash_risk: 'var(--chart-4)',
  memory_durability: 'var(--chart-5)',
  audience_fit: 'oklch(0.72 0.12 200)',
  polarization_index: 'oklch(0.65 0.14 340)',
};

const CHART_CONFIG: ChartConfig = {
  attention_score: { label: 'Attention', color: LINE_COLORS.attention_score },
  virality_potential: { label: 'Virality', color: LINE_COLORS.virality_potential },
  conversion_potential: { label: 'Conversion', color: LINE_COLORS.conversion_potential },
  audience_fit: { label: 'Audience Fit', color: LINE_COLORS.audience_fit },
  memory_durability: { label: 'Memory', color: LINE_COLORS.memory_durability },
  backlash_risk: { label: 'Backlash Risk', color: LINE_COLORS.backlash_risk },
  polarization_index: { label: 'Polarization', color: LINE_COLORS.polarization_index },
};

interface ChartDataPoint {
  iteration: number;
  [key: string]: number | null;
}

/**
 * Transform iteration records into chart data points.
 * Groups by iteration_number, picks the best variant per iteration
 * (highest average composite score), extracts composite values.
 */
function buildChartData(iterations: IterationRecord[]): ChartDataPoint[] {
  const grouped = new Map<number, IterationRecord[]>();
  for (const it of iterations) {
    const existing = grouped.get(it.iteration_number) ?? [];
    existing.push(it);
    grouped.set(it.iteration_number, existing);
  }

  const points: ChartDataPoint[] = [];

  for (const [iterNum, variants] of grouped) {
    // Find best variant by average composite score
    let bestAvg = -1;
    let bestScores: CompositeScores | null = null;

    for (const v of variants) {
      if (!v.composite_scores) continue;
      const vals = COMPOSITE_KEYS.map((k) => v.composite_scores![k]).filter(
        (n): n is number => n !== null,
      );
      if (!vals.length) continue;
      const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
      if (avg > bestAvg) {
        bestAvg = avg;
        bestScores = v.composite_scores;
      }
    }

    if (bestScores) {
      const point: ChartDataPoint = { iteration: iterNum };
      for (const key of COMPOSITE_KEYS) {
        point[key] = bestScores[key];
      }
      points.push(point);
    }
  }

  return points.sort((a, b) => a.iteration - b.iteration);
}

interface IterationChartProps {
  iterations: IterationRecord[];
}

export function IterationChart({ iterations }: IterationChartProps) {
  const chartData = useMemo(() => buildChartData(iterations), [iterations]);

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-border bg-card py-12">
        <p className="text-sm text-muted-foreground">
          No iteration data available for chart.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5 ring-1 ring-foreground/[0.06]">
      <ChartContainer config={CHART_CONFIG} className="h-[320px] w-full">
        <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
          <CartesianGrid
            strokeDasharray="3 6"
            vertical={false}
            stroke="oklch(0.26 0.01 260 / 0.5)"
          />
          <XAxis
            dataKey="iteration"
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `Iter ${v}`}
            tick={{ fontSize: 11 }}
          />
          <YAxis
            domain={[0, 100]}
            tickLine={false}
            axisLine={false}
            tickCount={6}
            tick={{ fontSize: 11 }}
          />
          <ChartTooltip
            content={
              <ChartTooltipContent
                labelFormatter={(value) => `Iteration ${value}`}
              />
            }
          />
          <ChartLegend content={<ChartLegendContent />} />
          {COMPOSITE_KEYS.map((key) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={`var(--color-${key})`}
              strokeWidth={2}
              dot={{ r: 3, strokeWidth: 0, fill: `var(--color-${key})` }}
              activeDot={{ r: 5, strokeWidth: 2, stroke: 'oklch(0.12 0.008 260)' }}
              connectNulls
            />
          ))}
        </LineChart>
      </ChartContainer>
    </div>
  );
}
