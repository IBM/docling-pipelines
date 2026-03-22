# Google Drive Source Adapter

A LangChain-based adapter for ingesting documents from Google Drive with automatic OAuth2 authentication and Google Workspace file export.

## Features

- **Automatic OAuth2 Authentication**: Built-in OAuth2 flow with token caching and refresh
- **Google Workspace Export**: Automatically exports Google Docs, Sheets, Slides, and Drawings to standard formats
- **Recursive Traversal**: Optionally traverse subdirectories
- **File Filtering**: Filter by file extensions and exclude patterns
- **Size Limits**: Optional maximum file size filtering
- **LangChain Integration**: Uses battle-tested `GoogleDriveLoader` from LangChain

## Quick Start

### Prerequisites

1. **Python 3.8+** with pip or uv
2. **Google Cloud Project** with Drive API enabled
3. **OAuth 2.0 Credentials** (Desktop application type)

### Step-by-Step Setup

#### 1. Install Dependencies

```bash
# Using uv (recommended)
cd src/datasift_opensource/backend
uv pip install langchain-google-community google-auth-oauthlib google-auth-httplib2
```

**Required packages:**
- `langchain-google-community` - LangChain's Google Drive integration
- `google-auth-oauthlib` - OAuth2 authentication flow
- `google-auth-httplib2` - HTTP transport for Google APIs

#### 2. Create Google Cloud Credentials

**Important**: You must create OAuth 2.0 credentials before running the adapter.

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Drive API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Drive API"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop app" as application type
   - Name it (e.g., "DataSift Google Drive Connector")
   - Click "Create"
5. Download the credentials:
   - Click the download icon next to your new OAuth client
   - Save as `credentials.json` in your working directory

#### 3. Get Your Folder ID

To ingest documents from a specific folder:

1. Open the folder in Google Drive web interface
2. Copy the folder ID from the URL:
   ```
   https://drive.google.com/drive/folders/1ABC123xyz...
                                            ^^^^^^^^^^^
                                            This is your folder_id
   ```

#### 4. Set Environment Variables

```bash
export GOOGLE_DRIVE_FOLDER_ID='1ABC123xyz...'  # Your folder ID from step 3
export GOOGLE_DRIVE_CREDENTIALS_PATH='credentials.json'  # Path to credentials file
```

#### 5. Run the Test Script

```bash
cd src/datasift_opensource/backend
export PYTHONPATH="$(pwd):${PYTHONPATH}"
python -m core.operators.universal.ingest.adapters.outbound.sources.google_drive.adapter
```

**First Run**: A browser window will open for OAuth2 authentication. After granting access, the token will be cached in `token.json` for future use.

## Usage

### Testing the Adapter

The adapter includes a built-in test script:

```bash
# Set environment variables
export GOOGLE_DRIVE_FOLDER_ID='your-folder-id-here'
export GOOGLE_DRIVE_CREDENTIALS_PATH='path/to/credentials.json'  # Optional, defaults to credentials.json
export GOOGLE_DRIVE_TOKEN_PATH='path/to/token.json'  # Optional, defaults to token.json

# Run the test
cd src/datasift_opensource/backend
python -m core.operators.universal.ingest.adapters.outbound.sources.google_drive.adapter
```

**First Run**: The script will open a browser for OAuth2 authentication. After granting access, the token will be cached for future use.

### Finding Folder ID

To get a Google Drive folder ID:
1. Open the folder in Google Drive web interface
2. Copy the ID from the URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`

### Configuration Example

```python
from .config import GoogleDriveSourceConfig

config = GoogleDriveSourceConfig(
    credentials_path="~/.config/google/credentials.json",
    token_path="~/.config/google/token.json",
    folder_id="1ABC123xyz...",  # Optional, None = root folder
    recursive=True,
    file_extensions=[".pdf", ".docx", ".txt"],
    exclude_patterns=["*.tmp", "Trash/*"],
    max_file_size_mb=100,
)
```

### Using in Code

```python
from .adapter import GoogleDriveSourceAdapter
from .config import GoogleDriveSourceConfig

# Create configuration
config = GoogleDriveSourceConfig(
    credentials_path="credentials.json",
    folder_id="your-folder-id",
    recursive=True,
)

# Create adapter
adapter = GoogleDriveSourceAdapter()

# Test connection
success, message = await adapter.test_connection(config)
print(f"Connection: {message}")

# Fetch documents
async for document in adapter.fetch_documents(config):
    print(f"Document: {document.name} ({len(document.content)} bytes)")
```

### Using in Flow Configuration

```json
{
  "nodes": [
    {
      "id": "ingest_gdrive",
      "operator_type": "datasift_opensource.backend.core.operators.universal.ingest.IngestSourceOperator",
      "operator_params": {
        "source_type": "google_drive",
        "source_config": {
          "credentials_path": "credentials.json",
          "folder_id": "your-folder-id",
          "recursive": true,
          "file_extensions": [".pdf", ".docx"]
        }
      }
    }
  ]
}
```

## Configuration Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `credentials_path` | str | Yes | - | Path to OAuth credentials JSON |
| `token_path` | str | No | Same dir as credentials | Path to store OAuth token |
| `drive_id` | str | No | None | Specific Drive ID (for shared drives) |
| `folder_id` | str | No | None | Folder ID to start from (None = root) |
| `folder_path` | str | No | None | Folder path (alternative to folder_id) |
| `recursive` | bool | No | True | Traverse subdirectories |
| `file_extensions` | List[str] | No | [] | File extensions to include (empty = all) |
| `exclude_patterns` | List[str] | No | [] | Glob patterns to exclude |
| `max_file_size_mb` | int | No | None | Maximum file size in MB (None = no limit) |
| `scopes` | List[str] | No | drive.readonly | OAuth scopes |

## Google Workspace File Export

The adapter automatically exports Google Workspace files to standard formats:

| Google Format | Export Format |
|---------------|---------------|
| Google Docs | PDF |
| Google Sheets | XLSX |
| Google Slides | PDF |
| Google Drawings | PDF |

## Troubleshooting

### "Your default credentials were not found"

**Error Message**:
```
Connection test failed: Your default credentials were not found.
To set up Application Default Credentials, see https://cloud.google.com/docs/authentication/external/set-up-adc
```

**Root Cause**:
This error occurs when the adapter cannot find valid OAuth2 credentials. The `langchain-google-community` library (v3.x) requires proper OAuth2 credentials to be configured.

**Solution**:
1. **Ensure you have created OAuth2 credentials** (not Service Account credentials):
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Navigate to "APIs & Services" > "Credentials"
   - Create "OAuth client ID" with type "Desktop app"
   - Download the credentials JSON file

2. **Install required authentication packages**:
   ```bash
   cd src/datasift_opensource/backend
   uv pip install google-auth-oauthlib google-auth-httplib2
   ```

3. **Set the credentials path**:
   ```bash
   export GOOGLE_DRIVE_CREDENTIALS_PATH='/path/to/your/credentials.json'
   ```

4. **Run the test** - it will open a browser for OAuth authentication:
   ```bash
   python -m core.operators.universal.ingest.adapters.outbound.sources.google_drive.adapter
   ```

5. **After first authentication**, a `token.json` file will be created and cached for future use

### "Credentials file does not exist"

**Solution**:
- Verify the path to `credentials.json` is correct
- Use absolute path or expand `~` manually:
  ```bash
  export GOOGLE_DRIVE_CREDENTIALS_PATH="$HOME/.config/google/credentials.json"
  ```

### "Connection test failed: invalid_grant"

**Solution**:
- Delete `token.json` and re-authenticate:
  ```bash
  rm token.json
  ```
- Verify credentials are for "Desktop application" type (not "Web application")
- Check that the Google Cloud project has Drive API enabled

### "Connection test failed: insufficient permissions"

**Solution**:
- Verify OAuth scopes include `drive.readonly`
- Delete `token.json` and re-authenticate after changing scopes
- Check that the OAuth consent screen is configured correctly

### "No documents found"

**Solution**:
- Verify `folder_id` is correct (copy from Drive URL)
- Check that folder contains files matching `file_extensions` filter
- Ensure the OAuth account has access to the folder
- Try with `recursive=True` to search subdirectories

### "ImportError: No module named 'google_auth_oauthlib'"

**Solution**:
```bash
cd src/datasift_opensource/backend
uv pip install google-auth-oauthlib google-auth-httplib2
```

### "ImportError: No module named 'langchain_google_community'"

**Solution**:
```bash
cd src/datasift_opensource/backend
uv pip install langchain-google-community
```

### File Type Filtering Issues

**Note**: In `langchain-google-community` v3.x, the `file_types` parameter expects Google Drive MIME types, not file extensions:
- `.pdf` → `'pdf'`
- `.docx`, `.doc` → `'document'`
- `.xlsx`, `.xls` → `'sheet'`
- `.pptx`, `.ppt` → `'presentation'`

The adapter automatically converts common file extensions to the appropriate MIME types.

## Performance Considerations

- **Large Folders**: Use `file_extensions` to filter unnecessary files
- **File Size**: Set `max_file_size_mb` to skip large files
- **Recursive Traversal**: Disable `recursive` for shallow scans
- **Rate Limiting**: LangChain handles Google API rate limits automatically

## Architecture

This adapter follows the Hexagonal Architecture pattern:

```
Domain Layer (models.py)
    ↑
Port Interface (document_source.py)
    ↑
Adapter Implementation (adapter.py)
    ↑
External Service (Google Drive via LangChain)
```

## Version History

- **2.0.1**: Fixed authentication for langchain-google-community v3.x
  - Added OAuth2 credential handling with `google-auth-oauthlib`
  - Fixed file type filtering to use MIME types instead of extensions
  - Added automatic token caching and refresh
- **2.0.0**: Refactored to use LangChain's GoogleDriveLoader (73% code reduction)
- **1.0.0**: Initial implementation with direct Google API calls

## References

- [LangChain GoogleDriveLoader](https://python.langchain.com/docs/integrations/document_loaders/google_drive)
- [Google Drive API](https://developers.google.com/drive/api/v3/about-sdk)
- [OAuth 2.0 for Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app)