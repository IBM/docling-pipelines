/**
 * Helpers for constructing flow payloads.
 */

import type { FlowDefinition } from '@/types/flow';

/**
 * Generates a RFC 4122 v4 UUID using the Web Crypto API.
 * Falls back to a timestamp-based ID in environments where crypto is unavailable.
 */
function generateUUID(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // Fallback: timestamp + random hex
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

/**
 * Builds the default `definition` block for a newly created flow.
 *
 * The structure mirrors the canonical template payload used by the BFF/backend
 * (doc_type "pipeline", version "3.0", one empty pipeline with ds_flow app_data).
 *
 * A fresh UUID is generated for the pipeline `id` on every call — required
 * because each flow must own a distinct pipeline object in the backend store.
 *
 * @param name        Human-readable flow name — stored in ds_flow.name.
 * @param description Free-text description — stored in ds_flow.description.
 * @param nodes       Optional pre-populated node array. When omitted the pipeline
 *                    starts empty (`[]`). Pass a static node list (e.g. from a
 *                    sample flow JSON) to seed the canvas with pre-built operators.
 */
export function buildFlowDefinition(
  name: string,
  description: string,
  nodes: unknown[] = []
): FlowDefinition {
  const pipelineId = generateUUID();
  return {
    doc_type: 'pipeline',
    version: '3.0',
    primary_pipeline: pipelineId,
    pipelines: [
      {
        id: pipelineId,
        nodes,
        app_data: {
          ds_flow: {
            name,
            description,
            schedule: {},
            global_config: {},
          },
          ui_data: {
            comments: [],
          },
        },
        runtime_ref: '',
      },
    ],
    schemas: [],
  };
}
