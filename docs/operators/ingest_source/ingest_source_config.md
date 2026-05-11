# Ingest Source Operator - Configuration Reference

## Overview

The Ingest Source Operator provides a unified interface for ingesting documents from various cloud storage providers and sources. It uses LangChain loaders and custom adapters to support multiple providers through a single operator interface.

- **Operator Name:** `ingest_source`
- **Category**: Ingest
- **Short Name**: `ingest_source`

## Supported Providers

- **s3**: Amazon S3 and S3-compatible storage
- **ibm_cos**: IBM Cloud Object Storage
- **sharepoint**: Microsoft SharePoint (via Microsoft Graph API)
- **onedrive**: Microsoft OneDrive (via Microsoft Graph API)
- **google_drive**: Google Drive
- **filesystem**: Local filesystem (alternative to ingest_local)
- **web**: Web scraping and URL-based ingestion
- **custom**: Custom LangChain loaders via dynamic import

## Configuration Parameters

### 1. `provider` (String)
**Type:** String  
**Required:** Yes  
**Description:** Storage provider type. Determines which adapter to use for document ingestion.

**Valid Values:** `s3`, `ibm_cos`, `sharepoint`, `onedrive`, `google_drive`, `filesystem`, `web`, `custom`

**Examples:**
```json
"provider": "s3"
```

```json
"provider": "sharepoint"
```

### 2. `connection_params` (JSON)
**Type:** JSON Object  
**Required:** Yes  
**Description:** Provider-specific connection parameters. Structure varies by provider.

**S3 Example:**
```json
"connection_params": {
  "bucket": "my-documents",
  "prefix": "invoices/",
  "region": "us-east-1"
}
```

**SharePoint Example:**
```json
"connection_params": {
  "drive_id": "b!abc123...",
  "folder_path": "/Shared Documents/Reports"
}
```

**Google Drive Example:**
```json
"connection_params": {
  "folder_id": "1a2b3c4d5e6f",
  "recursive": true
}
```

### 3. `credentials` (JSON)
**Type:** JSON Object  
**Required:** Yes  
**Description:** Authentication credentials for the provider. Structure varies by provider.

**S3 Example:**
```json
"credentials": {
  "aws_access_key_id": "AKIA...",
  "aws_secret_access_key": "..."
}
```

**Microsoft (SharePoint/OneDrive) Example:**
```json
"credentials": {
  "client_id": "abc123...",
  "client_secret": "...",
  "tenant_id": "xyz789..."
}
```

**Google Drive Example:**
```json
"credentials": {
  "service_account_key": "/path/to/service-account.json"
}
```

### 4. `max_files` (Integer)
**Type:** Integer  
**Required:** No  
**Default:** `100`  
**Description:** Maximum number of files to ingest from the source.

**Examples:**
```json
"max_files": 500
```

### 5. `include_filter` (List)
**Type:** List (comma-separated string)  
**Required:** No  
**Description:** File extensions to include. Only files with these extensions will be processed.

**Examples:**
```json
"include_filter": "pdf,docx,xlsx"
```

### 6. `exclude_filter` (List)
**Type:** List (comma-separated string)  
**Required:** No  
**Description:** File extensions to exclude. Files with these extensions will be skipped.

**Examples:**
```json
"exclude_filter": "tmp,log,bak"
```

### 7. `force_ingest` (Boolean)
**Type:** Boolean  
**Required:** No  
**Default:** `false`  
**Description:** Force re-ingestion of previously processed documents. When false, documents are skipped if they haven't been modified.

**Examples:**
```json
"force_ingest": true
```

### 8. `ignore_hidden_files` (Boolean)
**Type:** Boolean  
**Required:** No  
**Default:** `true`  
**Description:** Skip files starting with '.' (hidden files).

**Examples:**
```json
"ignore_hidden_files": false
```

## Output Features

### `path` (String)
**Type:** String  
**Description:** The source identifier (URL, file path, etc.) for the document  
**Available for Filter:** Yes  
**Available for Vector DB:** No

### `binary_content` (Binary)
**Type:** Binary  
**Description:** The raw binary content of the document for downstream extraction operators  
**Available for Filter:** No  
**Available for Vector DB:** No

### `metadata` (String)
**Type:** String (JSON)  
**Description:** JSON-serialized metadata from the source document  
**Available for Filter:** Yes  
**Available for Vector DB:** No

### `source_id` (String)
**Type:** String  
**Description:** The source identifier (file path, URL, etc.)  
**Available for Filter:** Yes  
**Available for Vector DB:** No

### `doc_id_hash` (String)
**Type:** String  
**Description:** Hash ID of the document  
**Available for Vector DB:** Yes  
**Is Primary:** Yes  
**Tags:** `mandatory`, `primary`

## Provider-Specific Configuration

### S3 / IBM COS
```json
{
  "provider": "s3",
  "connection_params": {
    "bucket": "my-bucket",
    "prefix": "documents/",
    "region": "us-east-1",
    "endpoint_url": "https://s3.amazonaws.com"
  },
  "credentials": {
    "aws_access_key_id": "AKIA...",
    "aws_secret_access_key": "..."
  }
}
```

### SharePoint
```json
{
  "provider": "sharepoint",
  "connection_params": {
    "drive_id": "b!abc123...",
    "folder_path": "/Shared Documents",
    "recursive": true
  },
  "credentials": {
    "client_id": "app-id",
    "client_secret": "secret", # pragma: allowlist secret
    "tenant_id": "tenant-id"
  }
}
```

### OneDrive
```json
{
  "provider": "onedrive",
  "connection_params": {
    "drive_id": "b!xyz789...",
    "folder_path": "/Documents/Reports",
    "recursive": true
  },
  "credentials": {
    "client_id": "app-id",
    "client_secret": "secret", # pragma: allowlist secret
    "tenant_id": "tenant-id"
  }
}
```

### Google Drive
```json
{
  "provider": "google_drive",
  "connection_params": {
    "folder_id": "1a2b3c4d5e6f",
    "recursive": true
  },
  "credentials": {
    "service_account_key": "/path/to/credentials.json"
  }
}
```

### Web Scraping
```json
{
  "provider": "web",
  "connection_params": {
    "urls": [
      "https://example.com/page1",
      "https://example.com/page2"
    ],
    "recursive": false,
    "max_depth": 2
  },
  "credentials": {}
}
```

## Configuration Examples

### Example 1: S3 Ingestion
```json
{
  "id": "f1c9e4b7-2a6d-4a85-b3f2-7e0c9d1a5b6e",
  "operator": "ingest_source",
  "config": {
    "provider": "s3",
    "connection_params": {
      "bucket": "company-documents",
      "prefix": "invoices/2024/"
    },
    "credentials": {
      "aws_access_key_id": "AKIA...",
      "aws_secret_access_key": "..."
    },
    "max_files": 1000,
    "include_filter": "pdf,xlsx"
  }
}
```

### Example 2: SharePoint Ingestion
```json
{
  "id": "f1c9e4b7-2a6d-4a85-b3f2-7e0c9d1a5b6e",
  "operator": "ingest_source",
  "config": {
    "provider": "sharepoint",
    "connection_params": {
      "drive_id": "b!abc123...",
      "folder_path": "/Shared Documents/Contracts",
      "recursive": true
    },
    "credentials": {
      "client_id": "your-app-id",
      "client_secret": "your-secret", # pragma: allowlist secret
      "tenant_id": "your-tenant-id"
    },
    "include_filter": "docx,pdf",
    "force_ingest": false
  }
}
```

### Example 3: Google Drive Ingestion
```json
{
  "id": "f1c9e4b7-2a6d-4a85-b3f2-7e0c9d1a5b6e",
  "operator": "ingest_source",
  "config": {
    "provider": "google_drive",
    "connection_params": {
      "folder_id": "1a2b3c4d5e6f",
      "recursive": true
    },
    "credentials": {
      "service_account_key": "/secrets/gdrive-sa.json"
    },
    "max_files": 500,
    "ignore_hidden_files": true
  }
}
```

## Best Practices

1. **Credentials Security**: Store credentials in environment variables or secrets management systems
2. **Start Small**: Test with small `max_files` values before full ingestion
3. **Use Filters**: Leverage `include_filter` to process only relevant file types
4. **Incremental Updates**: Use `force_ingest: false` for efficient incremental processing
5. **Provider-Specific Limits**: Be aware of API rate limits for cloud providers
6. **Folder Paths**: Use absolute paths for `folder_path` parameters

## Validation Rules

- `provider` must be a supported provider type
- `connection_params` must contain provider-specific required fields
- `credentials` must contain valid authentication information
- `max_files` must be greater than 0
- File extensions in filters should not include the dot (use "pdf" not ".pdf")

## Complete Flow Example

- [Sample Flow](tests/sample_test_flows/invoice_processing/flow_invoice_k8s.json)
