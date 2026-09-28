/**
 * @fileoverview Type-safe Redux selector hook for the Docling Pipelines application.
 * Provides a typed version of useSelector with RootState type.
 */

import { useSelector } from 'react-redux';
import type { RootState } from '@/store';

/**
 * Type-safe hook for selecting data from the Redux store.
 * Use this instead of the plain `useSelector` from react-redux for full type safety.
 *
 * @returns A selector function typed with RootState
 *
 * @example
 * ```tsx
 * import { useAppSelector } from '@/hooks';
 * import { selectCurrentFlow } from '@/selectors';
 *
 * function MyComponent() {
 *   // Using a selector function
 *   const currentFlow = useAppSelector(selectCurrentFlow);
 *
 *   // Using inline selector
 *   const loading = useAppSelector((state) => state.flow.loading);
 * }
 * ```
 */
export const useAppSelector = useSelector.withTypes<RootState>();
