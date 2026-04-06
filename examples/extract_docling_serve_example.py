#!/usr/bin/env python3
"""
Example: Document Extraction with Docling-Serve

This example demonstrates how to extract content from documents (PDFs, DOCX, etc.)
using the Docling-Serve API integration. Docling-Serve provides a REST API for
document processing with support for OCR, table extraction, and various PDF backends.

Prerequisites:
    1. Start docling-serve locally:
       docker run -p 5001:5001 ds4sd/docling-serve:latest

    2. Or use a remote docling-serve instance via --url argument:
       python extract_docling_serve_example.py --url http://jjojo1.fyre.ibm.com:5001

For more information on docling-serve:
    https://github.com/DS4SD/docling-serve
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa

# Add src to path for imports
sys.path.insert(
    0, str(Path(__file__).parent.parent / "src" / "datasift_opensource" / "backend")
)

from common.constants.operator_constants import OperatorConstants
from core.operators.extract.extract_docling import ExtractDoclingOperator

logger = logging.getLogger(__name__)


def main(docling_serve_base_url: str) -> int:
    """
    Main function to test the extract_docling_operator with docling-serve.
    Configure the variables below to test different extraction scenarios.

    Args:
        docling_serve_base_url: Base URL for the docling-serve API endpoint
    """
    # ============ CONFIGURATION VARIABLES ============
    # Set these variables to configure the extraction

    # Input: Path to file or directory
    input_path_str: str = "../tests/fixtures/invoices/TR-INV_044_1_1.1.pdf"

    # File pattern for directory processing (only used if input is a directory)
    file_pattern: str = "*.pdf"

    # ========== Docling-Serve Configuration ==========
    # Enable docling-serve integration
    use_docling_serve: bool = True

    # Docling-Serve API endpoint (passed via command-line argument)
    print(f"Using docling-serve at: {docling_serve_base_url}")

    # Optional API key for authentication (if required by your instance)
    docling_serve_api_key: str | None = None

    # Request timeout in seconds (default: 300)
    # Increase for large documents or slow processing
    docling_serve_timeout: int = 300

    # Polling interval in seconds for checking job status (default: 2)
    docling_serve_poll_interval: int = 2

    # Maximum number of retries for failed requests (default: 3)
    docling_serve_max_retries: int = 3

    # ========== OCR Configuration ==========
    # Enable OCR for scanned documents or images
    docling_serve_do_ocr: bool = True

    # OCR engine selection:
    # - "easyocr": EasyOCR engine (default, supports many languages)
    # - "tesseract": Tesseract OCR engine
    docling_serve_ocr_engine: str = "easyocr"

    # OCR languages (list of language codes)
    # Examples: ["en"], ["en", "es"], ["en", "fr", "de"]
    docling_serve_ocr_languages: list[str] = ["en"]

    # ========== PDF Processing Configuration ==========
    # PDF backend selection:
    # - "dlparse_v4": Docling parser v4 (default, recommended)
    # - "dlparse_v3": Docling parser v3 (legacy)
    # - "pypdfium2": PyPDFium2 backend
    docling_serve_pdf_backend: str = "dlparse_v4"

    # Table extraction mode:
    # - "accurate": High accuracy table extraction (slower)
    # - "fast": Fast table extraction (less accurate)
    docling_serve_table_mode: str = "accurate"

    # Image export mode:
    # - "embedded": Embed images in the output
    # - "referenced": Reference images by path
    # - "none": Do not export images
    docling_serve_image_export_mode: str = "embedded"

    # ================================================

    # Initialize operator with docling-serve configuration
    config: dict[str, Any] = {
        OperatorConstants.Columns.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
        OperatorConstants.Columns.DOC_ID_HASH: OperatorConstants.Columns.DOC_ID_HASH_DEFAULT,
        OperatorConstants.Config.EXTRACT_TABLES: True,
        OperatorConstants.Config.EXTRACT_IMAGES: True,
        # Docling-Serve configuration
        OperatorConstants.Config.USE_DOCLING_SERVE: use_docling_serve,
        OperatorConstants.Config.DOCLING_SERVE_BASE_URL: docling_serve_base_url,
        OperatorConstants.Config.DOCLING_SERVE_API_KEY: docling_serve_api_key,
        OperatorConstants.Config.DOCLING_SERVE_TIMEOUT: docling_serve_timeout,
        OperatorConstants.Config.DOCLING_SERVE_POLL_INTERVAL: docling_serve_poll_interval,
        OperatorConstants.Config.DOCLING_SERVE_MAX_RETRIES: docling_serve_max_retries,
        OperatorConstants.Config.DOCLING_SERVE_DO_OCR: docling_serve_do_ocr,
        OperatorConstants.Config.DOCLING_SERVE_OCR_ENGINE: docling_serve_ocr_engine,
        OperatorConstants.Config.DOCLING_SERVE_OCR_LANGUAGES: docling_serve_ocr_languages,
        OperatorConstants.Config.DOCLING_SERVE_PDF_BACKEND: docling_serve_pdf_backend,
        OperatorConstants.Config.DOCLING_SERVE_TABLE_MODE: docling_serve_table_mode,
        OperatorConstants.Config.DOCLING_SERVE_IMAGE_EXPORT_MODE: docling_serve_image_export_mode,
    }

    operator: ExtractDoclingOperator = ExtractDoclingOperator(config)

    input_path: Path = Path(input_path_str)

    if input_path.is_file():
        logger.info(f"Processing single file: {input_path}")

        # Read file
        with open(input_path, "rb") as f:
            binary_content = f.read()

        # Create PyArrow table
        table = pa.table(
            {
                OperatorConstants.Columns.ID: [str(input_path)],
                OperatorConstants.Columns.NAME: [input_path.name],
                OperatorConstants.Columns.PATH: [str(input_path)],
                OperatorConstants.Columns.BINARY_CONTENT: [binary_content],
            }
        )

        # Transform
        logger.info("Sending document to docling-serve for processing...")
        result_tables, metadata = operator.transform(table)
        result_table = result_tables[0]

        # Log results
        logger.info("Extraction complete!")
        logger.info(f"Metadata: {metadata}")
        logger.info(f"Result columns: {result_table.column_names}")

        # Use shorter aliases for readability
        cols = OperatorConstants.Columns

        if cols.DOC_COLUMN_DEFAULT in result_table.column_names:
            content = result_table[cols.DOC_COLUMN_DEFAULT][0].as_py()
            logger.info(f"Content length: {len(content) if content else 0} characters")
            if content:
                logger.info(f"Content preview: {content[:200]}...")

        if cols.EXTRACTED_DATA in result_table.column_names:
            extracted_data = result_table[cols.EXTRACTED_DATA][0].as_py()
            if extracted_data:
                logger.info(f"Extracted data length: {len(extracted_data)} characters")
                logger.info(f"Extracted data preview: {extracted_data[:200]}...")

        if cols.DOC_ID_HASH_DEFAULT in result_table.column_names:
            hash_id = result_table[cols.DOC_ID_HASH_DEFAULT][0].as_py()
            logger.info(f"Document hash: {hash_id}")

    elif input_path.is_dir():
        logger.info(f"Processing directory: {input_path}")
        files = list(input_path.glob(file_pattern))

        if not files:
            logger.warning(
                f"No files matching pattern '{file_pattern}' found in {input_path}"
            )
            return 1

        logger.info(f"Found {len(files)} files to process")

        # Process all files
        file_data = {
            OperatorConstants.Columns.ID: [],
            OperatorConstants.Columns.NAME: [],
            OperatorConstants.Columns.PATH: [],
            OperatorConstants.Columns.BINARY_CONTENT: [],
        }

        for file_path in files:
            with open(file_path, "rb") as f:
                binary_content = f.read()

            file_data[OperatorConstants.Columns.ID].append(str(file_path))
            file_data[OperatorConstants.Columns.NAME].append(file_path.name)
            file_data[OperatorConstants.Columns.PATH].append(str(file_path))
            file_data[OperatorConstants.Columns.BINARY_CONTENT].append(binary_content)

        # Create PyArrow table
        table = pa.table(file_data)

        # Transform
        logger.info("Sending documents to docling-serve for processing...")
        result_tables, metadata = operator.transform(table)
        result_table = result_tables[0]

        # Log results
        logger.info(f"Processed {len(files)} files")
        logger.info(f"Metadata: {metadata}")
        logger.info(f"Result columns: {result_table.column_names}")
        logger.info(f"Successfully processed: {metadata['processed_docs']} documents")
        logger.info(f"Failed: {metadata['failed_docs']} documents")

        # Show processing statistics
        if metadata.get("processing_time_seconds"):
            avg_time = metadata["processing_time_seconds"] / len(files)
            logger.info(f"Average processing time: {avg_time:.2f} seconds per document")

    else:
        logger.error(f"Input path does not exist: {input_path}")
        return 1

    return 0


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Extract content from documents using Docling-Serve API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example configurations for testing different scenarios:

1. Use default local URL:
   python extract_docling_serve_example.py

2. Use custom remote URL:
   python extract_docling_serve_example.py --url http://jjojo1.fyre.ibm.com:5001

3. Use HTTPS endpoint:
   python extract_docling_serve_example.py --url https://your-docling-serve.example.com
        """,
    )
    parser.add_argument(
        "--url",
        "--base-url",
        dest="url",
        type=str,
        default="http://0.0.0.0:5001",
        help="Base URL for the docling-serve API endpoint (default: http://0.0.0.0:5001)",
    )
    args = parser.parse_args()

    sys.exit(main(args.url))
