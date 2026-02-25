# Ingest LangChain Loader Operator

## Overview
The [`IngestLangchainOperator`](../../../src/datasift_opensource/backend/core/operators/universal/ingest/ingest_langchain_loader.py) provides a unified interface for ingesting documents from multiple cloud storage and collaboration platforms using LangChain document loaders. It supports Amazon S3, IBM Cloud Object Storage, Microsoft SharePoint, Microsoft OneDrive, Google Drive, and custom loaders.

## Features
- **Multi-Provider Support**: Single operator for multiple data sources
- **Automatic File Filtering**: Skips directories, hidden files, and empty objects
- **Metadata Preservation**: Maintains source metadata for downstream processing
- **PyArrow Output**: Returns structured data in PyArrow table format
- **Error Handling**: Graceful error handling with detailed logging
- **Custom Loader Support**: Extensible architecture for custom implementations

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
        'secret_key': 'YOUR_AWS_SECRET_KEY'
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
        'secret_key': 'YOUR_IBM_SECRET_KEY'
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
        'client_secret': 'YOUR_CLIENT_SECRET',
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
        'client_secret': 'YOUR_CLIENT_SECRET',
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
        'token_path': '/path/to/token.json'  # Optional
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
        'api_key': 'YOUR_API_KEY'
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
from datasift_opensource.backend.core.operators.universal.ingest.ingest_langchain_loader import IngestLangchainOperator
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
        'secret_key': 'YOUR_SECRET_KEY'
    }
}

# Create operator instance
ingest_node = IngestLangchainOperator(node_config)

# Execute ingestion (input_table is used as trigger)
input_table = pa.Table.from_arrays([])
output_tables, metadata = ingest_node.transform(input_table)

# Access results
result_table = output_tables[0]
print(f"Status: {metadata['status']}")
print(f"Documents ingested: {metadata['count']}")
print(f"Schema: {result_table.schema}")
```

### Output Schema
The operator returns a PyArrow table with the following schema:

| Column | Type | Description |
|--------|------|-------------|
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

### S3/IBM COS Filtering
The operator automatically filters out:
- **Directory markers**: Objects with keys ending in `/`
- **Hidden files**: Files or directories starting with `.` (except `.` and `..`)
- **Empty objects**: Objects with size 0 bytes

This ensures only actual file content is processed, improving efficiency and data quality.

## Error Handling

### Graceful Degradation
The operator handles errors gracefully:
- Individual file load failures are logged as warnings
- Processing continues for remaining files
- Empty table returned on complete failure with error metadata

### Error Response
```python
# On error, returns:
output_tables = [empty_table]  # Empty PyArrow table with correct schema
metadata = {
    "status": "error",
    "message": "Error description"
}
```

### Common Errors

**Authentication Errors:**
```
Error: Invalid credentials
```
**Solution:** Verify credentials are correct and have necessary permissions.

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
ingest_node = IngestLangchainOperator(ingest_config)
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
    aws_secret_access_key='YOUR_SECRET')
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
# Navigate to backend directory
cd src/datasift_opensource/backend

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

### Class: IngestLangchainOperator

#### `__init__(node_config: dict)`
Initialize the operator with configuration.

**Parameters:**
- `node_config` (dict): Configuration dictionary containing:
  - `provider` (str): Provider identifier
  - `connection_params` (dict): Provider-specific connection parameters
  - `credentials` (dict): Authentication credentials

#### `transform(input_table: pa.Table) -> tuple[list[pa.Table], dict]`
Execute document ingestion.

**Parameters:**
- `input_table` (pa.Table): Input PyArrow table (used as trigger, content ignored)

**Returns:**
- `tuple[list[pa.Table], dict]`: 
  - List containing single output PyArrow table with schema (text, metadata, source_id)
  - Metadata dictionary with status and count/error information

**Raises:**
- Returns error metadata instead of raising exceptions for graceful degradation

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
        'secret_key': os.getenv('AWS_SECRET_KEY')
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
        'token_path': os.path.expanduser('~/.credentials/gdrive_token.json')
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
        'secret_key': os.getenv('IBM_COS_SECRET_KEY')
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
- [Operators Overview](../../src/datasift_opensource/backend/operators/README.md)

## License
See project LICENSE file for details.