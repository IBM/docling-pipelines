/**
 * Attribute key names for the `ingest_source` operator.
 *
 * These must match the backend attribute keys returned by
 * `IngestSourceOperator.get_metadata()["attributes"]`.
 * Used as the `name` argument to `controller.getPropertyValue()` /
 * `controller.updatePropertyValue()` throughout the panel.
 */
export const INGEST_SOURCE_ATTRIBUTE = {
  /** Storage provider identifier — e.g. "s3", "ibm_cos", "sharepoint" */
  PROVIDER: 'provider',
  /** Provider-specific connection parameters (ingest_source uses this instead of provider_config) */
  CONNECTION_PARAMS: 'connection_params',
  /** Provider-specific configuration */
  PROVIDER_CONFIG: 'provider_config',
  /** Maximum number of files to ingest */
  MAX_FILES: 'max_files',
  /** Comma-separated file extensions to include */
  INCLUDE_FILTER: 'include_filter',
  /** Comma-separated file extensions to exclude */
  EXCLUDE_FILTER: 'exclude_filter',
  /** Skip files starting with '.' (hidden files) */
  IGNORE_HIDDEN_FILES: 'ignore_hidden_files',
} as const;

/**
 * Custom loader provider value.
 * UI falls back to the generic JSON TextArea for connection parameters.
 */
export const CUSTOM_PROVIDER = 'custom';

/**
 * Maps backend provider keys to user-friendly display labels.
 * Keys match the `valid_values` returned by the operator metadata.
 */
export const PROVIDER_DISPLAY_LABELS: Record<string, string> = {
  s3: 'Amazon S3',
  ibm_cos: 'IBM Cloud Object Storage',
  sharepoint: 'Microsoft SharePoint',
  onedrive: 'Microsoft OneDrive',
  google_drive: 'Google Drive',
  box_driver: 'Box',
  filesystem: 'Local filesystem',
  web: 'Web',
  custom: 'Custom loader',
};

/**
 * User-friendly descriptions shown under the Provider configuration accordion
 * for each provider.
 */
export const PROVIDER_DESCRIPTIONS: Record<string, string> = {
  s3: 'Connect to an Amazon S3 bucket or any S3-compatible storage such as MinIO.',
  ibm_cos: 'Connect to an IBM Cloud Object Storage bucket using S3-compatible credentials.',
  sharepoint: 'Ingest documents from a Microsoft SharePoint document library using Azure AD app authentication.',
  onedrive: 'Ingest documents from a Microsoft OneDrive drive using Azure AD app authentication.',
  google_drive: 'Ingest documents from a Google Drive folder using a service account or OAuth credentials.',
  box_driver: 'Ingest documents from a Box folder using a Box JWT service account credentials file.',
  filesystem: 'Ingest documents from one or more paths on the local filesystem.',
  web: 'Crawl and ingest documents from one or more web URLs.',
  custom: 'Use a custom LangChain-compatible loader class. Provide the class path and any required parameters.',
};

/**
 * Description shown under the Ingestion settings accordion.
 */
export const INGESTION_SETTINGS_DESCRIPTION =
  'Control how many files are ingested and which file types are included or excluded.';

/**
 * Union type of all valid `ingest_source` attribute key strings.
 */
export type IngestSourceAttributeKey =
  typeof INGEST_SOURCE_ATTRIBUTE[keyof typeof INGEST_SOURCE_ATTRIBUTE];

/**
 * Human-readable labels for every field in the IngestSource panel.
 */
export const INGEST_SOURCE_LABELS = {
  PROVIDER: 'Provider',
  PROVIDER_CONFIG: 'Provider configuration',
  MAX_FILES: 'Maximum files',
  INCLUDE_FILTER: 'Include file types',
  EXCLUDE_FILTER: 'Exclude file types',
  IGNORE_HIDDEN_FILES: 'Ignore hidden files',
} as const;

/**
 * Supported file extensions for `include_filter` and `exclude_filter`.
 * Matches OperatorConstants.FileExtensions from backend.
 */
export const SUPPORTED_FILE_EXTENSIONS = [
  // Documents
  'pdf',
  'docx',
  'pptx',
  'xlsx',
  // Text & Markup
  'txt',
  'md',
  'html',
  // Images
  'png',
  'jpeg',
  'jpg',
  'tiff',
  'tif',
  'bmp',
  'webp',
  'gif',
  'jfif',
  // Audio
  'wav',
  'mp3',
  'm4a',
  'aac',
  'ogg',
  'flac',
  // Video
  'mp4',
  'avi',
  'mov',
] as const;
