/**
 * Carbon Charts CardNode wrapper for Elyra Canvas nodes
 * 
 * @module components/ElyraCanvas/CardNodeWrapper
 */

import React from 'react';
import {
  CardNode,
  CardNodeColumn,
  CardNodeSubtitle,
  CardNodeTitle,
} from '@carbon/charts-react';
import { getIconForOperator } from '@/utils/paletteEnhancer';

/**
 * Node data structure expected by CardNodeWrapper
 */
interface NodeData {
  op: string;
  label: string;
  parameters?: {
    display_label?: string;
  };
  app_data: {
    react_nodes_data: {
      color: string;
      cardDescription: string;
    };
  };
}

interface CardNodeWrapperProps {
  nodeData: NodeData;
}

/**
 * CardNode wrapper component for rendering Elyra Canvas nodes
 * using Carbon Charts React CardNode components.
 * 
 * @param props - Component props
 * @param props.nodeData - Node data from Elyra Canvas
 * @returns JSX element containing the styled CardNode
 */
export function CardNodeWrapper({ nodeData }: CardNodeWrapperProps): React.JSX.Element {
  const color = nodeData?.app_data?.react_nodes_data?.color;
  const displayLabel = nodeData?.parameters?.display_label ?? nodeData?.label;
  const cardDescription = nodeData?.app_data?.react_nodes_data?.cardDescription ?? '';

  return (
    <div className="card-node">
      <CardNode color={color}>
        <CardNodeColumn>
          {getIconForOperator(nodeData.op)}
        </CardNodeColumn>
        <CardNodeColumn>
          <CardNodeTitle>{displayLabel}</CardNodeTitle>
          <CardNodeSubtitle>{cardDescription}</CardNodeSubtitle>
        </CardNodeColumn>
      </CardNode>
    </div>
  );
}