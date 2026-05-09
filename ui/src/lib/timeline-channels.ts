/**
 * Phase 5: derive the 4 display channels from a TRIBE per-window timeline.
 *
 * TRIBE emits 7 functional brain dimensions per window. The demo audience
 * recognises anatomical labels, so the chart shows 4 derived channels —
 * three direct/blended proxies for region groups and one engagement
 * composite. Formulas mirror demo_assets/README.md so the README and the
 * code stay in lockstep.
 *
 * Display channel       Formula
 * Visual cortex         attention_capture
 * Auditory cortex       (social_relevance + cognitive_load) / 2
 * Language regions      (cognitive_load + memory_encoding) / 2
 * Engagement composite  0.5·emotional_resonance + 0.3·reward_response + 0.2·attention_capture
 *
 * After deriving, each channel is min-max normalised across its own
 * timeline so the chart's 0-1 axis stays comparable across stimuli.
 */

import type { TribeTimeline } from '@/api/types';

export type DisplayChannel =
  | 'visual_cortex'
  | 'auditory_cortex'
  | 'language_regions'
  | 'engagement';

export const DISPLAY_CHANNEL_LABELS: Record<DisplayChannel, string> = {
  visual_cortex: 'Visual cortex',
  auditory_cortex: 'Auditory cortex',
  language_regions: 'Language regions',
  engagement: 'Engagement composite',
};

export const DISPLAY_CHANNEL_COLORS: Record<DisplayChannel, string> = {
  // Pulled from the dark-amber palette in index.css; chosen so the four
  // lines stay distinguishable on the dark canvas without resorting to
  // primary RGB rainbow.
  visual_cortex: 'var(--primary)',         // amber — attention/foveal
  auditory_cortex: 'var(--mirofish)',      // teal — auditory cortex (left-temporal)
  language_regions: 'var(--tribe)',        // purple — Broca/Wernicke proxy
  engagement: 'var(--heat-hot)',           // coral — limbic/reward composite
};

export interface TimelinePoint {
  /** Wallclock seconds since stimulus start. */
  t: number;
  visual_cortex: number;
  auditory_cortex: number;
  language_regions: number;
  engagement: number;
}

const EPS = 1e-9;

function minMaxNormalise(values: number[]): number[] {
  if (values.length === 0) return values;
  let lo = values[0];
  let hi = values[0];
  for (const v of values) {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  const range = hi - lo;
  if (range < EPS) return values.map(() => 0);
  return values.map((v) => (v - lo) / range);
}

/**
 * Build the 4-channel display timeline from a raw TRIBE timeline.
 * Returns null when the timeline is missing or malformed.
 */
export function buildDisplayTimeline(
  raw: TribeTimeline | null | undefined,
  trSeconds: number | null | undefined,
): TimelinePoint[] | null {
  if (!raw || !trSeconds || trSeconds <= 0) return null;

  const att = raw.attention_capture ?? [];
  const emo = raw.emotional_resonance ?? [];
  const mem = raw.memory_encoding ?? [];
  const rwd = raw.reward_response ?? [];
  const cog = raw.cognitive_load ?? [];
  const soc = raw.social_relevance ?? [];

  const n = Math.min(att.length, emo.length, mem.length, rwd.length, cog.length, soc.length);
  if (n === 0) return null;

  const visualRaw: number[] = [];
  const auditoryRaw: number[] = [];
  const languageRaw: number[] = [];
  const engagementRaw: number[] = [];

  for (let i = 0; i < n; i++) {
    visualRaw.push(att[i]);
    auditoryRaw.push((soc[i] + cog[i]) / 2);
    languageRaw.push((cog[i] + mem[i]) / 2);
    engagementRaw.push(0.5 * emo[i] + 0.3 * rwd[i] + 0.2 * att[i]);
  }

  const visual = minMaxNormalise(visualRaw);
  const auditory = minMaxNormalise(auditoryRaw);
  const language = minMaxNormalise(languageRaw);
  const engagement = minMaxNormalise(engagementRaw);

  const out: TimelinePoint[] = [];
  for (let i = 0; i < n; i++) {
    out.push({
      t: i * trSeconds,
      visual_cortex: visual[i],
      auditory_cortex: auditory[i],
      language_regions: language[i],
      engagement: engagement[i],
    });
  }
  return out;
}
