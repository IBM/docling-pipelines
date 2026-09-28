import React, { useState, useEffect, useMemo, type ReactNode } from 'react';
import { type ThemeType, type ThemeContextType } from '@/types';
import { ThemeContext } from './ThemeContext';
import { THEMES, getStoredTheme, saveTheme } from '@/config';

/**
 * Props for {@link ThemeProvider}.
 */
interface ThemeProviderProps {
  /** Application subtree to wrap with the theme context. */
  children: ReactNode;
}

/**
 * Provides the global Carbon theme context to the application.
 *
 * - Reads the initial theme from localStorage via `getStoredTheme()`.
 * - Persists any theme change back to localStorage via `saveTheme()`.
 * - Exposes `theme`, `setTheme`, `toggleTheme`, and `isDarkMode` through
 *   {@link ThemeContext}, consumed by {@link useTheme}.
 */
export function ThemeProvider({ children }: ThemeProviderProps): React.JSX.Element {
  const [theme, setTheme] = useState<ThemeType>(getStoredTheme);

  useEffect(() => {
    saveTheme(theme);
  }, [theme]);

  const toggleTheme = (): void => {
    setTheme((prevTheme) => (prevTheme === THEMES.DARK ? THEMES.LIGHT : THEMES.DARK));
  };

  const value: ThemeContextType = useMemo(
    () => ({
      theme,
      setTheme,
      toggleTheme,
      isDarkMode: theme === THEMES.DARK,
    }),
    [theme]
  );

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
}
