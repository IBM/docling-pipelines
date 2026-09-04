/**
 * @file elyra.ts
 *
 * Shared TypeScript interface for the Elyra `CommonProperties` controller
 * instance injected into all custom panel components via `CommonPropertiesPanelWrapper`.
 *
 * Elyra does not export a public TypeScript type for its controller, so this
 * interface documents only the methods actually used across the properties panels.
 * Typed as `unknown` returns where Elyra's runtime shape varies by parameter.
 */

/**
 * Minimal interface for the Elyra CommonProperties controller.
 *
 * Used as the type for the `controller` prop in all custom panel components
 * (e.g. `AnnotationFilterPanelBody`, `DocumentClassifierPanelBody`, etc.)
 * instead of `any`.
 */
export interface ElyraController {
  /** Returns the panel's `appData` object containing node context. */
  getAppData(): Record<string, unknown>;
  /**
   * Reads the current value of a node parameter.
   *
   * @param ref - Object with `name` set to the parameter key.
   * @returns The stored value, or `undefined` if not set.
   */
  getPropertyValue(ref: { name: string }): unknown;
  /**
   * Writes a value to a node parameter, persisted when the user saves.
   *
   * @param ref - Object with `name` set to the parameter key.
   * @param value - The value to store.
   */
  updatePropertyValue(ref: { name: string }, value: unknown): void;
  /**
   * Enables or disables the Save button in the properties flyout.
   * Call with `false` to re-enable Save after a custom panel writes a value
   * via `updatePropertyValue` — Elyra only fires `propertyListener` for its
   * own bound form controls, so custom panels must unlock Save explicitly.
   *
   * @param disabled - `true` to disable, `false` to enable.
   */
  setSaveButtonDisable(disabled: boolean): void;
}
