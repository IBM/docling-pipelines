import { describe, it, expect } from 'vitest';
import {
  selectProjects,
  selectProjectsArray,
  selectProjectCount,
  selectProjectsLoading,
  selectProjectsError,
  selectSelectedProjectId,
  makeSelectProject,
  selectProjectsState,
  selectSelectedProject,
  selectHasSelectedProject,
  selectProjectById,
  makeSelectIsProjectCached,
  makeSelectProjectBySlug,
} from '@/selectors/projectsSelectors';
import type { RootState } from '@/store';
import { projectDomainFixture } from '../../mocks/fixtures/project.fixture';

function buildState(overrides: Partial<RootState['projects']> = {}): RootState {
  return {
    projects: {
      items: {},
      selectedProjectId: null,
      loading: false,
      error: null,
      ...overrides,
    },
  } as unknown as RootState;
}

describe('projectsSelectors', () => {
  // ── existing tests (kept) ────────────────────────────────────────────────

  it('selectProjects returns items map', () => {
    const state = buildState({ items: { 'p-1': projectDomainFixture } });
    expect(selectProjects(state)).toEqual({ 'p-1': projectDomainFixture });
  });

  it('selectProjectsArray returns array of projects', () => {
    const state = buildState({ items: { 'p-1': projectDomainFixture } });
    expect(selectProjectsArray(state)).toEqual([projectDomainFixture]);
  });

  it('selectProjectCount returns count of keys', () => {
    const state = buildState({ items: { 'p-1': projectDomainFixture, 'p-2': { ...projectDomainFixture, id: 'p-2' } } });
    expect(selectProjectCount(state)).toBe(2);
  });

  it('selectProjectsLoading returns loading flag', () => {
    expect(selectProjectsLoading(buildState({ loading: true }))).toBe(true);
  });

  it('selectProjectsError returns error', () => {
    expect(selectProjectsError(buildState({ error: 'fail' }))).toBe('fail');
    expect(selectProjectsError(buildState({ error: null }))).toBeNull();
  });

  it('selectSelectedProjectId returns selectedProjectId', () => {
    expect(selectSelectedProjectId(buildState({ selectedProjectId: 'p-1' }))).toBe('p-1');
    expect(selectSelectedProjectId(buildState())).toBeNull();
  });

  it('makeSelectProject returns project for known id', () => {
    const state = buildState({ items: { 'p-1': projectDomainFixture } });
    expect(makeSelectProject('p-1')(state)).toEqual(projectDomainFixture);
  });

  it('makeSelectProject returns null for unknown id', () => {
    expect(makeSelectProject('unknown')(buildState())).toBeNull();
  });

  it('makeSelectProject returns null for null id', () => {
    expect(makeSelectProject(null)(buildState())).toBeNull();
  });

  // ── new tests ────────────────────────────────────────────────────────────

  it('selectProjectsState returns the full projects slice', () => {
    const state = buildState({ items: { 'p-1': projectDomainFixture }, loading: true });
    const slice = selectProjectsState(state);
    expect(slice.items).toEqual({ 'p-1': projectDomainFixture });
    expect(slice.loading).toBe(true);
  });

  it('selectSelectedProject returns the selected project', () => {
    const state = buildState({
      items: { 'p-1': projectDomainFixture },
      selectedProjectId: 'p-1',
    });
    expect(selectSelectedProject(state)).toEqual(projectDomainFixture);
  });

  it('selectSelectedProject returns null when no project is selected', () => {
    const state = buildState({ items: { 'p-1': projectDomainFixture } });
    expect(selectSelectedProject(state)).toBeNull();
  });

  it('selectHasSelectedProject is true when a project is selected', () => {
    expect(selectHasSelectedProject(buildState({ selectedProjectId: 'p-1' }))).toBe(true);
  });

  it('selectHasSelectedProject is false when no project is selected', () => {
    expect(selectHasSelectedProject(buildState())).toBe(false);
  });

  it('selectProjectById factory returns project for known id', () => {
    const state = buildState({ items: { 'p-1': projectDomainFixture } });
    expect(selectProjectById(state)('p-1')).toEqual(projectDomainFixture);
  });

  it('selectProjectById factory returns null for unknown id', () => {
    expect(selectProjectById(buildState())('no-such-id')).toBeNull();
  });

  it('makeSelectIsProjectCached returns true for cached project', () => {
    const state = buildState({ items: { 'p-1': projectDomainFixture } });
    expect(makeSelectIsProjectCached('p-1')(state)).toBe(true);
  });

  it('makeSelectIsProjectCached returns false for uncached project', () => {
    expect(makeSelectIsProjectCached('unknown')(buildState())).toBe(false);
  });

  it('makeSelectIsProjectCached returns false for null id', () => {
    expect(makeSelectIsProjectCached(null)(buildState())).toBe(false);
  });

  it('makeSelectProjectBySlug returns project matching slugified name', () => {
    const project = { ...projectDomainFixture, name: 'OSS UI Project' };
    const state = buildState({ items: { 'p-1': project } });
    expect(makeSelectProjectBySlug('oss-ui-project')(state)).toEqual(project);
  });

  it('makeSelectProjectBySlug returns null when no project matches slug', () => {
    const state = buildState({ items: { 'p-1': projectDomainFixture } });
    expect(makeSelectProjectBySlug('no-match')(state)).toBeNull();
  });

  it('makeSelectProjectBySlug returns null for null slug', () => {
    expect(makeSelectProjectBySlug(null)(buildState())).toBeNull();
  });
});
