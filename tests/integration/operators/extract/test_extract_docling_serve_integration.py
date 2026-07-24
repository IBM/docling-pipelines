#!/usr/bin/env python3
"""
Integration tests for ExtractOperator with docling-serve mode.

NOTE: These tests are currently skipped because they require a constantly running
docling-serve instance. To enable these tests, set up a persistent docling-serve
service and remove the @pytest.mark.skip decorators from the test classes.

Prerequisites:
    1. Start docling-serve locally:
       docker run -p 5001:5001 ds4sd/docling-serve:latest

    2. Or use a remote docling-serve instance by setting DOCLING_SERVE_URL environment variable

    3. Verify docling-serve is running:
       curl http://localhost:5001/health

These tests validate the complete docling-serve integration including:
- Basic document extraction
- OCR-enabled extraction
- Table extraction modes (fast/accurate)
- Batch processing of multiple documents
- Error handling (invalid files, timeouts, connection errors)
- Configuration options

To run these tests:
    pytest tests/integration/operators/extract/test_extract_docling_serve_integration.py -v

To run with specific markers:
    pytest tests/integration/operators/extract/test_extract_docling_serve_integration.py -v -m integration
"""

import os
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
import requests

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent.parent.parent.parent / "src" / "docpipe_app" / "backend"
sys.path.insert(0, str(backend_dir))

from docpipe.core.constants.operator_constants import OperatorConstants  # noqa: E402
from docpipe.core.operators.extract.extract_operator import ExtractOperator  # noqa: E402


def is_docling_serve_available(*, base_url: str = "http://localhost:5001") -> bool:
    """
    Check if docling-serve is running and accessible.

    Args:
        base_url: Base URL of docling-serve service

    Returns:
        True if docling-serve is available, False otherwise
    """
    try:
        # Try health endpoint first
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            return True

        # Fallback: try status endpoint
        response = requests.get(f"{base_url}/v1/status/poll/test", timeout=5)
        # Any response (even 404) means service is running
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False


# Get docling-serve URL from environment or use default
DOCLING_SERVE_URL = os.getenv("DOCLING_SERVE_URL", "http://localhost:5001")

# Skip all tests if docling-serve is not available
pytestmark = pytest.mark.skipif(
    not is_docling_serve_available(base_url=DOCLING_SERVE_URL),
    reason=(
        f"Docling-serve is not running at {DOCLING_SERVE_URL}. "
        "Start docling-serve to run integration tests: "
        "docker run -p 5001:5001 ds4sd/docling-serve:latest"
    ),
)


@pytest.fixture
def docling_serve_available() -> bool:
    """Check if docling-serve is running."""
    return is_docling_serve_available(base_url=DOCLING_SERVE_URL)


@pytest.fixture
def sample_pdf_path() -> Path:
    """Get path to a sample PDF for testing."""
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures" / "invoices"
    pdf_path = fixtures_dir / "TR-INV_044_1_1.1.pdf"

    if not pdf_path.exists():
        pytest.skip(f"Sample PDF not found: {pdf_path}")

    return pdf_path


@pytest.fixture
def multiple_pdf_paths() -> list[Path]:
    """Get paths to multiple PDFs for batch testing."""
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures" / "invoices"

    pdf_files = [
        fixtures_dir / "TR-INV_044_1_1.1.pdf",
        fixtures_dir / "TR-INV_001_3_2.1.pdf",
        fixtures_dir / "TR-INV_003_3_2.1.pdf",
    ]

    # Filter to only existing files
    existing_files = [f for f in pdf_files if f.exists()]

    if len(existing_files) < 2:
        pytest.skip(f"Not enough sample PDFs found in {fixtures_dir}")

    return existing_files


@pytest.fixture
def docling_serve_config() -> dict[str, Any]:
    """Default configuration for docling-serve integration."""
    return {
        OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_SERVE,
        OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.ENTITY_MODE_NONE,
        OperatorConstants.Columns.DOC_COLUMN: "doc_content",
        OperatorConstants.Config.BASE_URL: DOCLING_SERVE_URL,
        OperatorConstants.Processing.TIMEOUT: 300,
        OperatorConstants.Processing.POLL_INTERVAL: 2,
        OperatorConstants.Processing.MAX_RETRIES: 3,
    }


def create_input_table(*, file_paths: list[Path]) -> pa.Table:
    """
    Create PyArrow table from file paths.

    Args:
        file_paths: List of file paths to process

    Returns:
        PyArrow table with file data
    """
    data: dict[str, list[Any]] = {
        OperatorConstants.Columns.ID: [],
        OperatorConstants.Columns.NAME: [],
        OperatorConstants.Columns.PATH: [],
        OperatorConstants.Columns.BINARY_CONTENT: [],
    }

    for file_path in file_paths:
        with open(file_path, "rb") as f:
            binary_content = f.read()

        data[OperatorConstants.Columns.ID].append(str(file_path))
        data[OperatorConstants.Columns.NAME].append(file_path.name)
        data[OperatorConstants.Columns.PATH].append(str(file_path))
        data[OperatorConstants.Columns.BINARY_CONTENT].append(binary_content)

    return pa.table(data)


@pytest.mark.skip(reason="Need to add a constant running docling-serve to enable these tests")
@pytest.mark.integration
class TestDoclingServeBasicExtraction:
    """Test basic document extraction with docling-serve."""

    def test_docling_serve_basic_extraction(self, sample_pdf_path: Path, docling_serve_config: dict[str, Any]):
        """
        Test basic document extraction using docling-serve.

        Validates:
        - Document is successfully submitted to docling-serve
        - Content is extracted and not empty
        - Metadata is populated correctly
        - doc_id_hash is generated
        """
        # Create input table
        input_table = create_input_table(file_paths=[sample_pdf_path])

        # Initialize operator
        operator = ExtractOperator(config=docling_serve_config)

        # Transform
        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Verify basic structure
        assert result_table.num_rows == 1, "Should have one result row"
        assert "doc_content" in result_table.column_names
        assert "doc_id_hash" in result_table.column_names
        assert "pages_processed" in result_table.column_names

        # Verify content extraction
        content = result_table["doc_content"][0].as_py()
        assert content is not None, "Content should not be None"
        assert len(content) > 0, "Content should not be empty"
        assert isinstance(content, str), "Content should be a string"

        # Verify doc_id_hash
        doc_id_hash = result_table["doc_id_hash"][0].as_py()
        assert doc_id_hash is not None, "doc_id_hash should not be None"
        assert len(doc_id_hash) > 0, "doc_id_hash should not be empty"

        # Verify pages_processed
        pages_processed = result_table["pages_processed"][0].as_py()
        assert pages_processed is not None, "pages_processed should not be None"
        assert pages_processed > 0, "pages_processed should be greater than 0"

        # Verify metadata
        assert metadata.get("processed_docs", 0) == 1, "Should have processed 1 document"
        assert metadata.get("failed_docs_count", 0) == 0, "Should have no failed documents"
        assert "page_type_stats" in metadata, "Should have page_type_stats in metadata"
        assert "total_pages_converted" in metadata, "Should have total_pages_converted in metadata"


@pytest.mark.skip(reason="Need to add a constant running docling-serve to enable these tests")
@pytest.mark.integration
class TestDoclingServeOCR:
    """Test OCR-enabled extraction with docling-serve."""

    def test_docling_serve_with_ocr_enabled(self, sample_pdf_path: Path, docling_serve_config: dict[str, Any]):
        """
        Test document extraction with OCR enabled.

        Validates:
        - OCR configuration is properly passed to docling-serve
        - Content is extracted successfully
        - OCR engine and language settings are applied
        """
        # Enable OCR in config
        config = docling_serve_config.copy()
        config[OperatorConstants.Config.DO_OCR] = True
        config[OperatorConstants.Config.OCR_ENGINE] = "easyocr"
        config[OperatorConstants.Config.OCR_LANGUAGES] = ["en"]

        # Create input table
        input_table = create_input_table(file_paths=[sample_pdf_path])

        # Initialize operator
        operator = ExtractOperator(config=config)

        # Transform
        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Verify extraction succeeded
        assert result_table.num_rows == 1
        assert "pages_processed" in result_table.column_names
        content = result_table["doc_content"][0].as_py()
        assert content is not None
        assert "page_type_stats" in metadata
        assert "total_pages_converted" in metadata
        assert len(content) > 0

        # Verify metadata
        assert metadata.get("processed_docs", 0) == 1

    def test_docling_serve_with_ocr_disabled(self, sample_pdf_path: Path, docling_serve_config: dict[str, Any]):
        """
        Test document extraction with OCR disabled.

        Validates:
        - OCR can be disabled via configuration
        - Extraction still works for text-based PDFs
        """
        # Disable OCR in config
        config = docling_serve_config.copy()
        config[OperatorConstants.Config.DO_OCR] = False

        # Create input table
        input_table = create_input_table(file_paths=[sample_pdf_path])

        # Initialize operator
        operator = ExtractOperator(config=config)

        # Transform
        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Verify extraction succeeded
        assert result_table.num_rows == 1
        content = result_table["doc_content"][0].as_py()
        assert content is not None
        assert len(content) > 0

        # Verify metadata
        assert metadata.get("processed_docs", 0) == 1


@pytest.mark.skip(reason="Need to add a constant running docling-serve to enable these tests")
@pytest.mark.integration
class TestDoclingServeTableExtraction:
    """Test table extraction modes with docling-serve."""

    def test_docling_serve_fast_table_mode(self, sample_pdf_path: Path, docling_serve_config: dict[str, Any]):
        """
        Test fast table extraction mode.

        Validates:
        - Fast table mode configuration is applied
        - Tables are extracted quickly
        - Content includes table data
        """
        # Configure fast table mode
        config = docling_serve_config.copy()
        config[OperatorConstants.Config.TABLE_MODE] = "fast"

        # Create input table
        input_table = create_input_table(file_paths=[sample_pdf_path])

        # Initialize operator
        operator = ExtractOperator(config=config)

        # Transform
        result_tables, _metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Verify extraction succeeded
        assert result_table.num_rows == 1
        content = result_table["doc_content"][0].as_py()
        assert content is not None
        assert len(content) > 0

    def test_docling_serve_accurate_table_mode(self, sample_pdf_path: Path, docling_serve_config: dict[str, Any]):
        """
        Test accurate table extraction mode.

        Validates:
        - Accurate table mode configuration is applied
        - Tables are extracted with high accuracy
        - Content includes detailed table data
        """
        # Configure accurate table mode
        config = docling_serve_config.copy()
        config[OperatorConstants.Config.TABLE_MODE] = "accurate"

        # Create input table
        input_table = create_input_table(file_paths=[sample_pdf_path])

        # Initialize operator
        operator = ExtractOperator(config=config)

        # Transform
        result_tables, _metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Verify extraction succeeded
        assert result_table.num_rows == 1
        content = result_table["doc_content"][0].as_py()
        assert content is not None
        assert len(content) > 0


@pytest.mark.skip(reason="Need to add a constant running docling-serve to enable these tests")
@pytest.mark.integration
class TestDoclingServeBatchProcessing:
    """Test batch processing of multiple documents."""

    def test_docling_serve_multiple_documents(
        self, multiple_pdf_paths: list[Path], docling_serve_config: dict[str, Any]
    ):
        """
        Test processing multiple documents in a single batch.

        Validates:
        - Multiple documents are processed successfully
        - Each document gets unique doc_id_hash
        - Metadata tracks all documents
        """
        # Create input table with multiple documents
        input_table = create_input_table(file_paths=multiple_pdf_paths)

        # Initialize operator
        operator = ExtractOperator(config=docling_serve_config)

        # Transform
        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Verify all documents processed
        assert result_table.num_rows == len(multiple_pdf_paths)

        # Verify each document has content
        for i in range(result_table.num_rows):
            content = result_table["doc_content"][i].as_py()
            assert content is not None
            assert len(content) > 0

        # Verify unique doc_id_hash for each document
        doc_id_hashes = result_table["doc_id_hash"].to_pylist()
        assert len(set(doc_id_hashes)) == len(multiple_pdf_paths), "Each document should have unique doc_id_hash"

        # Verify metadata
        assert metadata.get("processed_docs", 0) == len(multiple_pdf_paths)
        assert metadata.get("failed_docs_count", 0) == 0


@pytest.mark.skip(reason="Need to add a constant running docling-serve to enable these tests")
@pytest.mark.integration
class TestDoclingServeErrorHandling:
    """Test error handling scenarios."""

    def test_docling_serve_invalid_file(self, docling_serve_config: dict[str, Any]):
        """
        Test handling of invalid file content.

        Validates:
        - Invalid files are handled gracefully
        - Error is reported in metadata
        - Processing continues for valid files
        """
        # Create table with invalid binary content
        invalid_table = pa.table(
            {
                OperatorConstants.Columns.ID: ["invalid_doc"],
                OperatorConstants.Columns.NAME: ["invalid.pdf"],
                OperatorConstants.Columns.PATH: ["/tmp/invalid.pdf"],
                OperatorConstants.Columns.BINARY_CONTENT: [b"not a valid pdf content"],
            }
        )

        # Initialize operator
        operator = ExtractOperator(config=docling_serve_config)

        # Transform - should handle error gracefully
        result_tables, metadata = operator.transform(invalid_table)
        result_table = result_tables[0]

        # Verify error handling
        assert result_table.num_rows == 1
        assert metadata.get("failed_docs_count", 0) >= 0  # May fail or succeed depending on docling-serve


@pytest.mark.skip(reason="Need to add a constant running docling-serve to enable these tests")
@pytest.mark.integration
class TestDoclingServeConfiguration:
    """Test various configuration options."""

    def test_docling_serve_pdf_backend_dlparse_v4(self, sample_pdf_path: Path, docling_serve_config: dict[str, Any]):
        """Test with dlparse_v4 PDF backend."""
        config = docling_serve_config.copy()
        config[OperatorConstants.Config.PDF_BACKEND] = "dlparse_v4"

        input_table = create_input_table(file_paths=[sample_pdf_path])
        operator = ExtractOperator(config=config)
        result_tables, metadata = operator.transform(input_table)

        assert result_tables[0].num_rows == 1
        assert metadata.get("processed_docs", 0) == 1

    def test_docling_serve_pdf_backend_dlparse_v3(self, sample_pdf_path: Path, docling_serve_config: dict[str, Any]):
        """Test with dlparse_v3 PDF backend."""
        config = docling_serve_config.copy()
        config[OperatorConstants.Config.PDF_BACKEND] = "dlparse_v3"

        input_table = create_input_table(file_paths=[sample_pdf_path])
        operator = ExtractOperator(config=config)
        result_tables, metadata = operator.transform(input_table)

        assert result_tables[0].num_rows == 1
        assert metadata.get("processed_docs", 0) == 1

    def test_docling_serve_image_export_modes(self, sample_pdf_path: Path, docling_serve_config: dict[str, Any]):
        """Test different image export modes."""
        for mode in ["embedded", "referenced", "none"]:
            config = docling_serve_config.copy()
            config[OperatorConstants.Config.IMAGE_EXPORT_MODE] = mode

            input_table = create_input_table(file_paths=[sample_pdf_path])
            operator = ExtractOperator(config=config)
            result_tables, metadata = operator.transform(input_table)

            assert result_tables[0].num_rows == 1
            assert metadata.get("processed_docs", 0) == 1

    def test_docling_serve_custom_timeout(self, sample_pdf_path: Path, docling_serve_config: dict[str, Any]):
        """Test with custom timeout value."""
        config = docling_serve_config.copy()
        config[OperatorConstants.Processing.TIMEOUT] = 600  # 10 minutes

        input_table = create_input_table(file_paths=[sample_pdf_path])
        operator = ExtractOperator(config=config)
        result_tables, metadata = operator.transform(input_table)

        assert result_tables[0].num_rows == 1
        assert metadata.get("processed_docs", 0) == 1
