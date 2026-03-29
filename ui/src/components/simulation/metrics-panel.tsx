/**
 * MiroFish simulation metrics panel displaying 8 key social metrics.
 *
 * Each metric rendered as an individual card with contextual icon,
 * formatted value, and descriptive label. Handles null/missing data.
 */

import {
  BarChart3,
  GitFork,
  MessageSquare,
  Share2,
  TrendingUp,
  Users,
  ArrowUpDown,
  Activity,
} from 'lucide-react';
import type { MirofishMetrics } from '@/api/types';
import { Card, CardContent } from '@/components/ui/card';

interface MetricCardConfig {
  key: keyof MirofishMetrics;
  label: string;
  icon: typeof Share2;
  format: (value: number | number[]) => string;
  description: string;
}

const METRIC_CONFIGS: MetricCardConfig[] = [
  {
    key: 'organic_shares',
    label: 'Organic Shares',
    icon: Share2,
    format: (v) => String(v),
    description: 'Total unprompted shares across platforms',
  },
  {
    key: 'sentiment_trajectory',
    label: 'Sentiment',
    icon: Activity,
    format: (v) => {
      const arr = v as number[];
      if (!arr.length) return 'No data';
      const latest = arr[arr.length - 1];
      const trend = arr.length > 1 ? latest - arr[arr.length - 2] : 0;
      const arrow = trend > 0.01 ? ' ^' : trend < -0.01 ? ' v' : '';
      return `${latest.toFixed(2)}${arrow}`;
    },
    description: 'Latest sentiment value with trend direction',
  },
  {
    key: 'counter_narrative_count',
    label: 'Counter-narratives',
    icon: MessageSquare,
    format: (v) => String(v),
    description: 'Opposing narratives that emerged',
  },
  {
    key: 'peak_virality_cycle',
    label: 'Peak Virality',
    icon: TrendingUp,
    format: (v) => `Round ${v}`,
    description: 'Simulation round with highest activity',
  },
  {
    key: 'sentiment_drift',
    label: 'Sentiment Drift',
    icon: ArrowUpDown,
    format: (v) => `${((v as number) * 100).toFixed(1)}%`,
    description: 'Net sentiment change over simulation',
  },
  {
    key: 'coalition_formation',
    label: 'Coalitions',
    icon: Users,
    format: (v) => `${v} groups`,
    description: 'Distinct opinion groups that formed',
  },
  {
    key: 'influence_concentration',
    label: 'Influence Gini',
    icon: BarChart3,
    format: (v) => `${((v as number) * 100).toFixed(1)}%`,
    description: 'Concentration of influence (0=equal, 1=monopoly)',
  },
  {
    key: 'platform_divergence',
    label: 'Platform Divergence',
    icon: GitFork,
    format: (v) => `${((v as number) * 100).toFixed(1)}%`,
    description: 'Difference in behavior between platforms',
  },
];

interface MetricsPanelProps {
  metrics: MirofishMetrics | null | undefined;
}

export function MetricsPanel({ metrics }: MetricsPanelProps) {
  if (!metrics) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-dashed border-muted-foreground/25 py-12">
        <p className="text-sm text-muted-foreground">
          No simulation metrics available for this iteration.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {METRIC_CONFIGS.map((config) => {
        const rawValue = metrics[config.key];
        const Icon = config.icon;

        return (
          <Card
            key={config.key}
            size="sm"
            className="group relative overflow-hidden transition-colors hover:ring-foreground/20"
          >
            <CardContent className="flex flex-col gap-1.5">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Icon className="size-3.5 shrink-0" />
                <span className="truncate text-xs font-medium">
                  {config.label}
                </span>
              </div>
              <p className="font-mono text-lg font-semibold tabular-nums tracking-tight text-foreground">
                {rawValue != null ? config.format(rawValue) : 'N/A'}
              </p>
              <p className="text-[11px] leading-tight text-muted-foreground/70">
                {config.description}
              </p>
            </CardContent>
            {/* Subtle accent line at top */}
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent" />
          </Card>
        );
      })}
    </div>
  );
}
