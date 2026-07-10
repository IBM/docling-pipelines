# OpenSearch Documentation

> For setup and first-run instructions, start with [`USER_GUIDE_PIPELINE_SETUP.md`](../../../USER_GUIDE_PIPELINE_SETUP.md). It covers prerequisites, dependency installation, OpenSearch startup, pipeline creation, execution, verification, and troubleshooting.

This directory is a technical reference index for OpenSearch-related documentation in docpipe.

The [`VectorDBOperator`](../../../src/docpipe/core/operators/vectordb/vectordb_operator.py) with OpenSearch adapter stores document embeddings in OpenSearch for vector similarity search within docpipe pipelines.

## Reference Index

| File | Purpose |
|---|---|
| [`OPENSEARCH_QUICKSTART.md`](OPENSEARCH_QUICKSTART.md) | OpenSearch-specific unit test command and links to related references |
| [`ENVIRONMENT_SETUP.md`](ENVIRONMENT_SETUP.md) | Environment variable reference and `.env` setup details |

## Additional References

- Main user guide for setup and execution: [`USER_GUIDE_PIPELINE_SETUP.md`](../../../USER_GUIDE_PIPELINE_SETUP.md)
- Operator API reference: [`docs/operators/vectordb/opensearch.md`](../../operators/vectordb/opensearch.md)
- Example flow configuration: [`sample_flows/vectordb/opensearch_integration.json`](../../../sample_flows/vectordb/opensearch_integration.json)
