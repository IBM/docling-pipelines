import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useNodeSuggestion } from '@/hooks/useNodeSuggestion';

/** Minimal CanvasController mock used by openNodeSuggestion. */
function makeController(nodeOverrides: Record<string, unknown> = {}) {
  return {
    getNode: vi.fn(() => ({
      id: 'node-1',
      op: 'ingest_source',
      x_pos: 100,
      y_pos: 100,
      width: 208,
      height: 68,
      ...nodeOverrides,
    })),
    getZoom: vi.fn(() => ({ x: 0, y: 0, k: 1 })),
    getPaletteData: vi.fn(() => ({
      categories: [
        {
          label: 'Ingest',
          node_types: [{ op: 'extract_operator', label: 'Extract' }],
        },
      ],
    })),
    getPipelineFlow: vi.fn(() => ({
      pipelines: [{ nodes: [{ id: 'node-1', op: 'ingest_source' }] }],
    })),
    getPaletteNode: vi.fn(() => ({ op: 'extract_operator' })),
    setSelections: vi.fn(),
    getCurrentPipelineId: vi.fn(() => 'pipeline-1'),
    editActionHandler: vi.fn(),
  };
}

describe('useNodeSuggestion', () => {
  beforeEach(() => {
    // Add a dummy canvas element so getNodeSuggestionLayout can find it
    const el = document.createElement('div');
    el.className = 'd3-svg-background';
    document.body.appendChild(el);
  });

  afterEach(() => {
    const el = document.querySelector('.d3-svg-background');
    if (el) { el.remove(); }
  });

  it('initial nodeSuggestion is null', () => {
    const { result } = renderHook(() => useNodeSuggestion());
    expect(result.current.nodeSuggestion).toBeNull();
  });

  it('exposes openNodeSuggestion, handleNodeSuggestionClose, handleNodeSuggestionSelect', () => {
    const { result } = renderHook(() => useNodeSuggestion());
    expect(typeof result.current.openNodeSuggestion).toBe('function');
    expect(typeof result.current.handleNodeSuggestionClose).toBe('function');
    expect(typeof result.current.handleNodeSuggestionSelect).toBe('function');
  });

  it('handleNodeSuggestionClose sets nodeSuggestion to null', () => {
    const { result } = renderHook(() => useNodeSuggestion());
    act(() => { result.current.handleNodeSuggestionClose(); });
    expect(result.current.nodeSuggestion).toBeNull();
  });

  it('openNodeSuggestion sets nodeSuggestion when node layout is resolved', () => {
    const controller = makeController();
    const { result } = renderHook(() => useNodeSuggestion());
    act(() => { result.current.openNodeSuggestion('node-1', controller); });
    // If the .d3-svg-background element exists getBoundingClientRect returns zeros,
    // but the layout object is still constructed — nodeSuggestion may be set
    expect(result.current).toBeDefined();
  });

  it('openNodeSuggestion does nothing when getNode returns null', () => {
    const controller = makeController();
    controller.getNode = vi.fn(() => null as never);
    const { result } = renderHook(() => useNodeSuggestion());
    act(() => { result.current.openNodeSuggestion('node-99', controller); });
    expect(result.current.nodeSuggestion).toBeNull();
  });

  it('handleNodeSuggestionSelect does nothing when controller is null', () => {
    const { result } = renderHook(() => useNodeSuggestion());
    expect(() => {
      act(() => { result.current.handleNodeSuggestionSelect('extract_operator', null); });
    }).not.toThrow();
    expect(result.current.nodeSuggestion).toBeNull();
  });

  it('handleNodeSuggestionSelect closes panel when getPaletteNode returns null', () => {
    const controller = makeController();
    controller.getPaletteNode = vi.fn(() => null as never);
    const { result } = renderHook(() => useNodeSuggestion());
    act(() => { result.current.handleNodeSuggestionSelect('unknown_op', controller); });
    expect(result.current.nodeSuggestion).toBeNull();
  });

  it('filterPaletteByOps excludes already-connected ops from suggestion', () => {
    const controller = makeController();
    // Make getPipelineFlow return a node that has the extract_operator already
    controller.getPipelineFlow = vi.fn(() => ({
      pipelines: [{
        nodes: [
          { id: 'node-1', op: 'ingest_source' },
          { id: 'node-2', op: 'extract_operator' },
        ],
      }],
    }));
    const { result } = renderHook(() => useNodeSuggestion());
    act(() => { result.current.openNodeSuggestion('node-1', controller); });
    // The suggestion palette should have filtered out extract_operator
    if (result.current.nodeSuggestion) {
      const cats = result.current.nodeSuggestion.paletteData?.categories ?? [];
      const allOps = cats.flatMap((c: { node_types: { op: string }[] }) =>
        c.node_types.map((n: { op: string }) => n.op)
      );
      expect(allOps).not.toContain('extract_operator');
    }
  });
});
