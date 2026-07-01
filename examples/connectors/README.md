# Connector Test Scripts

This directory contains test scripts for various data source adapters (OneDrive, SharePoint, Google Drive, etc.).

## Setup

### Option 1: Using .env file (Recommended)

1. Copy the example environment file:
   ```bash
   cp examples/connectors/.env.example examples/connectors/.env
   ```

2. Edit `examples/connectors/.env` and fill in your credentials:
   ```bash
   # OneDrive Configuration
   ONEDRIVE_CLIENT_ID=your-actual-client-id
   ONEDRIVE_CLIENT_SECRET=your-actual-client-secret
   ONEDRIVE_TENANT_ID=your-actual-tenant-id
   ONEDRIVE_DRIVE_ID=your-drive-id
   ONEDRIVE_FOLDER_PATH=/Documents
   
   # SharePoint Configuration
   SHAREPOINT_CLIENT_ID=your-actual-client-id
   SHAREPOINT_CLIENT_SECRET=your-actual-client-secret
   SHAREPOINT_TENANT_ID=your-actual-tenant-id
   SHAREPOINT_SITE_URL=https://yourtenant.sharepoint.com/sites/yoursite
   SHAREPOINT_FOLDER_PATH=/Shared Documents
   ```

3. Install python-dotenv (if not already installed):
   ```bash
   pip install python-dotenv
   ```

4. Run the test scripts:
   ```bash
   python examples/connectors/test_onedrive_adapter.py
   python examples/connectors/test_sharepoint_adapter.py
   ```

### Option 2: Using Environment Variables

Set environment variables directly in your shell:

```bash
# OneDrive
export ONEDRIVE_CLIENT_ID='your-client-id'
export ONEDRIVE_CLIENT_SECRET='your-client-secret'  # pragma: allowlist secret
export ONEDRIVE_TENANT_ID='your-tenant-id'
python examples/connectors/test_onedrive_adapter.py

# SharePoint
export SHAREPOINT_CLIENT_ID='your-client-id'
export SHAREPOINT_CLIENT_SECRET='your-client-secret'  # pragma: allowlist secret
export SHAREPOINT_TENANT_ID='your-tenant-id'
export SHAREPOINT_DOCUMENT_LIBRARY_ID='your-document-library-id'
python examples/connectors/test_sharepoint_adapter.py
```

## Important Notes

- **Security**: The `.env` file is gitignored and should NEVER be committed to version control
- **Scope**: These environment variables are only for testing the connector scripts, NOT for the main pipeline
- **Pipeline Configuration**: The main docpipe pipeline uses credentials embedded in flow JSON files (see `sample_flows/use_cases/` for examples)

## Available Test Scripts

- `test_onedrive_adapter.py` - Test OneDrive connection and document fetching
- `test_sharepoint_adapter.py` - Test SharePoint connection and document fetching

Each script will:
1. Test the connection to the service
2. Fetch up to 10 documents from the configured location
3. Display document metadata (ID, name, size, URL, etc.)