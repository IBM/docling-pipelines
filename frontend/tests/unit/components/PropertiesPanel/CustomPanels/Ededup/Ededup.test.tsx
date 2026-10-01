import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EdedupPanelBody } from '@/components/PropertiesPanel/CustomPanels/Ededup/Ededup';

describe('EdedupPanelBody', () => {
  it('renders info notification about no configuration', () => {
    const controller = { getAppData: vi.fn(), getPropertyValue: vi.fn(), updatePropertyValue: vi.fn() };
    render(<EdedupPanelBody controller={controller} />);
    expect(screen.getByText('No configuration required')).toBeInTheDocument();
  });

  it('mentions content hash in subtitle', () => {
    const controller = { getAppData: vi.fn(), getPropertyValue: vi.fn(), updatePropertyValue: vi.fn() };
    render(<EdedupPanelBody controller={controller} />);
    expect(
      screen.getByText(/automatically removes exact duplicate documents based on a content hash/i)
    ).toBeInTheDocument();
  });
});
