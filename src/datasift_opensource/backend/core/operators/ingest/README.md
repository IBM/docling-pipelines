# Ingest Operators

## Overview

The `IngestLocalOperator` is a metadata-only operator for ingesting documents from local file systems. It discovers files, collects metadata, and optionally stores binary content for downstream extraction operators.

**Key Principle**: This operator does NOT extract text content. Content extraction is handled by specialized operators like `ExtractOperator`.
This directory also includes source adapters used by `IngestSourceOperator`, including the web page adapter for recursive crawling with LangChain `RecursiveUrlLoader`.

## Features

- Discovers files through recursive directory traversal
- Collects file metadata (id, name, size, timestamps)
- Stores file paths for downstream access
- Optionally stores binary content for extraction
- Supports file filtering by extension (include/exclude)
- Enforces file size and count limits
- Supports incremental updates (skip previously processed files)
- Works with all file types (not limited to specific formats)

## Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input_folder` | string | `"../test-data/input"` | Path to the folder containing documents to ingest |
| `include_filter` | string | `None` | Comma-separated list of file extensions to include (e.g., "pdf,docx,txt") |
| `exclude_filter` | string | `None` | Comma-separated list of file extensions to exclude |
| `max_files` | integer | `100` | Maximum number of files to ingest |
| `max_file_size` | integer | `100` | Maximum file size in MB (files larger than this are skipped) |
| `store_binary_content` | boolean | `true` | Whether to store binary content for downstream extraction |
| `force_ingest` | boolean | `false` | Force re-ingestion of previously processed documents |
| `retain_deleted_docs` | boolean | `true` | Whether to retain documents that have been deleted from the source |

## Output Schema

| Column | Type | Description |
|--------|------|-------------|
| `id` | string | Document ID (file inode) |
| `name` | string | File path |
| `path` | string | Absolute file path |
| `binary_content` | bytes | Raw file content (if `store_binary_content=True`) |
| `size` | integer | File size in bytes |
| `created_time` | integer | Creation timestamp (Unix epoch) |
| `modified_time` | integer | Modification timestamp (Unix epoch) |

## Usage Examples

### Example 1: Basic Metadata-Only Mode with Binary Content

```python
from core.operators.universal.ingest.ingest_local_folder import IngestLocalOperator

config = {
    "input_folder": "data/documents",
    "include_filter": "pdf,docx,pptx",
    "store_binary_content": True,
    "max_files": 100
}

operator = IngestLocalOperator(config)
tables, metadata = operator.transform(None)
table = tables[0]

print(f"Ingested {table.num_rows} documents")
print(f"Columns: {table.column_names}")
```

### Example 2: Path-Only Mode (No Binary Content)

```python
config = {
    "input_folder": "data/documents",
    "include_filter": "pdf",
    "store_binary_content": False,  # Only store paths
    "max_files": 50
}

operator = IngestLocalOperator(config)
tables, metadata = operator.transform(None)
```

### Example 3: Sequential Flow with ExtractDocling

```python
from core.operators.universal.ingest.ingest_local_folder import IngestLocalOperator
from operators.universal.extract.extract_operator_operator import ExtractOperator

# Step 1: Ingest metadata
ingest_config = {
    "input_folder": "data/invoices",
    "include_filter": "pdf",
    "store_binary_content": True
}

ingest_op = IngestLocalOperator(ingest_config)
ingest_tables, _ = ingest_op.transform(None)

# Step 2: Extract content with Docling
extract_config = {
    "doc_column": "content",
    "extract_tables": True,
    "extract_images": True
}

extract_op = ExtractOperator(extract_config)
extract_tables, _ = extract_op.transform(ingest_tables[0])

result_table = extract_tables[0]
print(f"Extracted content from {result_table.num_rows} documents")
```

## File Filtering

### Include Filter
Specify file extensions to include (comma-separated):
```python
config = {
    "include_filter": "pdf,docx,pptx,txt"
}
```

### Exclude Filter
Specify file extensions to exclude (comma-separated):
```python
config = {
    "exclude_filter": "tmp,bak,log"
}
```

### Combined Filtering
You can use both include and exclude filters together:
```python
config = {
    "include_filter": "pdf,docx",  # Only PDF and DOCX
    "exclude_filter": "draft"      # But exclude files with .draft extension
}
```

## Incremental Updates

The operator supports incremental updates by tracking previously processed documents:

```python
config = {
    "input_folder": "data/documents",
    "force_ingest": False,  # Skip previously processed documents
    "retain_deleted_docs": True  # Keep records of deleted files
}
```

- `force_ingest=False`: Only processes new or modified documents
- `force_ingest=True`: Re-processes all documents regardless of previous state

## Error Handling

The operator handles various error scenarios:

1. **File Size Exceeded**: Files larger than `max_file_size` are skipped
2. **File Count Exceeded**: Processing stops after `max_files` documents
3. **Read Errors**: Files that cannot be read are logged and skipped

Metadata includes counts of:
- `total_docs`: Total files found
- `processed_docs`: Successfully processed files
- `failed_docs`: Files that failed processing
- `skipped_docs`: Files skipped due to filters or constraints

## Performance Considerations

### Memory Usage

**With Binary Content** (`store_binary_content=True`):
- Higher memory usage
- Faster downstream extraction (no file I/O)
- Recommended for small to medium datasets

**Path-Only** (`store_binary_content=False`):
- Lower memory usage
- Requires file access during extraction
- Recommended for large datasets or when files are on fast storage

### Batch Processing

For very large datasets, consider:
1. Using `max_files` to process in batches
2. Setting `store_binary_content=False` to reduce memory
3. Processing subdirectories separately

## Sequential Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ IngestLocalOperator (Metadata-Only)                         │
│                                                              │
│ Input: None                                                  │
│ Output: PyArrow Table with:                                 │
│   - id: Document ID (inode)                                 │
│   - name: File path                                         │
│   - path: Absolute file path                                │
│   - binary_content: Raw file bytes (optional)               │
│   - size: File size                                         │
│   - created_time: Creation timestamp                        │
│   - modified_time: Modification timestamp                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ ExtractOperator                                       │
│                                                              │
│ Input: PyArrow Table from IngestLocal                       │
│ Output: PyArrow Table with:                                 │
│   - All columns from input                                  │
│   - content: Extracted markdown text                        │
│   - doc_id_hash: Document hash ID                           │
│   - extracted_data: Structured data (if template used)      │
└─────────────────────────────────────────────────────────────┘
```

## Testing

### Prerequisites

Before running tests, ensure:

1. **Virtual environment is activated**:
   ```bash
   cd src/datasift_opensource/backend
   source venv/bin/activate
   ```

2. **PYTHONPATH is set**:
   ```bash
   export PYTHONPATH="${PYTHONPATH}:$(pwd)/src/datasift_opensource/backend"
   ```

3. **Test fixtures exist**:
   ```bash
   ls tests/fixtures/invoices/  # Should contain PDF files
   ```

### Unit Tests

Test the ingest operator in isolation:

```bash
# All ingest unit tests
pytest tests/unit/operators/ingest/ -v

# Specific test file
pytest tests/unit/operators/ingest/test_ingest_local.py -v

# Single test
pytest tests/unit/operators/ingest/test_ingest_local.py::TestIngestLocalOperator::test_metadata_only_mode -v

# With output
pytest tests/unit/operators/ingest/test_ingest_local.py -v -s
```

### Integration Tests

Test the ingest operator with downstream operators:

```bash
# Ingest + Extract integration
pytest tests/integration/test_ingest_extract_integration.py -v

# Full pipeline (Ingest + Extract + Chunking)
pytest tests/integration/test_full_pipeline_integration.py -v

# Specific integration test
pytest tests/integration/test_full_pipeline_integration.py::TestFullPipelineIntegration::test_ingest_extract_chunk_pipeline -v
```

### Running from Repository Root

```bash
# From /Users/adityars/codebase/datasift-opensource
cd src/datasift_opensource/backend
source venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Run all ingest-related tests
pytest tests/unit/operators/ingest/ tests/integration/test_ingest_extract_integration.py -v
```

## Related Operators

- **ExtractOperator**: Advanced extraction using Docling library
- **DoclingChunkerOperator**: Chunks extracted content for vector databases
- **IngestSourceOperator**: Multi-provider ingest supporting S3, IBM COS, SharePoint, OneDrive, Google Drive, web pages, and custom loaders

## Support

For issues or questions:
1. Check the integration tests for usage examples
2. Review the operator source code for implementation details
3. Refer to the main project documentation