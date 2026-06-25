#!/usr/bin/env python3
"""
Example: ExtractOperator - Document Extraction

Demonstrates the ExtractOperator with multiple extraction modes.

Text Extraction Providers:
1. Basic (docling_library) - Standard local Docling extraction
2. VLM (docling_library + VLM) - Vision-Language Model enhanced extraction
   - Transformers (local inference, GPU recommended)
   - MLX (macOS Apple Silicon optimized)
   - Ollama API (local or remote)
   - Watsonx AI (IBM Cloud)
   - OpenAI API
   - LM Studio (local API server)
   - Generic API (custom endpoints)
3. ASR (docling_library + ASR) - Audio/Video transcription with Automatic Speech Recognition
   - Whisper models (tiny, base, small, medium, large, turbo)
   - MLX variants for Apple Silicon optimization
4. Docling Serve - Remote extraction via Docling Serve API

Entity Extraction Providers:
1. LiteLLM - Multi-provider LLM entity extraction (OpenAI, Anthropic, Cohere, Ollama via openai/ prefix, etc.)
2. WatsonX - IBM WatsonX AI LLM-based entity extraction
3. Docling - Template-based entity extraction using Docling's structured extraction
4. None - No entity extraction (text extraction only)

Prerequisites:
    # Basic extraction
    pip install docling

    # VLM extraction (Transformers/MLX)
    pip install docling[vlm]

    # ASR extraction (Audio/Video transcription)
    pip install docling[asr]
    # For M4A, AAC, OGG, FLAC, and video formats, also install ffmpeg:
    brew install ffmpeg  # macOS
    # apt-get install ffmpeg  # Linux

    # VLM extraction (Ollama)
    brew install ollama
    ollama serve
    ollama pull ibm/granite-docling:258m

    # Entity extraction (LiteLLM with Ollama)
    ollama serve
    ollama pull llama3.2

    # Entity extraction (WatsonX)
    # Set environment variables: WATSONX_API_KEY, WATSONX_CONTAINER_ID

    # Docling Serve
    docker run -p 5001:5001 ds4sd/docling-serve:latest

Usage:
    python extract_operator_example.py [--text-mode MODE] [--entity-mode MODE] [--vlm-engine ENGINE] [--asr-model MODEL] [--pdf PATH] [--schema JSON]

Examples:
    # Basic text extraction only (default: text-mode=docling_library, entity-mode=none)
    python extract_operator_example.py

    # VLM text extraction with Transformers
    python extract_operator_example.py --text-mode vlm --vlm-engine transformers

    # VLM text extraction with Ollama
    python extract_operator_example.py --text-mode vlm --vlm-engine ollama

    # ASR audio/video transcription
    python extract_operator_example.py --text-mode asr --asr-model whisper_turbo

    # ASR with Apple Silicon optimization
    python extract_operator_example.py --text-mode asr --asr-model whisper_small_mlx

    # Docling Serve text extraction
    python extract_operator_example.py --text-mode serve

    # Basic text + LiteLLM entity extraction with Ollama (no schema - free-form extraction)
    python extract_operator_example.py --entity-mode litellm

    # Basic text + LiteLLM entity extraction with Ollama and custom schema
    python extract_operator_example.py --entity-mode litellm --schema '{"invoice_number": "string", "total_amount": "float"}'

    # Basic text + WatsonX entity extraction with custom schema
    python extract_operator_example.py --entity-mode watsonx --schema '{"invoice_number": "string", "total_amount": "float"}'

    # Basic text + Template-based entity extraction (schema required for docling mode)
    python extract_operator_example.py --entity-mode docling --schema '{"type": "object", "properties": {"invoice_number": {"type": "string"}}}'

    # VLM text + LiteLLM entity extraction (with schema)
    python extract_operator_example.py --text-mode vlm --entity-mode litellm --schema '{"vendor": "string", "amount": "float"}'

    # Docling Serve + LiteLLM entity extraction (no schema)
    python extract_operator_example.py --text-mode serve --entity-mode litellm

    # Process your own PDF file
    python extract_operator_example.py --pdf /path/to/your/document.pdf
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, cast

import pyarrow as pa
from dotenv import load_dotenv

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.extract.extract_operator import ExtractOperator

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


def get_basic_config() -> dict[str, Any]:
    """
    Get configuration for basic Docling extraction (no VLM).

    Best for: Standard document extraction, fastest processing
    Requirements: pip install docling
    """
    return {
        OperatorConstants.Config.TEXT_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY,
            OperatorConstants.Config.DOC_COLUMN: "doc_content",
        },
        OperatorConstants.Config.ENTITY_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.ENTITY_MODE_NONE,
        },
        OperatorConstants.Config.MAX_WORKERS: 4,
    }


def get_docling_serve_config(*, base_url: str = "http://localhost:5001") -> dict[str, Any]:
    """
    Get configuration for Docling Serve (remote API extraction).

    Best for: Scalable production workloads, containerized deployments
    Requirements: Docling Serve running (docker run -p 5001:5001 ds4sd/docling-serve:latest)
    """
    return {
        OperatorConstants.Config.TEXT_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_SERVE,
            OperatorConstants.Config.DOC_COLUMN: "doc_content",
            OperatorConstants.Config.PROVIDER_CONFIG: {
                OperatorConstants.Config.BASE_URL: base_url,
                OperatorConstants.Processing.TIMEOUT: 300,
                OperatorConstants.Config.DO_OCR: True,
            },
        },
        OperatorConstants.Config.ENTITY_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.ENTITY_MODE_NONE,
        },
    }


def get_asr_config(*, model_id: str = "whisper_turbo") -> dict[str, Any]:
    """
    Get configuration for ASR (Automatic Speech Recognition) audio/video transcription.

    Best for: Transcribing audio and video files to text
    Requirements: pip install docling[asr], ffmpeg (for some formats)

    Args:
        model_id: Whisper model variant
            - whisper_tiny: Fastest, least accurate
            - whisper_base: Balanced speed and accuracy
            - whisper_small: Good accuracy, moderate speed
            - whisper_medium: Better accuracy, slower
            - whisper_large: Best accuracy, slowest
            - whisper_turbo: Optimized for speed (recommended)
            - Variants with _mlx suffix (e.g., whisper_small_mlx): Apple Silicon optimized
            - Variants with _native suffix (e.g., whisper_tiny_native): Native implementation
    """
    return {
        OperatorConstants.Config.TEXT_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY,
            OperatorConstants.Config.DOC_COLUMN: "doc_content",
            OperatorConstants.Config.PROVIDER_CONFIG: {
                OperatorConstants.Config.ASR_PIPELINE: {
                    OperatorConstants.Config.MODEL_ID: model_id,
                }
            },
        },
        OperatorConstants.Config.ENTITY_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.ENTITY_MODE_NONE,
        },
        OperatorConstants.Config.MAX_WORKERS: 2,  # ASR is resource-intensive
    }


def get_vlm_config(
    *,
    engine: str,
    preset: str = "granite_docling",
    api_key: str | None = None,
    api_base_url: str | None = None,
    model: str | None = None,
    container_id: str | None = None,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get unified VLM configuration for any supported engine.

    Args:
        engine: VLM engine type (transformers, mlx, ollama, watsonx, openai, lmstudio, generic)
        preset: VLM preset (default: "granite_docling")
        api_key: API key for cloud providers (OpenAI, Watsonx)
        api_base_url: Custom API base URL
        model: Model name/ID
        container_id: Watsonx project/space ID (UUID)
        headers: Custom headers for generic API
        params: Custom parameters for generic API

    Engine-specific defaults and requirements:
        - transformers: Local inference, GPU recommended, no API config needed
        - mlx: macOS Apple Silicon optimized, no API config needed
        - ollama: api_base_url defaults to http://localhost:11434, model defaults to ibm/granite-docling:258m
        - watsonx: Requires api_key, container_id, model
        - openai: Requires api_key, model defaults to gpt-4-vision-preview
        - lmstudio: api_base_url defaults to http://localhost:1234/v1/chat/completions
        - generic: Requires api_base_url, optional api_key/headers/params
    """
    # Engine type mapping
    engine_type_map = {
        "transformers": OperatorConstants.Config.VLM_ENGINE_TRANSFORMERS,
        "mlx": OperatorConstants.Config.VLM_ENGINE_MLX,
        "ollama": OperatorConstants.Config.VLM_ENGINE_API_OLLAMA,
        "watsonx": OperatorConstants.Config.VLM_ENGINE_API_WATSONX,
        "openai": OperatorConstants.Config.VLM_ENGINE_API_OPENAI,
        "lmstudio": OperatorConstants.Config.VLM_ENGINE_API_LMSTUDIO,
        "generic": OperatorConstants.Config.VLM_ENGINE_API,
    }

    if engine not in engine_type_map:
        raise ValueError(f"Unknown VLM engine: {engine}. Supported: {list(engine_type_map.keys())}")

    # Base configuration with VLM nested under text_extraction.provider_config
    config: dict[str, Any] = {
        OperatorConstants.Config.TEXT_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY,
            OperatorConstants.Config.DOC_COLUMN: "doc_content",
            OperatorConstants.Config.PROVIDER_CONFIG: {
                OperatorConstants.Config.VLM_PIPELINE: {
                    OperatorConstants.Config.PRESET: preset,
                    OperatorConstants.Config.ENGINE: engine_type_map[engine],
                }
            },
        },
        OperatorConstants.Config.ENTITY_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.ENTITY_MODE_NONE,
        },
    }

    # Engine-specific configuration
    if engine in ["transformers", "mlx"]:
        # Local inference engines - no engine_options needed
        config[OperatorConstants.Config.MAX_WORKERS] = 2  # VLM is resource-intensive

    elif engine == "ollama":
        # Ollama API
        base_url = api_base_url or "http://localhost:11434"
        model_name = model or "ibm/granite-docling:258m"
        config[OperatorConstants.Config.TEXT_EXTRACTION][OperatorConstants.Config.PROVIDER_CONFIG][
            OperatorConstants.Config.VLM_PIPELINE
        ][OperatorConstants.Config.ENGINE_OPTIONS] = {
            OperatorConstants.Config.VLM_API_BASE_URL: f"{base_url}/v1/chat/completions",
            OperatorConstants.Config.VLM_MODEL_NAME: model_name,
        }
        config[OperatorConstants.Config.MAX_WORKERS] = 2

    elif engine == "watsonx":
        # IBM Watsonx AI
        if not all([api_key, container_id, model]):
            raise ValueError("Watsonx engine requires api_key, container_id, and model parameters")
        base_url = api_base_url or "https://us-south.ml.cloud.ibm.com/ml/v1/text/chat?version=2023-05-29"
        config[OperatorConstants.Config.TEXT_EXTRACTION][OperatorConstants.Config.PROVIDER_CONFIG][
            OperatorConstants.Config.VLM_PIPELINE
        ][OperatorConstants.Config.ENGINE_OPTIONS] = {
            OperatorConstants.Config.VLM_API_KEY: api_key,
            OperatorConstants.Config.VLM_WATSONX_CONTAINER_ID: container_id,
            OperatorConstants.Config.VLM_MODEL_NAME: model,
            OperatorConstants.Config.VLM_API_BASE_URL: base_url,
        }
        config[OperatorConstants.Config.MAX_WORKERS] = 4  # API-based can handle more

    elif engine == "openai":
        # OpenAI API
        if not api_key:
            raise ValueError("OpenAI engine requires api_key parameter")
        model_name = model or "gpt-4-vision-preview"
        base_url = api_base_url or "https://api.openai.com"
        config[OperatorConstants.Config.TEXT_EXTRACTION][OperatorConstants.Config.PROVIDER_CONFIG][
            OperatorConstants.Config.VLM_PIPELINE
        ][OperatorConstants.Config.ENGINE_OPTIONS] = {
            OperatorConstants.Config.VLM_API_KEY: api_key,
            OperatorConstants.Config.VLM_MODEL_NAME: model_name,
            OperatorConstants.Config.VLM_API_BASE_URL: base_url,
        }
        config[OperatorConstants.Config.MAX_WORKERS] = 4

    elif engine == "lmstudio":
        # LM Studio API
        base_url = api_base_url or "http://localhost:1234/v1/chat/completions"
        config[OperatorConstants.Config.TEXT_EXTRACTION][OperatorConstants.Config.PROVIDER_CONFIG][
            OperatorConstants.Config.VLM_PIPELINE
        ][OperatorConstants.Config.ENGINE_OPTIONS] = {
            OperatorConstants.Config.VLM_API_BASE_URL: base_url,
        }
        config[OperatorConstants.Config.MAX_WORKERS] = 2

    elif engine == "generic":
        # Generic API
        if not api_base_url:
            raise ValueError("Generic API engine requires api_base_url parameter")
        engine_options: dict[str, Any] = {
            OperatorConstants.Config.VLM_API_BASE_URL: api_base_url,
        }
        if api_key:
            engine_options[OperatorConstants.Config.VLM_API_KEY] = api_key
        if headers:
            engine_options["headers"] = headers
        if params:
            engine_options[OperatorConstants.Config.PARAMETERS] = params
        config[OperatorConstants.Config.TEXT_EXTRACTION][OperatorConstants.Config.PROVIDER_CONFIG][
            OperatorConstants.Config.VLM_PIPELINE
        ][OperatorConstants.Config.ENGINE_OPTIONS] = engine_options
        config[OperatorConstants.Config.MAX_WORKERS] = 4

    return config


def get_litellm_ollama_entity_config(
    *,
    text_mode: str = OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY,
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    max_doc_chars: int = 8000,
    custom_schema: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Get configuration for LiteLLM entity extraction using Ollama backend.

    Best for: Flexible entity extraction, complex document understanding with local models
    Requirements: Ollama server running, model pulled

    Setup:
        ollama serve
        ollama pull llama3.2

    Args:
        text_mode: Text extraction provider to use
        model: Model identifier with openai/ prefix for Ollama (e.g., "openai/llama3.2"). Required.
        temperature: Sampling temperature (0.0 = deterministic)
        max_tokens: Maximum response tokens
        max_doc_chars: Maximum document characters to send to LLM
        custom_schema: Optional schema dictionary for structured extraction
    """
    config = {
        OperatorConstants.Config.TEXT_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: text_mode,
            OperatorConstants.Config.DOC_COLUMN: "doc_content",
        },
        OperatorConstants.Config.ENTITY_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM,
            OperatorConstants.Config.PROVIDER_CONFIG: {
                OperatorConstants.Config.MODEL_ID: model,
                OperatorConstants.LLM.TEMPERATURE: temperature,
                OperatorConstants.LLM.MAX_TOKENS: max_tokens,
                OperatorConstants.LLM.API_BASE: "http://localhost:11434/v1",
            },
            OperatorConstants.LLM.MAX_DOC_CHARS: max_doc_chars,
        },
        OperatorConstants.Config.MAX_WORKERS: 2,  # Reduce for LLM processing
    }

    if custom_schema:
        entity_config = cast(dict[str, Any], config[OperatorConstants.Config.ENTITY_EXTRACTION])
        entity_config[OperatorConstants.Config.CUSTOM_SCHEMA] = custom_schema

    return config


def get_watsonx_entity_config(
    *,
    text_mode: str = OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY,
    model: str,
    api_key: str | None = None,
    api_base: str | None = None,
    container_id: str | None = None,
    container_kind: str = "project",
    temperature: float = 0.0,
    max_tokens: int = 2000,
    custom_schema: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Get configuration for WatsonX entity extraction.

    Best for: Enterprise-grade entity extraction with IBM WatsonX AI
    Requirements: IBM Cloud API key, WatsonX project/space ID

    Setup:
        Set environment variables:
        - WATSONX_API_KEY: IBM Cloud API key
        - WATSONX_CONTAINER_ID: Project or space ID
        - WATSONX_API_BASE: API endpoint (optional, has default)

    Args:
        text_mode: Text extraction provider to use
        model: WatsonX model identifier (e.g., "ibm/granite-13b-chat-v2")
        api_key: IBM Cloud API key
        api_base: WatsonX API endpoint URL
        container_id: Project or space ID (UUID)
        container_kind: Container type ("project" or "space")
        temperature: Sampling temperature (0.0 = deterministic)
        max_tokens: Maximum response tokens
        custom_schema: Optional schema dictionary for structured extraction
    """
    if not all([api_key, container_id]):
        raise ValueError("WatsonX entity extraction requires api_key and container_id")

    provider_config = {
        OperatorConstants.Config.MODEL_ID: model,
        OperatorConstants.Config.API_KEY: api_key,
        OperatorConstants.LLM.TEMPERATURE: temperature,
        OperatorConstants.LLM.MAX_TOKENS: max_tokens,
        OperatorConstants.Config.CONTAINER_ID: container_id,
        OperatorConstants.Config.CONTAINER_KIND: container_kind,
    }

    if api_base:
        provider_config[OperatorConstants.LLM.API_BASE] = api_base

    config = {
        OperatorConstants.Config.TEXT_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: text_mode,
            OperatorConstants.Config.DOC_COLUMN: "doc_content",
        },
        OperatorConstants.Config.ENTITY_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.ENTITY_MODE_WATSONX,
            OperatorConstants.Config.PROVIDER_CONFIG: provider_config,
        },
        OperatorConstants.Config.MAX_WORKERS: 4,  # API-based can handle more
    }

    if custom_schema:
        entity_config = cast(dict[str, Any], config[OperatorConstants.Config.ENTITY_EXTRACTION])
        entity_config[OperatorConstants.Config.CUSTOM_SCHEMA] = custom_schema

    return config


def get_docling_entity_config(
    *,
    text_mode: str = OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY,
    custom_schema: dict[str, Any] | None = None,
    expand_data: bool = False,
) -> dict[str, Any]:
    """
    Get configuration for Docling template-based entity extraction.

    Best for: Standardized forms, known schemas, fast deterministic extraction
    Requirements: None (uses Docling's built-in extraction)

    Args:
        text_mode: Text extraction provider to use
        custom_schema: JSON schema for structured extraction
        expand_data: Expand entity data into individual columns
    """
    config = {
        OperatorConstants.Config.TEXT_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: text_mode,
            OperatorConstants.Config.DOC_COLUMN: "doc_content",
        },
        OperatorConstants.Config.ENTITY_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.ENTITY_MODE_DOCLING,
            OperatorConstants.Config.EXPAND_EXTRACTED_DATA: expand_data,
        },
        OperatorConstants.Config.MAX_WORKERS: 2,
    }

    if custom_schema:
        entity_config = cast(dict[str, Any], config[OperatorConstants.Config.ENTITY_EXTRACTION])
        entity_config[OperatorConstants.Config.CUSTOM_SCHEMA] = custom_schema

    return config


def get_litellm_entity_config(
    *,
    text_mode: str = OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY,
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 2000,
    api_key: str | None = None,
    api_base: str | None = None,
    custom_schema: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Get configuration for LiteLLM entity extraction.

    Best for: Multi-provider LLM support, cloud-based processing
    Requirements: API key for chosen provider

    Supported providers: OpenAI, Anthropic, Cohere, Google, Azure, AWS Bedrock, etc.

    Args:
        text_mode: Text extraction mode to use
        model: LLM model identifier (e.g., "gpt-3.5-turbo", "claude-3-sonnet"). Required.
        temperature: Sampling temperature
        max_tokens: Maximum response tokens
        api_key: API key for the provider
        api_base: Optional custom API base URL
        custom_schema: Optional schema dictionary for structured extraction
    """
    provider_config = {}
    if api_key:
        provider_config[OperatorConstants.Config.API_KEY] = api_key
    if api_base:
        provider_config[OperatorConstants.LLM.API_BASE] = api_base

    provider_config.update(
        {
            OperatorConstants.Config.MODEL_ID: model,
            OperatorConstants.LLM.TEMPERATURE: temperature,
            OperatorConstants.LLM.MAX_TOKENS: max_tokens,
        }
    )

    config = {
        OperatorConstants.Config.TEXT_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: text_mode,
            OperatorConstants.Config.DOC_COLUMN: "doc_content",
        },
        OperatorConstants.Config.ENTITY_EXTRACTION: {
            OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM,
            OperatorConstants.Config.PROVIDER_CONFIG: provider_config,
        },
        OperatorConstants.Config.MAX_WORKERS: 4,
    }

    if custom_schema:
        entity_config = cast(dict[str, Any], config[OperatorConstants.Config.ENTITY_EXTRACTION])
        entity_config[OperatorConstants.Config.CUSTOM_SCHEMA] = custom_schema

    return config


def main() -> int:
    """Main function demonstrating ExtractOperator with multiple modes."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Demo: ExtractOperator with independent text and entity extraction modes"
    )
    parser.add_argument(
        "--text-mode",
        type=str,
        default="basic",
        choices=["basic", "vlm", "asr", "serve"],
        help="Text extraction provider: basic (docling_library), vlm (docling_library+VLM), asr (docling_library+ASR), serve (docling_serve)",
    )
    parser.add_argument(
        "--entity-mode",
        type=str,
        default="none",
        choices=["none", "litellm", "watsonx", "docling"],
        help="Entity extraction provider: none, litellm (includes Ollama via openai/ prefix), watsonx, docling (default: none)",
    )
    parser.add_argument(
        "--vlm-engine",
        type=str,
        default="transformers",
        choices=[
            "transformers",
            "mlx",
            "ollama",
            "watsonx",
            "openai",
            "lmstudio",
            "generic",
        ],
        help="VLM engine when text-mode=vlm (default: transformers)",
    )
    parser.add_argument(
        "--asr-model",
        type=str,
        default="whisper_turbo",
        choices=[
            "whisper_tiny",
            "whisper_base",
            "whisper_small",
            "whisper_medium",
            "whisper_large",
            "whisper_turbo",
            "whisper_tiny_mlx",
            "whisper_small_mlx",
            "whisper_medium_mlx",
        ],
        help="ASR model when text-mode=asr (default: whisper_turbo)",
    )
    parser.add_argument(
        "--pdf",
        type=str,
        default="tests/fixtures/invoices/TR-INV_044_1_1.1.pdf",
        help="Path to PDF file (default: tests/fixtures/invoices/TR-INV_044_1_1.1.pdf)",
    )
    parser.add_argument(
        "--preset",
        type=str,
        default="granite_docling",
        choices=["granite_docling", "qwen2_vl"],
        help="VLM preset when text-mode=vlm (default: granite_docling)",
    )
    parser.add_argument(
        "--schema",
        type=str,
        default=None,
        help='JSON schema string for entity extraction (e.g., \'{"invoice_number": "string", "total_amount": "float"}\')',
    )
    args = parser.parse_args()

    print("=" * 80)
    print("EXTRACT OPERATOR")
    print("=" * 80)
    print(f"PDF: {args.pdf}")
    print(f"Text Extraction Provider: {args.text_mode}")
    if args.text_mode == "vlm":
        print(f"  VLM Engine: {args.vlm_engine}")
        print(f"  VLM Preset: {args.preset}")
    elif args.text_mode == "asr":
        print(f"  ASR Model: {args.asr_model}")
    print(f"Entity Extraction Provider: {args.entity_mode}")
    if args.entity_mode != "none" and args.schema:
        print(f"  Custom Schema: {args.schema}")
    print("=" * 80)

    # Build configuration based on text and entity modes
    config: dict[str, Any] = {}

    # Configure text extraction
    if args.text_mode == "asr":
        config = get_asr_config(model_id=args.asr_model)
        print("\nText Extraction: ASR (Automatic Speech Recognition)")
        print(f"Model: {args.asr_model}")
        print("Note: Processes audio and video files to extract transcribed text")
        if "_mlx" in args.asr_model:
            print("      Using Apple Silicon optimized model")
    elif args.text_mode == "serve":
        config = get_docling_serve_config()
        print("\nText Extraction: Docling Serve (remote API)")
        print("Note: Ensure Docling Serve is running on http://localhost:5001")
        print("      docker run -p 5001:5001 ds4sd/docling-serve:latest")
    elif args.text_mode == "vlm":
        # VLM mode - select engine
        try:
            if args.vlm_engine == "watsonx":
                # Load from environment variables
                api_key = os.getenv("WATSONX_API_KEY")
                container_id = os.getenv("WATSONX_CONTAINER_ID")
                container_kind = os.getenv("WATSONX_CONTAINER_KIND", "project")
                model = os.getenv("WATSONX_MODEL")
                api_base_url = os.getenv("WATSONX_API_BASE_URL")

                if not all([api_key, container_id, model]):
                    print("\n❌ Watsonx engine requires credentials in .env file:")
                    print("   WATSONX_API_KEY=your_ibm_cloud_api_key")
                    print("   WATSONX_CONTAINER_ID=your_project_or_space_id")
                    print("   WATSONX_MODEL=meta-llama/llama-3-2-90b-vision-instruct")
                    print(
                        "   WATSONX_CONTAINER_KIND=project  # optional: project, space, or catalog (default: project)"
                    )
                    print("   WATSONX_API_BASE_URL=https://...  # optional, has default")
                    print("\nSee .env.example for template")
                    return 1

                config = get_vlm_config(
                    engine="watsonx",
                    preset=args.preset,
                    api_key=api_key,
                    container_id=container_id,
                    model=model,
                    api_base_url=api_base_url,
                )
                # Add container_kind to config
                config[OperatorConstants.Config.VLM_PROVIDER_CONFIG][
                    OperatorConstants.Config.VLM_WATSONX_CONTAINER_KIND
                ] = container_kind

                print("\nText Extraction: VLM with Watsonx AI engine")
                print(f"Model: {model}")
                print(f"Container: {container_kind} ({container_id[:8]}...)")  # type: ignore[index]

            elif args.vlm_engine == "openai":
                # Load from environment variables
                api_key = os.getenv("OPENAI_API_KEY")
                model = os.getenv("OPENAI_MODEL", "gpt-4-vision-preview")
                api_base_url = os.getenv("OPENAI_API_BASE_URL")

                if not api_key:
                    print("\n❌ OpenAI engine requires API key in .env file:")
                    print("   OPENAI_API_KEY=your_openai_api_key")
                    print("   OPENAI_MODEL=gpt-4-vision-preview  # optional, has default")
                    print("   OPENAI_API_BASE_URL=https://...  # optional, has default")
                    print("\nSee .env.example for template")
                    return 1

                config = get_vlm_config(
                    engine="openai",
                    preset=args.preset,
                    api_key=api_key,
                    model=model,
                    api_base_url=api_base_url,
                )
                print("\nText Extraction: VLM with OpenAI API engine")
                print(f"Model: {model}")

            elif args.vlm_engine == "generic":
                # Load from environment variables
                api_base_url = os.getenv("GENERIC_API_BASE_URL")
                api_key = os.getenv("GENERIC_API_KEY")

                if not api_base_url:
                    print("\n❌ Generic API engine requires base URL in .env file:")
                    print("   GENERIC_API_BASE_URL=https://your-api.com/v1/chat")
                    print("   GENERIC_API_KEY=your_api_key  # optional")
                    print("\nSee .env.example for template")
                    return 1

                config = get_vlm_config(
                    engine="generic",
                    preset=args.preset,
                    api_base_url=api_base_url,
                    api_key=api_key,
                )
                print("\nText Extraction: VLM with Generic API engine")
                print(f"API URL: {api_base_url}")

            else:
                # Local engines (transformers, mlx, ollama, lmstudio)
                config = get_vlm_config(engine=args.vlm_engine, preset=args.preset)

                # Print engine-specific info
                if args.vlm_engine == "transformers":
                    print("\nText Extraction: VLM with Transformers engine (local inference)")
                    print("Note: First run will download the VLM model")
                elif args.vlm_engine == "mlx":
                    print("\nText Extraction: VLM with MLX engine (macOS Apple Silicon optimized)")
                    print("Note: Requires macOS with Apple Silicon (M1/M2/M3)")
                elif args.vlm_engine == "ollama":
                    print("\nText Extraction: VLM with Ollama API engine")
                    print("Note: Ensure Ollama is running: ollama serve")
                    print("      And vision model is available: ollama pull ibm/granite-docling:258m")
                elif args.vlm_engine == "lmstudio":
                    print("\nText Extraction: VLM with LM Studio API engine")
                    print("Note: Ensure LM Studio is running with a vision model loaded")

        except ValueError as e:
            logger.error(f"VLM configuration error: {e}")
            return 1
    else:
        config = get_basic_config()
        print("\nText Extraction: Basic Docling extraction (no VLM)")
        print("Fast processing with standard table and image extraction")

    # Configure entity extraction
    if args.entity_mode == "litellm":
        custom_schema = None
        if args.schema:
            import json

            try:
                custom_schema = json.loads(args.schema)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON schema: {e}")
                return 1

        # Update config with entity extraction (using litellm with Ollama backend)
        config[OperatorConstants.Config.ENTITY_EXTRACTION][OperatorConstants.Config.PROVIDER] = (
            OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM
        )
        config[OperatorConstants.Config.ENTITY_EXTRACTION][OperatorConstants.Config.PROVIDER_CONFIG] = {
            OperatorConstants.Config.MODEL_ID: "openai/llama3.2",
            OperatorConstants.LLM.TEMPERATURE: 0.0,
            OperatorConstants.LLM.MAX_TOKENS: 4096,
            OperatorConstants.LLM.API_BASE: "http://localhost:11434/v1",
        }
        config[OperatorConstants.Config.ENTITY_EXTRACTION][OperatorConstants.LLM.MAX_DOC_CHARS] = 8000
        config[OperatorConstants.Config.MAX_WORKERS] = 2  # Reduce for LLM

        if custom_schema:
            config[OperatorConstants.Config.ENTITY_EXTRACTION][OperatorConstants.Config.CUSTOM_SCHEMA] = custom_schema

        print("\nEntity Extraction: LiteLLM with Ollama backend")
        print("Note: Ensure Ollama is running: ollama serve")
        print("      And model is available: ollama pull llama3.2")
        if custom_schema:
            print(f"      Using custom schema: {list(custom_schema.keys())}")

    elif args.entity_mode == "watsonx":
        custom_schema = None
        if args.schema:
            import json

            try:
                custom_schema = json.loads(args.schema)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON schema: {e}")
                return 1

        # Load from environment variables
        api_key = os.getenv("WATSONX_API_KEY")
        container_id = os.getenv("WATSONX_CONTAINER_ID")
        container_kind = os.getenv("WATSONX_CONTAINER_KIND", "project")
        model = os.getenv("WATSONX_ENTITY_MODEL", "ibm/granite-13b-chat-v2")
        api_base = os.getenv("WATSONX_API_BASE")

        if not all([api_key, container_id]):
            print("\n❌ WatsonX entity extraction requires credentials in .env file:")
            print("   WATSONX_API_KEY=your_ibm_cloud_api_key")
            print("   WATSONX_CONTAINER_ID=your_project_or_space_id")
            print("   WATSONX_ENTITY_MODEL=ibm/granite-13b-chat-v2  # optional, has default")
            print("   WATSONX_CONTAINER_KIND=project  # optional: project or space (default: project)")
            print("   WATSONX_API_BASE=https://...  # optional, has default")
            print("\nSee .env.example for template")
            return 1

        # Update config with WatsonX entity extraction
        provider_config = {
            OperatorConstants.Config.MODEL_ID: model,
            OperatorConstants.Config.API_KEY: api_key,
            OperatorConstants.LLM.TEMPERATURE: 0.0,
            OperatorConstants.LLM.MAX_TOKENS: 2000,
            OperatorConstants.Config.CONTAINER_ID: container_id,
            OperatorConstants.Config.CONTAINER_KIND: container_kind,
        }
        if api_base:
            provider_config[OperatorConstants.LLM.API_BASE] = api_base

        config[OperatorConstants.Config.ENTITY_EXTRACTION][OperatorConstants.Config.PROVIDER] = (
            OperatorConstants.ExtractionModes.ENTITY_MODE_WATSONX
        )
        config[OperatorConstants.Config.ENTITY_EXTRACTION][OperatorConstants.Config.PROVIDER_CONFIG] = provider_config
        config[OperatorConstants.Config.MAX_WORKERS] = 4  # API-based can handle more

        if custom_schema:
            config[OperatorConstants.Config.ENTITY_EXTRACTION][OperatorConstants.Config.CUSTOM_SCHEMA] = custom_schema

        print("\nEntity Extraction: IBM WatsonX AI")
        print(f"Model: {model}")
        print(f"Container: {container_kind} ({container_id[:8]}...)")  # type: ignore[index]
        if custom_schema:
            print(f"Using custom schema: {list(custom_schema.keys())}")

    elif args.entity_mode == "docling":
        # Docling provider requires a schema
        if not args.schema:
            logger.error("Docling entity extraction provider requires --schema parameter")
            print("\nExample:")
            print('  --schema \'{"type": "object", "properties": {"invoice_number": {"type": "string"}}}\'')
            return 1

        import json

        try:
            custom_schema = json.loads(args.schema)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON schema: {e}")
            return 1

        # If user provided simple schema, wrap it in JSON Schema format for Docling
        if "type" not in custom_schema:
            custom_schema = {
                "type": "object",
                "properties": {
                    key: {"type": value} if isinstance(value, str) else value for key, value in custom_schema.items()
                },
            }

            # Original hardcoded example for reference:
            # custom_schema = {
            #     "type": "object",
            #     "properties": {
            #         "invoice_number": {"type": "string"},
            #         "invoice_date": {"type": "string"},
            #         "total_amount": {"type": "number"},
            #         "line_items": {
            #             "type": "array",
            #             "items": {
            #                 "type": "object",
            #                 "properties": {
            #                     "description": {"type": "string"},
            #                     "quantity": {"type": "number"},
            #                     "unit_price": {"type": "number"}
            #                 }
            #             }
            #         }
            #     }
            # }

        # Update config with entity extraction
        config[OperatorConstants.Config.ENTITY_EXTRACTION][OperatorConstants.Config.PROVIDER] = (
            OperatorConstants.ExtractionModes.ENTITY_MODE_DOCLING
        )
        config[OperatorConstants.Config.ENTITY_EXTRACTION][OperatorConstants.Config.EXPAND_EXTRACTED_DATA] = False
        config[OperatorConstants.Config.ENTITY_EXTRACTION][OperatorConstants.Config.CUSTOM_SCHEMA] = custom_schema

        print("\nEntity Extraction: Docling template-based extraction")
        print("Fast, deterministic extraction for standardized documents")
        if custom_schema:
            print(f"      Using JSON schema with properties: {list(custom_schema.get('properties', {}).keys())}")

    elif args.entity_mode == "none":
        # Entity extraction already set to "none" in base configs
        print("\nEntity Extraction: None (text extraction only)")
    else:
        logger.error(f"Unknown entity provider: {args.entity_mode}")
        return 1

    # Initialize operator
    operator = ExtractOperator(config=config)

    # Read input file
    input_path = Path(args.pdf)
    if not input_path.exists():
        logger.error(f"File not found: {input_path}")
        return 1

    logger.info(f"Processing file: {input_path}")

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
    text_label = {
        "basic": "basic Docling",
        "vlm": f"VLM ({args.vlm_engine})",
        "asr": f"ASR ({args.asr_model})",
        "serve": "Docling Serve",
    }.get(args.text_mode, "unknown")

    entity_label = {
        "none": "no entity extraction",
        "litellm": "LiteLLM entity extraction (Ollama)",
        "watsonx": "WatsonX entity extraction",
        "docling": "Docling template entity extraction",
    }.get(args.entity_mode, "unknown")

    print(f"\nExtracting content with {text_label} + {entity_label}...")
    result_tables, metadata = operator.transform(table=table)
    result_table = result_tables[0]

    # Display results
    print("\n" + "=" * 80)
    print("EXTRACTION RESULTS")
    print("=" * 80)
    print(f"Metadata: {metadata}")
    print(f"Result columns: {result_table.column_names}")

    if "doc_content" in result_table.column_names:
        content = result_table["doc_content"][0].as_py()
        print(f"\nContent length: {len(content) if content else 0} characters")
        if content:
            print("\nContent preview (first 500 chars):")
            print("-" * 80)
            print(content[:500] + "..." if len(content) > 500 else content)
            print("-" * 80)

    # Display entity extraction results if available
    if "entities" in result_table.column_names:
        entities = result_table["entities"][0].as_py()
        print("\nExtracted Entities:")
        print("-" * 80)
        print(entities)
        print("-" * 80)

    if OperatorConstants.Columns.EXTRACTED_DATA in result_table.column_names:
        extracted_data = result_table[OperatorConstants.Columns.EXTRACTED_DATA][0].as_py()
        print("\nExtracted Data (Template-based):")
        print("-" * 80)
        print(extracted_data)
        print("-" * 80)

    print("\n" + "=" * 80)
    print("Extraction completed successfully!")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    sys.exit(main())
