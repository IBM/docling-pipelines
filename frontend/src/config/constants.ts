/**
 * Application-wide constants — theme identifiers, app metadata, UI configuration.
 *
 * Route paths and URL generators live in `routes.config.ts`.
 * Import everything from `@/config` — do not import this file directly.
 */

/**
 * Theme identifiers
 */
export const THEMES = {
  LIGHT: 'g10',
  DARK: 'g100',
} as const;

/**
 * Application metadata
 */
export const APP_INFO = {
  NAME: 'Docling Pipelines',
  TAGLINE: 'Open Source Data Processing Framework',
} as const;

/**
 * UI Configuration
 */
export const UI_CONFIG = {
  MAX_CONTENT_WIDTH: '1200px',
  PAGE_PADDING: '2rem',
} as const;
