# Docling Pipelines Documentation

> **For the best experience open [docs/index.html](index.html)** — a fully styled landing page with
> left-sidebar navigation, dark/light mode toggle, and direct links into the Documentation Book.

The table below is a plain-text fallback for tools that render only Markdown.

---

## Documentation Book

The [Docling-pipelines Book](book/site/docling-pipelines/1.0/index.html) is a 12-chapter guide
covering architecture, installation, flow authoring, document processing, vector storage, LLM
integration, deployment, and more.

| # | Chapter |
|---|---------|
| 01 | [Introduction & Architecture](book/site/docling-pipelines/1.0/01_introduction_and_architecture.html) |
| 02 | [Installation & Quick Start](book/site/docling-pipelines/1.0/02_installation_and_quick_start.html) |
| 03 | [Authoring Flows](book/site/docling-pipelines/1.0/03_authoring_flows.html) |
| 04 | [Ingesting Data](book/site/docling-pipelines/1.0/04_ingesting_data.html) |
| 05 | [Extracting & Processing Documents](book/site/docling-pipelines/1.0/05_extracting_and_processing_documents.html) |
| 06 | [Data Quality & Enrichment](book/site/docling-pipelines/1.0/06_data_quality_and_enrichment.html) |
| 07 | [Vector Storage & Retrieval](book/site/docling-pipelines/1.0/07_vector_storage_and_retrieval.html) |
| 08 | [LLM Integration](book/site/docling-pipelines/1.0/08_llm_integration.html) |
| 09 | [Python API](book/site/docling-pipelines/1.0/09_python_api_and_programmatic_usage.html) |
| 10 | [Extending Docling Pipelines](book/site/docling-pipelines/1.0/10_extending_docling_pipelines.html) |
| 11 | [Production Deployment](book/site/docling-pipelines/1.0/11_production_deployment_and_observability.html) |
| 12 | [Troubleshooting & Contributing](book/site/docling-pipelines/1.0/12_troubleshooting_and_contributing.html) |

## Getting Started

- **[Quick Start Guide](../QUICKSTART.md)** — Get your first pipeline running in 5 minutes
- **[Complete Setup Guide](../USER_GUIDE_PIPELINE_SETUP.md)** — Detailed installation and configuration
- **[Troubleshooting Guide](../TROUBLESHOOTING.md)** — Solutions to common issues

## Guides

### Core Guides
- **[Flow Authoring Format](guides/FLOW_AUTHORING_FORMAT.md)**
- **[Flow Configuration Guide](guides/FLOW_CONFIGURATION_GUIDE.md)**
- **[Python API Guide](guides/PYTHON_API_GUIDE.md)**

### Developer Guides
- **[Create Connector Guide](guides/CREATE_CONNECTOR_GUIDE.md)**
- **[Custom Operators Guide](guides/CUSTOM_OPERATORS_GUIDE.md)**
- **[External Operator Integration](guides/EXTERNAL_OPERATOR_INTEGRATION.md)**
- **[Testing Standards](guides/TESTING_STANDARDS.md)**

### Advanced Topics
- **[Advanced Configuration](guides/ADVANCED_CONFIGURATION.md)**
- **[Security Best Practices](guides/SECURITY_BEST_PRACTICES.md)**
- **[Unified LLM Architecture](guides/UNIFIED_LLM_ARCHITECTURE_GUIDE.md)**
- **[Document Libraries](guides/USER_GUIDE_DOCUMENT_LIBRARIES.md)**
- **[Vault Integration](guides/VAULT_INTEGRATION_GUIDE.md)**
- **[UI User Guide](guides/UI_USER_GUIDE.md)**
- **[Logging Best Practices](guides/LOGGING_BEST_PRACTICES.md)**

## Operators

- **[IngestSource](operators/ingest/ingest_source_readme.md)**
- **[Extract](operators/extract/extract_operator_readme.md)**
- **[Chunker](operators/functional/chunker_readme.md)**
- **[Embeddings](operators/functional/embeddings_readme.md)**
- **[VectorDB](operators/vectordb/vectordb_readme.md)**
- **[StorageOutput](operators/storage/storage_output_readme.md)**

Browse all operator docs in [operators/](operators/).

## Reference

- **[Global Configuration Reference](reference/GLOBAL_CONFIG.md)**
- **[Operator Reference](reference/OPERATORS.md)**
- **[Document Schemas](reference/DOCUMENT_SCHEMAS.md)**

## REST API

- **[REST API Server](api/REST_API_SERVER.md)**
- **[Document Retrieval API](api/ACL_DOCUMENT_RETRIEVAL.md)**
- **[OAuth2 Authentication](api/OAUTH2_AUTHENTICATION.md)**

## Integrations

- **[OpenSearch](integrations/opensearch/OPENSEARCH_QUICKSTART.md)**
- **[Milvus](integrations/milvus/README.md)**
- **[Prefect](integrations/prefect/DISTRIBUTED_EXECUTION_GUIDE.md)**
- **[HashiCorp Vault](integrations/vault/README.md)**

## Deployment

- **[OpenShift Deployment](deployment/OPENSHIFT.md)**
- **[Architecture Overview](../ARCHITECTURE.md)**

## Contributing

- **[Contributing Guide](../CONTRIBUTING.md)**
- **[Documentation Style Guide](guides/DOCUMENTATION_STYLE_GUIDE.md)**
