/**
 * Flow Run Properties Constants
 *
 * Constants used in the Flow Run Properties Tearsheet component.
 */

import type { IntermediateDataStorageType } from '@/types';

/**
 * Flow property attribute names for flow_def global config.
 * These constants ensure consistency between frontend and backend property names.
 */
export const FLOW_PROPERTY_KEYS = {
  ENABLE_INCREMENTAL_PROCESSING: 'enableIncrementalProcessing',
  RETAIN_RECORDS_FOR_DELETED_DOCUMENTS: 'retainRecordsForDeletedDocuments',
  VALIDATE_FLOW: 'validateFlow',
  INTERMEDIATE_DATA_STORAGE: 'intermediateDataStorage',
} as const;

export interface StorageOption {
  id: IntermediateDataStorageType;
  text: string;
}

export const STORAGE_OPTIONS: StorageOption[] = [
  { id: 'container', text: 'Container file system' },
  { id: 'memory', text: 'Memory' },
];

export const FLOW_RUN_PROPERTIES_LABELS = {
  title: 'Flow run properties',
  description: 'Configure the properties for running the flow.',
  primaryAction: 'Save',
  secondaryAction: 'Cancel',
  toggles: {
    incrementalProcessing: 'Enable incremental processing',
    retainRecords: 'Retain records for deleted documents',
    validateFlow: 'Validate flow',
  },
  dropdown: {
    intermediateStorage: 'Intermediate data storage',
    label: 'Select storage type',
  },
  toggleLabels: {
    off: 'Off',
    on: 'On',
  },
};
