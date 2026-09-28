/**
 * @fileoverview Redux slice for managing job run state.
 * Handles job run executions, logs, statistics, and execution tracking.
 */

// TODO: Update with API implementation
import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { JobRunState, JobRun, LogEntry, RunStats, JobRunStatusResponse } from '@/types';

const initialState: JobRunState = {
  items: {},
  byJobId: {},
  selectedRunId: null,
  logs: {},
  statistics: {},
  loading: false,
  error: null,
  isRunning: false,
  currentJobRunId: null,
  currentJobId: null,
  executionLogs: null,
};

/**
 * Redux slice for job run state management.
 * Manages multiple job runs with their logs, statistics, and execution data.
 */
const jobRunSlice = createSlice({
  name: 'jobRun',
  initialState,
  reducers: {
    /**
     * Sets multiple job runs at once.
     * Clears loading and error states on success.
     * @param state - Current job run state
     * @param action - Action containing the job runs map
     */
    setJobRuns: (state, action: PayloadAction<Record<string, JobRun>>) => {
      state.items = action.payload;
      state.loading = false;
      state.error = null;
    },
    /**
     * Sets or updates a single job run and maintains the byJobId index.
     * @param state - Current job run state
     * @param action - Action containing the job run ID and data
     */
    setJobRun: (state, action: PayloadAction<{ jobRunId: string; jobRun: JobRun }>) => {
      const { jobRunId, jobRun } = action.payload;
      state.items[jobRunId] = jobRun;

      // Update byJobId index
      if (jobRun.jobId) {
        const {jobId} = jobRun;
        state.byJobId[jobId] ??= [];
        if (!state.byJobId[jobId].includes(jobRunId)) {
          state.byJobId[jobId].push(jobRunId);
        }
      }
    },
    /**
     * Partially updates an existing job run.
     * @param state - Current job run state
     * @param action - Action containing the job run ID and partial updates
     */
    updateJobRun: (state, action: PayloadAction<{ jobRunId: string; updates: Partial<JobRun> }>) => {
      const { jobRunId, updates } = action.payload;
      if (state.items[jobRunId]) {
        state.items[jobRunId] = { ...state.items[jobRunId], ...updates };
      }
    },
    /**
     * Sets the log entries for a specific job run.
     * @param state - Current job run state
     * @param action - Action containing the job run ID and log entries
     */
    setLogs: (state, action: PayloadAction<{ jobRunId: string; logs: LogEntry[] }>) => {
      const { jobRunId, logs } = action.payload;
      state.logs[jobRunId] = logs;
    },
    /**
     * Sets the execution statistics for a specific job run.
     * @param state - Current job run state
     * @param action - Action containing the job run ID and statistics
     */
    setStatistics: (state, action: PayloadAction<{ jobRunId: string; stats: RunStats }>) => {
      const { jobRunId, stats } = action.payload;
      state.statistics[jobRunId] = stats;
    },
    /**
     * Sets the currently selected job run for detail view.
     * @param state - Current job run state
     * @param action - Action containing the job run ID or null
     */
    selectRun: (state, action: PayloadAction<string | null>) => {
      state.selectedRunId = action.payload;
    },
    /**
     * Sets the loading state for async operations.
     * @param state - Current job run state
     * @param action - Action containing the loading boolean
     */
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    /**
     * Sets an error message and clears loading state.
     * @param state - Current job run state
     * @param action - Action containing the error message or null
     */
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
      state.loading = false;
    },
    /**
     * Clears the current error message.
     * @param state - Current job run state
     */
    clearError: (state) => {
      state.error = null;
    },
    /**
     * Arms the run-viewer with the IDs to poll. Pass null on exit.
     * @param state - Current job run state
     * @param action - Action containing job ID and job run ID, or null
     */
    setCurrentRun: (state, action: PayloadAction<{ jobId: string; jobRunId: string } | null>) => {
      if (action.payload) {
        state.currentJobId = action.payload.jobId;
        state.currentJobRunId = action.payload.jobRunId;
      } else {
        state.currentJobId = null;
        state.currentJobRunId = null;
      }
    },
    /**
     * Tracks whether execution is in-flight (drives Stop/Run-Again state).
     * @param state - Current job run state
     * @param action - Action containing the running state boolean
     */
    setRunning: (state, action: PayloadAction<boolean>) => {
      state.isRunning = action.payload;
    },
    /**
     * Updated on every poll tick; null when not in run-viewer mode.
     * @param state - Current job run state
     * @param action - Action containing the execution logs or null
     */
    setExecutionLogs: (state, action: PayloadAction<JobRunStatusResponse | null>) => {
      state.executionLogs = action.payload;
    },
  },
});

export const {
 setJobRuns,
 setJobRun,
 updateJobRun,
 setLogs,
 setStatistics,
 selectRun,
 setLoading,
 setError,
 clearError,
 setCurrentRun,
 setRunning,
 setExecutionLogs,
} = jobRunSlice.actions;

export default jobRunSlice.reducer;
