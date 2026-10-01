import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReadabilityPanelBody } from '@/components/PropertiesPanel/CustomPanels/Readability/Readability';

function makeController(overrides: Record<string, unknown> = {}) {
  return {
    getAppData: vi.fn(() => ({ operatorMetadata: {} })),
    getPropertyValue: vi.fn(() => undefined),
    updatePropertyValue: vi.fn(),
    ...overrides,
  };
}

describe('ReadabilityPanelBody', () => {
  it('renders readability_score_list multi-select', () => {
    render(<ReadabilityPanelBody controller={makeController()} />);
    // FilterableMultiSelect renders a combobox
    expect(document.getElementById('readability_score_list')).not.toBeNull();
  });

  it('renders Readability scores label', () => {
    render(<ReadabilityPanelBody controller={makeController()} />);
    expect(screen.getAllByText('Readability scores').length).toBeGreaterThan(0);
  });

  it('uses stored score list value', () => {
    const controller = makeController({
      getPropertyValue: vi.fn((p: { name: string }) =>
        p.name === 'readability_score_list' ? ['flesch_kincaid_grade'] : undefined
      ),
    });
    const { container } = render(<ReadabilityPanelBody controller={controller} />);
    expect(container.querySelector('#readability_score_list')).not.toBeNull();
  });

  it('renders panel container', () => {
    const { container } = render(<ReadabilityPanelBody controller={makeController()} />);
    expect(container.firstChild).not.toBeNull();
  });
});
