import type { OperatorMetadata, OperatorsResponse } from '@/types';

const baseOperator: OperatorMetadata = {
  label: 'Test Operator',
  category: 'Quality',
  description: 'A test operator',
  features: {},
  required_features: [],
  attributes: {},
};

export const ingestOperatorFixture: OperatorMetadata = {
  ...baseOperator,
  label: 'Ingest Source',
  category: 'Ingest',
  description: 'Ingests documents from a source',
  attributes: {
    provider: {
      type: 'string',
      description: 'The ingest provider',
      required: true,
      default: null,
      available_for_filter: null,
      available_for_vector_db: null,
    },
    paths: {
      type: 'array',
      description: 'Source paths to ingest',
      required: false,
      default: [],
      available_for_filter: null,
      available_for_vector_db: null,
    },
  },
};

export const chunkerOperatorFixture: OperatorMetadata = {
  ...baseOperator,
  label: 'Chunker',
  category: 'Functional',
  description: 'Splits documents into chunks',
  attributes: {
    chunk_size: {
      type: 'number',
      description: 'Size of each chunk',
      required: false,
      default: 512,
      available_for_filter: null,
      available_for_vector_db: null,
    },
    overlap: {
      type: 'number',
      description: 'Overlap between chunks',
      required: false,
      default: 50,
      available_for_filter: null,
      available_for_vector_db: null,
    },
  },
};

export const noopOperatorFixture: OperatorMetadata = {
  ...baseOperator,
  label: 'NOOP',
  category: 'Functional',
  description: 'No-operation passthrough',
  attributes: {},
};

export const operatorsFixture: OperatorsResponse = {
  ingest_source: ingestOperatorFixture,
  chunker: chunkerOperatorFixture,
  noop: noopOperatorFixture,
};
