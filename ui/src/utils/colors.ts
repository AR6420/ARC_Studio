/**
 * Score-to-color mapping.
 *
 * The backend's report_generator.color_code_score() emits traffic-light color
 * names ('green' | 'amber' | 'red') in the report scorecard. The UI remaps
 * those strings onto a scientific heat-map palette so scores read as
 * intensity/magnitude, not a traffic signal.
 *
 *   backend 'green' (good)  → hot coral  (strong signal)
 *   backend 'amber' (mid)   → warm amber (mid signal)
 *   backend 'red'   (bad)   → cool blue  (weak signal)
 *
 * For inverted metrics (backlash_risk, polarization_index), the backend
 * already flips the category — we just honour what it sends.
 */

export const INVERTED_SCORES = new Set(['backlash_risk', 'polarization_index']);

/** Backend-compatible category. Kept for interop with report scorecard.color_coding. */
export type ScoreCategory = 'green' | 'amber' | 'red';

export function getScoreColor(
  metricName: string,
  value: number,
): ScoreCategory {
  if (INVERTED_SCORES.has(metricName)) {
    if (value < 30) return 'green';
    if (value < 60) return 'amber';
    return 'red';
  }
  if (value >= 70) return 'green';
  if (value >= 40) return 'amber';
  return 'red';
}

/** Tailwind text colour classes keyed by score category. Maps to heat palette. */
export const SCORE_COLORS = {
  green: 'text-heat-hot',
  amber: 'text-heat-mid',
  red: 'text-heat-cold',
} as const;

/** Tailwind background classes with opacity keyed by score category. */
export const SCORE_BG_COLORS = {
  green: 'bg-heat-hot/12',
  amber: 'bg-heat-mid/12',
  red: 'bg-heat-cold/12',
} as const;

/** Tailwind border classes with opacity keyed by score category. */
export const SCORE_BORDER_COLORS = {
  green: 'border-heat-hot/35',
  amber: 'border-heat-mid/35',
  red: 'border-heat-cold/35',
} as const;

// ─── Fine-grained 5-stop heat scale ─────────────────────────────────────────

export type HeatStop = 'cold' | 'cool' | 'mid' | 'warm' | 'hot';

/**
 * Map a 0-100 score to one of 5 heat stops.
 * Inverted metrics get the scale flipped so "low backlash" still reads as hot.
 */
export function getHeatStop(metricName: string, value: number): HeatStop {
  const v = INVERTED_SCORES.has(metricName) ? 100 - value : value;
  if (v < 20) return 'cold';
  if (v < 40) return 'cool';
  if (v < 60) return 'mid';
  if (v < 80) return 'warm';
  return 'hot';
}

/** CSS variable references — use inside inline style or arbitrary values. */
export const HEAT_VARS: Record<HeatStop, string> = {
  cold: 'var(--heat-cold)',
  cool: 'var(--heat-cool)',
  mid: 'var(--heat-mid)',
  warm: 'var(--heat-warm)',
  hot: 'var(--heat-hot)',
};

/** Tailwind text utility classes per heat stop. */
export const HEAT_TEXT: Record<HeatStop, string> = {
  cold: 'text-heat-cold',
  cool: 'text-heat-cool',
  mid: 'text-heat-mid',
  warm: 'text-heat-warm',
  hot: 'text-heat-hot',
};

/** Tailwind background utility classes per heat stop (12% opacity). */
export const HEAT_BG: Record<HeatStop, string> = {
  cold: 'bg-heat-cold/12',
  cool: 'bg-heat-cool/12',
  mid: 'bg-heat-mid/12',
  warm: 'bg-heat-warm/12',
  hot: 'bg-heat-hot/12',
};
