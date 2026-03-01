# OpenSearch Operator — Quick Start

## 1. Install Dependencies

```bash
cd src/datasift_opensource/backend
uv sync --extra dev
```

## 2. Run Unit Tests

```bash
# From the backend directory
export PYTHONPATH="$(cd ../../.. && pwd)/src:${PYTHONPATH}"
uv run pytest ../../../tests/unit/operators/vectordb/test_opensearch_operator.py -v
```

## 3. Run the Integration Example

Requires a running OpenSearch instance (see [`DOCKER_SETUP.md`](DOCKER_SETUP.md)).

```bash
python examples/opensearch_integration_example.py
```

## 4. Flow JSON Config Example

A complete pipeline flow config is available at [`tests/flow_with_opensearch.json`](../../tests/flow_with_opensearch.json). Run it with:

```bash
datasift-orchestrator run --flow tests/flow_with_opensearch.json
```

> For operator configuration parameters, engine/algorithm options, and Python usage examples, see [`docs/operators/opensearch.md`](../operators/opensearch.md).