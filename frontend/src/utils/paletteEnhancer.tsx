/**
 * Palette enhancement utilities for adding visual elements to operator palette
 *
 * @module utils/paletteEnhancer
 */

import React from 'react';
import {
  DocumentDownload,
  TextIndent,
  Data_2,
  IbmCloudDirectLink_1DedicatedHosting,
  DataBaseAlt,
  WorkspaceImport,
  SettingsEdit,
  Category,
  Filter,
  DocumentSecurity,
  ReadMe,
  Language,
  Document,
  LicenseMaintenance,
  Analytics,
  UserAccessLocked,
  RuleDataQuality,
  DocumentRequirements,
  Shuffle,
  Merge,
  Debug,
} from '@carbon/icons-react';
import { yellow } from '@carbon/colors';
import { log4js, logUtil } from './logger';
import type { PaletteData } from '../types/palette';
import { NodeOperator, CATEGORY_COLORS } from '../constants/operators';

const logger = log4js.getLogger('paletteEnhancer');

/**
 * Icon map for O(1) lookup performance.
 * Maps operator names to their Carbon Design System icons.
 *
 * @constant
 * @type {Record<string, React.ReactElement>}
 */
const OPERATOR_ICON_MAP: Record<string, React.ReactElement> = {
  [NodeOperator.INGEST]: <WorkspaceImport size={20} />,
  [NodeOperator.INGEST_SOURCE]: <WorkspaceImport size={20} />,
  [NodeOperator.EXTRACT]: <DocumentDownload size={20} />,
  [NodeOperator.CHUNKER]: <TextIndent size={20} />,
  [NodeOperator.EMBEDDINGS]: <Data_2 size={20} />,
  [NodeOperator.DEDUPLICATION]: <IbmCloudDirectLink_1DedicatedHosting size={20} />,
  [NodeOperator.VECTORDB]: <DataBaseAlt size={20} />,
  [NodeOperator.DOCUMENT_SET]: <DocumentRequirements size={20} />,
  [NodeOperator.DOCUMENT_CLASSIFIER]: <Category size={20} />,
  [NodeOperator.LANG_DETECT]: <Language size={20} />,
  [NodeOperator.SQL_FILTER]: <Filter size={20} />,
  [NodeOperator.REDACTION]: <DocumentSecurity size={20} />,
  [NodeOperator.READABILITY]: <ReadMe size={20} />,
  [NodeOperator.ENTITY_CURATION]: <LicenseMaintenance size={20} />,
  [NodeOperator.ML_ENRICHMENT]: <Analytics size={20} />,
  [NodeOperator.DOC_QUALITY]: <Document size={20} />,
  [NodeOperator.ACL_OPERATOR]: <UserAccessLocked size={20} />,
  [NodeOperator.NOOP]: <Debug size={20} />,
  [NodeOperator.PII_AND_HAP]: <RuleDataQuality size={20} />,
  [NodeOperator.BRANCHING]: <Shuffle size={20} />,
  [NodeOperator.MERGING]: <Merge size={20} />,
};

/**
 * Default icon for unmapped operators.
 *
 * @constant
 * @type {React.ReactElement}
 */
const DEFAULT_ICON = <SettingsEdit size={20} />;

/**
 * Gets icon for operator with warning for unmapped operators.
 *
 * @param {string} op - The operator name
 * @returns {React.ReactElement} React element containing the appropriate Carbon icon
 *
 * @remarks
 * Logs a warning when an unmapped operator is encountered to help identify missing icon mappings during development.
 */
export const getIconForOperator = (op: string): React.ReactElement => {
  const icon = OPERATOR_ICON_MAP[op];

  if (!icon) {
    logUtil.warn({
      logger,
      message: 'Unmapped operator type, using default icon',
      data: { operator: op },
    });
    return DEFAULT_ICON;
  }

  return icon;
};

/**
 * Enhances palette data by adding Carbon Design System icons and category colors.
 *
 * Transforms the static palette JSON by adding visual elements required by Elyra Canvas:
 * - React icon elements for each operator (via OPERATOR_ICON_MAP)
 * - Category-specific colors from Carbon Design System (via CATEGORY_COLORS)
 * - Card descriptions for palette UI
 *
 * @param {PaletteData} paletteData - The base palette data from JSON
 * @returns {PaletteData} Enhanced palette data with icons and colors
 *
 * @example
 * ```typescript
 * import operatorPaletteData from '@/data/operatorPalette.json';
 *
 * const enhancedPalette = enhancePalette(operatorPaletteData as PaletteData);
 * canvasController.setPipelineFlowPalette(enhancedPalette);
 * ```
 *
 * @remarks
 * - Icons are mapped based on operator name (op field) using O(1) lookup
 * - Colors are assigned based on category ID from CATEGORY_COLORS constant
 * - Falls back to yellow[50] for unmapped categories
 * - Logs warnings for unmapped operators to aid development
 * - This transformation typically happens once at component initialization
 *
 * @see {@link OPERATOR_ICON_MAP} for icon mappings
 * @see {@link CATEGORY_COLORS} for color mappings
 */
export const enhancePalette = (paletteData: PaletteData): PaletteData => ({
  ...paletteData,
  categories: paletteData.categories.map((category) => ({
    ...category,
    node_types: category.node_types.map((nodeType) => {
      const icon = getIconForOperator(nodeType.op);
      return {
        ...nodeType,
        app_data: {
          ...nodeType.app_data,
          react_nodes_data: {
            color: CATEGORY_COLORS[category.id] ?? yellow[50],
            cardDescription: category.label ?? '',
          },
          ui_data: {
            ...nodeType.app_data.ui_data,
            image: icon,
          },
        },
      };
    }),
  })),
});
