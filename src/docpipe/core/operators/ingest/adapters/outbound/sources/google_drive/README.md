# Google Drive Source Adapter

A Google Drive API-based adapter for ingesting documents from Google Drive with OAuth2 or Service Account authentication and Google Workspace file export.

## Features

- **OAuth2 Authentication**: Built-in OAuth2 flow with token caching and refresh (for user access)
- **Service Account Authentication**: Non-interactive server-to-server authentication (for automated workflows)
- **Google Workspace Export**: Automatically exports Google Docs, Sheets, Slides, and Drawings to standard formats
- **Recursive Traversal**: Optionally traverse subdirectories
- **File Filtering**: Filter by file extensions and exclude patterns
- **Size Limits**: Optional maximum file size filtering
- **Lazy Loading**: Efficient metadata-first approach with on-demand binary content fetching

## Quick Start

### Prerequisites

1. **Python 3.8+** with pip or uv
2. **Google Cloud Project** with Drive API enabled
3. **Authentication Credentials** (choose one):
   - **OAuth 2.0 Credentials** (Desktop application type) - for user access
   - **Service Account JSON** - for server-to-server access

### Step-by-Step Setup

#### 1. Install Dependencies

```bash
# Using uv (recommended, from project root)
uv pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
```

**Required packages:**
- `google-api-python-client` - Google Drive API client
- `google-auth-oauthlib` - OAuth2 authentication flow
- `google-auth-httplib2` - HTTP transport for Google APIs

#### 2. Create Google Cloud Credentials

Choose one of the following authentication methods:

##### Option A: OAuth 2.0 Credentials (User Access)

**Use when**: You need to access files in a user's personal Google Drive.

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
   - Name it (e.g., "Docling Pipelines Google Drive Connector")
   - Click "Create"
5. Download the credentials:
   - Click the download icon next to your new OAuth client
   - Save as `credentials.json` in your working directory

##### Option B: Service Account (Server-to-Server Access)

**Use when**: You need automated, non-interactive access to shared drives or specific folders.

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Drive API** (same as above)
4. Create Service Account:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "Service Account"
   - Name it (e.g., "docpipe-gdrive-service")
   - Click "Create and Continue"
   - Skip optional steps and click "Done"
5. Create and download key:
   - Click on the created service account
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key"
   - Choose "JSON" format
   - Click "Create" - the key file will download automatically
   - Save as `service-account.json` in your working directory
6. **Grant access to folders**:
   - Copy the service account email (e.g., `docpipe-gdrive-service@project-id.iam.gserviceaccount.com`)
   - In Google Drive, share the folder(s) you want to access with this email address
   - Grant "Viewer" or "Editor" permissions as needed

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

**For OAuth 2.0:**
```bash
export GOOGLE_DRIVE_FOLDER_ID='1ABC123xyz...'  # Your folder ID from step 3
export GOOGLE_DRIVE_CREDENTIALS_PATH='credentials.json'  # Path to OAuth credentials file
```

**For Service Account:**
```bash
export GOOGLE_DRIVE_FOLDER_ID='1ABC123xyz...'  # Your folder ID from step 3
export GOOGLE_DRIVE_SERVICE_ACCOUNT_PATH='service-account.json'  # Path to service account JSON
```

#### 5. Run the Test Script

```bash
# From project root
source .venv/bin/activate
python -m docpipe.core.operators.ingest.adapters.outbound.sources.google_drive.adapter
```

**OAuth First Run**: A browser window will open for authentication. After granting access, the token will be cached in `token.json` for future use.

**Service Account**: No browser interaction needed - authentication is automatic.

## Usage

### Testing the Adapter

The adapter includes a built-in test script:

**OAuth 2.0:**
```bash
# Set environment variables
export GOOGLE_DRIVE_FOLDER_ID='your-folder-id-here'
export GOOGLE_DRIVE_CREDENTIALS_PATH='path/to/credentials.json'
export GOOGLE_DRIVE_TOKEN_PATH='path/to/token.json'  # Optional

# Run the test from project root
source .venv/bin/activate
python -m docpipe.core.operators.ingest.adapters.outbound.sources.google_drive.adapter
```

**Service Account:**
```bash
# Set environment variables
export GOOGLE_DRIVE_FOLDER_ID='your-folder-id-here'
export GOOGLE_DRIVE_SERVICE_ACCOUNT_PATH='path/to/service-account.json'

# Run the test from project root
source .venv/bin/activate
python -m docpipe.core.operators.ingest.adapters.outbound.sources.google_drive.adapter
```

**First Run (OAuth)**: The script will open a browser for authentication. After granting access, the token will be cached for future use.

**Service Account**: No browser interaction - authentication is automatic.

### Finding Folder ID

To get a Google Drive folder ID:
1. Open the folder in Google Drive web interface
2. Copy the ID from the URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`

### Configuration Examples

**OAuth 2.0:**
```python
from .config import GoogleDriveSourceConfig

config = GoogleDriveSourceConfig(
    credentials_path="~/.config/google/credentials.json",
    token_path="~/.config/google/token.json",
    folder_id="1ABC123xyz...",
    recursive=True,
    file_extensions=[".pdf", ".docx", ".txt"],
    exclude_patterns=["*.tmp", "Trash/*"],
    max_file_size_mb=100,
)
```

**Service Account:**
```python
from .config import GoogleDriveSourceConfig

config = GoogleDriveSourceConfig(
    service_account_json_path="~/.config/google/service-account.json",
    folder_id="1ABC123xyz...",
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

**OAuth 2.0:**
```json
{
  "nodes": [
    {
      "id": "ingest_gdrive",
      "operator_type": "docpipe.core.operators.ingest.ingest_source.IngestSourceOperator",
      "operator_params": {
        "provider": "google_drive",
        "connection_params": {
          "folder_id": "${GOOGLE_DRIVE_FOLDER_ID}",
          "recursive": true
        },
        "credentials": {
          "credentials_json_path": "${GOOGLE_DRIVE_CREDENTIALS_PATH}",
          "_comment": "For the first run, run the flow without token_path. After authentication, add the token_path as an env variable and export it and add the field below for future use.",
          "token_path": "${GOOGLE_DRIVE_TOKEN_PATH}"
        },
        "included_extensions": [".pdf", ".docx"]
      }
    }
  ]
}
```

**Service Account:**
```json
{
  "nodes": [
    {
      "id": "ingest_gdrive",
      "operator_type": "docpipe.core.operators.ingest.ingest_source.IngestSourceOperator",
      "operator_params": {
        "provider": "google_drive",
        "connection_params": {
          "folder_id": "${GOOGLE_DRIVE_FOLDER_ID}",
          "recursive": true
        },
        "credentials": {
          "service_account_json_path": "${GOOGLE_DRIVE_SERVICE_ACCOUNT_PATH}"
        },
        "included_extensions": [".pdf", ".docx"]
      }
    }
  ]
}
```

## Configuration Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `credentials_path` | str | Conditional* | - | Path to OAuth credentials JSON (for OAuth) |
| `token_path` | str | No | Same dir as credentials | Path to store OAuth token (OAuth only) |
| `service_account_json_path` | str | Conditional* | - | Path to Service Account JSON (for Service Account) |
| `drive_id` | str | No | None | Specific Drive ID (for shared drives) |
| `folder_id` | str | No | None | Folder ID to start from (None = root) |
| `folder_path` | str | No | None | Folder path (alternative to folder_id) |
| `recursive` | bool | No | True | Traverse subdirectories |
| `file_extensions` | List[str] | No | [] | File extensions to include (empty = all) |
| `exclude_patterns` | List[str] | No | [] | Glob patterns to exclude |
| `max_file_size_mb` | int | No | None | Maximum file size in MB (None = no limit) |
| `scopes` | List[str] | No | drive.readonly | OAuth/Service Account scopes |

\* Either `credentials_path` (OAuth) or `service_account_json_path` (Service Account) must be provided, but not both.

## Google Workspace File Export

The adapter automatically exports Google Workspace files to standard formats:

| Google Format | Export Format |
|---------------|---------------|
| Google Docs | PDF |
| Google Sheets | XLSX |
| Google Slides | PDF |
| Google Drawings | PDF |

## Authentication Methods Comparison

| Feature | OAuth 2.0 | Service Account |
|---------|-----------|-----------------|
| **Use Case** | User's personal Drive | Automated workflows, shared drives |
| **Setup Complexity** | Medium | Medium |
| **Browser Required** | Yes (first time) | No |
| **Token Refresh** | Automatic | Not needed |
| **Access Scope** | User's files only | Shared folders only |
| **Best For** | Interactive use, personal files | CI/CD, scheduled jobs, team folders |

## Troubleshooting

### "Your default credentials were not found"

**Error Message**:
```
Connection test failed: Your default credentials were not found.
To set up Application Default Credentials, see https://cloud.google.com/docs/authentication/external/set-up-adc
```

**Root Cause**:
This error occurs when the adapter cannot find valid OAuth2 credentials. The Google Drive API requires proper OAuth2 credentials to be configured.

**Solution**:
1. **Ensure you have created OAuth2 credentials** (not Service Account credentials):
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Navigate to "APIs & Services" > "Credentials"
   - Create "OAuth client ID" with type "Desktop app"
   - Download the credentials JSON file

2. **Install required authentication packages**:
   ```bash
   # From project root
   uv pip install google-auth-oauthlib google-auth-httplib2
   ```

3. **Set the credentials path**:
   ```bash
   export GOOGLE_DRIVE_CREDENTIALS_PATH='/path/to/your/credentials.json'
   ```

4. **Run the test** - it will open a browser for OAuth authentication:
   ```bash
   python -m core.operators.ingest.adapters.outbound.sources.google_drive.adapter
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
- **OAuth**: Ensure the OAuth account has access to the folder
- **Service Account**: Ensure the folder is shared with the service account email
- Try with `recursive=True` to search subdirectories

### Service Account: "insufficient permissions" or "File not found"

**Solution**:
- Verify the folder is shared with the service account email
- Check that the service account has at least "Viewer" permissions
- Ensure the folder ID is correct
- For shared drives, verify the service account has access to the shared drive

### "ImportError: No module named 'google_auth_oauthlib'"

**Solution**:
```bash
# From project root
uv pip install google-auth-oauthlib google-auth-httplib2
```

### "ImportError: No module named 'googleapiclient'"

**Solution**:
```bash
# From project root
uv pip install google-api-python-client
```

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

- **3.0.0**: Removed LangChain dependency, using Google Drive API directly
  - Cleaner implementation with direct Google Drive API calls
  - Removed unnecessary LangChain dependencies
  - Improved lazy loading for better performance
  - Maintained all authentication features (OAuth2 and Service Account)
- **2.1.0**: Added Service Account authentication support
  - Support for both OAuth 2.0 and Service Account authentication
  - Non-interactive authentication for automated workflows
- **2.0.0**: Initial LangChain-based implementation
- **1.0.0**: Initial implementation with direct Google API calls

## References

- [Google Drive API](https://developers.google.com/drive/api/v3/about-sdk)
- [OAuth 2.0 for Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Service Account Authentication](https://developers.google.com/identity/protocols/oauth2/service-account)
