# Google Drive Provider Setup

## Overview
The Google Drive provider allows you to ingest documents from Google Drive folders using OAuth 2.0 authentication.

## Prerequisites
1. Google Cloud Project with Drive API enabled
2. OAuth 2.0 credentials (client secret JSON file)
3. Python packages installed via: `uv pip install -e ".[google-drive]"` or `pip install -e ".[google-drive]"`

## Setup Steps

### 1. Create Google Cloud Project and Enable Drive API
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Drive API for your project
4. Go to "Credentials" and create OAuth 2.0 Client ID
5. Download the credentials JSON file

### 2. Install Dependencies

From the backend directory, install the Google Drive dependencies:

```bash
cd src/datasift_opensource/backend
uv pip install -e ".[google-drive]"
# or using pip
pip install -e ".[google-drive]"
```

This will install:
- `google-auth-oauthlib` - OAuth 2.0 authentication
- `google-auth-httplib2` - HTTP library for Google APIs
- `google-api-python-client` - Google Drive API client
- `pypdf2` - PDF processing
- `unstructured[pdf]` - Advanced PDF parsing with OCR support

### 3. Configure the Ingest Node

```python
node_config = {
    "provider": "google_drive",
    "connection_params": {
        "folder_id": "your-google-drive-folder-id",
        "recursive": False  # Optional: set to True to include subfolders
    },
    "credentials": {
        "credentials_json_path": "/path/to/client_secret.json",
        "token_path": "/path/to/token.json"  # Optional: defaults to ~/.credentials/token.json
    }
}
```

### 4. First-Time Authentication
On the first run, the application will:
1. Create the token directory if it doesn't exist (default: `~/.credentials/`)
2. Open a browser window for OAuth authentication
3. Save the access token to the specified token path
4. Use the saved token for subsequent requests

### 5. Token Management
- The token file stores OAuth access and refresh tokens
- Tokens are automatically refreshed when expired
- If authentication fails, delete the token file and re-authenticate

## Configuration Parameters

### connection_params
- `folder_id` (required): Google Drive folder ID or full URL
  - Example ID: `1DKN_mxnoW1Uaacghz8vyEeqw-j4IOSFK`
  - Example URL: `https://drive.google.com/drive/folders/1DKN_mxnoW1Uaacghz8vyEeqw-j4IOSFK`
- `recursive` (optional): Boolean, whether to include subfolders (default: False)

### credentials
- `credentials_json_path` (required): Path to OAuth client secret JSON file
- `token_path` (optional): Path to store OAuth tokens (default: `~/.credentials/token.json`)

## Troubleshooting

### Error: No such file or directory: '/Users/username/.credentials/token.json'
**Solution**: The token directory will be created automatically. Ensure you have write permissions to the parent directory.

### Error: Invalid credentials
**Solution**: 
1. Verify the credentials JSON file path is correct
2. Ensure the OAuth client is properly configured in Google Cloud Console
3. Delete the token file and re-authenticate

### Error: Access denied
**Solution**: 
1. Ensure the Google account has access to the specified folder
2. Check that the Drive API is enabled in your Google Cloud project
3. Verify OAuth scopes include Drive access

## Example Usage

```python
from datasift_opensource.backend.operators.universal.ingest_new import UserNode
import pyarrow as pa

# Configure the node
node_config = {
    "provider": "google_drive",
    "connection_params": {
        "folder_id": "1DKN_mxnoW1Uaacghz8vyEeqw-j4IOSFK",
        "recursive": True
    },
    "credentials": {
        "credentials_json_path": "/path/to/client_secret.json"
    }
}

# Create and execute the ingest node
ingest_node = UserNode(node_config)
input_table = pa.Table.from_arrays([])
output_tables, metadata = ingest_node.transform(input_table)

print(f"Ingested {metadata['count']} documents")
```

## Security Best Practices
1. Never commit credentials JSON files to version control
2. Store credentials in secure locations with restricted permissions
3. Use environment variables or secret management systems in production
4. Regularly rotate OAuth credentials
5. Limit OAuth scopes to minimum required permissions