import { describe, it, expect } from 'vitest';
import { server } from '../../../../mocks/server';
import { http, HttpResponse } from 'msw';
import { getDocumentClasses } from '@/services/api/actions/document-class-actions';

describe('document-class-actions', () => {
  it('getDocumentClasses calls GET /api/documentClasses and returns data', async () => {
    server.use(
      http.get('/api/documentClasses', () =>
        HttpResponse.json([{ id: 'research', label: 'Research' }])
      )
    );
    const res = await getDocumentClasses();
    expect(res.data).toEqual([{ id: 'research', label: 'Research' }]);
  });

  it('getDocumentClasses throws when server returns error', async () => {
    server.use(
      http.get('/api/documentClasses', () => HttpResponse.json({ message: 'Server Error' }, { status: 500 }))
    );
    await expect(getDocumentClasses()).rejects.toBeDefined();
  });
});
