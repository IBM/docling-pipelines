import { describe, it, expect } from 'vitest';
import { fromResponse, toCreateRequest, toUpdateRequest } from '@/services/api/mappers/project-mapper';
import type { ProjectResponse } from '@/types';

const projectResponse: ProjectResponse = {
  project_id: 'p-1',
  name: 'Test Project',
  description: 'A test project',
  tags: ['tag1', 'tag2'],
  flow_count: 3,
  created_on: '2024-01-10T09:00:00Z',
  modified_on: '2024-01-20T12:00:00Z',
  created_by: 'alice',
  modified_by: 'bob',
  href: '/api/v1/projects/p-1',
};

describe('fromResponse', () => {
  it('maps all API wire fields to camelCase domain model', () => {
    const project = fromResponse(projectResponse);
    expect(project.id).toBe('p-1');
    expect(project.name).toBe('Test Project');
    expect(project.description).toBe('A test project');
    expect(project.tags).toEqual(['tag1', 'tag2']);
    expect(project.flowCount).toBe(3);
    expect(project.createdOn).toBe('2024-01-10T09:00:00Z');
    expect(project.modifiedOn).toBe('2024-01-20T12:00:00Z');
    expect(project.createdBy).toBe('alice');
    expect(project.modifiedBy).toBe('bob');
  });

  it('passes null description through', () => {
    const project = fromResponse({ ...projectResponse, description: null });
    expect(project.description).toBeNull();
  });
});

describe('toCreateRequest', () => {
  it('maps form values to API request body', () => {
    const result = toCreateRequest({ name: 'New Project', description: 'Desc', tags: ['a'] });
    expect(result.name).toBe('New Project');
    expect(result.description).toBe('Desc');
    expect(result.tags).toEqual(['a']);
  });

  it('empty description → null in request body', () => {
    const result = toCreateRequest({ name: 'P', description: '', tags: [] });
    expect(result.description).toBeNull();
  });
});

describe('toUpdateRequest', () => {
  it('maps update shape to API body', () => {
    const result = toUpdateRequest({ name: 'Updated', description: 'New', tags: ['x'] });
    expect(result.name).toBe('Updated');
    expect(result.description).toBe('New');
    expect(result.tags).toEqual(['x']);
  });

  it('empty description → null', () => {
    const result = toUpdateRequest({ name: 'P', description: '', tags: [] });
    expect(result.description).toBeNull();
  });
});
