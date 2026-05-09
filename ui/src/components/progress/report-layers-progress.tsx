/**
 * Phase 5 session 3 — per-layer report progress strip.
 *
 * Surfaces the 4 report layers (verdict, scorecard, deep analysis, mass
 * psychology) once the iteration loop has finished. Each layer animates
 * from pending → active → complete. Renders nothing until the first
 * `report_generating` event arrives, so it doesn't visually shout
 * during the much longer pre-report stages.
 */

import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import type { ProgressEvent } from '@/api/types';

const LAYERS: { key: string; label: string }[] = [
  { key: 'verdict',          label: 'Verdict'         },
  { key: 'scorecard',        label: 'Scorecard'       },
  { key: 'deep_analysis',    label: 'Deep analysis'   },
  { key: 'mass_psychology',  label: 'Mass psychology' },
];

type LayerState = 'pending' | 'active' | 'complete';

function deriveLayerStates(events: ProgressEvent[]): {
  byLayer: Record<string, LayerState>;
  reportStarted: boolean;
  reportComplete: boolean;
  reportFailed: string | null;
} {
  const byLayer: Record<string, LayerState> = {
    verdict: 'pending',
    scorecard: 'pending',
    deep_analysis: 'pending',
    mass_psychology: 'pending',
  };
  let reportStarted = false;
  let reportComplete = false;
  let reportFailed: string | null = null;

  for (const e of events) {
    if (e.event === 'report_generating') reportStarted = true;
    else if (e.event === 'report_complete') reportComplete = true;
    else if (e.event === 'report_failed') {
      reportFailed = (e.data as { error?: string } | null)?.error ?? 'unknown';
    } else if (e.event === 'report_layer_start' && e.layer && e.layer in byLayer) {
      byLayer[e.layer] = 'active';
      reportStarted = true;
    } else if (e.event === 'report_layer_complete' && e.layer && e.layer in byLayer) {
      byLayer[e.layer] = 'complete';
    }
  }

  return { byLayer, reportStarted, reportComplete, reportFailed };
}

interface ReportLayersProgressProps {
  events: ProgressEvent[];
  className?: string;
}

export function ReportLayersProgress({ events, className }: ReportLayersProgressProps) {
  const { byLayer, reportStarted, reportComplete, reportFailed } = useMemo(
    () => deriveLayerStates(events),
    [events],
  );

  if (!reportStarted) return null;

  return (
    <div
      className={cn(
        'flex flex-col gap-2 border border-border bg-card/30 p-3',
        className,
      )}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-[0.62rem] tracking-[0.12em] text-muted-foreground uppercase">
          Report layers
        </span>
        <span className="font-mono text-[0.62rem] tabular-nums text-muted-foreground">
          {reportComplete ? 'complete' : reportFailed ? 'partial' : 'generating'}
        </span>
      </div>
      <ul className="flex flex-wrap gap-x-3 gap-y-1.5">
        {LAYERS.map((layer) => {
          const state = byLayer[layer.key];
          return (
            <li
              key={layer.key}
              className={cn(
                'flex items-center gap-1.5 font-mono text-[0.7rem] tabular-nums',
                state === 'complete' && 'text-foreground/85',
                state === 'active' && 'text-primary',
                state === 'pending' && 'text-muted-foreground/55',
              )}
            >
              <span
                className={cn(
                  'inline-block h-1.5 w-1.5 rounded-full',
                  state === 'complete' && 'bg-foreground/55',
                  state === 'active' && 'bg-primary shimmer',
                  state === 'pending' && 'bg-border',
                )}
              />
              <span>{layer.label}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
