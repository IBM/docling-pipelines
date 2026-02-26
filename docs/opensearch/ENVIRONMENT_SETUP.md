# Environment Configuration Guide

This guide explains how to configure the OpenSearch operator using environment variables.

## Overview

All OpenSearch connection details, engine selection, and configuration parameters are managed through environment variables. This approach provides:

- **Security**: Sensitive credentials are kept out of source code
- **Flexibility**: Easy configuration changes without code modifications
- **Consistency**: Same configuration across all tests and examples

## Setup Instructions

### 1. Copy the Example Environment File

```bash
cp .env.example .env
```

### 2. Edit the .env File

Open `.env` in your editor and update the values:

```bash
# OpenSearch Server
OPENSEARCH_HOST=your-opensearch-host
OPENSEARCH_PORT=9200
OPENSEARCH_USE_SSL=true
OPENSEARCH_VERIFY_CERTS=false

# Authentication
OPENSEARCH_USERNAME=your-username
OPENSEARCH_PASSWORD=your-password

# Engine Configuration
OPENSEARCH_ENGINE=faiss
OPENSEARCH_ALGORITHM=hnsw
OPENSEARCH_SPACE_TYPE=l2
OPENSEARCH_VECTOR_DIMENSION=384

# Performance Settings
OPENSEARCH_BATCH_SIZE=100
OPENSEARCH_CREATE_INDEX=true

# Index Configuration
OPENSEARCH_INDEX_NAME=datasift_test
OPENSEARCH_DOC_ID_COLUMN=doc_id_hash
OPENSEARCH_EMBEDDINGS_COLUMN=embeddings
```

### 3. Verify Configuration

The `.env` file is automatically loaded by the `env_config.py` utility module. You can verify your configuration:

```python
from datasift_opensource.backend.common.util.env_config import get_opensearch_config

config = get_opensearch_config()
print(config)
```

## Configuration Parameters

### Connection Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `OPENSEARCH_HOST` | string | localhost | OpenSearch server hostname or IP |
| `OPENSEARCH_PORT` | integer | 9200 | OpenSearch server port |
| `OPENSEARCH_USE_SSL` | boolean | false | Enable SSL/TLS connection |
| `OPENSEARCH_VERIFY_CERTS` | boolean | false | Verify SSL certificates |

### Authentication

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `OPENSEARCH_USERNAME` | string | - | Username for authentication |
| `OPENSEARCH_PASSWORD` | string | - | Password for authentication |
| `OPENSEARCH_AWS_AUTH` | boolean | false | Use AWS authentication |
| `OPENSEARCH_AWS_REGION` | string | us-east-1 | AWS region (if using AWS auth) |

### Engine Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `OPENSEARCH_ENGINE` | string | faiss | Vector search engine (faiss, lucene, nmslib) |
| `OPENSEARCH_ALGORITHM` | string | hnsw | Search algorithm (hnsw, ivf) |
| `OPENSEARCH_SPACE_TYPE` | string | l2 | Distance metric (l2, cosine, inner_product) |
| `OPENSEARCH_VECTOR_DIMENSION` | integer | 384 | Vector embedding dimension |

### Performance Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `OPENSEARCH_BATCH_SIZE` | integer | 100 | Number of documents per batch |
| `OPENSEARCH_CREATE_INDEX` | boolean | true | Create index if it doesn't exist |

### Index Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `OPENSEARCH_INDEX_NAME` | string | datasift_test | Name of the OpenSearch index |
| `OPENSEARCH_DOC_ID_COLUMN` | string | doc_id_hash | Column name for document IDs |
| `OPENSEARCH_EMBEDDINGS_COLUMN` | string | embeddings | Column name for vector embeddings |

## Usage in Code

### Using Default Configuration

```python
from datasift_opensource.backend.common.util.env_config import get_opensearch_config
from datasift_opensource.backend.core.operators.universal.vectordb.opensearch_operator import OpenSearchOperator

# Get configuration from environment
config = get_opensearch_config()

# Add required features and mappings
config.update({
    "available_features": {
        "doc_id_hash": {
            "available_for_vector_db": True,
            "mandatory_for_vector_db": True,
            "type": "string",
            "is_primary": True
        },
        "embeddings": {
            "available_for_vector_db": True,
            "mandatory_for_vector_db": True,
            "type": "vector"
        }
    },
    "feature_mappings": {
        "doc_id_hash": "id",
        "embeddings": "vector"
    }
})

# Initialize operator
operator = OpenSearchOperator(config)
```

### Overriding Specific Values

```python
from datasift_opensource.backend.common.util.env_config import get_opensearch_config

# Get base configuration
config = get_opensearch_config()

# Override specific values
config.update({
    "index_name": "my_custom_index",
    "batch_size": 50,
    "engine": "lucene"
})
```

### Using Individual Environment Variables

```python
from datasift_opensource.backend.common.util.env_config import get_env_var, get_env_bool, get_env_int

host = get_env_var("OPENSEARCH_HOST", "localhost")
port = get_env_int("OPENSEARCH_PORT", 9200)
use_ssl = get_env_bool("OPENSEARCH_USE_SSL", False)
```

## Testing

All tests automatically use environment variables:

### Unit Tests

```bash
# Run unit tests
pytest tests/unit/operators/vectordb/test_opensearch_operator.py -v
```

### Integration Examples

```bash
# Run integration examples
python examples/opensearch_integration_example.py
```

### Advanced Tests

```bash
# Run advanced test suite
python test_opensearch_advanced.py
```

## Security Best Practices

1. **Never commit `.env` file**: The `.env` file is already in `.gitignore`
2. **Use strong passwords**: Ensure your OpenSearch password is strong
3. **Enable SSL in production**: Always use `OPENSEARCH_USE_SSL=true` in production
4. **Rotate credentials regularly**: Update passwords periodically
5. **Use AWS IAM roles**: When possible, use AWS authentication instead of username/password

## Troubleshooting

### Connection Issues

If you encounter connection errors:

1. Verify `OPENSEARCH_HOST` and `OPENSEARCH_PORT` are correct
2. Check if `OPENSEARCH_USE_SSL` matches your server configuration
3. Ensure firewall rules allow connections to the OpenSearch port

### Authentication Errors

If authentication fails:

1. Verify `OPENSEARCH_USERNAME` and `OPENSEARCH_PASSWORD` are correct
2. Check if the user has necessary permissions
3. For AWS OpenSearch, ensure `OPENSEARCH_AWS_AUTH=true` and AWS credentials are configured

### Engine/Algorithm Errors

If you get engine or algorithm errors:

1. Check OpenSearch version compatibility
2. Verify the engine-algorithm combination is supported
3. Ensure the space_type is compatible with your OpenSearch version

## Example Configurations

### Local Development

```bash
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_USE_SSL=false
OPENSEARCH_VERIFY_CERTS=false
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=admin
```

### Production (Self-Hosted)

```bash
OPENSEARCH_HOST=opensearch.example.com
OPENSEARCH_PORT=9200
OPENSEARCH_USE_SSL=true
OPENSEARCH_VERIFY_CERTS=true
OPENSEARCH_USERNAME=prod_user
OPENSEARCH_PASSWORD=strong_password_here
```

### AWS OpenSearch Service

```bash
OPENSEARCH_HOST=search-domain.us-east-1.es.amazonaws.com
OPENSEARCH_PORT=443
OPENSEARCH_USE_SSL=true
OPENSEARCH_VERIFY_CERTS=true
OPENSEARCH_AWS_AUTH=true
OPENSEARCH_AWS_REGION=us-east-1
```

## Additional Resources

- [OpenSearch Documentation](https://opensearch.org/docs/latest/)
- [OpenSearch Operator Documentation](docs/operators/opensearch.md)
- [Quick Start Guide](OPENSEARCH_QUICKSTART.md)
- [Integration Examples](examples/opensearch_example_README.md)