/**
 * @fileoverview Type-safe Redux dispatch hook.
 * Provides a typed version of useDispatch for use throughout the application.
 */

import { useDispatch } from 'react-redux';
import type { AppDispatch } from '@/store';

/**
 * Type-safe version of useDispatch hook.
 * Use this instead of plain useDispatch to get proper TypeScript support for thunks.
 *
 * @example
 * const dispatch = useAppDispatch();
 * dispatch(fetchOperatorsMetadata());
 */
export const useAppDispatch = (): AppDispatch => useDispatch<AppDispatch>();
