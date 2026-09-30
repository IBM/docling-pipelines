import { describe, it, expect } from 'vitest';
import jobRunReducer, {
  setJobRuns,
  setJobRun,
  updateJobRun,
  selectRun,
  setLoading,
  setError,
  clearError,
  setRunning,
  setCurrentRun,
} from '@/slices/jobRunSlice';
import type { JobRunState } from '@/types';

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

describe('jobRunSlice reducers', () => {
  it('initial state is correct', () => {
    const state = jobRunReducer(undefined, { type: '@@INIT' });
    expect(state).toEqual(initialState);
  });

  it('setJobRuns replaces items, clears loading and error', () => {
    const start = { ...initialState, loading: true, error: 'old' };
    const runs = { 'r-1': { jobRunId: 'r-1', status: 'Completed' } };
    const state = jobRunReducer(start, setJobRuns(runs));
    expect(state.items['r-1']).toEqual({ jobRunId: 'r-1', status: 'Completed' });
    expect(state.loading).toBe(false);
    expect(state.error).toBeNull();
  });

  it('setJobRun inserts a job run and updates byJobId index', () => {
    const run = { jobRunId: 'r-1', jobId: 'j-1', status: 'Running' };
    const state = jobRunReducer(initialState, setJobRun({ jobRunId: 'r-1', jobRun: run }));
    expect(state.items['r-1']).toEqual(run);
    expect(state.byJobId['j-1']).toContain('r-1');
  });

  it('updateJobRun merges partial updates', () => {
    const start = { ...initialState, items: { 'r-1': { jobRunId: 'r-1', status: 'Running' } } };
    const state = jobRunReducer(start, updateJobRun({ jobRunId: 'r-1', updates: { status: 'Completed' } }));
    expect(state.items['r-1']?.status).toBe('Completed');
  });

  it('selectRun sets selectedRunId', () => {
    const state = jobRunReducer(initialState, selectRun('r-1'));
    expect(state.selectedRunId).toBe('r-1');
  });

  it('setLoading updates loading flag', () => {
    expect(jobRunReducer(initialState, setLoading(true)).loading).toBe(true);
  });

  it('setError sets error and clears loading', () => {
    const start = { ...initialState, loading: true };
    const state = jobRunReducer(start, setError('failed'));
    expect(state.error).toBe('failed');
    expect(state.loading).toBe(false);
  });

  it('clearError sets error to null', () => {
    const state = jobRunReducer({ ...initialState, error: 'prev' }, clearError());
    expect(state.error).toBeNull();
  });

  it('setRunning updates isRunning', () => {
    expect(jobRunReducer(initialState, setRunning(true)).isRunning).toBe(true);
    expect(jobRunReducer(initialState, setRunning(false)).isRunning).toBe(false);
  });

  it('setCurrentRun stores jobId and jobRunId', () => {
    const state = jobRunReducer(initialState, setCurrentRun({ jobId: 'j-1', jobRunId: 'r-1' }));
    expect(state.currentJobId).toBe('j-1');
    expect(state.currentJobRunId).toBe('r-1');
  });

  it('setCurrentRun(null) clears currentJobId and currentJobRunId', () => {
    const start = { ...initialState, currentJobId: 'j-1', currentJobRunId: 'r-1' };
    const state = jobRunReducer(start, setCurrentRun(null));
    expect(state.currentJobId).toBeNull();
    expect(state.currentJobRunId).toBeNull();
  });
});
