import { describe, it, expect } from 'vitest';
import projectsReducer, {
  setProjects,
  setProject,
  removeProject,
  selectProject,
  setLoading,
  setError,
  clearError,
} from '@/slices/projectsSlice';
import type { ProjectsState, Project } from '@/types';

const initialState: ProjectsState = {
  items: {},
  selectedProjectId: null,
  loading: false,
  error: null,
};

const project: Project = {
  id: 'p-1',
  name: 'Test Project',
  description: null,
  tags: [],
  flowCount: 0,
  createdOn: '2024-01-01T00:00:00Z',
  modifiedOn: '2024-01-01T00:00:00Z',
  createdBy: null,
  modifiedBy: null,
};

describe('projectsSlice reducers', () => {
  it('initial state is correct', () => {
    const state = projectsReducer(undefined, { type: '@@INIT' });
    expect(state).toEqual(initialState);
  });

  it('setProjects replaces items and clears loading and error', () => {
    const start = { ...initialState, loading: true, error: 'old error' };
    const state = projectsReducer(start, setProjects({ 'p-1': project }));
    expect(state.items['p-1']).toEqual(project);
    expect(state.loading).toBe(false);
    expect(state.error).toBeNull();
  });

  it('setProject inserts or updates a single project', () => {
    const state = projectsReducer(initialState, setProject({ projectId: 'p-1', project }));
    expect(state.items['p-1']).toEqual(project);
  });

  it('removeProject removes by id', () => {
    const start = { ...initialState, items: { 'p-1': project } };
    const state = projectsReducer(start, removeProject('p-1'));
    expect(state.items['p-1']).toBeUndefined();
  });

  it('removeProject clears selectedProjectId if it matches the removed id', () => {
    const start = { ...initialState, items: { 'p-1': project }, selectedProjectId: 'p-1' };
    const state = projectsReducer(start, removeProject('p-1'));
    expect(state.selectedProjectId).toBeNull();
  });

  it('selectProject updates selectedProjectId', () => {
    const state = projectsReducer(initialState, selectProject('p-1'));
    expect(state.selectedProjectId).toBe('p-1');
  });

  it('setLoading updates loading flag', () => {
    const state = projectsReducer(initialState, setLoading(true));
    expect(state.loading).toBe(true);
  });

  it('setError sets error and clears loading', () => {
    const start = { ...initialState, loading: true };
    const state = projectsReducer(start, setError('Failed'));
    expect(state.error).toBe('Failed');
    expect(state.loading).toBe(false);
  });

  it('clearError sets error to null', () => {
    const start = { ...initialState, error: 'previous' };
    const state = projectsReducer(start, clearError());
    expect(state.error).toBeNull();
  });
});
