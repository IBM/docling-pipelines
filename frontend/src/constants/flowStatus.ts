/**
 * @fileoverview Shared job-run status constants used by both the flow mapper
 * (`flow-mapper.ts`) and the FlowDetail page (`FlowDetail.tsx`).
 *
 * All status strings are the raw values returned by the backend API.
 * Keeping them in one place ensures the mapper and the detail page stay in sync
 * if the backend ever adds or renames a status.
 */

// ── Needs Review bucketing sets (used by flow-mapper.ts → FlowsTable) ────────

/**
 * API status strings that contribute to the "errors" count in the
 * Needs Review column of FlowsTable.
 *
 * Note: `CompletedWithErrors` is intentionally treated as a warning, not an
 * error — data was processed but with issues.
 */
export const ERROR_STATUSES = new Set(['Failed', 'Aborted', 'Failing']);

/**
 * API status strings that contribute to the "warnings" count in the
 * Needs Review column of FlowsTable.
 */
export const WARNING_STATUSES = new Set(['CompletedWithWarnings', 'CompletedWithErrors']);

/**
 * API status strings that contribute to the "running" count in the
 * Needs Review column of FlowsTable.
 */
export const RUNNING_STATUSES = new Set([
  'Queued',
  'Pending',
  'Starting',
  'Running',
  'Resuming',
  'Paused',
  'Canceling',
]);

// ── Run row status map (used by FlowDetail.tsx → FlowRunsTable) ───────────────

/**
 * Maps a raw backend job-run status string to the UI `RunStatus` category
 * rendered in FlowRunsTable and FlowMetrics.
 *
 * Unknown status strings fall back to `'run_with_issues'` at the call site so
 * they are surfaced visibly rather than silently mapped to a clean state.
 *
 * | UI category       | API statuses                                              |
 * |-------------------|-----------------------------------------------------------|
 * | `run`             | Completed                                                 |
 * | `in_progress`     | Queued, Pending, Starting, Running, Resuming, Paused, Canceling |
 * | `run_with_issues` | CompletedWithWarnings, CompletedWithErrors                |
 * | `failed`          | Failing, Failed, Aborted                                  |
 * | `cancelled`       | Canceled                                                  |
 */
export const API_STATUS_MAP: Record<string, string> = {
  Completed:             'run',
  CompletedWithWarnings: 'run_with_issues',
  CompletedWithErrors:   'run_with_issues',
  Queued:                'in_progress',
  Pending:               'in_progress',
  Starting:              'in_progress',
  Running:               'in_progress',
  Resuming:              'in_progress',
  Paused:                'in_progress',
  Canceling:             'in_progress',
  Failing:               'failed',
  Failed:                'failed',
  Aborted:               'failed',
  Canceled:              'cancelled',
};
