/**
 * Converts an ISO 8601 or locale date string into a human-readable relative
 * time label matching the design spec:
 *   "Just now"   — less than 1 minute ago
 *   "X min ago"  — 1–59 minutes ago
 *   "X h ago"    — 1–23 hours ago
 *   "X d ago"    — 1–29 days ago
 *   "X mo ago"   — 1–11 months ago
 *   "X y ago"    — 1+ years ago
 *
 * Returns an empty string if the input cannot be parsed.
 */
export function formatRelativeTime(dateString: string): string {
  if (!dateString) { return ''; }

  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) { return ''; }

  const diffMs = Date.now() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr  = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr  / 24);
  const diffMo  = Math.floor(diffDay / 30);
  const diffYr  = Math.floor(diffDay / 365);

  if (diffSec < 60)  { return 'Just now'; }
  if (diffMin < 60)  { return `${diffMin} min ago`; }
  if (diffHr  < 24)  { return `${diffHr} h ago`; }
  if (diffDay < 30)  { return `${diffDay} d ago`; }
  if (diffMo  < 12)  { return `${diffMo} mo ago`; }
  return `${diffYr} y ago`;
}
