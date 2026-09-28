/**
 * @fileoverview Redux slice for managing operators state.
 * Handles operator metadata, feature options, and configuration data.
 */

import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '@/store';
import type { NodeFeatureEntry, OperatorsState, OperatorMetadata } from '@/types';

const initialState: OperatorsState = {
  metadata: {},
  featureOptions: {},
  nodeFeatures: {},
  loading: false,
  featuresLoading: false,
  error: null,
};

/**
 * Redux slice for operators state management.
 * Manages operator metadata and available feature options.
 */
const operatorsSlice = createSlice({
  name: 'operators',
  initialState,
  reducers: {
    /**
     * Sets the complete operators metadata map.
     * Clears loading and error states on success.
     * @param state - Current operators state
     * @param action - Action containing the metadata map
     */
    setOperatorMetadata: (state, action: PayloadAction<Record<string, OperatorMetadata>>) => {
      state.metadata = action.payload;
      state.loading = false;
      state.error = null;
    },
    /**
     * Sets the available feature options for operator configuration.
     * @param state - Current operators state
     * @param action - Action containing the feature options map
     */
    setFeatureOptions: (state, action: PayloadAction<Record<string, any>>) => {
      state.featureOptions = action.payload;
    },
    /**
     * Stores enriched feature metadata keyed by node ID.
     * Each entry contains input_features and output_features for that node.
     * @param state - Current operators state
     * @param action - Action containing the full enriched pipeline flow (backend response)
     */
    setNodeFeatures: (state, action: PayloadAction<Record<string, NodeFeatureEntry>>) => {
      state.nodeFeatures = action.payload;
    },
    /**
     * Sets loading state specifically for feature enrichment API calls.
     */
    setFeaturesLoading: (state, action: PayloadAction<boolean>) => {
      state.featuresLoading = action.payload;
    },
    /**
     * Sets the loading state for async operations.
     * @param state - Current operators state
     * @param action - Action containing the loading boolean
     */
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    /**
     * Sets an error message and clears loading state.
     * @param state - Current operators state
     * @param action - Action containing the error message or null
     */
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
      state.loading = false;
    },
    /**
     * Clears the current error message.
     * @param state - Current operators state
     */
    clearError: (state) => {
      state.error = null;
    },
  },
});

export const {
  setOperatorMetadata,
  setFeatureOptions,
  setNodeFeatures,
  setFeaturesLoading,
  setLoading,
  setError,
  clearError,
} = operatorsSlice.actions;

export default operatorsSlice.reducer;

// Selectors
const path = (state: RootState) => state.operators;
export const getOperatorMetadata = (state: RootState) => path(state).metadata;
export const getOperatorsLoading = (state: RootState) => path(state).loading;
export const getOperatorsError = (state: RootState) => path(state).error;
export const getNodeFeatures = (state: RootState) => path(state).nodeFeatures ?? {};
export const getFeaturesLoading = (state: RootState) => path(state).featuresLoading ?? false;

/**
 * Returns the input_features and output_features for a specific node ID.
 * Each feature entry has: name, type, description, node_id (source node), tags, etc.
 */
export const getNodeFeaturesForNode = (state: RootState, nodeId: string) =>
  path(state).nodeFeatures?.[nodeId] ?? { input_features: {}, output_features: {} };
