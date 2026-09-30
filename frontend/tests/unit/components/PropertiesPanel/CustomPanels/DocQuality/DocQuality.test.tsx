import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DocQualityPanelBody } from '@/components/PropertiesPanel/CustomPanels/DocQuality/DocQuality';

function makeController(overrides: Record<string, unknown> = {}) {
  return {
    getAppData: vi.fn(() => ({ operatorMetadata: {} })),
    getPropertyValue: vi.fn(() => undefined),
    updatePropertyValue: vi.fn(),
    ...overrides,
  };
}

describe('DocQualityPanelBody', () => {
  it('renders the Language text input', () => {
    const controller = makeController();
    render(<DocQualityPanelBody controller={controller} />);
    expect(document.getElementById('text_lang')).not.toBeNull();
  });

  it('defaults to "en" when no value stored', () => {
    const controller = makeController();
    render(<DocQualityPanelBody controller={controller} />);
    const input = document.getElementById('text_lang') as HTMLInputElement;
    expect(input.value).toBe('en');
  });

  it('uses the stored value from controller', () => {
    const controller = makeController({
      getPropertyValue: vi.fn((prop: { name: string }) =>
        prop.name === 'text_lang' ? 'fr' : undefined
      ),
    });
    render(<DocQualityPanelBody controller={controller} />);
    const input = document.getElementById('text_lang') as HTMLInputElement;
    expect(input.value).toBe('fr');
  });

  it('calls updatePropertyValue when typing', () => {
    const update = vi.fn();
    const controller = makeController({ updatePropertyValue: update });
    render(<DocQualityPanelBody controller={controller} />);
    const input = document.getElementById('text_lang') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'de' } });
    expect(update).toHaveBeenCalledWith({ name: 'text_lang' }, 'de');
  });

  it('renders Language label via RequiredParamTooltip', () => {
    const controller = makeController();
    render(<DocQualityPanelBody controller={controller} />);
    const labels = screen.getAllByText('Language');
    expect(labels.length).toBeGreaterThan(0);
  });
});
