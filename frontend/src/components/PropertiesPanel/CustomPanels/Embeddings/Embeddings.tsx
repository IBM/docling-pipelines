/**
 * @file Embeddings operator properties panel body.
 *
 * Renders the configuration UI for the `embeddings` operator node.
 * The panel keeps provider selection visible at full width, groups provider-
 * specific fields in a shared subsection, and lazily loads model options from
 * the provider models API.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { getRequiredParamValidator } from '@/utils/requiredParamValidation';
import { RequiredParamTooltip, VaultInput } from '@/components/common';
import {
  Accordion,
  AccordionItem,
  DefinitionTooltip,
  Dropdown,
  InlineLoading,
  InlineNotification,
  NumberInput,
  TextInput,
} from '@carbon/react';
import {
  EMBEDDINGS_ATTRIBUTE as ATTR,
  EMBEDDINGS_DEFAULTS,
  EMBEDDINGS_LABELS as LABEL,
  EMBEDDINGS_PROVIDERS,
  EMBEDDINGS_PROVIDER_LABELS,
  type EmbeddingsProvider,
} from './constants';
import type { ModelInfo, OperatorFeature, OperatorMetadata } from '@/types';
import { NodeOperator } from '@/constants/operators';
import { getProviderModels } from '@/services/api';
import { filterModelsForEmbeddingsPanel } from '@/utils/providerModels';
import common from '../../CommonPropertiesPanel.module.scss';

/**
 * Props injected by Elyra's custom properties panel host.
 *
 * `controller` provides access to persisted node parameter values and the
 * mutation API used to write updates back into the canvas model.
 */
interface EmbeddingsPanelBodyProps {
  controller: any;
}

/**
 * Render the Embeddings operator configuration form.
 *
 * Data flow:
 * - reads persisted values from `controller.getPropertyValue()`
 * - stores provider-specific values inside a single `provider_config` object
 * - fetches provider model options for the selected provider / API base
 * - filters those models for embeddings-specific use in the model selector
 */
export function EmbeddingsPanelBody({ controller }: EmbeddingsPanelBodyProps): React.JSX.Element {
  // ── Operator metadata ─────────────────────────────────────────────────────
  // eslint-disable-next-line @typescript-eslint/no-unsafe-call
  const operatorMetadata = (controller?.getAppData?.()?.operatorMetadata ?? {}) as Record<string, OperatorMetadata>;
  const nodeAttributes: Record<string, OperatorFeature> = operatorMetadata[NodeOperator.EMBEDDINGS]?.attributes ?? {};

  const providerConfigAttr = nodeAttributes[ATTR.PROVIDER_CONFIG];
  const providerSchemas = providerConfigAttr?.providers ?? {};

  /** Returns the description for a top-level attribute from operator metadata. */
  const attrDesc = (key: string): string =>
    nodeAttributes[key]?.description ?? '';

  /** Returns the description for a provider_config field from operator metadata. */
  const providerFieldDesc = (providerKey: string, field: string): string =>
    providerSchemas[providerKey]?.properties?.[field]?.description ?? '';

  const provider: EmbeddingsProvider =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.PROVIDER }) as EmbeddingsProvider | undefined)
    ?? EMBEDDINGS_DEFAULTS.PROVIDER;

  const providerConfigValue =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    controller?.getPropertyValue?.({ name: ATTR.PROVIDER_CONFIG }) as string | Record<string, unknown> | undefined;
  const providerConfigObject: Record<string, unknown> =
    typeof providerConfigValue === 'string'
      ? {}
      : providerConfigValue ?? {};

  const modelId: string = typeof providerConfigObject.model_id === 'string'
    ? providerConfigObject.model_id
    : '';
  const apiBase: string = typeof providerConfigObject.api_base === 'string'
    ? providerConfigObject.api_base
    : '';
  const apiKey: string = typeof providerConfigObject.api_key === 'string' // pragma: allowlist secret
    ? providerConfigObject.api_key
    : '';

  const overlapRatio: number =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.OVERLAP_RATIO }) as number | undefined)
    ?? EMBEDDINGS_DEFAULTS.OVERLAP_RATIO;

  const tokenLimit: number =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.TOKEN_LIMIT }) as number | undefined)
    ?? EMBEDDINGS_DEFAULTS.TOKEN_LIMIT;

  // ── Required param validation ─────────────────────────────────────────────
  const validate = getRequiredParamValidator(nodeAttributes);
  const providerValidation = validate(ATTR.PROVIDER, provider);
  const overlapRatioValidation = validate(ATTR.OVERLAP_RATIO, overlapRatio);
  const tokenLimitValidation = validate(ATTR.TOKEN_LIMIT, tokenLimit);

  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const latestModelsRequestRef = useRef(0);

  /**
   * Load provider model options for the current provider context.
   *
   * Uses a monotonically increasing request id so stale async responses do not
   * overwrite newer provider/model state after rapid user edits.
   */
  const loadProviderModels = useCallback(async (
    nextProvider: EmbeddingsProvider,
    nextApiBase: string
  ): Promise<void> => {
    const requestId = latestModelsRequestRef.current + 1;
    latestModelsRequestRef.current = requestId;

    setModelsLoading(true);
    setModelsError(null);

    try {
      const response = await getProviderModels(nextProvider, nextApiBase ? { api_base: nextApiBase } : undefined);
      if (latestModelsRequestRef.current !== requestId) {
        return;
      }
      setAvailableModels(filterModelsForEmbeddingsPanel(nextProvider, response.models ?? []));
    } catch {
      if (latestModelsRequestRef.current !== requestId) {
        return;
      }
      setAvailableModels([]);
      setModelsError('Failed to load provider models. Enter a model ID manually.');
    } finally {
      if (latestModelsRequestRef.current === requestId) {
        setModelsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadProviderModels(provider, apiBase);
    // Initial load only. Subsequent reloads are triggered explicitly on provider
    // change and API base blur to avoid per-keystroke requests.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const update = useCallback((name: string, value: unknown): void => {
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    controller?.updatePropertyValue?.({ name }, value);
  }, [controller]);

  /**
   * Update a single field inside the persisted `provider_config` object.
   */
  const updateProviderConfig = useCallback((
    key:
      | typeof ATTR.PROVIDER_CONFIG_MODEL_ID
      | typeof ATTR.PROVIDER_CONFIG_API_BASE
      | typeof ATTR.PROVIDER_CONFIG_API_KEY,
    value: string
  ): void => {
    update(ATTR.PROVIDER_CONFIG, {
      ...providerConfigObject,
      [key]: value,
    });
  }, [providerConfigObject, update]);

  const handleProviderChange = useCallback((
    { selectedItem }: { selectedItem: EmbeddingsProvider | null }
  ): void => {
    if (selectedItem) {
      update(ATTR.PROVIDER, selectedItem);
      update(ATTR.PROVIDER_CONFIG, {});
      void loadProviderModels(selectedItem, '');
    }
  }, [loadProviderModels, update]);

  return (
    <div className={common.commonPropertiesPanelBody}>
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.PROVIDER}
            nodeAttributes={nodeAttributes}
            definition={attrDesc(ATTR.PROVIDER)}
          >
            {LABEL.PROVIDER}
          </RequiredParamTooltip>
        </div>
        <Dropdown
          id="embeddings-provider"
          titleText={LABEL.PROVIDER}
          hideLabel
          label="Select provider"
          items={[...EMBEDDINGS_PROVIDERS]}
          selectedItem={provider}
          itemToString={(item: EmbeddingsProvider | null) => (item ? EMBEDDINGS_PROVIDER_LABELS[item] : '')}
          onChange={handleProviderChange}
          invalid={providerValidation.isInvalid}
          invalidText={providerValidation.errorMessage}
        />
      </div>

      {/* Shared subsection groups provider-specific configuration under the
          selected provider while preserving full-width layout outside the
          accordion content area. */}

      <div className={common.subSection}>
        <div className={common.formField}>
          <div className={common.labelWithTooltip}>
            <DefinitionTooltip
              definition={providerFieldDesc(provider, ATTR.PROVIDER_CONFIG_API_BASE)}
              openOnHover
              align="right"
            >
              {LABEL.API_BASE}
            </DefinitionTooltip>
          </div>
          <TextInput
            id="embeddings-api-base"
            labelText={LABEL.API_BASE}
            hideLabel
            placeholder="http://localhost:11434/v1"
            value={apiBase}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
              updateProviderConfig(ATTR.PROVIDER_CONFIG_API_BASE, e.target.value);
            }}
            onBlur={(e: React.FocusEvent<HTMLInputElement>) => {
              void loadProviderModels(provider, e.target.value);
            }}
          />
        </div>

        <div className={common.formField}>
          <VaultInput
            id="embeddings-api-key"
            labelText={LABEL.API_KEY}
            labelComponent={
              <DefinitionTooltip
                definition={providerFieldDesc(provider, ATTR.PROVIDER_CONFIG_API_KEY)} // pragma: allowlist secret
                openOnHover
                align="right"
              >
                {LABEL.API_KEY}
              </DefinitionTooltip>
            }
            placeholder="sk-..."
            value={apiKey}
            onChange={(v: string) => {
              updateProviderConfig(ATTR.PROVIDER_CONFIG_API_KEY, v);
            }}
          />
        </div>

        <div className={common.formField}>
          <div className={common.labelWithTooltip}>
            <DefinitionTooltip
              definition={
                provider === 'watsonx'
                  ? "Model identifier for IBM watsonx.ai (e.g., 'ibm/slate-30m-english-rtrvr')."
                  : providerFieldDesc(provider, ATTR.PROVIDER_CONFIG_MODEL_ID)
              }
              openOnHover
              align="right"
            >
              {LABEL.MODEL_ID}
            </DefinitionTooltip>
          </div>

          {modelsLoading && (
            <InlineLoading description="Loading provider models..." />
          )}

          {!modelsLoading && modelsError && (
            <InlineNotification
              kind="warning"
              title=""
              subtitle={modelsError}
              lowContrast
              hideCloseButton
            />
          )}

          {!modelsLoading && availableModels.length > 0 ? (
            <Dropdown
              id="embeddings-model-id"
              titleText={LABEL.MODEL_ID}
              hideLabel
              label="Select model"
              items={availableModels}
              selectedItem={availableModels.find((model) => model.model_id === modelId) ?? null}
              itemToString={(item: ModelInfo | null) => item?.model_id ?? ''}
              onChange={({ selectedItem }: { selectedItem: ModelInfo | null }) => {
                if (selectedItem) {
                  updateProviderConfig(ATTR.PROVIDER_CONFIG_MODEL_ID, selectedItem.model_id);
                }
              }}
            />
          ) : (
            <TextInput
              id="embeddings-model-id"
              labelText={LABEL.MODEL_ID}
              hideLabel
              placeholder={provider === 'litellm' ? 'openai/nomic-embed-text' : 'ibm/slate-30m-english-rtrvr'}
              value={modelId}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                updateProviderConfig(ATTR.PROVIDER_CONFIG_MODEL_ID, e.target.value);
              }}
            />
          )}
        </div>
      </div>

      <Accordion align="start">
        <AccordionItem title="Advanced">
          <div className={common.formField}>
            <div className={common.labelWithTooltip}>
              <RequiredParamTooltip
                paramId={ATTR.OVERLAP_RATIO}
                nodeAttributes={nodeAttributes}
                definition={attrDesc(ATTR.OVERLAP_RATIO)}
              >
                {LABEL.OVERLAP_RATIO}
              </RequiredParamTooltip>
            </div>
            <NumberInput
              id="embeddings-overlap-ratio"
              label={LABEL.OVERLAP_RATIO}
              hideLabel
              value={overlapRatio}
              min={0}
              max={0.5}
              step={0.1}
              onChange={(_e: unknown, { value }: { value: number | string }) => {
                const numericValue = Number(value);
                update(ATTR.OVERLAP_RATIO, Number.isFinite(numericValue) ? numericValue : undefined);
              }}
              invalid={overlapRatioValidation.isInvalid}
              invalidText={overlapRatioValidation.errorMessage}
            />
          </div>

          <div className={common.formField}>
            <div className={common.labelWithTooltip}>
              <RequiredParamTooltip
                paramId={ATTR.TOKEN_LIMIT}
                nodeAttributes={nodeAttributes}
                definition={attrDesc(ATTR.TOKEN_LIMIT)}
              >
                {LABEL.TOKEN_LIMIT}
              </RequiredParamTooltip>
            </div>
            <NumberInput
              id="embeddings-token-limit"
              label={LABEL.TOKEN_LIMIT}
              hideLabel
              value={tokenLimit}
              min={1}
              step={1}
              onChange={(_e: unknown, { value }: { value: number | string }) => {
                const numericValue = Number(value);
                update(ATTR.TOKEN_LIMIT, Number.isFinite(numericValue) && numericValue > 0 ? numericValue : undefined);
              }}
              invalid={tokenLimitValidation.isInvalid}
              invalidText={tokenLimitValidation.errorMessage}
            />
          </div>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
