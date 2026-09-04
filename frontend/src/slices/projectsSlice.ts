/**
 * @fileoverview Redux slice for managing projects state.
 * Owns the full lifecycle of project data: loading, error, CRUD operations.
 * Populated by the Projects BFF actions (`getProjects`, `getProject`,
 * `createProject`, `replaceProject`, `deleteProject`).
 */

import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { Project, ProjectsState } from '@/types';

const initialState: ProjectsState = {
  items: {},
  selectedProjectId: null,
  loading: false,
  error: null,
};

/**
 * Redux slice for projects state management.
 * Manages the {@link Project} domain model map, selection state, loading, and error.
 */
const projectsSlice = createSlice({
  name: 'projects',
  initialState,
  reducers: {
    /**
     * Replaces the entire projects map with {@link Project} domain models.
     * Clears `loading` and `error` on success.
     * @param state  - Current projects state.
     * @param action - Action containing a `Record<id, Project>` map.
     */
    setProjects: (state, action: PayloadAction<Record<string, Project>>) => {
      state.items = action.payload;
      state.loading = false;
      state.error = null;
    },
    /**
     * Inserts or updates a single {@link Project} domain model in the map.
     * Used after `createProject` and `replaceProject` API calls.
     * @param state  - Current projects state.
     * @param action - Action containing `{ projectId, project }`.
     */
    setProject: (state, action: PayloadAction<{ projectId: string; project: Project }>) => {
      state.items[action.payload.projectId] = action.payload.project;
    },
    /**
     * Removes a single project from the map by ID.
     * Dispatched after a successful `DELETE /api/projects/:id` call.
     * Also clears `selectedProjectId` if the deleted project was the selected one.
     * @param state  - Current projects state.
     * @param action - Action whose payload is the `project_id` string to remove.
     */
    removeProject: (state, action: PayloadAction<string>) => {
      delete state.items[action.payload];
      if (state.selectedProjectId === action.payload) {
        state.selectedProjectId = null;
      }
    },
    /**
     * Sets the currently selected project ID for navigation.
     * @param state  - Current projects state.
     * @param action - Action containing the project ID or null to deselect.
     */
    selectProject: (state, action: PayloadAction<string | null>) => {
      state.selectedProjectId = action.payload;
    },
    /**
     * Sets the loading flag for in-flight project API requests.
     * @param state  - Current projects state.
     * @param action - Action containing the loading boolean.
     */
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    /**
     * Sets a project-scoped error message and clears the loading flag.
     * @param state  - Current projects state.
     * @param action - Action containing the error message string, or null to clear.
     */
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
      state.loading = false;
    },
    /**
     * Clears any existing project-scoped error message.
     * @param state - Current projects state.
     */
    clearError: (state) => {
      state.error = null;
    },
  },
});

export const {
  setProjects,
  setProject,
  removeProject,
  selectProject,
  setLoading,
  setError,
  clearError,
} = projectsSlice.actions;

export default projectsSlice.reducer;
