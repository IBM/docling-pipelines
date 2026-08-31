---
name: docpipe-ingest-source-adapter
description: >-
  Add or modify an ingest document source provider for IngestSourceOperator. Use when creating
  its Pydantic configuration, DocumentSourcePort adapter, factory registration, lazy binary
  retrieval, provider tests, runnable flow, dependency and documentation updates. Do not use
  for ordinary transform operators or storage destination adapters.
---

# Docpipe Ingest Source Adapter

Deliver a source provider that is discoverable by `SourceAdapterFactory`, streams domain `Document` metadata efficiently, and can retrieve binary content later for extraction.

## Confirm that a new adapter is needed

Inspect `SourceAdapterFactory._ALIASES` and existing providers first. Add an alias when the requested service is protocol-compatible with an existing adapter and only needs different endpoint configuration. Create a new adapter when authentication, listing, metadata, filtering, download semantics, or service APIs materially differ.

Select the closest reference implementation:

- filesystem-like local traversal: `filesystem`;
- object storage and pagination: `s3`;
- generic page retrieval: `web`;
- Microsoft Graph: `sharepoint` or `onedrive`;
- OAuth/service API with export formats: `google_drive`;
- SDK-based SaaS storage: `box`.

Read `docs/guides/CREATE_CONNECTOR_GUIDE.md`, the selected adapter, its tests, and `src/docpipe/core/operators/ingest/ports/outbound/document_source.py` before editing.

Use [references/reference-implementations.md](references/reference-implementations.md) to choose the closest adapter, tests, and runnable flow. Read only the provider family relevant to the requested connector.

## Required files

Create:

```text
src/docpipe/core/operators/ingest/adapters/outbound/sources/<provider>/
├── __init__.py
├── config.py
└── adapter.py
```

Add authentication helpers only when they encapsulate reusable provider-specific authentication. Do not create empty layers or duplicate the shared REST, secret, or AWS utilities.

## Configuration model

Define a Pydantic `BaseModel` in `config.py` that represents the adapter’s resolved runtime configuration.

- Separate non-secret `connection_params` from `credentials` at the flow boundary.
- Validate required fields, ranges, URLs, concurrency limits, and mutually exclusive options.
- Normalize file extensions to lowercase with a leading dot.
- Support `max_files` and filtering settings relevant to the provider.
- Keep credentials out of schema examples, repr output when practical, errors, and logs.
- Resolve environment-variable references while building config, not by hardcoding secrets into the flow.
- Do not perform network calls in Pydantic validators.

Add a dependency to `pyproject.toml` only when the shared `RestClient` or an existing dependency cannot implement the provider cleanly. Pin it consistently with project policy and verify the lockfile impact.

## Adapter contract

Decorate the concrete class with `@register_source_adapter` and inherit `DocumentSourcePort[ProviderConfig]`. Define:

- `SOURCE_NAME`: exact flow `provider` value;
- `SOURCE_DISPLAY_NAME`;
- `SOURCE_DESCRIPTION`;
- `SOURCE_VERSION`.

Implement every port method.

### `build_config_from_operator_params()`

Map `connection_params`, `credentials`, `included_extensions`, and `max_files` into the Pydantic configuration. Use keyword-only arguments exactly as declared by the port. Resolve environment references through existing helpers and raise actionable `ValueError` messages for missing user configuration.

### `test_connection()`

Perform the cheapest read-only request that proves authentication and target access. Return `(False, actionable_message)` for expected authentication, permission, not-found, throttling, and connection failures. Avoid downloading full documents.

### `fetch_documents()`

Implement an async generator that yields `docpipe.core.operators.ingest.domain.models.Document` objects incrementally.

- Paginate or stream; do not load an unbounded remote listing into memory.
- Apply provider-side filters when available, then enforce extension, hidden-file, empty-file, size, exclusion, and `max_files` semantics locally as needed.
- Use bounded concurrency and deterministic output ordering when downloading metadata concurrently.
- Populate stable `id`, `name`, `source_url`, timestamps, MIME type, size, extension, ACL, and provider metadata.
- Prefer metadata-only discovery with `content=b""`; binary content is fetched on demand.
- Preserve enough information in `source_url`, `id`, or metadata for later retrieval.
- Treat per-document failures consistently: log safely and continue only when the provider contract permits partial success.

### `fetch_binary_content()`

Retrieve bytes for one document using `source_id`, connection parameters, and credentials. Reuse safe clients or sessions where practical. Return `None` only for documented non-fatal cases; raise clear errors when invalid configuration or connection failure should stop processing. Handle provider-native documents that require export rather than download.

### `get_config_schema()`

Return the Pydantic configuration class. The inherited metadata method uses it for source discovery and UI configuration.

## Registration

Import the adapter class in:

```text
src/docpipe/core/operators/ingest/adapters/outbound/sources/__init__.py
```

Add it to `__all__`. This import triggers decorator registration. Do not add source adapters to `DOCPIPE_OPERATORS`; the flow still uses the existing `ingest_source` operator.

Ensure `SOURCE_NAME`, the central import, tests, docs, and sample flow all use the identical provider name. Check for collisions before registering.

## Architecture and security

- Keep provider I/O in the adapter and provider-neutral models in the ingest domain.
- Depend on the `DocumentSourcePort` abstraction; do not make the domain import this adapter.
- Use `get_logger()` and lazy `%s` arguments, with no f-strings or non-ASCII log text.
- Never log tokens, credentials, signed URLs, authorization headers, or full document content.
- Reuse `RestClient` retry and timeout behavior for HTTP providers unless the SDK already supplies equivalent controls.
- Bound retries and concurrency; honor throttling signals and avoid retrying permanent authentication failures.
- Do not make a unit test contact the live provider.

## Unit verification

Create `tests/unit/operators/ingest/test_<provider>_source_adapter.py` and separate config tests when the model is substantial. Cover:

- required fields, normalization, defaults, invalid bounds, and secret resolution;
- adapter metadata and returned config schema;
- mapping from operator parameters to provider config;
- successful and failed `test_connection()` responses;
- pagination, filtering, ordering, `max_files`, and empty listings;
- async document generation and complete domain metadata;
- transient and per-document error behavior;
- successful binary retrieval, export behavior, not found, permission denied, and malformed `source_id`;
- factory registration and creation by `SOURCE_NAME`.

Mock the SDK client or `RestClient` object with `patch.object`/injection. Use `@pytest.mark.asyncio` for async adapter methods and collect the async generator explicitly.

Run at least:

```bash
source .venv/bin/activate
pytest tests/unit/operators/ingest/test_<provider>_source_adapter.py -v
pytest tests/unit/operators/ingest/test_source_adapter_factory.py -v
```

Also run `tests/unit/utils/operators/test_binary_content_fetcher.py` when binary lookup or provider caching behavior changes.

## Runnable feature validation

Create a temporary flow using the provider:

```json
{
  "flow_name": "temporary-provider-validation",
  "global_config": {
    "disable_validation": false,
    "force_ingest": true,
    "enable_micro_batching": false,
    "data_storage_type": "local"
  },
  "flow": [
    {
      "type": "ingest_source",
      "name": "ingest",
      "config": {
        "provider": "<provider>",
        "connection_params": {},
        "credentials": {},
        "max_files": 3
      }
    }
  ]
}
```

Reference credentials through environment variables. Add `extract_operator` only when validating lazy binary retrieval. Validate before executing and use an isolated provider folder, prefix, or account resource.

Use `.skills/feature-testing-workflow/SKILL.md` to verify actual row counts, metadata columns, filters, job status, and extracted content without depending on pytest. Mark live-provider checks blocked when credentials or service access are unavailable; do not claim unit mocks prove live connectivity.

## Documentation and completion

- Add provider configuration, credentials, permissions, filters, limits, and examples to the appropriate ingest documentation and `docs/reference/OPERATORS.md`.
- Add a focused provider README beside existing adapters when that remains the local convention.
- Add one customer-facing sample flow only when it is safe, credential-placeholder based, and meaningfully distinct.
- Update setup or security documentation for new dependencies, scopes, environment variables, or network access.
- Add the change under `## [Unreleased]` in `CHANGELOG.md`.

Run focused tests, Ruff, formatting, relevant MyPy checks, flow validation, factory discovery, and the live feature scenario when access exists. Report unverified provider behavior explicitly.
