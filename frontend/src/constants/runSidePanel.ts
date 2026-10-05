/**
 * @fileoverview Constants for the RunSidePanel, JobRunLogs, and NodeSummary components.
 */

// ── JobRunLogs ────────────────────────────────────────────────────────────────

/** Delay (ms) before auto-scrolling to the selected node's accordion item. */
export const LOG_SCROLL_DELAY_MS = 100;

/** Log character length above which the "Show detailed log" button is shown. */
export const LOG_PREVIEW_THRESHOLD = 500;

// ── NodeSummary ───────────────────────────────────────────────────────────────

/** Maximum character length before a cell value is truncated with ellipsis. */
export const CELL_VALUE_MAX_LENGTH = 100;

/** Decimal places shown for non-integer float values in the metadata table. */
export const CELL_VALUE_FLOAT_DECIMALS = 4;

/** Float values above this magnitude are shown as integers (no decimal places). */
export const CELL_VALUE_FLOAT_THRESHOLD = 1000;

/** Default node status text shown when no node stat exists. */
export const DEFAULT_NODE_STATUS = 'Not Started';

/** Fallback text shown for execution time when no node stat exists. */
export const DEFAULT_EXECUTION_TIME = 'N/A';

/** Column headers for the NodeSummary metadata DataTable. */
export const METADATA_TABLE_HEADERS = [
  { key: 'name', header: 'Name' },
  { key: 'value', header: 'Value' },
];

// ── RunSidePanel tab labels ───────────────────────────────────────────────────

/** Label for the Log Details tab. */
export const TAB_LABEL_LOG_DETAILS = 'Log Details';

/** Label for the Node Summary tab. */
export const TAB_LABEL_NODE_SUMMARY = 'Node Summary';

/** Placeholder shown in Node Summary tab when no node is selected. */
export const NODE_SUMMARY_EMPTY_TEXT = 'Select a node to view details';

// ── RunSidePanel log download ─────────────────────────────────────────────────

/** MIME type used when generating the downloadable log file. */
export const LOG_DOWNLOAD_MIME_TYPE = 'text/plain';

/** Filename prefix for downloaded log files. */
export const LOG_DOWNLOAD_FILENAME_PREFIX = 'job-run-logs-';

/** Section separator format used in the downloaded log file. */
export const LOG_SECTION_SEPARATOR = (name: string): string =>
  `\n========== Node: ${name} ==========\n`;

// ── RunStatusTopPanel ─────────────────────────────────────────────────────────

/** Seconds per hour — used in elapsed time formatting. */
export const SECONDS_PER_HOUR = 3600;

/** Seconds per minute — used in elapsed time formatting. */
export const SECONDS_PER_MINUTE = 60;
