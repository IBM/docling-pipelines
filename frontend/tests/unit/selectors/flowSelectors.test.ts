import { describe, it, expect } from 'vitest';
import {
  selectFlows,
  selectCurrentFlow,
  selectFlowsArray,
  selectFlowCount,
  selectFlowLoading,
  selectFlowError,
  selectFlowRunProperties,
  makeSelectFlow,
  selectHasFlow,
  selectFlowDefinition,
  selectPrimaryPipeline,
  selectFlowNodes,
  makeSelectFlowName,
} from '@/selectors/flowSelectors';
import type { RootState } from '@/store';
import { flowRowFixture, flowFixture } from '../../mocks/fixtures/flow.fixture';

function buildState(overrides: Partial<RootState['flow']> = {}): RootState {
  return {
    flow: {
      items: {},
      currentFlow: null,
      flowRunProperties: {
        enableIncrementalProcessing: false,
        retainRecordsForDeletedDocuments: false,
        validateFlow: true,
        enableNodeOutputPreview: false,
        intermediateDataStorage: 'container',
      },
      loading: false,
      error: null,
      ...overrides,
    },
  } as unknown as RootState;
}

describe('flowSelectors', () => {
  it('selectFlows returns state.flow.items', () => {
    const state = buildState({ items: { 'f-1': flowRowFixture } });
    expect(selectFlows(state)).toEqual({ 'f-1': flowRowFixture });
  });

  it('selectCurrentFlow returns currentFlow', () => {
    const state = buildState({ currentFlow: flowFixture });
    expect(selectCurrentFlow(state)).toEqual(flowFixture);
  });

  it('selectFlowsArray returns array of flow rows', () => {
    const state = buildState({ items: { 'f-1': flowRowFixture } });
    expect(selectFlowsArray(state)).toEqual([flowRowFixture]);
  });

  it('selectFlowsArray is memoized — same reference on equal input', () => {
    const state = buildState({ items: { 'f-1': flowRowFixture } });
    const first = selectFlowsArray(state);
    const second = selectFlowsArray(state);
    expect(first).toBe(second);
  });

  it('selectFlowCount returns count of keys', () => {
    const state = buildState({ items: { 'f-1': flowRowFixture, 'f-2': { ...flowRowFixture, flow_id: 'f-2' } } });
    expect(selectFlowCount(state)).toBe(2);
  });

  it('selectFlowLoading returns loading flag', () => {
    expect(selectFlowLoading(buildState({ loading: true }))).toBe(true);
    expect(selectFlowLoading(buildState({ loading: false }))).toBe(false);
  });

  it('selectFlowError returns error', () => {
    expect(selectFlowError(buildState({ error: 'oops' }))).toBe('oops');
    expect(selectFlowError(buildState({ error: null }))).toBeNull();
  });

  it('selectFlowRunProperties returns flowRunProperties', () => {
    const props = selectFlowRunProperties(buildState());
    expect(props).toBeDefined();
    expect(props.validateFlow).toBe(true);
  });

  it('makeSelectFlow returns FlowRow for known id', () => {
    const state = buildState({ items: { 'f-1': flowRowFixture } });
    const selector = makeSelectFlow('f-1');
    expect(selector(state)).toEqual(flowRowFixture);
  });

  it('makeSelectFlow returns null for unknown id', () => {
    const state = buildState({ items: {} });
    const selector = makeSelectFlow('unknown');
    expect(selector(state)).toBeNull();
  });

  it('makeSelectFlow returns null when id is null', () => {
    const state = buildState({ items: { 'f-1': flowRowFixture } });
    expect(makeSelectFlow(null)(state)).toBeNull();
  });

  it('selectHasFlow returns false when currentFlow is null', () => {
    expect(selectHasFlow(buildState({ currentFlow: null }))).toBe(false);
  });

  it('selectHasFlow returns true when currentFlow is set', () => {
    expect(selectHasFlow(buildState({ currentFlow: flowFixture }))).toBe(true);
  });

  it('selectFlowDefinition returns null when currentFlow is null', () => {
    expect(selectFlowDefinition(buildState({ currentFlow: null }))).toBeNull();
  });

  it('selectFlowDefinition returns definition from currentFlow', () => {
    const def = { pipelines: [], primary_pipeline: 'p-1' };
    const flow = { ...flowFixture, definition: def };
    expect(selectFlowDefinition(buildState({ currentFlow: flow as any }))).toEqual(def);
  });

  it('selectPrimaryPipeline returns null when no currentFlow', () => {
    expect(selectPrimaryPipeline(buildState({ currentFlow: null }))).toBeNull();
  });

  it('selectPrimaryPipeline returns null when pipelines array is empty', () => {
    const flow = { ...flowFixture, definition: { pipelines: [], primary_pipeline: 'p-1' } };
    expect(selectPrimaryPipeline(buildState({ currentFlow: flow as any }))).toBeNull();
  });

  it('selectPrimaryPipeline returns the matching pipeline', () => {
    const pipeline = { id: 'p-1', nodes: [] };
    const flow = { ...flowFixture, definition: { pipelines: [pipeline], primary_pipeline: 'p-1' } };
    expect(selectPrimaryPipeline(buildState({ currentFlow: flow as any }))).toEqual(pipeline);
  });

  it('selectFlowNodes returns empty array when pipeline is null', () => {
    expect(selectFlowNodes(buildState({ currentFlow: null }))).toEqual([]);
  });

  it('selectFlowNodes returns nodes from primary pipeline', () => {
    const node1 = { id: 'n-1', type: 'execution_node' };
    const pipeline = { id: 'p-1', nodes: [node1] };
    const flow = { ...flowFixture, definition: { pipelines: [pipeline], primary_pipeline: 'p-1' } };
    expect(selectFlowNodes(buildState({ currentFlow: flow as any }))).toEqual([node1]);
  });

  it('makeSelectFlowName returns null when id is null', () => {
    const state = buildState({ items: { 'f-1': flowRowFixture } });
    expect(makeSelectFlowName(null)(state)).toBeNull();
  });

  it('makeSelectFlowName returns null when flow is not in store', () => {
    const state = buildState({ items: {} });
    expect(makeSelectFlowName('missing')(state)).toBeNull();
  });

  it('makeSelectFlowName returns the flow name when found', () => {
    const state = buildState({ items: { 'f-1': flowRowFixture } });
    expect(makeSelectFlowName('f-1')(state)).toBe(flowRowFixture.name);
  });
});
