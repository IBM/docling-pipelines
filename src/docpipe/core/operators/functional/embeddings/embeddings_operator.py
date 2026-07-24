"""
Embeddings Operator

This operator generates vector embeddings for text content using LLM providers.
Supports watsonx and litellm (which provides access to 100+ providers including Ollama, HuggingFace, OpenAI, etc.).
"""

import json
import os
import uuid
from typing import Any

import numpy as np
import pyarrow as pa

from docpipe.core.adapters.llm_adapter_factory import LLMAdapterFactory
from docpipe.core.constants.constants import (
    AttributeDataTypes,
    DocpipeConstants,
    ExecutionStatus,
    Metrics,
)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.core.operators.functional.doc_id_hash import DocIdHashOperator
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.core.ports.llm_embedding_port import LLMEmbeddingPort
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.utils.core.memmap_file_utils import write_content_to_file
from docpipe.utils.data.transform import TransformUtils
from docpipe.utils.infrastructure.filesystem import get_data_path
from docpipe.utils.infrastructure.logging import get_logger
from docpipe.utils.operators.config_validation import validate_config_from_metadata

logger = get_logger()

# Overlap ratio for chunking
OVERLAP_RATIO_KEY: str = "overlap_ratio"
OVERLAP_RATIO_DEFAULT: float = 0.2
OVERLAP_RATIO_MIN: float = 0.0
OVERLAP_RATIO_MAX: float = 0.5

# Token limit for chunking
TOKEN_LIMIT_KEY: str = "token_limit"
TOKEN_LIMIT_DEFAULT: int = 8192

# Provider configuration key
PROVIDER_KEY: str = "provider"
PROVIDER_DEFAULT: str = "litellm"


class EmbeddingsOperator(AbstractOperator):
    """
    Operator for generating embeddings using LLM providers.

    This operator processes documents and generates vector embeddings using
    watsonx or litellm providers. It supports:
    - Multiple embedding providers (watsonx, litellm)
    - Automatic chunking for long text
    - Pre-chunked content processing
    - Document hash generation
    - Error handling per document
    - Batch processing for improved performance

    Supported Providers:
    - watsonx: IBM watsonx.ai embedding models
    - litellm: 100+ providers via LiteLLM including:
      * Ollama (via OpenAI-compatible API with model prefix 'openai/')
      * HuggingFace (via API with model prefix 'huggingface/')
      * OpenAI, Anthropic, Cohere, AWS Bedrock, Google Vertex AI, and 90+ more

    LiteLLM Provider Examples:
    - OpenAI: text-embedding-3-small, text-embedding-ada-002
    - Ollama: openai/nomic-embed-text, openai/llama2
    - HuggingFace: huggingface/sentence-transformers/all-MiniLM-L6-v2
    - Azure OpenAI, Cohere, Bedrock, Vertex AI, etc.

    Attributes:
        provider (str): Embedding provider (watsonx or litellm)
        provider_config (dict): Provider-specific configuration
            - model_id (str): Model identifier in <provider>/<model_id> format for litellm
            - api_base (str): API endpoint URL (optional)
            - api_key (str): Authentication key (optional)
        embeddings_column (str): Output column name for embeddings
        overlap_ratio (float): Overlap ratio for chunking long text (0.0-0.5)
        token_limit (int): Maximum token limit for text chunking
        doc_column (str): Input column containing document content
        doc_id_hash_column (str): Column for document hash
    """

    short_name: str = OperatorConstants.Operators.EMBEDDINGS
    category: OperatorCategory = OperatorCategory.Functional
    owner = DocpipeConstants.OWNER_DOCPIPE

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the Embeddings Operator.

        Args:
            config: Configuration dictionary containing:
                - provider: Provider type ("watsonx" or "litellm", default: "litellm")
                - provider_config: Provider-specific configuration dictionary containing:
                    - model_id: Model identifier in <provider>/<model_id> format for litellm (e.g., "openai/nomic-embed-text")
                - embeddings_column: Output column name for embeddings (default: "embeddings")
                - overlap_ratio: Overlap ratio for chunking long text (default: 0.2)
                - token_limit: Maximum token limit for chunking (default: 8192)
                - doc_column: Input column containing document content (default: "content")
                - doc_id_hash_column: Column for document hash (default: "doc_id_hash")
        """
        super().__init__(config)

        # Provider configuration
        self.provider: str = config.get(PROVIDER_KEY, PROVIDER_DEFAULT).lower()

        # Provider-specific configuration
        self.provider_config: dict[str, Any] = config.get(OperatorConstants.Config.PROVIDER_CONFIG, {})

        # Model configuration - now from provider_config
        self.model_id: str = self.provider_config.get(OperatorConstants.Config.MODEL_ID, "openai/nomic-embed-text")

        # Column names
        self.embeddings_column: str = config.get(
            OperatorConstants.Columns.EMBEDDINGS_COLUMN,
            OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT,
        )
        self.doc_column: str = config.get(
            OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT
        )
        self.doc_id_hash_column: str = config.get(
            OperatorConstants.Columns.DOC_ID_HASH, OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
        )

        # Chunking configuration
        self.overlap_ratio: float = config.get(OVERLAP_RATIO_KEY, OVERLAP_RATIO_DEFAULT)
        self.token_limit: int = config.get(TOKEN_LIMIT_KEY, TOKEN_LIMIT_DEFAULT)

        # Logging
        self.common_log_arguments: dict[str, Any] = {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
        }

        # Initialize embedding adapter using unified factory
        self.embedding_adapter: LLMEmbeddingPort = self._initialize_embedding_adapter()

        logger.info(
            f"Initialized EmbeddingsOperator with provider: {self.provider}, model: {self.model_id}",
            extra=self.common_log_arguments,
        )

    def _initialize_embedding_adapter(self) -> LLMEmbeddingPort:
        """
        Initialize the appropriate embedding adapter based on provider.

        Uses the unified LLMAdapterFactory to create adapters for watsonx or litellm providers.

        Returns:
            The initialized embedding adapter implementing LLMEmbeddingPort

        Raises:
            DocpipeException: If the provider is unsupported or initialization fails
        """
        try:
            # Create adapter using unified factory
            adapter = LLMAdapterFactory.create_embedding_adapter(
                provider=self.provider,
                model_id=self.model_id,
                provider_config=self.provider_config,
            )

            # Validate adapter configuration
            self._validate_adapter(adapter)

            return adapter
        except Exception as e:
            raise DocpipeException(f"Failed to initialize embedding adapter '{self.provider}': {e!s}") from e

    def _validate_adapter(self, adapter: LLMEmbeddingPort) -> None:
        """Validate embedding adapter configuration on initialization.

        Args:
            adapter: The embedding adapter to validate

        Raises:
            DocpipeException: If adapter validation fails
        """
        result = adapter.validate()

        # Log warnings
        if result.get("warnings"):
            for warning in result["warnings"]:
                logger.warning(f"Embedding adapter validation warning: {warning}")

        # Raise error if validation failed
        if not result.get("valid", True):
            errors = result.get("errors", ["Unknown validation error"])
            raise DocpipeException(
                message=f"Embedding adapter validation failed: {'; '.join(errors)}",
                status_code=400,
            )

    @staticmethod
    def get_required_features() -> list[str]:
        """Return list of required input features."""
        return []

    def validate(
        self, errors: list[str], warnings: list[str], available_features: list[str]
    ) -> None:  # NOSONAR python:S3776
        """
        Validate operator configuration.

        Args:
            errors: List to append validation errors
            warnings: List to append validation warnings
            available_features: List of available input features
        """
        super().validate(errors, warnings, available_features)

        # Check for content OR chunked_content column
        has_content = OperatorConstants.Columns.DOC_COLUMN_DEFAULT in available_features
        has_chunked_content = OperatorConstants.Columns.CHUNKED_CONTENT in available_features

        if not has_content and not has_chunked_content:
            errors.append(
                f"Embeddings operator requires either '{OperatorConstants.Columns.DOC_COLUMN_DEFAULT}' "
                f"or '{OperatorConstants.Columns.CHUNKED_CONTENT}' column to be available"
            )

        # Get metadata and extract ATTRIBUTES for validation
        metadata = self.get_metadata()
        attributes = metadata.get(OperatorConstants.Config.ATTRIBUTES, {})

        # Validate configuration against metadata
        validate_config_from_metadata(config=self.config, attributes=attributes, errors=errors)

        # Validate provider
        if self.should_validate_field(field_value=self.provider):
            if not isinstance(self.provider, str):
                errors.append(f"provider must be a string, got {type(self.provider)}")
            else:
                supported_providers = LLMAdapterFactory.get_supported_providers(capability="embedding")
                if self.provider not in supported_providers:
                    errors.append(f"provider must be one of {sorted(supported_providers)}, got '{self.provider}'")

        # Validate overlap ratio
        if self.should_validate_field(field_value=self.overlap_ratio):
            if not isinstance(self.overlap_ratio, (int, float)):
                errors.append(f"overlap_ratio must be a number, got {type(self.overlap_ratio)}")
            elif not (OVERLAP_RATIO_MIN <= self.overlap_ratio <= OVERLAP_RATIO_MAX):
                errors.append(f"overlap_ratio must be between {OVERLAP_RATIO_MIN} and {OVERLAP_RATIO_MAX}")

        # Validate token limit
        if self.should_validate_field(field_value=self.token_limit):
            if not isinstance(self.token_limit, int):
                errors.append(f"token_limit must be an integer, got {type(self.token_limit)}")
            elif self.token_limit <= 0:
                errors.append(f"token_limit must be positive, got {self.token_limit}")

        # Validate provider_config and model_id
        if self.should_validate_field(field_value=self.provider_config):
            if not isinstance(self.provider_config, dict):
                errors.append(f"provider_config must be a dictionary, got {type(self.provider_config)}")
            else:
                # Validate model_id within provider_config
                model_id = self.provider_config.get(OperatorConstants.Config.MODEL_ID)
                if not model_id or not isinstance(model_id, str):
                    errors.append("provider_config.model_id is required and must be a non-empty string")

                # Validate max_concurrent_requests if present
                max_concurrent_requests = self.provider_config.get(OperatorConstants.Config.MAX_CONCURRENT_REQUESTS)
                if max_concurrent_requests is not None and self.should_validate_field(
                    field_value=max_concurrent_requests
                ):
                    if not isinstance(max_concurrent_requests, int):
                        errors.append(
                            f"provider_config.max_concurrent_requests must be an integer, got {type(max_concurrent_requests).__name__}"
                        )
                    elif max_concurrent_requests <= 0:
                        errors.append(
                            f"provider_config.max_concurrent_requests must be positive, got {max_concurrent_requests}"
                        )

                # Validate batch_size if present
                batch_size = self.provider_config.get(OperatorConstants.Config.BATCH_SIZE)
                if batch_size is not None and self.should_validate_field(field_value=batch_size):
                    if not isinstance(batch_size, int):
                        errors.append(f"provider_config.batch_size must be an integer, got {type(batch_size).__name__}")
                    elif batch_size <= 0:
                        errors.append(f"provider_config.batch_size must be positive, got {batch_size}")

        # Check if chunked_content feature is available (always validate, even during flow validation)
        chunked_content_exists = OperatorConstants.Columns.CHUNKED_CONTENT in available_features
        if not chunked_content_exists:
            from docpipe.exceptions.error_messages import ValidationCodeMessages

            warnings.append(ValidationCodeMessages.CHUNKER_OPERATOR_MISSING)

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """
        Return operator metadata for UI and documentation.

        Returns:
            dict: Operator metadata including features and attributes
        """
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: OperatorCategory.Functional.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: EmbeddingsOperator.is_available(),
            OperatorConstants.Misc.LABEL: "Embeddings",
            OperatorConstants.Config.DESCRIPTION: "Generate vector embeddings using watsonx or litellm (100+ providers including Ollama, HuggingFace, OpenAI, Azure, Cohere, etc.)",
            OperatorConstants.Config.FEATURES: {
                OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT: {
                    OperatorConstants.Misc.NAME: "Embeddings",
                    OperatorConstants.Config.DESCRIPTION: "Vector embeddings generated from document content",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_VECTOR,
                },
            },
            OperatorConstants.Config.ATTRIBUTES: {
                PROVIDER_KEY: {
                    OperatorConstants.Misc.NAME: "Provider",
                    OperatorConstants.Config.DESCRIPTION: "Embedding provider: watsonx (IBM watsonx.ai) or litellm (100+ providers including Ollama, HuggingFace, OpenAI, Azure, Cohere)",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Config.DEFAULT: PROVIDER_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.PROVIDER_CONFIG: {
                    OperatorConstants.Misc.NAME: "Provider Configuration",
                    OperatorConstants.Config.DESCRIPTION: "Provider-specific configuration",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                    OperatorConstants.Config.PROPERTIES: {
                        OperatorConstants.Config.MODEL_ID: {
                            OperatorConstants.Misc.NAME: "Model ID",
                            OperatorConstants.Config.DESCRIPTION: "Model identifier in <provider>/<model_id> format for litellm (e.g., 'openai/nomic-embed-text', 'huggingface/sentence-transformers/all-MiniLM-L6-v2'). For watsonx, use the model name directly.",
                            OperatorConstants.Config.REQUIRED: True,
                            OperatorConstants.Config.DEFAULT: "openai/nomic-embed-text",
                            OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                        },
                        OperatorConstants.Config.API_BASE: {
                            OperatorConstants.Misc.NAME: "API Base URL",
                            OperatorConstants.Config.DESCRIPTION: "API endpoint URL (e.g., 'http://localhost:11434/v1' for Ollama)",
                            OperatorConstants.Config.REQUIRED: False,
                            OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                        },
                        OperatorConstants.Config.API_KEY: {
                            OperatorConstants.Misc.NAME: "API Key",
                            OperatorConstants.Config.DESCRIPTION: "Authentication key",
                            OperatorConstants.Config.REQUIRED: False,
                            OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                        },
                    },
                },
                OperatorConstants.Columns.EMBEDDINGS_COLUMN: {
                    OperatorConstants.Misc.NAME: "Embeddings Column",
                    OperatorConstants.Config.DESCRIPTION: "Name of the output column for embeddings",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OVERLAP_RATIO_KEY: {
                    OperatorConstants.Misc.NAME: "Overlap Ratio",
                    OperatorConstants.Config.DESCRIPTION: "Overlap ratio for chunking long text (0.0 to 0.5)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OVERLAP_RATIO_DEFAULT,
                    OperatorConstants.Filtering.MIN_VALUE: OVERLAP_RATIO_MIN,
                    OperatorConstants.Filtering.MAX_VALUE: OVERLAP_RATIO_MAX,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.FLOAT,
                },
                TOKEN_LIMIT_KEY: {
                    OperatorConstants.Misc.NAME: "Token Limit",
                    OperatorConstants.Config.DESCRIPTION: "Maximum token limit for text chunking. Most embedding models support 512-8192 tokens. Adjust based on your model's context window.",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: TOKEN_LIMIT_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
            },
        }

    @staticmethod
    def _build_chunk_text_for_embedding(chunk: dict[str, Any]) -> str:
        """
        Prepends summary to chunk text if summary is present.
        chunk text will be generated as : abstract: <summary>\ncontent: <chunk_text>

        Args:
            chunk: Dictionary containing chunk data with 'chunk' and optionally 'summary' keys

        Returns:
            Formatted chunk text with optional summary prefix
        """
        chunk_text = chunk.get(OperatorConstants.Columns.CHUNK, "")

        if not chunk_text:
            return ""

        # If summary exists, prepend it to the chunk text
        summary = chunk.get(OperatorConstants.Columns.SUMMARY)
        if summary:
            return f"abstract: {summary}\ncontent: {chunk_text}"

        return chunk_text

    def _generate_document_hash(self, content: str) -> str:
        """
        Generate a SHA-256 hash for document content.

        Args:
            content: Document content string

        Returns:
            64-character hexadecimal SHA-256 hash string
        """
        import hashlib

        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _handle_embedding_error(self, error: Exception, model_name: str, context: str = "") -> None:
        """
        Handle embedding generation errors with context-aware messaging.

        Args:
            error: The exception that occurred
            model_name: Name of the model being used
            context: Additional context for logging (e.g., "for chunked text at index 0")

        Raises:
            DocpipeException: Always raises with appropriate error message
        """
        error_msg = str(error)

        # Check if this is a context length error (from any provider)
        if "input length exceeds the context length" in error_msg.lower() or "context length" in error_msg.lower():
            logger.error(
                f"Context length exceeded{' ' + context if context else ''}: Text is too long for model '{model_name}'",
                exc_info=True,
                extra=self.common_log_arguments,
            )
            raise DocpipeException(
                f"Chunked text exceeds the configured embeddings model's (Provider: {self.provider}, "
                f"Model: {model_name}) context length. Add Chunking operator and/or adjust the chunk_type/chunk_size"
                " in Chunking operator and the Embeddings model ID in Embeddings operator to avoid this error."
            ) from error
        else:
            logger.error(
                f"Failed to generate embeddings{' ' + context if context else ''}: {error!s}",
                exc_info=True,
                extra=self.common_log_arguments,
            )
            raise DocpipeException(f"Batch embedding generation failed: {error!s}") from error

    def _create_embeddings(
        self, text: list[str], model_name: str, overlap_ratio: float
    ) -> list[list[float]]:  # NOSONAR python:S3776
        """
        Generate embeddings for text using the configured provider with batch processing.

        This method handles chunking of long text based on approximate token limits
        and generates embeddings using efficient batch processing.

        Args:
            text: List of text strings to embed
            model_name: Name of the model to use
            overlap_ratio: Overlap ratio for chunking (0.0 to 0.5)

        Returns:
            list: List of embedding vectors (one per input text)

        Raises:
            DocpipeException: If embedding generation fails
        """
        # Use configured token limit (default: 8192 tokens)
        # Most embedding models support 512-8192 tokens
        token_limit: int = self.token_limit

        # Approximate: 1 token ≈ 4 characters
        char_limit: int = token_limit * 4
        overlap_chars: int = int(char_limit * overlap_ratio)

        logger.debug(
            f"Using token limit: {token_limit}, char limit: {char_limit}, "
            f"overlap: {overlap_chars} for model: {model_name}",
            extra=self.common_log_arguments,
        )

        # Separate texts into those that need chunking and those that don't
        texts_to_embed: list[str] = []
        text_indices: list[int] = []  # Track original indices
        chunked_texts: dict[int, list[str]] = {}  # Map index to chunks

        for idx, text_item in enumerate(text):
            if not text_item or not text_item.strip():
                # Empty text - will handle separately
                continue

            # Check if text needs chunking
            if len(text_item) <= char_limit:
                # Text fits in one chunk - add to batch
                texts_to_embed.append(text_item)
                text_indices.append(idx)
            else:
                # Text needs chunking
                logger.debug(
                    f"Text at index {idx} (length {len(text_item)}) exceeds limit {char_limit}, chunking...",
                    extra=self.common_log_arguments,
                )

                chunks: list[str] = []
                start: int = 0
                while start < len(text_item):
                    end: int = start + char_limit
                    chunk: str = text_item[start:end]
                    chunks.append(chunk)
                    start = end - overlap_chars if end < len(text_item) else end

                chunked_texts[idx] = chunks
                logger.debug(
                    f"Created {len(chunks)} chunks for text at index {idx}",
                    extra=self.common_log_arguments,
                )

        # Generate embeddings in batches for non-chunked texts
        embeddings_map: dict[int, list[float]] = {}

        if texts_to_embed:
            try:
                # Use batch processing for better performance with keyword arguments
                batch_embeddings = self.embedding_adapter.generate_embeddings_batch(texts=texts_to_embed)

                # Map embeddings back to original indices
                for i, embedding in enumerate(batch_embeddings):
                    embeddings_map[text_indices[i]] = embedding

            except Exception as e:
                self._handle_embedding_error(error=e, model_name=model_name)

        # Process chunked texts
        for idx, chunks in chunked_texts.items():
            try:
                # Generate embeddings for chunks in batch with keyword arguments
                chunk_embeddings = self.embedding_adapter.generate_embeddings_batch(texts=chunks)

                # Average the chunk embeddings
                avg_embedding: list[float] = np.mean(chunk_embeddings, axis=0).tolist()
                embeddings_map[idx] = avg_embedding

            except Exception as e:
                self._handle_embedding_error(error=e, model_name=model_name, context=f"for chunked text at index {idx}")

        # Build final embeddings list in original order
        embeddings: list[list[float]] = []
        for idx, text_item in enumerate(text):
            if not text_item or not text_item.strip():
                # Empty text - return zero vector
                logger.warning(
                    f"Empty text at index {idx} provided for embedding generation",
                    extra=self.common_log_arguments,
                )
                embeddings.append([0.0] * 384)  # Default embedding size
            else:
                embeddings.append(embeddings_map[idx])

        return embeddings

    def _get_doc_identifiers(self, table: pa.Table, idx: int) -> tuple[str, str]:
        """
        Get document ID and name from table at given index.

        Args:
            table: PyArrow table containing documents
            idx: Row index

        Returns:
            tuple: (doc_id, doc_name) as strings
        """
        doc_id: str = (
            table[OperatorConstants.Columns.ID][idx].as_py()
            if OperatorConstants.Columns.ID in table.column_names
            else f"doc_{idx}"
        )
        doc_name: str = (
            table[OperatorConstants.Columns.NAME][idx].as_py()
            if OperatorConstants.Columns.NAME in table.column_names
            else str(doc_id)
        )
        return str(doc_id), str(doc_name)

    def _parse_chunked_content(self, table: pa.Table, idx: int, doc_name: str) -> list[str]:  # NOSONAR python:S3776
        """
        Parse and extract text from chunked content.

        Args:
            table: PyArrow table containing documents
            idx: Row index
            doc_name: Document name for logging

        Returns:
            List of text strings from chunks

        Raises:
            DocpipeException: If chunked content is invalid or empty
        """
        chunked_content_raw: str | list[Any] | dict[str, Any] = table[OperatorConstants.Columns.CHUNKED_CONTENT][
            idx
        ].as_py()
        if not chunked_content_raw:
            raise DocpipeException("Chunked content is empty")

        # Parse chunked_content - it can be a JSON string, a list, or a dict with file path reference
        chunked_content: list[Any] = []
        if isinstance(chunked_content_raw, dict) and DocpipeConstants.CHUNKS_MEMMAP_FILE in chunked_content_raw:
            # Load chunks from binary file
            chunks_filepath = chunked_content_raw[DocpipeConstants.CHUNKS_MEMMAP_FILE]
            logger.debug(
                f"Loading chunks from binary file: {chunks_filepath} for document: {doc_name}",
                extra=self.common_log_arguments,
            )
            from docpipe.utils.core.memmap_file_utils import load_chunks_from_file

            chunked_content = load_chunks_from_file(filepath=chunks_filepath)
        elif isinstance(chunked_content_raw, str):
            # Parse JSON string from chunker operator
            try:
                chunked_content = json.loads(chunked_content_raw)
                logger.debug(
                    f"Parsed chunked_content from JSON string for document: {doc_name}",
                    extra=self.common_log_arguments,
                )
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to parse chunked_content JSON for document {doc_name}: {e!s}",
                    extra=self.common_log_arguments,
                )
                raise DocpipeException(f"Invalid chunked_content JSON format: {e!s}") from e
        elif isinstance(chunked_content_raw, list):
            # Already a list
            chunked_content = chunked_content_raw
            logger.debug(
                f"Using chunked_content as list for document: {doc_name}",
                extra=self.common_log_arguments,
            )
        else:
            raise DocpipeException(f"Unexpected chunked_content type: {type(chunked_content_raw).__name__}")

        # Extract text from chunks - handle both dict and string formats
        texts: list[str] = []
        for chunk in chunked_content:
            if isinstance(chunk, dict):
                # Chunk is a dictionary with 'chunk' key
                chunk_text = self._build_chunk_text_for_embedding(chunk=chunk)
                if chunk_text:
                    texts.append(chunk_text)
            elif isinstance(chunk, str):
                # Chunk is already a string
                if chunk:
                    texts.append(chunk)
            else:
                logger.warning(
                    f"Skipping chunk with unexpected type: {type(chunk).__name__}",
                    extra=self.common_log_arguments,
                )

        if not texts:
            raise DocpipeException("No valid text chunks found after parsing")

        logger.debug(
            f"Processing {len(texts)} chunks for document: {doc_name}",
            extra=self.common_log_arguments,
        )
        return texts

    def _get_full_document_content(self, table: pa.Table, idx: int) -> list[str]:
        """
        Extract full document content as a single-item list.

        Args:
            table: PyArrow table containing documents
            idx: Row index

        Returns:
            List containing single document content string

        Raises:
            DocpipeException: If content is missing or empty
        """
        content: str = table[self.doc_column][idx].as_py()
        if not content:
            raise DocpipeException(f"Document content column '{self.doc_column}' is empty or missing")
        return [content]

    def _handle_doc_hash_generation_failure(
        self, table: pa.Table, error: Exception, metadata: dict[str, Any]
    ) -> tuple[pa.Table, dict[str, Any]]:
        """
        Handle failure in document hash generation by marking all docs as failed.

        Args:
            table: PyArrow table containing documents
            error: The exception that occurred
            metadata: Metadata dictionary to update

        Returns:
            tuple: (empty table slice, updated metadata)
        """
        logger.error(
            f"Failed to generate document hashes: {error!s}",
            extra=self.common_log_arguments,
        )

        # Mark all documents as failed
        for idx in range(table.num_rows):
            doc_id, doc_name = self._get_doc_identifiers(table, idx)
            self.record_failed_document(
                metadata=metadata,
                doc_id=doc_id,
                doc_name=doc_name,
                reason=str(error),
            )

        current_status = metadata[Metrics.External.NODE_STATUS]
        metadata[Metrics.External.NODE_STATUS] = OperatorUtils.merge_status(
            current_status if isinstance(current_status, ExecutionStatus) else ExecutionStatus(current_status),
            ExecutionStatus.COMPLETED_WITH_ERRORS,
        ).value
        return [table.slice(0, 0)], metadata

    def _update_doc_hash_column(self, table: pa.Table, doc_id_hashes: list[str]) -> pa.Table:
        """
        Update or add document hash column to table.

        Args:
            table: PyArrow table to update
            doc_id_hashes: List of document hashes

        Returns:
            Updated PyArrow table with hash column
        """
        if not doc_id_hashes:
            return table

        if self.doc_id_hash_column in table.column_names:
            table = table.drop_columns([self.doc_id_hash_column])

        table = TransformUtils.add_column(table=table, name=self.doc_id_hash_column, content=doc_id_hashes)

        logger.info(
            f"Added document hash column '{self.doc_id_hash_column}' to table",
            extra=self.common_log_arguments,
        )
        return table

    def _process_single_document(
        self,
        table: pa.Table,
        idx: int,
        has_chunked_content: bool,
        doc_hash_values: list[str],
    ) -> tuple[list[float] | list[list[float]], str]:
        """
        Process a single document to generate embeddings.

        Args:
            table: PyArrow table containing documents
            idx: Row index of the document to process
            has_chunked_content: Whether the table contains chunked content
            doc_hash_values: Pre-cached list of document hash values

        Returns:
            tuple: (embeddings, doc_hash) where embeddings is either a single vector
                   or list of vectors depending on chunked_content

        Raises:
            Exception: Any error during content extraction or embedding generation
        """
        _doc_id, doc_name = self._get_doc_identifiers(table, idx)

        # Get content to embed using helper methods
        if has_chunked_content:
            texts = self._parse_chunked_content(table, idx, doc_name)
        else:
            texts = self._get_full_document_content(table, idx)

        # Generate embeddings using configured provider
        doc_embeddings: list[list[float]] = self._create_embeddings(
            text=texts,
            model_name=self.model_id,
            overlap_ratio=self.overlap_ratio,
        )

        # For chunked content, store all embeddings; for full doc, store single embedding
        embeddings_result: list[float] | list[list[float]]
        if has_chunked_content:
            embeddings_result = doc_embeddings
        else:
            embeddings_result = doc_embeddings[0]

        # Retrieve document hash from pre-cached values
        doc_hash: str = doc_hash_values[idx]

        logger.debug(
            f"Successfully generated embeddings for document: {doc_name}",
            extra=self.common_log_arguments,
        )

        return embeddings_result, doc_hash

    def transform(
        self, table: pa.Table, file_name: str | None = None
    ) -> tuple[list[pa.Table], dict[str, Any]]:  # NOSONAR python:S3776
        """
        Transform the input table by adding embeddings using memory-efficient internal slicing.

        Args:
            table: Input PyArrow table with document content
            file_name: Optional file name (not used)

        Returns:
            tuple: (list of output tables, metadata dictionary)
        """
        logger.info(
            f"Starting embeddings generation with provider: {self.provider}, model: {self.model_id}",
            extra=self.common_log_arguments,
        )

        # Initialize metadata
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=OperatorUtils.find_doc_count(table=table))

        # Ensure doc_id_hash column exists
        # DocIdHashOperator requires content column, so check if it's available
        if self.doc_id_hash_column not in table.column_names:
            if self.doc_column not in table.column_names:
                # Cannot generate doc_id_hash without content column
                error = DocpipeException(
                    f"Cannot generate '{self.doc_id_hash_column}' column: '{self.doc_column}' column is missing."
                )
                return self._handle_doc_hash_generation_failure(table, error, metadata)

            # Generate doc_id_hash using DocIdHashOperator
            try:
                doc_id_op: DocIdHashOperator = DocIdHashOperator(
                    config={
                        OperatorConstants.Columns.DOC_COLUMN: self.doc_column,
                        OperatorConstants.Columns.DOC_ID_HASH: self.doc_id_hash_column,
                    }
                )
                result_tables: list[pa.Table]
                result_tables, _ = doc_id_op.transform(table)
                table = result_tables[0]
            except Exception as e:
                return self._handle_doc_hash_generation_failure(table, e, metadata)

        # Check if we have chunked content
        has_chunked_content: bool = OperatorConstants.Columns.CHUNKED_CONTENT in table.column_names

        # Internal slicing to prevent Python memory spikes for large tables
        # We process in slices of 2,000 rows to keep object overhead low
        internal_slice_size = 2000
        processed_tables: list[pa.Table] = []

        num_rows = table.num_rows
        total_slices = (num_rows + internal_slice_size - 1) // internal_slice_size

        for start_idx in range(0, num_rows, internal_slice_size):
            end_idx = min(start_idx + internal_slice_size, num_rows)
            slice_num = (start_idx // internal_slice_size) + 1
            slice_table = table.slice(start_idx, end_idx - start_idx)

            logger.info(
                f"Processing slice {slice_num}/{total_slices} (rows {start_idx}-{end_idx - 1})",
                extra=self.common_log_arguments,
            )

            # Temporary lists for this slice only
            slice_embeddings: list[list[float] | list[list[float]]] = []
            slice_doc_id_hashes: list[str] = []
            slice_remove_idx: list[int] = []

            # Cache hash values for this slice
            slice_hash_values: list[str] = slice_table[self.doc_id_hash_column].to_pylist()

            for i in range(slice_table.num_rows):
                doc_id, doc_name = self._get_doc_identifiers(slice_table, i)
                try:
                    embeddings_result, doc_hash = self._process_single_document(
                        table=slice_table,
                        idx=i,
                        has_chunked_content=has_chunked_content,
                        doc_hash_values=slice_hash_values,
                    )
                    slice_embeddings.append(embeddings_result)
                    slice_doc_id_hashes.append(doc_hash)
                    metadata[Metrics.External.PROCESSED_DOCS] += 1
                except Exception as exc:
                    logger.error(
                        f"Failed embeddings for {doc_name}: {exc!s}",
                        extra=self.common_log_arguments,
                    )
                    self.record_failed_document(
                        metadata=metadata,
                        doc_id=doc_id,
                        doc_name=doc_name,
                        reason=f"Embedding failure: {exc!s}",
                    )
                    slice_remove_idx.append(i)

            # Cleanup failed rows from this slice
            if slice_remove_idx:
                slice_table = OperatorUtils.remove_rows(table=slice_table, remove_row_idx=slice_remove_idx)

            # Add results to this slice
            if slice_embeddings:
                # Check each row to determine storage format based on chunk storage
                # If chunks are stored as files for a row, embeddings must also be stored as files
                embeddings_column_data: list[dict[str, str] | list[float] | list[list[float]]] = []
                embeddings_dir = None
                doc_ids = None
                chunks_column_data = None

                # Get chunks column data if it exists
                if has_chunked_content:
                    chunks_column_data = slice_table[OperatorConstants.Columns.CHUNKED_CONTENT].to_pylist()

                # Get document IDs for filename generation
                if OperatorConstants.Columns.ID in slice_table.column_names:
                    doc_ids = slice_table[OperatorConstants.Columns.ID].to_pylist()

                for idx, embeddings in enumerate(slice_embeddings):
                    # Determine if this row's chunks are stored as files
                    row_chunks_as_files = False
                    if chunks_column_data and idx < len(chunks_column_data):
                        chunk_data = chunks_column_data[idx]
                        if isinstance(chunk_data, dict) and DocpipeConstants.CHUNKS_MEMMAP_FILE in chunk_data:
                            row_chunks_as_files = True

                    # Store embeddings as files if chunks are stored as files
                    if row_chunks_as_files:
                        # Lazy initialization of embeddings directory
                        # Include embeddings column name to segregate multi-model embeddings
                        if embeddings_dir is None:
                            embeddings_dir = get_data_path(
                                sub_dir=f"/{self.job_id}/{self.job_run_id}/temp_data/embeddings/{self.embeddings_column}"
                            )

                        # Generate filename using sanitized document ID
                        if doc_ids and idx < len(doc_ids):
                            from docpipe.core.operators.operator_utils import sanitize_doc_id_for_filename

                            sanitized_doc_id = sanitize_doc_id_for_filename(doc_ids[idx])
                            embeddings_filename = f"{sanitized_doc_id}_embeddings.bin"
                        else:
                            # Fallback to UUID if doc_id not available
                            embeddings_filename = f"embeddings_{uuid.uuid4().hex}.bin"
                        embeddings_filepath = os.path.join(embeddings_dir, embeddings_filename)

                        # Write embeddings to memmap file
                        write_content_to_file(content_list=embeddings, filepath=embeddings_filepath)

                        # Store file path reference
                        embeddings_column_data.append({DocpipeConstants.EMBEDDINGS_MEMMAP_FILE: embeddings_filepath})

                        logger.debug(
                            f"Wrote embeddings to memmap file: {embeddings_filepath}",
                            extra=self.common_log_arguments,
                        )
                    else:
                        # Store embeddings in-memory
                        embeddings_column_data.append(embeddings)

                # Add embeddings column with mixed storage format
                slice_table = TransformUtils.add_column(
                    table=slice_table, name=self.embeddings_column, content=embeddings_column_data
                )
                logger.info(
                    f"Added embeddings column '{self.embeddings_column}' to table",
                    extra=self.common_log_arguments,
                )
                # Add/Update hashes
                if self.doc_id_hash_column in slice_table.column_names:
                    slice_table = slice_table.drop_columns([self.doc_id_hash_column])
                    slice_table = TransformUtils.add_column(
                        table=slice_table, name=self.doc_id_hash_column, content=slice_doc_id_hashes
                    )

                processed_tables.append(slice_table)

                # Log memory-efficient completion
                logger.info(
                    f"Slice {slice_num}/{total_slices} complete: "
                    f"processed {len(slice_embeddings)} docs, "
                    f"failed {len(slice_remove_idx)} docs",
                    extra=self.common_log_arguments,
                )

            # CRITICAL: These lists are now eligible for GC before the next slice starts
            del slice_embeddings
            del slice_doc_id_hashes
            del slice_remove_idx

        # Final assembly
        final_table = pa.concat_tables(processed_tables) if processed_tables else table.slice(0, 0)

        # Update node status based on failures
        if metadata[Metrics.External.FAILED_DOCS_COUNT] > 0:
            current_status = metadata[Metrics.External.NODE_STATUS]
            metadata[Metrics.External.NODE_STATUS] = OperatorUtils.merge_status(
                current_status if isinstance(current_status, ExecutionStatus) else ExecutionStatus(current_status),
                ExecutionStatus.COMPLETED_WITH_ERRORS,
            ).value

        logger.info(
            f"Embeddings generation completed. Processed: {metadata[Metrics.External.PROCESSED_DOCS]}, "
            f"Failed: {metadata[Metrics.External.FAILED_DOCS_COUNT]}",
            extra=self.common_log_arguments,
        )

        return [final_table], metadata
