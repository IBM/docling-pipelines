/**
 * @file DocumentSet operator configuration panel body.
 *
 * Renders the configuration UI for the `document_set` operator node.
 */

import React from 'react';
import { getRequiredParamValidator } from '@/utils/requiredParamValidation';
import { RequiredParamTooltip } from '@/components/common';
import { Dropdown, TextInput } from '@carbon/react';
import type { OperatorFeature, OperatorMetadata } from '@/types';
import { NodeOperator } from '@/constants/operators';
import { JsonTextArea } from '@/components/common/JsonTextArea/JsonTextArea';
import {
  DOCUMENT_SET_ATTRIBUTE as ATTR,
  DOCUMENT_SET_LABELS as LABEL,
} from './constants';
import common from '../../CommonPropertiesPanel.module.scss';

interface DocumentSetPanelBodyProps {
  controller: any;
}

export function DocumentSetPanelBody({
  controller,
}: DocumentSetPanelBodyProps): React.JSX.Element {

  // ── Read operator attribute metadata from Redux ──
  // eslint-disable-next-line @typescript-eslint/no-unsafe-call
  const operatorMetadata = (controller?.getAppData?.()?.operatorMetadata ?? {}) as Record<string, OperatorMetadata>;
  const nodeAttributes: Record<string, OperatorFeature> = operatorMetadata[NodeOperator.DOCUMENT_SET]?.attributes ?? {};

  // ── Data backend: valid values from metadata, static fallback ────────
  const dataBackendValidValues = (nodeAttributes[ATTR.DATA_BACKEND] as Record<string, unknown> | undefined)?.valid_values;
  const dataBackendItems: string[] = Array.isArray(dataBackendValidValues)
    ? (dataBackendValidValues as string[])
    : ['duckdb', 'filesystem'];

  // ── Read current saved values from Elyra, falling back to backend defaults ──

  const documentSetName: string =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.DOCUMENT_SET_NAME }) as string | undefined)
    ?? (nodeAttributes[ATTR.DOCUMENT_SET_NAME]?.default as string | undefined)
    ?? '';

  const description: string =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.DESCRIPTION }) as string | undefined)
    ?? (nodeAttributes[ATTR.DESCRIPTION]?.default as string | undefined)
    ?? '';

  const documentSetId: string =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.DOCUMENT_SET_ID }) as string | undefined)
    ?? (nodeAttributes[ATTR.DOCUMENT_SET_ID]?.default as string | undefined)
    ?? '';

  const databasePath: string =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.DATABASE_PATH }) as string | undefined)
    ?? (nodeAttributes[ATTR.DATABASE_PATH]?.default as string | undefined)
    ?? '';

  const dataBackend: string =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.DATA_BACKEND }) as string | undefined)
    ?? (nodeAttributes[ATTR.DATA_BACKEND]?.default as string | undefined)
    ?? 'duckdb';

  const metadataStored =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.METADATA }) as Record<string, unknown> | null | undefined)
    ?? null;

  // ── Required param validation ─────────────────────────────────────────────
  const validate = getRequiredParamValidator(nodeAttributes);
  const documentSetNameValidation = validate(ATTR.DOCUMENT_SET_NAME, documentSetName);
  const descriptionValidation = validate(ATTR.DESCRIPTION, description);
  const documentSetIdValidation = validate(ATTR.DOCUMENT_SET_ID, documentSetId);
  const databasePathValidation = validate(ATTR.DATABASE_PATH, databasePath);
  const dataBackendValidation = validate(ATTR.DATA_BACKEND, dataBackend);

  return (
    <div className={common.commonPropertiesPanelBody}>

      {/* ── Document set name (required) ────────────────────────────── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.DOCUMENT_SET_NAME}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.DOCUMENT_SET_NAME]?.description ?? 'Name of the document set to create or update.'}
          >
            {LABEL.DOCUMENT_SET_NAME}
          </RequiredParamTooltip>
        </div>
        <TextInput
          id="document_set_name"
          labelText={LABEL.DOCUMENT_SET_NAME}
          hideLabel
          required
          placeholder="research_papers"
          value={documentSetName}
          invalid={documentSetName.trim() === '' || documentSetNameValidation.isInvalid}
          invalidText="This is a required parameter."
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            // eslint-disable-next-line @typescript-eslint/no-unsafe-call
            controller?.updatePropertyValue?.({ name: ATTR.DOCUMENT_SET_NAME }, e.target.value);
          }}
        />
      </div>

      {/* ── Document set description ─────────────────────────────────────────────── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.DESCRIPTION}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.DESCRIPTION]?.description ?? 'Human-readable description of the document set.'}
          >
            {LABEL.DESCRIPTION}
          </RequiredParamTooltip>
        </div>
        <TextInput
          id="description"
          labelText={LABEL.DESCRIPTION}
          hideLabel
          placeholder="Processed research papers"
          value={description}
          invalid={descriptionValidation.isInvalid}
          invalidText={descriptionValidation.errorMessage}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            // eslint-disable-next-line @typescript-eslint/no-unsafe-call
            controller?.updatePropertyValue?.({ name: ATTR.DESCRIPTION }, e.target.value);
          }}
        />
      </div>

      {/* ── Metadata (JSON) ──────────────────────────────────────────── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.METADATA}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.METADATA]?.description ?? 'Arbitrary JSON object stored as document set metadata.'}
          >
            {LABEL.METADATA}
          </RequiredParamTooltip>
        </div>
        <JsonTextArea
          id="metadata-param"
          labelText={LABEL.METADATA}
          storedValue={metadataStored}
          placeholder='{"department": "finance", "year": 2024}'
          onChange={(value) => {
            // eslint-disable-next-line @typescript-eslint/no-unsafe-call
            controller?.updatePropertyValue?.({ name: ATTR.METADATA }, value);
          }}
        />
      </div>

      {/* ── Document set ID ──────────────────────────────────────────── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.DOCUMENT_SET_ID}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.DOCUMENT_SET_ID]?.description ?? 'UUID of an existing document set to update instead of creating a new one.'}
          >
            {LABEL.DOCUMENT_SET_ID}
          </RequiredParamTooltip>
        </div>
        <TextInput
          id="document_set_id"
          labelText={LABEL.DOCUMENT_SET_ID}
          hideLabel
          placeholder="123e4567-e89b-12d3-a456-426614174000"
          value={documentSetId}
          invalid={documentSetIdValidation.isInvalid}
          invalidText={documentSetIdValidation.errorMessage}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            // eslint-disable-next-line @typescript-eslint/no-unsafe-call
            controller?.updatePropertyValue?.({ name: ATTR.DOCUMENT_SET_ID }, e.target.value);
          }}
        />
      </div>

      {/* ── Database path ─────────────────────────────────────────────── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.DATABASE_PATH}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.DATABASE_PATH]?.description ?? 'File path for the DuckDB database.'}
          >
            {LABEL.DATABASE_PATH}
          </RequiredParamTooltip>
        </div>
        <TextInput
          id="database_path"
          labelText={LABEL.DATABASE_PATH}
          hideLabel
          placeholder="data/duckdb/document_sets.duckdb"
          value={databasePath}
          invalid={databasePathValidation.isInvalid}
          invalidText={databasePathValidation.errorMessage}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            // eslint-disable-next-line @typescript-eslint/no-unsafe-call
            controller?.updatePropertyValue?.({ name: ATTR.DATABASE_PATH }, e.target.value);
          }}
        />
      </div>

      {/* ── Data backend ─────────────────────────────────────────────── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.DATA_BACKEND}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.DATA_BACKEND]?.description ?? 'Data store backend for PyArrow table data.'}
          >
            {LABEL.DATA_BACKEND}
          </RequiredParamTooltip>
        </div>
        <Dropdown
          id="data_backend"
          titleText={LABEL.DATA_BACKEND}
          hideLabel
          label="Select backend"
          items={dataBackendItems}
          selectedItem={dataBackend}
          onChange={({ selectedItem }: { selectedItem: string | null }) => {
            if (selectedItem) {
              // eslint-disable-next-line @typescript-eslint/no-unsafe-call
              controller?.updatePropertyValue?.({ name: ATTR.DATA_BACKEND }, selectedItem);
            }
          }}
          invalid={dataBackendValidation.isInvalid}
          invalidText={dataBackendValidation.errorMessage}
        />
      </div>
    </div>
  );
}
