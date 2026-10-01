import { describe, it, expect } from 'vitest';
import operatorsReducer, {
  setOperatorMetadata,
  setFeatureOptions,
  setNodeFeatures,
  setFeaturesLoading,
  setLoading,
  setError,
  clearError,
} from '@/slices/operatorsSlice';
import type { OperatorsState } from '@/types';

const initialState: OperatorsState = {
  metadata: {},
  featureOptions: {},
  nodeFeatures: {},
  loading: false,
  featuresLoading: false,
  error: null,
};

describe('operatorsSlice reducers', () => {
  it('initial state is correct', () => {
    const state = operatorsReducer(undefined, { type: '@@INIT' });
    expect(state).toEqual(initialState);
  });

  it('setOperatorMetadata populates metadata and clears loading/error', () => {
    const start = { ...initialState, loading: true, error: 'old' };
    const meta = { chunker: { label: 'Chunker', category: 'Functional', description: null, features: {}, required_features: [], attributes: {} } };
    const state = operatorsReducer(start, setOperatorMetadata(meta));
    expect(state.metadata).toEqual(meta);
    expect(state.loading).toBe(false);
    expect(state.error).toBeNull();
  });

  it('setFeatureOptions updates featureOptions', () => {
    const state = operatorsReducer(initialState, setFeatureOptions({ key: ['a', 'b'] }));
    expect(state.featureOptions).toEqual({ key: ['a', 'b'] });
  });

  it('setNodeFeatures stores node feature map', () => {
    const features = { 'node-1': { input_features: {}, output_features: {} } };
    const state = operatorsReducer(initialState, setNodeFeatures(features));
    expect(state.nodeFeatures).toEqual(features);
  });

  it('setFeaturesLoading updates featuresLoading', () => {
    const state = operatorsReducer(initialState, setFeaturesLoading(true));
    expect(state.featuresLoading).toBe(true);
  });

  it('setLoading updates loading flag', () => {
    const state = operatorsReducer(initialState, setLoading(true));
    expect(state.loading).toBe(true);
  });

  it('setError sets error and clears loading', () => {
    const start = { ...initialState, loading: true };
    const state = operatorsReducer(start, setError('Failed'));
    expect(state.error).toBe('Failed');
    expect(state.loading).toBe(false);
  });

  it('clearError sets error to null', () => {
    const start = { ...initialState, error: 'previous' };
    const state = operatorsReducer(start, clearError());
    expect(state.error).toBeNull();
  });
});
