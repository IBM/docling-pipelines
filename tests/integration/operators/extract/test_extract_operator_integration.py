#!/usr/bin/env python3
"""
Integration tests for ExtractOperator.

These tests verify the operator works with real extraction scenarios,
including actual document processing and parallel execution.

Note: These tests require Docling dependencies and may be skipped
if dependencies are not available.
"""

from pathlib import Path

import pyarrow as pa
import pytest

from docpipe.core.operators.extract.extract_operator import ExtractOperator


@pytest.mark.integration
class TestExtractOperatorIntegration:
    """Integration test suite for ExtractOperator"""

    @pytest.fixture
    def sample_pdf_content(self):
        """Create a minimal PDF-like binary content for testing"""
        # This is a minimal PDF structure for testing
        # In real scenarios, use actual PDF files
        pdf_header = b"%PDF-1.4\n"
        pdf_content = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        pdf_pages = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        pdf_page = b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>\nendobj\n"
        pdf_stream = (
            b"4 0 obj\n<< /Length 44 >>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(Test Document) Tj\nET\nendstream\nendobj\n"
        )
        pdf_xref = b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000179 00000 n\n"
        pdf_trailer = b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n283\n%%EOF\n"

        return pdf_header + pdf_content + pdf_pages + pdf_page + pdf_stream + pdf_xref + pdf_trailer

    @pytest.fixture
    def sample_documents_table(self, sample_pdf_content):
        """Create a PyArrow table with sample documents"""
        return pa.table(
            {
                "id": ["doc1", "doc2", "doc3"],
                "name": ["test1.pdf", "test2.pdf", "test3.pdf"],
                "path": ["/tmp/test1.pdf", "/tmp/test2.pdf", "/tmp/test3.pdf"],
                "binary_content": [sample_pdf_content, sample_pdf_content, sample_pdf_content],
            }
        )

    @pytest.mark.skip(reason="Requires Docling library and dependencies")
    def test_basic_extraction_integration(self, sample_documents_table):
        """Test basic extraction with real PyArrow table"""
        config = {
            "text_extraction": {
                "provider": "docling_library",
                "doc_column": "document",
                "provider_config": {"max_workers": 2},
            },
            "entity_extraction": {"provider": "none"},
        }

        operator = ExtractOperator(config=config)
        result_tables, metadata = operator.transform(sample_documents_table)

        # Verify results
        assert len(result_tables) > 0
        result_table = result_tables[0]

        # Check that document column exists
        assert "document" in result_table.column_names

        # Check metadata
        assert "processed_docs" in metadata
        assert "total_docs" in metadata
        assert metadata["total_docs"] == 3

    @pytest.mark.skip(reason="Requires Docling library and template support")
    def test_template_extraction_integration(self):
        """Test template-based extraction with structured data"""
        # Create sample invoice-like content
        invoice_content = b"""
        INVOICE
        Invoice Number: INV-001
        Date: 2024-01-15
        Total: $1000.00
        """

        table = pa.table(
            {
                "id": ["invoice1"],
                "name": ["invoice.txt"],
                "binary_content": [invoice_content],
            }
        )

        config = {
            "text_extraction": {
                "provider": "docling_library",
                "doc_column": "document",
                "provider_config": {
                    "extraction_mode": "template",
                    "use_template": True,
                    "template": {
                        "invoice_number": "string",
                        "date": "string",
                        "total": "float",
                    },
                    "max_workers": 1,
                },
            },
            "entity_extraction": {"provider": "none"},
        }

        operator = ExtractOperator(config=config)
        result_tables, metadata = operator.transform(table)

        # Verify structured data extraction
        result_table = result_tables[0]
        assert "extracted_data" in result_table.column_names

        # Check that extraction succeeded
        assert metadata["processed_docs"] >= 1

    @pytest.mark.skip(reason="Requires VLM models and GPU resources")
    def test_vlm_extraction_integration(self, sample_documents_table):
        """Test VLM extraction with complex documents"""
        config = {
            "text_extraction": {
                "provider": "docling_library",
                "doc_column": "document",
                "provider_config": {
                    "vlm_pipeline": {"preset": "granite_docling", "engine": "transformers"},
                    "max_workers": 1,  # VLM is resource-intensive
                },
            },
            "entity_extraction": {"provider": "none"},
        }

        operator = ExtractOperator(config=config)
        result_tables, metadata = operator.transform(sample_documents_table)

        # Verify results
        assert len(result_tables) > 0
        result_table = result_tables[0]
        assert "document" in result_table.column_names

        # VLM should provide high-quality extraction
        assert metadata["processed_docs"] > 0

    @pytest.mark.skip(reason="Requires Docling-Serve running on localhost:5001")
    def test_docling_serve_extraction_integration(self, sample_documents_table):
        """Test Docling Serve extraction with remote API"""
        config = {
            "text_extraction": {
                "provider": "docling_serve",
                "doc_column": "document",
                "provider_config": {
                    "base_url": "http://localhost:5001",
                    "timeout": 300,
                    "do_ocr": True,
                    "ocr_engine": "easyocr",
                    "pdf_backend": "dlparse_v4",
                },
            },
            "entity_extraction": {"provider": "none"},
        }

        operator = ExtractOperator(config=config)
        result_tables, metadata = operator.transform(sample_documents_table)

        # Verify results
        assert len(result_tables) > 0
        result_table = result_tables[0]
        assert "document" in result_table.column_names

        # Check metadata
        assert metadata["processed_docs"] > 0
        assert "failed_docs_count" in metadata

    def test_parallel_processing_with_multiple_workers(self, sample_documents_table):
        """Test parallel processing with multiple workers (mocked)"""
        # This test uses mocking to verify parallel processing logic
        # without requiring actual Docling dependencies
        from unittest.mock import MagicMock, patch

        with patch(
            "docpipe.core.operators.extract.adapters.outbound.factories.text_extraction_adapter_factory.TextExtractionAdapterFactory.create_adapter"
        ) as mock_create:
            # Setup mock adapter
            mock_adapter = MagicMock()
            mock_result_table = pa.table(
                {
                    "id": ["doc1", "doc2", "doc3"],
                    "doc_content": ["content1", "content2", "content3"],
                    "doc_id_hash": ["hash1", "hash2", "hash3"],
                }
            )
            mock_metadata = {
                "processed_docs": 3,
                "total_docs": 3,
                "failed_docs_count": 0,
            }
            mock_adapter.transform.return_value = ([mock_result_table], mock_metadata)
            mock_create.return_value = mock_adapter

            config = {
                "text_extraction": {"doc_column": "doc_content", "provider": "docling_library"},
                "entity_extraction": {"provider": "none"},
                "max_workers": 4,
            }

            operator = ExtractOperator(config=config)
            _result_tables, metadata = operator.transform(sample_documents_table)

            # Verify parallel processing was invoked
            assert mock_adapter.transform.called
            assert metadata["processed_docs"] == 3

    def test_error_handling_with_invalid_documents(self):
        """Test error handling with invalid document content"""
        # Create table with invalid binary content
        table = pa.table(
            {
                "id": ["bad_doc"],
                "name": ["invalid.pdf"],
                "binary_content": [b"not a valid pdf"],
            }
        )

        from unittest.mock import MagicMock, patch

        with patch(
            "docpipe.core.operators.extract.adapters.outbound.factories.text_extraction_adapter_factory.TextExtractionAdapterFactory.create_adapter"
        ) as mock_create:
            # Setup mock adapter that handles errors gracefully
            mock_adapter = MagicMock()
            mock_result_table = pa.table(
                {
                    "id": ["bad_doc"],
                    "doc_content": [None],
                    "doc_id_hash": ["hash1"],
                }
            )
            mock_metadata = {
                "processed_docs": 0,
                "total_docs": 1,
                "failed_docs_count": 1,
                "failed_docs": [{"id": "bad_doc", "error": "Invalid document"}],
            }
            mock_adapter.transform.return_value = ([mock_result_table], mock_metadata)
            mock_create.return_value = mock_adapter

            config = {
                "text_extraction": {"doc_column": "doc_content", "provider": "docling_library"},
                "entity_extraction": {"provider": "none"},
            }

            operator = ExtractOperator(config=config)
            _result_tables, metadata = operator.transform(table)

            # Verify error was handled
            assert metadata["failed_docs_count"] == 1
            assert len(metadata["failed_docs"]) == 1

    def test_metadata_propagation(self, sample_documents_table):
        """Test that metadata is properly propagated through the pipeline"""
        from unittest.mock import MagicMock, patch

        with patch(
            "docpipe.core.operators.extract.adapters.outbound.factories.text_extraction_adapter_factory.TextExtractionAdapterFactory.create_adapter"
        ) as mock_create:
            mock_adapter = MagicMock()
            mock_result_table = pa.table(
                {
                    "id": ["doc1"],
                    "doc_content": ["content"],
                    "doc_id_hash": ["hash1"],
                }
            )
            mock_metadata = {
                "processed_docs": 1,
                "total_docs": 1,
                "custom_field": "custom_value",
            }
            mock_adapter.transform.return_value = ([mock_result_table], mock_metadata)
            mock_create.return_value = mock_adapter

            config = {"text_extraction": {"provider": "docling_library"}, "entity_extraction": {"provider": "none"}}
            operator = ExtractOperator(config=config)

            # Pass initial metadata
            initial_metadata = {"upstream_operator": "test_ingest"}
            _result_tables, metadata = operator.transform(sample_documents_table, metadata=initial_metadata)

            # Verify metadata includes both initial and result metadata
            assert "processed_docs" in metadata
            assert metadata["custom_field"] == "custom_value"


@pytest.mark.integration
class TestExtractOperatorRealWorld:
    """Real-world integration tests (require actual dependencies)"""

    @pytest.mark.skip(reason="Requires actual PDF files and Docling installation")
    def test_extract_real_pdf_documents(self):
        """Test extraction with real PDF documents from fixtures"""
        # This test would use actual PDF files from a fixtures directory
        fixtures_dir = Path(__file__).parent / "fixtures"

        if not fixtures_dir.exists():
            pytest.skip("Fixtures directory not found")

        pdf_files = list(fixtures_dir.glob("*.pdf"))
        if not pdf_files:
            pytest.skip("No PDF files found in fixtures")

        # Create table from real files
        documents = []
        for pdf_file in pdf_files[:3]:  # Test with first 3 files
            with Path(pdf_file).open("rb") as f:
                content = f.read()
            documents.append(
                {
                    "id": pdf_file.stem,
                    "name": pdf_file.name,
                    "path": str(pdf_file),
                    "binary_content": content,
                }
            )

        table = pa.table(
            {
                "id": [doc["id"] for doc in documents],
                "name": [doc["name"] for doc in documents],
                "path": [doc["path"] for doc in documents],
                "binary_content": [doc["binary_content"] for doc in documents],
            }
        )

        config = {
            "text_extraction": {
                "provider": "docling_library",
                "doc_column": "document",
                "provider_config": {"max_workers": 2},
            },
            "entity_extraction": {"provider": "none"},
        }

        operator = ExtractOperator(config=config)
        result_tables, metadata = operator.transform(table)

        # Verify extraction succeeded
        assert metadata["processed_docs"] > 0
        assert len(result_tables) > 0
        assert "page_type_stats" in metadata
        assert "total_pages_converted" in metadata

        # Verify content was extracted
        result_table = result_tables[0]
        assert "document" in result_table.column_names
        assert "pages_processed" in result_table.column_names

        # Check that extracted content is not empty
        for content in result_table["document"].to_pylist():
            if content is not None:
                assert len(content) > 0

    @pytest.mark.skip(reason="Requires Docling-Serve setup and configuration")
    def test_docling_serve_with_ocr(self):
        """Test Docling Serve with OCR on scanned documents"""
        # This test would use scanned PDF documents that require OCR
        # Requires Docling-Serve running with OCR enabled

    @pytest.mark.skip(reason="Requires VLM models and significant compute resources")
    def test_vlm_with_complex_layouts(self):
        """Test VLM extraction on documents with complex layouts"""
        # This test would use documents with tables, images, and complex formatting
        # Requires VLM models and GPU resources

    def test_template_extraction_with_expansion(self):
        """Test template extraction with expand_extracted_data enabled"""
        from unittest.mock import MagicMock, patch

        # Create sample table
        table = pa.table(
            {
                "id": ["invoice1", "invoice2"],
                "name": ["invoice1.pdf", "invoice2.pdf"],
                "binary_content": [b"dummy content 1", b"dummy content 2"],
            }
        )

        with (
            patch(
                "docpipe.core.operators.extract.adapters.outbound.factories.text_extraction_adapter_factory.TextExtractionAdapterFactory.create_adapter"
            ) as mock_text_create,
            patch(
                "docpipe.core.operators.extract.adapters.outbound.factories.entity_extraction_adapter_factory.EntityExtractionAdapterFactory.create_adapter"
            ) as mock_entity_create,
        ):
            # Setup mock text extraction adapter
            mock_text_adapter = MagicMock()
            mock_text_table = pa.table(
                {
                    "id": ["invoice1", "invoice2"],
                    "name": ["invoice1.pdf", "invoice2.pdf"],
                    "content": ["extracted content 1", "extracted content 2"],
                }
            )
            mock_text_metadata = {
                "processed_docs": 2,
                "total_docs": 2,
                "failed_docs_count": 0,
            }
            mock_text_adapter.transform.return_value = ([mock_text_table], mock_text_metadata)
            mock_text_create.return_value = mock_text_adapter

            # Setup mock entity extraction adapter
            mock_entity_adapter = MagicMock()

            # Simulate extracted structured data
            extracted_data_list = [
                {"invoice_number": "INV-001", "total_amount": "1000.00", "vendor": "Acme Corp"},
                {"invoice_number": "INV-002", "total_amount": "2000.00", "vendor": "XYZ Inc"},
            ]

            # Create result table with extracted_data column and expanded columns
            import json

            mock_result_table = pa.table(
                {
                    "id": ["invoice1", "invoice2"],
                    "name": ["invoice1.pdf", "invoice2.pdf"],
                    "content": ["extracted content 1", "extracted content 2"],
                    "doc_id_hash": ["hash1", "hash2"],
                    "extracted_data": [json.dumps(data) for data in extracted_data_list],
                    # Expanded columns
                    "extracted_invoice_number": ["INV-001", "INV-002"],
                    "extracted_total_amount": ["1000.00", "2000.00"],
                    "extracted_vendor": ["Acme Corp", "XYZ Inc"],
                }
            )

            mock_entity_metadata = {
                "processed_docs": 2,
                "total_docs": 2,
                "failed_docs_count": 0,
            }

            mock_entity_adapter.transform.return_value = ([mock_result_table], mock_entity_metadata)
            mock_entity_create.return_value = mock_entity_adapter

            # Create operator with expand_extracted_data enabled
            config = {
                "text_extraction": {"provider": "docling_library"},
                "entity_extraction": {"provider": "docling"},
                "custom_schema": {
                    "type": "object",
                    "properties": {
                        "invoice_number": {"type": "string"},
                        "total_amount": {"type": "number"},
                        "vendor": {"type": "string"},
                    },
                },
                "expand_extracted_data": True,
                "doc_column": "content",
                "output_column": "extracted_data",
                "max_workers": 2,
            }

            operator = ExtractOperator(config=config)
            result_tables, metadata = operator.transform(table)

            # Verify results
            assert len(result_tables) > 0
            result_table = result_tables[0]

            # Verify extracted_data column exists (configured via output_column)
            assert "extracted_data" in result_table.column_names

            # Verify expanded columns exist
            assert "extracted_invoice_number" in result_table.column_names
            assert "extracted_total_amount" in result_table.column_names
            assert "extracted_vendor" in result_table.column_names

            # Verify expanded column values
            invoice_numbers = result_table.column("extracted_invoice_number").to_pylist()
            assert invoice_numbers == ["INV-001", "INV-002"]

            total_amounts = result_table.column("extracted_total_amount").to_pylist()
            assert total_amounts == ["1000.00", "2000.00"]

            vendors = result_table.column("extracted_vendor").to_pylist()
            assert vendors == ["Acme Corp", "XYZ Inc"]

            # Verify metadata
            assert metadata["processed_docs"] == 2
            assert metadata["failed_docs_count"] == 0
