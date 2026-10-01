import { describe, it, expect } from 'vitest';
import {
  selectJobRunItems,
  selectIsRunning,
  selectCurrentJobRunId,
  selectCurrentJobId,
  selectJobRunsArray,
  selectJobRunCount,
  selectSelectedJobRun,
  selectJobRunsByJobId,
  selectSelectedRunId,
  selectJobRunLogsMap,
  selectJobRunStatisticsMap,
  selectJobRunLoading,
  selectJobRunError,
  selectSelectedJobRunLogs,
  selectSelectedJobRunStatistics,
  selectHasSelectedJobRun,
  selectRunIdsByJobId,
  selectJobRunsByJob,
  selectJobRunsByStatus,
  selectExecutionLogs,
} from '@/selectors/jobRunSelectors';
import type { RootState } from '@/store';
import { buildPreloadedState } from '../../mocks/fixtures/store.fixture';

function makeState(overrides: Partial<RootState['jobRun']> = {}): RootState {
  return buildPreloadedState({
    jobRun: {
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
      ...overrides,
    },
  }) as RootState;
}

describe('jobRunSelectors', () => {
  // ── existing tests (kept) ────────────────────────────────────────────────

  it('selectJobRunItems returns items dict', () => {
    const items = { 'run-1': { job_run_id: 'run-1' } as never };
    expect(selectJobRunItems(makeState({ items }))).toEqual(items);
  });

  it('selectIsRunning returns isRunning flag', () => {
    expect(selectIsRunning(makeState({ isRunning: true }))).toBe(true);
    expect(selectIsRunning(makeState({ isRunning: false }))).toBe(false);
  });

  it('selectCurrentJobRunId returns currentJobRunId', () => {
    expect(selectCurrentJobRunId(makeState({ currentJobRunId: 'run-123' }))).toBe('run-123');
  });

  it('selectCurrentJobId returns currentJobId', () => {
    expect(selectCurrentJobId(makeState({ currentJobId: 'job-abc' }))).toBe('job-abc');
  });

  it('selectJobRunsArray converts dict to array', () => {
    const items = { r1: { job_run_id: 'r1' } as never, r2: { job_run_id: 'r2' } as never };
    expect(selectJobRunsArray(makeState({ items }))).toHaveLength(2);
  });

  it('selectJobRunCount counts entries', () => {
    const items = { r1: {} as never, r2: {} as never };
    expect(selectJobRunCount(makeState({ items }))).toBe(2);
  });

  it('selectSelectedJobRun returns null when no run selected', () => {
    expect(selectSelectedJobRun(makeState({ selectedRunId: null }))).toBeNull();
  });

  it('selectSelectedJobRun returns run by selectedRunId', () => {
    const run = { job_run_id: 'r1' } as never;
    const state = makeState({ items: { r1: run }, selectedRunId: 'r1' });
    expect(selectSelectedJobRun(state)).toEqual(run);
  });

  // ── new tests ────────────────────────────────────────────────────────────

  it('selectJobRunsByJobId returns byJobId map', () => {
    const byJobId = { 'job-1': ['run-1', 'run-2'] };
    expect(selectJobRunsByJobId(makeState({ byJobId }))).toEqual(byJobId);
  });

  it('selectSelectedRunId returns selectedRunId', () => {
    expect(selectSelectedRunId(makeState({ selectedRunId: 'run-42' }))).toBe('run-42');
    expect(selectSelectedRunId(makeState())).toBeNull();
  });

  it('selectJobRunLogsMap returns logs map', () => {
    const logs = { 'run-1': ['log line 1'] as never };
    expect(selectJobRunLogsMap(makeState({ logs }))).toEqual(logs);
  });

  it('selectJobRunStatisticsMap returns statistics map', () => {
    const statistics = { 'run-1': { total: 10 } as never };
    expect(selectJobRunStatisticsMap(makeState({ statistics }))).toEqual(statistics);
  });

  it('selectJobRunLoading returns loading flag', () => {
    expect(selectJobRunLoading(makeState({ loading: true }))).toBe(true);
    expect(selectJobRunLoading(makeState({ loading: false }))).toBe(false);
  });

  it('selectJobRunError returns error string or null', () => {
    expect(selectJobRunError(makeState({ error: 'something went wrong' }))).toBe('something went wrong');
    expect(selectJobRunError(makeState({ error: null }))).toBeNull();
  });

  it('selectSelectedJobRunLogs returns logs for selected run', () => {
    const logs = { 'run-1': ['line a', 'line b'] as never };
    const state = makeState({ logs, selectedRunId: 'run-1' });
    expect(selectSelectedJobRunLogs(state)).toEqual(['line a', 'line b']);
  });

  it('selectSelectedJobRunLogs returns empty array when no run selected', () => {
    expect(selectSelectedJobRunLogs(makeState())).toEqual([]);
  });

  it('selectSelectedJobRunStatistics returns stats for selected run', () => {
    const statistics = { 'run-1': { total: 5 } as never };
    const state = makeState({ statistics, selectedRunId: 'run-1' });
    expect(selectSelectedJobRunStatistics(state)).toEqual({ total: 5 });
  });

  it('selectSelectedJobRunStatistics returns null when no run selected', () => {
    expect(selectSelectedJobRunStatistics(makeState())).toBeNull();
  });

  it('selectHasSelectedJobRun is true when a run is selected', () => {
    expect(selectHasSelectedJobRun(makeState({ selectedRunId: 'run-1' }))).toBe(true);
  });

  it('selectHasSelectedJobRun is false when no run is selected', () => {
    expect(selectHasSelectedJobRun(makeState())).toBe(false);
  });

  it('selectRunIdsByJobId factory returns run IDs for known job', () => {
    const state = makeState({ byJobId: { 'job-1': ['r1', 'r2'] } });
    expect(selectRunIdsByJobId(state)('job-1')).toEqual(['r1', 'r2']);
  });

  it('selectRunIdsByJobId factory returns empty array for unknown job', () => {
    expect(selectRunIdsByJobId(makeState())('no-such-job')).toEqual([]);
  });

  it('selectJobRunsByJob factory returns runs for known job', () => {
    const run1 = { job_run_id: 'r1', status: 'completed' } as never;
    const run2 = { job_run_id: 'r2', status: 'failed' } as never;
    const state = makeState({
      items: { r1: run1, r2: run2 },
      byJobId: { 'job-1': ['r1', 'r2'] },
    });
    expect(selectJobRunsByJob(state)('job-1')).toEqual([run1, run2]);
  });

  it('selectJobRunsByJob factory returns empty array for unknown job', () => {
    expect(selectJobRunsByJob(makeState())('no-such-job')).toEqual([]);
  });

  it('selectJobRunsByStatus filters by status', () => {
    const run1 = { job_run_id: 'r1', status: 'completed' } as never;
    const run2 = { job_run_id: 'r2', status: 'failed' } as never;
    const state = makeState({ items: { r1: run1, r2: run2 } });
    expect(selectJobRunsByStatus(state)('completed')).toEqual([run1]);
    expect(selectJobRunsByStatus(state)('failed')).toEqual([run2]);
    expect(selectJobRunsByStatus(state)('running')).toEqual([]);
  });

  it('selectExecutionLogs returns executionLogs from state', () => {
    const logs = { some: 'data' } as never;
    expect(selectExecutionLogs(makeState({ executionLogs: logs }))).toEqual(logs);
    expect(selectExecutionLogs(makeState())).toBeNull();
  });
});
