# ACL Operator

## Overview

The ACL (Access Control List) operator extracts effective user permissions from document storage providers (SharePoint, S3, Google Drive, etc.). It automatically retrieves credentials from IngestSourceOperator metadata, eliminating configuration duplication. The operator follows hexagonal architecture principles to provide a clean, provider-agnostic interface for ACL extraction.

## Key Features

- **Automatic Credential Extraction**: Reads provider and credentials from IngestSourceOperator metadata - no duplication needed
- **Stable Identity Tuples**: Uses stable identifiers (siteId, driveId, itemId) for reliable ACL lookups
- **Single Column Output**: Adds only `allowed_users` column with JSON array of normalized user identities
- **All-or-Nothing Behavior**: By default (`fail_on_error=true`), fails completely if ANY document fails ACL extraction
- **Flexible Error Handling**: With `fail_on_error=false`, skips failed documents and continues processing
- **Hexagonal Architecture**: Clean separation between domain logic, ports, and provider-specific adapters
- **Batch Processing**: Efficient concurrent ACL extraction for multiple documents
- **Fresh Data**: Always fetches latest ACL information (no caching)

## Architecture

The operator follows hexagonal architecture with three layers:

### Domain Layer (`domain/`)

- **Models**: Core business entities (ACLRequest, ACLResponse, ACLExtractionResult, RawPermission)
- Provider-agnostic data structures representing ACL concepts

### Ports Layer (`ports/`)

- **ACLExtractionPort**: Abstract interface defining the contract for ACL extraction
- Methods for extraction, inheritance resolution, group expansion, and identity normalization

### Adapters Layer (`adapters/`)

- **Factory**: ACLAdapterFactory for creating provider-specific adapters
- **Outbound Adapters**: Provider-specific implementations (SharePoint, S3, etc.)
- Each adapter implements the ACLExtractionPort interface

## Supported Providers

### Currently Implemented

- **SharePoint**: Full implementation with inheritance resolution and group expansion

### Future Providers

- S3
- Google Drive
- OneDrive
- Box

## Configuration

The ACL operator requires minimal configuration since it automatically extracts credentials from the input table metadata (populated by IngestSourceOperator).

### Minimal Configuration

```json
{
  "operator": "acl_operator",
  "config": {
    "fail_on_error": true
  }
}
```

### With Provider-Specific Settings

```json
{
  "operator": "acl_operator",
  "config": {
    "provider_config": {
      "resolve_inheritance": true,
      "expand_groups": true,
      "normalize_identities": true
    },
    "fail_on_error": false
  }
}
```

### Configuration Parameters

| Parameter         | Type | Required | Default | Description                                                                         |
| ----------------- | ---- | -------- | ------- | ----------------------------------------------------------------------------------- |
| `provider_config` | dict | No       | `{}`    | Optional ACL-specific settings (e.g., resolve_inheritance, expand_groups)           |
| `fail_on_error`   | bool | No       | `true`  | If true, fails completely on ANY error. If false, skips failed files and continues. |

**Note**: Provider, credentials, and connection_params are automatically extracted from the input table metadata - no need to specify them in the ACL operator configuration.

## Flow Example

Complete flow showing IngestSourceOperator → ACLOperator → ExtractOperator:

```json
{
  "flow_name": "acl-extraction-pipeline",
  "description": "Extract documents with ACL permissions",
  "flow": [
    {
      "type": "ingest_source",
      "name": "ingest_sharepoint_documents",
      "config": {
        "provider": "sharepoint",
        "connection_params": {
          "document_library_id": "b!...",
          "folder_path": null,
          "recursive": true
        },
        "credentials": {
          "client_id": "your-client-id",
          "client_secret": "your-client-secret",  # pragma: allowlist secret
          "tenant_id": "your-tenant-id"
        },
        "include_filter": ".txt,.pdf,.docx"
      }
    },
    {
      "type": "acl_operator",
      "name": "extract_acl_permissions",
      "config": {
        "fail_on_error": true
      },
      "depends_on": ["ingest_sharepoint_documents"]
    },
    {
      "type": "extract_operator",
      "name": "extract_document_content",
      "config": {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "none"
      },
      "depends_on": ["extract_acl_permissions"]
    }
  ]
}
```

## Output

The operator adds a single column to the PyArrow table:

### `allowed_users` Column

- **Type**: string (JSON array)
- **Content**: Normalized user identities (emails/UPNs) with access to the document
- **Format**: JSON array of strings, sorted alphabetically

Example:

```json
{
  "id": "doc123",
  "name": "document.pdf",
  "source_id": "/sites/mysite/Shared Documents/document.pdf",
  "allowed_users": "[\"user1@contoso.com\", \"user2@contoso.com\", \"user3@contoso.com\"]"
}
```

### Behavior Modes

#### fail_on_error=true (Default)

- **All-or-nothing**: If ANY document fails ACL extraction, the entire flow fails
- **Use case**: When ACL data is critical and incomplete results are unacceptable
- **Output**: All documents with ACL data, or complete failure

#### fail_on_error=false

- **Best-effort**: Skips documents that fail ACL extraction, continues with others
- **Use case**: When partial results are acceptable
- **Output**: Only documents with successful ACL extraction (failed documents removed from table)
- **Tracking**: Failed documents are tracked in operator metadata

## Implementation Status

### Phase 1: Foundation ✅

- [x] Directory structure
- [x] Domain models (ACLRequest, ACLResponse, ACLExtractionResult, RawPermission)
- [x] Port interface (ACLExtractionPort)
- [x] Adapter factory (ACLAdapterFactory)
- [x] Package initialization

### Phase 2: Core Operator ✅

- [x] ACLOperator implementation
- [x] PyArrow table integration
- [x] Batch processing with asyncio
- [x] Error handling (fail_on_error modes)
- [x] Metadata extraction from IngestSourceOperator
- [x] Statistics tracking (processed, failed, skipped)

### Phase 3: SharePoint Adapter ✅

- [x] SharePoint configuration
- [x] Graph API client integration
- [x] Inheritance resolution
- [x] Group expansion
- [x] Identity normalization
- [x] Stable identity tuple usage (siteId, driveId, itemId)

### Phase 4: Testing ✅

- [x] Unit tests for domain models
- [x] Integration tests (end-to-end with real SharePoint)
- [x] Flow validation tests

## Testing

### Unit Tests

```bash
# Run unit tests
PYTHONPATH=src pytest tests/unit/operators/acl/ -v

# Run specific test
PYTHONPATH=src pytest tests/unit/operators/acl/test_domain_models.py -v
```

### Integration Tests

```bash
# Run integration tests (requires SharePoint credentials)
PYTHONPATH=src pytest tests/integration/test_acl_e2e.py -v -s
```

The integration test executes a complete flow:

1. IngestSourceOperator - Ingests documents from SharePoint
2. ACLOperator - Extracts ACL permissions
3. ExtractOperator - Extracts document content

## Performance

### Optimizations

- **Batch Processing**: Single async batch call for all documents instead of individual calls
- **Concurrent Execution**: Uses asyncio for parallel ACL extraction
- **Efficient Identity Resolution**: Caches group expansions and identity lookups within a batch
- **Minimal Memory Footprint**: Processes documents in streaming fashion

### Typical Performance

- **Small batches** (1-10 documents): ~2-5 seconds
- **Medium batches** (10-100 documents): ~5-15 seconds
- **Large batches** (100+ documents): ~15-60 seconds

Performance depends on:

- Number of documents
- SharePoint API response times
- Number of groups to expand
- Network latency

## Design Principles

1. **No Credential Duplication**: Credentials come from IngestSourceOperator metadata
2. **Stable Identifiers**: Uses stable identity tuples (siteId, driveId, itemId) for reliable lookups
3. **No Caching**: ACLs are always fetched fresh to ensure latest permissions
4. **Provider Abstraction**: Internal provider details hidden behind port interface
5. **Keyword-Only Arguments**: All methods use keyword-only arguments for clarity
6. **Type Safety**: Comprehensive type hints throughout
7. **Error Handling**: Graceful degradation with detailed error messages
8. **Single Responsibility**: Each layer has a clear, focused purpose

## Troubleshooting

### Common Issues

#### Missing Metadata Error

```
FlowExecutionFailedException: No metadata found in input table
```

**Solution**: Ensure ACLOperator comes after IngestSourceOperator in the flow.

#### Provider Not Found

```
FlowExecutionFailedException: Provider not found in metadata
```

**Solution**: Verify IngestSourceOperator includes provider field in metadata.

#### Credentials Not Found

```
FlowExecutionFailedException: Credentials not found in metadata
```

**Solution**: Ensure IngestSourceOperator includes credentials in metadata.

#### All Documents Failed

```
ACL extraction completed: 0 processed, 10 failed, 0 skipped
```

**Solution**:

- Check SharePoint credentials are valid
- Verify document library permissions
- Review error logs for specific failure reasons
- Try with `fail_on_error=false` to see which documents succeed

### Debug Mode

Enable debug logging to see detailed ACL extraction information:

```bash
datasift-orchestrator --flow-file flow.json --log-level debug
```

## References

- [ACL Operator Architecture](docs/operators/acl/ACL_OPERATOR_ARCHITECTURE.md)
- [Implementation Plan Phase 1](docs/operators/acl/ACL_IMPLEMENTATION_PLAN_PHASE1_REVISED.md)
- [Operator Reference](OPERATOR_REFERENCE.md)
- [User Guide: Pipeline Setup](USER_GUIDE_PIPELINE_SETUP.md)
