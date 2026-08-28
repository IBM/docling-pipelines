# ACL Document Retrieval API

## Overview

The ACL Document Retrieval API provides secure, user-scoped access to documents stored in OpenSearch. All document access is automatically filtered based on the `allowed_users` field, ensuring users can only retrieve documents they are authorized to view.

## Features

- **Authentication-Required**: All endpoints require valid JWT authentication
- **ACL Enforcement**: Automatic filtering based on `allowed_users` field
- **Security by Obscurity**: Returns 404 for unauthorized access (not 403) to prevent information leakage
- **Full-Text Search**: Search across document content, title, and metadata
- **Field Filtering**: Filter documents by specific field values
- **Sorting**: Sort results by any field
- **Pagination**: Efficient pagination with limit/offset

## Architecture

### Components

1. **OpenSearchService** (`src/docpipe/api/services/opensearch_service.py`)
   - Manages OpenSearch client connections
   - Provides connection pooling and health checks
   - Configurable via environment variables

2. **ACLQueryBuilder** (`src/docpipe/api/services/acl_query_builder.py`)
   - Constructs OpenSearch queries with ACL filtering
   - Injects `allowed_users` filter into all queries
   - Validates ACL field presence and format

3. **Document DTOs** (`src/docpipe/api/dto/document_dto.py`)
   - `DocumentResponse`: Document retrieval response model
   - `DocumentSearchRequest`: Search request parameters
   - `DocumentSearchResponse`: Search results with pagination

4. **API Routes** (`src/docpipe/api/routes/documents.py`)
   - `GET /api/v1/documents/{document_id}`: Retrieve single document
   - `POST /api/v1/documents/search`: Search documents

## API Endpoints

### 1. Retrieve Document by ID

**Endpoint**: `GET /api/v1/documents/{document_id}`

**Authentication**: Required (JWT Bearer token)

**Description**: Retrieve a single document by its ID. Access is granted only if the authenticated user's username is present in the document's `allowed_users` field.

**Request**:
```bash
curl -X GET "http://localhost:8080/api/v1/documents/doc-123" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response** (200 OK):
```json
{
  "id": "doc-123",
  "content": "Document content here...",
  "title": "Sample Document",
  "metadata": {
    "category": "tech",
    "author": "John Doe"
  },
  "created_at": "2026-05-01T10:00:00Z",
  "updated_at": "2026-05-15T14:30:00Z"
}
```

**Error Responses**:
- `401 Unauthorized`: Missing or invalid JWT token
- `404 Not Found`: Document not found OR user not authorized (security by obscurity)
- `503 Service Unavailable`: OpenSearch service unavailable

### 2. Search Documents

**Endpoint**: `POST /api/v1/documents/search`

**Authentication**: Required (JWT Bearer token)

**Description**: Search documents with full-text search, filters, sorting, and pagination. Results are automatically filtered to only include documents where the authenticated user is in `allowed_users`.

**Request**:
```bash
curl -X POST "http://localhost:8080/api/v1/documents/search" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning",
    "filters": {
      "category": "tech",
      "status": "published"
    },
    "sort": [
      {"created_at": "desc"}
    ],
    "limit": 20,
    "offset": 0
  }'
```

**Request Body Parameters**:
- `query` (optional): Full-text search query across content, title, and metadata
- `filters` (optional): Field filters for exact matching (supports single values or arrays)
- `sort` (optional): Sort specification with field and direction (asc/desc)
- `limit` (optional): Maximum results per page (1-100, default: 10)
- `offset` (optional): Number of results to skip (default: 0)

**Response** (200 OK):
```json
{
  "documents": [
    {
      "id": "doc-1",
      "content": "Machine learning content...",
      "title": "ML Guide",
      "metadata": {"category": "tech"},
      "created_at": "2026-05-01T10:00:00Z",
      "updated_at": "2026-05-15T14:30:00Z"
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0,
  "has_more": true
}
```

**Error Responses**:
- `401 Unauthorized`: Missing or invalid JWT token
- `422 Unprocessable Entity`: Invalid request parameters
- `503 Service Unavailable`: OpenSearch service unavailable

## ACL Security Model

### Fail-Closed Security

The API implements a **fail-closed** security model:

1. **Missing `allowed_users` field**: Document is **NOT accessible**
2. **Empty `allowed_users` array**: Document is **NOT accessible**
3. **`allowed_users` contains username**: Document is **accessible**

### Information Leakage Prevention

The API returns `404 Not Found` for both:
- Documents that don't exist
- Documents that exist but user is not authorized

This prevents attackers from enumerating document IDs by observing different error codes.

### Query-Level Enforcement

ACL filtering is applied at the OpenSearch query level, not in application code. This ensures:
- Performance: OpenSearch filters results efficiently
- Security: No documents leak through application logic
- Consistency: Same ACL rules apply to all queries

## Configuration

### Environment Variables

Add to `.env` file:

```bash
# OpenSearch Connection
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_USE_SSL=false
OPENSEARCH_VERIFY_CERTS=false
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=admin

# Document Retrieval Configuration
OPENSEARCH_DEFAULT_INDEX=documents
OPENSEARCH_TIMEOUT=30
OPENSEARCH_MAX_RETRIES=3
```

### OpenSearch Index Setup

Documents must have an `allowed_users` field:

```json
{
  "_id": "doc-123",
  "_source": {
    "content": "Document content",
    "title": "Document title",
    "metadata": {},
    "allowed_users": ["john.doe", "jane.smith"],
    "created_at": "2026-05-01T10:00:00Z",
    "updated_at": "2026-05-15T14:30:00Z"
  }
}
```

**Index Mapping** (recommended):

```json
{
  "mappings": {
    "properties": {
      "content": {"type": "text"},
      "title": {"type": "text"},
      "metadata": {"type": "object"},
      "allowed_users": {"type": "keyword"},
      "created_at": {"type": "date"},
      "updated_at": {"type": "date"}
    }
  }
}
```

## Authentication Flow

### 1. Obtain JWT Token

```bash
curl -X POST "http://localhost:8080/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john.doe",
    "password": "${USER_PASSWORD}"
  }'
```

Response:
```json
{
  "access_token": "ey...",
  "token_type": "bearer"
}
```

### 2. Verify Identity

```bash
curl -X GET "http://localhost:8080/auth/me" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Response:
```json
{
  "username": "john.doe",
  "email": "john.doe@example.com",
  "full_name": "John Doe"
}
```

### 3. Access Documents

Use the JWT token in the `Authorization` header for all document requests.

## Usage Examples

### Example 1: Retrieve Specific Document

```python
import requests

# Authenticate
auth_response = requests.post(
    "http://localhost:8080/auth/login",
    json={"username": "john.doe", "password": "<YOUR_PASSWORD>"}
)
token = auth_response.json()["access_token"]

# Retrieve document
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    "http://localhost:8080/api/v1/documents/doc-123",
    headers=headers
)

if response.status_code == 200:
    document = response.json()
    print(f"Title: {document['title']}")
    print(f"Content: {document['content']}")
elif response.status_code == 404:
    print("Document not found or not authorized")
```

### Example 2: Search with Filters

```python
import requests

# Authenticate (same as above)
token = "YOUR_JWT_TOKEN"
headers = {"Authorization": f"Bearer {token}"}

# Search documents
search_request = {
    "query": "artificial intelligence",
    "filters": {
        "category": "tech",
        "status": "published"
    },
    "sort": [{"created_at": "desc"}],
    "limit": 20,
    "offset": 0
}

response = requests.post(
    "http://localhost:8080/api/v1/documents/search",
    headers=headers,
    json=search_request
)

results = response.json()
print(f"Found {results['total']} documents")
for doc in results['documents']:
    print(f"- {doc['title']}")
```

### Example 3: Pagination

```python
import requests

token = "YOUR_JWT_TOKEN"
headers = {"Authorization": f"Bearer {token}"}

# Fetch all results with pagination
all_documents = []
offset = 0
limit = 100

while True:
    response = requests.post(
        "http://localhost:8080/api/v1/documents/search",
        headers=headers,
        json={"limit": limit, "offset": offset}
    )

    results = response.json()
    all_documents.extend(results['documents'])

    if not results['has_more']:
        break

    offset += limit

print(f"Retrieved {len(all_documents)} total documents")
```

## Testing

### Unit Tests

Located in `tests/unit/api/services/test_acl_query_builder.py`:

```bash
# Run unit tests
pytest tests/unit/api/services/test_acl_query_builder.py -v
```

### Integration Tests

Located in `tests/integration/api/test_documents_api.py`:

```bash
# Run integration tests (requires OpenSearch)
pytest tests/integration/api/test_documents_api.py -v
```

### Test Coverage

```bash
# Run with coverage
pytest tests/unit/api/services/ tests/integration/api/test_documents_api.py \
  --cov=src/docpipe/api/services \
  --cov=src/docpipe/api/routes/documents \
  --cov-report=html
```

## Performance Considerations

### Query Optimization

1. **Index `allowed_users` field**: Create an index on the `allowed_users` field for fast filtering
2. **Use OpenSearch caching**: Enable query result caching in OpenSearch
3. **Pagination**: Use reasonable page sizes (10-100 documents)

### Connection Pooling

The `OpenSearchService` maintains a connection pool for efficient resource usage:
- Connections are reused across requests
- Automatic retry on transient failures
- Configurable timeout and max retries

### Monitoring

Monitor these metrics:
- Query response times
- OpenSearch cluster health
- Authentication failures
- 404 vs 401 error rates

## Security Best Practices

1. **Use HTTPS**: Always use HTTPS in production
2. **Rotate JWT secrets**: Regularly rotate JWT signing keys
3. **Monitor access patterns**: Log and monitor document access for anomalies
4. **Rate limiting**: Implement rate limiting on search endpoints
5. **Audit logging**: Log all document access attempts with user identity

## Troubleshooting

### Common Issues

**Issue**: `503 Service Unavailable`
- **Cause**: OpenSearch is down or unreachable
- **Solution**: Check OpenSearch health, verify connection settings

**Issue**: `401 Unauthorized`
- **Cause**: Invalid or expired JWT token
- **Solution**: Re-authenticate to obtain a new token

**Issue**: `404 Not Found` for existing documents
- **Cause**: User not in `allowed_users` field
- **Solution**: Verify user has proper access rights in the document

**Issue**: Empty search results
- **Cause**: No documents match both search criteria AND ACL filter
- **Solution**: Verify documents exist and user has access

### Debug Mode

Enable debug logging:

```bash
export DS_LOG_LEVEL=DEBUG
```

This will log:
- OpenSearch queries
- ACL filter construction
- Authentication details
- Query execution times

## Future Enhancements

Planned features for future releases:

1. **Group-Based ACLs**: Support `allowed_groups` in addition to `allowed_users`
2. **Role-Based Access**: Integrate with role management system
3. **Document Sharing**: API to modify `allowed_users` field
4. **Access Analytics**: Dashboard showing document access patterns
5. **Bulk Operations**: Batch document retrieval API
6. **Advanced Search**: Faceted search, aggregations, highlighting

## Related Documentation

- [API Reference](../reference/OPERATORS.md)
- [Architecture](../../ARCHITECTURE.md)
- [OAuth2 Authentication Guide](OAUTH2_AUTHENTICATION.md)

## Support

For issues or questions:
1. Check existing documentation
2. Search GitHub issues
3. Create a new issue with detailed information
