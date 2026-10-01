/** Attribute key names — must match operator metadata keys exactly. */
export const LANGUAGE_DETECT_ATTR = {
  LANGUAGE_PROVIDER: 'language_provider',
  FILTER_UNKNOWN_LANGUAGE: 'filter_unknown_language',
} as const;

/**
 * User-friendly labels for every field in the LanguageDetect panel.
 */
export const LANGUAGE_DETECT_LABEL = {
  LANGUAGE_PROVIDER: 'Language detection provider',
  FILTER_UNKNOWN_LANGUAGE: 'Filter unknown language documents',
} as const;

export const LANGUAGE_DETECT_PROVIDER_ITEMS = ['fasttext', 'langdetect'];
