/**
 * @file RequiredParamTooltip
 *
 * Drop-in replacement for the `DefinitionTooltip` + label pattern used in all
 * properties panels. Automatically appends "(required)" to the label
 * text when the parameter is marked `required: true` in the operator metadata.
 *
 * Only use this for top-level operator attributes. For nested params (e.g.
 * text_extraction sub-fields in the Extract panel) use a plain DefinitionTooltip.
 */

import React from 'react';
import { DefinitionTooltip } from '@carbon/react';
import type { OperatorFeature } from '@/types';

interface RequiredParamTooltipProps {
  /** Attribute key used to look up `required` in `nodeAttributes` */
  paramId: string;
  /** Top-level attributes map for the current operator */
  nodeAttributes: Record<string, OperatorFeature>;
  /** Tooltip definition text shown on hover */
  definition: string;
  /** Tooltip alignment */
  align?: React.ComponentProps<typeof DefinitionTooltip>['align'];
  /** The visible field label */
  children: React.ReactNode;
}

export function RequiredParamTooltip({
  paramId,
  nodeAttributes,
  definition,
  align = 'right',
  children,
}: RequiredParamTooltipProps): React.JSX.Element {
  const isRequired = nodeAttributes[paramId]?.required === true;
  const label = isRequired ? <>{children} (required)</> : children;

  return (
    <DefinitionTooltip definition={definition} openOnHover align={align}>
      {label}
    </DefinitionTooltip>
  );
}
