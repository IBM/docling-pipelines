# StorageOutputOperator

The `StorageOutputOperator` writes pipeline documents to a storage destination. It accepts the standard Docling Pipelines PyArrow table and produces the same table with write-result columns appended.

## Overview

| Attribute | Value |
|---|---|
| Operator type | `docpipe.core.operators.storage.storage_output_operator.StorageOutputOperator` |
| Short name | `storage_output` |
| Category | `Storage` |
| Input columns | `id, name, path, content, metadata, document_format` |
| Output columns | Input columns + `write_status, destination_path, bytes_written, write_error` |

## Operating Modes

### `processed_content`
Writes the extracted `content` column to the destination as `.md`, `.txt`, or `.json`. Does not require a source connection.

### `refetch_original`
Re-fetches the original binary file from the source system using the `path` column, then writes it to the destination in its original format. Requires an upstream ingest_source operator.

### `comprehensive_export`
Writes three artefacts per document to the destination:
- Original binary (re-fetched from source)
- Extracted content file (`.md`, `.txt`, or `.json`)
- Metadata JSON sidecar (optional, enabled by `include_metadata_sidecar: true`)

Requires an upstream ingest_source operator.

## Configuration

```json
{
  "type": "storage_output",
  "name": "storage_output",
  "config": {
    "mode": "processed_content",

    "destination_config": {
      "provider": "filesystem",
      "provider_config": {
        "root_path": "/output/docs",
        "create_dirs": true,
        "overwrite_existing": true
      },
      "credentials": {}
    },

    "output_format": {
      "content_format": "md",
      "include_metadata_sidecar": false
    },

    "output_structure": {
      "path_template": "{year}/{month}/{name}.{ext}"
    }
  }
}
```

## Parameters

### Top-level

| Parameter | Type | Required | Description |
|---|---|---|---|
| `mode` | string | Yes | `processed_content`, `refetch_original`, or `comprehensive_export` |
| `destination_config` | object | Yes | Destination connection where files are written |
| `output_format` | object | No | Controls content format and sidecar options |
| `output_structure` | object | No | Controls output directory/file naming |

### `destination_config`

| Field | Type | Description |
|---|---|---|
| `provider` | string | Adapter name: `filesystem`, `s3`, `ibm_cos`, `sharepoint`, or `onedrive` |
| `provider_config` | object | Provider-specific connection parameters |
| `credentials` | object | Provider-specific credentials |

### `output_format`

| Field | Type | Default | Description |
|---|---|---|---|
| `content_format` | string | `md` | Output format for content: `md`, `txt`, or `json` |
| `include_metadata_sidecar` | bool | `false` | Write a `.json` metadata sidecar per document (mode 3 only) |

### `output_structure`

| Field | Type | Default | Description |
|---|---|---|---|
| `path_template` | string | `{name}.{ext}` | Template string for output file path relative to `root_path` |
| `type` | string | `flat` | `flat` or `hierarchical` (mirrors source directory tree) |
| `overwrite_existing` | bool | `true` | When `false`, skips files already present at the destination |

## Path Template Variables

| Variable | Resolves to |
|---|---|
| `{doc_id}` | Document `id` column value |
| `{name}` | Document `name` stem (without extension) |
| `{ext}` | Output extension (`content_format` for mode 1, original format for modes 2 & 3) |
| `{year}` | UTC year at write time (e.g. `2026`) |
| `{month}` | UTC month, zero-padded (e.g. `06`) |
| `{day}` | UTC day, zero-padded (e.g. `26`) |

**Example:** `"{year}/{month}/{doc_id}.{ext}"` → `"2026/06/abc123.md"`

When no template is given, files are written flat as `{name}.{ext}`.

## Output Table Schema

All input columns are passed through unchanged. The following columns are appended:

| Column | Type | Values |
|---|---|---|
| `write_status` | string | `success`, `failed`, `skipped` |
| `destination_path` | string | Full path written; `null` on failure |
| `bytes_written` | int64 | Bytes written; `0` on failure |
| `write_error` | string | Error message; `null` on success |

## Providers

### Filesystem

**Prerequisites:** None — uses the local file system.

#### `provider_config`

| Field | Type | Default | Description |
|---|---|---|---|
| `root_path` | string | required | Base directory to write files into |
| `create_dirs` | bool | `true` | Auto-create missing subdirectories |
| `overwrite_existing` | bool | `true` | Overwrite files that already exist; `false` records `skipped` status |

#### `credentials`

Not required — pass `{}`.

---

### S3

Writes to Amazon S3 or any S3-compatible storage.

**Prerequisites:** Install the `boto3` extra:

```bash
uv pip install boto3
```

Credentials are read from environment variables. Never hard-code access keys in flow JSON files.

#### `provider_config`

| Field | Type | Default | Description |
|---|---|---|---|
| `bucket` | string | required | Target S3 bucket name |
| `prefix` | string | required | Base key prefix for all written objects (e.g. `exports/docs/`) |
| `region` | string | `None` | AWS region (e.g. `us-east-1`); optional for S3-compatible storage |
| `create_dirs` | bool | `true` | When `false`, validates the prefix already exists before writing |
| `endpoint_url` | string | `None` | Custom endpoint for S3-compatible storage (e.g. IBM COS) |
| `verify_expected_bucket_owner` | bool | `false` | Verify bucket owner via STS (AWS only) |

Writing to the bucket root is not permitted — `prefix` must be set.

#### `credentials`

| Field | Type | Description |
|---|---|---|
| `access_key` | string | AWS access key ID. Use `${ENV_VAR}` syntax to read from environment |
| `secret_key` | string | AWS secret access key. Use `${ENV_VAR}` syntax to read from environment |

#### `destination_path` format

For S3 writes the `destination_path` output column is formatted as `s3://<bucket>/<key>`.

---

### IBM COS

Writes to IBM Cloud Object Storage using HMAC credentials. Uses the S3 adapter internally — set `"provider": "ibm_cos"` and supply `endpoint_url` in `provider_config`.

**Prerequisites:** Install the `boto3` extra:

```bash
uv pip install boto3
```

#### `provider_config`

| Field | Type | Default | Description |
|---|---|---|---|
| `bucket` | string | required | Target COS bucket name |
| `prefix` | string | required | Base key prefix for all written objects (e.g. `exports/docs/`) |
| `endpoint_url` | string | required | IBM COS regional endpoint (e.g. `https://s3.us-south.cloud-object-storage.appdomain.cloud`) |
| `region` | string | `None` | COS region; optional |
| `create_dirs` | bool | `true` | When `false`, validates the prefix already exists before writing |

Writing to the bucket root is not permitted — `prefix` must be set.

#### `credentials`

| Field | Type | Description |
|---|---|---|
| `access_key` | string | HMAC access key ID. Use `${ENV_VAR}` syntax to read from environment |
| `secret_key` | string | HMAC secret access key. Use `${ENV_VAR}` syntax to read from environment |

#### `destination_path` format

For IBM COS writes the `destination_path` output column is formatted as `s3://<bucket>/<key>`.

---

### SharePoint

Writes to a Microsoft SharePoint document library via the Microsoft Graph API using Azure AD app-only authentication.

**Prerequisites:** Install `msal` and `requests`:

```bash
uv pip install msal requests
```

Credentials must reference environment variables. Never hard-code Azure AD secrets in flow JSON files.

#### `provider_config`

| Field | Type | Default | Description |
|---|---|---|---|
| `drive_id` | string | required | Microsoft Graph drive ID for the SharePoint document library (e.g. `b!abc123...`) |
| `folder_path` | string | `""` | Destination folder within the drive (e.g. `/Processed Documents`). Leave empty to write to the drive root |
| `create_dirs` | bool | `true` | When `false`, `validate_destination` checks the target folder already exists before writing |
| `graph_api_version` | string | `v1.0` | Microsoft Graph API version: `v1.0` or `beta` |

#### `credentials`

| Field | Type | Description |
|---|---|---|
| `client_id` | string | Azure AD application (client) ID — use `${ENV_VAR}` syntax |
| `client_secret` | string | Azure AD application client secret — use `${ENV_VAR}` syntax |
| `tenant_id` | string | Azure AD tenant (directory) ID — use `${ENV_VAR}` syntax |

#### `destination_path` format

For SharePoint writes the `destination_path` output column contains the `webUrl` returned by the Graph API (e.g. `https://tenant.sharepoint.com/sites/MySite/...`).

---

### OneDrive

Writes to a Microsoft OneDrive drive via the Microsoft Graph API. Uses the SharePoint adapter internally — the configuration shape, credentials, and API endpoints are identical. Set `"provider": "onedrive"` in `destination_config`.

**Prerequisites:** Install `msal` and `requests`:

```bash
uv pip install msal requests
```

Credentials must reference environment variables. Never hard-code Azure AD secrets in flow JSON files.

#### `provider_config`

| Field | Type | Default | Description |
|---|---|---|---|
| `drive_id` | string | required | Microsoft Graph drive ID for the OneDrive drive (e.g. `b!abc123...`) |
| `folder_path` | string | `""` | Destination folder within the drive (e.g. `dest_files`). Leave empty to write to the drive root |
| `create_dirs` | bool | `true` | When `false`, `validate_destination` checks the target folder already exists before writing |
| `graph_api_version` | string | `v1.0` | Microsoft Graph API version: `v1.0` or `beta` |

#### `credentials`

| Field | Type | Description |
|---|---|---|
| `client_id` | string | Azure AD application (client) ID — use `${ENV_VAR}` syntax |
| `client_secret` | string | Azure AD application client secret — use `${ENV_VAR}` syntax |
| `tenant_id` | string | Azure AD tenant (directory) ID — use `${ENV_VAR}` syntax |

#### `destination_path` format

For OneDrive writes the `destination_path` output column contains the `webUrl` returned by the Graph API.

## Examples

### Filesystem — export extracted markdown

```json
{
  "type": "storage_output",
  "name": "storage_output",
  "config": {
    "mode": "processed_content",
    "destination_config": {
      "provider": "filesystem",
      "provider_config": { "root_path": "/output/markdown" },
      "credentials": {}
    },
    "output_format": { "content_format": "md" },
    "output_structure": { "path_template": "{year}/{month}/{name}.{ext}" }
  }
}
```

### Filesystem — copy original files to archive

Modes `refetch_original` and `comprehensive_export` re-fetch the original binary using the upstream ingest_source operator — no additional source configuration is required.

```json
{
  "type": "storage_output",
  "name": "storage_output",
  "config": {
    "mode": "refetch_original",
    "destination_config": {
      "provider": "filesystem",
      "provider_config": { "root_path": "/archive/originals", "overwrite_existing": false },
      "credentials": {}
    },
    "output_structure": { "path_template": "{name}.{ext}" }
  }
}
```

### Filesystem — full compliance archive

```json
{
  "type": "storage_output",
  "name": "storage_output",
  "config": {
    "mode": "comprehensive_export",
    "destination_config": {
      "provider": "filesystem",
      "provider_config": { "root_path": "/export/contracts" },
      "credentials": {}
    },
    "output_format": { "content_format": "md", "include_metadata_sidecar": true },
    "output_structure": { "path_template": "{year}/{month}/{doc_id}/{name}.{ext}" }
  }
}
```

Output per document:
```
/export/contracts/2026/06/abc123/
├── report.pdf        ← original binary
├── report.md         ← extracted content
└── report.json       ← metadata sidecar
```

---

### S3 — export extracted content

Credentials are supplied as environment variable references (`${ENV_VAR}`).

```json
{
  "type": "storage_output",
  "name": "storage_output",
  "config": {
    "mode": "processed_content",
    "destination_config": {
      "provider": "s3",
      "provider_config": {
        "bucket": "my-export-bucket",
        "prefix": "exports/markdown/",
        "region": "us-east-1",
        "create_dirs": true
      },
      "credentials": {
        "access_key": "${S3_DEST_ACCESS_KEY}",
        "secret_key": "${S3_DEST_SECRET_KEY}"
      }
    },
    "output_format": { "content_format": "md" },
    "output_structure": { "path_template": "{year}/{month}/{name}.{ext}" }
  }
}
```

### S3 — archive original files (S3 source → S3 destination)

```json
{
  "type": "storage_output",
  "name": "storage_output",
  "config": {
    "mode": "refetch_original",
    "destination_config": {
      "provider": "s3",
      "provider_config": {
        "bucket": "my-archive-bucket",
        "prefix": "archive/originals/",
        "region": "us-east-1",
        "create_dirs": true
      },
      "credentials": {
        "access_key": "${S3_DEST_ACCESS_KEY}",
        "secret_key": "${S3_DEST_SECRET_KEY}"
      }
    },
    "output_structure": { "overwrite_existing": false }
  }
}
```

### S3 — full compliance export (S3 destination)

```json
{
  "type": "storage_output",
  "name": "storage_output",
  "config": {
    "mode": "comprehensive_export",
    "destination_config": {
      "provider": "s3",
      "provider_config": {
        "bucket": "my-compliance-bucket",
        "prefix": "exports/contracts/",
        "region": "us-east-1"
      },
      "credentials": {
        "access_key": "${S3_DEST_ACCESS_KEY}",
        "secret_key": "${S3_DEST_SECRET_KEY}"
      }
    },
    "output_format": { "content_format": "md", "include_metadata_sidecar": true },
    "output_structure": { "path_template": "{year}/{month}/{doc_id}/{name}.{ext}" }
  }
}
```

Output per document in S3:
```
s3://my-compliance-bucket/exports/contracts/2026/06/abc123/
  report.pdf        ← original binary
  report.md         ← extracted content
  report.json       ← metadata sidecar
```

### IBM COS — export extracted content

```json
{
  "type": "storage_output",
  "name": "storage_output",
  "config": {
    "mode": "processed_content",
    "destination_config": {
      "provider": "ibm_cos",
      "provider_config": {
        "bucket": "my-cos-bucket",
        "prefix": "exports/markdown/",
        "endpoint_url": "${COS_ENDPOINT_URL}",
        "create_dirs": true
      },
      "credentials": {
        "access_key": "${COS_ACCESS_KEY}",
        "secret_key": "${COS_SECRET_KEY}"
      }
    },
    "output_format": { "content_format": "md" },
    "output_structure": { "path_template": "{year}/{month}/{name}.{ext}" }
  }
}
```

### IBM COS — full compliance archive

```json
{
  "type": "storage_output",
  "name": "storage_output",
  "config": {
    "mode": "comprehensive_export",
    "destination_config": {
      "provider": "ibm_cos",
      "provider_config": {
        "bucket": "my-compliance-bucket",
        "prefix": "exports/contracts/",
        "endpoint_url": "${COS_ENDPOINT_URL}"
      },
      "credentials": {
        "access_key": "${COS_ACCESS_KEY}",
        "secret_key": "${COS_SECRET_KEY}"
      }
    },
    "output_format": { "content_format": "md", "include_metadata_sidecar": true },
    "output_structure": { "path_template": "{year}/{month}/{doc_id}/{name}.{ext}" }
  }
}
```

---

### SharePoint — export extracted markdown

```json
{
  "type": "storage_output",
  "name": "storage_output",
  "config": {
    "mode": "processed_content",
    "destination_config": {
      "provider": "sharepoint",
      "provider_config": {
        "drive_id": "${SHAREPOINT_DRIVE_ID}",
        "folder_path": "/Processed Documents",
        "create_dirs": true
      },
      "credentials": {
        "client_id": "${SHAREPOINT_CLIENT_ID}",
        "client_secret": "${SHAREPOINT_CLIENT_SECRET}",
        "tenant_id": "${SHAREPOINT_TENANT_ID}"
      }
    },
    "output_format": { "content_format": "md" },
    "output_structure": { "path_template": "{year}/{month}/{name}.{ext}" }
  }
}
```

### SharePoint — copy original files to archive

```json
{
  "type": "storage_output",
  "name": "storage_output",
  "config": {
    "mode": "refetch_original",
    "destination_config": {
      "provider": "sharepoint",
      "provider_config": {
        "drive_id": "${SHAREPOINT_DRIVE_ID}",
        "folder_path": "/Archive",
        "create_dirs": true
      },
      "credentials": {
        "client_id": "${SHAREPOINT_CLIENT_ID}",
        "client_secret": "${SHAREPOINT_CLIENT_SECRET}",
        "tenant_id": "${SHAREPOINT_TENANT_ID}"
      }
    },
    "output_structure": { "overwrite_existing": false }
  }
}
```

### SharePoint — full compliance export

```json
{
  "type": "storage_output",
  "name": "storage_output",
  "config": {
    "mode": "comprehensive_export",
    "destination_config": {
      "provider": "sharepoint",
      "provider_config": {
        "drive_id": "${SHAREPOINT_DRIVE_ID}",
        "folder_path": "/Compliance Archive",
        "create_dirs": true
      },
      "credentials": {
        "client_id": "${SHAREPOINT_CLIENT_ID}",
        "client_secret": "${SHAREPOINT_CLIENT_SECRET}",
        "tenant_id": "${SHAREPOINT_TENANT_ID}"
      }
    },
    "output_format": { "content_format": "md", "include_metadata_sidecar": true },
    "output_structure": { "path_template": "{year}/{month}/{doc_id}/{name}.{ext}" }
  }
}
```

---

### OneDrive — export extracted markdown

```json
{
  "type": "storage_output",
  "name": "storage_output",
  "config": {
    "mode": "processed_content",
    "destination_config": {
      "provider": "onedrive",
      "provider_config": {
        "drive_id": "${ONEDRIVE_DRIVE_ID}",
        "folder_path": "dest_files",
        "create_dirs": true
      },
      "credentials": {
        "tenant_id": "${ONEDRIVE_TENANT_ID}",
        "client_id": "${ONEDRIVE_CLIENT_ID}",
        "client_secret": "${ONEDRIVE_CLIENT_SECRET}"
      }
    },
    "output_format": { "content_format": "md" },
    "output_structure": { "type": "hierarchical" }
  }
}
```

### OneDrive — copy original files to archive

```json
{
  "type": "storage_output",
  "name": "storage_output",
  "config": {
    "mode": "refetch_original",
    "destination_config": {
      "provider": "onedrive",
      "provider_config": {
        "drive_id": "${ONEDRIVE_DRIVE_ID}",
        "folder_path": "dest_files",
        "create_dirs": true
      },
      "credentials": {
        "tenant_id": "${ONEDRIVE_TENANT_ID}",
        "client_id": "${ONEDRIVE_CLIENT_ID}",
        "client_secret": "${ONEDRIVE_CLIENT_SECRET}"
      }
    },
    "output_structure": { "type": "hierarchical" }
  }
}
```

### OneDrive — full compliance export

```json
{
  "type": "storage_output",
  "name": "storage_output",
  "config": {
    "mode": "comprehensive_export",
    "destination_config": {
      "provider": "onedrive",
      "provider_config": {
        "drive_id": "${ONEDRIVE_DRIVE_ID}",
        "folder_path": "dest_files",
        "create_dirs": true
      },
      "credentials": {
        "tenant_id": "${ONEDRIVE_TENANT_ID}",
        "client_id": "${ONEDRIVE_CLIENT_ID}",
        "client_secret": "${ONEDRIVE_CLIENT_SECRET}"
      }
    },
    "output_format": { "content_format": "txt", "include_metadata_sidecar": true },
    "output_structure": { "type": "hierarchical" }
  }
}
```

## Sample Flow Files

| Flow | Description |
|---|---|
| [`sample_flows/storage_output/filesystem/processed_content_filesystem.json`](../../../sample_flows/storage_output/filesystem/processed_content_filesystem.json) | Extract markdown → write to local filesystem |
| [`sample_flows/storage_output/filesystem/refetch_original_filesystem.json`](../../../sample_flows/storage_output/filesystem/refetch_original_filesystem.json) | Re-fetch originals → archive to local filesystem |
| [`sample_flows/storage_output/filesystem/comprehensive_export_filesystem.json`](../../../sample_flows/storage_output/filesystem/comprehensive_export_filesystem.json) | Full compliance export → local filesystem |
| [`sample_flows/storage_output/s3/processed_content_s3.json`](../../../sample_flows/storage_output/s3/processed_content_s3.json) | Extract markdown → write to S3 |
| [`sample_flows/storage_output/s3/refetch_original_s3.json`](../../../sample_flows/storage_output/s3/refetch_original_s3.json) | Archive originals from S3 source → S3 destination |
| [`sample_flows/storage_output/s3/comprehensive_export_s3.json`](../../../sample_flows/storage_output/s3/comprehensive_export_s3.json) | Full compliance export → S3 |
| [`sample_flows/storage_output/ibm_cos/processed_content_ibm_cos.json`](../../../sample_flows/storage_output/ibm_cos/processed_content_ibm_cos.json) | Extract markdown → write to IBM COS |
| [`sample_flows/storage_output/ibm_cos/refetch_original_ibm_cos.json`](../../../sample_flows/storage_output/ibm_cos/refetch_original_ibm_cos.json) | Archive originals from IBM COS source → IBM COS destination |
| [`sample_flows/storage_output/ibm_cos/comprehensive_export_ibm_cos.json`](../../../sample_flows/storage_output/ibm_cos/comprehensive_export_ibm_cos.json) | Full compliance export → IBM COS |
| [`sample_flows/storage_output/sharepoint/processed_content_sharepoint.json`](../../../sample_flows/storage_output/sharepoint/processed_content_sharepoint.json) | Extract markdown → write to SharePoint |
| [`sample_flows/storage_output/sharepoint/refetch_original_sharepoint.json`](../../../sample_flows/storage_output/sharepoint/refetch_original_sharepoint.json) | Archive originals from SharePoint source → SharePoint destination |
| [`sample_flows/storage_output/sharepoint/comprehensive_export_sharepoint.json`](../../../sample_flows/storage_output/sharepoint/comprehensive_export_sharepoint.json) | Full compliance export → SharePoint |
