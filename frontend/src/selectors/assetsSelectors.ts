/**
 * @fileoverview Selectors for accessing shared navigation assets from the Redux store.
 * Covers flows and job runs. Project selectors live in `projectsSelectors.ts`.
 */

import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@/store';

// ── Basic selectors ───────────────────────────────────────────────────────

/** Selects the entire assets state slice. */
export const selectAssetsState = (state: RootState) => state.assets;

/** Selects the flows dictionary. */
export const selectAssetsFlows = (state: RootState) => state.assets.flows;

/** Selects the job runs dictionary. */
export const selectAssetsJobRuns = (state: RootState) => state.assets.jobRuns;

/** Selects the currently selected flow ID. */
export const selectAssetsSelectedFlowId = (state: RootState) => state.assets.selectedFlowId;

/** Selects the currently selected job run ID. */
export const selectAssetsSelectedJobRunId = (state: RootState) => state.assets.selectedJobRunId;

// ── Memoized selectors ────────────────────────────────────────────────────

/**
 * Retrieves the currently selected flow asset by ID.
 * @returns The selected flow asset or null if none selected.
 */
export const selectAssetsSelectedFlow = createSelector(
  [selectAssetsFlows, selectAssetsSelectedFlowId],
  (flows, selectedId) => (selectedId ? flows[selectedId] : null)
);

/**
 * Retrieves the currently selected job run asset by ID.
 * @returns The selected job run asset or null if none selected.
 */
export const selectAssetsSelectedJobRun = createSelector(
  [selectAssetsJobRuns, selectAssetsSelectedJobRunId],
  (jobRuns, selectedId) => (selectedId ? jobRuns[selectedId] : null)
);

/**
 * Converts the flows dictionary to an array.
 * @returns Array of all flow asset objects.
 */
export const selectAssetsFlowsArray = createSelector(
  [selectAssetsFlows],
  (flows) => Object.values(flows)
);

/**
 * Converts the job runs dictionary to an array.
 * @returns Array of all job run asset objects.
 */
export const selectAssetsJobRunsArray = createSelector(
  [selectAssetsJobRuns],
  (jobRuns) => Object.values(jobRuns)
);
