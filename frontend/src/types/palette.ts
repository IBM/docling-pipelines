/**
 * Type definitions for Elyra Canvas operator palette
 *
 * @module types/palette
 */

import type React from 'react';

/**
 * Represents a category of operators in the palette.
 * Categories group related operators together (e.g., Ingest, Extract, Functional).
 */
export interface PaletteCategory {
  /** Unique identifier for the category */
  id: string;
  
  /** Display name of the category */
  label: string;
  
  /** Description of the category's purpose */
  description: string;
  
  /** Array of operator node types in this category */
  node_types: PaletteNodeType[];
}

/**
 * Represents an operator node type in the palette.
 * Defines the structure and metadata for a draggable operator.
 */
export interface PaletteNodeType {
  /** Unique identifier for the node type */
  id: string;
  
  /** Node type (typically 'execution_node') */
  type: string;
  
  /** Operator name/identifier (e.g., 'ingest', 'extract', 'chunker') */
  op: string;
  
  /** Input port definitions (optional) */
  inputs?: unknown[];
  
  /** Output port definitions (optional) */
  outputs?: unknown[];
  
  /** Application-specific data including UI metadata */
  app_data: {
    /** UI-specific data for rendering the node */
    ui_data: {
      /** Display label for the operator */
      label: string;
      
      /** Description of what the operator does */
      description: string;
      
      /** React icon element for the operator (added by paletteEnhancer) */
      image?: React.ReactElement;
    };
  };
}

/**
 * Root palette data structure containing all operator categories.
 * This structure follows the Elyra Pipeline Editor palette schema.
 */
export interface PaletteData {
  /** Palette schema version */
  version: string;
  
  /** Array of operator categories */
  categories: PaletteCategory[];
}
