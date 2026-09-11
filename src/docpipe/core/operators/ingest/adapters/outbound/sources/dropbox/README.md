# Dropbox Source Adapter

## Overview

The Dropbox source adapter ingests documents from a Dropbox account using the official [Dropbox Python SDK](https://github.com/dropbox/dropbox-sdk-python). Listing is metadata-only and paginated: binary content is downloaded on demand by downstream operators through `fetch_binary_content()`.

The adapter registers with `SourceAdapterFactory` under the provider name `dropbox`.

## Features

- Access-token and refresh-token (long-lived) OAuth2 authentication
- Cursor-based pagination over `files/list_folder`
- Recursive or single-level folder traversal
- Single-file ingestion by path or Dropbox file id
- File extension, file size, and glob exclusion filters
- `max_files` limit
- Lazy binary retrieval by stable Dropbox file id
- Environment variable resolution for credentials and paths

## Configuration

### Credentials

Provide **either** an access token **or** a refresh token together with the app key and secret.

| Parameter | Type | Description |
|-----------|------|-------------|
| `access_token` | string | Dropbox OAuth2 access token (short-lived or legacy long-lived token) |
| `refresh_token` | string | Dropbox OAuth2 refresh token; the SDK refreshes access tokens automatically |
| `app_key` | string | Dropbox app key, required with `refresh_token` |
| `app_secret` | string | Dropbox app secret, required with `refresh_token` |

### Connection Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `folder_path` | string | `""` | Folder to ingest from (e.g. `/Reports`). Empty string or `/` means the account root |
| `file_path` | string | `None` | Ingest a single file by path (`/Reports/q1.pdf`) or file id (`id:abc123`). Ignores folder settings and filters |
| `recursive` | boolean | `true` | Whether to traverse subfolders |
| `exclude_patterns` | list[string] | `[]` | Glob patterns excluded by full path or file name (e.g. `["*.tmp", "*/Archive/*"]`) |
| `max_file_size_mb` | integer | `None` | Maximum file size in MB. `None` means no limit |

File extensions come from the operator-level `include_filter`, and the document limit from the operator-level `max_files`.

## Authentication Setup

### 1. Create a Dropbox App

1. Go to the [Dropbox App Console](https://www.dropbox.com/developers/apps).
2. Create a new app, choose **Scoped access**, and pick either **App folder** (recommended, limits access to one folder) or **Full Dropbox**.
3. On the **Permissions** tab enable at least:
   - `account_info.read` — used by the connection test
   - `files.metadata.read` — listing files and folders
   - `files.content.read` — downloading file content
4. Click **Submit** to save the permissions.

### 2. Obtain a Token

For a quick start, generate a short-lived access token on the app's **Settings** tab (`Generated access token`).

For unattended pipelines, use the refresh-token flow so the SDK renews access tokens automatically:

1. Open the authorization URL in a browser, replacing `<APP_KEY>`:
   `https://www.dropbox.com/oauth2/authorize?client_id=<APP_KEY>&response_type=code&token_access_type=offline`
2. Approve access and copy the authorization code.
3. Exchange the code for a refresh token:

   ```bash
   curl -X POST https://api.dropboxapi.com/oauth2/token \
     -u "<APP_KEY>:<APP_SECRET>" \
     -d code="<AUTH_CODE>" \
     -d grant_type=authorization_code
   ```

### 3. Export the Credentials

```bash
export DROPBOX_ACCESS_TOKEN="<your-access-token>"  # pragma: allowlist secret
# or, for the refresh-token flow
export DROPBOX_REFRESH_TOKEN="<your-refresh-token>"  # pragma: allowlist secret
export DROPBOX_APP_KEY="<your-app-key>"
export DROPBOX_APP_SECRET="<your-app-secret>"  # pragma: allowlist secret
```

Reference them from the flow as `${DROPBOX_ACCESS_TOKEN}` — never inline a token in a flow file.

## Usage in Flow

### Access token

```json
{
  "type": "ingest_source",
  "name": "ingest",
  "config": {
    "provider": "dropbox",
    "connection_params": {
      "folder_path": "/Reports",
      "recursive": true
    },
    "credentials": {
      "access_token": "${DROPBOX_ACCESS_TOKEN}"
    },
    "include_filter": "pdf,docx",
    "max_files": 100
  }
}
```

### Refresh token with filters

```json
{
  "type": "ingest_source",
  "name": "ingest",
  "config": {
    "provider": "dropbox",
    "connection_params": {
      "folder_path": "/Reports/2026",
      "recursive": true,
      "max_file_size_mb": 50,
      "exclude_patterns": ["*.tmp", "*/Archive/*"]
    },
    "credentials": {
      "refresh_token": "${DROPBOX_REFRESH_TOKEN}",
      "app_key": "${DROPBOX_APP_KEY}",
      "app_secret": "${DROPBOX_APP_SECRET}"
    },
    "include_filter": "pdf,docx,txt",
    "max_files": 500
  }
}
```

### Single file

```json
{
  "type": "ingest_source",
  "name": "ingest",
  "config": {
    "provider": "dropbox",
    "connection_params": { "file_path": "/Reports/q1.pdf" },
    "credentials": { "access_token": "${DROPBOX_ACCESS_TOKEN}" }
  }
}
```

## Document Metadata

| Field | Description |
|-------|-------------|
| `id` | Dropbox file id (e.g. `id:abc123`), stable across renames and moves |
| `name` | File name |
| `source_url` | `https://www.dropbox.com/home/<path>` |
| `modified_time` | Dropbox `server_modified` timestamp |
| `created_time` | Dropbox `client_modified` timestamp |
| `metadata.source_id` | Dropbox file id used for on-demand binary retrieval |
| `metadata.path` | Full Dropbox display path |
| `metadata.relative_path` | Path relative to the configured `folder_path` |
| `metadata.rev` | Dropbox file revision |
| `metadata.content_hash` | Dropbox content hash |

## Dependencies

```bash
pip install dropbox
```

The `dropbox` package is declared in `pyproject.toml` and installed with the project.

## Troubleshooting

### `Dropbox authentication failed`

- The access token expired — short-lived tokens last four hours; switch to the refresh-token flow.
- The token belongs to a different app than the configured `app_key` / `app_secret`.
- The required scopes were added after the token was issued; re-issue the token after saving permissions.

### `Dropbox API error, check that '/Folder' exists and is readable`

- The path is case-insensitive but must exist; verify it in the Dropbox web UI.
- Apps created with **App folder** access see paths relative to their own app folder, not the account root.
- Use `""` (or `/`) for the account root — Dropbox rejects a literal `"/"` path in API calls, which the config normalizes for you.

### No documents ingested

- `include_filter` extensions are matched case-insensitively against the file suffix; check for files with no extension.
- `exclude_patterns` are matched against both the full display path and the file name.
- `recursive: false` lists only the immediate folder contents.

## See Also

- [Dropbox API documentation](https://www.dropbox.com/developers/documentation/http/documentation)
- [Dropbox Python SDK](https://dropbox-sdk-python.readthedocs.io/)
- [IngestSource operator documentation](../../../../../../../../../docs/operators/ingest/ingest_source_readme.md)
