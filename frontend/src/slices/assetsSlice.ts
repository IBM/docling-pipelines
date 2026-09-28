/**
 * @fileoverview Redux slice for managing shared navigation assets.
 * Handles flows and job runs. Projects have been extracted to `projectsSlice`.
 */

import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { AssetsState, FlowAsset, JobRunAsset } from '@/types';

const initialState: AssetsState = {
  flows: {},
  jobRuns: {},
  selectedFlowId: null,
  selectedJobRunId: null,
};

/**
 * Redux slice for shared navigation asset state.
 * Manages flows and job runs. Projects are owned by `projectsSlice`.
 */
const assetsSlice = createSlice({
  name: 'assets',
  initialState,
  reducers: {
    /**
     * Sets multiple flow assets at once.
     * @param state  - Current assets state.
     * @param action - Action containing the flows map.
     */
    setFlows: (state, action: PayloadAction<Record<string, FlowAsset>>) => {
      state.flows = action.payload;
    },
    /**
     * Sets or updates a single flow asset.
     * @param state  - Current assets state.
     * @param action - Action containing `{ flowId, flow }`.
     */
    setFlow: (state, action: PayloadAction<{ flowId: string; flow: FlowAsset }>) => {
      state.flows[action.payload.flowId] = action.payload.flow;
    },
    /**
     * Sets multiple job run assets at once.
     * @param state  - Current assets state.
     * @param action - Action containing the job runs map.
     */
    setJobRuns: (state, action: PayloadAction<Record<string, JobRunAsset>>) => {
      state.jobRuns = action.payload;
    },
    /**
     * Sets or updates a single job run asset.
     * @param state  - Current assets state.
     * @param action - Action containing `{ jobRunId, jobRun }`.
     */
    setJobRun: (state, action: PayloadAction<{ jobRunId: string; jobRun: JobRunAsset }>) => {
      state.jobRuns[action.payload.jobRunId] = action.payload.jobRun;
    },
    /**
     * Sets the currently selected flow for navigation.
     * @param state  - Current assets state.
     * @param action - Action containing the flow ID or null.
     */
    selectFlow: (state, action: PayloadAction<string | null>) => {
      state.selectedFlowId = action.payload;
    },
    /**
     * Sets the currently selected job run for navigation.
     * @param state  - Current assets state.
     * @param action - Action containing the job run ID or null.
     */
    selectJobRun: (state, action: PayloadAction<string | null>) => {
      state.selectedJobRunId = action.payload;
    },
  },
});

export const {
  setFlows,
  setFlow,
  setJobRuns,
  setJobRun,
  selectFlow,
  selectJobRun,
} = assetsSlice.actions;

export default assetsSlice.reducer;
