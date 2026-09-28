/*
 * Licensed Materials - Property of IBM
 * © Copyright IBM Corp. 2024, 2026.
 */

import type { NavigateFunction, NavigateOptions, To } from 'react-router-dom';

/**
 * Calls `navigate()` and explicitly discards its return value.
 *
 * react-router-dom v7 types `NavigateFunction` as returning `void`, but some
 * TypeScript configurations (or future versions) may resolve it as
 * `Promise<void>`. Wrapping in this helper satisfies both
 * `@typescript-eslint/no-floating-promises` (CI) and
 * `@typescript-eslint/no-confusing-void-expression` (local) simultaneously —
 * neither rule applies to a call whose return type is `void` at the call site.
 */
export function go(navigate: NavigateFunction, to: To, options?: NavigateOptions): void {
  void navigate(to, options);
}
