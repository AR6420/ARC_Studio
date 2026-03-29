/**
 * Score-to-color mapping matching the backend color_code_score() function.
 *
 * Source: orchestrator/engine/report_generator.py color_code_score()
 * Per Results.md Section 4.2:
 *   Normal:   green >= 70, amber 40-69, red < 40
 *   Inverted: green < 30, amber 30-59, red >= 60
 *   (backlash_risk and polarization_index are inverted -- lower is better)
 */

export const INVERTED_SCORES = new Set(['backlash_risk', 'polarization_index']);

export function getScoreColor(
  metricName: string,
  value: number,
): 'green' | 'amber' | 'red' {
  if (INVERTED_SCORES.has(metricName)) {
    if (value < 30) return 'green';
    if (value < 60) return 'amber';
    return 'red';
  }
  if (value >= 70) return 'green';
  if (value >= 40) return 'amber';
  return 'red';
}

/** Tailwind text color classes keyed by score color. */
export const SCORE_COLORS = {
  green: 'text-emerald-400',
  amber: 'text-amber-400',
  red: 'text-red-400',
} as const;

/** Tailwind background classes with opacity keyed by score color. */
export const SCORE_BG_COLORS = {
  green: 'bg-emerald-500/15',
  amber: 'bg-amber-500/15',
  red: 'bg-red-500/15',
} as const;

/** Tailwind border classes with opacity keyed by score color. */
export const SCORE_BORDER_COLORS = {
  green: 'border-emerald-500/30',
  amber: 'border-amber-500/30',
  red: 'border-red-500/30',
} as const;
