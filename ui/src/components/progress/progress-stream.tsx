/**
 * Real-time campaign progress — terminal-style event log.
 *
 *   ┌─ campaign stream ─────────────── iter 2/4 · scoring · ~3m 15s ─┐
 *   │  11:23:04  iter          iteration 1 started                   │
 *   │  11:23:05  generating    creating 3 content variants           │
 *   │  11:23:18  scoring       tribe v2 scoring variant v1           │
 *   │  11:31:45  scoring       v1 scored  attn=72.4  emo=65.1        │
 *   │› 11:38:02  simulating    spawning 40 mirofish agents           │
 *   └───────────────────────────────────────────────────────────────┘
 *
 * No spinners, no pulsing bars — just a live monospace feed. Older
 * lines dim, the most recent line stays bright and gets a chevron.
 */

import { useEffect, useMemo, useRef } from 'react';
import { cn } from '@/lib/utils';
import { useProgress } from '@/hooks/use-progress';
import type { ProgressEvent } from '@/api/types';

// ─── Formatting helpers ────────────────────────────────────────────────

const STEP_LABEL: Record<string, string> = {
  generating: 'generating',
  scoring: 'scoring',
  simulating: 'simulating',
  analyzing: 'analyzing',
  checking: 'checking',
};

function formatEventTime(timestamp: string): string {
  try {
    const d = new Date(timestamp);
    return d.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return '--:--:--';
  }
}

function formatEta(seconds: number | null): string {
  if (seconds == null || seconds <= 0) return '';
  if (seconds < 60) return `${Math.ceil(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const secs = Math.ceil(seconds % 60);
  if (secs === 0) return `${minutes}m`;
  return `${minutes}m ${secs}s`;
}

/** Short category label shown in the middle column. */
function eventCategory(event: ProgressEvent): string {
  if (event.step && STEP_LABEL[event.step]) return STEP_LABEL[event.step];
  switch (event.event) {
    case 'iteration_start':
    case 'iteration_complete':
    case 'iteration_update':
      return 'iter';
    case 'campaign_start':
      return 'start';
    case 'campaign_complete':
      return 'done';
    case 'campaign_error':
      return 'error';
    case 'variant_generated':
      return 'generating';
    case 'variant_scored':
      return 'scoring';
    default:
      return event.event.replace(/_/g, ' ').slice(0, 11);
  }
}

/** Human-readable message drawn from the event data. */
function eventMessage(event: ProgressEvent): string {
  const d = (event.data as Record<string, unknown> | null) ?? {};
  switch (event.event) {
    case 'iteration_start':
      return `iteration ${event.iteration} started`;
    case 'iteration_complete':
      return `iteration ${event.iteration} complete`;
    case 'campaign_start':
      return 'campaign started';
    case 'campaign_complete':
      return `all ${event.max_iterations} iteration${event.max_iterations !== 1 ? 's' : ''} finished`;
    case 'campaign_error': {
      const err = d.error ?? d.message ?? 'unknown error';
      return `error  ${String(err)}`;
    }
    case 'variant_generated': {
      const id = d.variant_id ?? d.id;
      const strategy = d.strategy;
      return strategy ? `variant ${String(id ?? '')}  ${String(strategy)}` : `variant ${String(id ?? '')} generated`;
    }
    case 'variant_scored': {
      const id = d.variant_id ?? d.id;
      const attn = d.attention_capture ?? d.attention_score;
      if (id && attn != null) {
        return `variant ${String(id)} scored  attn=${Number(attn).toFixed(1)}`;
      }
      return `variant ${String(id ?? '')} scored`;
    }
    default: {
      if (event.step) {
        const stepName = STEP_LABEL[event.step] ?? event.step;
        if (event.step_index != null && event.total_steps != null) {
          return `${stepName}  step ${event.step_index}/${event.total_steps}`;
        }
        return stepName;
      }
      return event.event.replace(/_/g, ' ');
    }
  }
}

// ─── Sub-components ────────────────────────────────────────────────────

interface EventLineProps {
  event: ProgressEvent;
  isLatest: boolean;
  isTerminal: 'complete' | 'error' | null;
}

function EventLine({ event, isLatest, isTerminal }: EventLineProps) {
  const isErrorEvent =
    event.event === 'campaign_error' || isTerminal === 'error';
  const isCompleteEvent =
    event.event === 'campaign_complete' ||
    (isTerminal === 'complete' && isLatest);
  const highlight = isLatest;

  const glyph = isErrorEvent
    ? '✕'
    : isCompleteEvent
      ? '✓'
      : highlight
        ? '›'
        : ' ';

  const categoryClass = isErrorEvent
    ? 'text-heat-hot/80'
    : isCompleteEvent
      ? 'text-heat-hot/80'
      : highlight
        ? 'text-primary'
        : 'text-muted-foreground/45';

  const messageClass = isErrorEvent
    ? 'text-heat-hot/90'
    : highlight
      ? 'text-foreground'
      : 'text-muted-foreground/55';

  return (
    <div className="grid grid-cols-[14px_74px_88px_minmax(0,1fr)] items-baseline gap-3 px-2 py-[1px] font-mono text-[0.7rem] leading-[1.55] tracking-[-0.002em]">
      <span
        className={cn(
          'tabular-nums',
          isErrorEvent
            ? 'text-heat-hot'
            : highlight
              ? 'text-primary animate-pulse'
              : 'text-muted-foreground/30',
        )}
      >
        {glyph}
      </span>
      <span className="tabular-nums text-muted-foreground/50">
        {formatEventTime(event.timestamp)}
      </span>
      <span className={cn('uppercase tracking-[0.06em]', categoryClass)}>
        {eventCategory(event)}
      </span>
      <span className={cn('truncate', messageClass)}>
        {eventMessage(event)}
      </span>
    </div>
  );
}

interface TerminalLogProps {
  events: ProgressEvent[];
  isComplete: boolean;
  isError: boolean;
  statusText: string;
  statusClass: string;
  iteration: number;
  maxIterations: number;
  eta: string;
}

function TerminalLog({
  events,
  isComplete,
  isError,
  statusText,
  statusClass,
  iteration,
  maxIterations,
  eta,
}: TerminalLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events.length]);

  const terminal: 'complete' | 'error' | null = isError
    ? 'error'
    : isComplete
      ? 'complete'
      : null;

  return (
    <div className="border border-border bg-sidebar">
      {/* Terminal title bar */}
      <div className="flex items-baseline justify-between gap-4 border-b border-border px-3 py-1.5">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'inline-block size-1.5 rounded-full',
              isError
                ? 'bg-heat-hot'
                : isComplete
                  ? 'bg-[oklch(0.72_0.15_150)]'
                  : 'bg-primary animate-pulse',
            )}
          />
          <span className="font-mono text-[0.58rem] tracking-[0.14em] text-muted-foreground/80 uppercase">
            campaign stream
          </span>
        </div>
        <div className="flex items-baseline gap-3 font-mono text-[0.62rem] tabular-nums">
          {maxIterations > 0 && (
            <span className="text-muted-foreground/60">
              <span className="tracking-[0.1em] text-muted-foreground/45 uppercase">
                iter
              </span>{' '}
              <span className="text-foreground/80">
                {iteration}/{maxIterations}
              </span>
            </span>
          )}
          <span className="text-muted-foreground/60">
            <span className="tracking-[0.1em] text-muted-foreground/45 uppercase">
              step
            </span>{' '}
            <span className={statusClass}>{statusText}</span>
          </span>
          {eta && (
            <span className="text-muted-foreground/60">
              <span className="tracking-[0.1em] text-muted-foreground/45 uppercase">
                eta
              </span>{' '}
              <span className="text-foreground/80">{eta}</span>
            </span>
          )}
          <span className="text-muted-foreground/40">
            {events.length.toString().padStart(3, '0')}
          </span>
        </div>
      </div>

      {/* Log body */}
      <div
        ref={scrollRef}
        className="max-h-[260px] min-h-[96px] overflow-y-auto py-2"
      >
        {events.length === 0 ? (
          <div className="px-3 py-1 font-mono text-[0.7rem] text-muted-foreground/50">
            <span className="mr-2 animate-pulse text-primary">›</span>
            connecting to event stream…
          </div>
        ) : (
          events.map((event, i) => {
            const isLatest = i === events.length - 1;
            return (
              <EventLine
                key={`${event.timestamp}-${i}`}
                event={event}
                isLatest={isLatest}
                isTerminal={terminal}
              />
            );
          })
        )}
      </div>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────

interface ProgressStreamProps {
  campaignId: string;
}

export function ProgressStream({ campaignId }: ProgressStreamProps) {
  const { events, isConnected, isComplete, isError, currentStep, progress } =
    useProgress(campaignId);
  const { iteration, maxIterations, etaSeconds } = progress;
  const eta = formatEta(etaSeconds);

  const { statusText, statusClass } = useMemo(() => {
    if (isError) return { statusText: 'failed', statusClass: 'text-heat-hot' };
    if (isComplete)
      return {
        statusText: 'complete',
        statusClass: 'text-[oklch(0.72_0.15_150)]',
      };
    if (!isConnected)
      return {
        statusText: 'connecting',
        statusClass: 'text-muted-foreground/60',
      };
    return {
      statusText: currentStep ? STEP_LABEL[currentStep] ?? currentStep : 'initializing',
      statusClass: 'text-primary',
    };
  }, [isError, isComplete, isConnected, currentStep]);

  return (
    <TerminalLog
      events={events}
      isComplete={isComplete}
      isError={isError}
      statusText={statusText}
      statusClass={statusClass}
      iteration={iteration}
      maxIterations={maxIterations}
      eta={eta}
    />
  );
}
