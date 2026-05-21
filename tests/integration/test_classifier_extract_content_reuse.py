#!/usr/bin/env python3
"""
Integration tests for content column management between document_classifier and extract operators.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pytest

from datasift.core.constants import DatasiftConstants, Metrics, OperatorConstants
from datasift.core.operators.extract import ExtractOperator
from datasift.core.operators.quality.classification.document_classifier import DocumentClassifierOperator

PDF_FIXTURE_PATH = Path("tests/fixtures/invoices/TR-INV_001_3_2.1.pdf")
CLASSIFIER_TEMP_COLUMN = DatasiftConstants.TEMP_CONTENT_COLUMN
REUSED_CONTENT = "Classifier-prefetched content for reuse path."
FRESH_LIBRARY_CONTENT = "Fresh docling_library extraction content."
FRESH_SERVE_CONTENT = "Fresh docling_serve extraction content."


def _build_pdf_input_table() -> pa.Table:
    binary_content = PDF_FIXTURE_PATH.read_bytes()
    return pa.table(
        {
            OperatorConstants.Columns.ID: ["doc-1"],
            OperatorConstants.Columns.NAME: [PDF_FIXTURE_PATH.name],
            OperatorConstants.Columns.PATH: [str(PDF_FIXTURE_PATH)],
            OperatorConstants.Columns.BINARY_CONTENT: [binary_content],
        }
    )


def _build_classifier_config() -> dict:
    return {
        OperatorConstants.Config.PROVIDER: "ollama",
        OperatorConstants.Config.PROVIDER_CONFIG: {},
        OperatorConstants.Config.MODEL_ID: "granite4:latest",
        OperatorConstants.Config.DOCUMENT_TYPES: ["invoice", "receipt", "contract"],
        OperatorConstants.Config.CONFIDENCE_THRESHOLD: 7.0,
        OperatorConstants.Columns.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
        OperatorConstants.Columns.OUTPUT_COLUMN: OperatorConstants.Columns.DOCUMENT_TYPE,
        OperatorConstants.Config.INCLUDE_CONFIDENCE: True,
        OperatorConstants.Config.INCLUDE_REASONING: True,
        OperatorConstants.Config.MAX_WORKERS: 1,
    }


def _build_extract_config(*, text_extraction_mode: str) -> dict:
    config = {
        OperatorConstants.ExtractionModes.TEXT_EXTRACTION_MODE: text_extraction_mode,
        OperatorConstants.ExtractionModes.ENTITY_EXTRACTION_MODE: OperatorConstants.ExtractionModes.ENTITY_MODE_NONE,
        OperatorConstants.Columns.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
        OperatorConstants.Config.EXTRACT_TABLES: False,
        OperatorConstants.Config.EXTRACT_IMAGES: False,
        OperatorConstants.Config.MAX_WORKERS: 1,
        OperatorConstants.Config.USE_PROCESSES: False,
    }
    if text_extraction_mode == OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_SERVE:
        config[OperatorConstants.Config.DOCLING_SERVE_BASE_URL] = "http://localhost:5001"
    return config


def _mock_classification_response() -> str:
    return json.dumps(
        {
            "document_type": "invoice",
            "confidence": 9,
            "reasoning": "The document contains invoice-like content.",
        }
    )


@pytest.mark.integration
def test_classifier_content_reuse_with_docling_library():
    extract_operator = ExtractOperator(
        config=_build_extract_config(text_extraction_mode=OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY)
    )

    classifier_output = pa.table(
        {
            OperatorConstants.Columns.ID: ["doc-1"],
            OperatorConstants.Columns.NAME: [PDF_FIXTURE_PATH.name],
            OperatorConstants.Columns.PATH: [str(PDF_FIXTURE_PATH)],
            OperatorConstants.Columns.BINARY_CONTENT: [PDF_FIXTURE_PATH.read_bytes()],
            CLASSIFIER_TEMP_COLUMN: [REUSED_CONTENT],
            OperatorConstants.Columns.DOCUMENT_TYPE: ["invoice"],
        }
    )
    with patch(
        "datasift.core.operators.extract.adapters.outbound.text_extraction.docling_adapter.OperatorUtils.extract_content"
    ) as mock_docling_extract_content:
        extract_tables, extract_metadata = extract_operator.transform(
            classifier_output,
            metadata=extract_operator.create_base_metadata(total_docs_count=classifier_output.num_rows),
        )
        extract_output = extract_tables[0]

        # Verify content reuse: extraction method should not be called
        mock_docling_extract_content.assert_not_called()
        assert OperatorConstants.Columns.DOC_COLUMN_DEFAULT in extract_output.column_names
        assert CLASSIFIER_TEMP_COLUMN not in extract_output.column_names
        assert extract_output[OperatorConstants.Columns.DOC_COLUMN_DEFAULT].to_pylist() == [REUSED_CONTENT]
        assert extract_metadata[Metrics.External.PROCESSED_DOCS] == 1


@pytest.mark.integration
def test_classifier_content_reextraction_with_docling_serve():
    input_table = _build_pdf_input_table()

    classifier = DocumentClassifierOperator(_build_classifier_config())

    with (
        patch.object(
            classifier.classification_service,
            "classify_document",
            return_value=type(
                "ClassificationResponse",
                (),
                {
                    "success": True,
                    "document_type": "invoice",
                    "confidence": 9,
                    "reasoning": "The document contains invoice-like content.",
                },
            )(),
        ),
        patch(
            "datasift.core.operators.quality.classification.document_classifier.OperatorUtils.extract_content",
            side_effect=lambda *args, **kwargs: {
                OperatorConstants.Extraction.SUCCESS: True,
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: REUSED_CONTENT,
            },
        ) as mock_extract_content,
        patch(
            "datasift.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter.DoclingServeClient"
        ) as mock_docling_serve_client_class,
    ):
        mock_docling_serve_client = mock_docling_serve_client_class.return_value
        mock_docling_serve_client.process_document.return_value = {
            "document": {"md_content": FRESH_SERVE_CONTENT},
            "processing_time": 1.25,
            "page_count": 1,
        }

        classifier_tables, _classifier_metadata = classifier.transform(input_table)
        classifier_output = classifier_tables[0]

        assert CLASSIFIER_TEMP_COLUMN in classifier_output.column_names
        assert classifier_output[CLASSIFIER_TEMP_COLUMN].to_pylist() == [REUSED_CONTENT]
        extract_operator = ExtractOperator(
            config=_build_extract_config(text_extraction_mode=OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_SERVE)
        )
        extract_tables, extract_metadata = extract_operator.transform(
            classifier_output,
            metadata=extract_operator.create_base_metadata(total_docs_count=classifier_output.num_rows),
        )
        extract_output = extract_tables[0]

        assert mock_extract_content.call_count == 1
        mock_docling_serve_client.process_document.assert_called_once()
        assert OperatorConstants.Columns.DOC_COLUMN_DEFAULT in extract_output.column_names
        assert CLASSIFIER_TEMP_COLUMN not in extract_output.column_names
        assert extract_output[OperatorConstants.Columns.DOC_COLUMN_DEFAULT].to_pylist() == [FRESH_SERVE_CONTENT]
        assert extract_metadata[Metrics.External.PROCESSED_DOCS] == 1


@pytest.mark.integration
def test_extract_backward_compatibility_without_classifier():
    input_table = _build_pdf_input_table()

    with patch(
        "datasift.core.operators.extract.adapters.outbound.text_extraction.docling_adapter.OperatorUtils.extract_content",
        return_value={
            OperatorConstants.Extraction.SUCCESS: True,
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: FRESH_LIBRARY_CONTENT,
            OperatorConstants.Metadata.METADATA: {"page_count": 1},
        },
    ) as mock_docling_extract_content:
        extract_operator = ExtractOperator(
            config=_build_extract_config(
                text_extraction_mode=OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY
            )
        )
        extract_tables, extract_metadata = extract_operator.transform(input_table)
        extract_output = extract_tables[0]

        mock_docling_extract_content.assert_called_once()
        assert OperatorConstants.Columns.DOC_COLUMN_DEFAULT in extract_output.column_names
        assert CLASSIFIER_TEMP_COLUMN not in extract_output.column_names
        assert extract_output[OperatorConstants.Columns.DOC_COLUMN_DEFAULT].to_pylist() == [FRESH_LIBRARY_CONTENT]
        assert extract_metadata[Metrics.External.PROCESSED_DOCS] == 1
