/**
 * @file VectorDB provider configuration save helpers.
 *
 * Pure serialisation utilities for persisting tearsheet output back to the Elyra
 * node controller. Contains no React, no side-effects, and no I/O.
 *
 * Exported functions:
 * - `mergeProviderConfig`          — merges resource name, similarity metric, and engine
 *                                    into the saved provider configuration object.
 * - `clearProviderConfigResource`  — removes the resource name key from the provider
 *                                    configuration so the panel reverts to empty state.
 */

/**
 * Merge tearsheet-selected values into the raw provider_config JSON string.
 *
 * The result is a plain object (never a string) so Elyra serialises
 * provider_config as a JSON object in the saved flow, not as a quoted string.
 *
 * Callers should treat the input `providerConfigJson` as validated — the
 * tearsheet only opens when the textarea already contains valid JSON.
 * The try/catch is retained as a safety net for unexpected edge cases.
 */
export function mergeProviderConfig(
  providerConfigJson: string,
  patch: Record<string, unknown>
): Record<string, unknown> {
  let base: Record<string, unknown> = {};
  try {
    base = JSON.parse(providerConfigJson) as Record<string, unknown>;
  } catch {
    // providerConfigJson is validated before the tearsheet opens — unreachable in practice.
  }
  return { ...base, ...patch };
}

/**
 * Return a copy of the parsed provider_config with the resource name key removed.
 * Used when clearing state (provider change, all mappings removed) so index_name /
 * collection_name no longer appears in the saved config.
 */
export function clearProviderConfigResource(
  parsedConfig: Record<string, unknown>,
  resourceNameKey: string
): Record<string, unknown> {
  const { [resourceNameKey]: _removed, ...rest } = parsedConfig;
  return rest;
}
