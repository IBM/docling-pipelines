#!/usr/bin/env python3
"""
Example: Document Extraction with Docling

This example demonstrates how to extract content from documents (PDFs, DOCX, etc.)
using the Docling extraction operator. Supports both basic markdown extraction
and template-based structured extraction.
"""

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


def main() -> int:
    """
    Main function to test the extract_docling_operator.
    Configure the variables below to test different extraction scenarios.
    """
    # ============ CONFIGURATION VARIABLES ============
    # Set these variables to configure the extraction

    # Input: Path to file or directory
    input_path_str: str = "tests/fixtures/invoices/TR-INV_044_1_1.1.pdf"

    # Extraction mode selection (only one can be True at a time):
    # - use_template: Template-based structured extraction
    # - use_vlm_pipeline: VLM (Vision Language Model) enhanced extraction
    # - Neither: Basic markdown extraction
    use_template: bool = False
    use_vlm_pipeline: bool = False  # Requires: pip install docling[vlm]

    # VLM Pipeline configuration (only used if use_vlm_pipeline=True)
    # Default: "granite_docling"
    vlm_preset: str = OperatorConstants.Config.VLM_PRESET_DEFAULT

    # VLM Engine Type - Choose one:
    # Local engines:
    #   - VLM_ENGINE_TRANSFORMERS: Local inference using Transformers (default)
    #   - VLM_ENGINE_MLX: Local inference optimized for macOS (Apple Silicon)
    # API-based engines:
    #   - VLM_ENGINE_API: Generic API endpoint (requires vlm_api_base_url)
    #   - VLM_ENGINE_API_LMSTUDIO: LMStudio API
    #   - VLM_ENGINE_API_OLLAMA: Ollama API
    #   - VLM_ENGINE_API_OPENAI: OpenAI API
    #   - VLM_ENGINE_API_WATSONX: IBM watsonx.ai API (requires vlm_api_key)
    vlm_engine_type: str = OperatorConstants.Config.VLM_ENGINE_TRANSFORMERS

    # API Configuration (only used for API-based engines)
    vlm_api_base_url: str | None = None  # e.g., "http://localhost:1234/v1"
    vlm_api_key: str | None = None  # Required for watsonx, optional for others

    # File pattern for directory processing (only used if input is a directory)
    file_pattern: str = "*.pdf"

    # ================================================

    # Define invoice template for structured extraction
    invoice_template: dict[str, str] = {
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

    # Initialize operator
    config: dict[str, Any] = {
        OperatorConstants.Columns.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
        OperatorConstants.Columns.DOC_ID_HASH: OperatorConstants.Columns.DOC_ID_HASH_DEFAULT,
        OperatorConstants.Config.EXTRACT_TABLES: True,
        OperatorConstants.Config.EXTRACT_IMAGES: True,
        OperatorConstants.Config.USE_TEMPLATE: use_template,
        OperatorConstants.Config.TEMPLATE: invoice_template if use_template else None,
        OperatorConstants.Config.USE_VLM_PIPELINE: use_vlm_pipeline,
        OperatorConstants.Config.VLM_PRESET: vlm_preset,
        OperatorConstants.Config.VLM_ENGINE_TYPE: vlm_engine_type
        if use_vlm_pipeline
        else None,
        OperatorConstants.Config.VLM_API_BASE_URL: vlm_api_base_url
        if use_vlm_pipeline
        else None,
        OperatorConstants.Config.VLM_API_KEY: vlm_api_key if use_vlm_pipeline else None,
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
        result_tables, metadata = operator.transform(table)
        result_table = result_tables[0]

        # Log results
        logger.info(f"Processed {len(files)} files")
        logger.info(f"Metadata: {metadata}")
        logger.info(f"Result columns: {result_table.column_names}")
        logger.info(f"Processed: {metadata['processed_docs']} documents")
        logger.info(f"Failed: {metadata['failed_docs']} documents")

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

    # Example configurations for testing different VLM engines:
    #
    # 1. Local Transformers (default):
    #    use_vlm_pipeline = True
    #    vlm_engine_type = OperatorConstants.Config.VLM_ENGINE_TRANSFORMERS
    #
    # 2. Local MLX (macOS Apple Silicon):
    #    use_vlm_pipeline = True
    #    vlm_engine_type = OperatorConstants.Config.VLM_ENGINE_MLX
    #
    # 3. Generic API:
    #    use_vlm_pipeline = True
    #    vlm_engine_type = OperatorConstants.Config.VLM_ENGINE_API
    #    vlm_api_base_url = "http://localhost:8000/v1"
    #
    # 4. LMStudio API:
    #    use_vlm_pipeline = True
    #    vlm_engine_type = OperatorConstants.Config.VLM_ENGINE_API_LMSTUDIO
    #
    # 5. Ollama API:
    #    use_vlm_pipeline = True
    #    vlm_engine_type = OperatorConstants.Config.VLM_ENGINE_API_OLLAMA
    #
    # 6. OpenAI API:
    #    use_vlm_pipeline = True
    #    vlm_engine_type = OperatorConstants.Config.VLM_ENGINE_API_OPENAI
    #
    # 7. IBM watsonx.ai API:
    #    use_vlm_pipeline = True
    #    vlm_engine_type = OperatorConstants.Config.VLM_ENGINE_API_WATSONX
    #    vlm_api_base_url = "https://us-south.ml.cloud.ibm.com/ml/v1/..."
    #    vlm_api_key = "your-ibm-cloud-api-key"  # pragma: allowlist secret

    sys.exit(main())

# Made with Bob
