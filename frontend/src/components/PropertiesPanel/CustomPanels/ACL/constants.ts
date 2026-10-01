/** Attribute key names — must match operator metadata keys exactly. */
export const ACL_ATTR = {
  PROVIDER_CONFIG: 'provider_config',
  FAIL_ON_ERROR: 'fail_on_error',
} as const;

/**
 * User-friendly labels for every field in the ACL panel.
 */
export const ACL_LABEL = {
  PROVIDER_CONFIG: 'Provider configuration',
  FAIL_ON_ERROR: 'Fail on error',
} as const;
