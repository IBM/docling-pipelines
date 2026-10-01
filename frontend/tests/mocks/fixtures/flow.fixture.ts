import type { Flow, FlowRow, PaginatedFlowResponse, FlowDefinition } from '@/types';

export const flowDefinitionFixture: FlowDefinition = {
  doc_type: 'pipeline',
  version: '3.0',
  json_schema: 'http://api.dataplatform.ibm.com/schemas/common-pipeline/pipeline-flow/pipeline-flow-v3-schema.json',
  id: 'test-pipeline-id',
  primary_pipeline: 'test-pipeline-id',
  pipelines: [
    {
      id: 'test-pipeline-id',
      nodes: [],
      app_data: {
        ui_data: { comments: [] },
        ds_flow: {
          name: 'Test Flow',
          description: 'A test flow',
        },
      },
    },
  ],
  schemas: [],
};

export const flowFixture: Flow = {
  flow_id: 'flow-1',
  name: 'Test Flow',
  description: 'A flow used in tests',
  tags: ['test', 'unit'],
  container_id: 'project-1',
  container_kind: 'project',
  definition: flowDefinitionFixture,
  flow_version: '1',
  created_on: '2024-01-15T10:00:00Z',
  created_by: 'test-user',
  modified_on: '2024-01-16T10:00:00Z',
  modified_by: 'test-user',
  href: '/api/v1/flows/flow-1',
  job_id: null,
  is_hidden: false,
  job_run_summary: {
    total_runs: 3,
    last_run_id: 'run-3',
    last_run_status: 'Completed',
    last_run_start_time: 1705329000,
    status_counts: { Completed: 2, Failed: 1 },
  },
};

export const flowRowFixture: FlowRow = {
  flow_id: 'flow-1',
  project_id: 'project-1',
  name: 'Test Flow',
  description: 'A flow used in tests',
  tags: ['test', 'unit'],
  run_count: 3,
  run_status: { errors: 1, warnings: 0, running: 0 },
  created_on: 'Jan 15, 2024',
  modified_on: 'Jan 16, 2024',
};

export const paginatedFlowResponseFixture: PaginatedFlowResponse = {
  flows: [flowFixture],
  total_count: 1,
  offset: 0,
  limit: 20,
  first: '/api/v1/flows?offset=0',
  next: null,
  prev: null,
};
