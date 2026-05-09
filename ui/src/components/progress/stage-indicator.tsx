/**
 * Phase 5 session 3 — horizontal pipeline stage indicator.
 *
 * 5 named stages mirror the orchestrator's run_single_iteration emission:
 *   variants → tribe → mirofish → composite → analysis
 * (the report block is implicit — once analysis completes the stream
 * switches into per-layer report progress, surfaced in the dedicated
 * Report row below the indicator.)
 *
 * Visual style matches the existing campaign-detail aesthetic: monospace
 * field labels, oklch heat palette, no rainbow. Active stage shimmers
 * with a 1.4s slide so a viewer instantly knows the system is alive even
 * during a 3-minute mirofish prepare wait.
 *
 * Drives off the `useProgress` event stream — no polling, no derived
 * timers from the wall clock that could drift on a tab switch. Elapsed
 * counter reads from the `step_start` event's wallclock so a refresh
 * during a long stage shows correct elapsed.
 */

import { useEffect, useMemo, useState } from 'react';
import { cn } from '@/lib/utils';
import { useConfig } from '@/hooks/use-config';
import type { ProgressEvent } from '@/api/types';

export type StageName = 'variants' | 'tribe' | 'mirofish' | 'composite' | 'analysis';

interface StageDef {
  key: StageName;
  label: string;
  sub: string;
}

// Subtitles for variants/analysis are overridden by /api/config so the
// label reflects the actual model tier in use (Qwen on MI300X, Haiku/Opus
// on Anthropic dev). Other stages stay static.
function buildStages(agentLabel: string, orchestratorLabel: string): StageDef[] {
  return [
    { key: 'variants',  label: 'Variants',  sub: agentLabel.toLowerCase()         },
    { key: 'tribe',     label: 'Neural',    sub: 'tribe v2'                       },
    { key: 'mirofish',  label: 'Social',    sub: 'mirofish'                       },
    { key: 'composite', label: 'Composite', sub: '7 dims'                         },
    { key: 'analysis',  label: 'Analysis',  sub: orchestratorLabel.toLowerCase()  },
  ];
}

type StageState = 'pending' | 'active' | 'complete' | 'error';

interface StageStatus {
  state: StageState;
  startedAt: number | null;   // ms epoch from event timestamp
  detail: string | null;      // live counter, e.g. "v 2 / 3" during mirofish
}

function deriveStageStatuses(
  events: ProgressEvent[],
): { byStage: Record<StageName, StageStatus>; activeStage: StageName | null } {
  const byStage: Record<StageName, StageStatus> = {
    variants:  { state: 'pending', startedAt: null, detail: null },
    tribe:     { state: 'pending', startedAt: null, detail: null },
    mirofish:  { state: 'pending', startedAt: null, detail: null },
    composite: { state: 'pending', startedAt: null, detail: null },
    analysis:  { state: 'pending', startedAt: null, detail: null },
  };
  let activeStage: StageName | null = null;

  for (const e of events) {
    if (e.event === 'step_start' && e.step && e.step in byStage) {
      const stage = e.step as StageName;
      byStage[stage].state = 'active';
      byStage[stage].startedAt = e.timestamp ? Date.parse(e.timestamp) : Date.now();
      activeStage = stage;
    } else if (e.event === 'step_complete' && e.step && e.step in byStage) {
      const stage = e.step as StageName;
      byStage[stage].state = 'complete';
      byStage[stage].detail = null;
      if (activeStage === stage) activeStage = null;
    } else if (e.event === 'mirofish_progress' && e.variant_index && e.variants_total) {
      // Live counter during the longest stage.
      byStage.mirofish.detail = `variant ${e.variant_index} / ${e.variants_total}`;
    } else if (e.event === 'campaign_error') {
      // Mark the currently-active stage as errored so the failure is
      // localised rather than rendered as a global red banner.
      if (activeStage) byStage[activeStage].state = 'error';
    }
  }

  return { byStage, activeStage };
}

// ─── Component ──────────────────────────────────────────────────────────

interface StageIndicatorProps {
  events: ProgressEvent[];
  /** When true, rendering becomes static (run finished) — no live elapsed tick. */
  paused?: boolean;
  className?: string;
}

export function StageIndicator({ events, paused = false, className }: StageIndicatorProps) {
  const { byStage, activeStage } = useMemo(() => deriveStageStatuses(events), [events]);
  const { data: config } = useConfig();
  const STAGES = useMemo(
    () =>
      buildStages(
        config?.agent_model?.label ?? 'haiku draft',
        config?.orchestrator_model?.label ?? 'opus',
      ),
    [config?.agent_model?.label, config?.orchestrator_model?.label],
  );

  // Live elapsed for the active stage. ticker only mounts a setInterval
  // when there's actually an active stage so an idle StageIndicator
  // burns no timers.
  const activeStartedAt = activeStage ? byStage[activeStage].startedAt : null;
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    if (paused || !activeStartedAt) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [paused, activeStartedAt]);

  return (
    <div
      className={cn(
        'flex flex-col gap-1.5 border border-border bg-card/40 px-3 py-2',
        className,
      )}
    >
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-mono text-[0.6rem] tracking-[0.12em] text-muted-foreground uppercase">
          Pipeline
        </span>
        {activeStage && !paused && (
          <span className="font-mono text-[0.6rem] tabular-nums text-muted-foreground">
            {byStage[activeStage].detail ?? STAGES.find(s => s.key === activeStage)?.sub}
            {activeStartedAt && (
              <span className="ml-2 text-foreground/70">
                {formatElapsed(now - activeStartedAt)}
              </span>
            )}
          </span>
        )}
      </div>

      <ol className="grid grid-cols-5 gap-2">
        {STAGES.map((stage, i) => {
          const status = byStage[stage.key];
          const isActive = status.state === 'active';
          const isComplete = status.state === 'complete';
          const isError = status.state === 'error';
          return (
            <li key={stage.key} className="flex flex-col gap-1">
              <div className="relative h-[3px] overflow-hidden bg-border/50">
                <div
                  className={cn(
                    'absolute inset-y-0 left-0 transition-all duration-500',
                    isComplete && 'w-full bg-foreground/55',
                    isError && 'w-full bg-destructive',
                    isActive && 'w-full bg-primary shimmer',
                    status.state === 'pending' && 'w-0',
                  )}
                />
              </div>
              <div className="flex items-baseline justify-between gap-1.5">
                <div className="flex items-baseline gap-1.5 min-w-0">
                  <span
                    className={cn(
                      'font-mono text-[0.58rem] tabular-nums',
                      isActive ? 'text-primary' : 'text-muted-foreground/55',
                    )}
                  >
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span
                    className={cn(
                      'text-[0.74rem] font-medium tracking-tight truncate',
                      isComplete && 'text-foreground/85',
                      isActive && 'text-foreground',
                      isError && 'text-destructive',
                      status.state === 'pending' && 'text-muted-foreground/60',
                    )}
                  >
                    {stage.label}
                  </span>
                </div>
                <span className="font-mono text-[0.55rem] tracking-[0.08em] text-muted-foreground/55 uppercase truncate">
                  {stage.sub}
                </span>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function formatElapsed(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return '0s';
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return r === 0 ? `${m}m` : `${m}m ${r}s`;
}
