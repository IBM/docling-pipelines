# IngestLangchainOperator - Package Dependencies Validation

## Summary
All Python packages required for the `IngestLangchainOperator` have been validated and are now properly configured in the project.

## Changes Made

### 1. Updated `pyproject.toml`
Added missing core dependencies and reorganized LangChain packages:
- `langchain==1.2.10` - Main LangChain package (core dependency)
- `langchain-core==1.2.14` - Pinned version for base Document class (core dependency)
- `langchain-community==0.4.1` - Moved to optional dependencies (provider-specific)
- `pandas==2.3.3` - Used for data manipulation and display

### 2. Dependency Categories

#### Core Dependencies (Always Installed)
```toml
[project]
dependencies = [
    "requests==2.32.5",
    "python-dotenv==1.2.1",
    "pyyaml==6.0.3",
    "fastapi==0.128.8",
    "uvicorn[standard]==0.40.0",
    "pydantic==2.12.5",
    "pydantic-settings==2.12.0",
    "docling[vlm]",
    "pyarrow==17.0.0",
    "urllib3==2.6.3",
    "botocore==1.42.55",
    "data-prep-toolkit-transforms==1.1.7",
    "filelock==3.20.3",
    "ibm-cos-sdk==2.14.3",
    "langdetect==1.0.9",
    "langchain==1.2.10",
    "langchain-core==1.2.14",
    "pandas==2.3.3",
    "prefect==3.4.23",
    "pyiceberg[glue]==0.9.1",
    "pyiceberg-core==0.7.0",
    "pypdf==6.7.1",
    "sqlglot==27.13.2",
    "tabulate==0.9.0",
    "toml==0.10.2",
    "pillow==12.1.1",
    "mlx==0.30.6",
    "orjson==3.11.7"
]
```

**Note:** `langchain-community` is now an optional dependency, installed only when specific cloud providers are needed.

#### Optional Dependencies (Provider-Specific)

**AWS/S3 Support:**
```toml
[project.optional-dependencies]
aws = [
    "boto3==1.42.55",
    "langchain-community==0.4.1",  # Required for S3 loaders
]
```

**Google Drive Support:**
```toml
google-drive = [
    "google-auth-oauthlib==1.2.4",
    "google-auth-httplib2==0.3.0",
    "google-api-python-client==2.190.0",
    "pypdf2==3.0.1",
    "unstructured[pdf]>=0.10.0",
    "langchain-google-community==3.0.5",  # Required for GoogleDriveLoader
]
```

**Microsoft (SharePoint/OneDrive) Support:**
```toml
microsoft = [
    "O365==2.1.9",  # For SharePoint and OneDrive
    "langchain-community==0.4.1",  # Required for SharePoint/OneDrive loaders
]
```

**All Cloud Providers:**
```toml
all-cloud = [
    "boto3==1.42.55",
    "google-cloud-storage==3.9.0",
    "azure-storage-blob==12.28.0",
    "google-auth-oauthlib==1.2.4",
    "google-auth-httplib2==0.3.0",
    "google-api-python-client==2.190.0",
    "pypdf2==3.0.1",
    "unstructured[pdf]>=0.10.0",
    "O365==2.1.9",
    "langchain-community==0.4.1",
    "langchain-google-community==3.0.5",
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
- `langchain==1.2.10` - Main LangChain package
- `langchain_core==1.2.14` - Base Document class (pinned version)
- `pandas==2.3.3` - Data manipulation
- `pyarrow==17.0.0` - Arrow table support
- `botocore==1.42.55` - AWS core functionality (included in core)
- `json`, `importlib`, `os` - Standard library

### ✅ Provider-Specific Packages (Optional)
- `langchain_community==0.4.1` - Document loaders (installed with provider extras)

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
- `S3DirectoryLoader` - Load from S3 directories (from `langchain-community`)
- `S3FileLoader` - Load individual S3 files (from `langchain-community`)
- `SharePointLoader` - Load from SharePoint (from `langchain-community`)
- `OneDriveLoader` - Load from OneDrive (from `langchain-community`)
- `GoogleDriveLoader` - Load from Google Drive (from `langchain-google-community`)
- `Document` - Base document class (from `langchain-core`)

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
   - Installs: Google auth packages, `langchain-google-community`
   
6. **Custom Loaders** (`provider: 'custom'`)
   - Requires: User-provided loader class
   - May need additional dependencies based on custom loader

## Notes

- `langchain` is pinned to version `1.2.10` for stability
- `langchain-core` is pinned to version `1.2.14` for stability
- `langchain-community` is only installed when provider-specific extras are used
- The `botocore==1.42.55` package is included in core dependencies
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
.venv/bin/python -c "from langchain_community.document_loaders import S3DirectoryLoader; from langchain_google_community import GoogleDriveLoader; print('✓ All loaders available')"
```

## Related Files
- [`ingest_langchain_loader.py`](../../src/datasift_opensource/backend/core/operators/universal/ingest/ingest_langchain_loader.py) - Operator implementation
- [`pyproject.toml`](../../src/datasift_opensource/backend/pyproject.toml) - Dependency configuration
- [`ingest_langchain_loader.md`](ingest_langchain_loader.md) - Operator documentation