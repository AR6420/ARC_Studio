/**
 * Sentiment timeline area chart showing how aggregate sentiment evolved
 * across simulation rounds using Recharts.
 *
 * Uses the shadcn ChartContainer for consistent theming and CSS variable
 * integration with the dark-first design system.
 */

import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from 'recharts';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart';
import type { ChartConfig } from '@/components/ui/chart';

const chartConfig = {
  sentiment: {
    label: 'Sentiment',
    color: 'oklch(0.72 0.15 230)',
  },
} satisfies ChartConfig;

interface SentimentTimelineProps {
  trajectory: number[] | null | undefined;
}

export function SentimentTimeline({ trajectory }: SentimentTimelineProps) {
  if (!trajectory || trajectory.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-dashed border-muted-foreground/25 py-16">
        <p className="text-sm text-muted-foreground">
          No sentiment trajectory data available.
        </p>
      </div>
    );
  }

  const data = trajectory.map((value, index) => ({
    round: index + 1,
    sentiment: Number(value.toFixed(3)),
  }));

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1">
        <h3 className="text-sm font-medium text-foreground">
          Sentiment Over Time
        </h3>
        <span className="text-xs tabular-nums text-muted-foreground">
          {trajectory.length} rounds
        </span>
      </div>
      <ChartContainer config={chartConfig} className="aspect-[3/1] w-full">
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="sentimentGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-sentiment)" stopOpacity={0.3} />
              <stop offset="95%" stopColor="var(--color-sentiment)" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid
            strokeDasharray="3 3"
            vertical={false}
            stroke="oklch(0.3 0.01 260 / 0.4)"
          />
          <XAxis
            dataKey="round"
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `R${v}`}
            fontSize={11}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            width={40}
            tickFormatter={(v: number) => v.toFixed(1)}
            fontSize={11}
          />
          <ChartTooltip
            content={
              <ChartTooltipContent
                labelFormatter={(_, payload) => {
                  const round = payload?.[0]?.payload?.round;
                  return `Round ${round ?? ''}`;
                }}
              />
            }
          />
          <Area
            type="monotone"
            dataKey="sentiment"
            stroke="var(--color-sentiment)"
            strokeWidth={2}
            fill="url(#sentimentGradient)"
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        </AreaChart>
      </ChartContainer>
    </div>
  );
}
