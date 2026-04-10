/**
 * Iteration trajectory — line chart showing composite score evolution.
 *
 * Thin lines, no dots, subtle dashed grid. One line per composite metric,
 * colored from the new palette (primary amber / TRIBE purple / MiroFish
 * teal / heat stops).
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

const LINE_COLORS: Record<string, string> = {
  attention_score: 'var(--primary)',
  virality_potential: 'var(--tribe)',
  conversion_potential: 'var(--mirofish)',
  audience_fit: 'var(--heat-cool)',
  memory_durability: 'var(--heat-warm)',
  backlash_risk: 'var(--heat-hot)',
  polarization_index: 'var(--heat-cold)',
};

const CHART_CONFIG: ChartConfig = {
  attention_score: { label: 'Attention', color: LINE_COLORS.attention_score },
  virality_potential: { label: 'Virality', color: LINE_COLORS.virality_potential },
  conversion_potential: { label: 'Conversion', color: LINE_COLORS.conversion_potential },
  audience_fit: { label: 'Audience Fit', color: LINE_COLORS.audience_fit },
  memory_durability: { label: 'Memory', color: LINE_COLORS.memory_durability },
  backlash_risk: { label: 'Backlash', color: LINE_COLORS.backlash_risk },
  polarization_index: { label: 'Polarization', color: LINE_COLORS.polarization_index },
};

interface ChartDataPoint {
  iteration: number;
  [key: string]: number | null;
}

function buildChartData(iterations: IterationRecord[]): ChartDataPoint[] {
  const grouped = new Map<number, IterationRecord[]>();
  for (const it of iterations) {
    const existing = grouped.get(it.iteration_number) ?? [];
    existing.push(it);
    grouped.set(it.iteration_number, existing);
  }

  const points: ChartDataPoint[] = [];
  for (const [iterNum, variants] of grouped) {
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
      for (const key of COMPOSITE_KEYS) point[key] = bestScores[key];
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
      <p className="font-mono text-[0.72rem] text-muted-foreground/55">
        › no iteration data for trajectory chart
      </p>
    );
  }

  const isSparkline = chartData.length <= 2;

  return (
    <div className="border border-border">
      <ChartContainer
        config={CHART_CONFIG}
        className={isSparkline ? 'aspect-[5/1] w-full p-2' : 'aspect-[5/2] w-full p-3'}
      >
        <LineChart data={chartData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid
            strokeDasharray="2 3"
            vertical={false}
            stroke="oklch(0.965 0.003 80 / 0.05)"
          />
          <XAxis
            dataKey="iteration"
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `i${v}`}
            tick={{ fontSize: 10, fill: 'oklch(0.55 0.008 70)' }}
            dy={4}
          />
          <YAxis
            domain={[0, 100]}
            tickLine={false}
            axisLine={false}
            width={28}
            tickCount={5}
            tick={{ fontSize: 10, fill: 'oklch(0.55 0.008 70)' }}
          />
          <ChartTooltip
            cursor={{ stroke: 'oklch(0.965 0.003 80 / 0.15)', strokeWidth: 1 }}
            content={
              <ChartTooltipContent
                labelFormatter={(value) => `Iteration ${value}`}
              />
            }
          />
          {!isSparkline && <ChartLegend content={<ChartLegendContent />} />}
          {COMPOSITE_KEYS.map((key) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={`var(--color-${key})`}
              strokeWidth={1.25}
              dot={false}
              activeDot={{ r: 2.5, strokeWidth: 0, fill: `var(--color-${key})` }}
              connectNulls
            />
          ))}
        </LineChart>
      </ChartContainer>
    </div>
  );
}
