# IngestLangchainOperator - Package Dependencies Validation

## Summary
All Python packages required for the `IngestLangchainOperator` have been validated and are now properly configured in the project.

## Changes Made

### 1. Updated `pyproject.toml`
Added missing core dependencies and reorganized LangChain packages:
- `langchain-core==1.2.14` - Pinned version for base Document class (core dependency)
- `langchain-community>=0.3.0` - Moved to optional dependencies (provider-specific)
- `pandas>=2.0.0` - Used for data manipulation and display

### 2. Dependency Categories

#### Core Dependencies (Always Installed)
```toml
[project]
dependencies = [
    "langchain-core==1.2.14",      # Pinned version for stability
    "pandas>=2.0.0",               # Data manipulation
    "pyarrow==16.1.0",
    "requests==2.32.5",
    "python-dotenv==1.2.1",
    "pyyaml==6.0.3",
    "fastapi==0.128.8",
    "uvicorn[standard]==0.40.0",
    "pydantic==2.12.5",
    "pydantic-settings==2.12.0",
    "docling[vlm]",
]
```

**Note:** `langchain-community` is now an optional dependency, installed only when specific cloud providers are needed.

#### Optional Dependencies (Provider-Specific)

**AWS/S3 Support:**
```toml
[project.optional-dependencies]
aws = [
    "boto3>=1.28.0",
    "langchain-community>=0.3.0",  # Required for S3 loaders
]
```

**Google Drive Support:**
```toml
google-drive = [
    "google-auth-oauthlib>=1.0.0",
    "google-auth-httplib2>=0.1.0",
    "google-api-python-client>=2.0.0",
    "pypdf2>=3.0.0",
    "unstructured[pdf]>=0.10.0",
    "langchain-community>=0.3.0",  # Required for GoogleDriveLoader
]
```

**Microsoft (SharePoint/OneDrive) Support:**
```toml
microsoft = [
    "O365>=2.0.0",
    "langchain-community>=0.3.0",  # Required for SharePoint/OneDrive loaders
]
```

**All Cloud Providers:**
```toml
all-cloud = [
    "boto3>=1.28.0",
    "google-cloud-storage>=2.10.0",
    "azure-storage-blob>=12.19.0",
    "google-auth-oauthlib>=1.0.0",
    "google-auth-httplib2>=0.1.0",
    "google-api-python-client>=2.0.0",
    "pypdf2>=3.0.0",
    "unstructured[pdf]>=0.10.0",
    "O365>=2.0.0",
    "langchain-community>=0.3.0",  # Required for all loaders
]
```

## Installation Instructions

### Basic Installation (Core Dependencies Only)
```bash
cd src/datasift_opensource/backend
uv sync
```

**Note:** Basic installation includes `langchain-core` but NOT `langchain-community`. You must install provider-specific extras to use the IngestLangchainOperator.

### With Specific Provider Support
```bash
# AWS/S3 only
uv sync --extra aws

# Google Drive only
uv sync --extra google-drive

# Microsoft (SharePoint/OneDrive) only
uv sync --extra microsoft

# All cloud providers
uv sync --extra all-cloud
```

## Validation Results

### ✅ Core Packages (Always Available)
- `langchain_core==1.2.14` - Base Document class (pinned version)
- `pandas>=2.0.0` - Data manipulation
- `pyarrow==16.1.0` - Arrow table support
- `json`, `importlib`, `os` - Standard library

### ✅ Provider-Specific Packages (Optional)
- `langchain_community>=0.3.0` - Document loaders (installed with provider extras)

### ✅ AWS/S3 Packages
- `boto3` - AWS SDK
- `botocore` - AWS core functionality

### ✅ Microsoft Packages
- `O365` - SharePoint and OneDrive support

### ✅ Google Drive Packages
- `google.oauth2` - OAuth authentication
- `googleapiclient` - Google API client

### ✅ LangChain Loaders
All required loaders are available:
- `S3DirectoryLoader` - Load from S3 directories
- `S3FileLoader` - Load individual S3 files
- `SharePointLoader` - Load from SharePoint
- `OneDriveLoader` - Load from OneDrive
- `GoogleDriveLoader` - Load from Google Drive
- `Document` - Base document class

## Supported Providers

The `IngestLangchainOperator` supports the following providers with all dependencies validated:

1. **Amazon S3** (`provider: 's3'`)
   - Requires: `uv sync --extra aws`
   - Installs: `boto3`, `langchain-community`
   
2. **IBM Cloud Object Storage** (`provider: 'ibm_cos'`)
   - Requires: `uv sync --extra aws` (S3-compatible)
   - Installs: `boto3`, `langchain-community`
   
3. **Microsoft SharePoint** (`provider: 'sharepoint'`)
   - Requires: `uv sync --extra microsoft`
   - Installs: `O365`, `langchain-community`
   
4. **Microsoft OneDrive** (`provider: 'onedrive'`)
   - Requires: `uv sync --extra microsoft`
   - Installs: `O365`, `langchain-community`
   
5. **Google Drive** (`provider: 'google_drive'`)
   - Requires: `uv sync --extra google-drive`
   - Installs: Google auth packages, `langchain-community`
   
6. **Custom Loaders** (`provider: 'custom'`)
   - Requires: User-provided loader class
   - May need additional dependencies based on custom loader

## Notes

- `langchain-core` is pinned to version `1.2.14` for stability
- `langchain-community` is only installed when provider-specific extras are used
- The `botocore` package is automatically installed as a dependency of `boto3`
- Standard library modules (`json`, `importlib`, `os`) are always available
- For production use, install with `uv sync --extra all-cloud` to support all providers
- The operator uses dynamic imports for custom loaders, allowing extensibility

## Testing

To verify the installation with all providers:
```bash
cd src/datasift_opensource/backend

# Verify core packages
.venv/bin/python -c "import langchain_core; import pandas; print(f'✓ Core: langchain-core {langchain_core.__version__}, pandas installed')"

# Verify loaders (requires --extra all-cloud)
.venv/bin/python -c "from langchain_community.document_loaders import S3DirectoryLoader, GoogleDriveLoader; print('✓ All loaders available')"
```

## Related Files
- [`ingest_langchain_loader.py`](../../src/datasift_opensource/backend/operators/universal/ingest/ingest_langchain_loader.py) - Operator implementation
- [`pyproject.toml`](../../src/datasift_opensource/backend/pyproject.toml) - Dependency configuration
- [`ingest_langchain_loader.md`](ingest_langchain_loader.md) - Operator documentation