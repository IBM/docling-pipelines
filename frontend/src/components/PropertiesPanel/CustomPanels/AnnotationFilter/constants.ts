/**
 * @file constants.ts
 *
 * All constants for the `sql_filter` (Annotation Filter) operator panel.
 *
 * Follows the same pattern as
 * `CustomPanels/DocumentClassifier/constants.ts`:
 * - `ANNOTATION_FILTER_ATTRIBUTE` — Elyra parameter / attribute key names
 * - `ANNOTATION_FILTER_LABELS` — human-readable field labels
 * - `ANNOTATION_FILTER_DEFAULTS` — static fallback strings
 * - `ANNOTATION_FILTER_TABLE_HEADERS` — shared column definitions
 * - `ADVANCED_EXPRESSION_ROW_ID` — sentinel ID for the advanced-mode table row
 *
 * Import from here instead of defining strings inline in component files.
 */

import type { SharedDataTableHeader } from '@/components/common/SharedDataTable';

// ---------------------------------------------------------------------------
// Attribute keys — Elyra parameter names
// ---------------------------------------------------------------------------

/**
 * Elyra property names for the `sql_filter` operator's parameters.
 *
 * Values must exactly match the `id` fields in `sql_filter_paramDef.json`
 * and the attribute keys returned by `SQLFilterOperator.get_metadata()`.
 * Used as the `name` argument to `controller.getPropertyValue()` /
 * `controller.updatePropertyValue()` throughout the panel.
 */
export const ANNOTATION_FILTER_ATTRIBUTE = {
  /**
   * Structured condition object written in Simple mode.
   * Shape: `{ logical_operator: "AND"|"OR", criteria_list: Condition[] }`
   */
  CRITERIA_JSON: 'criteria_json',
  /**
   * Single-element string array written in Advanced mode.
   * Shape: `["raw SQL expression"]`
   */
  CRITERIA_LIST: 'criteria_list',
} as const;

/**
 * Union type of all valid `sql_filter` attribute key strings.
 * Derived from {@link ANNOTATION_FILTER_ATTRIBUTE} so it stays in sync automatically.
 */
export type AnnotationFilterAttributeKey =
  typeof ANNOTATION_FILTER_ATTRIBUTE[keyof typeof ANNOTATION_FILTER_ATTRIBUTE];

// ---------------------------------------------------------------------------
// Labels — human-readable field text
// ---------------------------------------------------------------------------

/**
 * Human-readable labels for every field in the Annotation Filter panel.
 *
 * Used as:
 * - The child of `DefinitionTooltip` (inline label text shown on hover)
 * - `FormLabel` text for section headings
 * - Placeholder / button copy
 */
export const ANNOTATION_FILTER_LABELS = {
  /** Section label for the criteria list field. */
  CRITERIA_LIST: 'Criteria list',
  /** Section label for the available features table. */
  AVAILABLE_FEATURES: 'Available features',
  /** Column header in the available features table. */
  FEATURE_NAME: 'Feature name',
  /** Column header in the criteria table (panel and full-view). */
  CONDITION: 'Condition',
  /** Ghost button label when no criteria have been saved yet. */
  ADD_CRITERIA: 'Add Criteria',
  /** Ghost button label when at least one criterion already exists. */
  UPDATE_CRITERIA: 'Update Criteria',
  /** Icon button tooltip for the expand / maximize toolbar button. */
  EXPAND_VIEW: 'Expand view',
  /** Icon button tooltip for the delete button on a criteria row. */
  DELETE: 'Delete',
  /** Search box placeholder for the compact criteria table. */
  SEARCH_CRITERIA: 'Search criteria',
  /** Tearsheet title for the condition builder. */
  BUILDER_TITLE: 'Criteria',
  /** Tearsheet title for the full-view expand. */
  FULL_VIEW_TITLE: 'Criteria',
  /** Tearsheet description for the full-view expand. */
  FULL_VIEW_DESCRIPTION: 'Review all saved filter criteria.',
  /** Full-view tearsheet close button label. */
  CLOSE: 'Close',
} as const;

// ---------------------------------------------------------------------------
// Defaults — static fallback strings
// ---------------------------------------------------------------------------

/**
 * Static fallback values used when backend operator metadata is unavailable.
 */
export const ANNOTATION_FILTER_DEFAULTS = {
  /**
   * Tooltip description for the Criteria list field shown when
   * `operatorMetadata` has not loaded or does not include a description.
   */
  CRITERIA_DESCRIPTION:
    "List of SQL queries (not including the where clause). Examples: pii_bank_account >= 1, lang_score > 0.3, lang_name='en'",

  /**
   * Tearsheet description shown in the condition builder header.
   */
  BUILDER_DESCRIPTION:
    'Add list of SQL queries (not including the where clause). Examples: pii_bank_account >= 1, lang_score > 0.3',

  /**
   * Empty-state message shown in the available features table when no
   * upstream node is connected.
   */
  NO_FEATURES_MESSAGE: 'No features available — connect an upstream node.',
} as const;

// ---------------------------------------------------------------------------
// Table headers — shared column definitions
// ---------------------------------------------------------------------------

/**
 * Column definitions for the compact inline criteria table shown in the panel
 * body. Single column — each cell renders condition text + badge + delete button.
 */
export const CRITERIA_TABLE_HEADERS: SharedDataTableHeader[] = [
  { key: 'conditionDisplay', header: ANNOTATION_FILTER_LABELS.CONDITION },
];

/**
 * Column definitions for the full-view criteria tearsheet.
 * Single column — condition text + AND/OR badge (no delete button in full view).
 */
export const FULL_VIEW_TABLE_HEADERS: SharedDataTableHeader[] = [
  { key: 'conditionDisplay', header: ANNOTATION_FILTER_LABELS.CONDITION },
];

/**
 * Column definitions for the read-only available features table.
 * Shows both the feature name and its data type so users can write
 * correct filter conditions.
 */
export const AVAILABLE_FEATURES_TABLE_HEADERS: SharedDataTableHeader[] = [
  { key: 'feature', header: ANNOTATION_FILTER_LABELS.FEATURE_NAME },
  { key: 'type', header: 'Type' },
];

// ---------------------------------------------------------------------------
// Condition builder UI labels
// ---------------------------------------------------------------------------

/**
 * All human-readable strings used inside {@link ConditionBuilder} and the
 * logical-operator strip. Centralised here so they can be updated in one place.
 */
export const CONDITION_BUILDER_LABELS = {
  // ── Field labels ──────────────────────────────────────────────────────────
  VARIABLE: 'Variable',
  OPERATOR: 'Operator',
  VALUE: 'Value',
  START_VALUE: 'Start value',
  END_VALUE: 'End value',
  LOGICAL_OPERATOR: 'Logical operator',
  AND: 'AND',
  OR: 'OR',
  TRUE: 'True',
  FALSE: 'False',

  // ── Placeholders ──────────────────────────────────────────────────────────
  CHOOSE_VARIABLE: 'Choose a variable',
  CHOOSE_OPERATOR: 'Choose an operator',
  ENTER_VALUE: 'Enter value',
  ENTER_MULTIPLE_VALUES: 'Enter comma-separated values',
  ENTER_JSON_VALUE: 'Enter JSON value',

  // ── Helper texts ──────────────────────────────────────────────────────────
  DATETIME_HELPER: 'Format: YYYY-MM-DD HH:MM:SS (e.g., 2024-01-15 14:30:00)',
  COMMA_SEPARATED_HELPER: 'Separate multiple values with commas (e.g., A,B,C)',
  JSON_HELPER: 'Enter valid JSON format',

  // ── Validation error messages ─────────────────────────────────────────────
  ERROR_INVALID_TIMESTAMP: 'Please enter a valid timestamp in YYYY-MM-DD HH:MM:SS format',
  ERROR_INVALID_TIMESTAMP_RANGE: 'Please enter valid timestamps for both start and end values (YYYY-MM-DD HH:MM:SS)',
  ERROR_INVALID_JSON: 'Invalid JSON format',

  // ── Tooltip / icon descriptions ───────────────────────────────────────────
  LOGICAL_OPERATOR_TOOLTIP: 'Select either the AND or OR conditional operator for processing your criteria list of SQL queries',
  DELETE_CONDITION: 'Delete condition',
  ADD_CONDITION: 'Add condition',

  // ── Loading / empty states ────────────────────────────────────────────────
  LOADING_FEATURES: 'Loading features…',
  NO_FEATURES: 'No features available — connect an upstream node.',
} as const;

// ---------------------------------------------------------------------------
// Sentinel values
// ---------------------------------------------------------------------------

/**
 * Stable row ID used for the single Advanced-mode row in the criteria table.
 *
 * When `criteria_list` holds a raw SQL string, one synthetic row is created
 * with this ID. `handleDeleteCondition` checks for it to decide whether to
 * clear `criteria_list` (advanced) or filter `criteria_json.criteria_list`
 * (simple).
 */
export const ADVANCED_EXPRESSION_ROW_ID = 'advanced-expression' as const;
