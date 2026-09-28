/**
 * @file Feature mapping tearsheet for the VectorDB operator.
 *
 * Owns the enrichment API call lifecycle. The tearsheet opens immediately;
 * a loading skeleton is shown while the API is in flight and replaced with
 * content once resolved. The parent panel is never blocked on loading.
 *
 * Existing-resource behaviour:
 * - Similarity and engine dropdowns are read-only when an existing resource is
 *   selected and `stored_resource_metadata` carries those values.
 * - An info notification explains the read-only constraint to the user.
 * - The "Create new" name input is hidden when an existing resource is selected.
 * - New resource name validation: must start with a letter or underscore;
 *   only letters, numbers, and underscores are allowed.
 * - Unsupported resource: the Save button is disabled and the mappings table
 *   is replaced with an error empty state.
 */

import React, { useState, useMemo, useEffect } from 'react';
import { useThemeElement } from '@/contexts';
import {
  Checkbox,
  ComboBox,
  DataTableSkeleton,
  Dropdown,
  InlineNotification,
  Loading,
  TextInput,
  TextInputSkeleton,
} from '@carbon/react';
import { ErrorEmptyState } from '@carbon/ibm-products';
import { Tearsheet } from '@carbon/ibm-products';
import type { FeatureMappingRow, FeatureMappingItem, VectorDBEnrichmentResult } from '@/types';
import { enrichFlowFeaturesForNode } from './vectordb-enrichment';
import {
  DEFAULT_COLUMN_MAPPINGS,
  VECTORDB_LABELS,
  VECTORDB_PROVIDERS,
  omitProviderConfigKeys,
  type ProviderConfig,
} from './constants';
import { VectorDBFeatureMappingTable } from './VectorDBFeatureMappingTable';
import { AddFeatureMappingModal } from './AddFeatureMappingModal';
import styles from './VectorDB.module.scss';

const { CREATE_NEW } = VECTORDB_LABELS;

/** Validation for new resource names: must start with letter/underscore, then word chars only. */
const NEW_RESOURCE_NAME_RE = /^[A-Za-z_]\w*$/;

interface VectorDBFeatureMappingTearsheetProps {
  open: boolean;
  onClose: () => void;
  onSave: (data: {
    resourceName: string;
    similarityMetric: string;
    engine: string;
    featureMappings: FeatureMappingRow[];
    addSparseVector: boolean;
  }) => void;
  /** Provider-specific config — keys, labels, defaults. No if/switch needed. */
  providerCfg: ProviderConfig;
  /** The active provider string (e.g. "opensearch" / "milvus") — passed to enrichment API. */
  provider: string;
  /** Previously saved index/collection name — pre-fills the selector on re-open. */
  savedResourceName: string;
  currentFeatureMappings: FeatureMappingRow[];
  /** Full Elyra pipeline JSON — passed to the enrichment API. */
  pipelineFlow: object;
  /** Elyra node ID of this vectordb node. */
  nodeId: string;
  /** Already-parsed provider_config object. */
  parsedProviderConfig: Record<string, unknown>;
  /** Whether sparse vector (BM25) support is enabled. Milvus-only. */
  addSparseVector: boolean;
  /** Valid similarity values from operator metadata (space_type / metric_type). */
  vectorSimilarityOptions: string[];
  /** Saved similarity value from provider_config — pre-fills dropdown on re-open. */
  savedVectorSimilarity: string;
  /** Valid engine values from operator metadata (OpenSearch only). */
  engineOptions: string[];
  /** Saved engine from provider_config — pre-fills dropdown on re-open. */
  savedEngine: string;
}

/**
 * Derive the initial rows for the mappings table on tearsheet open.
 *
 * Matches datasift-ui's `deriveInitialRows` + `processMappingsAndRows` pattern:
 *
 * Priority:
 * 1. currentFeatureMappings (user's saved edits) when they exist — preserves
 *    column edits the user made on a previous save for the same resource.
 *    Descriptions and mandatory flags are enriched from available_features.
 * 2. API-returned feature_mappings when no saved mappings exist yet (first open).
 * 3. available_features keys as a last resort when API returns no mappings.
 */
function buildTableRows(
  enrichmentResult: VectorDBEnrichmentResult | null,
  currentFeatureMappings: FeatureMappingRow[]
): FeatureMappingItem[] {
  const availableFeatures = enrichmentResult?.available_features ?? {};
  const apiMappings = enrichmentResult?.feature_mappings ?? [];

  // Priority 1: user's previously saved mappings — use saved column values,
  // enrich descriptions and mandatory flags from the latest API response.
  if (currentFeatureMappings.length > 0) {
    return currentFeatureMappings.map(({ feature_name, mapped_column_name }) => ({
      feature: feature_name,
      description: availableFeatures[feature_name]?.description ?? '',
      column: mapped_column_name || (DEFAULT_COLUMN_MAPPINGS[feature_name] ?? feature_name),
      isMandatory: availableFeatures[feature_name]?.mandatory_for_vector_db ?? false,
    }));
  }

  // Priority 2: API-returned mappings (first open, no saved mappings yet).
  if (apiMappings.length > 0) {
    return apiMappings.map(({ feature_name, mapped_column_name }) => ({
      feature: feature_name,
      description: availableFeatures[feature_name]?.description ?? '',
      column: mapped_column_name || (DEFAULT_COLUMN_MAPPINGS[feature_name] ?? feature_name),
      isMandatory: availableFeatures[feature_name]?.mandatory_for_vector_db ?? false,
    }));
  }

  // Priority 3: available_features keys with default column names.
  const featureKeys = Object.keys(availableFeatures);
  if (featureKeys.length > 0) {
    return featureKeys.map((name) => ({
      feature: name,
      description: availableFeatures[name]?.description ?? '',
      column: DEFAULT_COLUMN_MAPPINGS[name] ?? name,
      isMandatory: availableFeatures[name]?.mandatory_for_vector_db ?? false,
    }));
  }

  return [];
}

/** Validate a proposed new resource name. Returns an error string or null. */
function validateNewName(name: string, existingNames: string[]): string | null {
  const trimmed = name.trim();
  if (!trimmed) { return 'Name is required'; }
  if (!/^[A-Za-z_]/.test(trimmed)) { return 'Name must start with a letter or underscore'; }
  if (!NEW_RESOURCE_NAME_RE.test(trimmed)) { return 'Only letters, numbers, and underscores are allowed'; }
  if (existingNames.includes(trimmed)) { return `"${trimmed}" already exists — choose a different name`; }
  return null;
}

export function VectorDBFeatureMappingTearsheet({
  open,
  onClose,
  onSave,
  providerCfg,
  provider,
  savedResourceName,
  currentFeatureMappings,
  pipelineFlow,
  nodeId,
  parsedProviderConfig,
  vectorSimilarityOptions,
  savedVectorSimilarity,
  engineOptions,
  savedEngine,
  addSparseVector,
}: VectorDBFeatureMappingTearsheetProps): React.JSX.Element {
  const portalTarget = useThemeElement();
  const {
    resourceLabel,
    resourceNameKey,
    similarityLabel,
    similarityLabels,
    hasEngine,
    engineLabels,
  } = providerCfg;

  // ── Enrichment state — owned here, not in the parent panel ──
  const [loading, setLoading] = useState(false);
  // Separate from `loading`: true only while re-enriching after resource selection.
  // Controls keep showing while only the table area skeleton is active.
  const [loadingMappings, setLoadingMappings] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [enrichmentResult, setEnrichmentResult] = useState<VectorDBEnrichmentResult | null>(null);

  // ── Form state ──
  const [selectedResource, setSelectedResource] = useState<string>(CREATE_NEW);
  const [newResourceName, setNewResourceName] = useState<string>('');
  const [newNameError, setNewNameError] = useState<string | null>('Name is required');
  const [resourceNameEdited, setResourceNameEdited] = useState<boolean>(true);
  const [similarityMetric, setSimilarityMetric] = useState<string>(savedVectorSimilarity);
  const [engine, setEngine] = useState<string>(savedEngine);
  const [submitted, setSubmitted] = useState<boolean>(false);
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [tableRows, setTableRows] = useState<FeatureMappingItem[]>([]);
  const [sparseVectorEnabled, setSparseVectorEnabled] = useState<boolean>(addSparseVector);

  // Cancellation token for in-flight API calls — incremented on each new call
  // so stale responses from superseded requests are discarded.
  const runRef = React.useRef(0);

  // Fire the enrichment API whenever the tearsheet opens.
  // The tearsheet opens immediately; the loading skeleton renders inside it.
  useEffect(() => {
    if (!open) { return; }

    runRef.current += 1;
    const token = runRef.current;

    const run = async () => {
      setLoading(true);
      setLoadError(null);
      setEnrichmentResult(null);

      try {
        // Pass savedResourceName so the backend returns stored_resource_metadata
        // (vector_similarity, dimension_size) for the already-saved resource.
        // Pass undefined when creating new (empty savedResourceName) so the backend
        // returns defaults instead.
        const result = await enrichFlowFeaturesForNode(
          pipelineFlow, nodeId, provider, parsedProviderConfig, resourceNameKey,
          savedResourceName || undefined,
          sparseVectorEnabled
        );
        if (runRef.current !== token) { return; }
        setEnrichmentResult(result);

        // Initialise form state from the API response.
        const availableResources = result?.available_resources ?? [];
        const storedMeta = result?.stored_resource_metadata;
        const isCreateNew = !availableResources.includes(savedResourceName);

        setSelectedResource(isCreateNew ? CREATE_NEW : savedResourceName);
        setNewResourceName(isCreateNew ? savedResourceName : '');
        setNewNameError(validateNewName(isCreateNew ? savedResourceName : '', availableResources));
        setResourceNameEdited(true);
        setSimilarityMetric(storedMeta?.vector_similarity ?? savedVectorSimilarity);
        setEngine(savedEngine);
        setSubmitted(false);
        setIsAddModalOpen(false);
        setSparseVectorEnabled(addSparseVector);
        setTableRows(buildTableRows(result, currentFeatureMappings));
      } catch {
        if (runRef.current !== token) { return; }
        setLoadError('Failed to load available resources. Check your connection settings and try again.');
        // Still show the tearsheet with last-saved mappings so the user is not blocked.
        setSelectedResource(savedResourceName ? savedResourceName : CREATE_NEW);
        setNewResourceName('');
        setTableRows(buildTableRows(null, currentFeatureMappings));
      } finally {
        if (runRef.current === token) { setLoading(false); }
      }
    };

    void run();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]); // re-runs only when the tearsheet opens/closes

  const availableResources = enrichmentResult?.available_resources ?? [];
  const storedMeta = enrichmentResult?.stored_resource_metadata;
  const availableFeatures = enrichmentResult?.available_features ?? {};

  const isCreateNew = selectedResource === CREATE_NEW;

  const effectiveResourceName = isCreateNew
    ? newResourceName.trim()
    : selectedResource;

  // Similarity and engine are locked for existing resources when the backend
  // already knows those values (they were set at index/collection creation time).
  const isConfigReadOnly = !isCreateNew && Boolean(storedMeta?.vector_similarity);

  const handleResourceChange = ({ selectedItem }: { selectedItem?: string | null }): void => {
    const selectedResourceName = selectedItem ?? CREATE_NEW;
    setSelectedResource(selectedResourceName);
    setLoadError(null);

    // Strip all resource-specific keys from provider_config before sending —
    // these are saved state and must not bleed into the API call for a different
    // resource (or for create-new). Uses providerCfg.resourceSpecificKeys so
    // no hardcoded key names live in this component.
    const baseConfig = omitProviderConfigKeys(parsedProviderConfig, providerCfg.resourceSpecificKeys);

    runRef.current += 1;
    const token = runRef.current;

    // When creating new: omit the resource name so the backend returns generic
    // defaults. When selecting existing: pass the name so the backend returns
    // stored_resource_metadata and feature_mappings for that specific resource.
    const resourceArg = selectedResourceName === CREATE_NEW ? undefined : selectedResourceName;

    const fetchOnResourceChange = async () => {
      setLoadingMappings(true);
      try {
        const result = await enrichFlowFeaturesForNode(
          pipelineFlow, nodeId, provider, baseConfig, resourceNameKey, resourceArg,
          sparseVectorEnabled
        );
        if (runRef.current !== token) { return; }
        setEnrichmentResult(result);
        // For existing resources use the stored similarity; for new ones reset to the saved default.
        const freshMeta = result?.stored_resource_metadata;
        const nextSimilarity = resourceArg
          ? (freshMeta?.vector_similarity ?? savedVectorSimilarity)
          : savedVectorSimilarity;
        setSimilarityMetric(nextSimilarity);
        setEngine(savedEngine);
        // Always drive rows from the API response when the user switches resource —
        // passing currentFeatureMappings would bleed saved column values from a previously
        // configured resource into the new selection (including switching to "Create new").
        setTableRows(buildTableRows(result, []));
      } catch {
        if (runRef.current !== token) { return; }
        setLoadError(
          resourceArg
            ? 'Failed to load details for the selected resource. Try again or choose a different one.'
            : 'Failed to load feature mappings for new resource. Try again.'
        );
      } finally {
        if (runRef.current === token) { setLoadingMappings(false); }
      }
    };

    void fetchOnResourceChange();
  };

  const handleNewNameChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const val = e.target.value;
    setNewResourceName(val);
    setResourceNameEdited(true);
    setNewNameError(validateNewName(val, availableResources));
  };

  const handleColumnChange = (featureName: string, column: string): void => {
    setTableRows((prev) =>
      prev.map((row) => (row.feature === featureName ? { ...row, column } : row))
    );
  };

  const handleRemoveSelected = (featureNames: string[]): void => {
    setTableRows((prev) =>
      prev.filter((row) => row.isMandatory || !featureNames.includes(row.feature))
    );
  };

  const handleAddFeature = (feature: string, column: string): void => {
    const isMandatory = availableFeatures[feature]?.mandatory_for_vector_db ?? false;
    const description = availableFeatures[feature]?.description ?? '';
    setTableRows((prev) => [
      ...prev,
      { feature, description, column, isMandatory },
    ]);
  };

  const handleSparseVectorChange = (_evt: React.ChangeEvent<HTMLInputElement>, { checked }: { checked: boolean }): void => {
    setSparseVectorEnabled(checked);
    setLoadError(null);

    const baseConfig = omitProviderConfigKeys(parsedProviderConfig, providerCfg.resourceSpecificKeys);
    const resourceArg = isCreateNew ? undefined : selectedResource;

    runRef.current += 1;
    const token = runRef.current;

    const fetchOnSparseToggle = async () => {
      setLoadingMappings(true);
      try {
        const result = await enrichFlowFeaturesForNode(
          pipelineFlow, nodeId, provider, baseConfig, resourceNameKey, resourceArg, checked
        );
        if (runRef.current !== token) { return; }
        setEnrichmentResult(result);
        setTableRows(buildTableRows(result, []));
      } catch {
        if (runRef.current !== token) { return; }
        setLoadError('Failed to reload feature mappings. Try again.');
      } finally {
        if (runRef.current === token) { setLoadingMappings(false); }
      }
    };

    void fetchOnSparseToggle();
  };

  const isUnsupported =
    !isCreateNew &&
    enrichmentResult?.is_docpipe_supported_resource?.supported === false;

  // newNameError only blocks save when we are in "Create new" mode — it holds
  // stale validation state when the user switches to an existing resource.
  const canSave =
    !loading &&
    !loadingMappings &&
    Boolean(effectiveResourceName) &&
    (!isCreateNew || !newNameError) &&
    !isUnsupported;

  const handleSave = (): void => {
    setSubmitted(true);
    if (!canSave) { return; }

    const mappings: FeatureMappingRow[] = tableRows
      .filter((row) => row.column.trim())
      .map((row) => ({
        feature_name: row.feature,
        mapped_column_name: row.column.trim(),
        is_mandatory: row.isMandatory,
      }));

    onSave({
      resourceName: effectiveResourceName,
      similarityMetric,
      engine,
      featureMappings: mappings,
      addSparseVector: sparseVectorEnabled,
    });
    onClose();
  };

  const dropdownItems = [CREATE_NEW, ...availableResources];
  const alreadyMapped = useMemo(() => tableRows.map((r) => r.feature), [tableRows]);

  const unsupportedSubtitle =
    resourceLabel === 'collection'
      ? `The selected ${resourceLabel} is not compatible since it does not have a vector field configured. Select another ${resourceLabel} or create a new one.`
      : `The selected ${resourceLabel} is not compatible since it does not have a dense vector field with indexing enabled on that field. Select another ${resourceLabel} or create a new one.`;

  return (
    <Tearsheet
      open={open}
      title={currentFeatureMappings.length > 0 ? 'Edit feature mappings' : 'Add feature mappings'}
      description={`Configure the target ${resourceLabel} and map pipeline features to its columns`}
      onClose={onClose}
      portalTarget={portalTarget}
      actions={[
        {
          label: 'Save',
          onClick: handleSave,
          kind: 'primary' as const,
          disabled: !canSave,
        },
        {
          label: 'Cancel',
          onClick: onClose,
          kind: 'secondary' as const,
        },
      ]}
    >
      <div className={styles.tearsheetForm}>
        {/* Full-body centered spinner while the enrichment API is in flight */}
        {loading && (
          <div className={styles.tearsheetLoadingCenter}>
            <Loading withOverlay={false} small={false} />
          </div>
        )}

        {!loading && (
          <>
            {/* API error — shown when enrichment fails; table still usable with saved data */}
            {loadError && (
              <InlineNotification
                kind="error"
                title="Error"
                subtitle={loadError}
                lowContrast
                hideCloseButton
              />
            )}

            {/* Read-only notice for existing resources */}
            {isConfigReadOnly && (
              <InlineNotification
                kind="info"
                title={`${similarityLabel}${hasEngine ? ', engine,' : ''} and dimension size are fixed by the existing ${resourceLabel} and cannot be changed.`}
                lowContrast
                hideCloseButton
              />
            )}

            {/* Controls row — ComboBox always present; remaining fields hidden when unsupported
                so the user can only select a different resource, not configure the broken one. */}
            <div className={styles.rowInputs}>
              <ComboBox
                id="resource-select"
                titleText={`Search or select a ${resourceLabel} name`}
                placeholder={`Search or select a ${resourceLabel} name`}
                items={dropdownItems}
                selectedItem={selectedResource}
                onChange={handleResourceChange}
              />

              {/* New-name / similarity / engine / dimension — hidden for unsupported resources */}
              {!isUnsupported && (
                <>
                  {/* New-name input — only shown when creating a new resource */}
                  {isCreateNew && (
                    <TextInput
                      id="new-resource-name"
                      labelText={`Enter a new ${resourceLabel} name`}
                      placeholder={`e.g. my_${resourceLabel}`}
                      value={newResourceName}
                      invalid={(resourceNameEdited || submitted) && Boolean(newNameError)}
                      invalidText={newNameError ?? undefined}
                      onChange={handleNewNameChange}
                    />
                  )}

                  {/* Similarity/engine/dimension:
                      - loadingMappings → skeletons (API in flight after resource selection)
                      - isConfigReadOnly → disabled TextInputs (existing resource, values known)
                      - else            → editable Dropdowns (create new) */}
                  {loadingMappings && !isCreateNew ? (
                    <>
                      <TextInputSkeleton hideLabel />
                      {hasEngine && <TextInputSkeleton hideLabel />}
                    </>
                  ) : isConfigReadOnly ? (
                    <>
                      <TextInput
                        id="similarity-metric-readonly"
                        labelText={similarityLabel}
                        value={similarityLabels[similarityMetric] ?? similarityMetric}
                        disabled
                      />
                      {hasEngine && (
                        <TextInput
                          id="engine-readonly"
                          labelText="Engine"
                          value={(engineLabels?.[engine] ?? engine)}
                          disabled
                        />
                      )}
                      {storedMeta?.dimension_size !== null && storedMeta?.dimension_size !== undefined && (
                        <TextInput
                          id="dimension-size-readonly"
                          labelText="Dimension size"
                          value={String(storedMeta.dimension_size)}
                          disabled
                        />
                      )}
                    </>
                  ) : (
                    <>
                      <Dropdown
                        id="similarity-metric-select"
                        titleText={similarityLabel}
                        label={`Select ${similarityLabel.toLowerCase()}`}
                        items={vectorSimilarityOptions.map((v) => similarityLabels[v] ?? v)}
                        selectedItem={similarityLabels[similarityMetric] ?? similarityMetric}
                        onChange={({ selectedItem }: { selectedItem?: string | null }) => {
                          if (selectedItem) {
                            const value = vectorSimilarityOptions.find(
                              (v) => (similarityLabels[v] ?? v) === selectedItem
                            );
                            if (value) { setSimilarityMetric(value); }
                          }
                        }}
                      />
                      {hasEngine && (
                        <Dropdown
                          id="engine-select"
                          titleText="Engine"
                          label="Select engine"
                          items={engineOptions.map((v) => engineLabels?.[v] ?? v)}
                          selectedItem={engineLabels?.[engine] ?? engine}
                          onChange={({ selectedItem }: { selectedItem?: string | null }) => {
                            if (selectedItem) {
                              const value = engineOptions.find(
                                (v) => (engineLabels?.[v] ?? v) === selectedItem
                              );
                              if (value) { setEngine(value); }
                            }
                          }}
                        />
                      )}
                    </>
                  )}
                </>
              )}
            </div>

            {/* Milvus-only: sparse vector (BM25) toggle — hidden when unsupported (nothing to configure) */}
            {provider === VECTORDB_PROVIDERS.MILVUS && !isUnsupported && (
              <div className={styles.sparseVectorCheckbox}>
                <Checkbox
                  id="add-sparse-vector"
                  labelText="Compute sparse vectors for hybrid search"
                  checked={sparseVectorEnabled}
                  onChange={handleSparseVectorChange}
                />
              </div>
            )}

            {/* Table area — skeleton while re-enriching after resource selection */}
            {loadingMappings ? (
              <DataTableSkeleton
                columnCount={3}
                rowCount={4}
                showHeader={false}
                showToolbar={false}
              />
            ) : isUnsupported ? (
              <div className={styles.emptyStateWrapper}>
                <ErrorEmptyState
                  title={`Unsupported ${resourceLabel}`}
                  subtitle={unsupportedSubtitle}
                />
              </div>
            ) : (
              <>
                <VectorDBFeatureMappingTable
                  rows={tableRows}
                  onColumnChange={handleColumnChange}
                  onRemoveSelected={handleRemoveSelected}
                  onAddClick={() => { setIsAddModalOpen(true); }}
                />

                {/* Add feature mapping modal — inside Tearsheet so Carbon stacks it correctly */}
                <AddFeatureMappingModal
                  open={isAddModalOpen}
                  availableFeatures={availableFeatures}
                  alreadyMapped={alreadyMapped}
                  onClose={() => { setIsAddModalOpen(false); }}
                  onAdd={handleAddFeature}
                />
              </>
            )}
          </>
        )}
      </div>
    </Tearsheet>
  );
}
