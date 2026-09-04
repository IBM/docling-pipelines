/**
 * Theme configuration and utilities
 */

import { THEMES } from './constants';
import type { ThemeType } from '../types/theme';

/**
 * Storage key for theme preference
 */
export const THEME_STORAGE_KEY = 'datasift-theme';

/**
 * Default theme
 */
export const DEFAULT_THEME: ThemeType = THEMES.DARK;

/**
 * Theme display names for supported themes
 */
export const THEME_NAMES: Partial<Record<ThemeType, string>> = {
  [THEMES.LIGHT]: 'Light',
  [THEMES.DARK]: 'Dark',
} as const;

/**
 * Check if a theme value is valid
 */
export function isValidTheme(theme: string): theme is ThemeType {
  return theme === THEMES.LIGHT || theme === THEMES.DARK;
}

/**
 * Get theme from storage or return default
 */
export function getStoredTheme(): ThemeType {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  if (stored && isValidTheme(stored)) {
    return stored;
  }
  return DEFAULT_THEME;
}

/**
 * Save theme to storage
 */
export function saveTheme(theme: ThemeType): void {
  localStorage.setItem(THEME_STORAGE_KEY, theme);
}
