/**
 * @fileoverview Selectors for accessing operators state from Redux store.
 * Provides both basic and memoized selectors for efficient state access.
 */

// TODO: Update with API implementation
import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@/store';

// Basic selectors

/** Selects the entire operators state slice */
export const selectOperatorsState = (state: RootState) => state.operators;

/** Selects the operators metadata dictionary */
export const selectOperatorsMetadata = (state: RootState) => state.operators.metadata;

/** Selects the loading state for operators operations */
export const selectOperatorsLoading = (state: RootState) => state.operators.loading;

/** Selects the error message for operators operations */
export const selectOperatorsError = (state: RootState) => state.operators.error;

/** Selects the feature options configuration */
export const selectFeatureOptions = (state: RootState) => state.operators.featureOptions;

// Memoized selectors for derived state

/**
 * Groups operators by their category.
 * Operators without a category are placed in 'uncategorized'.
 * @returns Dictionary mapping category names to arrays of operators
 * @example
 * {
 *   'extract': [{ key: 'extract_op', category: 'extract', ... }],
 *   'ingest': [{ key: 'ingest_op', category: 'ingest', ... }]
 * }
 */
export const selectOperatorsByCategory = createSelector(
  [selectOperatorsMetadata],
  (metadata) => {
    const byCategory: Record<string, any[]> = {};
    Object.entries(metadata).forEach(([key, operator]) => {
      const category = operator.category ?? 'uncategorized';
      byCategory[category] ??= [];
      byCategory[category].push({ key, ...operator });
    });
    return byCategory;
  }
);

/**
 * Counts the total number of operators in metadata.
 * @returns The number of operators
 */
export const selectOperatorCount = createSelector(
  [selectOperatorsMetadata],
  (metadata) => Object.keys(metadata).length
);
