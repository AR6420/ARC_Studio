/**
 * Real-time campaign progress display with iteration tracking, step labels, and ETA.
 *
 * Per D-06: Inline in campaign detail, not a separate page.
 * Per D-07: Premium visual treatment -- segmented pipeline, animated active step,
 *           collapsible event log with monospace timestamp entries.
 *
 * Connects to the SSE progress endpoint via the useProgress hook.
 */

import { useState, useMemo } from 'react';
import {
  CheckCircle,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Loader2,
  Wifi,
  WifiOff,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useProgress } from '@/hooks/use-progress';
import type { ProgressEvent } from '@/api/types';

// -- Step label mapping --

const STEP_LABELS: Record<string, string> = {
  generating: 'Generating Variants',
  scoring: 'Neural Scoring (TRIBE v2)',
  simulating: 'Social Simulation (MiroFish)',
  analyzing: 'Cross-System Analysis',
  checking: 'Evaluating Thresholds',
};

const STEP_ORDER = ['generating', 'scoring', 'simulating', 'analyzing', 'checking'];

function formatStepLabel(step: string | null): string {
  if (!step) return 'Initializing';
  return STEP_LABELS[step] ?? step;
}

// -- ETA formatting --

function formatEta(seconds: number | null): string {
  if (seconds === null || seconds <= 0) return '';
  if (seconds < 60) return `~${Math.ceil(seconds)}s remaining`;
  const minutes = Math.floor(seconds / 60);
  const secs = Math.ceil(seconds % 60);
  if (secs === 0) return `~${minutes}m remaining`;
  return `~${minutes}m ${secs}s remaining`;
}

// -- Event log formatting --

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

function formatEventLabel(event: ProgressEvent): string {
  const type = event.event.replace(/_/g, ' ');
  if (event.step) {
    return `${type} -- ${formatStepLabel(event.step)}`;
  }
  if (event.event === 'iteration_start' || event.event === 'iteration_complete') {
    return `${type} (${event.iteration}/${event.max_iterations})`;
  }
  return type;
}

// -- Sub-components --

interface IterationSegmentsProps {
  current: number;
  max: number;
  stepIndex: number;
  totalSteps: number;
}

function IterationSegments({ current, max, stepIndex, totalSteps }: IterationSegmentsProps) {
  if (max === 0) return null;

  const segments = Array.from({ length: max }, (_, i) => {
    const iterNum = i + 1;
    if (iterNum < current) return 'complete' as const;
    if (iterNum === current) return 'active' as const;
    return 'pending' as const;
  });

  // Width of partially filled segment within the active iteration
  const activeProgress = totalSteps > 0 ? (stepIndex / totalSteps) * 100 : 0;

  return (
    <div className="flex items-center gap-1">
      {segments.map((status, i) => (
        <div
          key={i}
          className={cn(
            'relative h-2 flex-1 rounded-full overflow-hidden transition-all duration-500',
            status === 'complete' && 'bg-primary',
            status === 'pending' && 'bg-muted',
            status === 'active' && 'bg-muted',
          )}
        >
          {status === 'active' && (
            <div
              className="absolute inset-y-0 left-0 rounded-full bg-primary animate-pulse transition-[width] duration-700 ease-out"
              style={{ width: `${Math.max(activeProgress, 8)}%` }}
            />
          )}
        </div>
      ))}
    </div>
  );
}

interface StepPipelineProps {
  currentStep: string | null;
  isComplete: boolean;
  isError: boolean;
}

function StepPipeline({ currentStep, isComplete, isError }: StepPipelineProps) {
  const activeIndex = currentStep ? STEP_ORDER.indexOf(currentStep) : -1;

  return (
    <div className="flex items-center gap-0.5">
      {STEP_ORDER.map((step, i) => {
        const isDone = isComplete || (activeIndex >= 0 && i < activeIndex);
        const isActive = !isComplete && !isError && i === activeIndex;
        const isPending = !isDone && !isActive;

        return (
          <div key={step} className="flex items-center gap-0.5 flex-1 min-w-0">
            <div
              className={cn(
                'h-1 flex-1 rounded-full transition-all duration-500',
                isDone && 'bg-primary',
                isActive && 'bg-primary/60 animate-pulse',
                isPending && 'bg-muted',
                isError && i === activeIndex && 'bg-destructive/60 animate-pulse',
              )}
            />
          </div>
        );
      })}
    </div>
  );
}

interface EventLogProps {
  events: ProgressEvent[];
}

function EventLog({ events }: EventLogProps) {
  const [expanded, setExpanded] = useState(false);
  const recentEvents = useMemo(() => events.slice(-8).reverse(), [events]);

  if (events.length === 0) return null;

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5" />
        )}
        Event log ({events.length} events)
      </button>
      {expanded && (
        <div className="mt-2 max-h-36 overflow-y-auto rounded-md border border-border bg-background/50 p-2">
          {recentEvents.map((evt, i) => (
            <div
              key={`${evt.timestamp}-${i}`}
              className="flex gap-2 py-0.5 text-xs font-mono text-muted-foreground animate-in fade-in-0 duration-300"
            >
              <span className="text-muted-foreground/60 shrink-0">
                {formatEventTime(evt.timestamp)}
              </span>
              <span className="truncate">{formatEventLabel(evt)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// -- Main component --

interface ProgressStreamProps {
  campaignId: string;
}

export function ProgressStream({ campaignId }: ProgressStreamProps) {
  const {
    events,
    isConnected,
    isComplete,
    isError,
    currentStep,
    progress,
  } = useProgress(campaignId);

  const { iteration, maxIterations, stepIndex, totalSteps, etaSeconds } = progress;
  const eta = formatEta(etaSeconds);

  // Terminal states
  if (isComplete && !isError) {
    return (
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-score-green/15">
            <CheckCircle className="h-5 w-5 text-score-green" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">Campaign Complete</p>
            <p className="text-xs text-muted-foreground">
              All {maxIterations} iteration{maxIterations !== 1 ? 's' : ''} finished successfully
            </p>
          </div>
        </div>
        <div className="mt-3">
          <IterationSegments
            current={maxIterations + 1}
            max={maxIterations}
            stepIndex={0}
            totalSteps={0}
          />
        </div>
        <EventLog events={events} />
      </div>
    );
  }

  if (isError) {
    const errorEvent = events.findLast((e) => e.event === 'campaign_error');
    const errorMsg = errorEvent?.data?.error ?? errorEvent?.data?.message ?? 'An error occurred';

    return (
      <div className="rounded-lg border border-destructive/30 bg-card p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/15">
            <AlertTriangle className="h-5 w-5 text-destructive" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">Campaign Failed</p>
            <p className="text-xs text-muted-foreground max-w-md truncate">
              {String(errorMsg)}
            </p>
          </div>
        </div>
        <div className="mt-3">
          <IterationSegments
            current={iteration}
            max={maxIterations}
            stepIndex={stepIndex}
            totalSteps={totalSteps}
          />
        </div>
        <EventLog events={events} />
      </div>
    );
  }

  // Active / connecting state
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      {/* Header: connection indicator + iteration count + ETA */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className="relative flex items-center justify-center">
            {isConnected ? (
              <Zap className="h-4 w-4 text-primary animate-pulse" />
            ) : (
              <Loader2 className="h-4 w-4 text-muted-foreground animate-spin" />
            )}
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">
              {iteration > 0
                ? `Iteration ${iteration} of ${maxIterations}`
                : 'Connecting to campaign...'}
            </p>
            {currentStep && (
              <p className="text-xs text-primary/80">
                {formatStepLabel(currentStep)}
                {totalSteps > 0 && (
                  <span className="text-muted-foreground ml-1.5">
                    -- step {stepIndex} of {totalSteps}
                  </span>
                )}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {eta && (
            <span className="text-xs text-muted-foreground tabular-nums">{eta}</span>
          )}
          <div
            className={cn(
              'flex items-center gap-1 text-xs',
              isConnected ? 'text-score-green' : 'text-muted-foreground',
            )}
            title={isConnected ? 'Connected to event stream' : 'Disconnected'}
          >
            {isConnected ? (
              <Wifi className="h-3 w-3" />
            ) : (
              <WifiOff className="h-3 w-3" />
            )}
          </div>
        </div>
      </div>

      {/* Iteration segment bar */}
      {maxIterations > 0 && (
        <div className="mb-3">
          <IterationSegments
            current={iteration}
            max={maxIterations}
            stepIndex={stepIndex}
            totalSteps={totalSteps}
          />
          <div className="flex justify-between mt-1">
            <span className="text-[10px] text-muted-foreground/50">Iteration 1</span>
            <span className="text-[10px] text-muted-foreground/50">
              Iteration {maxIterations}
            </span>
          </div>
        </div>
      )}

      {/* Step pipeline (fine-grained within the current iteration) */}
      {currentStep && (
        <div className="mb-1">
          <StepPipeline
            currentStep={currentStep}
            isComplete={isComplete}
            isError={isError}
          />
          <div className="flex justify-between mt-1">
            {STEP_ORDER.map((step) => {
              const activeIdx = currentStep ? STEP_ORDER.indexOf(currentStep) : -1;
              const stepIdx = STEP_ORDER.indexOf(step);
              const isActiveStep = stepIdx === activeIdx;
              return (
                <span
                  key={step}
                  className={cn(
                    'text-[9px] max-w-[18%] text-center truncate transition-colors duration-300',
                    isActiveStep ? 'text-primary font-medium' : 'text-muted-foreground/40',
                  )}
                >
                  {STEP_LABELS[step]}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Event log */}
      <EventLog events={events} />
    </div>
  );
}
