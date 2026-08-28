# Box Source Adapter

## Overview

The Box source adapter enables ingesting documents from Box using LangChain's BoxLoader with JWT authentication. It provides automatic OAuth2 handling and supports recursive folder traversal with file filtering.

## Features

- JWT authentication with Box enterprise apps
- Recursive folder traversal
- File extension filtering
- File size limits
- Exclusion patterns for unwanted files
- Box-specific metadata (box_id, box_name, source_url)
- Environment variable resolution for credentials

## Configuration

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `credentials_path` | string | Path to Box JWT config file (supports env vars) |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `folder_id` | string | `"0"` | Box folder ID to start ingestion from. Default "0" is root folder |
| `recursive` | boolean | `true` | Whether to recursively traverse subdirectories |
| `file_extensions` | list[string] | `[]` | File extensions to include (e.g., `[".pdf", ".docx"]`). Empty means all files |
| `exclude_patterns` | list[string] | `[]` | Glob patterns to exclude (e.g., `["*.tmp", "Trash/*"]`) |
| `max_file_size_mb` | integer | `None` | Maximum file size in MB. None means no limit |

## Authentication Setup

### 1. Create Box App

1. Go to [Box Developer Console](https://app.box.com/developers/console)
2. Create a new Custom App
3. Choose "Server Authentication (with JWT)"
4. Configure OAuth 2.0 settings
5. Generate a public/private keypair
6. Download the JSON configuration file

### 2. Configure JWT File

The JWT config file should have this structure:

```json
{
  "boxAppSettings": {
    "clientID": "your_client_id",
    "clientSecret": "your_client_secret",  # pragma: allowlist secret
    "appAuth": {
      "publicKeyID": "your_key_id",
      "privateKey": "-----BEGIN ENCRYPTED PRIVATE KEY-----\n...\n-----END ENCRYPTED PRIVATE KEY-----\n",
      "passphrase": "<your-private-key-passphrase>"
    }
  },
  "enterpriseID": "your_enterprise_id"
}
```

### 3. Set Environment Variable

```bash
export BOX_JWT_CONFIG_FILE="/path/to/box-config.json"
```

## Environment Variable Resolution

The `credentials_path` supports multiple formats:

- **Environment variables**: `${BOX_JWT_CONFIG_FILE}` or `$BOX_JWT_CONFIG_FILE`
- **User home expansion**: `~/box/config.json`
- **Absolute paths**: `/etc/box/config.json`
- **Relative paths**: `./config/box.json`

Examples:
```json
{
  "credentials_path": "${BOX_JWT_CONFIG_FILE}"
}
```

```json
{
  "credentials_path": "~/.config/box/jwt-config.json"
}
```

## Usage in Flow

### Basic Configuration

```json
{
  "operator": "ingest_source",
  "config": {
    "provider": "box_driver",
    "connection_params": {
      "folder_id": "0",
      "recursive": true,
      "max_file_size_mb": 50
    },
    "credentials": {
      "credentials_json_path": "${BOX_JWT_CONFIG_FILE}"
    },
    "included_extensions": [".pdf", ".docx", ".txt"]
  }
}
```

### Advanced Configuration

```json
{
  "operator": "ingest_source",
  "config": {
    "provider": "box_driver",
    "connection_params": {
      "folder_id": "123456789",
      "recursive": true,
      "max_file_size_mb": 100,
      "exclude_patterns": ["*.tmp", "Trash/*", ".DS_Store"]
    },
    "credentials": {
      "credentials_json_path": "${BOX_JWT_CONFIG_FILE}"
    },
    "included_extensions": [".pdf", ".docx", ".pptx", ".xlsx", ".txt"],
    "max_files": 1000,
    "force_ingest": true
  }
}
```

## Output Schema

| Column | Type | Description |
|--------|------|-------------|
| `id` | string | Box file ID |
| `name` | string | File name |
| `source_url` | string | Box file URL (`https://app.box.com/file/{id}`) |
| `modified_time` | datetime | Last modification timestamp |
| `box_id` | string | Box file ID (metadata) |
| `box_name` | string | Box file name (metadata) |
| `mime_type` | string | File MIME type |
| `file_size` | integer | File size in bytes |

## Dependencies

```bash
pip install box_sdk_gen langchain-box
```

## Example Flow

For complete example pipelines using cloud source connectors, see `sample_flows/use_cases/`:
- Ingest from cloud sources (Box, S3, OneDrive, etc.)
- Extract with Docling
- Chunk with hybrid strategy
- Generate embeddings with Ollama
- Store in OpenSearch

## Troubleshooting

### Authentication Errors

**Problem**: `Failed to authenticate with Box`

**Solutions**:
- Verify JWT config file path is correct
- Check that the Box app has proper permissions
- Ensure the enterprise ID is correct
- Verify the private key and passphrase are valid

### File Access Errors

**Problem**: `Permission denied accessing credentials file`

**Solutions**:
- Check file permissions: `chmod 600 /path/to/box-config.json`
- On macOS, grant Terminal/Python access in System Preferences > Security & Privacy
- Verify the file exists at the specified path

### Environment Variable Not Resolved

**Problem**: Credentials path shows `${BOX_JWT_CONFIG_FILE}` literally

**Solutions**:
- Ensure environment variable is set: `echo $BOX_JWT_CONFIG_FILE`
- Export the variable in your shell: `export BOX_JWT_CONFIG_FILE="/path/to/config.json"`
- Add to `.env` file if using environment file loading

## See Also

- [Box Developer Documentation](https://developer.box.com/)
- [LangChain Box Integration](https://python.langchain.com/docs/integrations/document_loaders/box)
- [IngestSource Operator](../../../../../../../../../README.md)
