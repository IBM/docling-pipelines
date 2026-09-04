/**
 * Environment configuration.
 *
 * No application env vars are exposed to the browser — all backend config
 * lives in the BFF server and is read from the root .env file at startup.
 *
 * Only Vite's built-in mode flags are available here.
 */
export const env = {
  IS_DEV: import.meta.env.DEV,
  IS_PROD: import.meta.env.PROD,
} as const;
