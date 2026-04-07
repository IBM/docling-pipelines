#!/usr/bin/env python3
"""
Example: Document Extraction with Docling

This example demonstrates how to extract content from documents (PDFs, DOCX, etc.)
using the Docling extraction operator. Supports both basic markdown extraction
and template-based structured extraction.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa
import requests

# Add src to path for imports
sys.path.insert(
    0, str(Path(__file__).parent.parent / "src" / "datasift_opensource" / "backend")
)

from common.constants.operator_constants import OperatorConstants
from core.operators.extract.extract_docling import ExtractDoclingOperator

logger = logging.getLogger(__name__)


def check_and_pull_ollama_model(
    model_name: str, api_base_url: str = "http://localhost:11434"
) -> bool:
    """Check if model exists in Ollama and attempt to pull if not.

    Args:
        model_name: The model name to check/pull
        api_base_url: Ollama API base URL (default: http://localhost:11434)

    Returns:
        True if model exists or successfully pulled, False otherwise
    """
    try:
        # Check if model exists
        response = requests.get(f"{api_base_url}/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [m.get("name") for m in models]
            # Check for exact match or with :latest tag
            if model_name in model_names or f"{model_name}:latest" in model_names:
                logger.info(f"Model '{model_name}' is already available in Ollama")
                return True

            # Try to pull the model using Ollama API
            logger.info(f"Attempting to pull model '{model_name}' in Ollama...")
            logger.info("This may take a few minutes...")

            # Ollama pull API endpoint
            pull_response = requests.post(
                f"{api_base_url}/api/pull",
                json={"name": model_name},
                stream=True,
                timeout=300,
            )

            if pull_response.status_code == 200:
                # Stream the response to show progress
                for line in pull_response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            status = data.get("status", "")
                            if status:
                                print(f"  {status}", end="\r")
                        except json.JSONDecodeError:
                            pass
                print()  # New line after progress
                logger.info(f"Successfully pulled model '{model_name}'")
                return True
            else:
                logger.error(f"Failed to pull model: HTTP {pull_response.status_code}")
                return False
        return False
    except requests.exceptions.Timeout:
        logger.error("Timeout while trying to pull model (this can take a while)")
        logger.error(f"Please try pulling manually: ollama pull {model_name}")
        return False
    except Exception as e:
        logger.error(f"Error checking/pulling model: {e}")
        return False


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
    #   - VLM_ENGINE_API_OPENAI: OpenAI API (requires vlm_api_key and model_name)
    #   - VLM_ENGINE_API_WATSONX: IBM watsonx.ai API (requires vlm_api_key)
    vlm_engine_type: str = OperatorConstants.Config.VLM_ENGINE_API_WATSONX

    # Common API Configuration (used by multiple API-based engines)
    vlm_api_base_url: str | None = None
    vlm_api_key: str | None = None  # pragma: allowlist secret

    # WatsonX-specific Configuration
    vlm_watsonx_container_kind: str | None = "project"  # Required for watsonx
    vlm_watsonx_container_id: str | None = ""  # Required for watsonx
    vlm_model_name: str | None = (
        "meta-llama/llama-3-2-11b-vision-instruct"  # Required for watsonx and OpenAI
    )

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

    # Build VLM provider config for API-based engines
    vlm_provider_config: dict[str, Any] | None = None
    if use_vlm_pipeline and vlm_engine_type:
        # All API-based engines need provider config
        if vlm_engine_type in [
            OperatorConstants.Config.VLM_ENGINE_API,
            OperatorConstants.Config.VLM_ENGINE_API_LMSTUDIO,
            OperatorConstants.Config.VLM_ENGINE_API_OLLAMA,
            OperatorConstants.Config.VLM_ENGINE_API_OPENAI,
            OperatorConstants.Config.VLM_ENGINE_API_WATSONX,
        ]:
            vlm_provider_config = {}

            # Add API base URL if provided
            if vlm_api_base_url:
                vlm_provider_config[OperatorConstants.Config.VLM_API_BASE_URL] = (
                    vlm_api_base_url
                )

            # Add API key if provided (used by OpenAI, WatsonX, and generic API)
            if vlm_api_key:
                vlm_provider_config[OperatorConstants.Config.VLM_API_KEY] = vlm_api_key

            # Add Ollama-specific configs
            if vlm_engine_type == OperatorConstants.Config.VLM_ENGINE_API_OLLAMA:
                # Override model name to use Ollama format instead of preset default
                vlm_provider_config[OperatorConstants.Config.VLM_MODEL_NAME] = (
                    "ibm/granite-docling:258m"
                )

            # Add OpenAI-specific configs
            if vlm_engine_type == OperatorConstants.Config.VLM_ENGINE_API_OPENAI:
                if vlm_model_name:
                    vlm_provider_config[OperatorConstants.Config.VLM_MODEL_NAME] = (
                        vlm_model_name
                    )

            # Add WatsonX-specific configs
            if vlm_engine_type == OperatorConstants.Config.VLM_ENGINE_API_WATSONX:
                if vlm_watsonx_container_kind:
                    vlm_provider_config[
                        OperatorConstants.Config.VLM_WATSONX_CONTAINER_KIND
                    ] = vlm_watsonx_container_kind
                if vlm_watsonx_container_id:
                    vlm_provider_config[
                        OperatorConstants.Config.VLM_WATSONX_CONTAINER_ID
                    ] = vlm_watsonx_container_id
                if vlm_model_name:
                    vlm_provider_config[OperatorConstants.Config.VLM_MODEL_NAME] = (
                        vlm_model_name
                    )

    # Check and pull Ollama model if using VLM pipeline with Ollama
    if (
        use_vlm_pipeline
        and vlm_engine_type == OperatorConstants.Config.VLM_ENGINE_API_OLLAMA
    ):
        # Use the official Ollama model for granite-docling
        ollama_model_name = "ibm/granite-docling:258m"
        ollama_api_url = (
            vlm_api_base_url if vlm_api_base_url else "http://localhost:11434"
        )

        logger.info(f"Checking Ollama model: {ollama_model_name}")
        if not check_and_pull_ollama_model(ollama_model_name, ollama_api_url):
            logger.error(f"Failed to ensure model '{ollama_model_name}' is available")
            logger.error(
                "Please install the model manually: ollama pull ibm/granite-docling:258m"
            )
            return 1

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
        OperatorConstants.Config.VLM_PROVIDER_CONFIG: vlm_provider_config,
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
    #    # No vlm_provider_config needed for local engines
    #
    # 2. Local MLX (macOS Apple Silicon):
    #    use_vlm_pipeline = True
    #    vlm_engine_type = OperatorConstants.Config.VLM_ENGINE_MLX
    #    # No vlm_provider_config needed for local engines
    #
    # 3. Generic API:
    #    use_vlm_pipeline = True
    #    vlm_engine_type = OperatorConstants.Config.VLM_ENGINE_API
    #    vlm_provider_config = {
    #        OperatorConstants.Config.VLM_API_BASE_URL: "http://localhost:8000/v1/chat",
    #        OperatorConstants.Config.VLM_API_KEY: "your-api-key"  # Optional  # pragma: allowlist secret
    #    }
    #
    # 4. LMStudio API:
    #    use_vlm_pipeline = True
    #    vlm_engine_type = OperatorConstants.Config.VLM_ENGINE_API_LMSTUDIO
    #    vlm_provider_config = {
    #        OperatorConstants.Config.VLM_API_BASE_URL: "http://localhost:1234/v1/chat/completions"  # Optional, defaults to this
    #    }
    #
    # 5. Ollama API:
    #    use_vlm_pipeline = True
    #    vlm_engine_type = OperatorConstants.Config.VLM_ENGINE_API_OLLAMA
    #    vlm_provider_config = {
    #        OperatorConstants.Config.VLM_API_BASE_URL: "http://localhost:11434/v1/chat/completions",  # Optional, defaults to this
    #        OperatorConstants.Config.VLM_MODEL_NAME: "ibm/granite-docling:258m"  # Optional, overrides preset default
    #    }
    #
    # 6. OpenAI API:
    #    use_vlm_pipeline = True
    #    vlm_engine_type = OperatorConstants.Config.VLM_ENGINE_API_OPENAI
    #    vlm_provider_config = {
    #        OperatorConstants.Config.VLM_API_KEY: "sk-...",  # Required  # pragma: allowlist secret
    #        OperatorConstants.Config.VLM_MODEL_NAME: "gpt-4-vision-preview",  # Required
    #        OperatorConstants.Config.VLM_API_BASE_URL: "https://api.openai.com/v1/chat/completions"  # Optional
    #    }
    #
    # 7. IBM watsonx.ai API:
    #    use_vlm_pipeline = True
    #    vlm_engine_type = OperatorConstants.Config.VLM_ENGINE_API_WATSONX
    #    vlm_provider_config = {
    #        OperatorConstants.Config.VLM_API_KEY: "your-ibm-cloud-api-key",  # Required  # pragma: allowlist secret
    #        OperatorConstants.Config.VLM_WATSONX_CONTAINER_KIND: "project",  # Optional, defaults to this
    #        OperatorConstants.Config.VLM_WATSONX_CONTAINER_ID: "your-project-id",  # Required
    #        OperatorConstants.Config.VLM_MODEL_NAME: "meta-llama/llama-3-2-11b-vision-instruct",  # Required
    #        OperatorConstants.Config.VLM_API_BASE_URL: "https://us-south.ml.cloud.ibm.com/ml/v1/text/chat?version=2023-05-29"  # Optional
    #    }

    sys.exit(main())
