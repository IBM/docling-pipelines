/**
 * @fileoverview Assets-related type definitions for Redux state management.
 * Defines the structure of flows and job runs for the assets state slice.
 * Projects have been extracted to `ProjectsState` in `types/projects.ts`.
 */

/**
 * Represents a flow asset in the assets management system.
 * Lightweight representation of flows for listing and selection.
 */
export interface FlowAsset {
  /** Unique identifier for the flow */
  flowId?: string;
  /** Human-readable name of the flow */
  name?: string;
  /** Version string for the flow */
  version?: string;
  /** Current status of the flow (e.g., "active", "draft") */
  status?: string;
  /** Additional dynamic properties */
  [key: string]: unknown;
}

/**
 * Represents a job run asset in the assets management system.
 * Lightweight representation of job runs for listing and selection.
 */
export interface JobRunAsset {
  /** Unique identifier for the job run */
  jobRunId?: string;
  /** ID of the parent job */
  jobId?: string;
  /** Current execution status */
  status?: string;
  /** Historical execution records */
  executionHistory?: any[];
  /** Additional dynamic properties */
  [key: string]: unknown;
}

/**
 * Redux state slice for managing shared navigation assets.
 * Stores flows and job runs with selection tracking for UI navigation.
 * Projects are owned by `ProjectsState` / `projectsSlice`.
 */
export interface AssetsState {
  /** Map of flow IDs to their asset data. */
  flows: Record<string, FlowAsset>;
  /** Map of job run IDs to their asset data. */
  jobRuns: Record<string, JobRunAsset>;
  /** Currently selected flow ID for navigation. */
  selectedFlowId: string | null;
  /** Currently selected job run ID for navigation. */
  selectedJobRunId: string | null;
}
