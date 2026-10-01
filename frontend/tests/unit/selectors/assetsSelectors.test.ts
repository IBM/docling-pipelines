import { describe, it, expect } from 'vitest';
import {
  selectAssetsFlows,
  selectAssetsJobRuns,
  selectAssetsSelectedFlowId,
  selectAssetsSelectedJobRunId,
  selectAssetsSelectedFlow,
  selectAssetsSelectedJobRun,
  selectAssetsFlowsArray,
  selectAssetsJobRunsArray,
} from '@/selectors/assetsSelectors';
import type { RootState } from '@/store';
import { buildPreloadedState } from '../../mocks/fixtures/store.fixture';

function makeState(overrides: Partial<RootState['assets']> = {}): RootState {
  return buildPreloadedState({
    assets: {
      flows: {},
      jobRuns: {},
      selectedFlowId: null,
      selectedJobRunId: null,
      ...overrides,
    },
  }) as RootState;
}

describe('assetsSelectors', () => {
  it('selectAssetsFlows returns state.assets.flows', () => {
    const flows = { 'f1': { id: 'f1' } as never };
    const state = makeState({ flows });
    expect(selectAssetsFlows(state)).toEqual(flows);
  });

  it('selectAssetsJobRuns returns state.assets.jobRuns', () => {
    const jobRuns = { 'jr1': { id: 'jr1' } as never };
    const state = makeState({ jobRuns });
    expect(selectAssetsJobRuns(state)).toEqual(jobRuns);
  });

  it('selectAssetsSelectedFlowId returns selected flow id', () => {
    const state = makeState({ selectedFlowId: 'flow-xyz' });
    expect(selectAssetsSelectedFlowId(state)).toBe('flow-xyz');
  });

  it('selectAssetsSelectedJobRunId returns selected job run id', () => {
    const state = makeState({ selectedJobRunId: 'run-abc' });
    expect(selectAssetsSelectedJobRunId(state)).toBe('run-abc');
  });

  it('selectAssetsSelectedFlow returns null when no flow selected', () => {
    const state = makeState({ selectedFlowId: null });
    expect(selectAssetsSelectedFlow(state)).toBeNull();
  });

  it('selectAssetsSelectedFlow returns the correct flow by id', () => {
    const flow = { id: 'f1' } as never;
    const state = makeState({ flows: { f1: flow }, selectedFlowId: 'f1' });
    expect(selectAssetsSelectedFlow(state)).toEqual(flow);
  });

  it('selectAssetsSelectedJobRun returns null when no job run selected', () => {
    const state = makeState({ selectedJobRunId: null });
    expect(selectAssetsSelectedJobRun(state)).toBeNull();
  });

  it('selectAssetsFlowsArray converts dict to array', () => {
    const flows = { f1: { id: 'f1' } as never, f2: { id: 'f2' } as never };
    const state = makeState({ flows });
    expect(selectAssetsFlowsArray(state)).toHaveLength(2);
  });

  it('selectAssetsJobRunsArray converts dict to array', () => {
    const jobRuns = { jr1: { id: 'jr1' } as never };
    const state = makeState({ jobRuns });
    expect(selectAssetsJobRunsArray(state)).toHaveLength(1);
  });
});
