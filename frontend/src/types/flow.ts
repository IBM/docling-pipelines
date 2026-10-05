/**
 * @fileoverview Flow domain type definitions.
 *
 * Three layers are defined here:
 * 1. **API wire types** — shapes returned by the BFF/backend (`Flow`, `JobRunSummary`,
 *    `FlowDefinition`, `PaginatedFlowResponse`). Only `flow-mapper.ts` reads these directly.
 * 2. **UI form types** — values collected from modals (`CreateFlowFormValues`).
 * 3. **Redux state types** — the `FlowState` slice shape owned by `flowSlice`.
 *
 * All components, selectors, and slices work with {@link FlowRow} (defined in
 * `types/projects.ts`) — never with raw `Flow` objects.
 */

import type { FlowRow } from './projects';

// ── API wire types ───────────────────────────────────────────────────────

/**
 * Paginated response envelope returned by:
 * - `GET /api/projects/:id/flows`
 * - `GET /api/flows`
 *
 * Each item in `flows` may include a {@link JobRunSummary} when the flow has been run.
 */
export interface PaginatedFlowResponse {
  /** Flows on the current page. */
  flows: Flow[];
  /** Total number of matching flows across all pages. */
  total_count: number;
  /** Zero-based offset of this page. */
  offset: number;
  /** Maximum number of items per page. */
  limit: number;
  /** URL for the first page. */
  first: string;
  /** URL for the next page, or null if this is the last page. */
  next: string | null;
  /** URL for the previous page, or null if this is the first page. */
  prev: string | null;
}

/**
 * Nested Elyra pipeline definition stored inside a {@link Flow}.
 *
 * The schema is intentionally loose (`[key: string]: unknown`) because the
 * Canvas editor owns its full structure. Only the top-level fields consumed
 * by the UI are typed explicitly.
 */
export interface FlowDefinition {
  /** Document type identifier */
  doc_type?: string;
  /** Version of the flow definition schema */
  version?: string;
  /** JSON schema URL for validation */
  json_schema?: string;
  /** Unique identifier for this definition */
  id?: string;
  /** ID of the primary pipeline to execute */
  primary_pipeline?: string;
  /** Array of pipeline objects containing nodes and configuration */
  pipelines?: unknown[];
  /** Schema definitions for data validation */
  schemas?: unknown[];
  /** Additional dynamic properties */
  [key: string]: unknown;
}

/**
 * Run summary returned inline with each flow by the list-flows endpoint
 * (`GET /api/projects/:id/flows`).
 *
 * Present when the flow has been run at least once; `null` otherwise.
 * Never returned by `GET /api/flows/:id` (single-flow fetch).
 *
 * `status_counts` is a map of API status string → number of runs in that state,
 * e.g. `{ "Completed": 3, "Failed": 1 }`. The full set of API status strings is
 * documented in `flow-mapper.ts` (`ERROR_STATUSES`, `WARNING_STATUSES`, `RUNNING_STATUSES`).
 */
export interface JobRunSummary {
  /** Total number of job runs for this flow. */
  total_runs: number;
  /** ID of the most recent job run. */
  last_run_id: string | null;
  /** Status string of the most recent job run (e.g. "Completed", "Failed"). */
  last_run_status: string | null;
  /** Unix epoch seconds when the last run started. */
  last_run_start_time: number | null;
  /** Map of status string → count across all runs. */
  status_counts: Record<string, number>;
}

/**
 * A single flow object as returned by the BFF API.
 *
 * All fields are optional because the same type is used for both full responses
 * (GET /api/flows/:id) and partial list items (GET /api/projects/:id/flows).
 *
 * **Consumers must use {@link FlowRow} for UI rendering** — convert via
 * `flowMapper.fromResponse()`. Only `flow-mapper.ts` should read `Flow` fields directly.
 */
export interface Flow {
  /** Type of container (e.g., "project") */
  container_kind?: string;
  /** ID of the containing project or workspace */
  container_id?: string;
  /** Human-readable name of the flow */
  name?: string;
  /** Detailed description of the flow's purpose */
  description?: string;
  /** Nested pipeline definition with nodes and configuration */
  definition?: FlowDefinition;
  /** Array of tags for categorization */
  tags?: string[];
  /** Whether the flow is hidden from UI */
  is_hidden?: boolean;
  /** Version string for the flow */
  flow_version?: string;
  /** Unique identifier for this flow */
  flow_id?: string;
  /** Associated job ID if flow is part of a job */
  job_id?: string | null;
  /** ISO 8601 timestamp of creation */
  created_on?: string;
  /** User ID who created the flow */
  created_by?: string;
  /** ISO 8601 timestamp of last modification */
  modified_on?: string;
  /** User ID who last modified the flow */
  modified_by?: string;
  /** API endpoint URL for this flow */
  href?: string;
  /**
   * Run summary injected by the list-flows endpoint.
   * Null when the flow has never been run, or when fetched via GET /api/flows/:id.
   */
  job_run_summary?: JobRunSummary | null;
  /** Additional dynamic properties */
  [key: string]: unknown;
}

// ── UI form types ────────────────────────────────────────────────────────

/**
 * Form values collected from the **Create Flow** modal (`CreateFlowTearsheet`).
 *
 * Converted into a `POST /api/flows` payload via `flowMapper.toCreateRequest()`.
 * Lives in `@/types` and re-exported from `CreateFlowTearsheet` for backward compat.
 */
export interface CreateFlowFormValues {
  /** Human-readable flow name. Required — Create is disabled until filled. */
  name: string;
  /** Optional free-text description of the flow. */
  description: string;
  /** Zero or more tag strings to attach to the flow. */
  tags: string[];
}

/**
 * Storage backend for intermediate data produced during flow execution.
 * - `'container'` — persisted to the project container (default).
 * - `'memory'`    — kept in-process; faster but lost if the executor restarts.
 */
export type IntermediateDataStorageType = 'container' | 'memory';

/**
 * Canvas run-time settings surfaced in the Flow Run Properties panel.
 * Stored in Redux at `state.flow.flowRunProperties` and sent to the job-run endpoint.
 */
export interface FlowRunProperties {
  /** Process only documents added or changed since the last run. */
  enableIncrementalProcessing: boolean;
  /**
   * When incremental processing is on, keep store records for documents that
   * have been deleted from the source since the last run.
   */
  retainRecordsForDeletedDocuments: boolean;
  /** Validate the flow definition against registered operators before executing. */
  validateFlow: boolean;
  /** Capture and display operator output snapshots after each node executes. */
  enableNodeOutputPreview: boolean;
  /** Where intermediate operator outputs are staged during execution. */
  intermediateDataStorage: IntermediateDataStorageType;
}

/**
 * Redux state slice for flow data. Mounted at `state.flow`, owned by `flowSlice`.
 *
 * Two parallel data shapes co-exist:
 * - **`items`** — flat map of `flow_id → FlowRow` display objects. Written by
 *   `ProjectDetail` (list fetch) and `FlowDetail` (deep-link single fetch); read
 *   by `FlowsTable` and `FlowDetail`. Follows the same `items` pattern as `projectsSlice`.
 * - **`currentFlow`** — the full `Flow` object including the `definition` blob.
 *   Written and read exclusively by the Canvas editor. Retained unchanged so
 *   Canvas continues to work without modification.
 *
 * `loading` and `error` cover both the list fetch and the single-flow bootstrap.
 */
export interface FlowState {
  /**
   * Map of `flow_id` → {@link FlowRow} display objects.
   * Written by `ProjectDetail` and `FlowDetail`; read by both pages and `FlowsTable`.
   */
  items: Record<string, FlowRow>;
  /**
   * The full active flow (with nested `definition`) used by the Canvas editor.
   * Null when no flow is open in Canvas.
   */
  currentFlow: Flow | null;
  /** Canvas run-time settings — see {@link FlowRunProperties}. */
  flowRunProperties: FlowRunProperties;
  /** True while any flows API request is in-flight. */
  loading: boolean;
  /** Error message from the last failed flows request, or null. */
  error: string | null;
}
