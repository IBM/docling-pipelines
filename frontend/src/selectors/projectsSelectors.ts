/**
 * @fileoverview Selectors for accessing projects state from the Redux store.
 * All selectors read from `state.projects`, owned by `projectsSlice`.
 */

import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@/store';
import type { Project } from '@/types';
import { slugify } from '@/lib/helpers';

// ── Basic selectors ───────────────────────────────────────────────────────

/** Selects the entire projects state slice. */
export const selectProjectsState = (state: RootState) => state.projects;

/** Selects the `items` map (`project.id` → {@link Project} domain model). */
export const selectProjects = (state: RootState) => state.projects.items;

/** Selects the currently selected project ID, or null if none selected. */
export const selectSelectedProjectId = (state: RootState) => state.projects.selectedProjectId;

/** Selects the loading flag — true while any projects request is in-flight. */
export const selectProjectsLoading = (state: RootState) => state.projects.loading;

/** Selects the error message from the last failed projects request, or null. */
export const selectProjectsError = (state: RootState) => state.projects.error;

// ── Memoized selectors ────────────────────────────────────────────────────

/**
 * Returns all projects as an array.
 * Recomputes only when the `items` map reference changes.
 *
 * @returns Array of all cached {@link Project} domain objects.
 */
export const selectProjectsArray = createSelector(
  [selectProjects],
  (items): Project[] => Object.values(items)
);

/**
 * Returns the currently selected project object, or null if none selected.
 *
 * @returns The selected {@link Project}, or null.
 */
export const selectSelectedProject = createSelector(
  [selectProjects, selectSelectedProjectId],
  (items, selectedId): Project | null =>
    selectedId ? (items[selectedId] ?? null) : null
);

/**
 * Returns true if any project is currently selected.
 *
 * @returns Boolean selection flag.
 */
export const selectHasSelectedProject = createSelector(
  [selectSelectedProjectId],
  (selectedId) => selectedId !== null
);

/**
 * Returns the total number of cached projects.
 *
 * @returns Count of projects in the store.
 */
export const selectProjectCount = createSelector(
  [selectProjects],
  (items) => Object.keys(items).length
);

/**
 * Factory selector — returns a lookup function for retrieving any project by ID.
 * Useful when you need to look up **multiple IDs in one render pass**.
 *
 * **Memoisation caveat:** `createSelector` caches the inner function keyed on the
 * `items` map reference — not per project ID. Any change to the map (add, update,
 * delete of any project) returns a new inner function and re-renders all subscribers.
 * For single-project reads in a component, use an inline selector or a plain factory
 * instead, so the component only re-renders when its specific project changes.
 *
 * @returns A `(projectId: string) => Project | null` lookup function.
 *
 * @example
 * ```tsx
 * const getProject = useAppSelector(selectProjectById);
 * const alpha = getProject('id-alpha');
 * const beta  = getProject('id-beta');
 * ```
 */
export const selectProjectById = createSelector(
  [selectProjects],
  (items) =>
    (projectId: string): Project | null =>
      items[projectId] ?? null
);

// ── Per-component selector factories ─────────────────────────────────────

/**
 * Returns a stable selector for a single project by ID.
 *
 * Unlike {@link selectProjectById}, this is a plain selector factory — not
 * wrapped in `createSelector`. `useAppSelector` re-renders the component only
 * when `state.projects.items[projectId]` changes by reference, so unrelated
 * project mutations (other users' projects being added/updated) are ignored.
 *
 * No `useMemo` wrapper is needed at the call site: `projectId` is a URL param
 * (string primitive) that React Router returns as the same value each render
 * unless the URL itself changes.
 *
 * @param projectId - The project ID to read, or `null`/`undefined` to return `null`.
 * @returns A selector `(state: RootState) => Project | null`.
 *
 * @example
 * ```tsx
 * const project = useAppSelector(makeSelectProject(projectId));
 * ```
 */
export const makeSelectProject =
  (projectId: string | null | undefined) =>
  (state: RootState): Project | null =>
    projectId ? (state.projects.items[projectId] ?? null) : null;

/**
 * Returns a stable selector that checks whether a specific project is cached.
 *
 * Re-renders the component only when the cached/not-cached status of that
 * specific project changes — unrelated project mutations are ignored.
 *
 * @param projectId - The project ID to check, or `null`/`undefined` to return `false`.
 * @returns A selector `(state: RootState) => boolean`.
 *
 * @example
 * ```tsx
 * const isCached = useAppSelector(makeSelectIsProjectCached(projectId));
 * ```
 */
export const makeSelectIsProjectCached =
  (projectId: string | null | undefined) =>
  (state: RootState): boolean =>
    projectId ? projectId in state.projects.items : false;

/**
 * Returns a stable selector that finds a project by its slugified name.
 *
 * Used by {@link ProjectDetail} which receives a name slug from the URL
 * (e.g. `"my-project"`) rather than a UUID. The store is keyed by UUID,
 * so we scan `items` for the first entry whose slugified name matches.
 *
 * @param slug - The slugified project name from the URL param.
 * @returns A selector `(state: RootState) => Project | null`.
 */
export const makeSelectProjectBySlug =
  (slug: string | null | undefined) =>
  (state: RootState): Project | null => {
    if (!slug) { return null; }
    return Object.values(state.projects.items).find((p) => slugify(p.name) === slug) ?? null;
  };
