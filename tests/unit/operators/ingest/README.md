# Ingest Operator Tests

This directory contains unit tests for the ingest operators.

## Test Files

### test_ingest_source.py

Comprehensive test suite for [`IngestSourceOperator`](../../../../src/docpipe/core/operators/ingest/ingest_source.py) covering all major functionality.

## Test Coverage

The test suite includes **26 test cases** organized into the following categories:

### 1. Initialization Tests (6 tests)
Tests for proper operator initialization with different providers:
- ✅ S3 provider initialization
- ✅ IBM COS provider initialization
- ✅ Google Drive provider initialization
- ✅ SharePoint provider initialization
- ✅ OneDrive provider initialization
- ✅ Custom provider initialization

### 2. Loader Factory Tests (8 tests)
Tests for the [`_get_loader()`](../../../../src/docpipe/core/operators/ingest/ingest_source.py) method:
- ✅ S3DirectoryLoader creation for S3
- ✅ S3DirectoryLoader with endpoint for IBM COS
- ✅ GoogleDriveLoader creation with token directory setup
- ✅ SharePointLoader creation
- ✅ OneDriveLoader creation
- ✅ Custom loader dynamic import
- ✅ Error handling for missing custom loader path
- ✅ Error handling for unsupported providers

### 3. S3 File Filtering Tests (5 tests)
Tests for the [`_get_s3_file_keys()`](../../../../src/docpipe/core/operators/ingest/ingest_source.py) method:
- ✅ Basic file key retrieval
- ✅ Filtering hidden files (starting with `.`)
- ✅ Filtering zero-size files
- ✅ IBM COS endpoint URL configuration
- ✅ Empty bucket handling

### 4. Transform Method Tests (6 tests)
Tests for the main [`transform()`](../../../../src/docpipe/core/operators/ingest/ingest_source.py) method:
- ✅ Successful document processing
- ✅ Empty document list handling
- ✅ Error handling and graceful degradation
- ✅ Output schema validation
- ✅ Google Drive provider integration
- ✅ Documents without source metadata

### 5. Integration Tests (1 test)
End-to-end pipeline tests:
- ✅ Complete S3 to PyArrow table pipeline

## Running the Tests

Run all tests in this file:
```bash
python -m pytest tests/unit/operators/ingest/test_ingest_source.py -v
```

Run specific test class:
```bash
python -m pytest tests/unit/operators/ingest/test_ingest_source.py::TestTransform -v
```

Run specific test:
```bash
python -m pytest tests/unit/operators/ingest/test_ingest_source.py::TestTransform::test_transform_success -v
```

Run with coverage:
```bash
python -m pytest tests/unit/operators/ingest/test_ingest_source.py --cov=operators.universal.ingest.ingest_source --cov-report=html
```

## Test Fixtures

### `mock_documents`
Provides sample LangChain Document objects for testing:
- 3 documents with different content and metadata
- Includes source and page information

### `empty_input_table`
Provides an empty PyArrow table used as input trigger for the operator.

## Mocking Strategy

The tests use `unittest.mock` to mock external dependencies:
- **LangChain loaders**: S3DirectoryLoader, GoogleDriveLoader, etc.
- **boto3 client**: For S3 operations
- **File system operations**: os.path.exists, os.makedirs
- **Dynamic imports**: importlib.import_module

This approach ensures:
- Tests run quickly without external dependencies
- No actual cloud service calls are made
- Tests are deterministic and reliable
- Easy to test error conditions

## Key Test Patterns

### 1. Provider-Specific Tests
Each provider (S3, IBM COS, Google Drive, SharePoint, OneDrive, Custom) has dedicated tests ensuring proper configuration and loader initialization.

### 2. Error Handling Tests
Tests verify graceful error handling:
- Missing required parameters
- Unsupported providers
- Loader exceptions
- Empty results

### 3. Data Validation Tests
Tests ensure output data integrity:
- Correct PyArrow schema
- JSON-serialized metadata
- Proper source_id extraction
- Handling of missing metadata fields

### 4. Integration Tests
End-to-end tests verify the complete pipeline from document loading to PyArrow table creation.

## Expected Output Schema

The operator produces PyArrow tables with the following schema:
```python
pa.schema([
    ('text', pa.string()),        # Document content
    ('metadata', pa.string()),    # JSON-serialized metadata
    ('source_id', pa.string())    # Source identifier
])
```

## Notes

- All tests pass successfully (26/26)
- Tests use mocking to avoid external dependencies
- Tests follow the same pattern as existing operator tests
- Coverage includes happy paths, edge cases, and error conditions
