# Ingest Source Reference Implementations

Choose one provider family and study its config, adapter, tests, and flow. Do not combine SDK, Graph, and object-storage patterns unless the requested service genuinely requires them.

## Provider map

| Provider family | Implementation | Primary tests | Best use |
|---|---|---|---|
| Local traversal | `sources/filesystem/config.py`, `sources/filesystem/adapter.py` | `tests/unit/operators/ingest/test_filesystem_source_adapter.py` | Path validation, recursion, extension filters, lazy local reads |
| Object storage | `sources/s3/config.py`, `sources/s3/adapter.py` | `tests/unit/operators/ingest/test_s3_source_adapter.py` | Pagination, prefixes, S3-compatible endpoints, bounded concurrency |
| Web pages | `sources/web/config.py`, `sources/web/adapter.py` | `tests/unit/operators/ingest/test_web_source_adapter.py` | URL validation, page retrieval, HTML/PDF content types |
| Google Drive | `sources/google_drive/config.py`, `sources/google_drive/adapter.py` | `tests/unit/operators/ingest/test_google_drive_source_adapter.py`, `test_google_drive_config.py` | Service APIs, native-file export, shared-drive traversal |
| Microsoft Graph | `sources/onedrive/` and `sources/sharepoint/` | `tests/unit/operators/ingest/test_microsoft_source_adapters.py` | Client credentials, drives/sites, Graph pagination and downloads |
| SDK-backed SaaS | `sources/box/config.py`, `sources/box/adapter.py`, `sources/box/auth.py` | `tests/unit/operators/ingest/test_box_source_adapter.py` | Provider SDK auth, folders, relative paths, binary downloads |

All source paths above are relative to `src/docpipe/core/operators/ingest/adapters/outbound/sources/`.

## Registration and discovery

- Port: `src/docpipe/core/operators/ingest/ports/outbound/document_source.py`
- Factory and decorator: `src/docpipe/core/operators/ingest/adapters/outbound/sources/factories/source_factory.py`
- Central registration imports: `src/docpipe/core/operators/ingest/adapters/outbound/sources/__init__.py`
- Factory tests: `tests/unit/operators/ingest/test_source_adapter_factory.py`

Use the actual `SOURCE_NAME` as the flow provider. For example, the Box adapter currently registers `box_driver`; do not assume the folder name is always the provider string.

## Lazy-content path

- Domain document: `src/docpipe/core/operators/ingest/domain/models.py`
- Adapter-to-table conversion: `src/docpipe/core/operators/ingest/ingest_source.py`
- On-demand lookup: `src/docpipe/utils/operators/binary_content_fetcher.py`
- Lookup tests: `tests/unit/utils/operators/test_binary_content_fetcher.py`
- Extraction integration: `tests/integration/test_ingest_extract_integration.py`

For metadata discovery, yield `Document(content=b"")` when the provider supports later retrieval. Ensure the resulting source identifier is sufficient for `fetch_binary_content()` after the initial adapter instance is gone.

## Flow references

- Local baseline: `sample_flows/quickstart/basic_ingest_extract.json`
- S3 to OpenSearch: `sample_flows/use_cases/s3_to_opensearch.json`
- Storage-output source/refetch scenarios: files under `sample_flows/storage_output/`
- S3 integration test: `tests/integration/test_s3_ingest_extract_pipeline.py`

Reduce these flows to `ingest_source` plus the minimum downstream operator. Add `extract_operator` specifically when proving lazy binary retrieval or provider-native export.

## Documentation references

- Connector workflow: `docs/guides/CREATE_CONNECTOR_GUIDE.md`
- Ingest parameters: the `ingest_source` section of `docs/reference/OPERATORS.md`
- Existing provider notes: `README.md` files inside each source folder
- Security practices: `docs/guides/SECURITY_BEST_PRACTICES.md`

Use existing provider READMEs for service-specific scopes and configuration, while following current global documentation and changelog rules for new files.
