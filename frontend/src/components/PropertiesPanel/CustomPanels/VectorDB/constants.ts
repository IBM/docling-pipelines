/**
 * @file Constants for the VectorDB operator properties panel and feature mapping tearsheet.
 *
 * All provider-specific differences (key names, labels, default values) are
 * expressed as data in `PROVIDER_CONFIG_MAP` — never as `if`/`switch` branches
 * in components. To add a new vector database provider, add a single entry to
 * that map; no component code needs to change.
 */

export const VECTORDB_ATTRIBUTES = {
  PROVIDER: 'provider',
  PROVIDER_CONFIG: 'provider_config',
  FEATURE_MAPPINGS: 'feature_mappings',
  ADD_SPARSE_VECTOR: 'add_sparse_vector',
} as const;

export const VECTORDB_LABELS = {
  PROVIDER: 'Provider',
  PROVIDER_CONFIG: 'Provider configuration',
  FEATURE_MAPPING_TITLE: 'Map features to resource columns',
  FEATURE_MAPPING_DESC:
    'Select features from connected nodes and add them to your target resource columns',
  FEATURE_MAPPINGS_CONFIG: 'Feature mappings configuration',
  ADD_FEATURE_MAPPINGS: 'Add feature mappings',
  EDIT_FEATURE_MAPPINGS: 'Edit feature mappings',
  /** Sentinel value for the resource ComboBox "create a new resource" option. */
  CREATE_NEW: 'Create new',
} as const;

export const VECTORDB_PROVIDERS = {
  OPENSEARCH: 'opensearch',
  MILVUS: 'milvus',
} as const;

// ── OpenSearch constants ──────────────────────────────────────────────────────

/** Display labels for OpenSearch space_type values. */
const SPACE_TYPE_LABELS: Record<string, string> = {
  l2: 'Euclidean distance',
  cosine: 'Cosine similarity',
  inner_product: 'Inner product',
};

/** Display labels for OpenSearch engine values. */
const ENGINE_LABELS: Record<string, string> = {
  faiss: 'Faiss',
  lucene: 'Lucene',
  nmslib: 'NMSLIB',
  jvector: 'jVector',
};

/** Fallback space_type options when metadata valid_values are unavailable. */
export const DEFAULT_SPACE_TYPE_VALUES = ['l2', 'cosine', 'inner_product'];

/** Fallback engine options when metadata valid_values are unavailable. */
export const DEFAULT_ENGINE_VALUES = ['faiss', 'lucene', 'nmslib', 'jvector'];

// ── Milvus constants ──────────────────────────────────────────────────────────

/**
 * Display labels for Milvus metric_type values.
 * Valid values returned by the backend: L2, IP, COSINE, BM25.
 */
const METRIC_TYPE_LABELS: Record<string, string> = {
  L2: 'Euclidean distance (L2)',
  IP: 'Inner product (IP)',
  COSINE: 'Cosine similarity',
  BM25: 'BM25 (sparse)',
};

/** Fallback metric_type options when metadata valid_values are unavailable. */
export const DEFAULT_METRIC_TYPE_VALUES = ['L2', 'IP', 'COSINE', 'BM25'];

// ── Provider configuration map ───────────────────────────────────────────────

/**
 * All provider-specific configuration for the VectorDB panel and tearsheet.
 * Components read `cfg = getProviderConfig(provider)` and use `cfg.*` throughout.
 */

/** Fields shared by every provider configuration. */
interface ProviderConfigBase {
  /** Key in provider_config that holds the resource name (e.g. index_name / collection_name). */
  resourceNameKey: string;
  /** User-facing singular label for the resource type (e.g. "index" / "collection"). */
  resourceLabel: string;
  /** Key in provider_config that holds the similarity metric (e.g. space_type / metric_type). */
  similarityKey: string;
  /** User-facing label for the similarity field (e.g. "Space type" / "Metric type"). */
  similarityLabel: string;
  /** Display labels for similarity raw values { raw: 'Human label' }. */
  similarityLabels: Record<string, string>;
  /** Fallback similarity options when operator metadata returns none. */
  defaultSimilarityValues: string[];
  /**
   * All resource-specific keys to omit from provider_config before API calls.
   * These are saved state, not connection parameters — the backend must not see them.
   */
  resourceSpecificKeys: string[];
  /** Default provider_config JSON shown in the textarea when no config is saved yet. null = show empty textarea. */
  defaultConfig: Record<string, unknown> | null;
}

/** Provider that exposes an engine field (e.g. OpenSearch). */
interface ProviderConfigWithEngine extends ProviderConfigBase {
  hasEngine: true;
  /** Key in provider_config for the engine. */
  engineKey: string;
  /** Display labels for engine raw values { raw: 'Human label' }. */
  engineLabels: Record<string, string>;
}

/** Provider without an engine field (e.g. Milvus). */
interface ProviderConfigNoEngine extends ProviderConfigBase {
  hasEngine: false;
  engineKey?: never;
  engineLabels?: never;
}

/** Discriminated union — narrow with `cfg.hasEngine` to access engine fields without `!`. */
export type ProviderConfig = ProviderConfigWithEngine | ProviderConfigNoEngine;

const PROVIDER_CONFIG_MAP: Record<string, ProviderConfig> = {
  [VECTORDB_PROVIDERS.OPENSEARCH]: {
    resourceNameKey:         'index_name',
    resourceLabel:           'index',
    similarityKey:           'space_type',
    similarityLabel:         'Space type',
    similarityLabels:        SPACE_TYPE_LABELS,
    defaultSimilarityValues: DEFAULT_SPACE_TYPE_VALUES,
    hasEngine:               true,
    engineKey:               'engine',
    engineLabels:            ENGINE_LABELS,
    resourceSpecificKeys:    ['index_name', 'space_type', 'engine'],
    defaultConfig:           null,
  },
  [VECTORDB_PROVIDERS.MILVUS]: {
    resourceNameKey:         'collection_name',
    resourceLabel:           'collection',
    similarityKey:           'metric_type',
    similarityLabel:         'Metric type',
    similarityLabels:        METRIC_TYPE_LABELS,
    defaultSimilarityValues: DEFAULT_METRIC_TYPE_VALUES,
    hasEngine:               false,
    resourceSpecificKeys:    ['collection_name', 'metric_type'],
    defaultConfig:           null,
  },
};

/**
 * Returns the provider-specific config for the given provider string.
 * Falls back to OpenSearch config for unknown providers so the UI never breaks.
 */
export function getProviderConfig(provider: string): ProviderConfig {
  return PROVIDER_CONFIG_MAP[provider] ?? (PROVIDER_CONFIG_MAP[VECTORDB_PROVIDERS.OPENSEARCH] as ProviderConfig);
}

/** Canonical default target column/field names for standard feature names. */
export const DEFAULT_COLUMN_MAPPINGS: Record<string, string> = {
  doc_id_hash: 'pk',
  id: 'document_id',
  name: 'document_name',
  embeddings: 'vector_embeddings',
  sparse_embeddings: 'sparse_embeddings',
  content: 'text',
};

/**
 * Omit a set of keys from a provider_config object before sending to the API.
 * Used to strip resource-specific saved values so the backend computes fresh ones.
 */
export function omitProviderConfigKeys(
  config: Record<string, unknown>,
  keys: string[]
): Record<string, unknown> {
  const keySet = new Set(keys);
  return Object.fromEntries(Object.entries(config).filter(([k]) => !keySet.has(k)));
}
