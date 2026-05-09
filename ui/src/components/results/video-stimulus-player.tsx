/**
 * Phase 5: HTML5 video + per-window neural timeline, side-by-side.
 *
 * Binds the video's `timeupdate` event to a piece of state that drives
 * the chart's playhead. Falls back to the bundled mock TRIBE timeline
 * when:
 *   - no real timeline is available on the campaign yet (running on the
 *     laptop where TRIBE returns pseudo scores), OR
 *   - the dev/mock toggle is on.
 *
 * The orchestrator's media_path is an absolute host path. For local-dev
 * playback we map it to the /api/campaigns/media/<basename> endpoint
 * exposed by the API (existing audio path mirror). When the campaign has
 * no media (text seed), the player only shows the mock when the toggle
 * is on.
 */

import { useEffect, useMemo, useRef, useState } from 'react';

import { TimelineChart } from '@/components/results/timeline-chart';
import {
  buildDisplayTimeline,
  type TimelinePoint,
} from '@/lib/timeline-channels';
import type { TribeScores } from '@/api/types';

const MOCK_TIMELINE_URL = '/mock_timeline_apple1984.json';
const MOCK_VIDEO_FALLBACK_URL = '/demo_assets/apple_1984.mp4'; // when surfaced from public

interface MockTimelineDoc {
  tr_seconds: number;
  duration_seconds: number;
  timeline: TribeScores['timeline'];
}

interface VideoStimulusPlayerProps {
  /** Browser-resolvable video src, or null when no video is attached. */
  videoSrc: string | null;
  /** Real TRIBE per-window timeline + tr_seconds, when available. */
  tribeScores?: TribeScores | null;
  /**
   * Force-load the bundled mock timeline (and the bundled mock video
   * URL when no real videoSrc is provided). Useful in dev / for the
   * demo when running against a stack with no real TRIBE timeline yet.
   */
  forceMock?: boolean;
}

export function VideoStimulusPlayer({
  videoSrc,
  tribeScores,
  forceMock = false,
}: VideoStimulusPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [videoDuration, setVideoDuration] = useState<number>(0);
  const [mockData, setMockData] = useState<MockTimelineDoc | null>(null);
  const [useMock, setUseMock] = useState(forceMock);

  const realTimelineAvailable = Boolean(
    tribeScores?.timeline && tribeScores?.tr_seconds && tribeScores.tr_seconds > 0,
  );

  // Auto-fall-back to mock when no real timeline exists yet.
  const effectiveUseMock = useMock || !realTimelineAvailable;

  useEffect(() => {
    if (!effectiveUseMock) return;
    if (mockData) return;
    let cancelled = false;
    fetch(MOCK_TIMELINE_URL)
      .then((r) => (r.ok ? r.json() : null))
      .then((doc: MockTimelineDoc | null) => {
        if (!cancelled && doc) setMockData(doc);
      })
      .catch(() => {
        // mock unavailable; chart will render its empty-state
      });
    return () => {
      cancelled = true;
    };
  }, [effectiveUseMock, mockData]);

  const { timelineData, durationFromData } = useMemo<{
    timelineData: TimelinePoint[];
    durationFromData: number;
  }>(() => {
    if (effectiveUseMock && mockData) {
      const built = buildDisplayTimeline(mockData.timeline, mockData.tr_seconds);
      return {
        timelineData: built ?? [],
        durationFromData: mockData.duration_seconds,
      };
    }
    if (tribeScores?.timeline && tribeScores.tr_seconds) {
      const built = buildDisplayTimeline(
        tribeScores.timeline,
        tribeScores.tr_seconds,
      );
      const sampleLen = built?.length ?? 0;
      return {
        timelineData: built ?? [],
        durationFromData: sampleLen * (tribeScores.tr_seconds ?? 0),
      };
    }
    return { timelineData: [], durationFromData: 0 };
  }, [effectiveUseMock, mockData, tribeScores]);

  const effectiveDuration = videoDuration > 0 ? videoDuration : durationFromData;
  const effectiveVideoSrc = videoSrc || (effectiveUseMock ? MOCK_VIDEO_FALLBACK_URL : null);

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-4 border-b border-border pb-2">
        <div className="flex items-baseline gap-3">
          <h2 className="text-[1rem] font-medium tracking-[-0.005em] text-foreground">
            Stimulus playback
          </h2>
          <span className="font-mono text-[0.62rem] tracking-[0.1em] text-muted-foreground uppercase">
            neural timeline · synced to playhead
          </span>
        </div>
        {!realTimelineAvailable && (
          <span className="font-mono text-[0.62rem] uppercase tracking-[0.1em] text-muted-foreground/70">
            mock data
          </span>
        )}
        {realTimelineAvailable && (
          <button
            type="button"
            onClick={() => setUseMock((v) => !v)}
            className="font-mono text-[0.62rem] uppercase tracking-[0.1em] text-muted-foreground hover:text-foreground transition"
          >
            {useMock ? 'using mock · switch to live' : 'using live · switch to mock'}
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <div className="flex flex-col gap-2">
          {effectiveVideoSrc ? (
            <video
              ref={videoRef}
              src={effectiveVideoSrc}
              controls
              preload="metadata"
              className="aspect-video w-full bg-black border border-border"
              onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
              onLoadedMetadata={(e) => setVideoDuration(e.currentTarget.duration)}
            />
          ) : (
            <div className="aspect-video w-full bg-card/40 border border-border flex items-center justify-center">
              <p className="font-mono text-[0.72rem] text-muted-foreground/60">
                › no video stimulus attached
              </p>
            </div>
          )}
          <p className="font-mono text-[0.62rem] tabular-nums text-muted-foreground">
            t = {currentTime.toFixed(2)}s
            {effectiveDuration > 0 && ` / ${effectiveDuration.toFixed(2)}s`}
          </p>
        </div>

        <TimelineChart
          data={timelineData}
          durationSeconds={effectiveDuration}
          currentTimeSeconds={currentTime}
        />
      </div>
    </section>
  );
}
