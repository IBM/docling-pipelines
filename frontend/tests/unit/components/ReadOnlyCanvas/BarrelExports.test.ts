/**
 * @fileoverview Tests for ReadOnlyCanvas index.ts barrel re-exports.
 * Each export is imported and verified to be a defined function/object,
 * so coverage tools record the module as executed.
 */
import { describe, it, expect, vi } from 'vitest';

// Dynamic imports under parallel worker load can be slow — raise timeout for this file.
vi.setConfig({ testTimeout: 15000 });

describe('ReadOnlyCanvas index.ts re-exports', () => {
  it('exports ReadOnlyCanvas from the barrel', async () => {
    const mod = await import('@/components/ReadOnlyCanvas');
    expect(mod.ReadOnlyCanvas).toBeDefined();
    expect(typeof mod.ReadOnlyCanvas).toBe('function');
  });

  it('exports RunSidePanel from the barrel', async () => {
    const mod = await import('@/components/ReadOnlyCanvas');
    expect(mod.RunSidePanel).toBeDefined();
    expect(typeof mod.RunSidePanel).toBe('function');
  });

  it('exports RunStatusTopPanel from the barrel', async () => {
    const mod = await import('@/components/ReadOnlyCanvas');
    expect(mod.RunStatusTopPanel).toBeDefined();
    expect(typeof mod.RunStatusTopPanel).toBe('function');
  });
});

describe('JobRunLogs index.ts re-export', () => {
  it('exports JobRunLogs from the barrel', async () => {
    const mod = await import('@/components/ReadOnlyCanvas/RunSidePanel/JobRunLogs');
    expect(mod.JobRunLogs).toBeDefined();
    expect(typeof mod.JobRunLogs).toBe('function');
  });
});

describe('NodeSummary index.ts re-export', () => {
  it('exports NodeSummary from the barrel', async () => {
    const mod = await import('@/components/ReadOnlyCanvas/RunSidePanel/NodeSummary');
    expect(mod.NodeSummary).toBeDefined();
    expect(typeof mod.NodeSummary).toBe('function');
  });
});

describe('RunSidePanel index.ts re-export', () => {
  it('exports RunSidePanel from the barrel', async () => {
    const mod = await import('@/components/ReadOnlyCanvas/RunSidePanel');
    expect(mod.RunSidePanel).toBeDefined();
    expect(typeof mod.RunSidePanel).toBe('function');
  });
});
