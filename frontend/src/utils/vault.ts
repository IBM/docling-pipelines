/**
 * @fileoverview Vault reference utility functions.
 */

/**
 * Returns true when value is a vault:// reference string. Mirrors the backend check.
 */
export const isVaultReference = (value: unknown): value is string =>
  typeof value === 'string' && value.startsWith('vault://');
