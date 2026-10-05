/**
 * @fileoverview Redux slice for managing flows state.
 * Owns the full lifecycle of flow data: loading, error, CRUD operations.
 *
 * - `items` — map of `flow_id → FlowRow` for table display (ProjectDetail, FlowDetail).
 * - `currentFlow` — the full `Flow` object (with `definition`) used by Canvas.
 * - `flowRunProperties` — Canvas run-time settings.
 */

import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit';
import type { FlowState, Flow, FlowRunProperties, FlowRow } from '@/types';
import { getFlow as apiGetFlow, updateFlow as apiUpdateFlow, createFlow as apiCreateFlow } from '@/services/api';
import { fromResponse } from '@/services/api/mappers/flow-mapper';

const initialState: FlowState = {
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
};

/**
 * Fetches a flow by ID and stores it as `currentFlow` in Redux.
 * Called by Canvas on mount when a flow_id is present in the URL.
 */
export const fetchFlow = createAsyncThunk<Flow, string>(
  'flow/fetchFlow',
  async (flowId, { rejectWithValue }) => {
    try {
      const response = await apiGetFlow(flowId);
      return response.data;
    } catch (error: unknown) {
      const e = error as { response?: { data?: { detail?: string } }; message?: string };
      return rejectWithValue(e?.response?.data?.detail ?? e?.message ?? 'Failed to fetch flow');
    }
  }
);

/**
 * Saves the current canvas state back to the backend.
 * PUT when the flow already has a flow_id; POST otherwise.
 * On success the backend's `definition` is intentionally ignored —
 * only metadata fields (modified_on, flow_version, etc.) are merged
 * so canvas node positions are never reset.
 */
export const saveFlow = createAsyncThunk<Flow, Flow>(
  'flow/saveFlow',
  async (flowData, { rejectWithValue }) => {
    try {
      const response = flowData.flow_id
        ? await apiUpdateFlow(flowData.flow_id, flowData)
        : await apiCreateFlow(flowData);
      // Merge backend response (updated metadata: flow_id, modified_on, etc.) with the
      // definition we sent. The backend may omit definition or return it empty — always
      // keep the sent definition so Canvas nodes are never lost after save.
      return { ...flowData, ...response.data, definition: flowData.definition };
    } catch (error: unknown) {
      const e = error as { response?: { data?: { detail?: string } }; message?: string };
      return rejectWithValue(e?.response?.data?.detail ?? e?.message ?? 'Failed to save flow');
    }
  }
);

const flowSlice = createSlice({
  name: 'flow',
  initialState,
  reducers: {
    /**
     * Replaces the entire flows map with `FlowRow` display objects.
     * Only updates data — does not touch `loading` or `error`.
     * The caller is responsible for dispatching `setLoading(false)` in `.finally()`.
     * @param state  - Current flow state.
     * @param action - Action containing a `Record<flow_id, FlowRow>` map.
     */
    setFlows: (state, action: PayloadAction<Record<string, FlowRow>>) => {
      state.items = action.payload;
    },
    /**
     * Inserts or updates a single `FlowRow` in the items map.
     * Used after `createFlow`, `patchFlow`, and `getFlow` API calls.
     * @param state  - Current flow state.
     * @param action - Action containing `{ flowId, flow }`.
     */
    setFlow: (state, action: PayloadAction<{ flowId: string; flow: FlowRow }>) => {
      state.items[action.payload.flowId] = action.payload.flow;
    },
    /**
     * Updates specific fields of an existing `FlowRow` in the items map.
     * Used for optimistic local updates after PATCH without a full re-fetch.
     * No-ops silently if `flowId` is not in the map.
     * @param state  - Current flow state.
     * @param action - Action containing `{ flowId, updates }`.
     */
    updateFlow: (state, action: PayloadAction<{ flowId: string; updates: Partial<FlowRow> }>) => {
      const existing = state.items[action.payload.flowId];
      if (existing) {
        state.items[action.payload.flowId] = { ...existing, ...action.payload.updates };
      }
    },
    /**
     * Removes a single flow from the items map by ID.
     * Dispatched after a successful `DELETE /api/flows/:id` call.
     * @param state  - Current flow state.
     * @param action - Action whose payload is the `flow_id` string to remove.
     */
    removeFlow: (state, action: PayloadAction<string>) => {
      delete state.items[action.payload];
    },
    /**
     * Sets the full active flow object (with `definition`) for Canvas.
     * Only updates data — does not touch `loading` or `error`.
     * The caller is responsible for dispatching `setLoading(false)` in `.finally()`.
     * @param state  - Current flow state.
     * @param action - Action containing the full `Flow` object or null.
     */
    setCurrentFlow: (state, action: PayloadAction<Flow | null>) => {
      state.currentFlow = action.payload;
    },
    /**
     * Clears the current full flow object.
     * @param state - Current flow state.
     */
    clearFlow: (state) => {
      state.currentFlow = null;
    },
    /**
     * Sets the loading flag for in-flight flow API requests.
     * @param state  - Current flow state.
     * @param action - Action containing the loading boolean.
     */
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    /**
     * Sets a flow-scoped error message and clears the loading flag.
     * @param state  - Current flow state.
     * @param action - Action containing the error message string, or null to clear.
     */
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
      state.loading = false;
    },
    /**
     * Clears any existing flow-scoped error message.
     * @param state - Current flow state.
     */
    clearError: (state) => {
      state.error = null;
    },
    /**
     * Replaces all flow run properties.
     * @param state  - Current flow state.
     * @param action - Action containing the full `FlowRunProperties` object.
     */
    setFlowRunProperties: (state, action: PayloadAction<FlowRunProperties>) => {
      state.flowRunProperties = action.payload;
    },
    /**
     * Updates a single flow run property by key.
     * @param state  - Current flow state.
     * @param action - Action containing `{ key, value }`.
     */
    updateFlowRunProperty: (
      state,
      action: PayloadAction<{ key: keyof FlowRunProperties; value: FlowRunProperties[keyof FlowRunProperties] }>
    ) => {
      const { key, value } = action.payload;
      // Immer requires a direct cast when the key type is generic.
      (state.flowRunProperties as Record<keyof FlowRunProperties, unknown>)[key] = value;
    },
    /**
     * Resets flow run properties to their default values.
     * @param state - Current flow state.
     */
    resetFlowRunProperties: (state) => {
      state.flowRunProperties = initialState.flowRunProperties;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchFlow.pending, (state) => {
        // Do NOT touch state.loading — Canvas uses local isLoading state for the
        // fetch guard. Flipping state.loading here unmounts ElyraCanvas via the
        // flowLoading guard, which remounts Canvas, re-fires the fetch effect,
        // and creates an infinite request loop.
        state.error = null;
      })
      .addCase(fetchFlow.fulfilled, (state, action) => {
        state.currentFlow = action.payload;
        // Also populate items so makeSelectFlowName() resolves the name
        // in the breadcrumb without requiring a separate list fetch.
        if (action.payload.flow_id) {
          state.items[action.payload.flow_id] = fromResponse(action.payload);
        }
        state.error = null;
      })
      .addCase(fetchFlow.rejected, (state, action) => {
        state.error = (action.payload as string) ?? 'Unknown error';
      })
      .addCase(saveFlow.pending, (state) => {
        // Do NOT touch state.loading — that flag gates the Canvas loading spinner
        // which would unmount ElyraCanvas and wipe the controller. Save has its own
        // local isSaving state in Canvas.tsx.
        state.error = null;
      })
      .addCase(saveFlow.fulfilled, (state, action) => {
        // The thunk always returns { ...sentFlow, ...backendMeta, definition: sentDefinition }
        // so action.payload has the correct definition + up-to-date metadata (flow_id,
        // modified_on, flow_version, etc.). Safe to replace currentFlow in full.
        state.currentFlow = action.payload;
        state.error = null;
      })
      .addCase(saveFlow.rejected, (state, action) => {
        state.error = (action.payload as string) ?? 'Unknown error';
      });
  },
});

export const {
  setFlows,
  setFlow,
  updateFlow,
  removeFlow,
  setCurrentFlow,
  clearFlow,
  setLoading,
  setError,
  clearError,
  setFlowRunProperties,
  updateFlowRunProperty,
  resetFlowRunProperties,
} = flowSlice.actions;

export default flowSlice.reducer;
