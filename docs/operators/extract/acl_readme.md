# ACLOperator

Extracts effective user permissions from document storage providers and appends them as an `allowed_users` column.

- **Short Name:** `acl_operator`
- **Category:** Extract

---

## Overview

`ACLOperator` reads provider credentials from the input table metadata (populated by
`IngestSourceOperator`) and fetches current ACL data for each document from the source system
(SharePoint, S3, Google Drive, etc.). It appends a single `allowed_users` column containing a
JSON array of normalised user identities, leaving all other columns unchanged.

No credential duplication is needed — the operator reads provider and credentials automatically
from upstream `IngestSourceOperator` metadata.

## Key Features

- **Automatic credential extraction**: Provider and credentials come from `IngestSourceOperator` metadata — no duplication
- **Stable identity tuples**: Uses `siteId`/`driveId`/`itemId` for reliable ACL lookups
- **Always-fresh data**: ACLs are fetched at pipeline run time, never cached
- **All-or-nothing mode** (`fail_on_error: true`): Fails the flow if any document fails ACL extraction
- **Best-effort mode** (`fail_on_error: false`): Skips failed documents and continues
- **Batch processing**: Concurrent extraction via asyncio

---

## Operator Configuration

The operator requires minimal configuration; credentials come from the upstream `IngestSourceOperator`.

```json
{
  "type": "acl_operator",
  "name": "extract_acl_permissions",
  "config": {
    "fail_on_error": true
  },
  "depends_on": ["ingest_documents"]
}
```

---

## Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `provider_config` | object | No | `{}` | Provider-specific settings (e.g. `resolve_inheritance`, `expand_groups`) |
| `fail_on_error` | boolean | No | `true` | `true` — fail the flow if any document fails ACL extraction; `false` — skip failed documents and continue |

**Note:** `provider`, credentials, and `connection_params` are read automatically from
`IngestSourceOperator` metadata — do not set them here.

---

## Output Columns

All input columns are preserved. The operator appends:

| Column | PyArrow Type | Description |
|---|---|---|
| `allowed_users` | `string` | JSON array of normalised user identities (emails/UPNs) with access to the document, sorted alphabetically. Empty array `"[]"` when no users have access. |

---

## Examples

### Example 1 — Minimal configuration

```json
{
  "type": "acl_operator",
  "name": "extract_acl_permissions",
  "config": { "fail_on_error": true },
  "depends_on": ["ingest_sharepoint_documents"]
}
```

### Example 2 — With provider-specific settings (best-effort)

```json
{
  "type": "acl_operator",
  "name": "extract_acl_permissions",
  "config": {
    "provider_config": {
      "resolve_inheritance": true,
      "expand_groups": true,
      "normalize_identities": true
    },
    "fail_on_error": false
  },
  "depends_on": ["ingest_sharepoint_documents"]
}
```

### Example 3 — Complete flow (SharePoint → ACL → Extract)

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
        "text_extraction": {"provider": "docling_library"},
        "entity_extraction": {"provider": "none"}
      },
      "depends_on": ["extract_acl_permissions"]
    }
  ]
}
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `FlowExecutionFailedException: No metadata found in input table` | ACLOperator runs before IngestSourceOperator | Ensure `depends_on` points to the ingest node |
| `FlowExecutionFailedException: Provider not found in metadata` | IngestSourceOperator metadata missing provider field | Verify the ingest node includes `provider` in its config |
| `FlowExecutionFailedException: Credentials not found in metadata` | IngestSourceOperator metadata missing credentials | Ensure credentials are set in the ingest config |
| `ACL extraction completed: 0 processed, N failed` | Credentials invalid or insufficient permissions | Check SharePoint credentials; try `fail_on_error: false` to identify failing documents |

---

## Architecture

### Hexagonal layers

The operator follows a three-layer hexagonal architecture:

- **Domain** (`domain/`) — provider-agnostic models: `ACLRequest`, `ACLResponse`, `ACLExtractionResult`, `RawPermission`
- **Ports** (`ports/`) — `ACLExtractionPort` abstract interface
- **Adapters** (`adapters/`) — concrete provider implementations (SharePoint, future: S3, Google Drive, OneDrive, Box)

### Currently supported providers

- **SharePoint** — full implementation with inheritance resolution and group expansion

### Typical pipeline position

```
IngestSourceOperator → ACLOperator → ExtractOperator → [Chunker → Embeddings → VectorDB]
```

### `allowed_users` output format

```json
{ "allowed_users": "[\"user1@contoso.com\", \"user2@contoso.com\"]" }
```

### Error handling modes

| Mode | Behaviour |
|---|---|
| `fail_on_error: true` | All-or-nothing — any single failure aborts the flow |
| `fail_on_error: false` | Best-effort — failed documents are skipped and tracked in metadata |

### Missing Metadata Error (legacy section)

See the [Troubleshooting table](#troubleshooting) above for quick fixes.

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
docling-pipelines --flow-file flow.json --log-level debug
```

## References

- [Operator Reference](../../reference/OPERATORS.md)
- [User Guide: Pipeline Setup](../../../USER_GUIDE_PIPELINE_SETUP.md)
