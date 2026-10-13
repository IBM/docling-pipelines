/**
 * @file Extract operator properties panel body.
 *
 * Renders the configuration UI for the `extract_operator` node.
 */

import React, { useCallback, useState } from 'react';
import { getRequiredParamValidator } from '@/utils/requiredParamValidation';
import { RequiredParamTooltip, VaultInput } from '@/components/common';
import {
  Accordion,
  AccordionItem,
  Checkbox,
  DefinitionTooltip,
  Dropdown,
  NumberInput,
  TextArea,
  TextInput,
  Toggle,
} from '@carbon/react';
import type { OperatorFeature, OperatorMetadata } from '@/types';
import { NodeOperator } from '@/constants/operators';
import {
  ACCELERATOR_KEY,
  ADDITIONAL_FORMATS,
  ADDITIONAL_FORMAT_LABELS,
  ASR_PIPELINE_KEY,
  DOCLING_ENTITY_CONFIG_KEY,
  DOCLING_LIBRARY_CONFIG_KEY,
  DOCLING_SERVE_CONFIG_KEY,
  ENTITY_PROVIDER_LABELS,
  ENTITY_PROVIDERS,
  EXTRACT_ATTRIBUTE as ATTR,
  EXTRACTION_KEY,
  EXTRACT_LABELS as LABEL,
  IMAGE_EXPORT_MODE_LABELS,
  IMAGE_EXPORT_MODES,
  LLM_ENTITY_CONFIG_KEY,
  PDF_BACKEND_LABELS,
  PDF_BACKENDS,
  TEXT_PROVIDER_LABELS,
  TEXT_PROVIDERS,
  VLM_ENGINE_LABELS,
  VLM_ENGINES,
  VLM_PIPELINE_KEY,
  WATSONX_CONTAINER_KINDS,
  WATSONX_ENTITY_CONFIG_KEY,
  type AdditionalFormat,
  type EntityProvider,
  type ImageExportMode,
  type PdfBackend,
  type TextProvider,
  type VlmEngine,
  type WatsonxContainerKind,
} from './constants';
import styles from './Extract.module.scss';
import common from '../../CommonPropertiesPanel.module.scss';
import { TagInput } from '@/components/common/TagInput/TagInput';
import { isValidJsonObject } from '@/utils/json';
import { useProviderConfigDefaults } from '@/hooks/useProviderConfigDefaults';

interface ExtractPanelBodyProps {
  controller: any;
}

export function ExtractPanelBody({ controller }: ExtractPanelBodyProps): React.JSX.Element {

  // ── Operator metadata ─────────────────────────────────────────────────────
  // eslint-disable-next-line @typescript-eslint/no-unsafe-call
  const operatorMetadata = (controller?.getAppData?.()?.operatorMetadata ?? {}) as Record<string, OperatorMetadata>;
  const nodeAttributes: Record<string, OperatorFeature> = operatorMetadata[NodeOperator.EXTRACT]?.attributes ?? {};

  // Convenience accessors for nested attribute metadata.
  // text_extraction.properties.<field>
  const textAttrs = (nodeAttributes['text_extraction'] as Record<string, unknown> | undefined)
    ?.properties as Record<string, OperatorFeature> | undefined ?? {};
  // text_extraction.properties.provider_config.providers.<provider>.<field>
  const textProviderSchemas = (textAttrs['provider_config'] as Record<string, unknown> | undefined)
    ?.providers as Record<string, Record<string, OperatorFeature>> | undefined ?? {};
  const serveAttrs = textProviderSchemas['docling_serve']?.properties ?? {};

  // entity_extraction.properties.<field>
  const entityAttrs = (nodeAttributes['entity_extraction'] as Record<string, unknown> | undefined)
    ?.properties as Record<string, OperatorFeature> | undefined ?? {};
  // entity_extraction.properties.provider_config.providers.<provider>.<field>
  const entityProviderSchemas = (entityAttrs['provider_config'] as Record<string, unknown> | undefined)
    ?.providers as Record<string, Record<string, OperatorFeature>> | undefined ?? {};
  const litellmAttrs = entityProviderSchemas['litellm']?.properties ?? {};
  const watsonxAttrs = entityProviderSchemas['watsonx']?.properties ?? {};

  /** Returns the metadata default for a field, or undefined if not available. */
  const metaDefault = <T,>(attrs: Record<string, OperatorFeature>, field: string): T | undefined =>
    attrs[field]?.default as T | undefined;

  /** Returns true when value is null or undefined. */
  const isNil = (value: unknown): value is null | undefined => value === null || value === undefined;

  /** Reads a string value from a provider config object or returns '' if absent/non-string. */
  const strVal = (cfg: Record<string, unknown>, key: string): string =>
    typeof cfg[key] === 'string' ? cfg[key] : '';

  /** Reads a number value from a provider config object or returns the fallback. */
  const numVal = (cfg: Record<string, unknown>, key: string, fallback: number | ''): number | '' =>
    typeof cfg[key] === 'number' ? cfg[key] : fallback;

  // ── Top-level objects read from node.parameters ──────────────────────────
  // eslint-disable-next-line @typescript-eslint/no-unsafe-call
  const textExtractionRaw = controller?.getPropertyValue?.({ name: ATTR.TEXT_EXTRACTION }) as Record<string, unknown> | undefined;
  const textExtraction: Record<string, unknown> = textExtractionRaw ?? {};

  // eslint-disable-next-line @typescript-eslint/no-unsafe-call
  const entityExtractionRaw = controller?.getPropertyValue?.({ name: ATTR.ENTITY_EXTRACTION }) as Record<string, unknown> | undefined;
  const entityExtraction: Record<string, unknown> = entityExtractionRaw ?? {};

  // ── Text extraction field values ─────────────────────────────────────────
  const textProvider: TextProvider | undefined =
    (textExtraction[EXTRACTION_KEY.PROVIDER] as TextProvider | undefined)
    ?? metaDefault<TextProvider>(textAttrs, EXTRACTION_KEY.PROVIDER);

  const textProviderConfig: Record<string, unknown> =
    (textExtraction[EXTRACTION_KEY.PROVIDER_CONFIG] as Record<string, unknown> | undefined) ?? {};

  const textDocColumn: string =
    (textExtraction[EXTRACTION_KEY.DOC_COLUMN] as string | undefined)
    ?? metaDefault<string>(textAttrs, EXTRACTION_KEY.DOC_COLUMN)
    ?? '';

  // ── Entity extraction field values ───────────────────────────────────────
  const entityProvider: EntityProvider | undefined =
    (entityExtraction[EXTRACTION_KEY.PROVIDER] as EntityProvider | undefined)
    ?? metaDefault<EntityProvider>(entityAttrs, EXTRACTION_KEY.PROVIDER);

  const entityProviderConfig: Record<string, unknown> =
    (entityExtraction[EXTRACTION_KEY.PROVIDER_CONFIG] as Record<string, unknown> | undefined) ?? {};

  const entityOutputColumn: string =
    (entityExtraction[EXTRACTION_KEY.OUTPUT_COLUMN] as string | undefined)
    ?? metaDefault<string>(entityAttrs, EXTRACTION_KEY.OUTPUT_COLUMN)
    ?? '';

  const entityMaxDocChars: number | undefined =
    (entityExtraction[EXTRACTION_KEY.ENTITY_MAX_DOC_CHARS] as number | undefined)
    ?? metaDefault<number>(entityAttrs, EXTRACTION_KEY.ENTITY_MAX_DOC_CHARS);

  const entityExpandData: boolean =
    (entityExtraction[EXTRACTION_KEY.EXPAND_EXTRACTED_DATA] as boolean | undefined)
    ?? metaDefault<boolean>(entityAttrs, EXTRACTION_KEY.EXPAND_EXTRACTED_DATA)
    ?? false;

  const entityCustomSchemaValue = entityExtraction[EXTRACTION_KEY.CUSTOM_SCHEMA];
  const entityCustomSchemaPersisted: string = !isNil(entityCustomSchemaValue)
    ? JSON.stringify(entityCustomSchemaValue, null, 2)
    : '';

  // ── Top-level values ─────────────────────────────────────────────────────
  const maxWorkers: number | undefined =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    controller?.getPropertyValue?.({ name: ATTR.MAX_WORKERS }) as number | undefined;

  const useProcesses: boolean =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR.USE_PROCESSES }) as boolean | undefined)
    ?? metaDefault<boolean>(nodeAttributes, 'use_processes')
    ?? false;

  // ── Update helpers ────────────────────────────────────────────────────────
  const update = useCallback((name: string, value: unknown): void => {
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    controller?.updatePropertyValue?.({ name }, value);
  }, [controller]);

  /** Merges a single key into the text_extraction object and persists it. */
  const updateTextExtraction = useCallback((key: string, value: unknown): void => {
    update(ATTR.TEXT_EXTRACTION, { ...textExtraction, [key]: value });
  }, [update, textExtraction]);

  /** Merges a single key into text_extraction.provider_config and persists text_extraction. */
  const updateTextProviderConfig = useCallback((key: string, value: unknown): void => {
    update(ATTR.TEXT_EXTRACTION, {
      ...textExtraction,
      provider_config: { ...textProviderConfig, [key]: value },
    });
  }, [update, textExtraction, textProviderConfig]);

  /** Merges a single child key into a nested object inside text_extraction.provider_config. */
  const updateTextProviderConfigNested = useCallback((
    parentKey: string,
    childKey: string,
    value: unknown
  ): void => {
    const parent = (textProviderConfig[parentKey] as Record<string, unknown> | undefined) ?? {};
    update(ATTR.TEXT_EXTRACTION, {
      ...textExtraction,
      provider_config: {
        ...textProviderConfig,
        [parentKey]: { ...parent, [childKey]: value },
      },
    });
  }, [update, textExtraction, textProviderConfig]);

  const entityProviderActive = entityProvider !== 'none';

  /** Merges a single key into entity_extraction.provider_config and persists entity_extraction. */
  const updateEntityProviderConfig = useCallback((key: string, value: unknown): void => {
    update(ATTR.ENTITY_EXTRACTION, {
      ...entityExtraction,
      provider_config: { ...entityProviderConfig, [key]: value },
    });
  }, [update, entityExtraction, entityProviderConfig]);

  /** Merges a single key into the entity_extraction object and persists it. */
  const updateEntityExtraction = useCallback((key: string, value: unknown): void => {
    update(ATTR.ENTITY_EXTRACTION, { ...entityExtraction, [key]: value });
  }, [update, entityExtraction]);

  const [touchedFields, setTouchedFields] = useState<Record<string, boolean>>({
    entityDoclingVlmPipeline: false,
    entityCustomSchema: false,
    vlmEngineOptions: false,
  });

  // Raw string state for JSON textareas — holds the in-progress typed value
  // independently of the persisted value so typing invalid JSON
  // mid-edit doesn't wipe the field.
  const [vlmEngineOptionsRaw, setVlmEngineOptionsRaw] = useState<string | null>(null);
  const [entityDoclingVlmPipelineRaw, setEntityDoclingVlmPipelineRaw] = useState<string | null>(null);
  const [customSchemaRaw, setCustomSchemaRaw] = useState<string | null>(null);

  const markFieldAsTouched = (field: string): void => {
    setTouchedFields((previous) => ({ ...previous, [field]: true }));
  };

  useProviderConfigDefaults(controller, nodeAttributes);

  // ── Required param validator ──────────────────────────────────────────────
  const validate = getRequiredParamValidator(nodeAttributes);
  const textExtractionValidation = validate(ATTR.TEXT_EXTRACTION, textExtractionRaw);
  const entityExtractionValidation = validate(ATTR.ENTITY_EXTRACTION, entityExtractionRaw);
  const maxWorkersValidation = validate(ATTR.MAX_WORKERS, maxWorkers);

  // ── Derived docling_library config values ─────────────────────────────────
  const vlmConfig = textProviderConfig[DOCLING_LIBRARY_CONFIG_KEY.VLM_PIPELINE] as Record<string, unknown> | null | undefined;
  const vlmEnabled = !isNil(vlmConfig);
  const vlmPreset: string = typeof vlmConfig?.preset === 'string' ? vlmConfig.preset : 'granite_docling';
  const vlmEngine: VlmEngine = (vlmConfig?.engine as VlmEngine | undefined) ?? 'transformers';
  const vlmEngineOptions: string = !isNil(vlmConfig?.engine_options)
    ? JSON.stringify(vlmConfig.engine_options, null, 2)
    : '';

  const asrConfig = textProviderConfig[DOCLING_LIBRARY_CONFIG_KEY.ASR_PIPELINE] as Record<string, unknown> | null | undefined;
  const asrEnabled = !isNil(asrConfig);
  const asrModelId: string = typeof asrConfig?.model_id === 'string' ? asrConfig.model_id : '';

  const additionalFormats: AdditionalFormat[] = Array.isArray(textProviderConfig[DOCLING_LIBRARY_CONFIG_KEY.ADDITIONAL_FORMATS])
    ? (textProviderConfig[DOCLING_LIBRARY_CONFIG_KEY.ADDITIONAL_FORMATS] as AdditionalFormat[])
    : [];

  const standardPipelineConfig = textProviderConfig[DOCLING_LIBRARY_CONFIG_KEY.STANDARD_PIPELINE] as Record<string, unknown> | null | undefined;
  const standardPipelineEnabled = !isNil(standardPipelineConfig);
  const acceleratorConfig = (standardPipelineConfig?.accelerator as Record<string, unknown> | undefined) ?? {};
  const acceleratorDevice: string = typeof acceleratorConfig[ACCELERATOR_KEY.DEVICE] === 'string'
    ? (acceleratorConfig[ACCELERATOR_KEY.DEVICE] as string)
    : '';
  const acceleratorNumThreads: number | undefined = typeof acceleratorConfig[ACCELERATOR_KEY.NUM_THREADS] === 'number'
    ? (acceleratorConfig[ACCELERATOR_KEY.NUM_THREADS] as number)
    : undefined;

  // ── Derived docling_serve config values ───────────────────────────────────
  const serveBaseUrl: string = typeof textProviderConfig[DOCLING_SERVE_CONFIG_KEY.BASE_URL] === 'string'
    ? (textProviderConfig[DOCLING_SERVE_CONFIG_KEY.BASE_URL] as string)
    : metaDefault<string>(serveAttrs, 'base_url') ?? '';
  const serveApiKey: string = typeof textProviderConfig[DOCLING_SERVE_CONFIG_KEY.API_KEY] === 'string' // pragma: allowlist secret
    ? (textProviderConfig[DOCLING_SERVE_CONFIG_KEY.API_KEY] as string)
    : '';
  const serveTimeout: number | undefined = typeof textProviderConfig[DOCLING_SERVE_CONFIG_KEY.TIMEOUT] === 'number'
    ? (textProviderConfig[DOCLING_SERVE_CONFIG_KEY.TIMEOUT] as number)
    : metaDefault<number>(serveAttrs, 'timeout');
  const servePollInterval: number | undefined = typeof textProviderConfig[DOCLING_SERVE_CONFIG_KEY.POLL_INTERVAL] === 'number'
    ? (textProviderConfig[DOCLING_SERVE_CONFIG_KEY.POLL_INTERVAL] as number)
    : metaDefault<number>(serveAttrs, 'poll_interval');
  const serveMaxRetries: number | undefined = typeof textProviderConfig[DOCLING_SERVE_CONFIG_KEY.MAX_RETRIES] === 'number'
    ? (textProviderConfig[DOCLING_SERVE_CONFIG_KEY.MAX_RETRIES] as number)
    : metaDefault<number>(serveAttrs, 'max_retries');
  const serveVerifySsl: boolean = typeof textProviderConfig[DOCLING_SERVE_CONFIG_KEY.VERIFY_SSL] === 'boolean'
    ? (textProviderConfig[DOCLING_SERVE_CONFIG_KEY.VERIFY_SSL] as boolean)
    : metaDefault<boolean>(serveAttrs, 'verify_ssl') ?? false;
  const serveDoOcr: boolean = typeof textProviderConfig[DOCLING_SERVE_CONFIG_KEY.DO_OCR] === 'boolean'
    ? (textProviderConfig[DOCLING_SERVE_CONFIG_KEY.DO_OCR] as boolean)
    : metaDefault<boolean>(serveAttrs, 'do_ocr') ?? false;
  const servePdfBackend: PdfBackend | undefined = (textProviderConfig[DOCLING_SERVE_CONFIG_KEY.PDF_BACKEND] as PdfBackend | undefined)
    ?? metaDefault<PdfBackend>(serveAttrs, 'pdf_backend');
  const serveOcrEngine: string = typeof textProviderConfig[DOCLING_SERVE_CONFIG_KEY.OCR_ENGINE] === 'string'
    ? (textProviderConfig[DOCLING_SERVE_CONFIG_KEY.OCR_ENGINE] as string)
    : '';
  const serveOcrLanguages: string[] = Array.isArray(textProviderConfig[DOCLING_SERVE_CONFIG_KEY.OCR_LANGUAGES])
    ? (textProviderConfig[DOCLING_SERVE_CONFIG_KEY.OCR_LANGUAGES] as string[])
    : [];
  const serveTableMode: string = typeof textProviderConfig[DOCLING_SERVE_CONFIG_KEY.TABLE_MODE] === 'string'
    ? (textProviderConfig[DOCLING_SERVE_CONFIG_KEY.TABLE_MODE] as string)
    : '';
  const serveImageExportMode: ImageExportMode | undefined =
    (textProviderConfig[DOCLING_SERVE_CONFIG_KEY.IMAGE_EXPORT_MODE] as ImageExportMode | undefined)
    ?? metaDefault<ImageExportMode>(serveAttrs, 'image_export_mode');

  return (
    <div className={styles.panelBody}>
      <Accordion align="start">

      {/* ═══════════════════════════════════════════════════════════════════
          TEXT EXTRACTION
      ═══════════════════════════════════════════════════════════════════ */}
      <AccordionItem title="Text Extraction" open>

        {/* Provider */}
        <div className={styles.formField}>
          <div className={common.labelWithTooltip}>
            <RequiredParamTooltip
              paramId={ATTR.TEXT_EXTRACTION}
              nodeAttributes={nodeAttributes}
              definition="Choose between local Docling processing or a remote Docling Serve instance."
            >
              {LABEL.TEXT_PROVIDER}
            </RequiredParamTooltip>
          </div>
          <Dropdown
            id="text_provider"
            titleText={LABEL.TEXT_PROVIDER}
            hideLabel
            label="Select provider"
            items={[...TEXT_PROVIDERS]}
            selectedItem={textProvider}
            itemToString={(item: TextProvider | null) => (item ? TEXT_PROVIDER_LABELS[item] : '')}
            invalid={textExtractionValidation.isInvalid}
            invalidText={textExtractionValidation.errorMessage}
            onChange={({ selectedItem }: { selectedItem: TextProvider | null }) => {
              if (selectedItem) { updateTextExtraction('provider', selectedItem); }
            }}
          />
        </div>

        {/* ── docling_library provider_config ─────────────────────────── */}
        {textProvider === 'docling_library' && (
          <div className={common.subSection}>

            {/* VLM pipeline */}
            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="Enable the Vision-Language Model pipeline for enhanced document extraction."
                  openOnHover
                  align="right"
                >
                  {LABEL.VLM_PIPELINE}
                </DefinitionTooltip>
              </div>
              <Toggle
                id="vlm_pipeline_enabled"
                labelText={LABEL.VLM_PIPELINE}
                hideLabel
                labelA="Off"
                labelB="On"
                toggled={vlmEnabled}
                onToggle={(checked: boolean) => {
                  if (checked) {
                    updateTextProviderConfig(DOCLING_LIBRARY_CONFIG_KEY.VLM_PIPELINE, {
                      [VLM_PIPELINE_KEY.PRESET]: 'granite_docling',
                      [VLM_PIPELINE_KEY.ENGINE]: 'transformers',
                    });
                  } else {
                    const { vlm_pipeline: _removed, ...rest } = textProviderConfig;
                    update(ATTR.TEXT_EXTRACTION, { ...textExtraction, provider_config: rest });
                  }
                }}
              />
            </div>

            {vlmEnabled && (
              <div className={common.subSection}>
                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="VLM preset name (e.g., 'granite_docling', 'fast')."
                      openOnHover
                      align="right"
                    >
                      {LABEL.VLM_PRESET}
                    </DefinitionTooltip>
                  </div>
                  <TextInput
                    id="vlm_preset"
                    labelText={LABEL.VLM_PRESET}
                    hideLabel
                    value={vlmPreset}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                      updateTextProviderConfigNested(
                        DOCLING_LIBRARY_CONFIG_KEY.VLM_PIPELINE,
                        VLM_PIPELINE_KEY.PRESET,
                        e.target.value
                      );
                    }}
                  />
                </div>

                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="VLM engine."
                      openOnHover
                      align="right"
                    >
                      {LABEL.VLM_ENGINE}
                    </DefinitionTooltip>
                  </div>
                  <Dropdown
                    id="vlm_engine"
                    titleText={LABEL.VLM_ENGINE}
                    hideLabel
                    label="Select engine"
                    items={[...VLM_ENGINES]}
                    selectedItem={vlmEngine}
                    itemToString={(item: VlmEngine | null) => (item ? VLM_ENGINE_LABELS[item] : '')}
                    onChange={({ selectedItem }: { selectedItem: VlmEngine | null }) => {
                      if (selectedItem) {
                        updateTextProviderConfigNested(
                          DOCLING_LIBRARY_CONFIG_KEY.VLM_PIPELINE,
                          VLM_PIPELINE_KEY.ENGINE,
                          selectedItem
                        );
                      }
                    }}
                  />
                </div>

                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="Engine-specific configuration (e.g. api_base, model_id, api_key)."
                      openOnHover
                      align="right"
                    >
                      {LABEL.VLM_ENGINE_OPTIONS}
                    </DefinitionTooltip>
                  </div>
                  <TextArea
                    id="vlm_engine_options"
                    labelText={LABEL.VLM_ENGINE_OPTIONS}
                    hideLabel
                    value={vlmEngineOptionsRaw ?? vlmEngineOptions}
                    rows={3}
                    invalid={touchedFields.vlmEngineOptions && !isValidJsonObject(vlmEngineOptionsRaw ?? vlmEngineOptions)}
                    invalidText="Engine options must be a valid JSON object."
                    onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => {
                      const raw = e.target.value;
                      setVlmEngineOptionsRaw(raw);
                      if (raw === '' || isValidJsonObject(raw)) {
                        updateTextProviderConfigNested(
                          DOCLING_LIBRARY_CONFIG_KEY.VLM_PIPELINE,
                          VLM_PIPELINE_KEY.ENGINE_OPTIONS,
                          raw === '' ? null : (JSON.parse(raw) as Record<string, unknown>)
                        );
                      }
                    }}
                    onBlur={() => {
                      markFieldAsTouched('vlmEngineOptions');
                      if (vlmEngineOptionsRaw !== null && isValidJsonObject(vlmEngineOptionsRaw)) {
                        setVlmEngineOptionsRaw(null);
                      }
                    }}
                  />
                </div>
              </div>
            )}

            {/* ASR pipeline */}
            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="Enable ASR (Automatic Speech Recognition) pipeline for audio/video extraction."
                  openOnHover
                  align="right"
                >
                  {LABEL.ASR_PIPELINE}
                </DefinitionTooltip>
              </div>
              <Toggle
                id="asr_pipeline_enabled"
                labelText={LABEL.ASR_PIPELINE}
                hideLabel
                labelA="Off"
                labelB="On"
                toggled={asrEnabled}
                onToggle={(checked: boolean) => {
                  if (checked) {
                    updateTextProviderConfig(DOCLING_LIBRARY_CONFIG_KEY.ASR_PIPELINE, {});
                  } else {
                    const { asr_pipeline: _removed, ...rest } = textProviderConfig;
                    update(ATTR.TEXT_EXTRACTION, { ...textExtraction, provider_config: rest });
                  }
                }}
              />
            </div>

            {asrEnabled && (
              <div className={common.subSection}>
                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="ASR model name (e.g., whisper_turbo, whisper_small, whisper_medium). Valid values: whisper_tiny, whisper_small, whisper_medium, whisper_base, whisper_large, whisper_turbo, and their _mlx/_native variants."
                      openOnHover
                      align="right"
                    >
                      {LABEL.ASR_MODEL_ID}
                    </DefinitionTooltip>
                  </div>
                  <TextInput
                    id="asr_model_id"
                    labelText={LABEL.ASR_MODEL_ID}
                    hideLabel
                    value={asrModelId}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                      updateTextProviderConfigNested(
                        DOCLING_LIBRARY_CONFIG_KEY.ASR_PIPELINE,
                        ASR_PIPELINE_KEY.MODEL_ID,
                        e.target.value || null
                      );
                    }}
                  />
                </div>
              </div>
            )}

            {/* Additional formats */}
            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="Additional output formats to generate beyond the mandatory markdown format."
                  openOnHover
                  align="right"
                >
                  {LABEL.ADDITIONAL_FORMATS}
                </DefinitionTooltip>
              </div>
              <div>
                {ADDITIONAL_FORMATS.map((fmt) => (
                  <Checkbox
                    key={fmt}
                    id={`additional_format_${fmt}`}
                    labelText={ADDITIONAL_FORMAT_LABELS[fmt]}
                    checked={additionalFormats.includes(fmt)}
                    onChange={(_e: unknown, { checked }: { checked: boolean }) => {
                      const next = checked
                        ? [...additionalFormats, fmt]
                        : additionalFormats.filter((f) => f !== fmt);
                      updateTextProviderConfig(DOCLING_LIBRARY_CONFIG_KEY.ADDITIONAL_FORMATS, next);
                    }}
                  />
                ))}
              </div>
            </div>

            {/* Standard pipeline (GPU acceleration) */}
            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="Enable GPU acceleration for PDF and image processing. Requires Maximum workers = 1 and Use processes = false. Cannot be combined with VLM Pipeline."
                  openOnHover
                  align="right"
                >
                  {LABEL.STANDARD_PIPELINE}
                </DefinitionTooltip>
              </div>
              <Toggle
                id="standard_pipeline_enabled"
                labelText={LABEL.STANDARD_PIPELINE}
                hideLabel
                labelA="Off"
                labelB="On"
                toggled={standardPipelineEnabled}
                onToggle={(checked: boolean) => {
                  if (checked) {
                    updateTextProviderConfig(DOCLING_LIBRARY_CONFIG_KEY.STANDARD_PIPELINE, { accelerator: {} });
                  } else {
                    const { standard_pipeline: _removed, ...rest } = textProviderConfig;
                    update(ATTR.TEXT_EXTRACTION, { ...textExtraction, provider_config: rest });
                  }
                }}
              />
            </div>

            {standardPipelineEnabled && (
              <div className={common.subSection}>
                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="GPU device for acceleration. Accepted values: 'mps' (Apple Silicon), 'cuda' (NVIDIA), 'cuda:<index>' (e.g. 'cuda:0'), 'xpu' (Intel). When omitted, the best available device is auto-detected via torch (CUDA -> MPS -> XPU)."
                      openOnHover
                      align="right"
                    >
                      {LABEL.ACCELERATOR_DEVICE}
                    </DefinitionTooltip>
                  </div>
                  <TextInput
                    id="accelerator_device"
                    labelText={LABEL.ACCELERATOR_DEVICE}
                    hideLabel
                    value={acceleratorDevice}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                      updateTextProviderConfigNested(
                        DOCLING_LIBRARY_CONFIG_KEY.STANDARD_PIPELINE,
                        'accelerator',
                        { ...acceleratorConfig, [ACCELERATOR_KEY.DEVICE]: e.target.value || null }
                      );
                    }}
                  />
                </div>

                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="Number of CPU-side pipeline threads. Must be a positive integer. Defaults to 4 when not set."
                      openOnHover
                      align="right"
                    >
                      {LABEL.ACCELERATOR_NUM_THREADS}
                    </DefinitionTooltip>
                  </div>
                  <NumberInput
                    id="accelerator_num_threads"
                    label={LABEL.ACCELERATOR_NUM_THREADS}
                    hideLabel
                    value={acceleratorNumThreads ?? 4}
                    min={1}
                    step={1}
                    onChange={(_e: unknown, { value }: { value: number | string }) => {
                      const n = Number(value);
                      updateTextProviderConfigNested(
                        DOCLING_LIBRARY_CONFIG_KEY.STANDARD_PIPELINE,
                        'accelerator',
                        { ...acceleratorConfig, [ACCELERATOR_KEY.NUM_THREADS]: Number.isFinite(n) && n > 0 ? n : null }
                      );
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── docling_serve provider_config ────────────────────────────── */}
        {textProvider === 'docling_serve' && (
          <div className={common.subSection}>

            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="Base URL of the Docling Serve API (e.g., http://0.0.0.0:5001)"
                  openOnHover
                  align="right"
                >
                  {LABEL.SERVE_BASE_URL}
                </DefinitionTooltip>
              </div>
              <TextInput
                id="serve_base_url"
                labelText={LABEL.SERVE_BASE_URL}
                hideLabel
                value={serveBaseUrl}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                  updateTextProviderConfig(DOCLING_SERVE_CONFIG_KEY.BASE_URL, e.target.value);
                }}
              />
            </div>

            <div className={styles.formField}>
              <VaultInput
                id="serve_api_key"
                labelText={LABEL.SERVE_API_KEY}
                labelComponent={
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="API key for authenticating with the Docling Serve endpoint (if required)."
                      openOnHover
                      align="right"
                    >
                      {LABEL.SERVE_API_KEY}
                    </DefinitionTooltip>
                  </div>
                }
                value={serveApiKey}
                onChange={(v: string) => {
                  updateTextProviderConfig(DOCLING_SERVE_CONFIG_KEY.API_KEY, v || null);
                }}
              />
            </div>

            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="Verify the server's SSL certificate."
                  openOnHover
                  align="right"
                >
                  {LABEL.SERVE_VERIFY_SSL}
                </DefinitionTooltip>
              </div>
              <Toggle
                id="serve_verify_ssl"
                labelText={LABEL.SERVE_VERIFY_SSL}
                hideLabel
                labelA="Off"
                labelB="On"
                toggled={serveVerifySsl}
                onToggle={(checked: boolean) => {
                  updateTextProviderConfig(DOCLING_SERVE_CONFIG_KEY.VERIFY_SSL, checked);
                }}
              />
            </div>

            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="Run OCR on document pages. When enabled, exposes OCR engine and language settings."
                  openOnHover
                  align="right"
                >
                  {LABEL.SERVE_DO_OCR}
                </DefinitionTooltip>
              </div>
              <Toggle
                id="serve_do_ocr"
                labelText={LABEL.SERVE_DO_OCR}
                hideLabel
                labelA="Off"
                labelB="On"
                toggled={serveDoOcr}
                onToggle={(checked: boolean) => {
                  updateTextProviderConfig(DOCLING_SERVE_CONFIG_KEY.DO_OCR, checked);
                }}
              />
            </div>

            {serveDoOcr && (
              <div className={common.subSection}>
                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="OCR engine to use. Leave empty to use the server default."
                      openOnHover
                      align="right"
                    >
                      {LABEL.SERVE_OCR_ENGINE}
                    </DefinitionTooltip>
                  </div>
                  <TextInput
                    id="serve_ocr_engine"
                    labelText={LABEL.SERVE_OCR_ENGINE}
                    hideLabel
                    value={serveOcrEngine}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                      updateTextProviderConfig(DOCLING_SERVE_CONFIG_KEY.OCR_ENGINE, e.target.value || null);
                    }}
                  />
                </div>

                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="List of language codes for OCR (e.g., en, fr). Leave unset to use the server default."
                      openOnHover
                      align="right"
                    >
                      {LABEL.SERVE_OCR_LANGUAGES}
                    </DefinitionTooltip>
                  </div>
                  <TagInput
                    id="serve_ocr_languages"
                    helperText="Press Enter or comma to add. Leave empty to use the server default."
                    tags={serveOcrLanguages}
                    onChange={(tags) => {
                      updateTextProviderConfig(DOCLING_SERVE_CONFIG_KEY.OCR_LANGUAGES, tags.length > 0 ? tags : null);
                    }}
                  />
                </div>
              </div>
            )}

            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="PDF parsing backend."
                  openOnHover
                  align="right"
                >
                  {LABEL.SERVE_PDF_BACKEND}
                </DefinitionTooltip>
              </div>
              <Dropdown
                id="serve_pdf_backend"
                titleText={LABEL.SERVE_PDF_BACKEND}
                hideLabel
                label="Select backend"
                items={[...PDF_BACKENDS]}
                selectedItem={servePdfBackend}
                itemToString={(item: PdfBackend | null) => (item ? PDF_BACKEND_LABELS[item] : '')}
                onChange={({ selectedItem }: { selectedItem: PdfBackend | null }) => {
                  if (selectedItem) {
                    updateTextProviderConfig(DOCLING_SERVE_CONFIG_KEY.PDF_BACKEND, selectedItem);
                  }
                }}
              />
            </div>

            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="How to export images found in the document."
                  openOnHover
                  align="right"
                >
                  {LABEL.SERVE_IMAGE_EXPORT_MODE}
                </DefinitionTooltip>
              </div>
              <Dropdown
                id="serve_image_export_mode"
                titleText={LABEL.SERVE_IMAGE_EXPORT_MODE}
                hideLabel
                label="Select mode"
                items={[...IMAGE_EXPORT_MODES]}
                selectedItem={serveImageExportMode}
                itemToString={(item: ImageExportMode | null) => (item ? IMAGE_EXPORT_MODE_LABELS[item] : '')}
                onChange={({ selectedItem }: { selectedItem: ImageExportMode | null }) => {
                  if (selectedItem) {
                    updateTextProviderConfig(DOCLING_SERVE_CONFIG_KEY.IMAGE_EXPORT_MODE, selectedItem);
                  }
                }}
              />
            </div>

            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="Table extraction strategy. Leave empty to use the server default."
                  openOnHover
                  align="right"
                >
                  {LABEL.SERVE_TABLE_MODE}
                </DefinitionTooltip>
              </div>
              <TextInput
                id="serve_table_mode"
                labelText={LABEL.SERVE_TABLE_MODE}
                hideLabel
                value={serveTableMode}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                  updateTextProviderConfig(DOCLING_SERVE_CONFIG_KEY.TABLE_MODE, e.target.value || null);
                }}
              />
            </div>

            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="Request timeout in seconds when calling Docling Serve."
                  openOnHover
                  align="right"
                >
                  {LABEL.SERVE_TIMEOUT}
                </DefinitionTooltip>
              </div>
              <NumberInput
                id="serve_timeout"
                label={LABEL.SERVE_TIMEOUT}
                hideLabel
                value={serveTimeout}
                min={1}
                step={10}
                onChange={(_e: unknown, { value }: { value: number | string }) => {
                  const n = Number(value);
                  updateTextProviderConfig(DOCLING_SERVE_CONFIG_KEY.TIMEOUT, Number.isFinite(n) && n > 0 ? n : undefined);
                }}
              />
            </div>

            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="Polling interval in seconds when waiting for async extraction results."
                  openOnHover
                  align="right"
                >
                  {LABEL.SERVE_POLL_INTERVAL}
                </DefinitionTooltip>
              </div>
              <NumberInput
                id="serve_poll_interval"
                label={LABEL.SERVE_POLL_INTERVAL}
                hideLabel
                value={servePollInterval}
                min={1}
                step={1}
                onChange={(_e: unknown, { value }: { value: number | string }) => {
                  const n = Number(value);
                  updateTextProviderConfig(DOCLING_SERVE_CONFIG_KEY.POLL_INTERVAL, Number.isFinite(n) && n > 0 ? n : undefined);
                }}
              />
            </div>

            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="Maximum number of retries on transient failures."
                  openOnHover
                  align="right"
                >
                  {LABEL.SERVE_MAX_RETRIES}
                </DefinitionTooltip>
              </div>
              <NumberInput
                id="serve_max_retries"
                label={LABEL.SERVE_MAX_RETRIES}
                hideLabel
                value={serveMaxRetries}
                min={0}
                step={1}
                onChange={(_e: unknown, { value }: { value: number | string }) => {
                  const n = Number(value);
                  updateTextProviderConfig(DOCLING_SERVE_CONFIG_KEY.MAX_RETRIES, Number.isFinite(n) && n >= 0 ? n : undefined);
                }}
              />
            </div>

          </div>
        )}

        {/* Document content column */}
        <div className={styles.formField}>
          <div className={common.labelWithTooltip}>
            <DefinitionTooltip
              definition="Column name to store the extracted document content."
              openOnHover
              align="right"
            >
              {LABEL.TEXT_DOC_COLUMN}
            </DefinitionTooltip>
          </div>
          <TextInput
            id="text_doc_column"
            labelText={LABEL.TEXT_DOC_COLUMN}
            hideLabel
            value={textDocColumn}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
              updateTextExtraction(EXTRACTION_KEY.DOC_COLUMN, e.target.value);
            }}
          />
        </div>

      </AccordionItem>

      {/* ═══════════════════════════════════════════════════════════════════
          ENTITY EXTRACTION
      ═══════════════════════════════════════════════════════════════════ */}
      <AccordionItem title="Entity Extraction">

        {/* Provider */}
        <div className={styles.formField}>
          <div className={common.labelWithTooltip}>
            <RequiredParamTooltip
              paramId={ATTR.ENTITY_EXTRACTION}
              nodeAttributes={nodeAttributes}
              definition="Choose the entity extraction strategy. Select 'None' to skip entity extraction."
            >
              {LABEL.ENTITY_PROVIDER}
            </RequiredParamTooltip>
          </div>
          <Dropdown
            id="entity_provider"
            titleText={LABEL.ENTITY_PROVIDER}
            hideLabel
            label="Select provider"
            items={[...ENTITY_PROVIDERS]}
            selectedItem={entityProvider}
            itemToString={(item: EntityProvider | null) => (item ? ENTITY_PROVIDER_LABELS[item] : '')}
            invalid={entityExtractionValidation.isInvalid}
            invalidText={entityExtractionValidation.errorMessage}
            onChange={({ selectedItem }: { selectedItem: EntityProvider | null }) => {
              if (selectedItem) { updateEntityExtraction('provider', selectedItem); }
            }}
          />
        </div>

        {/* Fields shown only when entity extraction is active */}
        {entityProviderActive && (
          <div className={common.subSection}>
            {/* Output column */}
            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="Column name to store the extracted entities."
                  openOnHover
                  align="right"
                >
                  {LABEL.ENTITY_OUTPUT_COLUMN}
                </DefinitionTooltip>
              </div>
              <TextInput
                id="entity_output_column"
                labelText={LABEL.ENTITY_OUTPUT_COLUMN}
                hideLabel
                value={entityOutputColumn}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                  updateEntityExtraction(EXTRACTION_KEY.OUTPUT_COLUMN, e.target.value);
                }}
              />
            </div>

            {/* ── litellm provider_config ──────────────────────────────── */}
            {entityProvider === 'litellm' && (
              <div className={common.subSection}>

                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="LLM model identifier (e.g., 'ollama/llama3.2', 'openai/gpt-4o', 'ibm/granite-3-8b-instruct')."
                      openOnHover
                      align="right"
                    >
                      {LABEL.ENTITY_MODEL_ID}
                    </DefinitionTooltip>
                  </div>
                  <TextInput
                    id="entity_litellm_model_id"
                    labelText={LABEL.ENTITY_MODEL_ID}
                    hideLabel
                    value={strVal(entityProviderConfig, LLM_ENTITY_CONFIG_KEY.MODEL_ID) || (metaDefault<string>(litellmAttrs, LLM_ENTITY_CONFIG_KEY.MODEL_ID) ?? '')}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                      updateEntityProviderConfig(LLM_ENTITY_CONFIG_KEY.MODEL_ID, e.target.value || null);
                    }}
                  />
                </div>

                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="Base URL for the LLM API endpoint (e.g., 'http://localhost:11434/v1')."
                      openOnHover
                      align="right"
                    >
                      {LABEL.ENTITY_API_BASE}
                    </DefinitionTooltip>
                  </div>
                  <TextInput
                    id="entity_litellm_api_base"
                    labelText={LABEL.ENTITY_API_BASE}
                    hideLabel
                    value={strVal(entityProviderConfig, LLM_ENTITY_CONFIG_KEY.API_BASE)}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                      updateEntityProviderConfig(LLM_ENTITY_CONFIG_KEY.API_BASE, e.target.value || null);
                    }}
                  />
                </div>

                <div className={styles.formField}>
                  <VaultInput
                    id="entity_litellm_api_key"
                    labelText={LABEL.ENTITY_API_KEY}
                    labelComponent={
                      <div className={common.labelWithTooltip}>
                        <DefinitionTooltip
                          definition="API key for authenticating with the LLM provider."
                          openOnHover
                          align="right"
                        >
                          {LABEL.ENTITY_API_KEY}
                        </DefinitionTooltip>
                      </div>
                    }
                    value={strVal(entityProviderConfig, LLM_ENTITY_CONFIG_KEY.API_KEY)} // pragma: allowlist secret
                    onChange={(v: string) => {
                      updateEntityProviderConfig(LLM_ENTITY_CONFIG_KEY.API_KEY, v || null);
                    }}
                  />
                </div>

                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="Sampling temperature (0.0-1.0). Lower values produce more deterministic output."
                      openOnHover
                      align="right"
                    >
                      {LABEL.ENTITY_TEMPERATURE}
                    </DefinitionTooltip>
                  </div>
                  <NumberInput
                    id="entity_litellm_temperature"
                    label={LABEL.ENTITY_TEMPERATURE}
                    hideLabel
                    value={
                      numVal(
                        entityProviderConfig,
                        LLM_ENTITY_CONFIG_KEY.TEMPERATURE,
                        metaDefault<number>(litellmAttrs, LLM_ENTITY_CONFIG_KEY.TEMPERATURE) ?? 0
                      )
                    }
                    min={0}
                    max={1}
                    step={0.1}
                    onChange={(_e: unknown, { value }: { value: number | string }) => {
                      const n = Number(value);
                      updateEntityProviderConfig(LLM_ENTITY_CONFIG_KEY.TEMPERATURE, Number.isFinite(n) ? n : 0);
                    }}
                  />
                </div>

                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="Maximum number of tokens to generate in the LLM response."
                      openOnHover
                      align="right"
                    >
                      {LABEL.ENTITY_MAX_TOKENS}
                    </DefinitionTooltip>
                  </div>
                  <NumberInput
                    id="entity_litellm_max_tokens"
                    label={LABEL.ENTITY_MAX_TOKENS}
                    hideLabel
                    value={numVal(entityProviderConfig, LLM_ENTITY_CONFIG_KEY.MAX_TOKENS, metaDefault<number>(litellmAttrs, LLM_ENTITY_CONFIG_KEY.MAX_TOKENS) ?? '')}
                    min={1}
                    step={100}
                    onChange={(_e: unknown, { value }: { value: number | string }) => {
                      const n = Number(value);
                      updateEntityProviderConfig(LLM_ENTITY_CONFIG_KEY.MAX_TOKENS, Number.isFinite(n) && n > 0 ? n : undefined);
                    }}
                  />
                </div>

              </div>
            )}

            {/* ── watsonx provider_config ──────────────────────────────── */}
            {entityProvider === 'watsonx' && (
              <div className={common.subSection}>

                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="LLM model identifier (e.g., 'ibm/granite-3-8b-instruct')."
                      openOnHover
                      align="right"
                    >
                      {LABEL.ENTITY_MODEL_ID}
                    </DefinitionTooltip>
                  </div>
                  <TextInput
                    id="entity_watsonx_model_id"
                    labelText={LABEL.ENTITY_MODEL_ID}
                    hideLabel
                    value={strVal(entityProviderConfig, LLM_ENTITY_CONFIG_KEY.MODEL_ID) || (metaDefault<string>(watsonxAttrs, LLM_ENTITY_CONFIG_KEY.MODEL_ID) ?? '')}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                      updateEntityProviderConfig(LLM_ENTITY_CONFIG_KEY.MODEL_ID, e.target.value || null);
                    }}
                  />
                </div>

                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="Watsonx.ai API endpoint URL (e.g., 'https://us-south.ml.cloud.ibm.com')."
                      openOnHover
                      align="right"
                    >
                      {LABEL.ENTITY_WATSONX_URL}
                    </DefinitionTooltip>
                  </div>
                  <TextInput
                    id="entity_watsonx_url"
                    labelText={LABEL.ENTITY_WATSONX_URL}
                    hideLabel
                    value={strVal(entityProviderConfig, WATSONX_ENTITY_CONFIG_KEY.URL)}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                      updateEntityProviderConfig(WATSONX_ENTITY_CONFIG_KEY.URL, e.target.value || null);
                    }}
                  />
                </div>

                <div className={styles.formField}>
                  <VaultInput
                    id="entity_watsonx_api_key"
                    labelText={LABEL.ENTITY_API_KEY}
                    labelComponent={
                      <div className={common.labelWithTooltip}>
                        <DefinitionTooltip
                          definition="API key for authenticating with IBM watsonx."
                          openOnHover
                          align="right"
                        >
                          {LABEL.ENTITY_API_KEY}
                        </DefinitionTooltip>
                      </div>
                    }
                    value={strVal(entityProviderConfig, LLM_ENTITY_CONFIG_KEY.API_KEY)} // pragma: allowlist secret
                    onChange={(v: string) => {
                      updateEntityProviderConfig(LLM_ENTITY_CONFIG_KEY.API_KEY, v || null);
                    }}
                  />
                </div>

                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="Container type for the watsonx project or space."
                      openOnHover
                      align="right"
                    >
                      {LABEL.ENTITY_CONTAINER_KIND}
                    </DefinitionTooltip>
                  </div>
                  <Dropdown
                    id="entity_watsonx_container_kind"
                    titleText={LABEL.ENTITY_CONTAINER_KIND}
                    hideLabel
                    label="Select container type"
                    items={[...WATSONX_CONTAINER_KINDS]}
                    selectedItem={(entityProviderConfig[WATSONX_ENTITY_CONFIG_KEY.CONTAINER_KIND] as WatsonxContainerKind | undefined) ?? metaDefault<WatsonxContainerKind>(watsonxAttrs, WATSONX_ENTITY_CONFIG_KEY.CONTAINER_KIND) ?? 'project'}
                    itemToString={(item: WatsonxContainerKind | null) => item ?? ''}
                    onChange={({ selectedItem }: { selectedItem: WatsonxContainerKind | null }) => {
                      if (selectedItem) { updateEntityProviderConfig(WATSONX_ENTITY_CONFIG_KEY.CONTAINER_KIND, selectedItem); }
                    }}
                  />
                </div>

                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="Container ID for the watsonx project or space."
                      openOnHover
                      align="right"
                    >
                      {LABEL.ENTITY_CONTAINER_ID}
                    </DefinitionTooltip>
                  </div>
                  <TextInput
                    id="entity_watsonx_container_id"
                    labelText={LABEL.ENTITY_CONTAINER_ID}
                    hideLabel
                    value={strVal(entityProviderConfig, WATSONX_ENTITY_CONFIG_KEY.CONTAINER_ID)}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                      updateEntityProviderConfig(WATSONX_ENTITY_CONFIG_KEY.CONTAINER_ID, e.target.value || null);
                    }}
                  />
                </div>

                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="Watsonx project ID."
                      openOnHover
                      align="right"
                    >
                      {LABEL.ENTITY_PROJECT_ID}
                    </DefinitionTooltip>
                  </div>
                  <TextInput
                    id="entity_watsonx_project_id"
                    labelText={LABEL.ENTITY_PROJECT_ID}
                    hideLabel
                    value={strVal(entityProviderConfig, WATSONX_ENTITY_CONFIG_KEY.PROJECT_ID)}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                      updateEntityProviderConfig(WATSONX_ENTITY_CONFIG_KEY.PROJECT_ID, e.target.value || null);
                    }}
                  />
                </div>

                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="Sampling temperature (0.0-1.0). Lower values produce more deterministic output."
                      openOnHover
                      align="right"
                    >
                      {LABEL.ENTITY_TEMPERATURE}
                    </DefinitionTooltip>
                  </div>
                  <NumberInput
                    id="entity_watsonx_temperature"
                    label={LABEL.ENTITY_TEMPERATURE}
                    hideLabel
                    value={
                      numVal(
                        entityProviderConfig,
                        LLM_ENTITY_CONFIG_KEY.TEMPERATURE,
                        metaDefault<number>(watsonxAttrs, LLM_ENTITY_CONFIG_KEY.TEMPERATURE) ?? 0
                      )
                    }
                    min={0}
                    max={1}
                    step={0.1}
                    onChange={(_e: unknown, { value }: { value: number | string }) => {
                      const n = Number(value);
                      updateEntityProviderConfig(LLM_ENTITY_CONFIG_KEY.TEMPERATURE, Number.isFinite(n) ? n : 0);
                    }}
                  />
                </div>

                <div className={styles.formField}>
                  <div className={common.labelWithTooltip}>
                    <DefinitionTooltip
                      definition="Maximum number of tokens to generate in the LLM response."
                      openOnHover
                      align="right"
                    >
                      {LABEL.ENTITY_MAX_TOKENS}
                    </DefinitionTooltip>
                  </div>
                  <NumberInput
                    id="entity_watsonx_max_tokens"
                    label={LABEL.ENTITY_MAX_TOKENS}
                    hideLabel
                    value={numVal(entityProviderConfig, LLM_ENTITY_CONFIG_KEY.MAX_TOKENS, metaDefault<number>(watsonxAttrs, LLM_ENTITY_CONFIG_KEY.MAX_TOKENS) ?? '')}
                    min={1}
                    step={100}
                    onChange={(_e: unknown, { value }: { value: number | string }) => {
                      const n = Number(value);
                      updateEntityProviderConfig(LLM_ENTITY_CONFIG_KEY.MAX_TOKENS, Number.isFinite(n) && n > 0 ? n : undefined);
                    }}
                  />
                </div>

              </div>
            )}

            {/* ── docling entity provider_config ───────────────────────── */}
            {entityProvider === 'docling' && (
                <div className={common.subSection}>

                  <div className={styles.formField}>
                    <div className={common.labelWithTooltip}>
                      <DefinitionTooltip
                        definition="Custom VLM model configuration for Docling entity extraction. Requires 'model_type': 'inline' and an 'inline_model' with a HuggingFace 'repo_id'."
                        openOnHover
                        align="right"
                      >
                        {LABEL.ENTITY_VLM_PIPELINE}
                      </DefinitionTooltip>
                    </div>
                    <TextArea
                      id="entity_docling_vlm_pipeline"
                      labelText={LABEL.ENTITY_VLM_PIPELINE}
                      hideLabel
                      value={entityDoclingVlmPipelineRaw ?? (!isNil(entityProviderConfig[DOCLING_ENTITY_CONFIG_KEY.VLM_PIPELINE]) ? JSON.stringify(entityProviderConfig[DOCLING_ENTITY_CONFIG_KEY.VLM_PIPELINE], null, 2) : '')}
                      rows={4}
                      invalid={touchedFields.entityDoclingVlmPipeline && !isValidJsonObject(entityDoclingVlmPipelineRaw ?? '')}
                      invalidText="VLM pipeline configuration must be a valid JSON object."
                      onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => {
                        const raw = e.target.value;
                        setEntityDoclingVlmPipelineRaw(raw);
                        if (raw === '' || isValidJsonObject(raw)) {
                          updateEntityProviderConfig(DOCLING_ENTITY_CONFIG_KEY.VLM_PIPELINE, raw === '' ? null : (JSON.parse(raw) as Record<string, unknown>));
                        }
                      }}
                      onBlur={() => {
                        markFieldAsTouched('entityDoclingVlmPipeline');
                        if (entityDoclingVlmPipelineRaw !== null && isValidJsonObject(entityDoclingVlmPipelineRaw)) {
                          setEntityDoclingVlmPipelineRaw(null);
                        }
                      }}
                    />
                  </div>

                </div>
            )}

            {/* Max document characters */}
            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="Maximum characters of document content sent for entity extraction per document."
                  openOnHover
                  align="right"
                >
                  {LABEL.ENTITY_MAX_DOC_CHARS}
                </DefinitionTooltip>
              </div>
              <NumberInput
                id="entity_max_doc_chars"
                label={LABEL.ENTITY_MAX_DOC_CHARS}
                hideLabel
                value={entityMaxDocChars}
                min={1}
                step={1000}
                onChange={(_e: unknown, { value }: { value: number | string }) => {
                  const inputNumber = Number(value);
                  updateEntityExtraction(EXTRACTION_KEY.ENTITY_MAX_DOC_CHARS,
                    Number.isFinite(inputNumber) && inputNumber > 0 ? inputNumber : undefined);
                }}
              />
            </div>

            {/* Custom schema */}
            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="JSON object defining a schema dictionary for structured entity extraction."
                  openOnHover
                  align="right"
                >
                  {LABEL.ENTITY_CUSTOM_SCHEMA}
                </DefinitionTooltip>
              </div>
              <TextArea
                id="entity_custom_schema"
                labelText={LABEL.ENTITY_CUSTOM_SCHEMA}
                hideLabel
                value={customSchemaRaw ?? entityCustomSchemaPersisted}
                rows={3}
                invalid={touchedFields.entityCustomSchema && !isValidJsonObject(customSchemaRaw ?? entityCustomSchemaPersisted)}
                invalidText="Custom schema must be a valid JSON object."
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => {
                  const raw = e.target.value;
                  setCustomSchemaRaw(raw);
                  if (raw === '' || isValidJsonObject(raw)) {
                    updateEntityExtraction(EXTRACTION_KEY.CUSTOM_SCHEMA, raw === '' ? null : (JSON.parse(raw) as Record<string, unknown>));
                  }
                }}
                onBlur={() => {
                  markFieldAsTouched('entityCustomSchema');
                  if (customSchemaRaw !== null && isValidJsonObject(customSchemaRaw)) {
                    setCustomSchemaRaw(null);
                  }
                }}
              />
            </div>

            {/* Expand extracted data */}
            <div className={styles.formField}>
              <div className={common.labelWithTooltip}>
                <DefinitionTooltip
                  definition="Expand extracted entity data into individual columns in the output table."
                  openOnHover
                  align="right"
                >
                  {LABEL.ENTITY_EXPAND_DATA}
                </DefinitionTooltip>
              </div>
              <Toggle
                id="entity_expand_data"
                labelText={LABEL.ENTITY_EXPAND_DATA}
                hideLabel
                labelA="Off"
                labelB="On"
                toggled={entityExpandData}
                onToggle={(checked: boolean) => { updateEntityExtraction(EXTRACTION_KEY.EXPAND_EXTRACTED_DATA, checked); }}
              />
            </div>
          </div>
        )}
      </AccordionItem>

      {/* ═══════════════════════════════════════════════════════════════════
          ADVANCED
      ═══════════════════════════════════════════════════════════════════ */}
      <AccordionItem title="Advanced">
        <div className={styles.formField}>
          <div className={common.labelWithTooltip}>
            <RequiredParamTooltip
              paramId={ATTR.MAX_WORKERS}
              nodeAttributes={nodeAttributes}
              definition="Maximum number of parallel workers for extraction (auto-detects based on CPU count if not specified)."
            >
              {LABEL.MAX_WORKERS}
            </RequiredParamTooltip>
          </div>
          <NumberInput
            id="max_workers"
            label={LABEL.MAX_WORKERS}
            hideLabel
            value={maxWorkers}
            min={0}
            max={64}
            step={1}
            invalid={maxWorkersValidation.isInvalid}
            invalidText={maxWorkersValidation.errorMessage}
            onChange={(_e: unknown, { value }: { value: number | string }) => {
              const n = Number(value);
              update(ATTR.MAX_WORKERS, Number.isFinite(n) && n > 0 ? n : undefined);
            }}
          />
        </div>

        <div className={styles.formField}>
          <div className={common.labelWithTooltip}>
            <RequiredParamTooltip
              paramId={ATTR.USE_PROCESSES}
              nodeAttributes={nodeAttributes}
              definition="Use separate processes instead of threads for CPU-intensive tasks."
            >
              {LABEL.USE_PROCESSES}
            </RequiredParamTooltip>
          </div>
          <Toggle
            id="use_processes"
            labelText={LABEL.USE_PROCESSES}
            hideLabel
            labelA="Off"
            labelB="On"
            toggled={useProcesses}
            onToggle={(checked: boolean) => { update(ATTR.USE_PROCESSES, checked); }}
          />
        </div>
      </AccordionItem>
      </Accordion>
    </div>
  );
}
