import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import React from 'react';
import { ThemeElementContext, useThemeElement } from '@/contexts/ThemeElementContext';

describe('useThemeElement', () => {
  it('inside provider with a real div ref returns that element', () => {
    const div = document.createElement('div');
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(ThemeElementContext.Provider, { value: div }, children);

    const { result } = renderHook(() => useThemeElement(), { wrapper });
    expect(result.current).toBe(div);
  });

  it('outside provider falls back to document.body', () => {
    const { result } = renderHook(() => useThemeElement());
    expect(result.current).toBe(document.body);
  });
});
