# Docling pipelines

[![PyPI version](https://img.shields.io/pypi/v/docling-pipelines)](https://pypi.org/project/docling-pipelines/)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License MIT](https://img.shields.io/github/license/IBM/docling-pipelines)](https://opensource.org/licenses/MIT)

## What is Docling pipelines?

Docling pipelines is an enterprise-grade document curation pipeline for Retrieval Augmented Generation (RAG) applications. It ingests data from unstructured sources, curates documents, and writes entities and vector embeddings to targets — enabling AI-ready pipelines at scale.

It connects to cloud document sources (S3, OneDrive, SharePoint, Google Drive, Box, and more) and extracts content and entities from PDF, DOCX, HTML, images, and other formats using [Docling](https://github.com/docling-project/docling). Extracted content is curated for LLMs, converted into chunks and embeddings, and stored in a vector database such as Milvus or OpenSearch.

## Features

- 📥 **Multi-source ingestion** — local filesystem, Amazon S3, IBM COS, SharePoint, OneDrive, Google Drive, Box, CSV, and web pages
- 📄 **Document extraction** — PDF, DOCX, HTML, images, and more via Docling, with optional VLM and ASR pipelines
- 🧠 **Entity extraction** — LLM-based extraction via LiteLLM (100+ providers), IBM watsonx.ai, or Docling templates
- ✂️ **Chunking** — Docling-native and semantic chunking strategies
- 🔢 **Embeddings** — vector embedding generation for any downstream vector store
- 🔍 **Quality operators** — language detection, readability scoring, PII/HAP detection, deduplication, redaction, SQL filtering, document classification, and ML enrichment
- 🗄️ **Vector storage** — write to OpenSearch or Milvus
- 🔀 **DAG-based flows** — define pipelines as JSON with automatic dependency resolution and parallel execution
- 🔌 **Extensible** — load custom operators from Python packages, local paths, or S3 without modifying core code
- 🖥️ **Multiple interfaces** — CLI, Python API (`DocpipeFlowManager`), and REST API (FastAPI)

## Quickstart

### 1. Install

```bash
pip install docling-pipelines
```

Requires Python 3.12. Works on macOS and Linux (x86_64 and arm64).

### 2. Run a flow (CLI)

```bash
docling-pipelines --flow-file path/to/flow.json
```

Validate without executing:

```bash
docling-pipelines --flow-file flow.json --validate
```

List all available operators:

```bash
docling-pipelines --list-operators
```

### 3. Python API

```python
from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

manager = DocpipeFlowManager(flow_file="path/to/flow.json")
result = manager.execute()
```

Log verbosity is controlled via `DS_LOG_LEVEL` (`DEBUG`, `INFO`, `WARNING`).

## Documentation

Check out the full [documentation](docs/README.md) for installation, flow authoring, operator reference, and more:

- [Quick Start Guide](QUICKSTART.md) — first pipeline in under 5 minutes
- [Pipeline Setup Guide](USER_GUIDE_PIPELINE_SETUP.md) — complete setup with Ollama, OpenSearch, and flow examples
- [Flow Authoring Format](docs/guides/FLOW_AUTHORING_FORMAT.md) — declarative flow authoring
- [Operator Reference](docs/reference/OPERATORS.md) — full parameter specs for all operators
- [Architecture](ARCHITECTURE.md) — system design and distributed execution patterns
- [Troubleshooting](TROUBLESHOOTING.md) — common issues and solutions

## Available Operators

| Category | Operators |
|---|---|
| **Ingest** | Local File Ingest (`ingest_local`), Remote Source Ingest (`ingest_source`) — [S3, IBM COS, SharePoint, OneDrive, Google Drive, Box, CSV, web](docs/operators/ingest_source/README.md) |
| **Extract** | Document Extractor (`extract_operator`), ACL Extraction (`acl_operator`) |
| **Functional** | Chunking (`chunker`), Embeddings (`embeddings`), Branching Operator (`branching`), Merge Operator (`merge`), Document ID Hash (`doc_id_hash`), Entity Curation (`entity_curation`), No-op (`noop`) |
| **Quality** | Language Annotator (`lang_detect`), Readability Operator (`readability`), PII and HAP Annotator (`pii_and_hap`), Document Classifier (`document_classifier`), Annotation Filter (`sql_filter`), Redaction (`redaction`), De-duplicator (`ededup`), ML Text Enrichment (`ml_enrichment`), Document Quality (`doc_quality`) |
| **VectorDB** | Vector Database (`vectordb`) — OpenSearch, Milvus |
| **Storage** | Document Set (`document_set`) — DuckDB-backed document collections |

For per-operator configuration guides, see [Operator Configuration Guides](docs/reference/OPERATORS.md).

## Examples

Explore [sample flows](examples/) and [DocpipeFlowManager examples](examples/docpipe_flow_manager/) for common pipeline patterns.

For interactive, hands-on tutorials, see the [Jupyter notebook examples](examples/notebooks/README.md).

## Contributing

Please read [Contributing to Docling pipelines](CONTRIBUTING.md) for development setup, code standards, testing requirements, and the pull request process.

## License

The Docling pipelines codebase is under the [MIT License](LICENSE).
