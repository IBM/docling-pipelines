# Docling-Serve Integration Tests

This directory contains integration tests for the `ExtractDoclingOperator` with docling-serve functionality.

> **Docling-Serve API compatibility:** These integration tests assume the Docling-Serve v1 API. Validation and troubleshooting steps below use the current v1 async endpoints and response fields.

## Prerequisites

### 1. Start Docling-Serve

You need a running docling-serve instance. The easiest way is using Docker:

```bash
# Start docling-serve on default port 5001
docker run -p 5001:5001 ds4sd/docling-serve:latest
```

### 2. Verify Docling-Serve is Running

```bash
# Check health endpoint
curl http://0.0.0.0:5001/health

# Optional: verify the v1 async API accepts file uploads
curl -X POST http://0.0.0.0:5001/v1/convert/file/async \
  -F "files=@/path/to/document.pdf" \
  -F "to_formats=md"
```

The v1 submit request should return a JSON payload containing a `task_id`.

### 3. Set Environment Variables (Optional)

If using a remote docling-serve instance:

```bash
export DOCLING_SERVE_URL="https://your-docling-serve.example.com"
```

## Running the Tests

### Run All Integration Tests

```bash
# From the backend directory
cd src/datasift_opensource/backend

# Activate the virtual environment
source .venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH="$(cd ../../.. && pwd)/src/datasift_opensource/backend:${PYTHONPATH}"

# Run all docling-serve integration tests
uv run pytest ../../../tests/integration/operators/extract/test_extract_docling_serve_integration.py -v
```

### Run Specific Test Classes

```bash
# Test basic extraction
uv run pytest ../../../tests/integration/operators/extract/test_extract_docling_serve_integration.py::TestDoclingServeBasicExtraction -v

# Test OCR functionality
uv run pytest ../../../tests/integration/operators/extract/test_extract_docling_serve_integration.py::TestDoclingServeOCR -v

# Test table extraction
uv run pytest ../../../tests/integration/operators/extract/test_extract_docling_serve_integration.py::TestDoclingServeTableExtraction -v

# Test batch processing
uv run pytest ../../../tests/integration/operators/extract/test_extract_docling_serve_integration.py::TestDoclingServeBatchProcessing -v

# Test error handling
uv run pytest ../../../tests/integration/operators/extract/test_extract_docling_serve_integration.py::TestDoclingServeErrorHandling -v

# Test configuration options
uv run pytest ../../../tests/integration/operators/extract/test_extract_docling_serve_integration.py::TestDoclingServeConfiguration -v
```

### Run Specific Test Methods

```bash
# Test basic extraction
uv run pytest ../../../tests/integration/operators/extract/test_extract_docling_serve_integration.py::TestDoclingServeBasicExtraction::test_docling_serve_basic_extraction -v

# Test OCR with enabled
uv run pytest ../../../tests/integration/operators/extract/test_extract_docling_serve_integration.py::TestDoclingServeOCR::test_docling_serve_with_ocr_enabled -v

# Test multiple documents
uv run pytest ../../../tests/integration/operators/extract/test_extract_docling_serve_integration.py::TestDoclingServeBatchProcessing::test_docling_serve_multiple_documents -v
```

### Run with Integration Marker

```bash
# Run all tests marked as integration
uv run pytest ../../../tests/integration/operators/extract/test_extract_docling_serve_integration.py -v -m integration
```

### Run with Verbose Output

```bash
# Show detailed output including print statements
uv run pytest ../../../tests/integration/operators/extract/test_extract_docling_serve_integration.py -v -s
```

## v1 API Expectations

These tests rely on the following Docling-Serve v1 behavior:

- **Submit endpoint:** `/v1/convert/file/async`
- **Status endpoint:** `/v1/status/poll/{task_id}`
- **Result endpoint:** `/v1/result/{task_id}`
- **Request format:** multipart/form-data file upload
- **Status field:** `task_status` with lowercase values such as `pending`, `processing`, and `success`
- **Result field:** extracted markdown under `document.md_content`

If your environment still exposes only the older `/convert/...` routes or expects base64 JSON payloads, these integration tests will not match the current client behavior.

## Test Coverage

The integration tests cover the following scenarios:

### 1. Basic Extraction (`TestDoclingServeBasicExtraction`)
- ✅ Basic document extraction
- ✅ Content validation
- ✅ Metadata verification
- ✅ Document hash generation

### 2. OCR Functionality (`TestDoclingServeOCR`)
- ✅ OCR-enabled extraction
- ✅ OCR-disabled extraction
- ✅ OCR engine configuration
- ✅ Language settings

### 3. Table Extraction (`TestDoclingServeTableExtraction`)
- ✅ Fast table extraction mode
- ✅ Accurate table extraction mode
- ✅ Table structure preservation

### 4. Batch Processing (`TestDoclingServeBatchProcessing`)
- ✅ Multiple document processing
- ✅ Unique document hashing
- ✅ Batch metadata tracking

### 5. Error Handling (`TestDoclingServeErrorHandling`)
- ✅ Invalid file handling
- ✅ Connection error handling
- ✅ Timeout handling
- ✅ Graceful failure recovery

### 6. Configuration Options (`TestDoclingServeConfiguration`)
- ✅ PDF backend selection (`dlparse_v4`, `dlparse_v3`, `pypdfium2`)
- ✅ Image export modes (`embedded`, `referenced`, `none`)
- ✅ Custom timeout values
- ✅ Polling interval configuration

## Skip Conditions

Tests will be automatically skipped if:

1. **Docling-serve is not running**: All tests require a running docling-serve instance
2. **Sample PDFs not found**: Tests requiring specific fixtures will skip if files are missing
3. **Insufficient test files**: Batch processing tests need at least 2 PDF files

## Troubleshooting

### Tests are Skipped

If tests are being skipped, check:

```bash
# Verify docling-serve is running
curl http://0.0.0.0:5001/health

# Check if it's running on a different port
docker ps | grep docling-serve

# Restart docling-serve if needed
docker run -p 5001:5001 ds4sd/docling-serve:latest
```

### Validate the v1 API Manually

If the tests cannot talk to docling-serve, verify the full v1 async flow:

```bash
# Submit a file
curl -X POST http://0.0.0.0:5001/v1/convert/file/async \
  -F "files=@/path/to/document.pdf" \
  -F "to_formats=md"

# Poll task status
curl http://0.0.0.0:5001/v1/status/poll/<task_id>

# Fetch result
curl http://0.0.0.0:5001/v1/result/<task_id>
```

Expected checks:
- submit returns a `task_id`
- polling returns `task_status`
- completed tasks report `task_status: "success"`
- markdown is returned under `document.md_content`

### Connection Errors

If you see connection errors:

1. Verify docling-serve is accessible:
   ```bash
   curl -v http://0.0.0.0:5001/health
   ```

2. Confirm the v1 submit endpoint responds:
   ```bash
   curl -X POST http://0.0.0.0:5001/v1/convert/file/async \
     -F "files=@/path/to/document.pdf" \
     -F "to_formats=md"
   ```

3. Check firewall settings

4. Try using localhost instead:
   ```bash
   export DOCLING_SERVE_URL="http://localhost:5001"
   ```

### Timeout Errors

If tests timeout:

1. Increase timeout in test configuration
2. Check docling-serve logs for processing issues
3. Confirm polling responses return `task_status` updates
4. Try with smaller or simpler PDF files

### Import Errors

If you see import errors:

```bash
# Ensure PYTHONPATH is set correctly
export PYTHONPATH="$(pwd)/src/datasift_opensource/backend:${PYTHONPATH}"

# Verify from backend directory
cd src/datasift_opensource/backend
source .venv/bin/activate
python -c "from common.constants.operator_constants import OperatorConstants; print('OK')"
```

## Test Fixtures

Tests use sample PDFs from `tests/fixtures/invoices/`:
- `TR-INV_044_1_1.1.pdf` - Primary test document
- `TR-INV_001_3_2.1.pdf` - Secondary test document
- `TR-INV_003_3_2.1.pdf` - Tertiary test document

## Performance Notes

- Basic extraction: ~2-5 seconds per document
- OCR-enabled extraction: ~5-15 seconds per document
- Accurate table mode: ~10-30 seconds per document
- Fast table mode: ~2-5 seconds per document

Actual times depend on:
- Document complexity
- Number of pages
- Table count
- Image count
- OCR requirements
- Server resources

## Additional Resources

- [Docling-Serve Documentation](https://github.com/DS4SD/docling-serve)
- [ExtractDoclingOperator Source](../../../../src/datasift_opensource/backend/core/operators/extract/extract_docling.py)
- [DoclingServeClient Source](../../../../src/datasift_opensource/backend/common/clients/docling_serve_client.py)
- [Example Usage](../../../../examples/extract_docling_serve_example.py)

## Made with Bob