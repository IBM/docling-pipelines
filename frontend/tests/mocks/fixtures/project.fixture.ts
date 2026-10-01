import type { Project, ProjectResponse, PaginatedProjectResponse } from '@/types';

export const projectResponseFixture: ProjectResponse = {
  project_id: 'project-1',
  name: 'Test Project',
  description: 'A project used in tests',
  tags: ['test'],
  flow_count: 2,
  created_on: '2024-01-10T09:00:00Z',
  modified_on: '2024-01-20T12:00:00Z',
  created_by: 'test-user',
  modified_by: 'test-user',
  href: '/api/v1/projects/project-1',
};

export const projectFixture: ProjectResponse = projectResponseFixture;

export const projectDomainFixture: Project = {
  id: 'project-1',
  name: 'Test Project',
  description: 'A project used in tests',
  tags: ['test'],
  flowCount: 2,
  createdOn: '2024-01-10T09:00:00Z',
  modifiedOn: '2024-01-20T12:00:00Z',
  createdBy: 'test-user',
  modifiedBy: 'test-user',
};

export const paginatedProjectResponseFixture: PaginatedProjectResponse = {
  projects: [projectResponseFixture],
  total_count: 1,
  offset: 0,
  limit: 20,
  first: '/api/v1/projects?offset=0',
  next: null,
  prev: null,
};
