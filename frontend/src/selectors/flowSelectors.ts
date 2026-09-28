/**
 * @fileoverview Selectors for accessing flow state from the Redux store.
 * All selectors read from `state.flow`, owned by `flowSlice`.
 *
 * - Items selectors — read from `state.flow.items` (the `FlowRow` map).
 * - Canvas selectors — read from `state.flow.currentFlow` (the full `Flow` object).
 */

import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@/store';
import type { FlowRow } from '@/types';

// ── Basic selectors ───────────────────────────────────────────────────────

/** Selects the entire flow state slice. */
export const selectFlowState = (state: RootState): RootState['flow'] => state.flow;

/** Selects the `items` map (`flow_id` → {@link FlowRow} display object). */
export const selectFlows = (state: RootState): Record<string, FlowRow> => state.flow.items;

/** Selects the loading flag — true while any flows request is in-flight. */
export const selectFlowLoading = (state: RootState): boolean => state.flow.loading;

/** Selects the error message from the last failed flows request, or null. */
export const selectFlowError = (state: RootState): string | null => state.flow.error;

/** Selects the full active flow object (with definition) used by Canvas. */
export const selectCurrentFlow = (state: RootState): RootState['flow']['currentFlow'] => state.flow.currentFlow;

/** Selects the flow run properties configuration. */
export const selectFlowRunProperties = (state: RootState): RootState['flow']['flowRunProperties'] => state.flow.flowRunProperties;

// ── Memoized selectors ────────────────────────────────────────────────────

/**
 * Returns all flow rows as an array.
 * Recomputes only when the `items` map reference changes.
 *
 * @returns Array of all cached {@link FlowRow} display objects.
 */
export const selectFlowsArray = createSelector(
  [selectFlows],
  (items): FlowRow[] => Object.values(items)
);

/**
 * Returns the total number of cached flow rows.
 *
 * @returns Count of flows in the store.
 */
export const selectFlowCount = createSelector(
  [selectFlows],
  (items) => Object.keys(items).length
);

/**
 * Checks if the full Canvas flow is currently loaded.
 *
 * @returns `true` if `currentFlow` is not null.
 */
export const selectHasFlow = createSelector(
  [selectCurrentFlow],
  (flow) => flow !== null
);

/**
 * Extracts the nested pipeline definition from the current Canvas flow.
 *
 * @returns The `FlowDefinition` object, or `null`.
 */
export const selectFlowDefinition = createSelector(
  [selectCurrentFlow],
  (flow) => flow?.definition ?? null
);

/**
 * Extracts the pipelines array from the Canvas flow definition.
 *
 * @returns Array of pipeline objects.
 */
export const selectFlowPipelines = createSelector(
  [selectFlowDefinition],
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Elyra pipeline shape is untyped
  (definition): any[] => definition?.pipelines ?? []
);

/**
 * Finds and returns the primary pipeline from the Canvas flow definition.
 *
 * @returns The primary pipeline object, or null.
 */
export const selectPrimaryPipeline = createSelector(
  [selectFlowDefinition, selectFlowPipelines],
  (definition, pipelines): unknown => {
    if (!definition?.primary_pipeline || !pipelines.length) { return null; }
    return (pipelines as Array<{ id: string }>).find((p) => p.id === (definition.primary_pipeline as string)) ?? null;
  }
);

/**
 * Extracts the operator nodes from the primary Canvas pipeline.
 *
 * @returns Array of operator node objects.
 */
export const selectFlowNodes = createSelector(
  [selectPrimaryPipeline],
  (pipeline): unknown[] => {
    const p = pipeline as { nodes?: unknown[] } | null;
    return p?.nodes ?? [];
  }
);

// ── Per-component selector factories ─────────────────────────────────────

/**
 * Returns a stable selector for a single flow row by ID.
 *
 * `useAppSelector` re-renders the component only when
 * `state.flow.items[flowId]` changes by reference, so unrelated flow mutations
 * do not cause unnecessary re-renders.
 *
 * @param flowId - The `flow_id` to read, or `null`/`undefined` to return `null`.
 * @returns A selector `(state: RootState) => FlowRow | null`.
 *
 * @example
 * ```tsx
 * const flowRow = useAppSelector(makeSelectFlow(flowId));
 * ```
 */
export const makeSelectFlow =
  (flowId: string | null | undefined) =>
  (state: RootState): FlowRow | null =>
    flowId ? (state.flow.items[flowId] ?? null) : null;

/**
 * Returns a stable selector that resolves a flow's human-readable name by its ID.
 *
 * Returns `null` when the flow is not yet in the store (e.g. before the first fetch).
 * Used by the Breadcrumb component to replace the raw `flow_id` URL segment with
 * the flow name once it is available.
 *
 * @param flowId - The `flow_id` to look up, or `null`/`undefined` to return `null`.
 * @returns A selector `(state: RootState) => string | null`.
 */
export const makeSelectFlowName =
  (flowId: string | null | undefined) =>
  (state: RootState): string | null =>
    flowId ? (state.flow.items[flowId]?.name ?? null) : null;
