# Incremental Metadata Storage

## Overview

Datasift supports incremental processing by tracking which documents have been processed in previous runs. This allows you to skip already-processed files and only process new or modified documents, significantly improving efficiency for large datasets.

## Storage Backends

Incremental metadata can be stored using different backends:

### 1. File System Storage (Default)
Stores metadata as JSON files on the local filesystem or shared storage.

**Use Cases:**
- Local development and testing
- Single-node deployments
- Shared filesystem environments (NFS, EFS, etc.)

**Advantages:**
- Simple setup, no external dependencies
- Good for development and small-scale deployments
- Automatic file locking for concurrent access

**Limitations:**
- Not suitable for distributed deployments without shared storage
- Performance may degrade with very large metadata sets

### 2. PostgreSQL Storage
Stores metadata in a PostgreSQL database.

**Use Cases:**
- Production deployments
- Distributed processing across multiple workers
- High-volume processing requiring robust concurrency

**Advantages:**
- Centralized storage accessible from multiple workers
- ACID compliance ensures data consistency
- Scales well with large metadata sets
- Built-in transaction support

**Limitations:**
- Requires PostgreSQL database setup and maintenance
- Additional infrastructure dependency

### 3. In-Memory Storage
Stores metadata in memory (non-persistent).

**Use Cases:**
- Testing and development only
- Temporary workflows where persistence is not needed

**Limitations:**
- Data is lost when the process terminates
- Not suitable for production use

## Configuration

### Flow-Level Configuration

Configure incremental metadata storage in your flow JSON file under `global_config`:

#### File System Storage

```json
{
  "global_config": {
    "incremental_metadata": {
      "storage_type": "file_system",
      "config": {
        "base_dir": "/path/to/metadata/storage",
        "lock_timeout": 30.0
      }
    }
  }
}
```

**Parameters:**
- `base_dir` (optional): Directory for storing metadata files. Defaults to `~/.datasift/data/incremental_metadata`
- `lock_timeout` (optional): Timeout in seconds for acquiring file locks. Default: 30.0

#### PostgreSQL Storage

```json
{
  "global_config": {
    "incremental_metadata": {
      "storage_type": "postgresql",
      "config": {
        "host": "localhost",
        "port": 5432,
        "database": "datasift",
        "username": "datasift_user",
        "password": "your_password",
        "schema": "incremental_metadata"
      }
    }
  }
}
```

**Parameters:**
- `host`: PostgreSQL server hostname
- `port`: PostgreSQL server port (default: 5432)
- `database`: Database name
- `username`: Database user
- `password`: Database password
- `schema` (optional): Schema name for metadata tables. Default: "incremental_metadata"

#### In-Memory Storage (Testing Only)

```json
{
  "global_config": {
    "incremental_metadata": {
      "storage_type": "in_memory",
      "config": {}
    }
  }
}
```

### Environment-Based Configuration

If no flow-level configuration is provided, the system falls back to the default job stats storage backend configured via environment variables:

```bash
export DATASIFT_STORAGE_BACKEND=json  # or postgresql
export DATASIFT_JOB_STATS_BASE_DIR=/path/to/storage  # for file system storage
```

## Usage in Flows

### Enabling Incremental Processing

To enable incremental processing in your ingest operators, set the `incremental` parameter:

```json
{
  "operator_type": "datasift.core.operators.ingest.IngestLocalOperator",
  "operator_params": {
    "folder_path": "/path/to/documents",
    "incremental": true
  }
}
```

### Force Re-processing

To force re-processing of all documents (ignoring previous metadata):

```json
{
  "global_config": {
    "force_ingest": true
  }
}
```

### Retaining Deleted Documents

By default, documents that no longer exist in the source are marked as deleted. To retain them in the metadata:

```json
{
  "global_config": {
    "retain_deleted_docs": true
  }
}
```

## How It Works

1. **First Run**: All documents are processed and their metadata (doc_id, name, modified_time) is stored
2. **Subsequent Runs**: 
   - The system checks which documents have been processed before
   - Only new or modified documents (based on modified_time) are processed
   - Documents that no longer exist can be marked as deleted (unless `retain_deleted_docs` is true)

## Metadata Schema

Each processed document stores:
- `job_id`: Unique identifier for the job/flow
- `doc_id`: Unique identifier for the document
- `name`: Document filename or identifier
- `modified_time`: Last modification timestamp
- `job_run_id`: ID of the job run that processed this document
- `deleted`: Boolean flag indicating if the document was deleted from source

## Best Practices

### For Development
- Use **file_system** storage with a local directory
- Consider using `in_memory` storage for quick tests that don't need persistence

### For Production
- Use **postgresql** storage for distributed deployments
- Ensure PostgreSQL is properly configured with:
  - Adequate connection pooling
  - Regular backups
  - Monitoring and alerting
- Use shared filesystem (NFS, EFS) if using **file_system** storage with multiple workers

### For Kubernetes Deployments
- Use **postgresql** storage with a managed database service (RDS, Cloud SQL, etc.)
- If using **file_system** storage, mount a PersistentVolume with ReadWriteMany access mode

## Troubleshooting

### File Lock Timeout Errors
If you see file lock timeout errors with file_system storage:
- Increase the `lock_timeout` value
- Check for stale lock files in the `.locks` directory
- Ensure no zombie processes are holding locks

### PostgreSQL Connection Issues
- Verify database credentials and network connectivity
- Check PostgreSQL logs for connection errors
- Ensure the schema exists or the user has permission to create it

### Metadata Not Persisting
- For **in_memory** storage: This is expected behavior
- For **file_system** storage: Check directory permissions and disk space
- For **postgresql** storage: Verify database connectivity and transaction commits

## Migration Between Backends

To migrate from one storage backend to another:

1. **Export existing metadata** (if needed for historical tracking)
2. **Update flow configuration** with new storage backend
3. **Run with `force_ingest: true`** for the first run to rebuild metadata
4. **Remove `force_ingest`** for subsequent runs

## Performance Considerations

- **File System**: Performance degrades with very large numbers of files (>100K documents)
- **PostgreSQL**: Scales well to millions of documents with proper indexing
- **In-Memory**: Fastest but not persistent

## Security

### File System Storage
- Ensure proper file permissions on the metadata directory
- Use encrypted filesystems for sensitive data
- Restrict access to the metadata directory

### PostgreSQL Storage
- Use SSL/TLS for database connections
- Store credentials securely (environment variables, secrets management)
- Follow PostgreSQL security best practices
- Regularly update and patch PostgreSQL

## Related Documentation

- [Testing Incremental Metadata Adapters](TESTING_INCREMENTAL_METADATA_ADAPTERS.md) - Internal testing guide
- [Job Stats Management](job_stats_management/) - Related job statistics storage
- [Distributed Execution Guide](prefect/DISTRIBUTED_EXECUTION_GUIDE.md) - Multi-worker deployments