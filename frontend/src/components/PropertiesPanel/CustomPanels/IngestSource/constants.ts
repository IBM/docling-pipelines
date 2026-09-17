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
  /** Provider-specific connection parameters (bucket, prefix, folder_id, …) */
  CONNECTION_PARAMS: 'connection_params',
  /** Authentication credentials for the provider */
  CREDENTIALS: 'credentials',
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
 * Configuration for the source locations input shown for providers where the
 * ingestion roots (filesystem paths, web URLs) are managed through a dedicated
 * TagInput rather than typed as an array in Connection parameters input.
 */
export interface ProviderSourceLocationsConfig {
  /** Key inside `connection_params` the backend expects (e.g. "paths", "urls"). */
  paramKey: string;
  /** User-friendly label shown above the TagInput. */
  label: string;
  /** Placeholder shown inside the empty TagInput. */
  placeholder: string;
  /** Helper text shown below the TagInput. */
  helperText: string;
}

/**
 * Maps provider names to their source locations config.
 * Providers not listed here have no separate source locations input.
 */
export const PROVIDER_SOURCE_LOCATIONS: Record<string, ProviderSourceLocationsConfig> = {
  filesystem: {
    paramKey: 'paths',
    label: 'Paths (required)',
    placeholder: '/data/documents',
    helperText: 'Type a path and press Enter or comma to add it.',
  },
  web: {
    paramKey: 'urls',
    label: 'URLs (required)',
    placeholder: 'https://example.com',
    helperText: 'Type a URL and press Enter or comma to add it.',
  },
};

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
  CONNECTION_PARAMS: 'Connection parameters',
  CREDENTIALS: 'Credentials',
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
