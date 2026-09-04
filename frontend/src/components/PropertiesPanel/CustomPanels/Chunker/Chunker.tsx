/**
 * @file Chunker operator properties panel body.
 *
 * Renders the configuration UI for the `chunker` node.
 *
 * Structure:
 *   - "Use Docling Serve" toggle — when on, writes provider='docling_serve' and
 *     auto-sets chunk_type='hybrid'. The provider_config JSON textarea appears
 *     beneath it.
 *   - chunk_type dropdown — always visible; drives conditional field visibility:
 *       simple:   chunk_size, chunk_overlap, chunk_overlap_percentage
 *       semantic: semantic_embeddings_model, breakpoint_threshold_type, breakpoint_threshold_amount
 *       hybrid:   chunk_size, chunk_overlap, chunk_overlap_percentage, docling_tokenizer
 *   - retain_original_content toggle — always visible
 *   - Summarization accordion — toggle to enable + JSON textarea when enabled
 */

import React, { useCallback, useState } from 'react';
import { getRequiredParamValidator } from '@/utils/requiredParamValidation';
import type { OperatorFeature, OperatorMetadata } from '@/types';
import { NodeOperator } from '@/constants/operators';
import { RequiredParamTooltip } from '@/components/common';
import {
  Accordion,
  AccordionItem,
  DefinitionTooltip,
  Dropdown,
  NumberInput,
  TextArea,
  TextInput,
  Toggle,
} from '@carbon/react';
import {
  CHUNKER_ATTRIBUTE as ATTR,
  CHUNKER_DEFAULTS,
  CHUNKER_LABELS as LABEL,
  CHUNK_TYPES,
  CHUNK_TYPE_LABELS,
  BREAKPOINT_THRESHOLD_TYPES,
  BREAKPOINT_THRESHOLD_TYPE_LABELS,
  type ChunkType,
  type BreakpointThresholdType,
} from './constants';
import common from '../../CommonPropertiesPanel.module.scss';
import { isValidJsonObject } from '@/utils/json';

interface ChunkerPanelBodyProps {
  controller: any;
}

export function ChunkerPanelBody({ controller }: ChunkerPanelBodyProps): React.JSX.Element {

  // ── Operator attribute metadata ──────────────────────────────────────────
  // eslint-disable-next-line @typescript-eslint/no-unsafe-call, @typescript-eslint/no-unsafe-member-access
  const operatorMetadata = (controller?.getAppData?.()?.operatorMetadata ?? {}) as Record<string, OperatorMetadata>;
  const nodeAttributes: Record<string, OperatorFeature> = operatorMetadata[NodeOperator.CHUNKER]?.attributes ?? {};

  // ── Read persisted values ────────────────────────────────────────────────

  const chunkType: ChunkType =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.CHUNK_TYPE }) as ChunkType | undefined)
    ?? CHUNKER_DEFAULTS.CHUNK_TYPE;

  const chunkSize: number =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.CHUNK_SIZE }) as number | undefined)
    ?? CHUNKER_DEFAULTS.CHUNK_SIZE;

  const chunkOverlap: number =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.CHUNK_OVERLAP }) as number | undefined)
    ?? CHUNKER_DEFAULTS.CHUNK_OVERLAP;

  const chunkOverlapPercentage: number =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.CHUNK_OVERLAP_PERCENTAGE }) as number | undefined)
    ?? CHUNKER_DEFAULTS.CHUNK_OVERLAP_PERCENTAGE;

  const semanticEmbeddingsModel: string =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.SEMANTIC_EMBEDDINGS_MODEL }) as string | undefined)
    ?? '';

  const breakpointThresholdType: BreakpointThresholdType =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.BREAKPOINT_THRESHOLD_TYPE }) as BreakpointThresholdType | undefined)
    ?? CHUNKER_DEFAULTS.BREAKPOINT_THRESHOLD_TYPE;

  const breakpointThresholdAmount: number | undefined =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    controller?.getPropertyValue?.({ name: ATTR.BREAKPOINT_THRESHOLD_AMOUNT }) as number | undefined;

  const doclingTokenizer: string =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.DOCLING_TOKENIZER }) as string | undefined)
    ?? CHUNKER_DEFAULTS.DOCLING_TOKENIZER;

  const retainOriginalContent: boolean =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.RETAIN_ORIGINAL_CONTENT }) as boolean | undefined)
    ?? CHUNKER_DEFAULTS.RETAIN_ORIGINAL_CONTENT;

  // summarization: controller stores an object (or null when disabled).
  // Stringify only for display; null/undefined = disabled.
  const summarizationStored =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    controller?.getPropertyValue?.({ name: ATTR.SUMMARIZATION }) as Record<string, unknown> | null | undefined;
  const summarizationPersisted: string =
    summarizationStored !== null && summarizationStored !== undefined
      ? JSON.stringify(summarizationStored)
      : '';

  const provider: string | null =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.PROVIDER }) as string | undefined)
    ?? null;

  // provider_config: controller stores an object; stringify only for display.
  const providerConfigStored =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    controller?.getPropertyValue?.({ name: ATTR.PROVIDER_CONFIG }) as Record<string, unknown> | undefined;
  const providerConfigPersisted: string =
    providerConfigStored !== null && providerConfigStored !== undefined
      ? JSON.stringify(providerConfigStored)
      : '';

  // ── Derived state ────────────────────────────────────────────────────────

  const doclingServeEnabled = provider === 'docling_serve';
  const isSimple = chunkType === 'simple';
  const isSemantic = chunkType === 'semantic';
  const isHybrid = chunkType === 'hybrid';
  const showSizeOverlap = isSimple || isHybrid;
  const summarizationEnabled = summarizationStored !== null && summarizationStored !== undefined;

  // ── Local raw state for JSON textareas ───────────────────────────────────
  // Holds the in-progress typed value independently of the persisted object so
  // that typing invalid JSON mid-edit never wipes the field. Once the value is
  // valid and the user blurs, local state is cleared and the persisted value
  // drives the display.

  const [summarizationRaw, setSummarizationRaw] = useState<string | null>(null);
  const [providerConfigRaw, setProviderConfigRaw] = useState<string | null>(null);

  // ── Touched state for JSON textarea validation ───────────────────────────

  type JsonField = 'summarization' | 'providerConfig';
  const [touchedFields, setTouchedFields] = useState<Record<JsonField, boolean>>({
    summarization: false,
    providerConfig: false,
  });

  const markTouched = (field: JsonField): void => {
    setTouchedFields((prev) => ({ ...prev, [field]: true }));
  };

  // ── Helpers ──────────────────────────────────────────────────────────────

  // ── Required param validator ──────────────────────────────────────────────
  const validate = getRequiredParamValidator(nodeAttributes);
  const chunkTypeValidation = validate(ATTR.CHUNK_TYPE, chunkType);
  const chunkSizeValidation = validate(ATTR.CHUNK_SIZE, chunkSize);
  const chunkOverlapValidation = validate(ATTR.CHUNK_OVERLAP, chunkOverlap);
  const chunkOverlapPercentageValidation = validate(
    ATTR.CHUNK_OVERLAP_PERCENTAGE, chunkOverlapPercentage
  );
  const semanticEmbeddingsModelValidation = validate(
    ATTR.SEMANTIC_EMBEDDINGS_MODEL, semanticEmbeddingsModel
  );
  const breakpointThresholdTypeValidation = validate(
    ATTR.BREAKPOINT_THRESHOLD_TYPE, breakpointThresholdType
  );
  const breakpointThresholdAmountValidation = validate(
    ATTR.BREAKPOINT_THRESHOLD_AMOUNT, breakpointThresholdAmount
  );
  const doclingTokenizerValidation = validate(ATTR.DOCLING_TOKENIZER, doclingTokenizer);
  const summarizationValidation = validate(ATTR.SUMMARIZATION, summarizationStored);
  const providerConfigValidation = validate(ATTR.PROVIDER_CONFIG, providerConfigStored);

  const update = useCallback((name: string, value: unknown): void => {
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    controller?.updatePropertyValue?.({ name }, value);
  }, [controller]);

  const handleChunkTypeChange = useCallback(
    ({ selectedItem }: { selectedItem: ChunkType | null }): void => {
      if (selectedItem) { update(ATTR.CHUNK_TYPE, selectedItem); }
    }, [update]
  );

  const handleBreakpointTypeChange = useCallback(
    ({ selectedItem }: { selectedItem: BreakpointThresholdType | null }): void => {
      if (selectedItem) { update(ATTR.BREAKPOINT_THRESHOLD_TYPE, selectedItem); }
    }, [update]
  );

  const handleDoclingServeToggle = useCallback(
    (checked: boolean): void => {
      update(ATTR.PROVIDER, checked ? 'docling_serve' : null);
      if (checked) {
        // Auto-set hybrid — docling_serve works best with hybrid and the backend
        // will warn if chunk_type is anything else (DOCLING_SERVE_CHUNK_TYPE_MISMATCH)
        update(ATTR.CHUNK_TYPE, 'hybrid');
      } else {
        // Clear provider_config so stale config isn't sent
        update(ATTR.PROVIDER_CONFIG, null);
      }
    }, [update]
  );

  const handleSummarizationToggle = useCallback(
    (checked: boolean): void => {
      // Enable: seed with minimum meaningful object
      // Disable: write null so backend omits the key entirely.
      update(ATTR.SUMMARIZATION, checked ? { provider: 'litellm', provider_config: {} } : null);
    }, [update]
  );

  return (
    <div className={common.commonPropertiesPanelBody}>

      {/* ═══════════════════════════════════════════════════════════════════
          DOCLING SERVE TOGGLE
      ═══════════════════════════════════════════════════════════════════ */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <DefinitionTooltip
            definition="Route chunking to a remote Docling Serve API. When enabled, Chunk type is set to 'hybrid' (recommended) but can still be changed. Provider configuration must include at minimum an api_base URL."
            openOnHover
            align="right"
          >
            {LABEL.USE_DOCLING_SERVE}
          </DefinitionTooltip>
        </div>
        <Toggle
          id="chunker-use-docling-serve"
          labelText={LABEL.USE_DOCLING_SERVE}
          hideLabel
          labelA="Off"
          labelB="On"
          toggled={doclingServeEnabled}
          onToggle={handleDoclingServeToggle}
        />
      </div>

      {/* Provider config — only when Docling Serve is active */}
      {doclingServeEnabled && (
        <div className={common.subSection}>
          <div className={common.formField}>
            <div className={common.labelWithTooltip}>
              <RequiredParamTooltip
                paramId={ATTR.PROVIDER_CONFIG}
                nodeAttributes={nodeAttributes}
                definition='Docling Serve connection settings as a JSON object. At minimum provide api_base. E.g. {"api_base": "https://docling-serve.example.com", "api_key": "...", "timeout": 300}'
              >
                {LABEL.PROVIDER_CONFIG}
              </RequiredParamTooltip>
            </div>
            <TextArea
              id="chunker-provider-config"
              labelText={LABEL.PROVIDER_CONFIG}
              hideLabel
              rows={4}
              value={providerConfigRaw ?? providerConfigPersisted}
              placeholder='{"api_base": "https://docling-serve.example.com"}'
              invalid={
                providerConfigValidation.isInvalid ||
                (touchedFields.providerConfig && !isValidJsonObject(providerConfigRaw ?? providerConfigPersisted))
              }
              invalidText={
                providerConfigValidation.isInvalid
                  ? providerConfigValidation.errorMessage
                  : 'Provider configuration must be a valid JSON object.'
              }
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => {
                const raw = e.target.value;
                setProviderConfigRaw(raw);
                if (raw === '' || isValidJsonObject(raw)) {
                  update(ATTR.PROVIDER_CONFIG, raw === '' ? {} : JSON.parse(raw) as object);
                }
              }}
              onBlur={() => {
                markTouched('providerConfig');
                if (providerConfigRaw !== null && isValidJsonObject(providerConfigRaw)) {
                  setProviderConfigRaw(null);
                }
              }}
            />
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          CHUNK TYPE
      ═══════════════════════════════════════════════════════════════════ */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.CHUNK_TYPE}
            nodeAttributes={nodeAttributes}
            definition="The strategy used to split document text into chunks."
          >
            {LABEL.CHUNK_TYPE}
          </RequiredParamTooltip>
        </div>
        <Dropdown
          id="chunker-chunk-type"
          titleText={LABEL.CHUNK_TYPE}
          hideLabel
          label="Select chunk type"
          items={[...CHUNK_TYPES]}
          selectedItem={chunkType}
          itemToString={(item: ChunkType | null) => (item ? CHUNK_TYPE_LABELS[item] : '')}
          invalid={chunkTypeValidation.isInvalid}
          invalidText={chunkTypeValidation.errorMessage}
          onChange={handleChunkTypeChange}
        />
      </div>

      {/* ═══════════════════════════════════════════════════════════════════
          SIMPLE / HYBRID — size + overlap
      ═══════════════════════════════════════════════════════════════════ */}
      {showSizeOverlap && (
        <div className={common.subSection}>
          <div className={common.formField}>
            <div className={common.labelWithTooltip}>
              <RequiredParamTooltip
                paramId={ATTR.CHUNK_SIZE}
                nodeAttributes={nodeAttributes}
                definition={
                  isHybrid
                    ? 'Chunk size in tokens (100–2048).'
                    : 'Chunk size in characters (500–5000).'
                }
              >
                {LABEL.CHUNK_SIZE}
              </RequiredParamTooltip>
            </div>
            <NumberInput
              id="chunker-chunk-size"
              label={LABEL.CHUNK_SIZE}
              hideLabel
              value={chunkSize}
              min={isHybrid ? 100 : 500}
              max={isHybrid ? 2048 : 5000}
              step={isHybrid ? 64 : 100}
              invalid={chunkSizeValidation.isInvalid}
              invalidText={chunkSizeValidation.errorMessage}
              onChange={(_e: unknown, { value }: { value: number | string }) => {
                const n = Number(value);
                if (Number.isFinite(n) && n > 0) { update(ATTR.CHUNK_SIZE, n); }
              }}
            />
          </div>

          <div className={common.formField}>
            <div className={common.labelWithTooltip}>
              <RequiredParamTooltip
                paramId={ATTR.CHUNK_OVERLAP}
                nodeAttributes={nodeAttributes}
                definition="Number of characters/tokens shared between consecutive chunks (0–512)."
              >
                {LABEL.CHUNK_OVERLAP}
              </RequiredParamTooltip>
            </div>
            <NumberInput
              id="chunker-chunk-overlap"
              label={LABEL.CHUNK_OVERLAP}
              hideLabel
              value={chunkOverlap}
              min={0}
              max={512}
              step={10}
              invalid={chunkOverlapValidation.isInvalid}
              invalidText={chunkOverlapValidation.errorMessage}
              onChange={(_e: unknown, { value }: { value: number | string }) => {
                const n = Number(value);
                if (Number.isFinite(n) && n >= 0) { update(ATTR.CHUNK_OVERLAP, n); }
              }}
            />
          </div>

          <div className={common.formField}>
            <div className={common.labelWithTooltip}>
              <RequiredParamTooltip
                paramId={ATTR.CHUNK_OVERLAP_PERCENTAGE}
                nodeAttributes={nodeAttributes}
                definition="Overlap expressed as a percentage of Chunk size (0–40). Values above 20 produce a warning."
              >
                {LABEL.CHUNK_OVERLAP_PERCENTAGE}
              </RequiredParamTooltip>
            </div>
            <NumberInput
              id="chunker-chunk-overlap-percentage"
              label={LABEL.CHUNK_OVERLAP_PERCENTAGE}
              hideLabel
              value={chunkOverlapPercentage}
              min={0}
              max={40}
              step={1}
              invalid={chunkOverlapPercentageValidation.isInvalid}
              invalidText={chunkOverlapPercentageValidation.errorMessage}
              onChange={(_e: unknown, { value }: { value: number | string }) => {
                const n = Number(value);
                if (Number.isFinite(n) && n >= 0) { update(ATTR.CHUNK_OVERLAP_PERCENTAGE, n); }
              }}
            />
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          HYBRID — Docling tokenizer
      ═══════════════════════════════════════════════════════════════════ */}
      {isHybrid && (
        <div className={common.formField}>
          <div className={common.labelWithTooltip}>
            <RequiredParamTooltip
              paramId={ATTR.DOCLING_TOKENIZER}
              nodeAttributes={nodeAttributes}
              definition="HuggingFace tokenizer model used for Docling chunking."
            >
              {LABEL.DOCLING_TOKENIZER}
            </RequiredParamTooltip>
          </div>
          <TextInput
            id="chunker-docling-tokenizer"
            labelText={LABEL.DOCLING_TOKENIZER}
            hideLabel
            placeholder="sentence-transformers/all-MiniLM-L6-v2"
            value={doclingTokenizer}
            invalid={doclingTokenizerValidation.isInvalid}
            invalidText={doclingTokenizerValidation.errorMessage}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
              update(ATTR.DOCLING_TOKENIZER, e.target.value);
            }}
          />
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          SEMANTIC — embeddings model + breakpoint settings
      ═══════════════════════════════════════════════════════════════════ */}
      {isSemantic && (
        <div className={common.subSection}>
          <div className={common.formField}>
            <div className={common.labelWithTooltip}>
              <RequiredParamTooltip
                paramId={ATTR.SEMANTIC_EMBEDDINGS_MODEL}
                nodeAttributes={nodeAttributes}
                definition="Ollama model used to generate embeddings in semantic chunking."
              >
                {LABEL.SEMANTIC_EMBEDDINGS_MODEL}
              </RequiredParamTooltip>
            </div>
            <TextInput
              id="chunker-semantic-embeddings-model"
              labelText={LABEL.SEMANTIC_EMBEDDINGS_MODEL}
              hideLabel
              placeholder="e.g. nomic-embed-text"
              value={semanticEmbeddingsModel}
              invalid={semanticEmbeddingsModelValidation.isInvalid || semanticEmbeddingsModel.trim() === ''}
              invalidText={
                semanticEmbeddingsModelValidation.isInvalid
                  ? semanticEmbeddingsModelValidation.errorMessage
                  : 'Embeddings model is required for semantic chunking.'
              }
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                update(ATTR.SEMANTIC_EMBEDDINGS_MODEL, e.target.value);
              }}
            />
          </div>

          <div className={common.formField}>
            <div className={common.labelWithTooltip}>
              <RequiredParamTooltip
                paramId={ATTR.BREAKPOINT_THRESHOLD_TYPE}
                nodeAttributes={nodeAttributes}
                definition="Method used to determine semantic chunk boundaries."
              >
                {LABEL.BREAKPOINT_THRESHOLD_TYPE}
              </RequiredParamTooltip>
            </div>
            <Dropdown
              id="chunker-breakpoint-threshold-type"
              titleText={LABEL.BREAKPOINT_THRESHOLD_TYPE}
              hideLabel
              label="Select threshold type"
              items={[...BREAKPOINT_THRESHOLD_TYPES]}
              selectedItem={breakpointThresholdType}
              itemToString={(item: BreakpointThresholdType | null) =>
                item ? BREAKPOINT_THRESHOLD_TYPE_LABELS[item] : ''
              }
              invalid={breakpointThresholdTypeValidation.isInvalid}
              invalidText={breakpointThresholdTypeValidation.errorMessage}
              onChange={handleBreakpointTypeChange}
            />
          </div>

          <div className={common.formField}>
            <div className={common.labelWithTooltip}>
              <RequiredParamTooltip
                paramId={ATTR.BREAKPOINT_THRESHOLD_AMOUNT}
                nodeAttributes={nodeAttributes}
                definition="Threshold value for the selected breakpoint type (e.g., 95.0 for 95th percentile)."
              >
                {LABEL.BREAKPOINT_THRESHOLD_AMOUNT}
              </RequiredParamTooltip>
            </div>
            <NumberInput
              id="chunker-breakpoint-threshold-amount"
              label={LABEL.BREAKPOINT_THRESHOLD_AMOUNT}
              hideLabel
              value={breakpointThresholdAmount ?? ''}
              min={0}
              step={0.5}
              invalid={breakpointThresholdAmountValidation.isInvalid}
              invalidText={breakpointThresholdAmountValidation.errorMessage}
              onChange={(_e: unknown, { value }: { value: number | string }) => {
                const n = Number(value);
                update(ATTR.BREAKPOINT_THRESHOLD_AMOUNT, Number.isFinite(n) && n >= 0 ? n : undefined);
              }}
            />
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          RETAIN ORIGINAL CONTENT
      ═══════════════════════════════════════════════════════════════════ */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR.RETAIN_ORIGINAL_CONTENT}
            nodeAttributes={nodeAttributes}
            definition="Keep the original content column after chunking."
          >
            {LABEL.RETAIN_ORIGINAL_CONTENT}
          </RequiredParamTooltip>
        </div>
        <Toggle
          id="chunker-retain-original-content"
          labelText={LABEL.RETAIN_ORIGINAL_CONTENT}
          hideLabel
          labelA="Off"
          labelB="On"
          toggled={retainOriginalContent}
          onToggle={(checked: boolean) => { update(ATTR.RETAIN_ORIGINAL_CONTENT, checked); }}
        />
      </div>

      {/* ═══════════════════════════════════════════════════════════════════
          SUMMARIZATION
      ═══════════════════════════════════════════════════════════════════ */}
     <Accordion align="start">
        <AccordionItem title="Summarization">
          <div className={common.accordionContent}>
          <div className={common.formField}>
            <div className={common.labelWithTooltip}>
              <RequiredParamTooltip
                paramId={ATTR.SUMMARIZATION}
                nodeAttributes={nodeAttributes}
                definition="Generate a summary for each chunk using LiteLLM or watsonx."
              >
                {LABEL.SUMMARIZATION}
              </RequiredParamTooltip>
            </div>
            <Toggle
              id="chunker-summarization-toggle"
              labelText={LABEL.SUMMARIZATION}
              hideLabel
              labelA="Off"
              labelB="On"
              toggled={summarizationEnabled}
              onToggle={handleSummarizationToggle}
            />
          </div>

          {summarizationEnabled && (
            <div className={common.subSection}>
              <div className={common.formField}>
                <div className={common.labelWithTooltip}>
                  <RequiredParamTooltip
                    paramId={ATTR.SUMMARIZATION}
                    nodeAttributes={nodeAttributes}
                    definition='Summarization configuration as a JSON object. E.g. {"provider": "litellm", "provider_config": {"model_id": "ollama/llama3.2", "api_base": "http://localhost:11434/v1"}}'
                  >
                    {LABEL.SUMMARIZATION_CONFIG}
                  </RequiredParamTooltip>
                </div>
                <TextArea
                  id="chunker-summarization-config"
                  labelText={LABEL.SUMMARIZATION_CONFIG}
                  hideLabel
                  rows={5}
                  value={summarizationRaw ?? summarizationPersisted}
                  placeholder='{}'
                  invalid={
                    summarizationValidation.isInvalid ||
                    (touchedFields.summarization && !isValidJsonObject(summarizationRaw ?? summarizationPersisted))
                  }
                  invalidText={
                    summarizationValidation.isInvalid
                      ? summarizationValidation.errorMessage
                      : 'Summarization configuration must be a valid JSON object.'
                  }
                  onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => {
                    const raw = e.target.value;
                    setSummarizationRaw(raw);
                    // Only persist when valid JSON. Empty string keeps local state only
                    // so clearing the input doesn't disable summarization mid-edit.
                    if (raw !== '' && isValidJsonObject(raw)) {
                      update(ATTR.SUMMARIZATION, JSON.parse(raw) as object);
                    }
                  }}
                  onBlur={() => {
                    markTouched('summarization');
                    if (summarizationRaw !== null && isValidJsonObject(summarizationRaw)) {
                      setSummarizationRaw(null);
                    }
                  }}
                />
              </div>
            </div>
          )}
          </div>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
