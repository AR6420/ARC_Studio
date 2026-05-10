/**
 * Phase 5 session 6 — auto-scroll the campaign-detail viewport to the
 * active stage's content area whenever a `step_start` SSE event fires.
 *
 * Behaviour:
 *  - On each new step_start, look up the stage's anchor element by id
 *    and scroll it into view with a sticky-pipeline-height offset.
 *  - Suppress auto-scroll if the user has scrolled within the last
 *    ~2 seconds (manual-scroll wins; we don't yank them back).
 *  - Suppress on hidden tab — no point scrolling something the user
 *    can't see, and the next stage transition will fire its own scroll.
 *  - Debounce so rapid back-to-back stage transitions only fire one
 *    scroll per ~1s — small campaigns finish stages in a few hundred
 *    ms each and the page should not be a slot machine.
 *
 * The hook is read-only: it observes events + window scroll, never
 * writes to React state, so it doesn't trigger re-renders.
 */

import { useEffect, useRef } from 'react';
import type { ProgressEvent } from '@/api/types';

interface UseStageAutoscrollOptions {
  /** Map of stage name → DOM element id (without leading `#`). */
  anchors: Record<string, string>;
  /** Pixel offset to leave room for the sticky pipeline strip. */
  stickyOffset?: number;
  /** Minimum ms between back-to-back auto-scrolls. Default: 800. */
  debounceMs?: number;
  /** Suppress auto-scroll for this many ms after a user scroll. Default: 2000. */
  userScrollWindowMs?: number;
}

export function useStageAutoscroll(
  events: ProgressEvent[],
  {
    anchors,
    stickyOffset = 64,
    debounceMs = 800,
    userScrollWindowMs = 2000,
  }: UseStageAutoscrollOptions,
): void {
  // Track the last stage we scrolled to so a re-render with the same
  // event tail doesn't re-trigger.
  const lastScrolledStageRef = useRef<string | null>(null);
  const lastScrollAtRef = useRef<number>(0);
  const lastUserScrollAtRef = useRef<number>(0);

  // User-scroll listener. wheel / touchmove / keydown(arrow/page) all
  // count as intent. The plain `scroll` event also fires when WE scroll
  // programmatically, so we filter via a flag set briefly during our
  // own calls. Simpler approach: only trust wheel/touch/key — those
  // can't fire from scrollIntoView.
  useEffect(() => {
    const onUserScroll = () => {
      lastUserScrollAtRef.current = Date.now();
    };
    window.addEventListener('wheel', onUserScroll, { passive: true });
    window.addEventListener('touchmove', onUserScroll, { passive: true });
    const onKey = (e: KeyboardEvent) => {
      if (
        e.key === 'ArrowUp' ||
        e.key === 'ArrowDown' ||
        e.key === 'PageUp' ||
        e.key === 'PageDown' ||
        e.key === 'Home' ||
        e.key === 'End' ||
        e.key === ' '
      ) {
        lastUserScrollAtRef.current = Date.now();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('wheel', onUserScroll);
      window.removeEventListener('touchmove', onUserScroll);
      window.removeEventListener('keydown', onKey);
    };
  }, []);

  useEffect(() => {
    // Find the most recent step_start event in the stream.
    let latestStartIndex = -1;
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i]!.event === 'step_start') {
        latestStartIndex = i;
        break;
      }
    }
    if (latestStartIndex === -1) return;
    const evt = events[latestStartIndex]!;
    const stage = evt.step;
    if (!stage) return;

    // Stage hasn't changed since our last scroll → no-op.
    if (stage === lastScrolledStageRef.current) return;

    const now = Date.now();
    if (now - lastScrollAtRef.current < debounceMs) return;
    if (now - lastUserScrollAtRef.current < userScrollWindowMs) {
      // Mark stage as "seen" so we don't keep retrying every render.
      lastScrolledStageRef.current = stage;
      return;
    }
    if (typeof document !== 'undefined' && document.hidden) {
      lastScrolledStageRef.current = stage;
      return;
    }

    const anchorId = anchors[stage];
    if (!anchorId) {
      lastScrolledStageRef.current = stage;
      return;
    }
    const el = document.getElementById(anchorId);
    if (!el) return;

    const rect = el.getBoundingClientRect();
    // scrollingElement honours both <html> and <body> overflow setups.
    const scroller =
      (document.scrollingElement as HTMLElement | null) ?? document.documentElement;
    // Prefer the closest scrollable ancestor — AppLayout's <main>
    // owns the scroll, not the document.
    const scrollableAncestor = findScrollableAncestor(el) ?? scroller;
    const ancestorRect =
      scrollableAncestor === scroller
        ? { top: 0 } as DOMRect
        : (scrollableAncestor as HTMLElement).getBoundingClientRect();
    const offsetWithin = rect.top - ancestorRect.top;
    const target =
      (scrollableAncestor as HTMLElement).scrollTop + offsetWithin - stickyOffset;
    (scrollableAncestor as HTMLElement).scrollTo({
      top: Math.max(0, target),
      behavior: 'smooth',
    });

    lastScrolledStageRef.current = stage;
    lastScrollAtRef.current = now;
  }, [events, anchors, stickyOffset, debounceMs, userScrollWindowMs]);
}

function findScrollableAncestor(el: HTMLElement): HTMLElement | null {
  let parent: HTMLElement | null = el.parentElement;
  while (parent) {
    const style = window.getComputedStyle(parent);
    const overflowY = style.overflowY;
    if (
      (overflowY === 'auto' || overflowY === 'scroll') &&
      parent.scrollHeight > parent.clientHeight
    ) {
      return parent;
    }
    parent = parent.parentElement;
  }
  return null;
}
