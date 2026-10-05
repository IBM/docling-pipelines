import { describe, it, expect } from 'vitest';
import assetsReducer, {
  setFlows,
  setFlow,
  setJobRuns,
  setJobRun,
  selectFlow,
  selectJobRun,
} from '@/slices/assetsSlice';
import type { AssetsState } from '@/types';

const initialState: AssetsState = {
  flows: {},
  jobRuns: {},
  selectedFlowId: null,
  selectedJobRunId: null,
};

describe('assetsSlice reducers', () => {
  it('initial state is correct', () => {
    const state = assetsReducer(undefined, { type: '@@INIT' });
    expect(state).toEqual(initialState);
  });

  it('setFlows replaces flows map', () => {
    const flows = { 'f-1': { flowId: 'f-1', name: 'Flow' } };
    const state = assetsReducer(initialState, setFlows(flows));
    expect(state.flows).toEqual(flows);
  });

  it('setFlow inserts or updates a single flow', () => {
    const state = assetsReducer(initialState, setFlow({ flowId: 'f-1', flow: { name: 'Flow 1' } }));
    expect(state.flows['f-1']).toEqual({ name: 'Flow 1' });
  });

  it('setJobRuns replaces jobRuns map', () => {
    const runs = { 'r-1': { jobRunId: 'r-1' } };
    const state = assetsReducer(initialState, setJobRuns(runs));
    expect(state.jobRuns).toEqual(runs);
  });

  it('setJobRun inserts or updates a single job run', () => {
    const state = assetsReducer(initialState, setJobRun({ jobRunId: 'r-1', jobRun: { status: 'Running' } }));
    expect(state.jobRuns['r-1']).toEqual({ status: 'Running' });
  });

  it('selectFlow sets selectedFlowId', () => {
    const state = assetsReducer(initialState, selectFlow('f-1'));
    expect(state.selectedFlowId).toBe('f-1');
  });

  it('selectFlow(null) clears selectedFlowId', () => {
    const start = { ...initialState, selectedFlowId: 'f-1' };
    expect(assetsReducer(start, selectFlow(null)).selectedFlowId).toBeNull();
  });

  it('selectJobRun sets selectedJobRunId', () => {
    const state = assetsReducer(initialState, selectJobRun('r-1'));
    expect(state.selectedJobRunId).toBe('r-1');
  });
});
