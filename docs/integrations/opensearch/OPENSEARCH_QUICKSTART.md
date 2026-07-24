# OpenSearch Operator — Quick Start

> Start with the main setup guide: [`USER_GUIDE_PIPELINE_SETUP.md`](../../../USER_GUIDE_PIPELINE_SETUP.md). It covers environment setup, OpenSearch startup, pipeline configuration, flow execution, verification, and troubleshooting.

This page only keeps OpenSearch-specific test and reference pointers that are not covered in the main user guide.

## 1. Run Unit Tests

```bash
# From project root
source .venv/bin/activate
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
uv run pytest tests/unit/operators/vectordb/test_vectordb_operator.py -v
```

## 2. Additional OpenSearch References

- Operator API and configuration reference: [`../operators/opensearch.md`](../../operators/vectordb/opensearch.md)
- OpenSearch environment variables: [`ENVIRONMENT_SETUP.md`](ENVIRONMENT_SETUP.md)
- Example flow config: [`../../../sample_flows/vectordb/opensearch_integration.json`](../../../sample_flows/vectordb/opensearch_integration.json)
