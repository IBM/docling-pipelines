import { describe, it, expect } from 'vitest';
import { go } from '@/utils/navigation';
import type { NavigateFunction } from 'react-router-dom';
import { vi } from 'vitest';

describe('go (navigation helper)', () => {
  it('calls navigate with the given path', () => {
    const navigate = vi.fn() as unknown as NavigateFunction;
    go(navigate, '/projects');
    expect(navigate).toHaveBeenCalledWith('/projects', undefined);
  });

  it('passes options when provided', () => {
    const navigate = vi.fn() as unknown as NavigateFunction;
    go(navigate, '/projects', { replace: true });
    expect(navigate).toHaveBeenCalledWith('/projects', { replace: true });
  });

  it('does not throw when navigate returns void', () => {
    const navigate = vi.fn().mockReturnValue(undefined) as unknown as NavigateFunction;
    expect(() => go(navigate, '/home')).not.toThrow();
  });
});
