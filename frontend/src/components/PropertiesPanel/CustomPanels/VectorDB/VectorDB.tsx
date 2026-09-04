/**
 * @file VectorDB operator properties panel body.
 *
 * Renders the configuration UI for a `vectordb` operator node on the canvas.
 *
 * **Data flow**:
 * - `controller.getAppData()` — reads operator metadata, nodeId, and pipelineFlow
 * - `controller.getPropertyValue({ name })` — reads a saved node parameter
 * - `controller.updatePropertyValue({ name }, value)` — writes a node parameter
 *
 * **Feature mapping flow** (triggered when the user clicks "Add / Edit feature mappings"):
 * 1. Validate and parse the provider configuration textarea as JSON.
 * 2. Call `enrichFlowFeaturesForNode` with the live pipeline flow and provider configuration patch.
 * 3. Pass the returned `available_resources`, `feature_mappings`, and `available_features` to the tearsheet.
 *
 * **Mandatory flag resolution for the summary table**:
 * - Rows saved after the fix carry `is_mandatory` directly.
 * - Legacy rows (saved before `is_mandatory` existed) fall back to
 *   `nodeFeatureMap[nodeId].input_features[feature].mandatory_for_vector_db`
 *   because VectorDB produces no output features of its own — `mandatory_for_vector_db`
 *   is carried on the features flowing *into* the node (input_features).
 */

import React, { useMemo, useState } from 'react';
import { getRequiredParamValidator } from '@/utils/requiredParamValidation';
import { RequiredParamTooltip } from '@/components/common';
import {
  Dropdown,
  InlineNotification,
  TextArea,
} from '@carbon/react';
import { NoDataEmptyState } from '@carbon/ibm-products';
import type { FeatureMappingRow, NodeFeatureEntry, OperatorMetadata } from '@/types';
import { NodeOperator } from '@/constants/operators';
import { isValidJsonObject } from '@/utils/json';
import {
  VECTORDB_ATTRIBUTES as ATTR,
  VECTORDB_LABELS as LABEL,
  VECTORDB_PROVIDERS,
  getProviderConfig,
} from './constants';
import { clearProviderConfigResource, mergeProviderConfig } from './vectordb-save';
import { VectorDBSummaryTable } from './VectorDBSummaryTable';
import { VectorDBFeatureMappingTearsheet } from './VectorDBFeatureMappingTearsheet';
import common from '../../CommonPropertiesPanel.module.scss';
import styles from './VectorDB.module.scss';

interface VectorDBPanelBodyProps {
  controller: any;
}

interface VectorDBEmptyStateProps {
  onAddClick: () => void;
}

function VectorDBEmptyState({ onAddClick }: VectorDBEmptyStateProps): React.JSX.Element {
  return (
    <div className={styles.emptyStateWrapper}>
      <NoDataEmptyState
        title={LABEL.FEATURE_MAPPING_TITLE}
        subtitle={LABEL.FEATURE_MAPPING_DESC}
        size="sm"
        action={{
          kind: 'tertiary',
          text: LABEL.ADD_FEATURE_MAPPINGS,
          onClick: onAddClick,
        }}
      />
    </div>
  );
}

/* eslint-disable @typescript-eslint/no-unsafe-call, @typescript-eslint/no-unsafe-member-access */
export function VectorDBPanelBody({
  controller,
}: VectorDBPanelBodyProps): React.JSX.Element {
  const [isTearsheetOpen, setIsTearsheetOpen] = useState(false);
  const [providerConfigDirty, setProviderConfigDirty] = useState(false);
  const [providerConfigError, setProviderConfigError] = useState<string | null>(null);

  // ── Operator metadata ──
  const appData = controller?.getAppData?.() ?? {};
  const operatorMetadata = (appData.operatorMetadata ?? {}) as Record<string, OperatorMetadata>;
  const nodeAttributes = operatorMetadata[NodeOperator.VECTORDB]?.attributes ?? {};
  const currentNodeId: string = appData.nodeId ?? '';
  const pipelineFlow: object = appData.pipelineFlow ?? {};
  const nodeFeatureMap = (appData.nodeFeatureMap ?? {}) as Record<string, NodeFeatureEntry>;
  // VectorDB introduces no output features of its own — mandatory_for_vector_db lives
  // on the features flowing into this node (input_features), not output_features.
  const currentNodeInputFeatures = nodeFeatureMap[currentNodeId]?.input_features ?? {};
  // True while the background enrich API call is in-flight (Phase 1 of panel open).
  // Used to show a skeleton in the summary table instead of checkboxes with wrong state.
  const featuresLoading: boolean = appData.featuresLoading === true;

  // ── Extract providers dynamically from metadata ──
  const providerConfigAttr = nodeAttributes[ATTR.PROVIDER_CONFIG] as Record<string, unknown> | undefined;
  const providersMap = (providerConfigAttr?.providers ?? {}) as Record<string, unknown>;
  const providerOptions: string[] =
    Object.keys(providersMap).length > 0
      ? Object.keys(providersMap)
      : [VECTORDB_PROVIDERS.OPENSEARCH, VECTORDB_PROVIDERS.MILVUS];

  // ── Read saved provider + provider-specific config ──
  const defaultProvider =
    (nodeAttributes[ATTR.PROVIDER]?.default as string | undefined) ?? VECTORDB_PROVIDERS.OPENSEARCH;
  const provider =
    (controller?.getPropertyValue?.({ name: ATTR.PROVIDER }) as string | undefined) ?? defaultProvider;

  // All provider-specific differences (keys, labels, defaults) live here.
  const cfg = getProviderConfig(provider);

  // Extract similarity and engine options from operator metadata for the active provider.
  const activeProviderProps = (
    ((providersMap[provider] as Record<string, unknown> | undefined)?.['properties'] ?? {})
  ) as Record<string, { valid_values?: string[]; default?: string }>;

  const vectorSimilarityOptions: string[] =
    activeProviderProps[cfg.similarityKey]?.valid_values ?? cfg.defaultSimilarityValues;
  const vectorSimilarityDefault: string =
    activeProviderProps[cfg.similarityKey]?.default ?? cfg.defaultSimilarityValues[0] ?? '';

  const engineOptions: string[] =
    cfg.hasEngine ? (activeProviderProps[cfg.engineKey]?.valid_values ?? ['faiss', 'lucene', 'nmslib', 'jvector']) : [];
  const engineDefault: string =
    cfg.hasEngine ? (activeProviderProps[cfg.engineKey]?.default ?? 'faiss') : '';

  const rawProviderConfig = controller?.getPropertyValue?.({ name: ATTR.PROVIDER_CONFIG });
  const providerConfig =
    typeof rawProviderConfig === 'string'
      ? rawProviderConfig
      : typeof rawProviderConfig === 'object' && rawProviderConfig !== null
      ? JSON.stringify(rawProviderConfig, null, 2)
      : '';

  // Memoised so the same object reference is reused across renders when providerConfig
  // has not changed — avoids passing a new object to the tearsheet on every render.
  const parsedSavedConfig = useMemo<Record<string, unknown>>(() => {
    try { return JSON.parse(providerConfig) as Record<string, unknown>; }
    catch { return {}; }
  }, [providerConfig]);

  const savedVectorSimilarity =
    (parsedSavedConfig[cfg.similarityKey] as string | undefined) ?? vectorSimilarityDefault;
  const savedEngine =
    cfg.hasEngine ? ((parsedSavedConfig[cfg.engineKey] as string | undefined) ?? engineDefault) : '';

  // Resource name is stored inside provider_config under the provider-specific key.
  const savedResourceName =
    (parsedSavedConfig[cfg.resourceNameKey] as string | undefined) ?? '';

  // Read on every render — controller internal state changes but its reference
  // stays the same, so useMemo([controller]) never invalidates.
  const featureMappings =
    (controller?.getPropertyValue?.({ name: ATTR.FEATURE_MAPPINGS }) as FeatureMappingRow[] | undefined) ?? [];

  // add_sparse_vector is a top-level node parameter (not inside provider_config).
  // Default is false to match the backend default.
  const savedAddSparseVector =
    (controller?.getPropertyValue?.({ name: ATTR.ADD_SPARSE_VECTOR }) as boolean | undefined) ?? false;

  // ── Required param validation ─────────────────────────────────────────────
  const validate = getRequiredParamValidator(nodeAttributes);
  const providerValidation = validate(ATTR.PROVIDER, provider);
  const providerConfigRequiredValidation = validate(ATTR.PROVIDER_CONFIG, providerConfig);

  const isProviderConfigValid = !providerConfigDirty || isValidJsonObject(providerConfig);

  const handleProviderConfigChange = (e: React.ChangeEvent<HTMLTextAreaElement>): void => {
    setProviderConfigDirty(true);
    setProviderConfigError(null);
    // Write as a parsed object when the input is valid JSON so Elyra serialises
    // provider_config as an object in the saved flow, not as a JSON string.
    // Fall back to the raw string while the user is still typing (invalid JSON).
    try {
      const parsed = JSON.parse(e.target.value) as Record<string, unknown>;
      controller?.updatePropertyValue?.({ name: ATTR.PROVIDER_CONFIG }, parsed);
    } catch {
      controller?.updatePropertyValue?.({ name: ATTR.PROVIDER_CONFIG }, e.target.value);
    }
  };

  // ── Open tearsheet: validate config then open immediately ──
  // The tearsheet itself owns the API call and loading state.
  const handleOpenTearsheet = (): void => {
    if (providerConfig !== '' && !isValidJsonObject(providerConfig)) {
      setProviderConfigError('Provider configuration must be a valid JSON object before opening feature mappings.');
      return;
    }
    setProviderConfigError(null);
    setIsTearsheetOpen(true);
  };

  const handleSaveFeatureMappings = (data: {
    resourceName: string;
    similarityMetric: string;
    engine: string;
    featureMappings: FeatureMappingRow[];
    addSparseVector: boolean;
  }): void => {
    const configPatch: Record<string, unknown> = {
      [cfg.resourceNameKey]: data.resourceName,
      [cfg.similarityKey]: data.similarityMetric,
    };
    if (cfg.hasEngine) {
      configPatch[cfg.engineKey] = data.engine;
    }
    const mergedConfig = mergeProviderConfig(providerConfig, configPatch);
    controller?.updatePropertyValue?.({ name: ATTR.PROVIDER_CONFIG }, mergedConfig);
    controller?.updatePropertyValue?.({ name: ATTR.FEATURE_MAPPINGS }, data.featureMappings);
    // Persist add_sparse_vector as a top-level node parameter (Milvus-only).
    // For other providers it is saved as false so a provider switch produces
    // a clean state — the backend treats absent/false identically.
    controller?.updatePropertyValue?.({ name: ATTR.ADD_SPARSE_VECTOR }, data.addSparseVector);
  };

  const hasMappings = featureMappings.length > 0 && Boolean(savedResourceName);

  // is_mandatory is persisted from the tearsheet (new saves) so mandatory rows are
  // correctly disabled in the summary table without needing a live enrichment call.
  // For legacy rows saved before is_mandatory existed, fall back to
  // input_features[feature].mandatory_for_vector_db — VectorDB consumes features
  // from upstream nodes, so mandatory flags live on input_features, not output_features.
  const summaryRows = featureMappings.map(({ feature_name, mapped_column_name, is_mandatory }) => ({
    feature: feature_name,
    column: mapped_column_name,
    isMandatory: is_mandatory ?? currentNodeInputFeatures[feature_name]?.mandatory_for_vector_db ?? false,
  }));

  const handleSummaryRemoveSelected = (featureNames: string[]): void => {
    const toRemove = new Set(featureNames);
    const updated = featureMappings.filter((m) => !toRemove.has(m.feature_name));
    controller?.updatePropertyValue?.({ name: ATTR.FEATURE_MAPPINGS }, updated);
    // hasMappings requires both featureMappings.length > 0 AND a saved resource name.
    // If the user batch-removes all rows, clear index_name from provider_config too
    // so the panel reverts to the empty state instead of showing a blank summary card.
    if (updated.length === 0) {
      controller?.updatePropertyValue?.(
        { name: ATTR.PROVIDER_CONFIG },
        clearProviderConfigResource(parsedSavedConfig, cfg.resourceNameKey)
      );
    }
  };

  return (
    <div className={common.commonPropertiesPanelBody}>
      {/* ── Provider Dropdown ── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.PROVIDER}
            nodeAttributes={nodeAttributes}
            definition={nodeAttributes[ATTR.PROVIDER]?.description ?? 'Vector database backend provider'}
          >
            {LABEL.PROVIDER}
          </RequiredParamTooltip>
        </div>
        <Dropdown
          id="vectordb-provider-dropdown"
          label="Select provider"
          titleText={LABEL.PROVIDER}
          hideLabel
          items={providerOptions}
          selectedItem={provider || null}
          onChange={({ selectedItem }: { selectedItem?: string | null }) => {
            if (selectedItem) {
              controller?.updatePropertyValue?.({ name: ATTR.PROVIDER }, selectedItem);
              // Clear stale mappings and index_name from provider_config when
              // the provider changes — they are provider-specific and no longer valid.
              controller?.updatePropertyValue?.(
                { name: ATTR.PROVIDER_CONFIG },
                clearProviderConfigResource(parsedSavedConfig, cfg.resourceNameKey)
              );
              controller?.updatePropertyValue?.({ name: ATTR.FEATURE_MAPPINGS }, []);
              setProviderConfigError(null);
            }
          }}
          invalid={providerValidation.isInvalid}
          invalidText={providerValidation.errorMessage}
        />
      </div>

      {/* ── Connection Details (JSON) ── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.PROVIDER_CONFIG}
            nodeAttributes={nodeAttributes}
            definition="Provider-specific configuration parameters (JSON object)."
          >
            {LABEL.PROVIDER_CONFIG}
          </RequiredParamTooltip>
        </div>
        <TextArea
          id="vectordb-provider-config-textarea"
          labelText={LABEL.PROVIDER_CONFIG}
          hideLabel
          rows={7}
          value={providerConfig}
          onChange={handleProviderConfigChange}
          invalid={!isProviderConfigValid || providerConfigRequiredValidation.isInvalid}
          invalidText={!isProviderConfigValid ? 'Must be a valid JSON object' : providerConfigRequiredValidation.errorMessage}
        />
      </div>

      {/* ── Provider configuration validation error ── */}
      {providerConfigError && (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={providerConfigError}
          lowContrast
          hideCloseButton
        />
      )}

      {hasMappings && (
        /* ── Summary card: shown after save ── */
        <VectorDBSummaryTable
          savedResourceName={savedResourceName}
          rows={summaryRows}
          onRemove={handleSummaryRemoveSelected}
          onEdit={handleOpenTearsheet}
          loading={featuresLoading}
        />
      )}

      {!hasMappings && (
        /* ── Empty state: shown before first save ── */
        <VectorDBEmptyState onAddClick={handleOpenTearsheet} />
      )}

      {/* ── Feature Mapping Tearsheet ── */}
      {/* Always mounted so Carbon's close animation plays; state resets inside on open. */}
      <VectorDBFeatureMappingTearsheet
        open={isTearsheetOpen}
        onClose={() => { setIsTearsheetOpen(false); }}
        onSave={handleSaveFeatureMappings}
        providerCfg={cfg}
        provider={provider}
        savedResourceName={savedResourceName}
        currentFeatureMappings={featureMappings}
        pipelineFlow={pipelineFlow}
        nodeId={currentNodeId}
        parsedProviderConfig={parsedSavedConfig}
        vectorSimilarityOptions={vectorSimilarityOptions}
        savedVectorSimilarity={savedVectorSimilarity}
        engineOptions={engineOptions}
        savedEngine={savedEngine}
        addSparseVector={savedAddSparseVector}
      />
    </div>
  );
}
