/**
 * Flow Run Properties Tearsheet Component
 *
 * A tearsheet component for configuring flow execution properties including
 * incremental processing, validation, node output preview, and storage options.
 * Uses the SharedTearsheet component for consistent modal behavior.
 * Connected to Redux store for state persistence.
 */
import React, { useState, useEffect } from 'react';
import { Toggle, Dropdown } from '@carbon/react';
import { useAppDispatch, useAppSelector } from '@/hooks';
import { setFlowRunProperties } from '@/slices/flowSlice';
import type { FlowRunProperties } from '@/types';
import { SharedTearsheet } from '../SharedTearsheet';
import {
  STORAGE_OPTIONS,
  FLOW_RUN_PROPERTIES_LABELS,
  FLOW_PROPERTY_KEYS,
} from '@/constants/flowRunProperties';
import styles from './FlowRunPropertiesTearsheet.module.scss';

/**
 * Props for the FlowRunPropertiesTearsheet component.
 */
interface FlowRunPropertiesTearsheetProps {
  open: boolean;
  onClose: () => void;
  onSave?: (properties: FlowRunProperties) => void;
}

/**
 * FlowRunPropertiesTearsheet component for configuring flow execution properties.
 *
 * Provides a user interface for configuring:
 * - Incremental processing with nested option for retaining deleted document records
 * - Flow validation toggle
 * - Node output preview toggle
 * - Intermediate data storage selection (Container file system or Memory)
 *
 * @param props - Component props
 * @returns React component displaying the flow run properties configuration tearsheet
 */
export function FlowRunPropertiesTearsheet({
  open,
  onClose,
  onSave,
}: FlowRunPropertiesTearsheetProps): React.JSX.Element {
  const dispatch = useAppDispatch();
  const reduxProperties = useAppSelector((state) => state.flow.flowRunProperties);
  
  // Local state for editing (syncs to Redux on save)
  const [localProperties, setLocalProperties] = useState<FlowRunProperties>(reduxProperties);

  // Sync local state with Redux when tearsheet opens
  useEffect(() => {
    if (open) {
      setLocalProperties(reduxProperties);
    }
  }, [open, reduxProperties]);

  const handleSave = () => {
    // Save to Redux store
    dispatch(setFlowRunProperties(localProperties));
    
    // Call optional callback
    if (onSave) {
      onSave(localProperties);
    }
    
    onClose();
  };

  const handleCancel = () => {
    // Discard local changes
    setLocalProperties(reduxProperties);
    onClose();
  };

  const updateLocalProperty = <K extends keyof FlowRunProperties>(
    key: K,
    value: FlowRunProperties[K]
  ) => {
    setLocalProperties((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <SharedTearsheet
      open={open}
      onClose={onClose}
      title={FLOW_RUN_PROPERTIES_LABELS.title}
      size="md"
      primaryActionLabel={FLOW_RUN_PROPERTIES_LABELS.primaryAction}
      secondaryActionLabel={FLOW_RUN_PROPERTIES_LABELS.secondaryAction}
      onPrimaryAction={handleSave}
      onSecondaryAction={handleCancel}
    >
      <div className={styles.propertiesContainer}>
        <p className={styles.description}>
          {FLOW_RUN_PROPERTIES_LABELS.description}
        </p>

        <div className={styles.propertySection}>
          <div className={styles.toggleWrapper}>
            <Toggle
              id="incremental-processing"
              labelText={FLOW_RUN_PROPERTIES_LABELS.toggles.incrementalProcessing}
              labelA={FLOW_RUN_PROPERTIES_LABELS.toggleLabels.off}
              labelB={FLOW_RUN_PROPERTIES_LABELS.toggleLabels.on}
              toggled={localProperties.enableIncrementalProcessing}
              onToggle={(checked) => {
                updateLocalProperty(FLOW_PROPERTY_KEYS.ENABLE_INCREMENTAL_PROCESSING as keyof FlowRunProperties, checked);
              }}
            />
          </div>

          {localProperties.enableIncrementalProcessing && (
            <div className={styles.nestedProperty}>
              <Toggle
                id="retain-records"
                labelText={FLOW_RUN_PROPERTIES_LABELS.toggles.retainRecords}
                labelA={FLOW_RUN_PROPERTIES_LABELS.toggleLabels.off}
                labelB={FLOW_RUN_PROPERTIES_LABELS.toggleLabels.on}
                toggled={localProperties.retainRecordsForDeletedDocuments}
                onToggle={(checked) => {
                  updateLocalProperty(FLOW_PROPERTY_KEYS.RETAIN_RECORDS_FOR_DELETED_DOCUMENTS as keyof FlowRunProperties, checked);
                }}
              />
            </div>
          )}
        </div>

        <div className={styles.propertySection}>
          <div className={styles.toggleWrapper}>
            <Toggle
              id="validate-flow"
              labelText={FLOW_RUN_PROPERTIES_LABELS.toggles.validateFlow}
              labelA={FLOW_RUN_PROPERTIES_LABELS.toggleLabels.off}
              labelB={FLOW_RUN_PROPERTIES_LABELS.toggleLabels.on}
              toggled={localProperties.validateFlow}
              onToggle={(checked) => {
                updateLocalProperty(FLOW_PROPERTY_KEYS.VALIDATE_FLOW as keyof FlowRunProperties, checked);
              }}
            />
          </div>
        </div>

        <div className={styles.propertySection}>
          <div className={styles.toggleWrapper}>
            <Toggle
              id="node-output-preview"
              labelText={FLOW_RUN_PROPERTIES_LABELS.toggles.nodeOutputPreview}
              labelA={FLOW_RUN_PROPERTIES_LABELS.toggleLabels.off}
              labelB={FLOW_RUN_PROPERTIES_LABELS.toggleLabels.on}
              toggled={localProperties.enableNodeOutputPreview}
              onToggle={(checked) => {
                updateLocalProperty(FLOW_PROPERTY_KEYS.ENABLE_NODE_OUTPUT_PREVIEW as keyof FlowRunProperties, checked);
              }}
            />
          </div>
        </div>

        <div className={styles.dropdownSection}>
          <Dropdown
            id="intermediate-storage"
            titleText={FLOW_RUN_PROPERTIES_LABELS.dropdown.intermediateStorage}
            label={FLOW_RUN_PROPERTIES_LABELS.dropdown.label}
            items={STORAGE_OPTIONS}
            selectedItem={STORAGE_OPTIONS.find(
              (opt) => opt.id === localProperties.intermediateDataStorage
            )}
            itemToString={(item) => (item ? item.text : '')}
            onChange={({ selectedItem }) => {
              if (selectedItem) {
                updateLocalProperty(
                  FLOW_PROPERTY_KEYS.INTERMEDIATE_DATA_STORAGE as keyof FlowRunProperties,
                  selectedItem.id
                );
              }
            }}
          />
        </div>
      </div>
    </SharedTearsheet>
  );
}
