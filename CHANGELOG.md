# Changelog

All notable changes to `docling-pipelines` will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning 2.0.0](https://semver.org/).

---

## [Unreleased]

### Added

- Initial public open-source release preparation
- Release process documentation (`RELEASE_PROCESS.md`)
- Deprecation policy (`docs/guides/DEPRECATION_POLICY.md`)
- Migration guide template (`docs/guides/MIGRATION_GUIDE_TEMPLATE.md`)

---

## [0.1.0] - 2026-07-15

### Added

- Modular operator-based data processing framework for building document curation pipelines
- **Extract operators**: `ExtractOperator` with support for Docling document extraction, entity extraction, and multiple output modes
- **Ingest operators**: `IngestLocalOperator`, `IngestSourceOperator` with support for local filesystem, S3, Azure Blob, Google Cloud Storage, and Box
- **ACL operators**: `ACLOperator` for access control list management
- **Functional operators**: `ChunkerOperator`, `EmbeddingsOperator`, `BranchingOperator`, `NOOPOperator`, `MergeOperator`, `EntityCurationOperator`, `DocIdHashOperator`
- **Quality operators**: `EdedupOperator`, `RedactionOperator`, `LanguageDetect`, `SQLFilterOperator`, `DocumentClassifierOperator`, `ReadabilityOperator`, `PIIAndHAPAnnotator`, `MLEnrichmentOperator`, `DocQuality`
- **Storage operators**: `DocumentSetOperator` for document set management
- **VectorDB operators**: `VectorDBOperator` with OpenSearch adapter
- DAG-based flow execution model defined via JSON flow configuration files
- Prefect orchestration layer for parallel execution and task dependency management
- FastAPI REST service with OpenAPI / Swagger documentation
- CLI entry point (`docling-pipelines`) for flow execution, validation, and operator listing
- Python library interface via `DocpipeFlowManager`
- PyArrow table format for all inter-operator data transfer
- JSON structured logging (`DS_LOG_JSON=True`) via `ConditionalFormatter`
- Sensitive data sanitisation (`sanitize_sensitive_data()`) in REST API calls
- Job run tracking with metadata aggregation
- `detect-secrets` pre-commit hook integration
- SonarQube, ruff, mypy, and Mend CI quality gates
- Comprehensive documentation under `docs/`

[Unreleased]: https://github.com/IBM/docling-pipelines/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/IBM/docling-pipelines/releases/tag/v0.1.0
