/**
 * Canvas-related type definitions
 */

import type { ContextMenuEntry, CtxMenuHandlerSource } from '@elyra/canvas';

export type CanvasContextMenuEntry = ContextMenuEntry;

/**
 * Handler function for customizing context menus in the canvas.
 * Called when a user right-clicks on canvas elements (nodes, comments, canvas).
 *
 * @param source - Information about what was clicked (type, id, etc.)
 * @param defaultMenu - The default menu entries provided by Elyra
 * @returns Array of menu entries to display
 *
 * @example
 * ```typescript
 * const contextMenuHandler: ContextMenuHandler = (source, defaultMenu) => {
 *   if (source.type === 'node') {
 *     return [
 *       { action: 'edit', label: 'Edit', enable: true },
 *       { action: 'delete', label: 'Delete', enable: true }
 *     ];
 *   }
 *   return defaultMenu;
 * };
 * ```
 */
export type ContextMenuHandler = (
  source: CtxMenuHandlerSource,
  defaultMenu: ContextMenuEntry[]
) => ContextMenuEntry[];

/**
 * Handler function for edit actions triggered from toolbar or context menu.
 * Receives action data with editType and additional properties.
 *
 * @param data - Action data object containing editType and other properties
 * @param data.editType - The type of edit action (e.g., 'save', 'run', 'undo')
 *
 * @remarks
 * Uses `unknown` type for index signature to maintain compatibility with Elyra's
 * type system. TypeScript doesn't allow mixing specific properties with
 * `[key: string]: object` index signatures.
 *
 * @example
 * ```typescript
 * const editActionHandler: EditActionHandler = (data) => {
 *   if (data.editType === 'save') {
 *     savePipeline();
 *   } else if (data.editType === 'run') {
 *     runPipeline();
 *   }
 * };
 * ```
 */
export type EditActionHandler = (data: { editType?: string; [key: string]: unknown }) => void;

/**
 * Handler function for click actions on canvas elements.
 * Called when user clicks on nodes, comments, or canvas.
 *
 * @param source - Information about what was clicked
 *
 * @remarks
 * Uses `unknown` type because Elyra's ClickActionSource is a complex union type.
 * Type should be narrowed in the implementation based on actual usage.
 *
 * @example
 * ```typescript
 * const clickActionHandler: ClickActionHandler = (source) => {
 *   console.log('Canvas element clicked:', source);
 * };
 * ```
 */
export type ClickActionHandler = (source: unknown) => void;
