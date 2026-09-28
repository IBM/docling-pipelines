/**
 * @file ProviderFieldsForm
 *
 * Renders a structured per-field form driven by the provider schema embedded
 * in the `provider_config.providers[provider]` entry of the operator metadata.
 *
 * Each field in the provider's `properties` map is rendered as the appropriate
 * Carbon input based on its `type` value:
 *
 *   string (sensitive) → VaultInput (supports plaintext or vault:// URI)
 *   string (non-sensitive) → TextInput
 *   int64 / double → NumberInput
 *   boolean → Toggle
 *   list → TagInput  (comma-separated string[] stored as array)
 *   json → JsonTextArea  (raw JSON object)
 *
 * Sensitivity is determined by `keyInfo.sensitive === true` from operator metadata.
 *
 * No wiring occurs here.
 * The component calls `onChange(fieldKey, value)` so the parent can
 * decide which controller attribute(s) to write to once.
 */

import React from 'react';
import {
  NumberInput,
  TextInput,
  Toggle,
} from '@carbon/react';
import { DefinitionTooltip } from '@carbon/react';
import { TagInput } from '@/components/common/TagInput/TagInput';
import { JsonTextArea } from '@/components/common/JsonTextArea/JsonTextArea';
import { VaultInput } from '@/components/common';
import type { OperatorFeature } from '@/types';
import common from '../../CommonPropertiesPanel.module.scss';

// ── Hidden fields ─────────────────────────────────────────────────────────────
// Fields that are intentionally suppressed from the provider form because they
// are already covered by a dedicated top-level operator attribute.
const HIDDEN_FIELDS = new Set([
  'file_extensions',
]);

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ProviderFieldsFormProps {
  /** Property definitions from `provider_config.providers[provider].properties`. */
  properties: Record<string, OperatorFeature>;
  /** Current field values keyed by property key. */
  values: Record<string, unknown>;
  /**
   * Called when the user changes a field.
   * Parent component decides how to persist the value.
   */
  onChange: (fieldKey: string, value: unknown) => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function asString(v: unknown): string {
  if (v === undefined || v === null) {return '';}
  return String(v);
}

function asNumber(v: unknown): number | string {
  if (v === undefined || v === null) {return '';}
  const n = Number(v);
  return Number.isFinite(n) ? n : '';
}

function asBoolean(v: unknown, defaultValue = false): boolean {
  if (typeof v === 'boolean') {return v;}
  return defaultValue;
}

function asStringArray(v: unknown): string[] {
  if (Array.isArray(v)) {return v.map(String);}
  if (typeof v === 'string' && v.trim()) {
    return v.split(',').map((s) => s.trim()).filter(Boolean);
  }
  return [];
}

/**
 * Renders one Carbon input per property defined in the provider schema.
 * Ordering follows the natural order of the `properties` object.
 */
export function ProviderFieldsForm({
  properties,
  values,
  onChange,
}: ProviderFieldsFormProps): React.JSX.Element {
  return (
    <>
      {Object.entries(properties).map(([fieldKey, keyInfo]: [string, OperatorFeature]) => {
        if (HIDDEN_FIELDS.has(fieldKey)) {return null;}
        const label = keyInfo.name ?? fieldKey;
        const description = keyInfo.description ?? '';
        const isRequired = keyInfo.required === true;
        const labelText = isRequired ? `${label} (required)` : label;
        const inputId = `provider-field-${fieldKey}`;

        // VaultInput owns its own header row.
        const isSensitive = keyInfo.type === 'string' && keyInfo.sensitive === true;

        if (isSensitive) {
          return (
            <div key={fieldKey} className={common.formField}>
              <VaultInput
                id={inputId}
                labelText={labelText}
                labelComponent={
                  <DefinitionTooltip
                    definition={description}
                    openOnHover
                    align="right"
                  >
                    {labelText}
                  </DefinitionTooltip>
                }
                value={asString(values[fieldKey])}
                onChange={(v: string) => {onChange(fieldKey, v);}}
              />
            </div>
          );
        }

        return (
          <div key={fieldKey} className={common.formField}>
            <div className={common.labelWithTooltip}>
              <DefinitionTooltip
                definition={description}
                openOnHover
                align="right"
              >
                {labelText}
              </DefinitionTooltip>
            </div>

            {/* boolean → Toggle */}
            {keyInfo.type === 'boolean' && (
              <Toggle
                id={inputId}
                labelText={label}
                hideLabel
                labelA="Off"
                labelB="On"
                toggled={asBoolean(values[fieldKey], keyInfo.default as boolean | undefined ?? false)}
                onToggle={(checked: boolean) => {onChange(fieldKey, checked);}}
              />
            )}

            {/* int64 / double → NumberInput */}
            {(keyInfo.type === 'int64' || keyInfo.type === 'double') && (
              <NumberInput
                id={inputId}
                label={label}
                hideLabel
                value={asNumber(values[fieldKey])}
                onChange={(_e: unknown, { value }: { value: number | string }) => {
                  onChange(fieldKey, value === '' ? undefined : Number(value));
                }}
              />
            )}

            {/* list → TagInput */}
            {keyInfo.type === 'list' && (
              <TagInput
                id={inputId}
                labelText={label}
                hideLabel
                tags={asStringArray(values[fieldKey])}
                placeholder={`Add ${label.toLowerCase()}`}
                helperText={`Press Enter or comma to add ${label.toLowerCase()}.`}
                onChange={(items: string[]) => {onChange(fieldKey, items);}}
              />
            )}

            {/* json → JsonTextArea */}
            {keyInfo.type === 'json' && (
              <JsonTextArea
                id={inputId}
                labelText={label}
                rows={3}
                storedValue={typeof values[fieldKey] === 'object' && values[fieldKey] !== null
                  ? values[fieldKey] as Record<string, unknown>
                  : null}
                onChange={(value) => {onChange(fieldKey, value ?? undefined);}}
              />
            )}

            {/* string non-sensitive → TextInput */}
            {keyInfo.type === 'string' && keyInfo.sensitive !== true && (
              <TextInput
                id={inputId}
                labelText={label}
                hideLabel
                value={asString(values[fieldKey])}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                  onChange(fieldKey, e.target.value);
                }}
              />
            )}
          </div>
        );
      })}
    </>
  );
}
