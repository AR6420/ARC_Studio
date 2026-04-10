/**
 * Sentiment timeline — thin line chart, MiroFish teal, no area fill.
 *
 * Renders aggregate sentiment across simulation rounds as a simple
 * monotone line over a dashed horizontal grid. Very short series
 * (< 5 rounds) cap the chart at 200px so the canvas doesn't dwarf a
 * single data point.
 */

import { CartesianGrid, Line, LineChart, XAxis, YAxis, ReferenceLine } from 'recharts';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart';
import type { ChartConfig } from '@/components/ui/chart';
import { cn } from '@/lib/utils';

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
      <div className="flex flex-col gap-3">
        <SentimentHeader rounds={0} latest={null} delta={null} />
        <div className="flex min-h-[120px] items-center justify-center border border-dashed border-border px-4 py-8 text-center">
          <p className="font-mono text-[0.78rem] text-muted-foreground">
            sentiment trajectory not available
          </p>
        </div>
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
  const isSparse = trajectory.length < 5;

  return (
    <div className="flex flex-col gap-3">
      <SentimentHeader
        rounds={trajectory.length}
        latest={latest}
        delta={delta}
      />

      <div className="border border-border">
        <ChartContainer
          config={chartConfig}
          className={cn(
            'w-full p-2',
            isSparse ? 'h-[200px] max-h-[200px]' : 'aspect-[4/1]',
          )}
        >
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid
              strokeDasharray="2 3"
              vertical={false}
              stroke="oklch(0.965 0.003 80 / 0.07)"
            />
            <XAxis
              dataKey="round"
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `R${v}`}
              tick={{ fontSize: 10, fill: 'oklch(0.62 0.008 70)' }}
              dy={4}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={32}
              tickFormatter={(v: number) => v.toFixed(1)}
              tick={{ fontSize: 10, fill: 'oklch(0.62 0.008 70)' }}
            />
            <ReferenceLine
              y={0}
              stroke="oklch(0.965 0.003 80 / 0.12)"
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
              strokeWidth={1.5}
              dot={isSparse ? { r: 2.5, strokeWidth: 0, fill: 'var(--color-sentiment)' } : false}
              activeDot={{ r: 3, strokeWidth: 0, fill: 'var(--color-sentiment)' }}
            />
          </LineChart>
        </ChartContainer>
      </div>
    </div>
  );
}

function SentimentHeader({
  rounds,
  latest,
  delta,
}: {
  rounds: number;
  latest: number | null;
  delta: number | null;
}) {
  return (
    <div className="flex items-baseline justify-between gap-6 border-b border-border pb-2">
      <div className="flex items-baseline gap-3">
        <h3 className="text-[0.95rem] font-medium tracking-[-0.005em] text-foreground">
          Sentiment timeline
        </h3>
        <span className="font-mono text-[0.6rem] tracking-[0.1em] text-mirofish uppercase">
          mirofish
        </span>
      </div>
      {rounds > 0 && (
        <div className="flex items-center gap-4 font-mono text-[0.72rem] tabular-nums">
          <span className="text-foreground/75">
            <span className="tracking-[0.08em] text-muted-foreground uppercase">
              rounds
            </span>{' '}
            {rounds}
          </span>
          {latest != null && (
            <span className="text-foreground/75">
              <span className="tracking-[0.08em] text-muted-foreground uppercase">
                latest
              </span>{' '}
              <span className="text-foreground">{latest.toFixed(2)}</span>
            </span>
          )}
          {delta != null && (
            <span className="text-foreground/75">
              <span className="tracking-[0.08em] text-muted-foreground uppercase">
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
          )}
        </div>
      )}
    </div>
  );
}
