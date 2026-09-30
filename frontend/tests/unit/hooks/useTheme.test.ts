import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import React from 'react';
import { useTheme } from '@/hooks/useTheme';
import { ThemeProvider } from '@/contexts';

describe('useTheme', () => {
  it('inside ThemeProvider returns context with isDarkMode boolean', () => {
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(ThemeProvider, null, children);

    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(typeof result.current.isDarkMode).toBe('boolean');
    expect(typeof result.current.toggleTheme).toBe('function');
    expect(result.current.theme).toBeDefined();
  });

  it('outside ThemeProvider throws with correct message', () => {
    expect(() => {
      renderHook(() => useTheme());
    }).toThrow('useTheme must be used within a ThemeProvider');
  });
});
