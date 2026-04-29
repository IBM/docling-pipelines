#!/usr/bin/env python3
"""
Unit tests for ExtractOperator (unified extraction operator).
Tests the operator with sample PDF files from the fixtures directory.
"""

import json
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from common.constants.constants import ExecutionStatus, Metrics
from common.constants.operator_constants import OperatorConstants

# Path setup is now automatic via conftest.py


@pytest.mark.unit
def test_extract_operator_docling_library_mode(sample_pdf_files):
    """Test the ExtractOperator with docling_library text extraction mode."""
    import pyarrow as pa

    from core.operators.extract.extract_operator import ExtractOperator

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

    # Initialize operator with docling_library text extraction configuration
    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "none",
        "doc_column": "doc_content",
        "extract_tables": True,
        "extract_images": True,
        "max_workers": 2,
    }

    operator = ExtractOperator(config=config)

    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    # Assertions
    assert "doc_content" in result_table.column_names, "Content column should exist"
    assert "doc_id_hash" in result_table.column_names, "Hash ID column should exist"

    # Check content
    first_content = result_table["doc_content"][0].as_py()
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
@pytest.mark.skip(reason="Requires docling-serve service running")
def test_extract_operator_docling_serve_mode(sample_pdf_files):
    """Test the ExtractOperator with docling_serve text extraction mode."""
    import pyarrow as pa

    from core.operators.extract.extract_operator import ExtractOperator

    # Use fixture for test files
    test_files = sample_pdf_files[:1]

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

    # Initialize operator with docling_serve configuration
    config = {
        "text_extraction_mode": "docling_serve",
        "entity_extraction_mode": "none",
        "doc_column": "doc_content",
        "docling_serve_base_url": "http://datasift-worker1.fyre.ibm.com:30501/",
        "docling_serve_timeout": 300,
        "docling_serve_poll_interval": 2,
        "docling_serve_max_retries": 3,
        "docling_serve_do_ocr": True,
        "docling_serve_ocr_engine": "easyocr",
        "docling_serve_pdf_backend": "dlparse_v2",
        "docling_serve_table_mode": "fast",
        "docling_serve_image_export_mode": "placeholder",
        "max_workers": 2,
    }

    operator = ExtractOperator(config=config)

    # Transform the table
    result_tables, metadata = operator.transform(table)
    result_table = result_tables[0]

    # Assertions
    assert "doc_content" in result_table.column_names, "Content column should exist"
    assert "doc_id_hash" in result_table.column_names, "Hash ID column should exist"

    # Check content
    first_content = result_table["doc_content"][0].as_py()
    assert first_content is not None, "Content should not be None"
    assert len(first_content) > 0, "Content should not be empty"

    # Check metadata
    assert metadata["total_docs_count"] == table.num_rows
    assert metadata["processed_docs"] > 0


@pytest.mark.unit
def test_extract_operator_docling_serve_config_validation():
    """Test docling_serve configuration parameter validation."""
    from core.operators.extract.extract_operator import ExtractOperator

    # Test with minimal docling_serve configuration
    config = {
        "text_extraction_mode": "docling_serve",
        "entity_extraction_mode": "none",
        "docling_serve_base_url": "http://datasift-worker1.fyre.ibm.com:30501/",
    }

    operator = ExtractOperator(config=config)

    # Verify operator was created successfully
    assert operator.text_extraction_mode.value == "docling_serve"
    assert operator.entity_extraction_mode.value == "none"


@pytest.mark.unit
def test_extract_operator_docling_serve_with_api_key():
    """Test docling_serve configuration with API key."""
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "docling_serve",
        "entity_extraction_mode": "none",
        "docling_serve_base_url": "http://datasift-worker1.fyre.ibm.com:30501/",
        "docling_serve_api_key": "test-api-key-12345",  # pragma: allowlist secret
        "docling_serve_timeout": 600,
    }

    operator = ExtractOperator(config=config)

    # Verify configuration was accepted
    assert operator.text_extraction_mode.value == "docling_serve"


@pytest.mark.unit
def test_extract_operator_docling_serve_with_ocr_languages():
    """Test docling_serve configuration with OCR language specification."""
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "docling_serve",
        "entity_extraction_mode": "none",
        "docling_serve_base_url": "http://datasift-worker1.fyre.ibm.com:30501/",
        "docling_serve_do_ocr": True,
        "docling_serve_ocr_engine": "easyocr",
        "docling_serve_ocr_languages": ["en", "es", "fr"],
    }

    operator = ExtractOperator(config=config)

    # Verify configuration was accepted
    assert operator.text_extraction_mode.value == "docling_serve"


@pytest.mark.unit
def test_extract_operator_docling_library_with_entity_extraction_ollama(
    sample_pdf_files,
):
    """Test ExtractOperator with docling_library text extraction + Ollama entity extraction."""
    import json
    from unittest.mock import Mock, patch

    import pyarrow as pa

    from core.operators.extract.extract_operator import ExtractOperator

    # Use fixture for test files
    test_files = sample_pdf_files[:1]

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

    # Initialize operator with both text and entity extraction
    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "ollama",
        "entity_model_name": "llama3.2",
        "temperature": 0.0,
        "max_tokens": 4096,
        "doc_column": "doc_content",
        "extract_tables": True,
        "extract_images": False,
        "max_workers": 2,
        "custom_schema": {
            "invoice_number": "string",
            "total_amount": "number",
            "date": "string",
        },
    }

    # Mock the Ollama client to avoid actual API calls
    with patch("common.clients.ollama_client.OllamaClient") as mock_ollama_class:
        mock_instance = Mock()
        # Mock the run method which is called by entity extraction
        mock_instance.run.return_value = json.dumps(
            {"invoice_number": "INV-001", "total_amount": 1500.00, "date": "2024-01-15"}
        )
        mock_ollama_class.return_value = mock_instance

        operator = ExtractOperator(config=config)

        # Transform the table
        result_tables, _metadata = operator.transform(table)
        result_table = result_tables[0]

        # Assertions
        assert "doc_content" in result_table.column_names, "Content column should exist"
        assert "entities" in result_table.column_names, "Entities column should exist"
        assert "doc_id_hash" in result_table.column_names, "Hash ID column should exist"


@pytest.mark.unit
def test_extract_operator_docling_serve_with_entity_extraction():
    """Test ExtractOperator with docling_serve text + entity extraction."""
    from unittest.mock import Mock, patch

    from core.operators.extract.extract_operator import ExtractOperator

    # Mock the Ollama client at the import location
    with patch("common.clients.ollama_client.OllamaClient") as mock_ollama_class:
        mock_instance = Mock()
        mock_ollama_class.return_value = mock_instance

        # Test configuration combining docling_serve and entity extraction
        config = {
            "text_extraction_mode": "docling_serve",
            "entity_extraction_mode": "ollama",
            "entity_model_name": "llama3.2",
            "doc_column": "doc_content",
            "docling_serve_base_url": "http://datasift-worker1.fyre.ibm.com:30501/",
            "docling_serve_timeout": 300,
            "max_workers": 2,
        }

        operator = ExtractOperator(config=config)

        # Verify both modes are configured
        assert operator.text_extraction_mode.value == "docling_serve"
        assert operator.entity_extraction_mode.value == "ollama"
        assert operator.entity_adapter is not None


@pytest.mark.unit
def test_extract_operator_invalid_text_mode():
    """Test ExtractOperator with invalid text extraction mode."""
    from common.exceptions.datasift_exceptions import FlowExecutionFailedException
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "invalid_mode",
        "entity_extraction_mode": "none",
    }

    with pytest.raises(FlowExecutionFailedException) as exc_info:
        ExtractOperator(config=config)

    assert "Invalid text_extraction_mode" in str(exc_info.value)


@pytest.mark.unit
def test_extract_operator_invalid_entity_mode():
    """Test ExtractOperator with invalid entity extraction mode."""
    from common.exceptions.datasift_exceptions import FlowExecutionFailedException
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "invalid_mode",
    }

    with pytest.raises(FlowExecutionFailedException) as exc_info:
        ExtractOperator(config=config)

    assert "Invalid entity_extraction_mode" in str(exc_info.value)


@pytest.mark.unit
def test_extract_operator_docling_library_vlm_mode_config():
    """Test ExtractOperator with docling_library VLM text extraction mode configuration."""
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "docling_library",
        "use_vlm_pipeline": True,
        "entity_extraction_mode": "none",
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "transformers",
        "doc_column": "doc_content",
        "max_workers": 2,
    }

    operator = ExtractOperator(config=config)

    # Verify docling_library with VLM mode is configured
    assert operator.text_extraction_mode.value == "docling_library"
    assert operator.entity_extraction_mode.value == "none"


@pytest.mark.unit
def test_extract_operator_get_metadata():
    """Test ExtractOperator metadata retrieval."""
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "none",
    }

    operator = ExtractOperator(config=config)
    metadata = operator.get_metadata()

    # Verify metadata structure
    assert "category" in metadata
    assert "features" in metadata
    assert "attributes" in metadata
    assert "is_operator_available" in metadata

    # Verify key attributes are present
    attributes = metadata["attributes"]
    assert "text_extraction_mode" in attributes
    assert "entity_extraction_mode" in attributes
    assert "docling_serve_base_url" in attributes
    assert "entity_model_name" in attributes
    assert "max_workers" in attributes

    # Verify docling_serve parameters
    assert "docling_serve_timeout" in attributes
    assert "docling_serve_poll_interval" in attributes
    assert "docling_serve_max_retries" in attributes
    assert "docling_serve_do_ocr" in attributes
    assert "docling_serve_ocr_engine" in attributes
    assert "docling_serve_ocr_languages" in attributes
    assert "docling_serve_pdf_backend" in attributes
    assert "docling_serve_table_mode" in attributes
    assert "docling_serve_image_export_mode" in attributes

    # Verify default values
    assert attributes["docling_serve_base_url"]["default"] == "http://localhost:5001"
    assert attributes["docling_serve_timeout"]["default"] == 300
    assert attributes["docling_serve_do_ocr"]["default"] is True


@pytest.mark.unit
def test_extract_operator_expand_extracted_data():
    """Test ExtractOperator with expand_extracted_data flag."""
    from unittest.mock import Mock, patch

    from core.operators.extract.extract_operator import ExtractOperator

    # Mock the Ollama client at the import location
    with patch("common.clients.ollama_client.OllamaClient") as mock_ollama_class:
        mock_instance = Mock()
        mock_ollama_class.return_value = mock_instance

        config = {
            "text_extraction_mode": "docling_library",
            "entity_extraction_mode": "ollama",
            "entity_model_name": "llama3.2",
            "expand_extracted_data": True,
            "custom_schema": {"invoice_number": "string", "amount": "number"},
        }

        operator = ExtractOperator(config=config)

        # Verify configuration
        assert operator.expand_extracted_data is True
        assert operator.entity_adapter is not None


@pytest.mark.unit
def test_extract_operator_default_values():
    """Test ExtractOperator with default configuration values."""
    from core.operators.extract.extract_operator import ExtractOperator

    # Minimal configuration - should use defaults
    config = {}

    operator = ExtractOperator(config=config)

    # Verify defaults
    assert operator.text_extraction_mode.value == "docling_library"
    assert operator.entity_extraction_mode.value == "none"
    assert operator.doc_column == "content"
    assert operator.expand_extracted_data is False
    assert operator.entity_adapter is None


@pytest.mark.unit
def test_extract_operator_docling_serve_all_parameters():
    """Test ExtractOperator with all docling_serve parameters specified."""
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "docling_serve",
        "entity_extraction_mode": "none",
        "doc_column": "content",
        "docling_serve_base_url": "http://datasift-worker1.fyre.ibm.com:30501/",
        "docling_serve_api_key": "secret-key",  # pragma: allowlist secret
        "docling_serve_timeout": 600,
        "docling_serve_poll_interval": 5,
        "docling_serve_max_retries": 5,
        "docling_serve_do_ocr": True,
        "docling_serve_ocr_engine": "tesseract",
        "docling_serve_ocr_languages": ["en", "de", "fr"],
        "docling_serve_pdf_backend": "pypdfium2",
        "docling_serve_table_mode": "accurate",
        "docling_serve_image_export_mode": "embedded",
        "extract_tables": True,
        "extract_images": True,
        "max_workers": 4,
    }

    operator = ExtractOperator(config=config)

    # Verify operator was created successfully with all parameters
    assert operator.text_extraction_mode.value == "docling_serve"
    assert operator.doc_column == "content"


@pytest.mark.unit
def test_extract_operator_mode_combinations():
    """Test various valid mode combinations."""
    from unittest.mock import Mock, patch

    from core.operators.extract.extract_operator import ExtractOperator

    # Mock the Ollama client at the import location
    with patch("common.clients.ollama_client.OllamaClient") as mock_ollama_class:
        mock_instance = Mock()
        mock_ollama_class.return_value = mock_instance

        # Test all valid text mode + entity mode combinations
        text_modes = ["docling_library", "docling_serve"]
        entity_modes = ["none", "ollama", "docling", "litellm"]

        for text_mode in text_modes:
            for entity_mode in entity_modes:
                config = {
                    "text_extraction_mode": text_mode,
                    "entity_extraction_mode": entity_mode,
                }

                # Add mode-specific required parameters
                if text_mode == "docling_serve":
                    config["docling_serve_base_url"] = "http://localhost:5001"

                if entity_mode in ["ollama", "litellm"]:
                    config["entity_model_name"] = "llama3.2"

                operator = ExtractOperator(config=config)
                assert operator.text_extraction_mode.value == text_mode
                assert operator.entity_extraction_mode.value == entity_mode


@pytest.mark.unit
def test_extract_operator_empty_table():
    """Test ExtractOperator with empty input table."""
    import pyarrow as pa

    from core.operators.extract.extract_operator import ExtractOperator

    # Create empty table
    schema = pa.schema(
        [
            ("id", pa.string()),
            ("name", pa.string()),
            ("path", pa.string()),
            ("binary_content", pa.binary()),
        ]
    )
    table = pa.table(
        {"id": [], "name": [], "path": [], "binary_content": []}, schema=schema
    )

    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "none",
    }

    operator = ExtractOperator(config=config)
    result_tables, metadata = operator.transform(table)

    # Should handle empty table gracefully
    assert len(result_tables) == 1
    assert result_tables[0].num_rows == 0
    assert metadata["total_docs_count"] == 0


def _build_pdf_input_table(*, sample_pdf_files, max_files: int = 1):
    """Build a PyArrow input table from sample PDF fixtures."""
    import pyarrow as pa

    test_files = sample_pdf_files[:max_files]
    file_data: dict[str, list[Any]] = {
        "id": [],
        "name": [],
        "path": [],
        "binary_content": [],
    }

    for file_path in test_files:
        with open(file_path, "rb") as file_handle:
            binary_content = file_handle.read()

        file_data["id"].append(str(file_path))
        file_data["name"].append(file_path.name)
        file_data["path"].append(str(file_path))
        file_data["binary_content"].append(binary_content)

    return pa.table(file_data)


@pytest.mark.unit
def test_extract_operator_litellm_entity_mode():
    """Test ExtractOperator with LiteLLM entity extraction mode."""
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "litellm",
        "entity_model_name": "gpt-3.5-turbo",
        "entity_temperature": 0.0,
        "entity_max_tokens": 2000,
        "entity_provider_config": {
            "api_key": "test-api-key",  # pragma: allowlist secret
            "api_base": "https://api.test.local/v1",
        },
        "custom_schema": {"company": "string", "date": "string"},
    }

    with patch(
        "common.clients.litellm_llm_client.LiteLLMLLMClient"
    ) as mock_litellm_class:
        mock_litellm_class.return_value = Mock()

        operator = ExtractOperator(config=config)

    # Verify LiteLLM entity mode is configured
    assert operator.entity_extraction_mode.value == "litellm"
    assert operator.entity_adapter is not None


@pytest.mark.unit
def test_extract_operator_docling_library_with_entity_extraction_litellm_schema(
    sample_pdf_files,
):
    """Execute ExtractOperator with LiteLLM schema-based entity extraction."""
    from core.operators.extract.extract_operator import ExtractOperator

    table = _build_pdf_input_table(sample_pdf_files=sample_pdf_files, max_files=1)

    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "litellm",
        "entity_model_name": "gpt-3.5-turbo",
        "entity_temperature": 0.0,
        "entity_max_tokens": 2000,
        "doc_column": "doc_content",
        "extract_tables": True,
        "extract_images": False,
        "max_workers": 2,
        "entity_provider_config": {
            "api_key": "test-api-key",  # pragma: allowlist secret
            "api_base": "https://api.test.local/v1",
        },
        "custom_schema": {
            "document_type": "invoice",
            "fields": [
                {"name": "person_name", "type": "string"},
                {"name": "invoice_date", "type": "string"},
                {"name": "total_amount", "type": "number"},
            ],
        },
    }

    mocked_entities = {
        "person_name": "John Doe",
        "invoice_date": "2024-01-15",
        "total_amount": 1500.0,
    }

    with patch(
        "common.clients.litellm_llm_client.LiteLLMLLMClient"
    ) as mock_litellm_class:
        mock_instance = Mock()
        mock_instance.chat.return_value = json.dumps(mocked_entities)
        mock_litellm_class.return_value = mock_instance

        operator = ExtractOperator(config=config)
        result_tables, metadata = operator.transform(table)

    result_table = result_tables[0]

    assert "doc_content" in result_table.column_names
    assert "entities" in result_table.column_names
    assert "doc_id_hash" in result_table.column_names
    assert result_table.num_rows == 1
    assert metadata["total_docs_count"] == table.num_rows
    assert metadata["processed_docs"] == 1
    assert metadata[Metrics.External.NODE_STATUS] in {
        ExecutionStatus.COMPLETED.value,
        ExecutionStatus.COMPLETED_WITH_WARNINGS.value,
        ExecutionStatus.COMPLETED_WITH_ERRORS.value,
    }

    extracted_entities = json.loads(result_table["entities"][0].as_py())
    assert extracted_entities == mocked_entities

    extracted_content = result_table["doc_content"][0].as_py()
    assert extracted_content is not None
    assert len(extracted_content) > 0

    mock_instance.chat.assert_called_once()
    chat_call = mock_instance.chat.call_args
    assert chat_call.kwargs["temperature"] == 0.0
    assert chat_call.kwargs["max_tokens"] == 2000
    assert len(chat_call.kwargs["messages"]) == 2


@pytest.mark.unit
def test_extract_operator_docling_library_with_entity_extraction_litellm_schema_free(
    sample_pdf_files,
):
    """Execute ExtractOperator with LiteLLM schema-free entity extraction."""
    from core.operators.extract.extract_operator import ExtractOperator

    table = _build_pdf_input_table(sample_pdf_files=sample_pdf_files, max_files=1)

    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "litellm",
        "entity_model_name": "gpt-3.5-turbo",
        "entity_temperature": 0.0,
        "entity_max_tokens": 1500,
        "doc_column": "doc_content",
        "extract_tables": True,
        "extract_images": False,
        "max_workers": 2,
        "entity_provider_config": {
            "api_key": "test-api-key",  # pragma: allowlist secret
            "api_base": "https://api.test.local/v1",
        },
        "custom_schema": {},
    }

    mocked_entities = {
        "person": "Jane Smith",
        "date": "2024-02-20",
        "amount": "$950.00",
        "organization": "Acme Corp",
    }

    with patch(
        "common.clients.litellm_llm_client.LiteLLMLLMClient"
    ) as mock_litellm_class:
        mock_instance = Mock()
        mock_instance.chat.return_value = json.dumps(mocked_entities)
        mock_litellm_class.return_value = mock_instance

        operator = ExtractOperator(config=config)
        result_tables, metadata = operator.transform(table)

    result_table = result_tables[0]

    assert "entities" in result_table.column_names
    assert result_table.num_rows == 1
    assert metadata["processed_docs"] == 1

    extracted_entities = json.loads(result_table["entities"][0].as_py())
    assert extracted_entities == mocked_entities
    assert extracted_entities["person"] == "Jane Smith"
    assert extracted_entities["organization"] == "Acme Corp"

    chat_call = mock_instance.chat.call_args
    assert (
        chat_call.kwargs["messages"][0]["content"]
        == OperatorConstants.ExtractionModes.ENTITY_EXTRACTION_SCHEMA_FREE_SYSTEM_PROMPT
    )


@pytest.mark.unit
def test_extract_operator_docling_library_with_entity_extraction_litellm_expanded_columns(
    sample_pdf_files,
):
    """Execute ExtractOperator with LiteLLM entity extraction and expanded columns."""
    from core.operators.extract.extract_operator import ExtractOperator

    table = _build_pdf_input_table(sample_pdf_files=sample_pdf_files, max_files=1)

    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "litellm",
        "entity_model_name": "gpt-3.5-turbo",
        "entity_temperature": 0.0,
        "entity_max_tokens": 2000,
        "doc_column": "doc_content",
        "extract_tables": True,
        "extract_images": False,
        "expand_extracted_data": True,
        "max_workers": 2,
        "entity_provider_config": {
            "api_key": "test-api-key",  # pragma: allowlist secret
            "api_base": "https://api.test.local/v1",
        },
        "custom_schema": {
            "document_type": "invoice",
            "fields": [
                {"name": "person_name", "type": "string"},
                {"name": "invoice_date", "type": "string"},
                {"name": "total_amount", "type": "number"},
            ],
        },
    }

    mocked_entities = {
        "person_name": "Alex Johnson",
        "invoice_date": "2024-03-01",
        "total_amount": 2750.5,
    }

    with patch(
        "common.clients.litellm_llm_client.LiteLLMLLMClient"
    ) as mock_litellm_class:
        mock_instance = Mock()
        mock_instance.chat.return_value = json.dumps(mocked_entities)
        mock_litellm_class.return_value = mock_instance

        operator = ExtractOperator(config=config)
        result_tables, metadata = operator.transform(table)

    result_table = result_tables[0]

    assert "entities" in result_table.column_names
    assert "entity_person_name" in result_table.column_names
    assert "entity_invoice_date" in result_table.column_names
    assert "entity_total_amount" in result_table.column_names
    assert metadata["processed_docs"] == 1

    assert result_table["entity_person_name"][0].as_py() == "Alex Johnson"
    assert result_table["entity_invoice_date"][0].as_py() == "2024-03-01"
    assert result_table["entity_total_amount"][0].as_py() == "2750.5"

    extracted_entities = json.loads(result_table["entities"][0].as_py())
    assert extracted_entities == mocked_entities


@pytest.mark.unit
def test_extract_operator_docling_entity_mode():
    """Test ExtractOperator with Docling template-based entity extraction."""
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "docling",
        "custom_schema": {"invoice_number": "string", "total": "number"},
    }

    operator = ExtractOperator(config=config)

    # Verify Docling entity mode is configured
    assert operator.entity_extraction_mode.value == "docling"
    assert operator.entity_adapter is not None


@pytest.mark.unit
def test_extract_operator_invalid_text_extraction_mode_error():
    """Test ExtractOperator with completely invalid text extraction mode."""
    from common.exceptions.datasift_exceptions import FlowExecutionFailedException
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "nonexistent_mode",
        "entity_extraction_mode": "none",
    }

    with pytest.raises(FlowExecutionFailedException) as exc_info:
        ExtractOperator(config=config)

    assert "Invalid text_extraction_mode" in str(exc_info.value)
    assert "nonexistent_mode" in str(exc_info.value)


@pytest.mark.unit
def test_extract_operator_invalid_entity_extraction_mode_error():
    """Test ExtractOperator with completely invalid entity extraction mode."""
    from common.exceptions.datasift_exceptions import FlowExecutionFailedException
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "nonexistent_entity_mode",
    }

    with pytest.raises(FlowExecutionFailedException) as exc_info:
        ExtractOperator(config=config)

    assert "Invalid entity_extraction_mode" in str(exc_info.value)
    assert "nonexistent_entity_mode" in str(exc_info.value)


@pytest.mark.unit
def test_extract_operator_missing_required_columns(sample_pdf_files):
    """Test ExtractOperator with table missing both path and binary content."""
    import pyarrow as pa

    from core.operators.extract.extract_operator import ExtractOperator

    table = pa.table(
        {
            "id": ["doc1"],
            "name": ["test.pdf"],
        }
    )

    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "none",
    }

    operator = ExtractOperator(config=config)
    result_tables, metadata = operator.transform(table)

    assert len(result_tables) == 1
    assert metadata["failed_docs_count"] > 0 or metadata["skipped_docs_count"] > 0


@pytest.mark.unit
def test_extract_operator_custom_doc_column():
    """Test ExtractOperator with custom doc_column name."""
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "none",
        "doc_column": "custom_content_column",
    }

    operator = ExtractOperator(config=config)

    assert operator.doc_column == "custom_content_column"


@pytest.mark.unit
def test_extract_operator_custom_output_columns():
    """Test ExtractOperator with custom output column configuration."""
    from unittest.mock import Mock, patch

    from core.operators.extract.extract_operator import ExtractOperator

    # Mock the Ollama client at the import location
    with patch("common.clients.ollama_client.OllamaClient") as mock_ollama_class:
        mock_instance = Mock()
        mock_ollama_class.return_value = mock_instance

        config = {
            "text_extraction_mode": "docling_library",
            "entity_extraction_mode": "ollama",
            "entity_model_name": "llama3.2",
            "doc_column": "my_doc",
            "output_column": "my_entities",
        }

        operator = ExtractOperator(config=config)

        assert operator.doc_column == "my_doc"
        assert operator.entity_adapter is not None


@pytest.mark.unit
def test_extract_operator_expand_extracted_data_flag():
    """Test ExtractOperator with expand_extracted_data enabled."""
    from unittest.mock import Mock, patch

    from core.operators.extract.extract_operator import ExtractOperator

    # Mock the Ollama client at the import location
    with patch("common.clients.ollama_client.OllamaClient") as mock_ollama_class:
        mock_instance = Mock()
        mock_ollama_class.return_value = mock_instance

        config = {
            "text_extraction_mode": "docling_library",
            "entity_extraction_mode": "ollama",
            "entity_model_name": "llama3.2",
            "expand_extracted_data": True,
            "custom_schema": {"field1": "string", "field2": "number"},
        }

        operator = ExtractOperator(config=config)

        assert operator.expand_extracted_data is True
        assert operator.entity_adapter is not None


@pytest.mark.unit
def test_extract_operator_max_workers_configuration():
    """Test ExtractOperator with custom max_workers setting."""
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "none",
        "max_workers": 8,
    }

    operator = ExtractOperator(config=config)

    # Verify operator was created (max_workers is passed to adapters)
    assert operator.text_adapter is not None


@pytest.mark.unit
def test_extract_operator_use_processes_flag():
    """Test ExtractOperator with use_processes flag."""
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "none",
        "use_processes": True,
    }

    operator = ExtractOperator(config=config)

    # Verify operator was created with process-based execution
    assert operator.text_adapter is not None


@pytest.mark.unit
def test_extract_operator_all_text_modes():
    """Test ExtractOperator initialization with all text extraction modes."""
    from core.operators.extract.extract_operator import ExtractOperator

    text_modes = ["docling_library", "docling_serve"]

    for mode in text_modes:
        config = {
            "text_extraction_mode": mode,
            "entity_extraction_mode": "none",
        }

        # Add mode-specific required parameters
        if mode == "docling_serve":
            config["docling_serve_base_url"] = "http://localhost:5001"

        operator = ExtractOperator(config=config)
        assert operator.text_extraction_mode.value == mode
        assert operator.text_adapter is not None


@pytest.mark.unit
def test_extract_operator_all_entity_modes():
    """Test ExtractOperator initialization with all entity extraction modes."""
    from unittest.mock import Mock, patch

    from core.operators.extract.extract_operator import ExtractOperator

    # Mock the Ollama client at the import location
    with patch("common.clients.ollama_client.OllamaClient") as mock_ollama_class:
        mock_instance = Mock()
        mock_ollama_class.return_value = mock_instance

        entity_modes = ["none", "ollama", "docling", "litellm"]

        for mode in entity_modes:
            config = {
                "text_extraction_mode": "docling_library",
                "entity_extraction_mode": mode,
            }

            # Add mode-specific required parameters
            if mode in ["ollama", "litellm"]:
                config["entity_model_name"] = "test-model"

            operator = ExtractOperator(config=config)
            assert operator.entity_extraction_mode.value == mode

            if mode == "none":
                assert operator.entity_adapter is None
            else:
                assert operator.entity_adapter is not None


@pytest.mark.unit
def test_extract_operator_custom_schema_validation():
    """Test ExtractOperator with custom schema for entity extraction."""
    from unittest.mock import Mock, patch

    from core.operators.extract.extract_operator import ExtractOperator

    # Mock the Ollama client at the import location
    with patch("common.clients.ollama_client.OllamaClient") as mock_ollama_class:
        mock_instance = Mock()
        mock_ollama_class.return_value = mock_instance

        custom_schema = {
            "invoice_number": "string",
            "date": "string",
            "total_amount": "number",
            "vendor": {"name": "string", "address": "string"},
        }

        config = {
            "text_extraction_mode": "docling_library",
            "entity_extraction_mode": "ollama",
            "entity_model_name": "llama3.2",
            "custom_schema": custom_schema,
        }

        operator = ExtractOperator(config=config)

        assert operator.entity_adapter is not None


@pytest.mark.unit
def test_extract_operator_temperature_and_max_tokens():
    """Test ExtractOperator with custom temperature and max_tokens."""
    from unittest.mock import Mock, patch

    from core.operators.extract.extract_operator import ExtractOperator

    # Mock the Ollama client at the import location
    with patch("common.clients.ollama_client.OllamaClient") as mock_ollama_class:
        mock_instance = Mock()
        mock_ollama_class.return_value = mock_instance

        config = {
            "text_extraction_mode": "docling_library",
            "entity_extraction_mode": "ollama",
            "entity_model_name": "llama3.2",
            "temperature": 0.7,
            "max_tokens": 2048,
        }

        operator = ExtractOperator(config=config)

        assert operator.entity_adapter is not None


@pytest.mark.unit
def test_extract_operator_docling_serve_comprehensive():
    """Test ExtractOperator with comprehensive docling_serve parameters."""
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "docling_serve",
        "entity_extraction_mode": "none",
        "docling_serve_base_url": "http://test-server:8080",
        "docling_serve_api_key": "test-key-123",  # pragma: allowlist secret
        "docling_serve_timeout": 600,
        "docling_serve_poll_interval": 5,
        "docling_serve_max_retries": 5,
        "docling_serve_do_ocr": False,
        "docling_serve_ocr_engine": "tesseract",
        "docling_serve_ocr_languages": ["en", "fr", "de"],
        "docling_serve_pdf_backend": "pypdfium2",
        "docling_serve_table_mode": "accurate",
        "docling_serve_image_export_mode": "embedded",
    }

    operator = ExtractOperator(config=config)

    assert operator.text_extraction_mode.value == "docling_serve"
    assert operator.text_adapter is not None


@pytest.mark.unit
def test_extract_operator_docling_library_vlm_all_parameters():
    """Test ExtractOperator with docling_library VLM and all parameters."""
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "docling_library",
        "use_vlm_pipeline": True,
        "entity_extraction_mode": "none",
        "vlm_preset": "granite_docling",
        "vlm_engine_type": "transformers",
        "vlm_provider_config": {
            "api_key": "test-key",  # pragma: allowlist secret
            "api_base_url": "http://localhost:8000",
        },
    }

    operator = ExtractOperator(config=config)

    assert operator.text_extraction_mode.value == "docling_library"
    assert operator.text_adapter is not None


@pytest.mark.unit
def test_extract_operator_metadata_structure():
    """Test ExtractOperator get_metadata returns correct structure."""
    from core.operators.extract.extract_operator import ExtractOperator

    config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "none",
    }

    operator = ExtractOperator(config=config)
    metadata = operator.get_metadata()

    # Verify metadata structure
    assert "category" in metadata
    assert "features" in metadata
    assert "attributes" in metadata
    assert "is_operator_available" in metadata

    # Verify key features
    features = metadata["features"]
    assert "content" in features or "doc_content" in features
    assert "doc_id_hash" in features

    # Verify key attributes
    attributes = metadata["attributes"]
    assert "text_extraction_mode" in attributes
    assert "entity_extraction_mode" in attributes
    assert "max_workers" in attributes


@pytest.mark.unit
def test_consolidate_metadata_merges_failed_and_skipped_docs_without_behavior_change():
    """Test metadata consolidation preserves merged output semantics."""
    from core.operators.extract.extract_operator import ExtractOperator

    operator = ExtractOperator(
        config={
            "text_extraction_mode": "docling_library",
            "entity_extraction_mode": "none",
        }
    )

    text_metadata = {
        Metrics.External.TOTAL_DOCS: 5,
        Metrics.External.FAILED_DOCS: [
            {
                OperatorConstants.Columns.ID: "doc-1",
                OperatorConstants.Misc.REASON: "text failed",
            },
            {
                OperatorConstants.Columns.ID: "doc-2",
                OperatorConstants.Misc.REASON: "text timeout",
            },
        ],
        Metrics.External.SKIPPED_DOCS: [
            {
                OperatorConstants.Columns.ID: "doc-3",
                OperatorConstants.Misc.REASON: "text skipped",
            },
        ],
    }
    entity_metadata = {
        Metrics.External.FAILED_DOCS: [
            {
                OperatorConstants.Columns.ID: "doc-1",
                OperatorConstants.Misc.REASON: "entity failed",
            },
            {
                OperatorConstants.Columns.ID: "doc-4",
                OperatorConstants.Misc.REASON: "entity parse failed",
            },
        ],
        Metrics.External.SKIPPED_DOCS: [
            {
                OperatorConstants.Columns.ID: "doc-3",
                OperatorConstants.Misc.REASON: "entity skipped",
            },
        ],
    }

    consolidated = operator._consolidate_metadata(
        text_metadata=text_metadata,
        entity_metadata=entity_metadata,
    )

    failed_docs = {
        doc[OperatorConstants.Columns.ID]: doc
        for doc in consolidated[Metrics.External.FAILED_DOCS]
    }
    skipped_docs = {
        doc[OperatorConstants.Columns.ID]: doc
        for doc in consolidated[Metrics.External.SKIPPED_DOCS]
    }

    assert consolidated[Metrics.External.TOTAL_DOCS] == 5
    assert consolidated[Metrics.External.FAILED_DOCS_COUNT] == 3
    assert consolidated[Metrics.External.SKIPPED_DOCS_COUNT] == 1
    assert consolidated[Metrics.External.PROCESSED_DOCS] == 1
    assert (
        consolidated[Metrics.External.NODE_STATUS]
        == ExecutionStatus.COMPLETED_WITH_ERRORS.value
    )

    assert failed_docs["doc-1"][OperatorConstants.Misc.REASON] == (
        "Text extraction: text failed | Entity extraction: entity failed"
    )
    assert failed_docs["doc-2"][OperatorConstants.Misc.REASON] == "text timeout"
    assert failed_docs["doc-4"][OperatorConstants.Misc.REASON] == "entity parse failed"
    assert skipped_docs["doc-3"][OperatorConstants.Misc.REASON] == (
        "Text extraction: text skipped | Entity extraction: entity skipped"
    )


@pytest.mark.unit
def test_consolidate_metadata_uses_default_reasons_and_doc_id_column():
    """Test metadata consolidation supports doc_id column and default reasons."""
    from core.operators.extract.extract_operator import ExtractOperator

    operator = ExtractOperator(
        config={
            "text_extraction_mode": "docling_library",
            "entity_extraction_mode": "none",
        }
    )

    text_metadata = {
        Metrics.External.TOTAL_DOCS: 3,
        Metrics.External.FAILED_DOCS: [
            {OperatorConstants.Columns.ID: "doc-1"},
        ],
        Metrics.External.SKIPPED_DOCS: [],
    }
    entity_metadata = {
        Metrics.External.FAILED_DOCS: [
            {
                OperatorConstants.Columns.ID: "doc-1",
                OperatorConstants.Misc.REASON: "entity missing schema",
            },
        ],
        Metrics.External.SKIPPED_DOCS: [
            {OperatorConstants.Columns.ID: "doc-2"},
        ],
    }

    consolidated = operator._consolidate_metadata(
        text_metadata=text_metadata,
        entity_metadata=entity_metadata,
    )

    failed_doc = consolidated[Metrics.External.FAILED_DOCS][0]
    skipped_doc = consolidated[Metrics.External.SKIPPED_DOCS][0]

    assert consolidated[Metrics.External.FAILED_DOCS_COUNT] == 1
    assert consolidated[Metrics.External.SKIPPED_DOCS_COUNT] == 1
    assert consolidated[Metrics.External.PROCESSED_DOCS] == 1
    assert failed_doc[OperatorConstants.Columns.ID] == "doc-1"
    assert failed_doc[OperatorConstants.Misc.REASON] == (
        f"Text extraction: {OperatorConstants.Extraction.ERROR} | Entity extraction: entity missing schema"
    )
    assert skipped_doc[OperatorConstants.Columns.ID] == "doc-2"
    assert OperatorConstants.Misc.REASON not in skipped_doc


@pytest.mark.unit
def test_consolidate_metadata_returns_text_metadata_when_entity_metadata_missing():
    """Test metadata consolidation returns text metadata unchanged when entity metadata is absent."""
    from core.operators.extract.extract_operator import ExtractOperator

    operator = ExtractOperator(
        config={
            "text_extraction_mode": "docling_library",
            "entity_extraction_mode": "none",
        }
    )

    text_metadata = {
        Metrics.External.TOTAL_DOCS: 2,
        Metrics.External.PROCESSED_DOCS: 2,
        Metrics.External.FAILED_DOCS_COUNT: 0,
        Metrics.External.FAILED_DOCS: [],
        Metrics.External.SKIPPED_DOCS_COUNT: 0,
        Metrics.External.SKIPPED_DOCS: [],
        Metrics.External.NODE_STATUS: ExecutionStatus.COMPLETED,
    }

    consolidated = operator._consolidate_metadata(
        text_metadata=text_metadata,
        entity_metadata=None,
    )

    assert consolidated is text_metadata


@pytest.mark.unit
def test_prepare_document_content_fetch_uses_path_when_id_missing():
    """Test document task preparation falls back to path before synthetic row ID."""
    import pyarrow as pa

    from core.operators.operator_utils import OperatorUtils

    table = pa.table(
        {
            OperatorConstants.Columns.PATH: ["/tmp/sample.pdf"],
            OperatorConstants.Columns.NAME: ["sample.pdf"],
            OperatorConstants.Columns.BINARY_CONTENT: [b"binary-data"],
        }
    )

    doc_tasks = OperatorUtils.prepare_document_content_fetch(table=table)

    assert len(doc_tasks) == 1
    assert doc_tasks[0]["doc_id"] == "/tmp/sample.pdf"
    assert doc_tasks[0]["doc_name"] == "sample.pdf"


@pytest.mark.unit
def test_extract_operator_prefers_path_only_input_without_binary_content(
    sample_pdf_files,
):
    """Test ExtractOperator succeeds when only path is provided."""
    import pyarrow as pa

    from core.operators.extract.extract_operator import ExtractOperator

    test_file = sample_pdf_files[0]
    table = pa.table(
        {
            "path": [str(test_file)],
            "name": [test_file.name],
        }
    )

    operator = ExtractOperator(
        config={
            "text_extraction_mode": "docling_library",
            "entity_extraction_mode": "none",
            "doc_column": "doc_content",
            "extract_tables": False,
            "extract_images": False,
        }
    )
    result_tables, metadata = operator.transform(table=table)
    result_table = result_tables[0]

    assert len(result_tables) == 1
    assert result_table["doc_content"][0].as_py()
    assert metadata["processed_docs"] == 1


@pytest.mark.unit
def test_consolidate_metadata_merges_document_in_both_failed_lists():
    """Test that a document failing in both text and entity extraction has merged reasons."""
    from unittest.mock import patch

    from core.operators.extract.extract_operator import ExtractOperator

    # Mock Ollama client to avoid connection requirement
    with patch("common.clients.ollama_client.OllamaClient") as mock_ollama:
        mock_instance = MagicMock()
        mock_ollama.return_value = mock_instance

        operator = ExtractOperator(
            config={
                "text_extraction_mode": "docling_library",
                "entity_extraction_mode": "ollama",
                "entity_model_name": "llama3.2",
            }
        )

        text_metadata = {
            Metrics.External.TOTAL_DOCS: 3,
            Metrics.External.FAILED_DOCS: [
                {
                    OperatorConstants.Columns.ID: "doc-1",
                    OperatorConstants.Misc.REASON: "text extraction timeout",
                },
                {
                    OperatorConstants.Columns.ID: "doc-2",
                    OperatorConstants.Misc.REASON: "text parsing error",
                },
            ],
            Metrics.External.SKIPPED_DOCS: [],
        }
        entity_metadata = {
            Metrics.External.FAILED_DOCS: [
                {
                    OperatorConstants.Columns.ID: "doc-1",
                    OperatorConstants.Misc.REASON: "entity model unavailable",
                },
            ],
            Metrics.External.SKIPPED_DOCS: [],
        }

        consolidated = operator._consolidate_metadata(
            text_metadata=text_metadata,
            entity_metadata=entity_metadata,
        )

        failed_docs = {
            doc[OperatorConstants.Columns.ID]: doc
            for doc in consolidated[Metrics.External.FAILED_DOCS]
        }

        # Verify doc-1 appears once with merged reasons
        assert len(consolidated[Metrics.External.FAILED_DOCS]) == 2
        assert "doc-1" in failed_docs
        assert failed_docs["doc-1"][OperatorConstants.Misc.REASON] == (
            "Text extraction: text extraction timeout | Entity extraction: entity model unavailable"
        )
        # Verify doc-2 appears with only text reason
        assert "doc-2" in failed_docs
        assert (
            failed_docs["doc-2"][OperatorConstants.Misc.REASON] == "text parsing error"
        )


@pytest.mark.unit
def test_consolidate_metadata_merges_document_in_both_skipped_lists():
    """Test that a document skipped in both text and entity extraction has merged reasons."""
    from unittest.mock import patch

    from core.operators.extract.extract_operator import ExtractOperator

    # Mock Ollama client to avoid connection requirement
    with patch("common.clients.ollama_client.OllamaClient") as mock_ollama:
        mock_instance = MagicMock()
        mock_ollama.return_value = mock_instance

        operator = ExtractOperator(
            config={
                "text_extraction_mode": "docling_library",
                "entity_extraction_mode": "ollama",
                "entity_model_name": "llama3.2",
            }
        )

        text_metadata = {
            Metrics.External.TOTAL_DOCS: 3,
            Metrics.External.FAILED_DOCS: [],
            Metrics.External.SKIPPED_DOCS: [
                {
                    OperatorConstants.Columns.ID: "doc-1",
                    OperatorConstants.Misc.REASON: "text unsupported format",
                },
                {
                    OperatorConstants.Columns.ID: "doc-2",
                    OperatorConstants.Misc.REASON: "text empty content",
                },
            ],
        }
        entity_metadata = {
            Metrics.External.FAILED_DOCS: [],
            Metrics.External.SKIPPED_DOCS: [
                {
                    OperatorConstants.Columns.ID: "doc-1",
                    OperatorConstants.Misc.REASON: "entity no schema match",
                },
            ],
        }

        consolidated = operator._consolidate_metadata(
            text_metadata=text_metadata,
            entity_metadata=entity_metadata,
        )

        skipped_docs = {
            doc[OperatorConstants.Columns.ID]: doc
            for doc in consolidated[Metrics.External.SKIPPED_DOCS]
        }

        # Verify doc-1 appears once with merged reasons
        assert len(consolidated[Metrics.External.SKIPPED_DOCS]) == 2
        assert "doc-1" in skipped_docs
        assert skipped_docs["doc-1"][OperatorConstants.Misc.REASON] == (
            "Text extraction: text unsupported format | Entity extraction: entity no schema match"
        )
        # Verify doc-2 appears with only text reason
        assert "doc-2" in skipped_docs
        assert (
            skipped_docs["doc-2"][OperatorConstants.Misc.REASON] == "text empty content"
        )
