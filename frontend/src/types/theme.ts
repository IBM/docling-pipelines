/**
 * Theme type definitions shared across the application.
 *
 * `ThemeType` enumerates the Carbon Design System theme tokens supported by this app.
 * `ThemeContextType` is the shape of the React context value exposed by {@link ThemeProvider}.
 */

/**
 * Valid Carbon theme identifiers.
 *
 * - `'white'` — Light (White) theme.
 * - `'g10'`   — Light (Gray 10) theme.
 * - `'g90'`   — Dark (Gray 90) theme.
 * - `'g100'`  — Dark (Gray 100) theme.
 */
export type ThemeType = 'white' | 'g10' | 'g90' | 'g100';

/**
 * Value shape of the global theme React context.
 *
 * Provided by {@link ThemeProvider} and consumed via {@link useTheme}.
 */
export interface ThemeContextType {
  /** The currently active Carbon theme token. */
  theme: ThemeType;
  /** Sets the active theme and persists the preference to localStorage. */
  setTheme: (theme: ThemeType) => void;
  /** Toggles between the light (`'g10'`) and dark (`'g100'`) themes. */
  toggleTheme: () => void;
  /** `true` when the active theme is a dark variant (`g90` or `g100`). */
  isDarkMode: boolean;
}
