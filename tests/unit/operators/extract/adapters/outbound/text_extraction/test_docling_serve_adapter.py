"""
Unit tests for DoclingServeAdapter.
"""

from unittest.mock import MagicMock, patch

import pytest

from docpipe.core.constants import OperatorConstants
from docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter import DoclingServeAdapter


class TestDoclingServeAdapter:
    """Test suite for DoclingServeAdapter."""

    @pytest.fixture
    def valid_config(self):
        """Provide valid configuration for adapter initialization."""
        return {
            "docling_serve_config": {
                "base_url": "http://localhost:5001",
                "api_key": "test-key",  # pragma: allowlist secret
                "timeout": 300,
                "poll_interval": 2,
                "max_retries": 3,
                "do_ocr": True,
                "pdf_backend": "dlparse_v2",
            }
        }

    @pytest.fixture
    def adapter(self, valid_config):
        """Create adapter instance with valid config."""
        return DoclingServeAdapter(config=valid_config)

    def test_init_with_valid_config(self, valid_config):
        """Test adapter initialization with valid configuration."""
        adapter = DoclingServeAdapter(config=valid_config)
        assert adapter.base_url == "http://localhost:5001"
        assert adapter.api_key == "test-key"  # pragma: allowlist secret
        assert adapter.timeout == 300
        assert adapter.poll_interval == 2
        assert adapter.max_retries == 3
        assert adapter.processing_options["do_ocr"] is True
        assert adapter.processing_options["pdf_backend"] == "dlparse_v2"

    def test_init_with_default_values(self):
        """Test adapter initialization with default values."""
        config = {"docling_serve_config": {"base_url": "http://0.0.0.0:5001"}}
        adapter = DoclingServeAdapter(config=config)
        assert adapter.base_url == "http://0.0.0.0:5001"
        assert adapter.api_key is None
        assert adapter.timeout == 300
        assert adapter.poll_interval == 2
        assert adapter.max_retries == 3

    def test_init_missing_docling_serve_config(self):
        """Test adapter initialization fails without docling_serve_config."""
        config = {}
        with pytest.raises(ValueError, match="docling_serve_config is required"):
            DoclingServeAdapter(config=config)

    def test_adapter_name_constants(self):
        """Test adapter name constants are correctly defined."""
        assert DoclingServeAdapter.ADAPTER_NAME == "docling_serve"
        assert DoclingServeAdapter.ADAPTER_DISPLAY_NAME == "Docling Serve Extractor"

    @patch(
        "docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.OperatorUtils.extract_text_file"
    )
    def test_extract_single_document_txt_file_routes_to_local_extraction(self, mock_extract_text_file, adapter):
        """Test that .txt files are routed to local extraction method."""
        # Setup
        file_path = "/path/to/document.txt"
        binary_content = b"This is plain text content"
        mock_extract_text_file.return_value = {
            OperatorConstants.Extraction.SUCCESS: True,
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: "This is plain text content",
        }

        # Execute
        result = adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify
        mock_extract_text_file.assert_called_once_with(
            file_path=file_path, binary_content=binary_content, additional_formats=[]
        )
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == "This is plain text content"

    @patch(
        "docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.OperatorUtils.extract_text_file"
    )
    def test_extract_single_document_txt_file_passes_additional_formats(self, mock_extract_text_file, adapter):
        """Test that additional_formats are forwarded to extract_text_file for .txt files."""
        file_path = "/path/to/document.txt"
        binary_content = b"Plain text content"
        mock_extract_text_file.return_value = {
            OperatorConstants.Extraction.SUCCESS: True,
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: "Plain text content",
            OperatorConstants.Columns.CONTENT_HTML: "<html>Plain text content</html>",
        }

        # Create adapter with additional_formats configured
        config_with_formats = {
            "docling_serve_config": {
                "base_url": "http://localhost:5001",
                "timeout": 300,
                "poll_interval": 2,
                "max_retries": 3,
                "do_ocr": True,
                "pdf_backend": "dlparse_v2",
            },
            "additional_formats": ["html"],
        }
        adapter_with_formats = DoclingServeAdapter(config=config_with_formats)

        result = adapter_with_formats.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify additional_formats is forwarded to extract_text_file
        mock_extract_text_file.assert_called_once_with(
            file_path=file_path, binary_content=binary_content, additional_formats=["html"]
        )
        assert result[OperatorConstants.Extraction.SUCCESS] is True

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_md_file_uses_docling_serve(self, mock_client_class, adapter):
        """Test that .md files are processed through Docling Serve."""
        # Setup
        file_path = "/path/to/document.md"
        binary_content = b"# Markdown content"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {"md_content": "# Markdown content"},
            "processing_time": 1.5,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        result = adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify
        mock_client_class.assert_called_once_with(
            base_url=adapter.base_url,
            api_key=adapter.api_key,
            timeout=adapter.timeout,
            poll_interval=adapter.poll_interval,
            max_retries=adapter.max_retries,
            verify_ssl=adapter.verify_ssl,
        )
        mock_client_instance.process_document.assert_called_once()
        call_kwargs = mock_client_instance.process_document.call_args.kwargs
        assert call_kwargs["binary_content"] == binary_content
        assert call_kwargs["filename"] == "document.md"
        assert result[OperatorConstants.Extraction.SUCCESS] is True

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_filename_extraction_from_path(self, mock_client_class, adapter):
        """Test that filename is correctly extracted from file path."""
        # Setup
        file_path = "/path/to/my_document.pdf"
        binary_content = b"PDF content"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {"md_content": "Extracted text"},
            "processing_time": 2.0,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify filename is passed correctly
        call_kwargs = mock_client_instance.process_document.call_args.kwargs
        assert call_kwargs["filename"] == "my_document.pdf"

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_filename_passing_to_client(self, mock_client_class, adapter):
        """Test that filename is passed to docling_serve_client."""
        # Setup
        file_path = "/path/to/report.docx"
        binary_content = b"DOCX content"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {"md_content": "Report content"},
            "processing_time": 1.8,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify
        call_kwargs = mock_client_instance.process_document.call_args.kwargs
        assert "filename" in call_kwargs
        assert call_kwargs["filename"] == "report.docx"
        assert call_kwargs["binary_content"] == binary_content

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_binary_content_with_filename_preservation(self, mock_client_class, adapter):
        """Test that filename is preserved when processing binary content."""
        # Setup
        file_path = "/path/to/presentation.pptx"
        binary_content = b"PPTX binary data"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {"md_content": "Slide content"},
            "processing_time": 3.2,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify filename preservation
        call_kwargs = mock_client_instance.process_document.call_args.kwargs
        assert call_kwargs["filename"] == "presentation.pptx"

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_success_with_metadata(self, mock_client_class, adapter):
        """Test successful extraction with metadata including page_count from json_content."""
        # Setup
        file_path = "/path/to/document.pdf"
        binary_content = b"PDF content"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {
                "md_content": "Extracted markdown text",
                "json_content": {
                    "pages": [
                        {"page_no": 1},
                        {"page_no": 2},
                        {"page_no": 3},
                        {"page_no": 4},
                        {"page_no": 5},
                        {"page_no": 6},
                        {"page_no": 7},
                        {"page_no": 8},
                        {"page_no": 9},
                        {"page_no": 10},
                    ]
                },
            },
            "processing_time": 2.5,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        result = adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == "Extracted markdown text"
        assert OperatorConstants.Metadata.METADATA in result
        assert result[OperatorConstants.Metadata.METADATA]["processing_time"] == 2.5
        assert result[OperatorConstants.Metadata.METADATA][OperatorConstants.Metadata.PAGE_COUNT] == 10

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_error_handling(self, mock_client_class, adapter):
        """Test error handling during extraction."""
        # Setup
        file_path = "/path/to/document.pdf"
        binary_content = b"PDF content"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.side_effect = Exception("Connection timeout")
        mock_client_class.return_value = mock_client_instance

        # Execute
        result = adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify
        assert result[OperatorConstants.Extraction.SUCCESS] is False
        assert OperatorConstants.Extraction.ERROR in result
        assert "Connection timeout" in result[OperatorConstants.Extraction.ERROR]
        assert result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] is None

    @patch(
        "docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.OperatorUtils.detect_extension_from_bytes"
    )
    @patch(
        "docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.OperatorUtils.extract_text_file"
    )
    def test_extract_single_document_no_extension_detection(
        self, mock_extract_text_file, mock_detect_extension, adapter
    ):
        """Test extension detection when file has no extension."""
        # Setup
        file_path = "/path/to/document"
        binary_content = b"Text content"
        mock_detect_extension.return_value = ".txt"
        mock_extract_text_file.return_value = {
            OperatorConstants.Extraction.SUCCESS: True,
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: "Text content",
        }

        # Execute
        result = adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify
        mock_detect_extension.assert_called_once_with(binary_content)
        mock_extract_text_file.assert_called_once()
        assert result[OperatorConstants.Extraction.SUCCESS] is True

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_pdf_file(self, mock_client_class, adapter):
        """Test PDF file processing through Docling Serve."""
        # Setup
        file_path = "/path/to/document.pdf"
        binary_content = b"%PDF-1.4 content"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {"md_content": "PDF extracted text"},
            "processing_time": 3.0,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        result = adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        call_kwargs = mock_client_instance.process_document.call_args.kwargs
        assert call_kwargs["filename"] == "document.pdf"

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_docx_file(self, mock_client_class, adapter):
        """Test DOCX file processing through Docling Serve."""
        # Setup
        file_path = "/path/to/document.docx"
        binary_content = b"PK\x03\x04 DOCX content"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {"md_content": "DOCX extracted text"},
            "processing_time": 2.2,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        result = adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        call_kwargs = mock_client_instance.process_document.call_args.kwargs
        assert call_kwargs["filename"] == "document.docx"

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_html_file(self, mock_client_class, adapter):
        """Test HTML file processing through Docling Serve."""
        # Setup
        file_path = "/path/to/page.html"
        binary_content = b"<html><body>Content</body></html>"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {"md_content": "HTML extracted text"},
            "processing_time": 1.0,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        result = adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        call_kwargs = mock_client_instance.process_document.call_args.kwargs
        assert call_kwargs["filename"] == "page.html"

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_processing_options_passed(self, mock_client_class, adapter):
        """Test that processing options are passed to client."""
        # Setup
        file_path = "/path/to/document.pdf"
        binary_content = b"PDF content"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {"md_content": "Text"},
            "processing_time": 1.5,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify processing options are passed
        call_kwargs = mock_client_instance.process_document.call_args.kwargs
        assert "options" in call_kwargs
        assert call_kwargs["options"]["do_ocr"] is True
        assert call_kwargs["options"]["pdf_backend"] == "dlparse_v2"

    def test_extract_single_document_with_optional_config_parameters(self):
        """Test adapter with optional configuration parameters."""
        config = {
            "docling_serve_config": {
                "base_url": "http://localhost:5001",
                "ocr_engine": "tesseract",
                "ocr_languages": ["eng", "fra"],
                "table_mode": "accurate",
                "image_export_mode": "embedded",
            }
        }
        adapter = DoclingServeAdapter(config=config)

        assert adapter.processing_options["ocr_engine"] == "tesseract"
        assert adapter.processing_options["ocr_languages"] == ["eng", "fra"]
        assert adapter.processing_options["table_mode"] == "accurate"
        assert adapter.processing_options["image_export_mode"] == "embedded"

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_page_count_from_json_content(self, mock_client_class, adapter):
        """Test page_count extraction from json_content.pages."""
        # Setup
        file_path = "/path/to/document.pdf"
        binary_content = b"PDF content"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {
                "md_content": "Extracted text",
                "json_content": {
                    "pages": [
                        {"page_no": 1, "content": "Page 1"},
                        {"page_no": 2, "content": "Page 2"},
                        {"page_no": 3, "content": "Page 3"},
                    ]
                },
            },
            "processing_time": 2.0,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        result = adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert OperatorConstants.Metadata.METADATA in result
        assert result[OperatorConstants.Metadata.METADATA][OperatorConstants.Metadata.PAGE_COUNT] == 3

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_page_count_empty_pages(self, mock_client_class, adapter):
        """Test page_count when json_content.pages is empty."""
        # Setup
        file_path = "/path/to/document.pdf"
        binary_content = b"PDF content"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {
                "md_content": "Extracted text",
                "json_content": {"pages": []},
            },
            "processing_time": 1.5,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        result = adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify - page_count should not be set when pages is empty
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert OperatorConstants.Metadata.METADATA in result
        assert OperatorConstants.Metadata.PAGE_COUNT not in result[OperatorConstants.Metadata.METADATA]

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_page_count_missing_json_content(self, mock_client_class, adapter):
        """Test page_count when json_content is missing."""
        # Setup
        file_path = "/path/to/document.pdf"
        binary_content = b"PDF content"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {"md_content": "Extracted text"},
            "processing_time": 1.5,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        result = adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify - page_count should not be set when json_content is missing
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert OperatorConstants.Metadata.METADATA in result
        assert OperatorConstants.Metadata.PAGE_COUNT not in result[OperatorConstants.Metadata.METADATA]

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_page_count_missing_pages_key(self, mock_client_class, adapter):
        """Test page_count when pages key is missing from json_content."""
        # Setup
        file_path = "/path/to/document.pdf"
        binary_content = b"PDF content"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {
                "md_content": "Extracted text",
                "json_content": {"other_data": "value"},
            },
            "processing_time": 1.5,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        result = adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify - page_count should not be set when pages key is missing
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert OperatorConstants.Metadata.METADATA in result
        assert OperatorConstants.Metadata.PAGE_COUNT not in result[OperatorConstants.Metadata.METADATA]

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_page_count_single_page(self, mock_client_class, adapter):
        """Test page_count extraction for single page document."""
        # Setup
        file_path = "/path/to/document.pdf"
        binary_content = b"PDF content"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {
                "md_content": "Single page content",
                "json_content": {"pages": [{"page_no": 1, "content": "Page 1"}]},
            },
            "processing_time": 1.0,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        result = adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Metadata.METADATA][OperatorConstants.Metadata.PAGE_COUNT] == 1

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_page_count_large_document(self, mock_client_class, adapter):
        """Test page_count extraction for large multi-page document."""
        # Setup
        file_path = "/path/to/large_document.pdf"
        binary_content = b"PDF content"

        # Create 50 pages
        pages = [{"page_no": i, "content": f"Page {i}"} for i in range(1, 51)]

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {
                "md_content": "Large document content",
                "json_content": {"pages": pages},
            },
            "processing_time": 5.0,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        result = adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Metadata.METADATA][OperatorConstants.Metadata.PAGE_COUNT] == 50

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_verify_ssl_parameter(self, mock_client_class, adapter):
        """Test that verify_ssl parameter is passed to DoclingServeClient."""
        # Setup
        file_path = "/path/to/document.pdf"
        binary_content = b"PDF content"

        mock_client_instance = MagicMock()
        mock_client_instance.process_document.return_value = {
            "document": {"md_content": "Text"},
            "processing_time": 1.5,
        }
        mock_client_class.return_value = mock_client_instance

        # Execute
        adapter.extract_single_document(file_path=file_path, binary_content=binary_content)

        # Verify verify_ssl is passed (default is True)
        mock_client_class.assert_called_once_with(
            base_url=adapter.base_url,
            api_key=adapter.api_key,
            timeout=adapter.timeout,
            poll_interval=adapter.poll_interval,
            max_retries=adapter.max_retries,
            verify_ssl=True,
        )

    def test_init_with_verify_ssl_false(self):
        """Test adapter initialization with verify_ssl set to False."""
        config = {
            "docling_serve_config": {
                "base_url": "http://localhost:5001",
                "verify_ssl": False,
            }
        }
        adapter = DoclingServeAdapter(config=config)
        assert adapter.verify_ssl is False

    def test_init_with_verify_ssl_true(self):
        """Test adapter initialization with verify_ssl set to True."""
        config = {
            "docling_serve_config": {
                "base_url": "http://localhost:5001",
                "verify_ssl": True,
            }
        }
        adapter = DoclingServeAdapter(config=config)
        assert adapter.verify_ssl is True

    def test_init_verify_ssl_default_value(self):
        """Test that verify_ssl defaults to True when not specified."""
        config = {"docling_serve_config": {"base_url": "http://localhost:5001"}}
        adapter = DoclingServeAdapter(config=config)
        assert adapter.verify_ssl is True


class TestDoclingServeAdapterV2Response:
    """Tests for _extract_from_v2_response (docling-serve artifact URI format)."""

    @pytest.fixture
    def adapter(self):
        return DoclingServeAdapter(
            config={
                "docling_serve_config": {
                    "base_url": "http://localhost:5001",
                    "timeout": 300,
                    "poll_interval": 2,
                    "max_retries": 3,
                }
            }
        )

    @pytest.fixture
    def adapter_with_html(self):
        return DoclingServeAdapter(
            config={
                "docling_serve_config": {
                    "base_url": "http://localhost:5001",
                    "timeout": 300,
                    "poll_interval": 2,
                    "max_retries": 3,
                },
                "additional_formats": ["html"],
            }
        )

    def _make_v2_result(self, artifacts: list) -> dict:
        return {"documents": [{"artifacts": artifacts}]}

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.requests.get")
    def test_v2_response_extracts_markdown(self, mock_get, adapter):
        """Happy path: markdown artifact URI is fetched and stored as doc content."""
        mock_get.return_value = MagicMock(text="# Hello World", raise_for_status=MagicMock())
        result = {"documents": [{"artifacts": [{"artifact_type": "markdown", "uri": "https://s3/md"}]}]}

        result_dict, formats = adapter._extract_from_v2_response(result=result, file_path="doc.pdf")

        mock_get.assert_called_once_with("https://s3/md", timeout=60, verify=True)
        assert result_dict[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == "# Hello World"
        assert OperatorConstants.Extraction.OUTPUT_FORMAT_MARKDOWN in formats

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.requests.get")
    def test_v2_response_fetches_additional_format(self, mock_get, adapter_with_html):
        """Additional format (html) URI is fetched and stored in the correct column."""
        mock_get.side_effect = [
            MagicMock(text="# Markdown", raise_for_status=MagicMock()),
            MagicMock(text="<h1>HTML</h1>", raise_for_status=MagicMock()),
        ]
        result = {
            "documents": [
                {
                    "artifacts": [
                        {"artifact_type": "markdown", "uri": "https://s3/md"},
                        {"artifact_type": "html", "uri": "https://s3/html"},
                    ]
                }
            ]
        }

        result_dict, formats = adapter_with_html._extract_from_v2_response(result=result, file_path="doc.pdf")

        assert result_dict[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == "# Markdown"
        assert result_dict[OperatorConstants.Columns.CONTENT_HTML] == "<h1>HTML</h1>"
        assert OperatorConstants.Extraction.OUTPUT_FORMAT_HTML in formats

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.requests.get")
    def test_v2_response_skips_unrequested_formats(self, mock_get, adapter):
        """Artifacts for formats not requested are not fetched."""
        mock_get.return_value = MagicMock(text="# Markdown", raise_for_status=MagicMock())
        result = {
            "documents": [
                {
                    "artifacts": [
                        {"artifact_type": "markdown", "uri": "https://s3/md"},
                        {"artifact_type": "html", "uri": "https://s3/html"},
                    ]
                }
            ]
        }

        _result_dict, formats = adapter._extract_from_v2_response(result=result, file_path="doc.pdf")

        # html was not requested — only one fetch for markdown
        assert mock_get.call_count == 1
        assert OperatorConstants.Extraction.OUTPUT_FORMAT_HTML not in formats

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.requests.get")
    def test_v2_response_skips_artifact_with_missing_uri(self, mock_get, adapter):
        """Artifact with empty URI is skipped gracefully without crashing."""
        result = {"documents": [{"artifacts": [{"artifact_type": "markdown", "uri": ""}]}]}

        result_dict, _formats = adapter._extract_from_v2_response(result=result, file_path="doc.pdf")

        mock_get.assert_not_called()
        assert result_dict[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == ""

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.requests.get")
    def test_v2_response_failed_fetch_is_skipped(self, mock_get, adapter):
        """A fetch error on an artifact is logged and skipped; extraction continues."""
        mock_get.side_effect = Exception("network error")
        result = {"documents": [{"artifacts": [{"artifact_type": "markdown", "uri": "https://s3/md"}]}]}

        result_dict, _formats = adapter._extract_from_v2_response(result=result, file_path="doc.pdf")

        assert result_dict[OperatorConstants.Extraction.SUCCESS] is True
        assert result_dict[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == ""

    def test_v2_response_empty_documents_list(self, adapter):
        """v2 response with no documents returns empty markdown content."""
        result = {"documents": []}

        result_dict, formats = adapter._extract_from_v2_response(result=result, file_path="doc.pdf")

        assert result_dict[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == ""
        assert OperatorConstants.Extraction.OUTPUT_FORMAT_MARKDOWN in formats

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.requests.get")
    def test_v2_response_json_artifact_is_serialised(self, mock_get, adapter):
        """JSON artifact content is parsed and re-serialised to a string."""
        adapter_json = DoclingServeAdapter(
            config={
                "docling_serve_config": {"base_url": "http://localhost:5001"},
                "additional_formats": ["json"],
            }
        )
        mock_get.side_effect = [
            MagicMock(text="# Markdown", raise_for_status=MagicMock()),
            MagicMock(text='{"key": "value"}', raise_for_status=MagicMock()),
        ]
        result = {
            "documents": [
                {
                    "artifacts": [
                        {"artifact_type": "markdown", "uri": "https://s3/md"},
                        {"artifact_type": "json", "uri": "https://s3/json"},
                    ]
                }
            ]
        }

        result_dict, _formats = adapter_json._extract_from_v2_response(result=result, file_path="doc.pdf")

        json_col = OperatorConstants.Columns.CONTENT_JSON
        assert json_col in result_dict
        import json

        parsed = json.loads(result_dict[json_col])
        assert parsed["key"] == "value"

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_routes_to_v2_when_documents_key_present(self, mock_client_class, adapter):
        """extract_single_document uses v2 path when 'documents' key is in the API response."""
        mock_instance = MagicMock()
        mock_instance.process_document.return_value = {
            "documents": [{"artifacts": [{"artifact_type": "markdown", "uri": ""}]}],
            "processing_time": 1.0,
        }
        mock_client_class.return_value = mock_instance

        result = adapter.extract_single_document(file_path="doc.pdf", binary_content=b"data")

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert OperatorConstants.Metadata.METADATA in result

    @patch("docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient")
    def test_extract_single_document_routes_to_v1_when_document_key_present(self, mock_client_class, adapter):
        """extract_single_document uses v1 path when 'document' key is in the API response."""
        mock_instance = MagicMock()
        mock_instance.process_document.return_value = {
            "document": {"md_content": "# V1 Content"},
            "processing_time": 0.8,
        }
        mock_client_class.return_value = mock_instance

        result = adapter.extract_single_document(file_path="doc.pdf", binary_content=b"data")

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == "# V1 Content"
