import { describe, it, expect } from 'vitest';
import { apiClient } from '@/services/api/client';

describe('apiClient', () => {
  it('has Content-Type: application/json header', () => {
    const headers = apiClient.defaults.headers as Record<string, unknown>;
    const common = headers['common'] as Record<string, unknown> | undefined;
    const contentType = common?.['Content-Type'] ?? headers['Content-Type'];
    expect(String(contentType)).toContain('application/json');
  });

  it('has a 10000ms timeout', () => {
    expect(apiClient.defaults.timeout).toBe(10000);
  });

  it('is an axios instance with get/post/put/delete methods', () => {
    expect(typeof apiClient.get).toBe('function');
    expect(typeof apiClient.post).toBe('function');
    expect(typeof apiClient.put).toBe('function');
    expect(typeof apiClient.delete).toBe('function');
  });
});
