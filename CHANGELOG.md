# Changelog

All notable changes to `docling-pipelines` will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning 2.0.0](https://semver.org/).

---

## [Unreleased]

### Added

- **Full OCR engine exposure** — Both `docling_library` and `docling_serve` providers now accept an `ocr` block inside `text_extraction.provider_config`. Users can set `ocr.engine` (8 engines: `auto`, `easyocr`, `tesserocr`, `tesseract`, `rapidocr`, `ocrmac`, `kserve_v2_ocr`, `nemotron-ocr`), `ocr.mode` (`default`, `full_page`, `layout_regions`, `pdf_aware_layout_regions`), `ocr.enabled` (bool), and `ocr.engine_options` (pass-through dict). The previously hardcoded `ocr_preset: "auto"` default in `DoclingServeClient` is removed — when no engine is specified, the docling-serve instance uses its own default. Old `do_ocr` / `ocr_engine` / `ocr_languages` fields remain functional but are deprecated in favour of the new `ocr` block.

- **docling-pipelines-slim** — New lightweight package variant that excludes certain operator dependencies. Use when your codebase doesn't require specific built-in operators. See [docs/guides/SLIM_VARIANT.md](docs/guides/SLIM_VARIANT.md) for installation and usage details.
- **CI: slim wheel push** — `Build and Push Wheel` Jenkins stage now builds and pushes `docling-pipelines-slim` to Artifactory alongside the main wheel under the same `docling-pipelines/${VERSION}/` folder.
- `StorageOutputOperator` — writes pipeline documents to a pluggable storage destination with three modes: `processed_content`, `refetch_original`, and `comprehensive_export`. Includes `FilesystemDestinationAdapter`, `S3DestinationAdapter`, and `DestinationAdapterFactory` for extensible backend support.
- `S3DestinationAdapter` — writes to Amazon S3 and S3-compatible storage (IBM COS, MinIO) with env-var credential resolution, pre-flight bucket validation, `create_dirs` prefix checking, and optional `verify_expected_bucket_owner` via STS.
- `ibm_cos` provider alias — routes to `S3DestinationAdapter` with a custom `endpoint_url`; no separate adapter required. Mirrors the same alias pattern added to `SourceAdapterFactory`.
- `SharePointDestinationAdapter` — writes to SharePoint document libraries via Microsoft Graph API (client credentials flow) with pre-flight drive/folder validation, overwrite control, and hierarchical path support.
- Hierarchical multi-source path namespacing — when `ingest_source` is configured with multiple `paths`, each source root is namespaced by its folder name at the destination to avoid collisions.
- `onedrive` provider alias — routes to `SharePointDestinationAdapter`; identical `connection_params` and `credentials` to `sharepoint`. Suitable for personal and organisational OneDrive drives.
- `GoogleDriveDestinationAdapter` — writes to Google Drive folders via the Drive API v3 with resumable uploads, lazy sub-folder creation with instance-level caching, overwrite control, and both Service Account and OAuth2 authentication.
- Initial public open-source release preparation
- Release process documentation (`RELEASE_PROCESS.md`)
- Deprecation policy (`docs/guides/DEPRECATION_POLICY.md`)
- Migration guide template (`docs/guides/MIGRATION_GUIDE_TEMPLATE.md`)
- **HashiCorp Vault integration** — `vault://` URI scheme for resolving secrets in flow operator configs at runtime. Enable via `secrets.vault.enabled: true` in `docling-pipelines-config.yaml`. Credentials (`VAULT_ROLE_ID`, `VAULT_SECRET_ID`) supplied via environment variables. Supports AppRole auth, KV v1/v2, TLS, mTLS, Vault Enterprise namespaces, and Docker/Kubernetes file-backed secrets.
- **GPU acceleration for `ExtractOperator`** — `docling_library` provider now supports GPU device selection via `standard_pipeline.accelerator` in `provider_config`. Accepted devices: `mps` (Apple Silicon), `cuda`, `cuda:<index>` (NVIDIA), `xpu` (Intel). When `device` is omitted from the accelerator block, the best available GPU is auto-detected at runtime via torch (CUDA → MPS → XPU). Validates device availability via torch backends before loading any model. Requires `max_workers: 1` and `use_processes: false`. One `DocumentConverter` is constructed per adapter execution and reused across all documents. Flows without accelerator config are unaffected.
- Flow execution now defaults `enable_micro_batching` to `true` for CLI, REST job runs, and `DocpipeFlowManager` when the flow does not set it explicitly. A user-provided `global_config.enable_micro_batching` value still overrides the default.

### Fixed

- `scripts/test_examples.py --dry-run` now skips examples before probing Ollama, OpenSearch, environment variables, or example files.

---

## [0.1.0] - 2025-07-15

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
