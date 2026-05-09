/**
 * Phase 5: per-window neural activation chart, playback-synced to a
 * companion video element (see VideoStimulusPlayer).
 *
 * Renders 4 channels derived from TRIBE's raw 7-dimension timeline (see
 * lib/timeline-channels.ts for the formulas). Visual style mirrors
 * IterationChart for consistency with the rest of the results view: thin
 * lines, dashed grid, monotone curve, dark amber palette.
 */

import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
} from '@/components/ui/chart';
import type { ChartConfig } from '@/components/ui/chart';
import {
  DISPLAY_CHANNEL_COLORS,
  DISPLAY_CHANNEL_LABELS,
  type DisplayChannel,
  type TimelinePoint,
} from '@/lib/timeline-channels';

const CHANNELS: DisplayChannel[] = [
  'visual_cortex',
  'auditory_cortex',
  'language_regions',
  'engagement',
];

const CHART_CONFIG: ChartConfig = {
  visual_cortex: {
    label: DISPLAY_CHANNEL_LABELS.visual_cortex,
    color: DISPLAY_CHANNEL_COLORS.visual_cortex,
  },
  auditory_cortex: {
    label: DISPLAY_CHANNEL_LABELS.auditory_cortex,
    color: DISPLAY_CHANNEL_COLORS.auditory_cortex,
  },
  language_regions: {
    label: DISPLAY_CHANNEL_LABELS.language_regions,
    color: DISPLAY_CHANNEL_COLORS.language_regions,
  },
  engagement: {
    label: DISPLAY_CHANNEL_LABELS.engagement,
    color: DISPLAY_CHANNEL_COLORS.engagement,
  },
};

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

interface TimelineChartProps {
  data: TimelinePoint[];
  /** Total stimulus duration in seconds; used to fix the X-axis domain. */
  durationSeconds: number;
  /** Current video playback position in seconds. Renders the playhead. */
  currentTimeSeconds: number;
}

export function TimelineChart({
  data,
  durationSeconds,
  currentTimeSeconds,
}: TimelineChartProps) {
  const chartData = useMemo(() => data, [data]);

  if (chartData.length === 0) {
    return (
      <p className="font-mono text-[0.72rem] text-muted-foreground/55">
        › no per-window timeline available for this stimulus
      </p>
    );
  }

  return (
    <div className="border border-border bg-card/40">
      <ChartContainer config={CHART_CONFIG} className="aspect-[5/2] w-full p-3">
        <LineChart
          data={chartData}
          margin={{ top: 8, right: 16, bottom: 4, left: 0 }}
        >
          <CartesianGrid
            strokeDasharray="2 3"
            vertical={false}
            stroke="oklch(0.965 0.003 80 / 0.05)"
          />
          <XAxis
            dataKey="t"
            type="number"
            domain={[0, durationSeconds]}
            tickLine={false}
            axisLine={false}
            tickFormatter={formatTime}
            tick={{ fontSize: 10, fill: 'oklch(0.55 0.008 70)' }}
            dy={4}
          />
          <YAxis
            domain={[0, 1]}
            tickLine={false}
            axisLine={false}
            width={28}
            tickCount={5}
            tickFormatter={(v: number) => v.toFixed(1)}
            tick={{ fontSize: 10, fill: 'oklch(0.55 0.008 70)' }}
          />
          <ChartTooltip
            cursor={{ stroke: 'oklch(0.965 0.003 80 / 0.15)', strokeWidth: 1 }}
            content={
              <ChartTooltipContent
                labelFormatter={(value) => `t = ${formatTime(Number(value))}`}
              />
            }
          />
          <ChartLegend content={<ChartLegendContent />} />
          {CHANNELS.map((key) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={`var(--color-${key})`}
              strokeWidth={1.5}
              dot={false}
              activeDot={{ r: 2.5, strokeWidth: 0, fill: `var(--color-${key})` }}
              isAnimationActive={false}
            />
          ))}
          {Number.isFinite(currentTimeSeconds) && currentTimeSeconds >= 0 && (
            <ReferenceLine
              x={currentTimeSeconds}
              stroke="var(--primary)"
              strokeWidth={1}
              strokeDasharray="3 2"
              ifOverflow="extendDomain"
            />
          )}
        </LineChart>
      </ChartContainer>
    </div>
  );
}
