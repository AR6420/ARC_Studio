/**
 * Sentiment timeline — thin line chart, MiroFish teal, no area fill.
 *
 * Renders aggregate sentiment across simulation rounds as a simple
 * monotone line over a dashed horizontal grid.
 */

import { CartesianGrid, Line, LineChart, XAxis, YAxis, ReferenceLine } from 'recharts';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart';
import type { ChartConfig } from '@/components/ui/chart';

const chartConfig = {
  sentiment: {
    label: 'Sentiment',
    color: 'var(--mirofish)',
  },
} satisfies ChartConfig;

interface SentimentTimelineProps {
  trajectory: number[] | null | undefined;
}

export function SentimentTimeline({ trajectory }: SentimentTimelineProps) {
  if (!trajectory || trajectory.length === 0) {
    return (
      <div className="border border-dashed border-border px-4 py-6 font-mono text-[0.7rem] text-muted-foreground/55">
        › sentiment trajectory not available
      </div>
    );
  }

  const data = trajectory.map((value, index) => ({
    round: index + 1,
    sentiment: Number(value.toFixed(3)),
  }));

  const latest = trajectory[trajectory.length - 1];
  const initial = trajectory[0];
  const delta = latest - initial;

  return (
    <div className="flex flex-col gap-3">
      {/* Header line — label + summary metrics */}
      <div className="flex items-baseline justify-between gap-6">
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-[0.6rem] font-semibold tracking-[0.16em] text-foreground/90 uppercase">
            Sentiment Timeline
          </span>
          <span className="font-mono text-[0.58rem] tracking-[0.1em] text-mirofish/70 uppercase">
            mirofish
          </span>
        </div>
        <div className="flex items-center gap-4 font-mono text-[0.7rem] tabular-nums">
          <span className="text-muted-foreground/60">
            <span className="tracking-[0.08em] text-muted-foreground/50 uppercase">
              rounds
            </span>{' '}
            {trajectory.length}
          </span>
          <span className="text-muted-foreground/60">
            <span className="tracking-[0.08em] text-muted-foreground/50 uppercase">
              latest
            </span>{' '}
            <span className="text-foreground">{latest.toFixed(2)}</span>
          </span>
          <span className="text-muted-foreground/60">
            <span className="tracking-[0.08em] text-muted-foreground/50 uppercase">
              Δ
            </span>{' '}
            <span
              className={
                delta > 0.01
                  ? 'text-[oklch(0.72_0.15_150)]'
                  : delta < -0.01
                    ? 'text-[oklch(0.68_0.20_22)]'
                    : 'text-foreground'
              }
            >
              {delta >= 0 ? '+' : ''}
              {delta.toFixed(2)}
            </span>
          </span>
        </div>
      </div>

      <div className="border border-border">
        <ChartContainer config={chartConfig} className="aspect-[4/1] w-full p-2">
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid
              strokeDasharray="2 3"
              vertical={false}
              stroke="oklch(0.965 0.003 80 / 0.05)"
            />
            <XAxis
              dataKey="round"
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `R${v}`}
              tick={{ fontSize: 10, fill: 'oklch(0.55 0.008 70)' }}
              dy={4}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={32}
              tickFormatter={(v: number) => v.toFixed(1)}
              tick={{ fontSize: 10, fill: 'oklch(0.55 0.008 70)' }}
            />
            <ReferenceLine
              y={0}
              stroke="oklch(0.965 0.003 80 / 0.1)"
              strokeDasharray="2 3"
            />
            <ChartTooltip
              cursor={{ stroke: 'oklch(0.965 0.003 80 / 0.15)', strokeWidth: 1 }}
              content={
                <ChartTooltipContent
                  labelFormatter={(_, payload) => {
                    const round = payload?.[0]?.payload?.round;
                    return `Round ${round ?? ''}`;
                  }}
                />
              }
            />
            <Line
              type="monotone"
              dataKey="sentiment"
              stroke="var(--color-sentiment)"
              strokeWidth={1.25}
              dot={false}
              activeDot={{ r: 3, strokeWidth: 0, fill: 'var(--color-sentiment)' }}
            />
          </LineChart>
        </ChartContainer>
      </div>
    </div>
  );
}
