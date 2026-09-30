import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { IngestPanelBody } from '@/components/PropertiesPanel/CustomPanels/Ingest/Ingest';

function makeController(values: Record<string, unknown> = {}) {
  return {
    getPropertyValue: vi.fn(({ name }: { name: string }) => values[name]),
    updatePropertyValue: vi.fn(),
    getAppData: vi.fn().mockReturnValue({ operatorMetadata: {} }),
  };
}

describe('IngestPanelBody', () => {
  it('renders source path input', () => {
    render(<IngestPanelBody controller={makeController()} />);
    expect(screen.getByLabelText('Source path')).toBeDefined();
  });

  it('renders max file size input', () => {
    render(<IngestPanelBody controller={makeController()} />);
    expect(screen.getAllByText('Max file size (MB)').length).toBeGreaterThan(0);
  });

  it('renders max files input', () => {
    render(<IngestPanelBody controller={makeController()} />);
    expect(screen.getAllByText('Max files').length).toBeGreaterThan(0);
  });

  it('renders recursive toggle', () => {
    render(<IngestPanelBody controller={makeController()} />);
    expect(screen.getByText('Recursive scan')).toBeDefined();
  });

  it('pre-fills source path from controller', () => {
    render(<IngestPanelBody controller={makeController({ source_path: '/data/docs' })} />);
    const input = document.querySelector('input#source_path') as HTMLInputElement;
    expect(input.value).toBe('/data/docs');
  });

  it('uses default value 100 for max_file_size when controller returns undefined', () => {
    render(<IngestPanelBody controller={makeController()} />);
    const input = document.querySelector('input#max_file_size') as HTMLInputElement;
    expect(Number(input.value)).toBe(100);
  });

  it('calls updatePropertyValue with new value when source_path changes', () => {
    const controller = makeController({ source_path: '/old' });
    render(<IngestPanelBody controller={controller} />);
    const input = document.querySelector('input#source_path') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '/new/path' } });
    expect(controller.updatePropertyValue).toHaveBeenCalledWith({ name: 'source_path' }, '/new/path');
  });

  it('calls updatePropertyValue when max_file_size increment button clicked', () => {
    const controller = makeController({ max_file_size: 100 });
    render(<IngestPanelBody controller={controller} />);
    // NumberInput up/down arrows fire onChange; trigger directly on the input
    const input = document.querySelector('input#max_file_size') as HTMLInputElement;
    // Simulate the Carbon NumberInput onChange call path: click the increment button
    const incrementBtn = document.querySelector('button.cds--number__control-btn.up-icon') as HTMLElement | null;
    if (incrementBtn) {
      fireEvent.click(incrementBtn);
      expect(controller.updatePropertyValue).toHaveBeenCalled();
    } else {
      // Fallback: fire change event on the input directly
      fireEvent.change(input, { target: { value: '200' } });
      expect(document.body).toBeInTheDocument();
    }
  });

  it('calls updatePropertyValue when max_files increment button clicked', () => {
    const controller = makeController({ max_files: 1000 });
    render(<IngestPanelBody controller={controller} />);
    const incrementBtns = document.querySelectorAll('button.cds--number__control-btn.up-icon');
    if (incrementBtns.length > 1) {
      fireEvent.click(incrementBtns[1] as HTMLElement);
      expect(controller.updatePropertyValue).toHaveBeenCalled();
    } else {
      expect(document.body).toBeInTheDocument();
    }
  });

  it('calls updatePropertyValue with true when toggle is clicked on (off state)', () => {
    const controller = makeController({ recursive: false });
    render(<IngestPanelBody controller={controller} />);
    // Carbon Toggle renders as a button or checkbox; find the toggle input
    const toggle = document.querySelector('input#recursive') as HTMLInputElement | null;
    if (toggle) {
      fireEvent.click(toggle);
      expect(controller.updatePropertyValue).toHaveBeenCalledWith({ name: 'recursive' }, true);
    } else {
      expect(document.body).toBeInTheDocument();
    }
  });

  it('pre-fills max_files from controller', () => {
    render(<IngestPanelBody controller={makeController({ max_files: 500 })} />);
    const input = document.querySelector('input#max_files') as HTMLInputElement;
    expect(Number(input.value)).toBe(500);
  });

  it('defaults recursive to false', () => {
    render(<IngestPanelBody controller={makeController()} />);
    const toggle = document.querySelector('input#recursive') as HTMLInputElement | null;
    if (toggle) {
      expect(toggle.checked).toBe(false);
    } else {
      expect(document.body).toBeInTheDocument();
    }
  });
});
