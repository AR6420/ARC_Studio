/**
 * Formatting utilities for scores, durations, dates, and metric labels.
 */

/**
 * Format a numeric score to 1 decimal place, or an em-dash for null/undefined.
 */
export function formatScore(value: number | null | undefined): string {
  if (value == null) return '—';
  return value.toFixed(1);
}

/**
 * Format a duration in minutes to a human-readable string.
 *
 * Examples: "~3 min", "~1 hr 20 min"
 */
export function formatDuration(minutes: number): string {
  if (minutes < 60) {
    return `~${Math.round(minutes)} min`;
  }
  const hrs = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  if (mins === 0) {
    return `~${hrs} hr`;
  }
  return `~${hrs} hr ${mins} min`;
}

/**
 * Format an ISO 8601 date string to a relative time description.
 *
 * Examples: "just now", "5 minutes ago", "2 hours ago", "yesterday", "Mar 15"
 */
export function formatDate(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin} minute${diffMin === 1 ? '' : 's'} ago`;
  if (diffHr < 24) return `${diffHr} hour${diffHr === 1 ? '' : 's'} ago`;
  if (diffDay === 1) return 'yesterday';
  if (diffDay < 7) return `${diffDay} days ago`;

  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/**
 * Compact relative-time format for dense tables and sidebar lists.
 *
 * Examples: "now", "5m ago", "2h ago", "1d ago", "Mar 15"
 */
export function formatRelative(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 45) return 'now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/**
 * Convert a snake_case metric name to Title Case.
 *
 * Example: "attention_score" -> "Attention Score"
 */
export function formatMetricLabel(snakeCase: string): string {
  return snakeCase
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
