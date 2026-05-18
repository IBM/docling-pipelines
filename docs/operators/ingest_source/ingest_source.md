# Ingest Source Operator

## Overview
The [`IngestSourceOperator`](../../../src/datasift/core/operators/ingest/ingest_source.py) provides a unified interface for ingesting documents from multiple cloud storage and collaboration platforms using LangChain document loaders. It inherits from [`AbstractOperator`](../../../src/datasift/core/operators/abstract_operator.py) and follows the same patterns as [`IngestLocalOperator`](../../../src/datasift/core/operators/ingest/ingest_local_folder.py).

## Features
- **Multi-Provider Support**: Single operator for multiple data sources
- **Automatic File Filtering**: Skips directories, hidden files, and empty objects by extension
- **Incremental Updates**: Skip previously processed documents (configurable)
- **Metadata Tracking**: Comprehensive tracking of processed, failed, and skipped documents
- **PyArrow Output**: Returns structured data in PyArrow table format
- **Error Handling**: Graceful error handling with detailed logging and metadata
- **Custom Loader Support**: Extensible architecture for custom implementations
- **AbstractOperator Pattern**: Consistent interface with other ingest operators

## Supported Providers

### 1. Amazon S3
Ingest documents from Amazon S3 buckets.

**Configuration:**
```python
node_config = {
    'provider': 's3',
    'connection_params': {
        'bucket': 'your-bucket-name',
        'prefix': 'optional/path/prefix/'  # Optional
    },
    'credentials': {
        'access_key': 'YOUR_AWS_ACCESS_KEY',
        'secret_key': 'YOUR_AWS_SECRET_KEY' # pragma: allowlist secret
    }
}
```

**Parameters:**
- `bucket` (required): S3 bucket name
- `prefix` (optional): Path prefix to filter objects
- `access_key` (required): AWS access key ID
- `secret_key` (required): AWS secret access key

### 2. IBM Cloud Object Storage (COS)
Ingest documents from IBM Cloud Object Storage (S3-compatible).

**Configuration:**
```python
node_config = {
    'provider': 'ibm_cos',
    'connection_params': {
        'bucket': 'your-bucket-name',
        'prefix': 'optional/path/prefix/',  # Optional
        'endpoint_url': 'https://s3.us-south.cloud-object-storage.appdomain.cloud'
    },
    'credentials': {
        'access_key': 'YOUR_IBM_ACCESS_KEY',
        'secret_key': 'YOUR_IBM_SECRET_KEY' # pragma: allowlist secret
    }
}
```

**Parameters:**
- `bucket` (required): COS bucket name
- `prefix` (optional): Path prefix to filter objects
- `endpoint_url` (required): IBM COS endpoint URL
- `access_key` (required): IBM COS access key (HMAC credentials)
- `secret_key` (required): IBM COS secret key (HMAC credentials)

### 3. Microsoft SharePoint
Ingest documents from SharePoint document libraries.

**Configuration:**
```python
node_config = {
    'provider': 'sharepoint',
    'connection_params': {
        'document_library_id': 'your-library-id'
    },
    'credentials': {
        'client_id': 'YOUR_CLIENT_ID',
        'client_secret': 'YOUR_CLIENT_SECRET', # pragma: allowlist secret
        'tenant_id': 'YOUR_TENANT_ID'
    }
}
```

**Prerequisites:**
- O365 package installed: `pip install O365`
- Azure AD app registration with SharePoint permissions

**Parameters:**
- `document_library_id` (required): SharePoint document library ID
- `client_id` (required): Azure AD application client ID
- `client_secret` (required): Azure AD application client secret
- `tenant_id` (required): Azure AD tenant ID

### 4. Microsoft OneDrive
Ingest documents from OneDrive folders.

**Configuration:**
```python
node_config = {
    'provider': 'onedrive',
    'connection_params': {
        'drive_id': 'your-drive-id',
        'folder_path': '/Documents/MyFolder'  # Optional
    },
    'credentials': {
        'client_id': 'YOUR_CLIENT_ID',
        'client_secret': 'YOUR_CLIENT_SECRET', # pragma: allowlist secret
        'tenant_id': 'YOUR_TENANT_ID'
    }
}
```

**Prerequisites:**
- O365 package installed: `pip install O365`
- Azure AD app registration with OneDrive permissions

**Parameters:**
- `drive_id` (required): OneDrive drive ID
- `folder_path` (optional): Path to specific folder
- `client_id` (required): Azure AD application client ID
- `client_secret` (required): Azure AD application client secret
- `tenant_id` (required): Azure AD tenant ID

### 5. Google Drive
Ingest documents from Google Drive folders using OAuth 2.0 authentication.

**Configuration:**
```python
node_config = {
    'provider': 'google_drive',
    'connection_params': {
        'folder_id': 'your-folder-id',
        'recursive': False  # Optional: include subfolders
    },
    'credentials': {
        'credentials_json_path': '/path/to/client_secret.json',
        'token_path': '/path/to/token.json',  # Optional
        'scopes': ['https://www.googleapis.com/auth/drive.readonly']  # Optional
    }
}
```

**Prerequisites:**
- Google Cloud Project with Drive API enabled
- OAuth 2.0 credentials (client secret JSON)
- Dependencies: `pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client`

**Parameters:**
- `folder_id` (required): Google Drive folder ID
- `recursive` (optional): Boolean, include subfolders (default: False)
- `credentials_json_path` (required): Path to OAuth client secret JSON
- `token_path` (optional): Path to store OAuth tokens (default: `~/.credentials/token.json`)
- `scopes` (optional): List of OAuth scopes (default: `['https://www.googleapis.com/auth/drive.readonly']`)

**OAuth Scopes:**
The operator uses read-only access by default for security. Available scopes:
- `https://www.googleapis.com/auth/drive.readonly` - Read-only access (recommended)
- `https://www.googleapis.com/auth/drive` - Full access to all files
- `https://www.googleapis.com/auth/drive.file` - Per-file access

**Important:** If you change scopes, you must delete the existing token file to re-authenticate with the new permissions.

### 6. Custom Loaders
Extend functionality with custom LangChain-compatible loaders.

**Configuration:**
```python
node_config = {
    'provider': 'custom',
    'connection_params': {
        'loader_class_path': 'my_package.loaders.CustomLoader',
        # Additional parameters specific to your loader
        'param1': 'value1',
        'param2': 'value2'
    },
    'credentials': {
        # Credentials specific to your loader
        'api_key': 'YOUR_API_KEY' # pragma: allowlist secret
    }
}
```

**Parameters:**
- `loader_class_path` (required): Python import path to loader class (e.g., `my_package.loaders.FileNetLoader`)
- Additional parameters are passed to the loader's `__init__` method

**Requirements:**
- Loader class must be importable
- Loader must implement LangChain's document loader interface with a `load()` method
- `load()` method must return `List[Document]`

## Usage

### Basic Example
```python
from datasift.core.operators.ingest.ingest_source import IngestSourceOperator
import pyarrow as pa

# Configure the operator
node_config = {
    'provider': 's3',
    'connection_params': {
        'bucket': 'my-bucket',
        'prefix': 'documents/'
    },
    'credentials': {
        'access_key': 'YOUR_ACCESS_KEY',
        'secret_key': 'YOUR_SECRET_KEY' # pragma: allowlist secret
    },
    'job_id': 'my-job-123',
    'job_run_id': 'run-456',
    'max_files': 100,  # Optional: limit number of files
    'include_filter': 'pdf,txt,docx',  # Optional: file extensions to include
    'exclude_filter': 'tmp,log',  # Optional: file extensions to exclude
    'force_ingest': False  # Optional: re-ingest previously processed docs
}

# Create operator instance
ingest_node = IngestSourceOperator(node_config)

# Execute ingestion (input_table is used as trigger)
input_table = pa.Table.from_arrays([])
output_tables, metadata = ingest_node.transform(input_table)

# Access results
result_table = output_tables[0]
print(f"Status: {metadata['node_status']}")
print(f"Documents processed: {metadata['processed_docs']}")
print(f"Total documents: {metadata['total_docs_count']}")
print(f"Failed: {metadata['failed_docs_count']}")
print(f"Skipped: {metadata['skipped_docs_count']}")
print(f"Schema: {result_table.schema}")
```

### Output Schema
The operator returns a PyArrow table with the following schema:

| Column | Type | Description |
|--------|------|-------------|
| `id` | string | Document ID (MD5 hash of source path) |
| `name` | string | Source path/identifier |
| `text` | string | Document content (page_content from LangChain Document) |
| `metadata` | string | JSON-serialized metadata from source |
| `source_id` | string | Source identifier (extracted from metadata['source']) |

### Accessing Results
```python
# Convert to pandas for analysis
df = result_table.to_pandas()

# Access individual documents
for i in range(result_table.num_rows):
    text = result_table['text'][i].as_py()
    metadata = json.loads(result_table['metadata'][i].as_py())
    source = result_table['source_id'][i].as_py()
    
    print(f"Document {i+1}:")
    print(f"  Source: {source}")
    print(f"  Text length: {len(text)}")
    print(f"  Metadata: {metadata}")
```

## File Filtering

### Extension-Based Filtering
The operator supports include/exclude filtering by file extension:
- **include_filter**: Comma-separated list of extensions to include (e.g., "pdf,txt,docx")
- **exclude_filter**: Comma-separated list of extensions to exclude (e.g., "tmp,log")

### S3/IBM COS Filtering
The operator automatically filters out:
- **Directory markers**: Objects with keys ending in `/`
- **Hidden files**: Files or directories starting with `.` (except `.` and `..`)
- **Empty objects**: Objects with size 0 bytes

### Max Files Limit
Use the `max_files` parameter to limit the number of documents processed (default: 100).

This ensures only actual file content is processed, improving efficiency and data quality.

## Incremental Updates

The operator supports incremental processing to avoid re-ingesting unchanged documents:

```python
node_config = {
    'provider': 's3',
    'connection_params': {...},
    'credentials': {...},
    'job_id': 'my-job-123',
    'force_ingest': False  # Set to True to re-ingest all documents
}
```

Documents are tracked by their ID and modification time. Previously processed documents are automatically skipped unless `force_ingest` is set to `True`.

## Error Handling

### Graceful Degradation
The operator handles errors gracefully following the AbstractOperator pattern:
- Individual file load failures are tracked in metadata
- Processing continues for remaining files
- Comprehensive error tracking with document-level details

### Metadata Response
```python
# Metadata structure (follows AbstractOperator pattern):
metadata = {
    "node_status": "completed" | "completed_with_errors" | "completed_with_warnings",
    "total_docs_count": 100,
    "processed_docs": 95,
    "failed_docs_count": 3,
    "failed_docs": [
        {"id": "doc1", "name": "file1.pdf", "reason": "Error description", "document_url": ""}
    ],
    "skipped_docs_count": 2,
    "skipped_docs": [
        {"id": "doc2", "name": "file2.pdf", "reason": "Already processed", "document_url": ""}
    ]
}
```

### Common Errors

**Authentication Errors:**
```
Error: Invalid credentials
```
**Solution:** Verify credentials are correct and have necessary permissions.

**Google Drive Scope Errors:**
```
Error: ('invalid_scope: Bad Request', {'error': 'invalid_scope', 'error_description': 'Bad Request'})
```
**Solution:** This error occurs when OAuth scopes are missing or incorrect. To fix:
1. Ensure the `scopes` parameter is included in credentials configuration
2. Delete the existing token file (default: `~/.credentials/token.json`)
3. Re-run the ingestion to trigger re-authentication with correct scopes
4. Use the default scope `['https://www.googleapis.com/auth/drive.readonly']` for read-only access

**Connection Errors:**
```
Error: Could not connect to endpoint
```
**Solution:** Check network connectivity and endpoint URLs (especially for IBM COS).

**Permission Errors:**
```
Error: Access denied
```
**Solution:** Ensure credentials have read permissions for the specified resources.

## Performance Considerations

### Large Datasets
- S3/COS: Uses pagination to handle large buckets efficiently
- Google Drive: Set `recursive=False` for large folder structures
- Consider using `prefix` parameter to limit scope

### Memory Usage
- Documents are loaded into memory before conversion to PyArrow
- For very large files, consider chunking strategies
- Monitor memory usage with large document sets

### Optimization Tips
1. Use specific prefixes/folder IDs to limit scope
2. Filter file types at the source when possible
3. Process in batches for very large datasets
4. Use appropriate loader configurations for your use case

## Integration with Downstream Operators

The output format is designed for seamless integration with:
- **Embedding operators**: Text column ready for vectorization
- **Transform operators**: Metadata available for filtering/routing
- **Storage operators**: PyArrow format for efficient storage

### Example Pipeline
```python
# 1. Ingest documents
ingest_node = IngestSourceOperator(ingest_config)
tables, metadata = ingest_node.transform(input_table)

# 2. Process with downstream operators
# embedding_node = EmbeddingOperator(embedding_config)
# embedded_tables, _ = embedding_node.transform(tables[0])

# 3. Store results
# storage_node = StorageOperator(storage_config)
# storage_node.transform(embedded_tables[0])
```

## Security Best Practices

1. **Credential Management:**
   - Never hardcode credentials in source code
   - Use environment variables or secret management systems
   - Rotate credentials regularly

2. **Access Control:**
   - Use least-privilege principle for service accounts
   - Limit bucket/folder access to necessary resources
   - Monitor access logs for suspicious activity

3. **Data Protection:**
   - Use encrypted connections (HTTPS/TLS)
   - Consider encrypting sensitive data at rest
   - Implement data retention policies

4. **OAuth Tokens (Google Drive, SharePoint, OneDrive):**
   - Store tokens securely with restricted file permissions
   - Never commit token files to version control
   - Implement token refresh mechanisms

## Troubleshooting

### Debug Mode
Enable detailed logging by examining the operator output:
```python
output_tables, metadata = ingest_node.transform(input_table)
print(f"Metadata: {metadata}")
if metadata['status'] == 'error':
    print(f"Error: {metadata['message']}")
```

### Testing Connectivity
Test each provider independently:
```python
# Test S3 connectivity
import boto3
s3_client = boto3.client('s3', 
    aws_access_key_id='YOUR_KEY',
    aws_secret_access_key='YOUR_SECRET') # pragma: allowlist secret
response = s3_client.list_objects_v2(Bucket='your-bucket', MaxKeys=1)
print(f"Connection successful: {response['ResponseMetadata']['HTTPStatusCode'] == 200}")
```

### Common Issues

**Issue: No documents loaded**
- Verify folder/bucket contains files
- Check prefix/path parameters
- Ensure files are not filtered (hidden, empty, directories)

**Issue: Metadata parsing errors**
- Some loaders may return non-JSON-serializable metadata
- Check metadata structure in debug output
- Consider custom metadata handling

**Issue: Slow performance**
- Reduce scope with prefix/folder parameters
- Check network latency to storage provider
- Consider parallel processing for large datasets

## Dependencies

### Core Dependencies
```
langchain==1.2.10
langchain-core==1.2.14
pyarrow==17.0.0
pandas==2.3.3
botocore==1.42.55
```

### Provider-Specific Dependencies
- **AWS/S3:** `boto3==1.42.55`, `langchain-community==0.4.1`
- **Google Drive:** `google-auth-oauthlib==1.2.4`, `google-auth-httplib2==0.3.0`, `google-api-python-client==2.190.0`, `langchain-google-community==3.0.5`
- **SharePoint/OneDrive:** `O365==2.1.9`, `langchain-community==0.4.1`
- **PDF Processing:** `pypdf2==3.0.1`, `unstructured[pdf]>=0.10.0`
- **GCP:** `google-cloud-storage==3.9.0`
- **Azure:** `azure-storage-blob==12.28.0`

### Installation

Using uv (recommended):
```bash
# From project root directory
# Core installation (includes langchain and langchain-core)
uv sync

# AWS/S3 support
uv sync --extra aws

# Google Drive support
uv sync --extra google-drive

# Microsoft (SharePoint/OneDrive) support
uv sync --extra microsoft

# All cloud providers
uv sync --extra all-cloud

# Development dependencies
uv sync --extra dev
```

Using pip:
```bash
# Core installation
pip install langchain==1.2.10 langchain-core==1.2.14 pyarrow==17.0.0 pandas==2.3.3

# AWS/S3 support
pip install boto3==1.42.55 langchain-community==0.4.1

# Google Drive support
pip install google-auth-oauthlib==1.2.4 google-auth-httplib2==0.3.0 google-api-python-client==2.190.0 langchain-google-community==3.0.5 pypdf2==3.0.1 "unstructured[pdf]>=0.10.0"

# Microsoft support
pip install O365==2.1.9 langchain-community==0.4.1
```

## API Reference

### Class: IngestSourceOperator

Inherits from: [`AbstractOperator`](../../../src/datasift/core/operators/abstract_operator.py)

#### `__init__(node_config: dict)`
Initialize the operator with configuration.

**Parameters:**
- `node_config` (dict): Configuration dictionary containing:
  - `provider` (str): Provider identifier (s3, ibm_cos, google_drive, sharepoint, onedrive, web, custom)
  - `connection_params` (dict): Provider-specific connection parameters
  - `credentials` (dict): Authentication credentials
  - `job_id` (str, optional): Job identifier for tracking
  - `job_run_id` (str, optional): Job run identifier
  - `max_files` (int, optional): Maximum number of files to process (default: 100)
  - `include_filter` (str, optional): Comma-separated file extensions to include
  - `exclude_filter` (str, optional): Comma-separated file extensions to exclude
  - `force_ingest` (bool, optional): Force re-ingestion of previously processed documents (default: False)

#### `transform(input_table: pa.Table) -> tuple[list[pa.Table], dict]`
Execute document ingestion.

**Parameters:**
- `input_table` (pa.Table): Input PyArrow table (can be None for initial ingestion)

**Returns:**
- `tuple[list[pa.Table], dict]`:
  - List containing single output PyArrow table with schema (id, name, text, metadata, source_id)
  - Metadata dictionary following AbstractOperator pattern with comprehensive tracking

**Raises:**
- Returns error metadata instead of raising exceptions for graceful degradation

#### `get_metadata() -> dict`
Get operator metadata including features and attributes.

**Returns:**
- `dict`: Operator metadata with features, attributes, and availability information

## Examples

### Example 1: S3 with Prefix Filtering
```python
node_config = {
    'provider': 's3',
    'connection_params': {
        'bucket': 'company-documents',
        'prefix': '2024/invoices/'
    },
    'credentials': {
        'access_key': os.getenv('AWS_ACCESS_KEY'),
        'secret_key': os.getenv('AWS_SECRET_KEY') # pragma: allowlist secret
    }
}
```

### Example 2: Google Drive Recursive
```python
node_config = {
    'provider': 'google_drive',
    'connection_params': {
        'folder_id': '1DKN_mxnoW1Uaacghz8vyEeqw-j4IOSFK',
        'recursive': True
    },
    'credentials': {
        'credentials_json_path': os.getenv('GOOGLE_CREDENTIALS_PATH'),
        'token_path': os.path.expanduser('~/.credentials/gdrive_token.json'),
        'scopes': ['https://www.googleapis.com/auth/drive.readonly']
    }
}
```

### Example 3: IBM COS with Custom Endpoint
```python
node_config = {
    'provider': 'ibm_cos',
    'connection_params': {
        'bucket': 'enterprise-data',
        'prefix': 'contracts/',
        'endpoint_url': 'https://s3.eu-gb.cloud-object-storage.appdomain.cloud'
    },
    'credentials': {
        'access_key': os.getenv('IBM_COS_ACCESS_KEY'),
        'secret_key': os.getenv('IBM_COS_SECRET_KEY') # pragma: allowlist secret
    }
}
```

## Contributing

To add support for a new provider:

1. Add the provider to the `_get_loader()` method
2. Import the corresponding LangChain loader
3. Map configuration parameters to loader initialization
4. Update this documentation with provider details
5. Add example configuration and usage

## Related Documentation
- [Operators Overview](../../../README.md)

## License
See project LICENSE file for details.
