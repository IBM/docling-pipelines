/**
 * @file MlEnrichment.tsx
 *
 * Configuration panel body for the `ml_enrichment` operator node.
 *
 * **Data flow**:
 * - `controller.getAppData().operatorMetadata` — backend attribute metadata (descriptions, defaults)
 * - `controller.getPropertyValue({ name })` — reads saved node parameter
 * - `controller.updatePropertyValue({ name }, value)` — writes node parameter on change
 */

import React from 'react';
import { getRequiredParamValidator } from '@/utils/requiredParamValidation';
import { RequiredParamTooltip } from '@/components/common';
import { TextInput } from '@carbon/react';
import type { OperatorFeature, OperatorMetadata } from '@/types';
import { NodeOperator } from '@/constants/operators';
import {
  ML_ENRICHMENT_ATTRIBUTE as ATTR,
  ML_ENRICHMENT_LABELS as LABEL,
} from './constants';
import common from '../../CommonPropertiesPanel.module.scss';

interface MlEnrichmentPanelBodyProps {
  controller: any;
}

export function MlEnrichmentPanelBody({
  controller,
}: MlEnrichmentPanelBodyProps): React.JSX.Element {
  // ── Read operator attribute metadata ──────────────────────────────────
  // eslint-disable-next-line @typescript-eslint/no-unsafe-call
  const operatorMetadata = (controller?.getAppData?.()?.operatorMetadata ?? {}) as Record<string, OperatorMetadata>;
  const nodeAttributes: Record<string, OperatorFeature> = operatorMetadata[NodeOperator.ML_ENRICHMENT]?.attributes ?? {};

  // ── Read current saved values, falling back to backend defaults ────────
  const docColumn: string =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.DOC_COLUMN }) as string | undefined)
    ?? (nodeAttributes[ATTR.DOC_COLUMN]?.default as string | undefined)
    ?? 'content';

  const langColumn: string =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.LANG_COLUMN }) as string | undefined)
    ?? (nodeAttributes[ATTR.LANG_COLUMN]?.default as string | undefined)
    ?? 'lang_name';

  const outputColumnPrefix: string =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.OUTPUT_COLUMN_PREFIX }) as string | undefined)
    ?? (nodeAttributes[ATTR.OUTPUT_COLUMN_PREFIX]?.default as string | undefined)
    ?? '';

  // ── Required param validation ─────────────────────────────────────────────
  const validate = getRequiredParamValidator(nodeAttributes);
  const docColumnValidation = validate(ATTR.DOC_COLUMN, docColumn);
  const langColumnValidation = validate(ATTR.LANG_COLUMN, langColumn);
  const outputColumnPrefixValidation = validate(ATTR.OUTPUT_COLUMN_PREFIX, outputColumnPrefix);

  return (
    <div className={common.commonPropertiesPanelBody}>

      {/* ── Document content column ─────────────────────────────────── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.DOC_COLUMN}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.DOC_COLUMN]?.description ?? ''}
          >
            {LABEL.DOC_COLUMN}
          </RequiredParamTooltip>
        </div>
        <TextInput
          id="doc_column"
          labelText={LABEL.DOC_COLUMN}
          hideLabel
          value={docColumn}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            // eslint-disable-next-line @typescript-eslint/no-unsafe-call
            controller?.updatePropertyValue?.({ name: ATTR.DOC_COLUMN }, e.target.value);
          }}
          invalid={docColumnValidation.isInvalid}
          invalidText={docColumnValidation.errorMessage}
        />
      </div>

      {/* ── Language column ──────────────────────────────────────────── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.LANG_COLUMN}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.LANG_COLUMN]?.description ?? ''}
          >
            {LABEL.LANG_COLUMN}
          </RequiredParamTooltip>
        </div>
        <TextInput
          id="lang_column"
          labelText={LABEL.LANG_COLUMN}
          hideLabel
          value={langColumn}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            // eslint-disable-next-line @typescript-eslint/no-unsafe-call
            controller?.updatePropertyValue?.({ name: ATTR.LANG_COLUMN }, e.target.value);
          }}
          invalid={langColumnValidation.isInvalid}
          invalidText={langColumnValidation.errorMessage}
        />
      </div>

      {/* ── Output column prefix ─────────────────────────────────────── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.OUTPUT_COLUMN_PREFIX}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.OUTPUT_COLUMN_PREFIX]?.description ?? ''}
          >
            {LABEL.OUTPUT_COLUMN_PREFIX}
          </RequiredParamTooltip>
        </div>
        <TextInput
          id="output_column_prefix"
          labelText={LABEL.OUTPUT_COLUMN_PREFIX}
          hideLabel
          value={outputColumnPrefix}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            // eslint-disable-next-line @typescript-eslint/no-unsafe-call
            controller?.updatePropertyValue?.({ name: ATTR.OUTPUT_COLUMN_PREFIX }, e.target.value);
          }}
          invalid={outputColumnPrefixValidation.isInvalid}
          invalidText={outputColumnPrefixValidation.errorMessage}
        />
      </div>

    </div>
  );
}
