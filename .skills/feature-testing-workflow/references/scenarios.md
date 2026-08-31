# Feature Validation Scenarios

Start from one maintained scenario, reduce it to the feature boundary, and write acceptance checks before execution. These examples are runtime references, not prerequisites for pytest coverage.

## Local operator scenario

Use for ingest, extraction, or a deterministic operator without external services.

- Starting flow: `sample_flows/quickstart/basic_ingest_extract.json`
- Small fixtures: `tests/fixtures/customer_support_docs/` or `tests/fixtures/invoices/invoice.md`
- Persist outputs with `data_storage_type: "local"`.
- Remove extraction when the feature consumes ingest metadata directly.

Example acceptance checks:

- job status is `Completed` or an explicitly accepted warning status;
- ingest and target-node document counts agree;
- target output contains the new column;
- the column has the expected value for a known input;
- failed document count is zero.

## Quality or enrichment operator

- PII/HAP: `sample_flows/operators/pii_hap_detection.json`
- Classification: `sample_flows/operators/classification_ollama.json`
- Entity curation: `sample_flows/operators/entity_curation_ollama.json`
- Multi-stage local behavior: `sample_flows/advanced/multi_stage_enrichment.json`

Use a fixture with deliberately known content. Assert exact annotations, labels, or scores where deterministic; for probabilistic LLM output, assert the documented structural and threshold invariants rather than a brittle full string.

## Branch and merge behavior

- Branching baseline: `sample_flows/advanced/branching_quality_routing.json`
- Multi-branch merge: `sample_flows/advanced/quality_branching_merge_pipeline.json`
- Dual embeddings: `sample_flows/advanced/branching_dual_embeddings.json`

Verify each input identifier lands in exactly the intended branch, no branch receives an unexpected identifier, and the merged identifier multiset matches the contract.

## Micro-batching parity

- Hybrid chunking: `sample_flows/advanced/hybrid_chunking.json`
- OpenSearch micro-batching: `sample_flows/vectordb/opensearch_integration.json`
- Unit-level orchestration references: `tests/unit/core/orchestrator/test_batch_manager.py` and `test_terminal_path_batch_propagation.py`

Run once with `enable_micro_batching: false` and once with it true. Compare row counts, schemas, document identifiers, feature values, and failed/skipped accounting. Timing differences are not parity failures.

## Ingest provider scenario

- Filesystem: `sample_flows/quickstart/basic_ingest_extract.json`
- S3: `sample_flows/use_cases/s3_to_opensearch.json`
- Provider implementation map: `.skills/docpipe-ingest-source-adapter/references/reference-implementations.md`

Verify filtering and metadata at the ingest node. Add extraction only to prove binary retrieval. For remote providers, use a dedicated folder or prefix containing a small known corpus.

## Vector database scenario

- OpenSearch: `sample_flows/vectordb/opensearch_integration.json`
- Milvus: `sample_flows/vectordb/milvus_integration.json`
- Full local-to-vector flow: `sample_flows/quickstart/complete_pipeline_ollama.json`

Use a unique temporary index or collection. Verify stored document count, identifier, vector dimension, mapped metadata, and one retrieval/query behavior when it is part of the feature. Do not mark the scenario passed from the pipeline exit code alone.

## Storage-output scenario

- Processed content to S3: `sample_flows/storage_output/processed_content_s3.json`
- Refetch original to filesystem: `sample_flows/storage_output/refetch_original_filesystem.json`
- Google Drive, SharePoint, and Box examples: other files in `sample_flows/storage_output/`

Verify destination paths or keys, bytes or serialized content, overwrite mode, per-document result metadata, and the absence of writes outside the isolated test prefix.

## API scenario

- Route implementations: `src/docpipe/api/routes/`
- DTOs and mappers: `src/docpipe/api/dto/`
- Existing request shapes: `tests/integration/api/`
- OpenAPI contract: `tests/unit/api/test_openapi.py`

Use the existing integration tests only to discover request payloads and dependency requirements. Send real HTTP requests to the running local API for feature validation, then verify both response DTOs and persisted externally visible state.

## Baseline verifier examples

Check one node and a produced column:

```bash
python .skills/feature-testing-workflow/scripts/verify_flow_run.py \
  --run-dir data/<job_id>/<job_run_id> \
  --expect-node enrich \
  --expect-column enrich:quality_score \
  --min-rows enrich:1
```

Check an exact job input count:

```bash
python .skills/feature-testing-workflow/scripts/verify_flow_run.py \
  --run-dir data/<job_id>/<job_run_id> \
  --expected-total 3
```

The baseline verifier proves only generic artifact invariants. Add a temporary feature-specific verifier or direct service query for exact values and side effects.
