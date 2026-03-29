/**
 * SSE progress streaming hook for real-time campaign execution feedback.
 *
 * Wraps the native EventSource API to connect to the orchestrator's
 * GET /api/campaigns/{id}/progress SSE endpoint.
 *
 * Per Pitfall 2: Uses addEventListener for named event types (NOT onmessage).
 * Per Pitfall 4: Invalidates React Query cache on campaign_complete.
 * Per Pitfall 6: Closes EventSource in useEffect cleanup on unmount.
 */

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { API_BASE } from '@/api/client';
import type { ProgressEvent } from '@/api/types';

const TERMINAL_EVENTS = new Set(['campaign_complete', 'campaign_error']);

const EVENT_TYPES = [
  'iteration_start',
  'step_start',
  'step_complete',
  'iteration_complete',
  'threshold_check',
  'convergence_check',
  'campaign_complete',
  'campaign_error',
] as const;

export interface ProgressState {
  iteration: number;
  maxIterations: number;
  stepIndex: number;
  totalSteps: number;
  etaSeconds: number | null;
}

export interface UseProgressReturn {
  events: ProgressEvent[];
  latestEvent: ProgressEvent | null;
  isConnected: boolean;
  isComplete: boolean;
  isError: boolean;
  currentStep: string | null;
  progress: ProgressState;
}

export function useProgress(campaignId: string | null): UseProgressReturn {
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [isError, setIsError] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const queryClient = useQueryClient();

  const connect = useCallback(() => {
    if (!campaignId || isComplete) return;

    // Tear down any existing connection before opening a new one
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    const url = `${API_BASE}/api/campaigns/${campaignId}/progress`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
    };

    es.onerror = () => {
      setIsConnected(false);
      es.close();
      esRef.current = null;
    };

    // Per Pitfall 2: Register addEventListener for each named event type.
    // The backend sends named events (event: iteration_start, etc.),
    // which are NOT dispatched to es.onmessage.
    for (const type of EVENT_TYPES) {
      es.addEventListener(type, (e: MessageEvent) => {
        const data: ProgressEvent = JSON.parse(e.data);
        setEvents((prev) => [...prev, data]);

        if (data.event === 'campaign_error') {
          setIsError(true);
        }

        if (TERMINAL_EVENTS.has(data.event)) {
          setIsComplete(true);
          es.close();
          esRef.current = null;

          // Per Pitfall 4: Invalidate React Query cache so the UI
          // fetches fresh campaign data (including report, iterations, etc.)
          void queryClient.invalidateQueries({
            queryKey: ['campaign', campaignId],
          });
          void queryClient.invalidateQueries({
            queryKey: ['campaigns'],
          });
        }
      });
    }
  }, [campaignId, isComplete, queryClient]);

  useEffect(() => {
    connect();

    // Per Pitfall 6: Close EventSource when component unmounts
    // or when campaignId changes to prevent leaked connections
    return () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [connect]);

  // Derived state computed from the latest event
  const latestEvent = events.length > 0 ? events[events.length - 1]! : null;

  const currentStep = useMemo(() => {
    if (!latestEvent) return null;
    return latestEvent.step ?? null;
  }, [latestEvent]);

  const progress = useMemo<ProgressState>(() => {
    if (!latestEvent) {
      return {
        iteration: 0,
        maxIterations: 0,
        stepIndex: 0,
        totalSteps: 0,
        etaSeconds: null,
      };
    }
    return {
      iteration: latestEvent.iteration,
      maxIterations: latestEvent.max_iterations,
      stepIndex: latestEvent.step_index ?? 0,
      totalSteps: latestEvent.total_steps ?? 0,
      etaSeconds: latestEvent.eta_seconds ?? null,
    };
  }, [latestEvent]);

  return {
    events,
    latestEvent,
    isConnected,
    isComplete,
    isError,
    currentStep,
    progress,
  };
}
