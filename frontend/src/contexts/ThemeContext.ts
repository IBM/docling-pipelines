import { createContext } from 'react';
import { type ThemeContextType } from '@/types';

/**
 * React context that holds the global theme state.
 *
 * Do not consume this context directly — use {@link useTheme} instead.
 * The context is provided by {@link ThemeProvider} at the application root.
 */
export const ThemeContext = createContext<ThemeContextType | undefined>(undefined);
