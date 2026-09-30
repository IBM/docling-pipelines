import { describe, it, expect, vi } from 'vitest';
import { server } from '../../../../mocks/server';
import { http, HttpResponse } from 'msw';
import { getOperatorMetadata, enrichFlowFeatures, getProviderModels } from '@/services/api/actions/operator-actions';
import { operatorsFixture } from '../../../../mocks/fixtures/operator.fixture';

describe('operator-actions', () => {
  describe('getOperatorMetadata', () => {
    it('happy path: dispatches setOperatorMetadata with fetched data', async () => {
      const dispatch = vi.fn();
      await getOperatorMetadata(dispatch);
      expect(dispatch).toHaveBeenCalledOnce();
      const action = dispatch.mock.calls[0]?.[0] as { payload: unknown };
      expect(action.payload).toEqual(operatorsFixture);
    });

    it('does not throw on network error (absorbed)', async () => {
      server.use(
        http.get('/api/fetchOperatorMetadata', () => HttpResponse.error())
      );
      const dispatch = vi.fn();
      await expect(getOperatorMetadata(dispatch)).resolves.toBeUndefined();
      expect(dispatch).not.toHaveBeenCalled();
    });
  });

  describe('enrichFlowFeatures', () => {
    it('happy path: returns enriched pipeline response', async () => {
      const res = await enrichFlowFeatures({ nodes: [] });
      expect(res.data).toBeDefined();
    });

    it('throws on network error', async () => {
      server.use(
        http.post('/api/enrichFlowFeatures', () => HttpResponse.error())
      );
      await expect(enrichFlowFeatures({})).rejects.toThrow();
    });
  });

  describe('getProviderModels', () => {
    it('happy path: returns models for provider', async () => {
      const data = await getProviderModels('ollama');
      expect(data.provider).toBe('ollama');
      expect(Array.isArray(data.models)).toBe(true);
    });

    it('throws on 4xx', async () => {
      server.use(
        http.get('/api/providers/:provider/models', () =>
          HttpResponse.json({ detail: 'Provider not found' }, { status: 404 })
        )
      );
      await expect(getProviderModels('unknown')).rejects.toBeDefined();
    });
  });
});
