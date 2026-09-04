/**
 * @file UI-only types for the VectorDB operator properties panel.
 *
 * Contains types used exclusively for internal rendering within the VectorDB
 * panel components. These are not part of the API contract.
 * Wire types (API response and controller-persisted shapes) live in
 * `src/types/operator.ts` and are exported from `@/types`.
 */

/** A single row in the feature-mapping table inside the VectorDB tearsheet. */
export interface FeatureMappingItem {
  feature: string;
  description: string;
  column: string;
  /** Mandatory features cannot be removed via batch action. */
  isMandatory: boolean;
}
