import { useContext } from 'react';
import { ThemeContext } from '@/contexts';
import type { ThemeContextType } from '@/types';

/**
 * Returns the global theme context value.
 *
 * Must be called inside a component that is a descendant of {@link ThemeProvider}.
 * Throws if used outside the provider tree.
 */
export function useTheme(): ThemeContextType {
  const context = useContext(ThemeContext);

  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }

  return context;
}
