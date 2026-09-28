/**
 * Input Features Tab — shown in the Properties Panel "Input" tab.
 *
 * Displays features flowing into the selected node from upstream operators,
 * grouped by the source node that introduced them.
 * The expand (↗) button opens a Tearsheet (ibm-products) with a Description column added.
 */

import React, { useMemo, useState } from 'react';
import { Button } from '@carbon/react';
import { NoDataEmptyState, Tearsheet } from '@carbon/ibm-products';
import { Maximize } from '@carbon/icons-react';
import { SharedDataTable } from '@/components/common/SharedDataTable';
import type { SharedDataTableHeader, SharedDataTableRow } from '@/components/common/SharedDataTable';
import type { FeatureAttributes } from '@/types';
import styles from './FeaturesTab.module.scss';

interface InputFeaturesTabProps {
  nodeId: string;
  inputFeatures: Record<string, FeatureAttributes>;
  pipelineNodes: Array<{ id: string; app_data?: { ui_data?: { label?: string } } }>;
  isLoading: boolean;
}

// Compact panel headers (no Description column — not enough width)
const PANEL_HEADERS: SharedDataTableHeader[] = [
  { key: 'name', header: 'Input feature' },
  { key: 'columnName', header: 'Column name' },
  { key: 'type', header: 'Type' },
];

// Expanded tearsheet headers — adds Description
const EXPANDED_HEADERS: SharedDataTableHeader[] = [
  { key: 'name', header: 'Input feature' },
  { key: 'columnName', header: 'Column name' },
  { key: 'description', header: 'Description' },
  { key: 'type', header: 'Type' },
];

const INPUT_EMPTY_STATE = (
  <NoDataEmptyState
    title="No input features available"
    subtitle="There are currently no input features for this node."
    size="sm"
  />
);

export function InputFeaturesTab({
  nodeId,
  inputFeatures,
  pipelineNodes,
  isLoading,
}: InputFeaturesTabProps): React.JSX.Element {
  const [isExpanded, setIsExpanded] = useState(false);

  const nodeLabels = useMemo(() => {
    const map: Record<string, string> = {};
    for (const n of pipelineNodes) {
      map[n.id] = n.app_data?.ui_data?.label ?? n.id;
    }
    return map;
  }, [pipelineNodes]);

  const rows = useMemo((): SharedDataTableRow[] => {
    const featureList = Object.values(inputFeatures);
    if (!featureList.length) { return []; }

    const groups: Record<string, FeatureAttributes[]> = {};
    for (const feature of featureList) {
      const srcId = feature.node_id ?? 'unknown';
      groups[srcId] ??= [];
      groups[srcId].push(feature);
    }

    // Current node's group first, remaining in natural order
    const sortedNodeIds = Object.keys(groups).sort((a, b) =>
      a === nodeId ? -1 : b === nodeId ? 1 : 0
    );

    const result: SharedDataTableRow[] = [];
    let groupIdx = 0;
    for (const nId of sortedNodeIds) {
      const features = groups[nId];
      const label = nodeLabels[nId] ?? nId;
      // Group header row
      result.push({
        id: `header-${groupIdx}`,
        name: label,
        columnName: '-',
        description: '-',
        type: '',
        _isGroupHeader: true,
        _nodeName: label,
      });
      for (const f of features) {
        result.push({
          id: `feature-${groupIdx}-${f.name}`,
          name: f.name,
          columnName: f.name,
          description: f.description ?? '',
          type: f.type,
          _isGroupHeader: false,
          _nodeName: label,
        });
      }
      groupIdx++;
    }
    return result;
  }, [inputFeatures, nodeLabels, nodeId]);

  const renderCellFn = (
    cell: { id: string; value: React.ReactNode; info: { header: string } },
    row: SharedDataTableRow
  ): React.ReactNode => {
    if (row._isGroupHeader) {
      if (cell.info.header === 'name') {
        return <span className={styles.groupHeaderLabel}>{String(row.name)}</span>;
      }
      return '-';
    }
    return undefined; // default rendering
  };

  return (
    <div className={styles.featuresTab}>
      <p className={styles.tabDescription}>
        Features added by upstream nodes in the flow that are available for this node.
      </p>
      <SharedDataTable
        headers={PANEL_HEADERS}
        rows={rows}
        searchable
        searchKeys={['name', '_nodeName']}
        searchPlaceholder="Search features"
        loading={isLoading}
        emptyState={INPUT_EMPTY_STATE}
        size="lg"
        horizontalScroll
        renderCell={renderCellFn}
        renderToolbarActions={() => (
          <Button
            kind="ghost"
            size="md"
            renderIcon={Maximize}
            iconDescription="Expand table"
            hasIconOnly
            onClick={() => { setIsExpanded(true); }}
            className={styles.expandButton}
          />
        )}
      />

      <Tearsheet
        open={isExpanded}
        onClose={() => { setIsExpanded(false); }}
        title="Input features"
        description="Review the list of features added by upstream nodes in the flow that are available for this node."
        actions={[
          {
            label: 'Close',
            kind: 'secondary' as const,
            onClick: () => { setIsExpanded(false); },
          },
        ]}
        hasCloseIcon
        closeIconDescription="Close"
      >
        <div className={styles.tearsheetTableWrapper}>
          <SharedDataTable
            key={String(isExpanded)}
            headers={EXPANDED_HEADERS}
            rows={rows}
            searchable
            searchKeys={['name', '_nodeName']}
            searchPlaceholder="Search features"
            loading={isLoading}
            emptyState={INPUT_EMPTY_STATE}
            size="lg"
            horizontalScroll
            renderCell={renderCellFn}
          />
        </div>
      </Tearsheet>
    </div>
  );
}
