#!/usr/bin/env python3
"""
Unit tests for extract_docling_operator.
Tests the operator with sample PDF files from the fixtures directory.
"""

import pytest
import json
from pathlib import Path

# Path setup is now automatic via conftest.py


@pytest.mark.unit
def test_extract_docling_basic(sample_pdf_files):
    """Test the ExtractDoclingOperator with basic extraction."""
    import pyarrow as pa
    from core.operators.extract.extract_docling import ExtractDoclingOperator

    # Use fixture for test files (automatically skips if not found)
    test_files = sample_pdf_files[:1]  # Test with first file

    # Prepare data for PyArrow table
    file_data = {"id": [], "name": [], "path": [], "binary_content": []}

    for file_path in test_files:
        with open(file_path, "rb") as f:
            binary_content = f.read()

        file_data["id"].append(str(file_path))
        file_data["name"].append(file_path.name)
        file_data["path"].append(str(file_path))
        file_data["binary_content"].append(binary_content)

    # Create PyArrow table
    table = pa.table(file_data)
    assert table.num_rows > 0, "Table should have rows"

    # Initialize operator with basic configuration
    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "extract_tables": True,
        "extract_images": True,
        "use_template": False,
    }

    operator = ExtractDoclingOperator(config)

    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    # Assertions
    assert "content" in result_table.column_names, "Content column should exist"
    assert "doc_id_hash" in result_table.column_names, "Hash ID column should exist"
    assert "extracted_data" not in result_table.column_names, (
        "Extracted_data column should not exist for basic extraction"
    )

    # Check content
    first_content = result_table["content"][0].as_py()
    assert first_content is not None, "Content should not be None"
    assert len(first_content) > 0, "Content should not be empty"

    # Check hash
    first_hash = result_table["doc_id_hash"][0].as_py()
    assert first_hash is not None, "Hash should not be None"
    assert len(first_hash) > 0, "Hash should not be empty"

    # Check metadata
    assert metadata["total_docs_count"] == table.num_rows, (
        "Total docs should match input rows"
    )
    assert metadata["processed_docs"] > 0, "Should have processed at least one document"


@pytest.mark.unit
@pytest.mark.skip(reason="Need to download the model for this test to run")
def test_extract_docling_with_template(sample_pdf_files):
    """Test the ExtractDoclingOperator with template extraction."""
    import pyarrow as pa
    from core.operators.extract.extract_docling import ExtractDoclingOperator

    # Check if DocumentExtractor is available
    try:
        from docling.document_extractor import DocumentExtractor  # noqa: F401
    except ImportError:
        pytest.skip(
            "DocumentExtractor not available. Install with: pip install docling[vlm]"
        )

    # Use fixture for test files (automatically skips if not found)
    test_files = sample_pdf_files[:1]  # Test with first file

    # Prepare data for PyArrow table
    file_data = {"id": [], "name": [], "path": [], "binary_content": []}

    for file_path in test_files:
        with open(file_path, "rb") as f:
            binary_content = f.read()

        file_data["id"].append(str(file_path))
        file_data["name"].append(file_path.name)
        file_data["path"].append(str(file_path))
        file_data["binary_content"].append(binary_content)

    # Create PyArrow table
    table = pa.table(file_data)

    # Define invoice template for structured extraction
    invoice_template = {
        "invoice_number": "string",
        "invoice_date": "string",
        "payment_due": "string",
        "bill_to": "string",
        "vendor_name": "string",
        "vendor_address": "string",
        "subtotal": "float",
        "tax": "float",
        "total": "float",
        "grand_total": "float",
    }

    # Initialize operator with template configuration
    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "extract_tables": True,
        "extract_images": True,
        "use_template": True,
        "template": invoice_template,
    }

    operator = ExtractDoclingOperator(config)

    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    # Assertions
    assert "content" in result_table.column_names, "Content column should exist"
    assert "doc_id_hash" in result_table.column_names, "Hash ID column should exist"
    assert "extracted_data" in result_table.column_names, (
        "Extracted_data column should exist for template extraction"
    )

    # Check content
    first_content = result_table["content"][0].as_py()
    assert first_content is not None, "Content should not be None"

    # Check extracted_data
    first_extracted = result_table["extracted_data"][0].as_py()
    if first_extracted:  # May be None if extraction failed
        extracted_dict = json.loads(first_extracted)
        assert isinstance(extracted_dict, list), "Extracted data should be a list"
        assert len(extracted_dict) > 0, "Extracted data should have at least one page"

        # Check structure of first page
        first_page = extracted_dict[0]
        assert "page_no" in first_page, "Page should have page_no"
        assert "extracted_data" in first_page, "Page should have extracted_data"

    # Check hash
    first_hash = result_table["doc_id_hash"][0].as_py()
    assert first_hash is not None, "Hash should not be None"

    # Check metadata
    assert metadata["total_docs_count"] == table.num_rows, (
        "Total docs should match input rows"
    )


@pytest.mark.skip(reason="Running into OOM on Jenkins")
def test_extract_docling_with_expand_extracted_data():
    """Test the ExtractDoclingOperator with expand_extracted_data flag."""
    import pyarrow as pa
    from core.operators.extract.extract_docling import ExtractDoclingOperator
    import pytest

    # Check if DocumentExtractor is available
    try:
        from docling.document_extractor import DocumentExtractor  # noqa: F401
    except ImportError:
        pytest.skip(
            "DocumentExtractor not available. Install with: pip install docling[vlm]"
        )

    # Get test files
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures" / "invoices"
    test_files = list(fixtures_dir.glob("*.pdf"))[:1]  # Test with first file

    assert len(test_files) > 0, f"No PDF files found in {fixtures_dir}"

    # Prepare data for PyArrow table
    file_data = {"id": [], "name": [], "path": [], "binary_content": []}

    for file_path in test_files:
        with open(file_path, "rb") as f:
            binary_content = f.read()

        file_data["id"].append(str(file_path))
        file_data["name"].append(file_path.name)
        file_data["path"].append(str(file_path))
        file_data["binary_content"].append(binary_content)

    # Create PyArrow table
    table = pa.table(file_data)

    # Define invoice template for structured extraction
    invoice_template = {
        "invoice_number": "string",
        "invoice_date": "string",
        "payment_due": "string",
        "bill_to": "string",
        "vendor_name": "string",
        "vendor_address": "string",
        "subtotal": "float",
        "tax": "float",
        "total": "float",
        "grand_total": "float",
    }

    # Initialize operator with template configuration and expand_extracted_data flag
    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "extract_tables": True,
        "extract_images": True,
        "use_template": True,
        "template": invoice_template,
        "expand_extracted_data": True,  # Enable expansion
    }

    operator = ExtractDoclingOperator(config)

    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    # Assertions
    assert "content" in result_table.column_names, "Content column should exist"
    assert "doc_id_hash" in result_table.column_names, "Hash ID column should exist"

    # When expand_extracted_data is True, individual columns should be created
    # Check for at least some of the expected expanded columns
    expected_prefixes = ["extracted_"]
    has_expanded_columns = any(
        col.startswith(prefix)
        for col in result_table.column_names
        for prefix in expected_prefixes
    )

    # Note: The test may not always have expanded columns if extraction fails
    # So we check if either expanded columns exist OR extracted_data exists
    has_data = has_expanded_columns or "extracted_data" in result_table.column_names
    assert has_data, "Should have either expanded columns or extracted_data column"

    # Check metadata
    assert metadata["total_docs_count"] == table.num_rows, (
        "Total docs should match input rows"
    )


def test_get_metadata():
    """Test the get_metadata static method."""
    from core.operators.extract.extract_docling import ExtractDoclingOperator

    # Create an instance with minimal config to call get_metadata
    config = {"doc_column": "content", "doc_id_hash": "doc_id_hash"}
    operator = ExtractDoclingOperator(config)

    # Call the instance method
    metadata = operator.get_metadata()

    # Assertions
    assert isinstance(metadata, dict), "Metadata should be a dictionary"
    assert "category" in metadata, "Metadata should have 'category' key"
    assert "features" in metadata, "Metadata should have 'features' key"
    assert "attributes" in metadata, "Metadata should have 'attributes' key"
    assert "is_operator_available" in metadata, (
        "Metadata should have 'is_operator_available' key"
    )

    # Check features
    features = metadata["features"]
    assert "content" in features, "Features should include 'content'"
    assert "doc_id_hash" in features, "Features should include 'doc_id_hash'"
    assert "extracted_data" in features, "Features should include 'extracted_data'"

    # Check attributes
    attributes = metadata["attributes"]
    assert "doc_column" in attributes, "Attributes should include 'doc_column'"
    assert "use_template" in attributes, "Attributes should include 'use_template'"
    assert "expand_extracted_data" in attributes, (
        "Attributes should include 'expand_extracted_data'"
    )

    # Check expand_extracted_data attribute details
    expand_attr = attributes["expand_extracted_data"]
    assert expand_attr["name"] == "Expand Extracted Data", "Attribute name should match"
    assert expand_attr["type"] == "boolean", "Attribute type should be boolean"
    assert expand_attr["default"] is False, "Default should be False"


def test_extract_docling_txt_files():
    """Test the ExtractDoclingOperator with .txt files."""
    import pyarrow as pa
    from core.operators.extract.extract_docling import ExtractDoclingOperator

    # Get test .txt files
    fixtures_dir = (
        Path(__file__).parent.parent.parent.parent
        / "fixtures"
        / "customer_support_docs"
    )
    test_files = list(fixtures_dir.glob("*.txt"))[:2]  # Test with first 2 txt files

    assert len(test_files) > 0, f"No TXT files found in {fixtures_dir}"

    # Prepare data for PyArrow table
    file_data = {"id": [], "name": [], "path": [], "binary_content": []}

    for file_path in test_files:
        with open(file_path, "rb") as f:
            binary_content = f.read()

        file_data["id"].append(str(file_path))
        file_data["name"].append(file_path.name)
        file_data["path"].append(str(file_path))
        file_data["binary_content"].append(binary_content)

    # Create PyArrow table
    table = pa.table(file_data)
    assert table.num_rows > 0, "Table should have rows"

    # Initialize operator with basic configuration
    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "extract_tables": False,  # No tables in txt files
        "extract_images": False,  # No images in txt files
        "use_template": False,
    }

    operator = ExtractDoclingOperator(config)

    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    # Assertions
    assert "content" in result_table.column_names, "Content column should exist"
    assert "doc_id_hash" in result_table.column_names, "Hash ID column should exist"
    assert "docling_document" not in result_table.column_names, (
        "docling_document column should not exist (created in chunker now)"
    )

    # Check content for each file
    for idx in range(result_table.num_rows):
        content = result_table["content"][idx].as_py()
        assert content is not None, f"Content should not be None for file {idx}"
        assert len(content) > 0, f"Content should not be empty for file {idx}"

    # Check hash
    first_hash = result_table["doc_id_hash"][0].as_py()
    assert first_hash is not None, "Hash should not be None"
    assert len(first_hash) > 0, "Hash should not be empty"

    # Check metadata
    assert metadata["total_docs_count"] == table.num_rows, (
        "Total docs should match input rows"
    )
    assert metadata["processed_docs"] > 0, "Should have processed at least one document"
    assert metadata["processed_docs"] == table.num_rows, (
        "All txt files should be processed successfully"
    )


def test_extract_docling_mixed_file_types():
    """Test the ExtractDoclingOperator with mixed file types (.txt and .pdf)."""
    import pyarrow as pa
    from core.operators.extract.extract_docling import ExtractDoclingOperator

    # Get test files - mix of txt and pdf
    txt_dir = (
        Path(__file__).parent.parent.parent.parent
        / "fixtures"
        / "customer_support_docs"
    )
    pdf_dir = Path(__file__).parent.parent.parent.parent / "fixtures" / "invoices"

    txt_files = list(txt_dir.glob("*.txt"))[:1]
    pdf_files = list(pdf_dir.glob("*.pdf"))[:1]

    test_files = txt_files + pdf_files

    if len(test_files) < 2:
        import pytest

        pytest.skip("Need both .txt and .pdf files for mixed type test")

    # Prepare data for PyArrow table
    file_data = {"id": [], "name": [], "path": [], "binary_content": []}

    for file_path in test_files:
        with open(file_path, "rb") as f:
            binary_content = f.read()

        file_data["id"].append(str(file_path))
        file_data["name"].append(file_path.name)
        file_data["path"].append(str(file_path))
        file_data["binary_content"].append(binary_content)

    # Create PyArrow table
    table = pa.table(file_data)

    # Initialize operator
    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "extract_tables": True,
        "extract_images": True,
        "use_template": False,
    }

    operator = ExtractDoclingOperator(config)

    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    # Assertions
    assert "content" in result_table.column_names, "Content column should exist"
    assert "doc_id_hash" in result_table.column_names, "Hash ID column should exist"
    assert "docling_document" not in result_table.column_names, (
        "docling_document column should not exist (created in chunker now)"
    )

    # Verify all files were processed
    assert metadata["processed_docs"] == len(test_files), (
        "All files should be processed"
    )

    # Check that both file types have content
    for idx in range(result_table.num_rows):
        content = result_table["content"][idx].as_py()
        assert content is not None, f"Content should not be None for file {idx}"
        assert len(content) > 0, f"Content should not be empty for file {idx}"


def test_extract_docling_txt_with_special_characters():
    """Test the ExtractDoclingOperator with .txt files containing special characters."""
    import pyarrow as pa
    from core.operators.extract.extract_docling import ExtractDoclingOperator
    import tempfile
    import os

    # Create a temporary txt file with special characters
    test_content = "Hello World!\n\nThis is a test with special chars: é, ñ, ü, 中文\n\nEnd of test."

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(test_content)
        temp_file_path = f.name

    try:
        # Read the file as binary
        with open(temp_file_path, "rb") as f:
            binary_content = f.read()

        # Create PyArrow table
        table = pa.table(
            {
                "id": [temp_file_path],
                "name": [os.path.basename(temp_file_path)],
                "path": [temp_file_path],
                "binary_content": [binary_content],
            }
        )

        # Initialize operator
        config = {
            "doc_column": "content",
            "doc_id_hash": "doc_id_hash",
            "extract_tables": False,
            "extract_images": False,
            "use_template": False,
        }

        operator = ExtractDoclingOperator(config)

        # Transform the table
        result_tables, metadata = operator.transform(table)
        result_table = result_tables[0]

        # Assertions
        assert "content" in result_table.column_names, "Content column should exist"
        content = result_table["content"][0].as_py()
        assert content is not None, "Content should not be None"
        assert "Hello World!" in content, "Content should contain the test text"
        assert "special chars" in content, (
            "Content should contain special characters text"
        )

        # Verify content was extracted (docling_document is now created in chunker)
        content = result_table["content"][0].as_py()
        assert content is not None, "content should not be None"
        assert len(content) > 0, "content should not be empty"

        # Check metadata
        assert metadata["processed_docs"] == 1, "Should have processed one document"

    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


@pytest.mark.unit
def test_extract_docling_with_existing_content():
    """Test that operator skips extraction if content column already exists."""
    import pyarrow as pa
    from core.operators.extract import ExtractDoclingOperator

    # Create table with existing content column
    table = pa.table(
        {
            "id": ["doc1"],
            "name": ["test.pdf"],
            "path": ["/path/to/test.pdf"],
            "content": ["Existing content"],
            "doc_id_hash": ["existing_hash"],
        }
    )

    # Initialize operator
    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "extract_tables": True,
        "extract_images": True,
    }

    operator = ExtractDoclingOperator(config)

    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    # Assertions - should return original table unchanged
    assert result_table.num_rows == 1, "Should have 1 row"
    assert result_table["content"][0].as_py() == "Existing content", (
        "Should keep existing content"
    )
    assert result_table["doc_id_hash"][0].as_py() == "existing_hash", (
        "Should keep existing hash"
    )
    assert "message" in metadata, "Should have message in metadata"


@pytest.mark.unit
def test_extract_docling_parallel_processing():
    """Test the ExtractDoclingOperator with parallel processing configuration."""
    import pyarrow as pa
    from core.operators.extract import ExtractDoclingOperator

    # Get test files
    fixtures_dir = (
        Path(__file__).parent.parent.parent.parent
        / "fixtures"
        / "customer_support_docs"
    )
    test_files = list(fixtures_dir.glob("*.txt"))[:3]

    if len(test_files) < 2:
        pytest.skip("Need at least 2 files for parallel processing test")

    # Prepare data for PyArrow table
    file_data = {"id": [], "name": [], "path": [], "binary_content": []}

    for file_path in test_files:
        with open(file_path, "rb") as f:
            binary_content = f.read()

        file_data["id"].append(str(file_path))
        file_data["name"].append(file_path.name)
        file_data["path"].append(str(file_path))
        file_data["binary_content"].append(binary_content)

    # Create PyArrow table
    table = pa.table(file_data)

    # Test with ThreadPoolExecutor
    config_threads = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "extract_tables": False,
        "extract_images": False,
        "max_workers": 2,
        "use_processes": False,
    }

    operator_threads = ExtractDoclingOperator(config_threads)
    result_tables, metadata = operator_threads.transform(table)
    result_table = result_tables[0]

    # Assertions
    assert result_table.num_rows == len(test_files), "Should process all files"
    assert metadata["processed_docs"] == len(test_files), "Should process all documents"

    # Verify all content was extracted
    for idx in range(result_table.num_rows):
        content = result_table["content"][idx].as_py()
        assert content is not None, f"Content should not be None for row {idx}"
        assert len(content) > 0, f"Content should not be empty for row {idx}"


# ============================================================================
# VLM Pipeline Mode Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.skip(reason="Requires docling[vlm] dependencies and model downloads")
def test_extract_docling_vlm_transformers_engine(sample_pdf_files):
    """Test VLM extraction with Transformers engine (local inference)."""
    import pyarrow as pa
    from core.operators.extract import ExtractDoclingOperator

    # Check if VLM dependencies are available
    try:
        from docling.pipeline.vlm_pipeline import VlmPipeline  # noqa: F401
    except ImportError:
        pytest.skip(
            "VLM pipeline dependencies not available. Install with: pip install docling[vlm]"
        )

    test_files = sample_pdf_files[:1]
    if not test_files:
        pytest.skip("No PDF files available for testing")

    # Prepare data
    file_data = {"id": [], "name": [], "path": [], "binary_content": []}
    for file_path in test_files:
        with open(file_path, "rb") as f:
            binary_content = f.read()
        file_data["id"].append(str(file_path))
        file_data["name"].append(file_path.name)
        file_data["path"].append(str(file_path))
        file_data["binary_content"].append(binary_content)

    table = pa.table(file_data)

    # Configure for VLM with Transformers engine
    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "transformers",
    }

    operator = ExtractDoclingOperator(config)
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    # Assertions
    assert "content" in result_table.column_names
    assert result_table["content"][0].as_py() is not None
    assert metadata["processed_docs"] > 0


@pytest.mark.unit
@pytest.mark.skip(reason="Requires docling[vlm] dependencies and MLX (macOS only)")
def test_extract_docling_vlm_mlx_engine(sample_pdf_files):
    """Test VLM extraction with MLX engine (macOS optimized)."""
    import pyarrow as pa
    from core.operators.extract import ExtractDoclingOperator
    import platform

    if platform.system() != "Darwin":
        pytest.skip("MLX engine only available on macOS")

    try:
        from docling.pipeline.vlm_pipeline import VlmPipeline  # noqa: F401
    except ImportError:
        pytest.skip(
            "VLM pipeline dependencies not available. Install with: pip install docling[vlm]"
        )

    test_files = sample_pdf_files[:1]
    if not test_files:
        pytest.skip("No PDF files available for testing")

    file_data = {"id": [], "name": [], "path": [], "binary_content": []}
    for file_path in test_files:
        with open(file_path, "rb") as f:
            binary_content = f.read()
        file_data["id"].append(str(file_path))
        file_data["name"].append(file_path.name)
        file_data["path"].append(str(file_path))
        file_data["binary_content"].append(binary_content)

    table = pa.table(file_data)

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "mlx",
    }

    operator = ExtractDoclingOperator(config)
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    assert "content" in result_table.column_names
    assert result_table["content"][0].as_py() is not None


@pytest.mark.unit
def test_extract_docling_vlm_ollama_engine_config():
    """Test VLM extraction configuration with Ollama API engine."""
    from core.operators.extract import ExtractDoclingOperator

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "api_ollama",
        "vlm_provider_config": {
            "vlm_api_base_url": "http://localhost:11434/v1/chat/completions",
            "vlm_model_name": "llava",
        },
    }

    # Should initialize without errors
    operator = ExtractDoclingOperator(config)
    assert operator.use_vlm_pipeline is True
    assert operator.vlm_engine_type == "api_ollama"
    assert operator.vlm_preset == "granite_docling"


@pytest.mark.unit
def test_extract_docling_vlm_openai_engine_config():
    """Test VLM extraction configuration with OpenAI API engine."""
    from core.operators.extract import ExtractDoclingOperator

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "api_openai",
        "vlm_provider_config": {
            "vlm_api_key": "test_key",  # pragma: allowlist secret
            "vlm_model_name": "gpt-4-vision-preview",
        },
    }

    operator = ExtractDoclingOperator(config)
    assert operator.use_vlm_pipeline is True
    assert operator.vlm_engine_type == "api_openai"


@pytest.mark.unit
def test_extract_docling_vlm_watsonx_engine_config():
    """Test VLM extraction configuration with Watsonx API engine."""
    from core.operators.extract import ExtractDoclingOperator

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "api_watsonx",
        "vlm_provider_config": {
            "vlm_api_key": "test_key",  # pragma: allowlist secret
            "vlm_watsonx_container_id": "12345678-1234-1234-1234-123456789abc",
            "vlm_model_name": "ibm/granite-13b-chat-v2",
        },
    }

    operator = ExtractDoclingOperator(config)
    assert operator.use_vlm_pipeline is True
    assert operator.vlm_engine_type == "api_watsonx"


@pytest.mark.unit
def test_extract_docling_vlm_lmstudio_engine_config():
    """Test VLM extraction configuration with LM Studio API engine."""
    from core.operators.extract import ExtractDoclingOperator

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "api_lmstudio",
        "vlm_provider_config": {
            "vlm_api_base_url": "http://localhost:1234/v1/chat/completions"
        },
    }

    operator = ExtractDoclingOperator(config)
    assert operator.use_vlm_pipeline is True
    assert operator.vlm_engine_type == "api_lmstudio"


@pytest.mark.unit
def test_extract_docling_vlm_generic_api_engine_config():
    """Test VLM extraction configuration with generic API engine."""
    from core.operators.extract import ExtractDoclingOperator

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "api",
        "vlm_provider_config": {"vlm_api_base_url": "https://api.example.com/v1/chat"},
    }

    operator = ExtractDoclingOperator(config)
    assert operator.use_vlm_pipeline is True
    assert operator.vlm_engine_type == "api"


@pytest.mark.unit
def test_extract_docling_vlm_default_engine_config():
    """Test VLM with no engine specified (defaults to transformers)."""
    from core.operators.extract import ExtractDoclingOperator

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        # No vlm_engine_type specified - defaults to transformers
    }

    operator = ExtractDoclingOperator(config)
    assert operator.use_vlm_pipeline is True
    assert operator.vlm_engine_type == "transformers"  # Default engine type


@pytest.mark.unit
def test_extract_docling_vlm_invalid_engine_type():
    """Test VLM extraction with invalid engine type."""
    from core.operators.extract import ExtractDoclingOperator

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "invalid_engine",
    }

    # Should raise ValueError during initialization
    with pytest.raises(ValueError, match="Invalid vlm_engine_type"):
        ExtractDoclingOperator(config)


@pytest.mark.unit
def test_extract_docling_vlm_with_different_presets():
    """Test VLM extraction configuration with different presets."""
    from core.operators.extract import ExtractDoclingOperator

    # Use valid presets from docling
    presets = ["granite_docling", "qwen", "pixtral"]

    for preset in presets:
        config = {
            "doc_column": "content",
            "doc_id_hash": "doc_id_hash",
            "use_vlm_pipeline": True,
            "vlm_preset": preset,
            "vlm_engine_type": "transformers",
        }

        operator = ExtractDoclingOperator(config)
        assert operator.use_vlm_pipeline is True
        assert operator.vlm_preset == preset


# ============================================================================
# VLM Pipeline Validation Tests - Missing Required Configuration
# ============================================================================


@pytest.mark.unit
def test_extract_docling_vlm_watsonx_missing_api_key():
    """Test Watsonx engine with missing API key."""
    from core.operators.extract import ExtractDoclingOperator

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "api_watsonx",
        "vlm_provider_config": {
            # Missing vlm_api_key
            "vlm_watsonx_container_id": "12345678-1234-1234-1234-123456789abc",
            "vlm_model_name": "ibm/granite-13b-chat-v2",
        },
    }

    with pytest.raises(ValueError, match="missing required fields"):
        ExtractDoclingOperator(config)


@pytest.mark.unit
def test_extract_docling_vlm_watsonx_missing_container_id():
    """Test Watsonx engine with missing container ID."""
    from core.operators.extract import ExtractDoclingOperator

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "api_watsonx",
        "vlm_provider_config": {
            "vlm_api_key": "test_key",  # pragma: allowlist secret
            # Missing vlm_watsonx_container_id
            "vlm_model_name": "ibm/granite-13b-chat-v2",
        },
    }

    with pytest.raises(ValueError, match="missing required fields"):
        ExtractDoclingOperator(config)


@pytest.mark.unit
def test_extract_docling_vlm_watsonx_missing_model_name():
    """Test Watsonx engine with missing model name."""
    from core.operators.extract import ExtractDoclingOperator

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "api_watsonx",
        "vlm_provider_config": {
            "vlm_api_key": "test_key",  # pragma: allowlist secret
            "vlm_watsonx_container_id": "12345678-1234-1234-1234-123456789abc",
            # Missing vlm_model_name
        },
    }

    with pytest.raises(ValueError, match="missing required fields"):
        ExtractDoclingOperator(config)


@pytest.mark.unit
def test_extract_docling_vlm_watsonx_empty_provider_config():
    """Test Watsonx engine with empty provider config."""
    from core.operators.extract import ExtractDoclingOperator
    from common.exceptions.datasift_exceptions import FlowExecutionFailedException

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "api_watsonx",
        "vlm_provider_config": {},  # Empty config
    }

    with pytest.raises(FlowExecutionFailedException, match="vlm_api_key is required"):
        ExtractDoclingOperator(config)


@pytest.mark.unit
def test_extract_docling_vlm_openai_missing_api_key():
    """Test OpenAI engine with missing API key."""
    from core.operators.extract import ExtractDoclingOperator

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "api_openai",
        "vlm_provider_config": {
            # Missing vlm_api_key
            "vlm_model_name": "gpt-4-vision-preview"
        },
    }

    with pytest.raises(ValueError, match="api_key is required"):
        ExtractDoclingOperator(config)


@pytest.mark.unit
def test_extract_docling_vlm_openai_missing_model_name():
    """Test OpenAI engine with missing model name."""
    from core.operators.extract import ExtractDoclingOperator

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "api_openai",
        "vlm_provider_config": {
            "vlm_api_key": "test_key"  # pragma: allowlist secret
            # Missing vlm_model_name
        },
    }

    with pytest.raises(ValueError, match="model_name is required"):
        ExtractDoclingOperator(config)


@pytest.mark.unit
def test_extract_docling_vlm_generic_api_missing_base_url():
    """Test generic API engine with missing base URL."""
    from core.operators.extract import ExtractDoclingOperator

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "api",
        "vlm_provider_config": {
            # Missing vlm_api_base_url
            "vlm_api_key": "test_key"  # pragma: allowlist secret
        },
    }

    with pytest.raises(ValueError, match="vlm_api_base_url is required"):
        ExtractDoclingOperator(config)


@pytest.mark.unit
def test_extract_docling_vlm_validation_modes():
    """Test that VLM mode is validated against other extraction modes."""
    from core.operators.extract import ExtractDoclingOperator

    # VLM mode should be mutually exclusive with template mode
    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "use_template": True,  # Should conflict
        "vlm_preset": "granite_docling",
    }

    with pytest.raises(ValueError, match="Cannot use both VLM pipeline and template"):
        ExtractDoclingOperator(config)


@pytest.mark.unit
def test_extract_docling_vlm_validation_with_docling_serve():
    """Test that VLM mode conflicts with docling_serve mode."""
    from core.operators.extract import ExtractDoclingOperator
    from common.exceptions.datasift_exceptions import FlowExecutionFailedException

    config = {
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "use_vlm_pipeline": True,
        "use_docling_serve": True,  # Should conflict
        "vlm_preset": "granite_docling",
    }

    with pytest.raises(FlowExecutionFailedException, match="mutually exclusive"):
        ExtractDoclingOperator(config)


@pytest.mark.unit
def test_extract_docling_vlm_metadata_attributes():
    """Test that VLM-related attributes are in operator metadata."""
    from core.operators.extract import ExtractDoclingOperator

    config = {"doc_column": "content", "doc_id_hash": "doc_id_hash"}

    operator = ExtractDoclingOperator(config)
    metadata = operator.get_metadata()

    # Check VLM-related attributes exist
    attributes = metadata["attributes"]
    assert "use_vlm_pipeline" in attributes
    assert "vlm_preset" in attributes
    assert "vlm_engine_type" in attributes
    assert "vlm_provider_config" in attributes

    # Verify attribute details
    vlm_attr = attributes["use_vlm_pipeline"]
    assert vlm_attr["type"] == "boolean"
    assert vlm_attr["default"] is False


@pytest.mark.unit
def test_extract_docling_vlm_configure_engine_function():
    """Test _configure_vlm_engine function."""
    from core.operators.extract.extract_docling import _configure_vlm_engine

    # Test with no engine type (should return None for Docling defaults)
    result = _configure_vlm_engine(
        vlm_engine_type=None, vlm_preset="granite_docling", vlm_provider_config=None
    )
    assert result is None

    # Test with transformers engine
    result = _configure_vlm_engine(
        vlm_engine_type="transformers",
        vlm_preset="granite_docling",
        vlm_provider_config={},
    )
    assert result is not None
    from docling.datamodel.pipeline_options import VlmPipelineOptions

    assert isinstance(result, VlmPipelineOptions)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
