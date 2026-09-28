/**
 * Operator category and color constants for the Canvas palette
 *
 * @module constants/operators
 */

import { yellow, cyan, teal, red, purple, blue } from '@carbon/colors';

/**
 * Operator category identifiers.
 * Categories group related operators in the palette.
 *
 * @constant
 */
export const OperatorCategory = {
  /** Text and entity extraction operators */
  EXTRACT: 'extract',

  /** Data ingestion operators */
  INGEST: 'ingest',

  /** Data transformation operators (chunking, embeddings, etc.) */
  FUNCTIONAL: 'functional',

  /** Data quality and filtering operators */
  QUALITY: 'quality',

  /** Vector database storage operators */
  VECTORDB: 'vectordb',

  /** Document storage and persistence operators */
  STORAGE: 'storage',

  /** Flow control operators — branching and merging */
  BRANCHING: 'branching',
} as const;

/**
 * Type representing valid operator category values
 */
export type OperatorCategoryType = typeof OperatorCategory[keyof typeof OperatorCategory];

/**
 * Individual operator identifiers.
 * Each operator represents a specific data processing step.
 *
 * @constant
 */
export const NodeOperator = {
  /** Data ingestion from various sources */
  INGEST: 'ingest_source',

  /** Text and entity extraction using Docling */
  EXTRACT: 'extract_operator',

  /** Text chunking for processing */
  CHUNKER: 'chunker',

  /** Vector embeddings generation */
  EMBEDDINGS: 'embeddings',

  /** Exact duplicate document removal */
  DEDUPLICATION: 'ededup',

  /** Vector database storage */
  VECTORDB: 'vectordb',

  /** Document set management */
  DOCUMENT_SET: 'document_set',

  /** Document classification using LLM */
  DOCUMENT_CLASSIFIER: 'document_classifier',

  /** Language detection and annotation */
  LANG_DETECT: 'lang_detect',

  /** SQL-based annotation filter */
  SQL_FILTER: 'sql_filter',

  /** Source ingestion (S3, IBM COS, SharePoint, OneDrive, Google Drive) */
  INGEST_SOURCE: 'ingest_source',

  /** Regex-based content redaction */
  REDACTION: 'redaction',

  /** Readability score computation */
  READABILITY: 'readability',

  /** Entity curation using document class schemas */
  ENTITY_CURATION: 'entity_curation',

  /** ML text enrichment */
  ML_ENRICHMENT: 'ml_enrichment',

  /** Document quality metrics (word counts, ratios, lorem ipsum, bad words) */
  DOC_QUALITY: 'doc_quality',

  /** ACL extraction from source provider */
  ACL_OPERATOR: 'acl_operator',

  /** Pass-through operator for testing and debugging */
  NOOP: 'noop',

  /** PII and HAP detection and redaction */
  PII_AND_HAP: 'pii_and_hap',
  /**
   * Conditional branching — fans one input stream out to N branches.
   * Output port id: `branching_outPort` (max: -1 / unlimited).
   * Stores per-link conditions in `parameters.link_conditions`.
   */
  BRANCHING: 'branching',

  /**
   * Merge — fans N input branches back into one stream.
   * Input port id: `merge_inPort` (max: -1 / unlimited).
   */
  MERGING: 'merge',

  /** Write pipeline documents to a storage destination */
  STORAGE_OUTPUT: 'storage_output',
} as const;

/**
 * Type representing valid operator values
 */
export type NodeOperatorType = typeof NodeOperator[keyof typeof NodeOperator];

/**
 * Maps operator categories to their Carbon Design System colors.
 * These colors are used for visual distinction in the palette.
 *
 * @constant
 *
 * @remarks
 * Colors are from Carbon Design System palette:
 * - Ingest: Yellow (warm, input-focused)
 * - Extract: Cyan (cool, processing)
 * - VectorDB: Teal (storage, database)
 * - Functional: Red (transformation)
 * - Quality: Purple (validation)
 * - Storage: Purple (persistence)
 */
export const CATEGORY_COLORS: Record<string, string> = {
  [OperatorCategory.INGEST]: yellow[50],
  [OperatorCategory.EXTRACT]: cyan[70],
  [OperatorCategory.VECTORDB]: teal[50],
  [OperatorCategory.FUNCTIONAL]: red[90],
  [OperatorCategory.QUALITY]: purple[80],
  [OperatorCategory.STORAGE]: purple[70],
  [OperatorCategory.BRANCHING]: blue[60],
};

// ── Branching port identifiers ────────────────────────────────────────────────

/**
 * The port id used on the **output** side of a Branching node.
 * Links originating from this port receive per-link name + condition decorations.
 */
export const BRANCHING_OUTPORT_ID = 'branching_outPort';

/**
 * The port id used on the **input** side of a Merging node.
 * Links targeting this port receive per-link name decorations.
 */
export const MERGING_INPORT_ID = 'merge_inPort';

/** Maximum number of output branches from a single Branching node. */
export const BRANCHING_MAX_OUTPUTS = 5;
