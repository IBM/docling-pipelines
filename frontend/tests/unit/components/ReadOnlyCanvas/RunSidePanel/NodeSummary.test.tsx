import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { NodeSummary } from '@/components/ReadOnlyCanvas/RunSidePanel/NodeSummary/NodeSummary';
import type { NodeMetadataItem, JobStats } from '@/types';

const makeJobStats = (overrides: Partial<JobStats> = {}): JobStats => ({
  status: 'completed',
  message: '',
  node_stats: {
    'node-1': { name: 'Extract Node', node_status: 'completed' } as any,
  },
  ...overrides,
} as unknown as JobStats);

const makeNodeMetadata = (overrides: Partial<NodeMetadataItem> = {}): NodeMetadataItem => ({
  id: 'node-1',
  operator: 'extract_operator',
  node_metadata: {
    documents_processed: 42,
    total_duration: 3.14,
  },
  ...overrides,
} as unknown as NodeMetadataItem);

describe('NodeSummary', () => {
  it('renders node name from job_stats', () => {
    render(
      <NodeSummary nodeMetadata={makeNodeMetadata()} jobStats={makeJobStats()} />
    );
    expect(screen.getByText('Extract Node')).toBeInTheDocument();
  });

  it('renders operator type', () => {
    render(
      <NodeSummary nodeMetadata={makeNodeMetadata()} jobStats={makeJobStats()} />
    );
    expect(screen.getAllByText('extract_operator').length).toBeGreaterThan(0);
  });

  it('renders node status badge', () => {
    render(
      <NodeSummary nodeMetadata={makeNodeMetadata()} jobStats={makeJobStats()} />
    );
    expect(screen.getByText('completed')).toBeInTheDocument();
  });

  it('renders metadata rows in the table', () => {
    render(
      <NodeSummary nodeMetadata={makeNodeMetadata()} jobStats={makeJobStats()} />
    );
    expect(screen.getByText('Documents Processed')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('shows fallback message when no stats and no metadata', () => {
    render(
      <NodeSummary
        nodeMetadata={makeNodeMetadata({ node_metadata: undefined })}
        jobStats={{ status: 'completed', message: '', node_stats: {} } as unknown as JobStats}
      />
    );
    expect(screen.getByText(/No metadata available/i)).toBeInTheDocument();
  });
});
