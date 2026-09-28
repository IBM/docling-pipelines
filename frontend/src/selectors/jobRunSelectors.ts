/**
 * @fileoverview Selectors for accessing job run state from Redux store.
 * Provides both basic and memoized selectors for efficient state access.
 */

// TODO: Update with API implementation
import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@/store';
import type { JobRun } from '@/types';

// Basic selectors

/** Selects the entire job run state slice */
export const selectJobRunState = (state: RootState) => state.jobRun;

/** Selects the job runs items dictionary */
export const selectJobRunItems = (state: RootState) => state.jobRun.items;

/** Selects the job ID to run IDs index */
export const selectJobRunsByJobId = (state: RootState) => state.jobRun.byJobId;

/** Selects the currently selected job run ID */
export const selectSelectedRunId = (state: RootState) => state.jobRun.selectedRunId;

/** Selects the logs dictionary (job run ID to log entries) */
export const selectJobRunLogsMap = (state: RootState) => state.jobRun.logs;

/** Selects the statistics dictionary (job run ID to stats) */
export const selectJobRunStatisticsMap = (state: RootState) => state.jobRun.statistics;

/** Selects the loading state for job run operations */
export const selectJobRunLoading = (state: RootState) => state.jobRun.loading;

/** Selects the error message for job run operations */
export const selectJobRunError = (state: RootState) => state.jobRun.error;

// Memoized selectors for derived state

/**
 * Retrieves the currently selected job run by ID.
 * @returns The selected job run object or null if none selected
 */
export const selectSelectedJobRun = createSelector(
  [selectJobRunItems, selectSelectedRunId],
  (items, selectedId) => (selectedId ? items[selectedId] ?? null : null)
);

/**
 * Retrieves logs for the currently selected job run.
 * @returns Array of log entries or empty array if none
 */
export const selectSelectedJobRunLogs = createSelector(
  [selectJobRunLogsMap, selectSelectedRunId],
  (logsMap, selectedId) => (selectedId ? logsMap[selectedId] ?? [] : [])
);

/**
 * Retrieves statistics for the currently selected job run.
 * @returns Statistics object or null if none
 */
export const selectSelectedJobRunStatistics = createSelector(
  [selectJobRunStatisticsMap, selectSelectedRunId],
  (statsMap, selectedId) => (selectedId ? statsMap[selectedId] ?? null : null)
);

/**
 * Converts the job runs items dictionary to an array.
 * @returns Array of all job run objects
 */
export const selectJobRunsArray = createSelector(
  [selectJobRunItems],
  (items) => Object.values(items)
);

/**
 * Counts the total number of job runs.
 * @returns The number of job runs
 */
export const selectJobRunCount = createSelector(
  [selectJobRunItems],
  (items) => Object.keys(items).length
);

/**
 * Checks if a job run is currently selected.
 * @returns true if a job run is selected, false otherwise
 */
export const selectHasSelectedJobRun = createSelector(
  [selectSelectedRunId],
  (selectedId) => selectedId !== null
);

/**
 * Gets all job run IDs for a specific job ID.
 * @returns Function that takes a job ID and returns array of run IDs
 */
export const selectRunIdsByJobId = createSelector(
  [selectJobRunsByJobId],
  (byJobId) => (jobId: string) => byJobId[jobId] ?? []
);

/**
 * Gets all job runs for a specific job ID.
 * @returns Function that takes a job ID and returns array of job runs
 */
export const selectJobRunsByJob = createSelector(
  [selectJobRunItems, selectJobRunsByJobId],
  (items, byJobId) => (jobId: string) => {
    const runIds = byJobId[jobId] ?? [];
    return runIds.map((runId) => items[runId]).filter((run): run is JobRun => run !== undefined);
  }
);

/**
 * Filters job runs by status.
 * @returns Function that takes a status and returns filtered job runs
 */
export const selectJobRunsByStatus = createSelector(
  [selectJobRunsArray],
  (jobRuns) => (status: string) =>
    jobRuns.filter((run) => run.status === status)
);

// ── ReadOnlyCanvas / run-viewer selectors ────────────────────────────────

/** true while execution is in-flight */
export const selectIsRunning = (s: RootState): boolean => s.jobRun.isRunning;

/** job_run_id being viewed on canvas, or null */
export const selectCurrentJobRunId = (s: RootState): string | null => s.jobRun.currentJobRunId;

/** job_id (= flow_id) being viewed on canvas, or null */
export const selectCurrentJobId = (s: RootState): string | null => s.jobRun.currentJobId;

/** Latest polled JobRunStatusResponse; null when not in run-viewer mode */
export const selectExecutionLogs = (s: RootState) => s.jobRun.executionLogs;
