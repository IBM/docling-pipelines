/**
 * @file IngestSource properties panel body.
 *
 * Renders the configuration UI for the `ingest_source` operator node.
 *
 * **Data flow**:
 * - `controller.getAppData().operatorMetadata` — backend attribute metadata (descriptions, defaults)
 * - `controller.getPropertyValue({ name })` — reads saved node parameter
 * - `controller.updatePropertyValue({ name }, value)` — writes node parameter on change
 *
 * **Source locations UX** (filesystem -> `paths`, web -> `urls`):
 * For providers in `PROVIDER_SOURCE_LOCATIONS`:
 * - A dedicated `TagInput` is shown for the source locations input.
 * - The source locations key is injected into `connection_params` before
 *   persisting so the backend always sees it.
 * - The source locations key is stripped from the displayed `connection_params`
 *   TextArea so users never see it there.
 * - If the user manually types the source locations key inside the TextArea,
 *   an error directs them to the dedicated input instead.
 */

import React, { useMemo, useState } from 'react';
import {
  DefinitionTooltip,
  Dropdown,
  NumberInput,
  TextArea,
  TextInput,
  Toggle,
} from '@carbon/react';
import type { OperatorFeature, OperatorMetadata } from '@/types';
import { NodeOperator } from '@/constants/operators';
import { TagInput } from '@/components/common/TagInput/TagInput';
import {
  INGEST_SOURCE_ATTRIBUTE as ATTR,
  INGEST_SOURCE_LABELS as LABEL,
  PROVIDER_SOURCE_LOCATIONS,
} from './constants';
import common from '../../CommonPropertiesPanel.module.scss';
import { isValidJsonObject, toJsonString } from '@/utils/json';
import { getRequiredParamValidator } from '@/utils/requiredParamValidation';
import { RequiredParamTooltip } from '@/components/common';

interface IngestSourcePanelBodyProps {
  controller: any;
}

/**
 * Returns `connection_params` with the provider's source locations key removed,
 * ready to be displayed in the TextArea.
 */
function stripSourceLocationsKeyFromDisplay(raw: unknown, paramKey: string | null): string {
  if (raw === undefined || raw === null) {return '';}

  let obj: Record<string, unknown> | null = null;

  if (typeof raw === 'object' && !Array.isArray(raw)) {
    obj = raw as Record<string, unknown>;
  } else if (typeof raw === 'string') {
    try { obj = JSON.parse(raw) as Record<string, unknown>; } catch { return raw; }
  }

  if (obj === null) {return toJsonString(raw);}
  if (paramKey === null) {return JSON.stringify(obj, null, 2);}

  const { [paramKey]: _omitted, ...rest } = obj;
  return Object.keys(rest).length > 0 ? JSON.stringify(rest, null, 2) : '';
}

/**
 * Merges the provider's source locations back into `connection_params` before persisting.
 * Returns a merged object (never a string).
 */
function mergeSourceLocationsIntoParams(
  connectionParamsRaw: unknown,
  paramKey: string,
  items: string[]
): Record<string, unknown> {
  let base: Record<string, unknown> = {};

  if (typeof connectionParamsRaw === 'object' && connectionParamsRaw !== null && !Array.isArray(connectionParamsRaw)) {
    base = connectionParamsRaw as Record<string, unknown>;
  } else if (typeof connectionParamsRaw === 'string' && isValidJsonObject(connectionParamsRaw)) {
    try { base = JSON.parse(connectionParamsRaw) as Record<string, unknown>; } catch { /* keep empty */ }
  }

  return items.length > 0 ? { ...base, [paramKey]: items } : base;
}

/* eslint-disable @typescript-eslint/no-unsafe-call, @typescript-eslint/no-unsafe-member-access */
export function IngestSourcePanelBody({
  controller,
}: IngestSourcePanelBodyProps): React.JSX.Element {

  // ── Read operator attribute metadata ──
  const operatorMetadata = (controller?.getAppData?.()?.operatorMetadata ?? {}) as Record<string, OperatorMetadata>;
  const nodeAttributes: Record<string, OperatorFeature> = operatorMetadata[NodeOperator.INGEST_SOURCE]?.attributes ?? {};

  // ── Provider dropdown: items come from operator metadata ──
  const providerValidValues = (nodeAttributes[ATTR.PROVIDER] as Record<string, unknown> | undefined)?.valid_values;
  const providerItems: string[] = Array.isArray(providerValidValues) ? (providerValidValues as string[]) : [];

  // ── Read current saved values, falling back to backend defaults ──────────

  const provider = (controller?.getPropertyValue?.({ name: ATTR.PROVIDER }) as string | undefined)
    ?? (nodeAttributes[ATTR.PROVIDER]?.default as string | undefined)
    ?? '';

  // Source locations config for this provider, or null if it has no dedicated input.
  const listFieldCfg = PROVIDER_SOURCE_LOCATIONS[provider] ?? null;

  const connectionParamsRaw = controller?.getPropertyValue?.({ name: ATTR.CONNECTION_PARAMS });

  // TextArea shows `connection_params` WITHOUT the provider's source locations key.
  const connectionParamsDisplayed = useMemo(
    () => stripSourceLocationsKeyFromDisplay(connectionParamsRaw, listFieldCfg?.paramKey ?? null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [JSON.stringify(connectionParamsRaw), listFieldCfg?.paramKey]
  );

  // Extract the saved list from `connection_params`.
  const savedListItems = useMemo((): string[] => {
    if (listFieldCfg === null) {return [];}
    const { paramKey } = listFieldCfg;
    if (typeof connectionParamsRaw === 'object' && connectionParamsRaw !== null) {
      const items = (connectionParamsRaw as Record<string, unknown>)[paramKey];
      return Array.isArray(items) ? (items as string[]) : [];
    }
    if (typeof connectionParamsRaw === 'string') {
      try {
        const parsed = JSON.parse(connectionParamsRaw) as Record<string, unknown>;
        const items = parsed[paramKey];
        return Array.isArray(items) ? (items as string[]) : [];
      } catch { return []; }
    }
    return [];
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(connectionParamsRaw), listFieldCfg?.paramKey]);

  const credentialsRaw = controller?.getPropertyValue?.({ name: ATTR.CREDENTIALS });
  const credentialsStored = (credentialsRaw !== undefined && credentialsRaw !== null)
    ? toJsonString(credentialsRaw)
    : toJsonString(nodeAttributes[ATTR.CREDENTIALS]?.default);

  const maxFiles = (controller?.getPropertyValue?.({ name: ATTR.MAX_FILES }) as number | undefined)
    ?? (nodeAttributes[ATTR.MAX_FILES]?.default as number | undefined)
    ?? 100;

  const includeFilter = (controller?.getPropertyValue?.({ name: ATTR.INCLUDE_FILTER }) as string | undefined)
    ?? (nodeAttributes[ATTR.INCLUDE_FILTER]?.default as string | undefined)
    ?? '';

  const excludeFilter = (controller?.getPropertyValue?.({ name: ATTR.EXCLUDE_FILTER }) as string | undefined)
    ?? (nodeAttributes[ATTR.EXCLUDE_FILTER]?.default as string | undefined)
    ?? '';

  const ignoreHiddenFiles = (controller?.getPropertyValue?.({ name: ATTR.IGNORE_HIDDEN_FILES }) as boolean | undefined)
    ?? (nodeAttributes[ATTR.IGNORE_HIDDEN_FILES]?.default as boolean | undefined)
    ?? true;

  // Raw string state for JSON textareas. Holds the in-progress typed value
  // independently of the persisted value so typing invalid JSON mid-edit
  // doesn't clear the field.
  const [connectionParamsRawEdit, setConnectionParamsRawEdit] = useState<string | null>(null);
  const [credentialsRawEdit, setCredentialsRawEdit] = useState<string | null>(null);

  const [touchedFields, setTouchedFields] = useState<Record<string, boolean>>({
    connectionParams: false,
    credentials: false,
  });

  // Error shown when the user types the source locations key directly into the TextArea.
  const [listKeyInParamsError, setListKeyInParamsError] = useState<boolean>(false);

  const markFieldAsTouched = (field: string): void => {
    setTouchedFields((previous) => ({
      ...previous,
      [field]: true,
    }));
  };

  // ── Required field validator ──────────────────────────────────────────────
  const validate = getRequiredParamValidator(nodeAttributes);
  const providerValidation = validate(ATTR.PROVIDER, provider || undefined);
  const connectionParamsValidation = validate(
    ATTR.CONNECTION_PARAMS,
    connectionParamsRaw ?? null
  );
  const credentialsValidation = validate(
    ATTR.CREDENTIALS,
    credentialsRaw ?? null
  );
  const maxFilesValidation = validate(ATTR.MAX_FILES, maxFiles);
  const includeFilterValidation = validate(ATTR.INCLUDE_FILTER, includeFilter);
  const excludeFilterValidation = validate(ATTR.EXCLUDE_FILTER, excludeFilter);

  /** TextArea value: live edit buffer, or the stripped persisted value. */
  const connectionParamsTextValue = connectionParamsRawEdit ?? connectionParamsDisplayed;

  /** True when the TextArea JSON contains the provider's source locations key. */
  const hasListKeyInTextarea = (text: string): boolean => {
    if (listFieldCfg === null) {return false;}
    try {
      const parsed = JSON.parse(text) as Record<string, unknown>;
      return listFieldCfg.paramKey in parsed;
    } catch { return false; }
  };

  /**
   * Persist `connection_params`. Always injects the source locations so the backend
   * sees them in the stored object.
   */
  const persistConnectionParams = (textValue: string, items: string[]): void => {
    if (listFieldCfg === null) {
      controller?.updatePropertyValue?.(
        { name: ATTR.CONNECTION_PARAMS },
        textValue === '' ? null : (isValidJsonObject(textValue) ? (JSON.parse(textValue) as Record<string, unknown>) : textValue)
      );
      return;
    }
    if (textValue === '') {
      const merged = items.length > 0 ? { [listFieldCfg.paramKey]: items } : null;
      controller?.updatePropertyValue?.({ name: ATTR.CONNECTION_PARAMS }, merged);
      return;
    }
    if (!isValidJsonObject(textValue)) {
      controller?.updatePropertyValue?.({ name: ATTR.CONNECTION_PARAMS }, textValue);
      return;
    }
    const merged = mergeSourceLocationsIntoParams(textValue, listFieldCfg.paramKey, items);
    controller?.updatePropertyValue?.({ name: ATTR.CONNECTION_PARAMS }, merged);
  };

  return (
    <div className={common.commonPropertiesPanelBody}>

      {/* ── Provider ───────────────────────────────────────────────── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.PROVIDER}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.PROVIDER]?.description ?? ''}
          >
            {LABEL.PROVIDER}
          </RequiredParamTooltip>
        </div>
        <Dropdown
          id="provider"
          titleText={LABEL.PROVIDER}
          hideLabel
          label="Select provider"
          items={providerItems}
          selectedItem={provider || null}
          invalid={providerValidation.isInvalid}
          invalidText={providerValidation.errorMessage}
          onChange={({ selectedItem }: { selectedItem: string | null }) => {
            if (selectedItem) {
              controller?.updatePropertyValue?.({ name: ATTR.PROVIDER }, selectedItem);
              controller?.updatePropertyValue?.({ name: ATTR.CONNECTION_PARAMS }, null);
              controller?.updatePropertyValue?.({ name: ATTR.CREDENTIALS }, null);
              setListKeyInParamsError(false);
              setConnectionParamsRawEdit(null);
            }
          }}
        />
      </div>

      {/* ── Dedicated source locations list input (paths, urls) ── */}
      {listFieldCfg !== null && (
        <div className={common.formField}>
          <div className={common.labelWithTooltip}>
            <DefinitionTooltip
              definition={listFieldCfg.label}
              openOnHover
              align="right"
            >
              {listFieldCfg.label}
            </DefinitionTooltip>
          </div>
          <TagInput
            id="ingest-source-list-field"
            tags={savedListItems}
            labelText={listFieldCfg.label}
            hideLabel
            helperText={listFieldCfg.helperText}
            placeholder={listFieldCfg.placeholder}
            onChange={(newItems) => {
              persistConnectionParams(connectionParamsTextValue, newItems);
            }}
          />
        </div>
      )}

      {/* ── Connection parameters ───────────────────────────────────── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.CONNECTION_PARAMS}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.CONNECTION_PARAMS]?.description ?? ''}
          >
            {LABEL.CONNECTION_PARAMS}
          </RequiredParamTooltip>
        </div>
        <TextArea
          id="connection_params"
          labelText={LABEL.CONNECTION_PARAMS}
          hideLabel
          placeholder='{"bucket": "my-bucket", "prefix": "data/"}'
          value={connectionParamsTextValue}
          rows={4}
          invalid={
            connectionParamsValidation.isInvalid ||
            Boolean(touchedFields.connectionParams && !isValidJsonObject(connectionParamsTextValue)) ||
            Boolean(listKeyInParamsError)
          }
          invalidText={
            connectionParamsValidation.isInvalid ? connectionParamsValidation.errorMessage :
              listKeyInParamsError
                ? `Use the ${listFieldCfg?.label ?? 'list'} input above instead of adding it to the Connection parameters JSON.`
                : 'Connection parameters must be a valid JSON object.'
          }
          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => {
            const rawInput = e.target.value;
            setConnectionParamsRawEdit(rawInput);

            if (hasListKeyInTextarea(rawInput)) {
              setListKeyInParamsError(true);
              return;
            }
            setListKeyInParamsError(false);

            if (rawInput === '' || isValidJsonObject(rawInput)) {
              persistConnectionParams(rawInput, savedListItems);
            }
          }}
          onBlur={() => {
            markFieldAsTouched('connectionParams');
            if (connectionParamsRawEdit !== null && isValidJsonObject(connectionParamsRawEdit) && !listKeyInParamsError) {
              setConnectionParamsRawEdit(null);
            }
          }}
        />
      </div>

      {/* ── Credentials ────────────────────────────────────────────── */}
      {/* TODO: Integrate support for vault reference URL */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.CREDENTIALS}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.CREDENTIALS]?.description ?? ''}
          >
            {LABEL.CREDENTIALS}
          </RequiredParamTooltip>
        </div>
        <TextArea
          id="credentials"
          labelText={LABEL.CREDENTIALS}
          hideLabel
          value={credentialsRawEdit ?? credentialsStored}
          rows={4}
          invalid={
            credentialsValidation.isInvalid ||
            (touchedFields.credentials && !isValidJsonObject(credentialsRawEdit ?? credentialsStored))
          }
          invalidText={
            credentialsValidation.isInvalid
              ? credentialsValidation.errorMessage
              : 'Credentials must be a valid JSON object.'
          }
          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => {
            const rawInput = e.target.value;
            setCredentialsRawEdit(rawInput);
            if (rawInput === '' || isValidJsonObject(rawInput)) {
              controller?.updatePropertyValue?.({ name: ATTR.CREDENTIALS }, rawInput === '' ? null : (JSON.parse(rawInput) as Record<string, unknown>));
            }
          }}
          onBlur={() => {
            markFieldAsTouched('credentials');
            if (credentialsRawEdit !== null && isValidJsonObject(credentialsRawEdit)) {
              setCredentialsRawEdit(null);
            }
          }}
        />
      </div>

      {/* ── Max files ──────────────────────────────────────────────── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.MAX_FILES}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.MAX_FILES]?.description ?? ''}
          >
            {LABEL.MAX_FILES}
          </RequiredParamTooltip>
        </div>
        <NumberInput
          id="max_files"
          label={LABEL.MAX_FILES}
          hideLabel
          value={maxFiles}
          min={1}
          invalid={maxFilesValidation.isInvalid}
          invalidText={maxFilesValidation.errorMessage}
          onChange={(_e: unknown, { value }: { value: number | string }) => {
            controller?.updatePropertyValue?.({ name: ATTR.MAX_FILES }, Number(value));
          }}
        />
      </div>

      {/* ── Include / Exclude filter ────────────────────────────────── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.INCLUDE_FILTER}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.INCLUDE_FILTER]?.description ?? ''}
          >
            {LABEL.INCLUDE_FILTER}
          </RequiredParamTooltip>
        </div>
        <TextInput
          id="include_filter"
          labelText={LABEL.INCLUDE_FILTER}
          hideLabel
          placeholder="pdf, docx, xlsx"
          value={includeFilter}
          invalid={includeFilterValidation.isInvalid}
          invalidText={includeFilterValidation.errorMessage}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            controller?.updatePropertyValue?.({ name: ATTR.INCLUDE_FILTER }, e.target.value);
          }}
        />
      </div>

      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.EXCLUDE_FILTER}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.EXCLUDE_FILTER]?.description ?? ''}
          >
            {LABEL.EXCLUDE_FILTER}
          </RequiredParamTooltip>
        </div>
        <TextInput
          id="exclude_filter"
          labelText={LABEL.EXCLUDE_FILTER}
          hideLabel
          placeholder="tmp, log"
          value={excludeFilter}
          invalid={excludeFilterValidation.isInvalid}
          invalidText={excludeFilterValidation.errorMessage}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            controller?.updatePropertyValue?.({ name: ATTR.EXCLUDE_FILTER }, e.target.value);
          }}
        />
      </div>

      {/* ── Toggles ────────────────────────────────────────────────── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.IGNORE_HIDDEN_FILES}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.IGNORE_HIDDEN_FILES]?.description ?? ''}
          >
            {LABEL.IGNORE_HIDDEN_FILES}
          </RequiredParamTooltip>
        </div>
        <Toggle
          id="ignore_hidden_files"
          labelText={LABEL.IGNORE_HIDDEN_FILES}
          hideLabel
          labelA="Off"
          labelB="On"
          toggled={ignoreHiddenFiles}
          onToggle={(checked: boolean) => {
            controller?.updatePropertyValue?.({ name: ATTR.IGNORE_HIDDEN_FILES }, checked);
          }}
        />
      </div>

    </div>
  );
}
