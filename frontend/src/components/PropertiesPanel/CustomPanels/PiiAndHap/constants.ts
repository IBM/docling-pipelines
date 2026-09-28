/**
 * Attribute key names for the `pii_and_hap` operator.
 *
 * These must exactly match the backend attribute keys returned by
 * `PIIAndHAPAnnotator.get_metadata()["attributes"]`.
 * Used as the `name` argument to `controller.getPropertyValue()` /
 * `controller.updatePropertyValue()` throughout the panel.
 */
export const PII_AND_HAP_ATTRIBUTE = {
  /** List of redaction types to perform — e.g. ["PII", "HAP"] */
  EXPECTED_REDACTIONS: 'expected_redactions',
  /** List of PII entity types to detect — e.g. ["EmailAddress", "PhoneNumber"] */
  PII_LIST: 'pii_list',
  /** Whether to include actual PII values in output columns for debugging */
  DISPLAY_PII: 'display_pii',
  /** Whether to enable PII redaction in document content */
  REDACTION: 'redaction',
  /** Single character used to mask PII matches */
  REDACTION_CHARACTER: 'redaction_character',
  /** Whether to enable HAP redaction in document content */
  HAP_REDACTION: 'hap_redaction',
  /** Single character used to mask HAP matches */
  HAP_REDACTION_CHARACTER: 'hap_redaction_character',
  /** Confidence threshold for PII detection (0.0 – 1.0) */
  PII_THRESHOLD: 'pii_threshold',
  /** Confidence threshold for HAP detection (0.0 – 1.0) */
  HAP_THRESHOLD: 'hap_threshold',
  /** LLM provider identifier — e.g. "litellm" or "watsonx" */
  PROVIDER: 'provider',
  /** Provider-specific configuration JSON (model, api_base, api_key, …) */
  PROVIDER_CONFIG: 'provider_config',
} as const;

/**
 * Union type of all valid `pii_and_hap` attribute key strings.
 * Derived from {@link PII_AND_HAP_ATTRIBUTE} so it stays in sync automatically.
 */
export type PiiAndHapAttributeKey =
  typeof PII_AND_HAP_ATTRIBUTE[keyof typeof PII_AND_HAP_ATTRIBUTE];

/**
 * Human-readable labels for every field in the PII and HAP Annotator panel.
 *
 * Used as:
 * - The child of `DefinitionTooltip` (inline label text)
 * - The `labelText` / `label` prop on Carbon inputs (with `hideLabel` to avoid duplication)
 */
export const PII_AND_HAP_LABELS = {
  EXPECTED_REDACTIONS: 'Redaction targets',
  PII_LIST: 'PII types to detect',
  DISPLAY_PII: 'Display PII values',
  REDACTION: 'Enable PII redaction',
  REDACTION_CHARACTER: 'PII masking character',
  HAP_REDACTION: 'Enable HAP redaction',
  HAP_REDACTION_CHARACTER: 'HAP masking character',
  PII_THRESHOLD: 'PII confidence threshold',
  HAP_THRESHOLD: 'HAP confidence threshold',
  PROVIDER: 'Provider',
  PROVIDER_CONFIG: 'Provider configuration (JSON)',
} as const;

/** Description shown at the top of the Provider configuration accordion item. */
export const PROVIDER_CONFIG_DESCRIPTION = 'Select the LLM provider used for detection and configure its connection settings.';

/** All available redaction target options */
export const EXPECTED_REDACTIONS_OPTIONS = ['PII', 'HAP'] as const;

/** All available PII entity type options */
export const PII_LIST_OPTIONS = [
  'BankAccountNumber',
  'CreditCardNumber',
  'EmailAddress',
  'IPAddress',
  'PhoneNumber',
  'SocialSecurityNumber',
] as const;
