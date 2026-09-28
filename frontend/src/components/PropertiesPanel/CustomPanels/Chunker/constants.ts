/**
 * Attribute key names for the `chunker` operator.
 *
 * These must exactly match the backend config keys consumed by
 * `ChunkerOperator.get_metadata()["attributes"]`.
 * Used as the `name` argument to `controller.getPropertyValue()` /
 * `controller.updatePropertyValue()` throughout the panel.
 */
export const CHUNKER_ATTRIBUTE = {
  /** Chunking strategy */
  CHUNK_TYPE: 'chunk_type',
  /** Chunk size in characters (simple) or tokens (hybrid) */
  CHUNK_SIZE: 'chunk_size',
  /** Overlap between consecutive chunks */
  CHUNK_OVERLAP: 'chunk_overlap',
  /** Overlap expressed as a percentage of chunk_size */
  CHUNK_OVERLAP_PERCENTAGE: 'chunk_overlap_percentage',
  /** Ollama model name for semantic chunking embeddings */
  SEMANTIC_EMBEDDINGS_MODEL: 'semantic_embeddings_model',
  /** Boundary detection method for semantic chunking */
  BREAKPOINT_THRESHOLD_TYPE: 'breakpoint_threshold_type',
  /** Threshold value for the selected breakpoint detection method */
  BREAKPOINT_THRESHOLD_AMOUNT: 'breakpoint_threshold_amount',
  /** HuggingFace tokenizer for hybrid chunking */
  DOCLING_TOKENIZER: 'docling_tokenizer',
  /** Whether to keep the original content column after chunking */
  RETAIN_ORIGINAL_CONTENT: 'retain_original_content',
  /** Summarization configuration */
  SUMMARIZATION: 'summarization',
  /** Set to 'docling_serve' to route chunking to a remote Docling Serve API */
  PROVIDER: 'provider',
  /** Provider-specific configuration */
  PROVIDER_CONFIG: 'provider_config',
} as const;

// ── Chunk types ───────────────────────────────────────────────────────────────

export const CHUNK_TYPES = ['simple', 'semantic', 'hybrid'] as const;
export type ChunkType = typeof CHUNK_TYPES[number];

/** Maps backend chunk_type value → User-friendly dropdown label. */
export const CHUNK_TYPE_LABELS: Record<ChunkType, string> = {
  simple: 'Simple',
  semantic: 'Semantic',
  hybrid: 'Hybrid (Docling)',
};

// ── Breakpoint threshold types ────────────────────────────────────────────────

export const BREAKPOINT_THRESHOLD_TYPES = [
  'percentile',
  'standard_deviation',
  'interquartile',
  'gradient',
] as const;
export type BreakpointThresholdType = typeof BREAKPOINT_THRESHOLD_TYPES[number];

/** Maps backend breakpoint_threshold_type value → User-friendly dropdown label. */
export const BREAKPOINT_THRESHOLD_TYPE_LABELS: Record<BreakpointThresholdType, string> = {
  percentile: 'Percentile',
  standard_deviation: 'Standard Deviation',
  interquartile: 'Interquartile',
  gradient: 'Gradient',
};

// ── Defaults ──────────────────────────────────────────────────────────────────

export const CHUNKER_DEFAULTS = {
  CHUNK_TYPE: 'simple' as ChunkType,
  CHUNK_SIZE: 1000,
  CHUNK_OVERLAP: 200,
  CHUNK_OVERLAP_PERCENTAGE: 20,
  BREAKPOINT_THRESHOLD_TYPE: 'percentile' as BreakpointThresholdType,
  DOCLING_TOKENIZER: 'sentence-transformers/all-MiniLM-L6-v2',
  RETAIN_ORIGINAL_CONTENT: false,
} as const;

// ── Human-readable labels ─────────────────────────────────────────────────────

export const CHUNKER_LABELS = {
  CHUNK_TYPE: 'Chunk type',
  CHUNK_SIZE: 'Chunk size',
  CHUNK_OVERLAP: 'Chunk overlap',
  CHUNK_OVERLAP_PERCENTAGE: 'Chunk overlap percentage',
  SEMANTIC_EMBEDDINGS_MODEL: 'Semantic embeddings model',
  BREAKPOINT_THRESHOLD_TYPE: 'Breakpoint threshold type',
  BREAKPOINT_THRESHOLD_AMOUNT: 'Breakpoint threshold amount',
  DOCLING_TOKENIZER: 'Docling tokenizer',
  RETAIN_ORIGINAL_CONTENT: 'Retain original content',
  SUMMARIZATION: 'Enable summarization',
  SUMMARIZATION_CONFIG: 'Summarization configuration (JSON)',
  USE_DOCLING_SERVE: 'Use Docling Serve (remote)',
  PROVIDER_CONFIG: 'Docling Serve configuration (JSON)',
} as const;

/** Description shown at the top of the Summarization accordion item. */
export const SUMMARIZATION_DESCRIPTION =
  'When enabled, an LLM generates a concise summary for each chunk after splitting. '
  + 'Select a provider and configure its connection settings below.';
