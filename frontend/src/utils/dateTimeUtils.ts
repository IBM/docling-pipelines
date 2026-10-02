/**
 * @file dateTimeUtils.ts
 *
 * Date/time utilities:
 *  - `useDateTimeFormatter` — React hook (requires react-intl IntlProvider in
 *    the component tree) for locale-aware date formatting.
 *  - `convertToEpoch` / `convertFromEpoch` / `isEpochValue` — pure functions
 *    for the sql_filter operator's epoch timestamp handling.
 *
 * @module utils/dateTimeUtils
 */

import { useIntl } from 'react-intl';

/** Accepted granularity values for date/time style options. */
export type DateTimeFormat = 'long' | 'medium' | 'short';

/**
 * Locale-aware date/time formatter backed by react-intl.
 *
 * Must be called from a component rendered inside an `<IntlProvider>`.
 *
 * @example
 * ```tsx
 * const { formatDate } = useDateTimeFormatter();
 * formatDate(new Date(), 'short', 'short') // "1/4/25, 2:03 PM"
 * formatDate(new Date(), 'short')          // "1/4/25"  (date only)
 * ```
 */
export function useDateTimeFormatter(): {
  formatDate: (date: Date, timeStyle: DateTimeFormat, dateStyle?: DateTimeFormat) => string;
  formatCurrentDate: (timeStyle: DateTimeFormat, dateStyle?: DateTimeFormat) => string;
} {
  const intl = useIntl();

  /**
   * Formats `date` using the browser locale.
   *
   * @param date       - The date to format.
   * @param timeStyle  - Granularity of the time portion (`'short'` = "2:03 PM").
   * @param dateStyle  - Granularity of the date portion (`'short'` = "1/4/25").
   *                     Omit to show time only.
   */
  const formatDate = (date: Date, timeStyle: DateTimeFormat, dateStyle?: DateTimeFormat): string =>
    intl.formatDate(date, { dateStyle, timeStyle });

  /** Formats the current instant using the same options as {@link formatDate}. */
  const formatCurrentDate = (timeStyle: DateTimeFormat, dateStyle?: DateTimeFormat): string =>
    formatDate(new Date(), timeStyle, dateStyle);

  return { formatDate, formatCurrentDate };
}

/**
 * Regex that validates a datetime string in `YYYY-MM-DD HH:MM:SS` format.
 * The only format accepted by the Simple-tab datetime inputs.
 */
const DATETIME_REGEX = /^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}$/;

/**
 * Converts a datetime string in `YYYY-MM-DD HH:MM:SS` format to a Unix
 * epoch timestamp (seconds since 1970-01-01 00:00:00 UTC).
 *
 * Returns `0` when `value` is empty or does not match the expected format.
 *
 * @param value - A datetime string in `YYYY-MM-DD HH:MM:SS` format.
 * @returns Unix epoch in seconds, or `0` on parse failure.
 *
 * @example
 * ```ts
 * convertToEpoch('2024-01-15 14:30:00') // → 1705329000
 * ```
 */
export function convertToEpoch(value: string): number {
  if (!value || !DATETIME_REGEX.test(value.trim())) { return 0; }

  const [datePart, timePart] = value.trim().split(' ');
  const [year, month, day] = (datePart ?? '').split('-').map(Number);
  const [hours, minutes, seconds] = (timePart ?? '').split(':').map(Number);

  // Use UTC so the epoch round-trips correctly regardless of the user's timezone.
  const ms = Date.UTC(
    year ?? 0,
    (month ?? 1) - 1,
    day ?? 1,
    hours ?? 0,
    minutes ?? 0,
    seconds ?? 0
  );

  return Math.floor(ms / 1000);
}

/**
 * Converts a Unix epoch timestamp (seconds) to a human-readable datetime
 * string in `YYYY-MM-DD HH:MM:SS` format.
 *
 * Returns an empty string when `epochValue` is `NaN`.
 *
 * @param epochValue - Unix epoch in seconds (number or numeric string).
 * @returns Formatted datetime string, or `""` on invalid input.
 *
 * @example
 * ```ts
 * convertFromEpoch(1705329000) // → "2024-01-15 14:30:00"
 * ```
 */
export function convertFromEpoch(epochValue: string | number): string {
  const epoch = typeof epochValue === 'string' ? Number.parseInt(epochValue, 10) : epochValue;
  if (Number.isNaN(epoch)) { return ''; }

  // Use UTC methods to match the UTC construction in convertToEpoch.
  const date = new Date(epoch * 1000);
  const yyyy = date.getUTCFullYear();
  const mm = String(date.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(date.getUTCDate()).padStart(2, '0');
  const hh = String(date.getUTCHours()).padStart(2, '0');
  const min = String(date.getUTCMinutes()).padStart(2, '0');
  const ss = String(date.getUTCSeconds()).padStart(2, '0');

  return `${yyyy}-${mm}-${dd} ${hh}:${min}:${ss}`;
}

/**
 * Returns `true` when `value` is a numeric string or number that looks like
 * a Unix epoch timestamp (i.e. all digits, no datetime formatting characters).
 *
 * Used to detect whether a saved condition value has already been converted to
 * epoch and should be passed through {@link convertFromEpoch} before display.
 *
 * @param value - The condition value to test.
 */
/**
 * Minimum plausible epoch for a condition value: 2000-01-01 00:00:00 UTC.
 * Pure-digit strings shorter than 10 characters (or values < this threshold)
 * are treated as plain numbers, not stored epochs.
 */
const MIN_EPOCH_SECONDS = 946684800; // 2000-01-01 00:00:00 UTC

export function isEpochValue(value: string | number): boolean {
  if (typeof value === 'number') {
    return Number.isFinite(value) && value >= MIN_EPOCH_SECONDS;
  }
  const trimmed = value.trim();
  if (!/^\d+$/.test(trimmed)) { return false; }
  // Must be at least 10 digits (≥ year 2001) to qualify as a stored epoch.
  // Short digit strings like "2" or "100" are plain numeric values, not epochs.
  return trimmed.length >= 10 && Number(trimmed) >= MIN_EPOCH_SECONDS;
}

/**
 * Converts a Unix epoch timestamp (seconds) to a locale-formatted date-time
 * string suitable for display in tables and panels.
 *
 * Returns `''` for falsy values (0, undefined).
 *
 * @param epochSeconds - Unix epoch in seconds.
 * @param options      - Optional `Intl.DateTimeFormatOptions` to customise the
 *                       output. When omitted the browser default locale format
 *                       is used (e.g. `"8/5/2026, 6:26:05 AM"`).
 *
 * @example
 * ```ts
 * formatEpochToDisplay(1722844765)
 * // → "8/5/2024, 6:26:05 AM"  (locale-dependent)
 *
 * formatEpochToDisplay(1722844765, { year: 'numeric', month: 'long', day: 'numeric',
 *   hour: 'numeric', minute: '2-digit', hour12: true })
 * // → "August 5, 2024 at 6:26 AM"  (locale-dependent)
 * ```
 */
export function formatEpochToDisplay(
  epochSeconds: number,
  options?: Intl.DateTimeFormatOptions
): string {
  if (!epochSeconds) { return ''; }
  return new Date(epochSeconds * 1000).toLocaleString(undefined, options);
}

/**
 * Formats a duration in whole seconds as a zero-padded `HH:MM:SS` string.
 *
 * Used by run-status panels and run history tables to display elapsed time.
 *
 * @param seconds - Non-negative integer number of seconds.
 * @returns A string like `"00:02:34"` or `"01:30:00"`.
 *
 * @example
 * ```ts
 * formatElapsedTime(154)  // → "00:02:34"
 * formatElapsedTime(3600) // → "01:00:00"
 * ```
 */
export function formatElapsedTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return [h, m, s].map((v) => String(v).padStart(2, '0')).join(':');
}
