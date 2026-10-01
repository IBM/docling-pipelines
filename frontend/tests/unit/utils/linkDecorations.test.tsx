import { describe, it, expect, vi } from 'vitest';
import { buildLinkDecorations, applyAllLinkDecorations } from '@/utils/linkDecorations';

describe('buildLinkDecorations', () => {
  it('returns a single decoration with pill jsx when label is non-empty', () => {
    const decs = buildLinkDecorations('condition-a', 'link-1');
    expect(decs).toHaveLength(1);
    expect((decs[0] as { id: string }).id).toBe('link-1-pill');
  });

  it('pill decoration has hotspot=true in editable mode', () => {
    const decs = buildLinkDecorations('label', 'link-2');
    expect((decs[0] as { hotspot: boolean }).hotspot).toBe(true);
  });

  it('pill decoration has hotspot=false in readOnly mode', () => {
    const decs = buildLinkDecorations('label', 'link-3', true);
    expect((decs[0] as { hotspot: boolean }).hotspot).toBe(false);
  });

  it('returns Add icon decoration when label is empty and not readOnly', () => {
    const decs = buildLinkDecorations('', 'link-4');
    expect(decs).toHaveLength(1);
    const dec = decs[0] as { id: string; hotspot: boolean };
    expect(dec.id).toContain('link-4');
    expect(dec.hotspot).toBe(true);
  });

  it('returns empty array when label is empty and readOnly=true', () => {
    const decs = buildLinkDecorations('', 'link-5', true);
    expect(decs).toHaveLength(0);
  });

  it('pill decoration uses middle position', () => {
    const decs = buildLinkDecorations('my-label', 'link-6');
    expect((decs[0] as { position: string }).position).toBe('middle');
  });

  it('add-icon decoration uses middle position', () => {
    const decs = buildLinkDecorations('', 'link-7');
    expect((decs[0] as { position: string }).position).toBe('middle');
  });

  it('decoration id includes the linkId', () => {
    const decs = buildLinkDecorations('x', 'my-link-id');
    expect((decs[0] as { id: string }).id).toContain('my-link-id');
  });
});

describe('applyAllLinkDecorations', () => {
  function makeController(nodes: object[]) {
    return {
      getPipelineFlow: vi.fn(() => ({
        pipelines: [{ nodes }],
      })),
      setLinkDecorations: vi.fn(),
    };
  }

  it('does nothing when there are no nodes', () => {
    const ctrl = makeController([]);
    applyAllLinkDecorations(ctrl as never);
    expect(ctrl.setLinkDecorations).not.toHaveBeenCalled();
  });

  it('does nothing when there are no branching nodes', () => {
    const ctrl = makeController([
      { id: 'n1', op: 'chunker', inputs: [] },
    ]);
    applyAllLinkDecorations(ctrl as never);
    expect(ctrl.setLinkDecorations).not.toHaveBeenCalled();
  });

  it('stamps decorations on links from a branching node', () => {
    const ctrl = makeController([
      {
        id: 'branching-1',
        op: 'branching',
        parameters: {
          link_conditions: [{ link_id: 'link-1', link_name: 'branch-a' }],
        },
        inputs: [],
      },
      {
        id: 'chunker-1',
        op: 'chunker',
        inputs: [
          {
            links: [
              { id: 'link-1', node_id_ref: 'branching-1' },
            ],
          },
        ],
      },
    ]);
    applyAllLinkDecorations(ctrl as never);
    expect(ctrl.setLinkDecorations).toHaveBeenCalledWith(
      'link-1',
      expect.arrayContaining([
        expect.objectContaining({ id: 'link-1-pill' }),
      ])
    );
  });

  it('stamps empty-label (Add icon) decoration when link_name is absent', () => {
    const ctrl = makeController([
      {
        id: 'branching-1',
        op: 'branching',
        parameters: { link_conditions: [] },
        inputs: [],
      },
      {
        id: 'next-1',
        op: 'chunker',
        inputs: [
          { links: [{ id: 'link-2', node_id_ref: 'branching-1' }] },
        ],
      },
    ]);
    applyAllLinkDecorations(ctrl as never, false);
    expect(ctrl.setLinkDecorations).toHaveBeenCalledWith('link-2', expect.any(Array));
  });

  it('stamps decorations on merging-node input links', () => {
    const ctrl = makeController([
      {
        id: 'merge-1',
        op: 'merge',
        inputs: [
          { links: [{ id: 'link-m', link_name: 'branch-b' }] },
        ],
      },
    ]);
    applyAllLinkDecorations(ctrl as never);
    expect(ctrl.setLinkDecorations).toHaveBeenCalledWith(
      'link-m',
      expect.any(Array)
    );
  });

  it('in readOnly mode branching link with name gets non-clickable pill', () => {
    const ctrl = makeController([
      {
        id: 'b1',
        op: 'branching',
        parameters: { link_conditions: [{ link_id: 'lk', link_name: 'my-branch' }] },
        inputs: [],
      },
      {
        id: 'c1',
        op: 'chunker',
        inputs: [{ links: [{ id: 'lk', node_id_ref: 'b1' }] }],
      },
    ]);
    applyAllLinkDecorations(ctrl as never, true);
    const call = ctrl.setLinkDecorations.mock.calls.find((c) => c[0] === 'lk');
    expect(call).toBeDefined();
    const decs = call?.[1] as { hotspot: boolean }[];
    expect(decs[0]?.hotspot).toBe(false);
  });

  it('handles undefined flow gracefully', () => {
    const ctrl = {
      getPipelineFlow: vi.fn(() => undefined),
      setLinkDecorations: vi.fn(),
    };
    expect(() => { applyAllLinkDecorations(ctrl as never); }).not.toThrow();
    expect(ctrl.setLinkDecorations).not.toHaveBeenCalled();
  });
});
