import { describe, it, expect } from 'vitest';
import { server } from '../../../../mocks/server';
import { http, HttpResponse } from 'msw';
import {
  createProject,
  getProjects,
  getProject,
  replaceProject,
  deleteProject,
} from '@/services/api/actions/project-actions';

describe('project-actions', () => {
  describe('createProject', () => {
    it('happy path: returns created project', async () => {
      const res = await createProject({ name: 'New Project', tags: [] });
      expect(res.status).toBe(201);
      expect(res.data.project_id).toBeDefined();
    });

    it('throws on network error', async () => {
      server.use(
        http.post('/api/projects', () => HttpResponse.error())
      );
      await expect(createProject({ name: 'X' })).rejects.toThrow();
    });

    it('throws on 4xx', async () => {
      server.use(
        http.post('/api/projects', () =>
          HttpResponse.json({ detail: 'Conflict' }, { status: 409 })
        )
      );
      await expect(createProject({ name: 'X' })).rejects.toBeDefined();
    });
  });

  describe('getProjects', () => {
    it('happy path: returns paginated projects', async () => {
      const res = await getProjects();
      expect(res.data.projects).toBeDefined();
    });
  });

  describe('getProject', () => {
    it('happy path: returns a single project', async () => {
      const res = await getProject('project-1');
      expect(res.data.project_id).toBe('project-1');
    });

    it('throws on 404', async () => {
      server.use(
        http.get('/api/projects/:id', () =>
          HttpResponse.json({ detail: 'Not Found' }, { status: 404 })
        )
      );
      await expect(getProject('missing')).rejects.toBeDefined();
    });
  });

  describe('replaceProject', () => {
    it('happy path: returns updated project', async () => {
      server.use(
        http.put('/api/projects/:id', ({ params }) =>
          HttpResponse.json({ project_id: params['id'], name: 'Updated', description: null, tags: [], flow_count: 0, created_on: '', modified_on: '', created_by: null, modified_by: null, href: null })
        )
      );
      const res = await replaceProject('project-1', { name: 'Updated', tags: [] });
      expect(res.data.name).toBe('Updated');
    });
  });

  describe('deleteProject', () => {
    it('happy path: returns 204', async () => {
      const res = await deleteProject('project-1');
      expect(res.status).toBe(204);
    });
  });
});
