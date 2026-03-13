"""
Embeddings Operator

This operator generates vector embeddings for text content using various embedding providers.
It supports multiple providers (Ollama, OpenAI, etc.) and handles chunking of long text.
"""

import json
from enum import Enum
from typing import Any

import numpy as np
import pyarrow as pa

try:
    from data_processing.utils import TransformUtils

    HAS_TRANSFORM_UTILS: bool = True
except ImportError:
    HAS_TRANSFORM_UTILS: bool = False

    # Fallback implementation
    class TransformUtils:
        @staticmethod
        def add_column(table: pa.Table, name: str, content: list[Any]) -> pa.Table:
            """Add a column to a PyArrow table."""
            # Infer the type from the content
            new_column = pa.array(content)
            new_field = pa.field(name, new_column.type)
            return table.append_column(new_field, new_column)


from common.clients.ollama_client import (
    DEFAULT_TOKEN_LIMIT,
    OLLAMA_MODEL_TOKEN_LIMITS,
    OllamaClient,
)
from common.constants.constants import (
    AttributeDataTypes,
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
)
from common.constants.operator_constants import OperatorConstants
from common.exceptions.datasift_exceptions import DatasiftException
from common.util.log import get_logger
from common.util.operator_utils import find_doc_count, remove_rows
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.operator_utils import OperatorUtils
from core.operators.universal.doc_id.doc_id_hash import DocIdHashOperator

logger = get_logger()


class EmbeddingsProvider(Enum):
    """
    Supported embeddings providers.

    This enum defines the available embedding providers that can be used
    for generating vector embeddings from text content.
    """

    OLLAMA = "ollama"
    OPENAI = "openai"


# Supported embeddings providers (for backward compatibility)
SUPPORTED_EMBEDDINGS_TYPES: list[str] = [provider.value for provider in EmbeddingsProvider]

# Overlap ratio for chunking
OVERLAP_RATIO_KEY: str = "overlap_ratio"
OVERLAP_RATIO_DEFAULT: float = 0.2
OVERLAP_RATIO_MIN: float = 0.0
OVERLAP_RATIO_MAX: float = 0.5

# Embeddings type configuration key
EMBEDDINGS_TYPE_KEY: str = "embeddings_type"
EMBEDDINGS_TYPE_DEFAULT: str = "ollama"


class EmbeddingsOperator(AbstractOperator):
    """
    Operator for generating embeddings using various embedding providers.

    This operator processes documents and generates vector embeddings using different
    embedding providers. It supports:
    - Multiple embedding providers (Ollama, OpenAI, etc.)
    - Multiple embedding models per provider
    - Automatic chunking for long text
    - Pre-chunked content processing
    - Document hash generation
    - Error handling per document

    Supported Providers:
    - ollama: Local Ollama models (llama2, mistral, etc.)
    - openai: OpenAI embedding models (text-embedding-ada-002, etc.)

    To add a new provider:
    1. Add provider name to SUPPORTED_EMBEDDINGS_TYPES
    2. Implement _create_embeddings_<provider>() method
    3. Add provider case to _create_embeddings() routing method
    4. Update metadata and documentation
    """

    short_name: str = OperatorConstants.Operators.EMBEDDINGS
    category: OperatorCategory = OperatorCategory.Functional

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the Embeddings Operator.

        Args:
            config: Configuration dictionary containing:
                - embeddings_type: Provider type ("ollama", "openai", etc.)
                - embeddings_model_id: Model name for the selected provider
                - embeddings_column: Output column name for embeddings (default: "embeddings")
                - overlap_ratio: Overlap ratio for chunking long text (default: 0.2)
                - doc_column: Input column containing document content (default: "content")
                - doc_id_hash_column: Column for document hash (default: "doc_id_hash")
        """
        super().__init__(config)

        # Provider configuration
        self.embeddings_type: str = config.get(EMBEDDINGS_TYPE_KEY, EMBEDDINGS_TYPE_DEFAULT)

        # Model configuration
        self.embeddings_model_id: str = config.get(OperatorConstants.Config.EMBEDDINGS_MODEL_ID, "granite4")

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

        # Logging
        self.common_log_arguments: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }

        # Initialize embedding client
        self.embedding_client: OllamaClient = self._initialize_embedding_client()

        logger.info(
            f"Initialized EmbeddingsOperator with provider: {self.embeddings_type}, model: {self.embeddings_model_id}",
            extra=self.common_log_arguments,
        )

    def _initialize_embedding_client(self) -> OllamaClient:
        """
        Initialize the appropriate embedding client based on embeddings_type.

        This method creates and returns the appropriate client (OllamaClient, OpenAIClient, etc.)
        based on the configured embeddings_type. The client is stored as self.embedding_client
        for reuse across multiple embedding operations.

        Returns:
            The initialized embedding client for the configured provider

        Raises:
            DatasiftException: If the provider is unsupported or client initialization fails
        """
        try:
            if self.embeddings_type == EmbeddingsProvider.OLLAMA.value:
                return OllamaClient(model=self.embeddings_model_id, validate_model=True)
            elif self.embeddings_type == EmbeddingsProvider.OPENAI.value:
                # Placeholder for OpenAI client initialization
                # TODO: Implement OpenAI client when available
                raise DatasiftException("OpenAI embeddings provider is not yet implemented")
            else:
                raise DatasiftException(
                    f"Unsupported embeddings_type: {self.embeddings_type}. "
                    f"Supported types: {SUPPORTED_EMBEDDINGS_TYPES}"
                )
        except Exception as e:
            raise DatasiftException(
                f"Failed to initialize embedding client for provider '{self.embeddings_type}': {e!s}"
            ) from e

    def get_required_features(self) -> list[str]:
        """Return list of required input features."""
        return [self.doc_column]

    def validate(self, errors: list[str], warnings: list[str], available_features: list[str]) -> None:
        """
        Validate operator configuration.

        Args:
            errors: List to append validation errors
            warnings: List to append validation warnings
            available_features: List of available input features
        """
        super().validate(errors, warnings, available_features)

        # Validate embeddings type
        if self.should_validate_field(field_value=self.embeddings_type):
            if not isinstance(self.embeddings_type, str):
                errors.append(f"embeddings_type must be a string, got {type(self.embeddings_type)}")
            elif self.embeddings_type not in SUPPORTED_EMBEDDINGS_TYPES:
                errors.append(
                    f"embeddings_type must be one of {SUPPORTED_EMBEDDINGS_TYPES}, got '{self.embeddings_type}'"
                )

        # Validate overlap ratio
        if self.should_validate_field(field_value=self.overlap_ratio):
            if not isinstance(self.overlap_ratio, (int, float)):
                errors.append(f"overlap_ratio must be a number, got {type(self.overlap_ratio)}")
            elif not (OVERLAP_RATIO_MIN <= self.overlap_ratio <= OVERLAP_RATIO_MAX):
                errors.append(f"overlap_ratio must be between {OVERLAP_RATIO_MIN} and {OVERLAP_RATIO_MAX}")

        # Validate model ID
        if self.should_validate_field(field_value=self.embeddings_model_id):
            if not self.embeddings_model_id or not isinstance(self.embeddings_model_id, str):
                errors.append("embeddings_model_id must be a non-empty string")

    def get_metadata(self) -> dict[str, Any]:
        """
        Return operator metadata for UI and documentation.

        Returns:
            dict: Operator metadata including features and attributes
        """
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: OperatorCategory.Functional.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: True,
            OperatorConstants.Misc.LABEL: "Embeddings",
            OperatorConstants.Config.DESCRIPTION: "Generate vector embeddings using various providers (Ollama, OpenAI, etc.)",
            OperatorConstants.Config.FEATURES: {
                OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT: {
                    OperatorConstants.Misc.NAME: "Embeddings",
                    OperatorConstants.Config.DESCRIPTION: "Vector embeddings generated from document content",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_VECTOR,
                },
                OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: {
                    OperatorConstants.Misc.NAME: "Document ID Hash",
                    OperatorConstants.Config.DESCRIPTION: "Unique hash identifier for the document",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TAGS: [
                        OperatorConstants.Misc.MANDATORY,
                        OperatorConstants.Misc.INTERNAL_FEATURE,
                    ],
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                },
            },
            OperatorConstants.Config.ATTRIBUTES: {
                EMBEDDINGS_TYPE_KEY: {
                    OperatorConstants.Misc.NAME: "Embeddings Provider",
                    OperatorConstants.Config.DESCRIPTION: f"Embedding provider to use ({', '.join(SUPPORTED_EMBEDDINGS_TYPES)})",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Config.DEFAULT: EMBEDDINGS_TYPE_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.EMBEDDINGS_MODEL_ID: {
                    OperatorConstants.Misc.NAME: "Embeddings Model",
                    OperatorConstants.Config.DESCRIPTION: "Model name for the selected provider",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Config.DEFAULT: "llama2",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
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
            },
        }

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

    def _create_embeddings(self, text: list[str], model_name: str, overlap_ratio: float) -> list[list[float]]:
        """
        Generate embeddings for text using the configured provider.

        This method routes to the appropriate provider-specific implementation
        based on the embeddings_type configuration.

        Args:
            text: List of text strings to embed
            model_name: Name of the model to use
            overlap_ratio: Overlap ratio for chunking (0.0 to 0.5)

        Returns:
            list: List of embedding vectors (one per input text)

        Raises:
            DatasiftException: If embedding generation fails or provider is unsupported
        """
        if self.embeddings_type == EmbeddingsProvider.OLLAMA.value:
            return self._generate_embeddings_ollama(text, model_name, overlap_ratio)
        elif self.embeddings_type == EmbeddingsProvider.OPENAI.value:
            return self._create_embeddings_openai(text, model_name, overlap_ratio)
        else:
            raise DatasiftException(
                f"Unsupported embeddings_type: {self.embeddings_type}. Supported types: {SUPPORTED_EMBEDDINGS_TYPES}"
            )

    def _generate_embeddings_ollama(self, text: list[str], model_name: str, overlap_ratio: float) -> list[list[float]]:
        """
        Generate embeddings for text using Ollama.

        This method handles chunking of long text based on model token limits
        and generates embeddings for each chunk, averaging them if needed.

        Args:
            text: List of text strings to embed
            model_name: Name of the Ollama model to use
            overlap_ratio: Overlap ratio for chunking (0.0 to 0.5)

        Returns:
            list: List of embedding vectors (one per input text)

        Raises:
            DatasiftException: If embedding generation fails
        """
        # Use the pre-initialized embedding client
        ollama_client: OllamaClient = self.embedding_client

        embeddings: list[list[float]] = []
        token_limit: int = OLLAMA_MODEL_TOKEN_LIMITS.get(model_name, DEFAULT_TOKEN_LIMIT)

        # Approximate: 1 token ≈ 4 characters
        char_limit: int = token_limit * 4
        overlap_chars: int = int(char_limit * overlap_ratio)

        logger.debug(
            f"Using token limit: {token_limit}, char limit: {char_limit}, "
            f"overlap: {overlap_chars} for model: {model_name}",
            extra=self.common_log_arguments,
        )

        for text_item in text:
            if not text_item or not text_item.strip():
                # Empty text - return zero vector
                logger.warning(
                    "Empty text provided for embedding generation",
                    extra=self.common_log_arguments,
                )
                embeddings.append([0.0] * 384)  # Default embedding size
                continue

            # Check if text needs chunking
            if len(text_item) <= char_limit:
                # Text fits in one chunk
                try:
                    embedding: list[float] = ollama_client.generate_embeddings(text_item)
                    embeddings.append(embedding)
                except Exception as e:
                    logger.error(
                        f"Failed to generate embedding: {e!s}",
                        exc_info=True,
                        extra=self.common_log_arguments,
                    )
                    raise DatasiftException(f"Ollama embedding generation failed: {e!s}") from e
            else:
                # Text needs chunking
                logger.debug(
                    f"Text length {len(text_item)} exceeds limit {char_limit}, chunking...",
                    extra=self.common_log_arguments,
                )

                chunks: list[str] = []
                start: int = 0
                while start < len(text_item):
                    end: int = start + char_limit
                    chunk: str = text_item[start:end]
                    chunks.append(chunk)
                    start = end - overlap_chars if end < len(text_item) else end

                logger.debug(
                    f"Created {len(chunks)} chunks for text",
                    extra=self.common_log_arguments,
                )

                # Generate embeddings for each chunk
                chunk_embeddings: list[list[float]] = []
                for i, chunk in enumerate(chunks):
                    try:
                        embedding = ollama_client.generate_embeddings(chunk)
                        chunk_embeddings.append(embedding)
                    except Exception as e:
                        logger.error(
                            f"Failed to generate embedding for chunk {i + 1}/{len(chunks)}: {e!s}",
                            exc_info=True,
                            extra=self.common_log_arguments,
                        )
                        raise DatasiftException(f"Ollama embedding generation failed for chunk {i + 1}: {e!s}") from e

                # Average the chunk embeddings
                avg_embedding: list[float] = np.mean(chunk_embeddings, axis=0).tolist()
                embeddings.append(avg_embedding)

        return embeddings

    def _create_embeddings_openai(self, text: list[str], model_name: str, overlap_ratio: float) -> list[list[float]]:
        """
        Generate embeddings for text using OpenAI.

        This is a placeholder implementation for OpenAI embeddings.
        To be implemented when OpenAI provider support is added.

        Args:
            text: List of text strings to embed
            model_name: Name of the OpenAI model to use
            overlap_ratio: Overlap ratio for chunking (0.0 to 0.5)

        Returns:
            list: List of embedding vectors (one per input text)

        Raises:
            DatasiftException: Currently raises as not yet implemented
        """
        raise DatasiftException(
            "OpenAI embeddings provider is not yet implemented. This is a placeholder for future extension."
        )

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
            table[OperatorConstants.ID][idx].as_py() if OperatorConstants.ID in table.column_names else f"doc_{idx}"
        )
        doc_name: str = (
            table[OperatorConstants.NAME][idx].as_py() if OperatorConstants.NAME in table.column_names else str(doc_id)
        )
        return str(doc_id), str(doc_name)

    def _parse_chunked_content(self, table: pa.Table, idx: int, doc_name: str) -> list[str]:
        """
        Parse and extract text from chunked content.

        Args:
            table: PyArrow table containing documents
            idx: Row index
            doc_name: Document name for logging

        Returns:
            List of text strings from chunks

        Raises:
            DatasiftException: If chunked content is invalid or empty
        """
        chunked_content_raw: str | list[Any] = table[OperatorConstants.CHUNKED_CONTENT][idx].as_py()
        if not chunked_content_raw:
            raise DatasiftException("Chunked content is empty")

        # Parse chunked_content - it can be a JSON string or a list
        chunked_content: list[Any] = []
        if isinstance(chunked_content_raw, str):
            # Parse JSON string from DoclingChunkerOperator
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
                raise DatasiftException(f"Invalid chunked_content JSON format: {e!s}") from e
        elif isinstance(chunked_content_raw, list):
            # Already a list
            chunked_content = chunked_content_raw
            logger.debug(
                f"Using chunked_content as list for document: {doc_name}",
                extra=self.common_log_arguments,
            )
        else:
            raise DatasiftException(f"Unexpected chunked_content type: {type(chunked_content_raw).__name__}")

        # Extract text from chunks - handle both dict and string formats
        texts: list[str] = []
        for chunk in chunked_content:
            if isinstance(chunk, dict):
                # Chunk is a dictionary with 'chunk' key
                chunk_text: str = chunk.get(OperatorConstants.CHUNK, "")
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
            raise DatasiftException("No valid text chunks found after parsing")

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
            DatasiftException: If content is missing or empty
        """
        content: str = table[self.doc_column][idx].as_py()
        if not content:
            raise DatasiftException(f"Document content column '{self.doc_column}' is empty or missing")
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

        metadata[Metrics.External.NODE_STATUS] = OperatorUtils.merge_status(
            metadata[Metrics.External.NODE_STATUS],
            ExecutionStatus.COMPLETED_WITH_ERRORS,
        )
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

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Transform the input table by adding embeddings.

        Args:
            table: Input PyArrow table with document content
            file_name: Optional file name (not used)

        Returns:
            tuple: (list of output tables, metadata dictionary)
        """
        logger.info(
            f"Starting embeddings generation with provider: {self.embeddings_type}, model: {self.embeddings_model_id}",
            extra=self.common_log_arguments,
        )

        # Initialize metadata
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=find_doc_count(table=table))

        # Ensure doc_id_hash column exists using DocIdHashOperator
        if self.doc_id_hash_column not in table.column_names:
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

        # Initialize result containers
        embeddings_list: list[list[float] | list[list[float]]] = []
        doc_id_hashes: list[str] = []
        remove_row_idx: list[int] = []

        # Check if we have chunked content
        has_chunked_content: bool = OperatorConstants.Columns.CHUNKED_CONTENT in table.column_names

        # Process each document using PyArrow columnar access
        for idx in range(table.num_rows):
            doc_id, doc_name = self._get_doc_identifiers(table, idx)

            try:
                # Get content to embed using helper methods
                if has_chunked_content:
                    texts = self._parse_chunked_content(table, idx, doc_name)
                else:
                    texts = self._get_full_document_content(table, idx)

                # Generate embeddings using configured provider
                doc_embeddings: list[list[float]] = self._create_embeddings(
                    text=texts,
                    model_name=self.embeddings_model_id,
                    overlap_ratio=self.overlap_ratio,
                )

                # For chunked content, store all embeddings; for full doc, store single embedding
                if has_chunked_content:
                    embeddings_list.append(doc_embeddings)
                else:
                    embeddings_list.append(doc_embeddings[0])

                # Retrieve document hash (guaranteed to exist after DocIdHashOperator)
                doc_hash: str = table[self.doc_id_hash_column][idx].as_py()
                doc_id_hashes.append(doc_hash)
                metadata[Metrics.External.PROCESSED_DOCS] += 1

                logger.debug(
                    f"Successfully generated embeddings for document: {doc_name}",
                    extra=self.common_log_arguments,
                )

            except Exception as exc:
                logger.error(
                    f"Failed to generate embeddings for document {doc_name}: {exc!s}",
                    exc_info=True,
                    stack_info=True,
                    extra=self.common_log_arguments,
                )

                self.record_failed_document(
                    metadata=metadata,
                    doc_id=doc_id,
                    doc_name=doc_name,
                    reason=f"Failed to generate embeddings: {exc!s}",
                )

                metadata[Metrics.External.NODE_STATUS] = OperatorUtils.merge_status(
                    metadata[Metrics.External.NODE_STATUS],
                    ExecutionStatus.COMPLETED_WITH_ERRORS,
                )

                remove_row_idx.append(idx)

        # Remove failed documents
        table = remove_rows(table=table, remove_row_idx=remove_row_idx)

        # Add embeddings column
        if embeddings_list:
            table = TransformUtils.add_column(table=table, name=self.embeddings_column, content=embeddings_list)
            logger.info(
                f"Added embeddings column '{self.embeddings_column}' to table",
                extra=self.common_log_arguments,
            )

        # Add or update document hash column using helper method
        table = self._update_doc_hash_column(table, doc_id_hashes)

        logger.info(
            f"Embeddings generation completed. Processed: {metadata[Metrics.External.PROCESSED_DOCS]}, "
            f"Failed: {metadata[Metrics.External.FAILED_DOCS_COUNT]}",
            extra=self.common_log_arguments,
        )

        return [table], metadata


def main() -> int:
    """
    Demo pipeline: Ingest → Extract → Chunk → Embeddings

    This demonstrates the complete workflow using a PDF from test fixtures.
    The script now automatically handles Ollama setup:
    - Checks if Ollama is installed
    - Starts Ollama server if not running
    - Pulls the specified model if not available

    Usage:
        python embeddings_operator.py [OPTIONS]

    Examples:
        # Use default PDF and model (auto-setup enabled)
        python embeddings_operator.py

        # Specify custom PDF
        python embeddings_operator.py --pdf tests/fixtures/invoices/TR-INV_001_3_2.1.pdf

        # Specify custom Ollama model
        python embeddings_operator.py --model mistral

        # Skip automatic setup
        python embeddings_operator.py --no-auto-setup

        # Disable automatic model pulling
        python embeddings_operator.py --no-auto-pull
    """
    import argparse
    from pathlib import Path

    # Calculate project root directory dynamically
    # Current file is at: src/datasift_opensource/backend/core/operators/universal/embeddings/embeddings_operator.py
    # Path structure: embeddings_operator.py -> embeddings -> universal -> operators -> core -> backend -> datasift_opensource -> src -> PROJECT_ROOT
    # Need to go up 8 levels to reach project root
    project_root: Path = Path(__file__).resolve().parents[7]
    default_pdf_path: Path = project_root / "tests" / "fixtures" / "invoices"

    # Parse command line arguments
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Demo: Complete pipeline from PDF ingestion to embeddings generation"
    )
    parser.add_argument(
        "--pdf",
        type=str,
        default=str(default_pdf_path),
        help=f"Path to PDF file or directory (default: {default_pdf_path})",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="granite4",
        help="Ollama model to use for embeddings (default: granite4)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Chunk size in tokens (default: 512)",
    )
    parser.add_argument(
        "--no-auto-setup",
        action="store_true",
        help="Skip automatic Ollama setup (installation check, server start, model pull)",
    )
    parser.add_argument(
        "--no-auto-pull",
        action="store_true",
        help="Disable automatic model pulling (only check if model exists)",
    )
    args: argparse.Namespace = parser.parse_args()

    # ========================================================================
    # OLLAMA SETUP - Automatic setup if not disabled
    # ========================================================================
    if not args.no_auto_setup:
        print("=" * 80)
        print("OLLAMA SETUP CHECK")
        print("=" * 80)

        # Check Ollama readiness with auto-remediation
        print("\nChecking Ollama prerequisites...")
        auto_pull = not args.no_auto_pull
        success, message = OllamaClient.ensure_ready(model_name=args.model, auto_start=True, auto_pull=auto_pull)

        if not success:
            print(f"\n✗ {message}")
            print("\n" + "=" * 80)
            print("SETUP REQUIRED")
            print("=" * 80)
            print("Please follow the instructions above to set up Ollama.")
            print("=" * 80)
            return 1

        print(f"✓ {message}")
    else:
        # Manual setup mode - just check if everything is ready
        print("=" * 80)
        print("OLLAMA SETUP CHECK (Manual Mode)")
        print("=" * 80)

        # Check if Ollama package is available
        try:
            import ollama
        except ImportError:
            print("\n❌ Error: ollama package not installed")
            print("   Install it with: pip install ollama")
            return 1

        # Check if Ollama is running
        try:
            ollama.list()
            print("✓ Ollama is running")
        except Exception:
            print("\n❌ Error: Ollama is not running or not accessible")
            print("   Please start Ollama with: ollama serve")
            print(f"   Then pull a model with: ollama pull {args.model}")
            return 1

    # Import required operators
    try:
        from core.operators.universal.chunker.docling_chunker import (
            DoclingChunkerOperator,
        )
        from core.operators.universal.extract.extract_docling import (
            ExtractDoclingOperator,
        )
        from core.operators.universal.ingest.ingest_local_folder import (
            IngestLocalOperator,
        )
    except ImportError as e:
        logger.error(f"Failed to import required operators: {e}")
        print("\n❌ Error: Failed to import operators. Make sure you're running from the correct directory.")
        print(
            "   Try: cd src/datasift_opensource/backend && python -m core.operators.universal.embeddings.embeddings_operator"
        )
        return 1

    # Validate PDF path
    pdf_path: Path = Path(args.pdf)
    if not pdf_path.exists():
        print("\n" + "=" * 80)
        print("❌ ERROR: PDF PATH NOT FOUND")
        print("=" * 80)
        print(f"The specified path does not exist: {pdf_path}")
        print(f"Absolute path: {pdf_path.resolve()}")
        print(f"\nProject root: {project_root}")
        print(f"Expected test fixtures at: {default_pdf_path}")
        print("\nPlease ensure:")
        print("  1. The path exists")
        print("  2. You have the correct permissions")
        print("  3. The test fixtures are in the expected location")
        return 1

    # Count PDF files
    pdf_files: list[Path]
    pdf_count: int
    if pdf_path.is_dir():
        pdf_files = list(pdf_path.glob("*.pdf")) + list(pdf_path.glob("*.PDF"))
        pdf_count = len(pdf_files)
    else:
        pdf_count = 1 if pdf_path.suffix.lower() == ".pdf" else 0

    print("=" * 80)
    print("EMBEDDINGS PIPELINE DEMO")
    print("=" * 80)
    print(f"PDF Path: {args.pdf}")
    print(f"  Resolved: {pdf_path.resolve()}")
    print(f"  Type: {'Directory' if pdf_path.is_dir() else 'File'}")
    print(f"  PDF files found: {pdf_count}")
    print(f"Model: {args.model}")
    print(f"Chunk Size: {args.chunk_size}")
    print(f"Project Root: {project_root}")
    print("=" * 80)

    if pdf_count == 0:
        print("\n❌ WARNING: No PDF files found in the specified path")
        print("The pipeline will continue but may not find any documents to process.")

    # ========================================================================
    # STEP 1: INGEST - Load PDF files from local folder
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 1: INGEST PDF FILES")
    print("=" * 80)

    # Handle both file and directory paths
    # IngestLocalOperator expects a directory, so if a file is passed,
    # we need to pass its parent directory and filter by the specific filename
    ingest_path: str
    include_filter: str
    if pdf_path.is_file():
        # For a single file, ingest from parent directory
        ingest_path = str(pdf_path.parent)
        include_filter = "pdf"
        print(f"  Ingesting single file: {pdf_path.name}")
        print(f"  From directory: {ingest_path}")
    else:
        # For a directory, ingest all PDFs from it
        ingest_path = args.pdf
        include_filter = "pdf"
        print(f"  Ingesting all PDFs from directory: {ingest_path}")

    ingest_config: dict[str, Any] = {
        "input_folder": ingest_path,
        "include_filter": include_filter,
        "max_files": 10,
        "store_binary_content": True,
        "force_ingest": True,  # Bypass incremental processing for demo
    }

    try:
        ingest_operator: Any = IngestLocalOperator(ingest_config)
        ingest_tables: list[pa.Table]
        ingest_metadata: dict[str, Any]
        ingest_tables, ingest_metadata = ingest_operator.transform(None)
        ingest_table: pa.Table = ingest_tables[0]

        # If a specific file was requested, filter to only that file
        if pdf_path.is_file() and ingest_table.num_rows > 0:
            # Resolve both paths to handle symlinks (e.g., /tmp -> /private/tmp on macOS)
            target_path: str = str(pdf_path.resolve())
            if "name" in ingest_table.column_names:
                # Filter table to only include the target file
                # Compare resolved paths to handle symlinks
                mask: list[bool] = [
                    str(Path(ingest_table["name"][i].as_py()).resolve()) == target_path
                    for i in range(ingest_table.num_rows)
                ]
                ingest_table = ingest_table.filter(pa.array(mask))
                print(f"  Filtered to target file: {pdf_path.name}")

        print(f"✓ Ingested {ingest_table.num_rows} document(s)")
        print(f"  Columns: {ingest_table.column_names}")
        print(
            f"  Metadata: Processed={ingest_metadata.get('processed_docs', 0)}, "
            f"Failed={ingest_metadata.get('failed_docs_count', 0)}"
        )

        if ingest_table.num_rows == 0:
            print(f"\n❌ No documents found in {args.pdf}")
            print(f"   Expected path: {pdf_path.resolve()}")
            if pdf_path.is_file():
                print("   Note: When passing a file, all PDFs in parent directory are scanned first")
            return 1

        # Show sample document info
        if "name" in ingest_table.column_names:
            print(f"\n  Sample document: {ingest_table['name'][0].as_py()}")

    except Exception as e:
        print(f"\n❌ Ingest failed: {e}")
        logger.error(f"Ingest error: {e}", exc_info=True)
        return 1

    # ========================================================================
    # STEP 2: EXTRACT - Extract content using Docling
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 2: EXTRACT CONTENT WITH DOCLING")
    print("=" * 80)

    extract_config: dict[str, Any] = {
        "doc_column": "content",
        "extract_tables": True,
        "extract_images": False,
    }

    try:
        extract_operator: Any = ExtractDoclingOperator(extract_config)
        extract_tables: list[pa.Table]
        extract_metadata: dict[str, Any]
        extract_tables, extract_metadata = extract_operator.transform(ingest_table)
        extract_table: pa.Table = extract_tables[0]

        print(f"✓ Extracted content from {extract_table.num_rows} document(s)")
        print(f"  Columns: {extract_table.column_names}")
        print(
            f"  Metadata: Processed={extract_metadata.get('processed_docs', 0)}, "
            f"Failed={extract_metadata.get('failed_docs_count', 0)}"
        )

        # Show sample extracted content
        if "content" in extract_table.column_names and extract_table.num_rows > 0:
            content: Any = extract_table["content"][0].as_py()
            if content:
                preview: str = content[:200].replace("\n", " ")
                print(f"\n  Content preview: {preview}...")
                print(f"  Total characters: {len(content)}")

    except Exception as e:
        print(f"\n❌ Extract failed: {e}")
        logger.error(f"Extract error: {e}", exc_info=True)
        return 1

    # ========================================================================
    # STEP 3: CHUNK - Split content into chunks
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 3: CHUNK CONTENT")
    print("=" * 80)

    chunk_config: dict[str, Any] = {
        "doc_column": "content",
        "chunk_size": args.chunk_size,
        "chunk_overlap": 128,
        "retain_original_content": True,
    }

    try:
        chunker_operator: Any = DoclingChunkerOperator(chunk_config)
        chunk_tables: list[pa.Table]
        chunk_metadata: dict[str, Any]
        chunk_tables, chunk_metadata = chunker_operator.transform(extract_table)
        chunk_table: pa.Table = chunk_tables[0]

        print(f"✓ Chunked {chunk_table.num_rows} document(s)")
        print(f"  Columns: {chunk_table.column_names}")
        print(f"  Total chunks: {chunk_metadata.get('total_chunks', 0)}")
        print(
            f"  Metadata: Processed={chunk_metadata.get('processed_docs', 0)}, "
            f"Failed={chunk_metadata.get('failed_docs_count', 0)}"
        )

        # Show sample chunk info
        if "chunked_content" in chunk_table.column_names and chunk_table.num_rows > 0:
            import json

            chunked_content: Any = chunk_table["chunked_content"][0].as_py()
            if chunked_content:
                chunks: list[dict[str, Any]] = json.loads(chunked_content)
                print(f"\n  First document has {len(chunks)} chunks")
                if chunks:
                    first_chunk: dict[str, Any] = chunks[0]
                    preview = first_chunk["chunk"][:150].replace("\n", " ")
                    print(f"  First chunk preview: {preview}...")
                    print(f"  First chunk metadata: {first_chunk.get('metadata', {})}")

    except Exception as e:
        print(f"\n❌ Chunking failed: {e}")
        logger.error(f"Chunking error: {e}", exc_info=True)
        return 1

    # ========================================================================
    # STEP 4: EMBEDDINGS - Generate embeddings with Ollama
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 4: GENERATE EMBEDDINGS")
    print("=" * 80)

    embeddings_config: dict[str, Any] = {
        "embeddings_type": "ollama",
        "embeddings_model_id": args.model,
        "embeddings_column": "embeddings",
        "overlap_ratio": 0.2,
        "doc_column": "content",
    }

    try:
        embeddings_operator: EmbeddingsOperator = EmbeddingsOperator(embeddings_config)
        embeddings_tables: list[pa.Table]
        embeddings_metadata: dict[str, Any]
        embeddings_tables, embeddings_metadata = embeddings_operator.transform(chunk_table)
        embeddings_table: pa.Table = embeddings_tables[0]

        print(f"✓ Generated embeddings for {embeddings_table.num_rows} document(s)")
        print(f"  Columns: {embeddings_table.column_names}")
        print(
            f"  Metadata: Processed={embeddings_metadata.get('processed_docs', 0)}, "
            f"Failed={embeddings_metadata.get('failed_docs_count', 0)}"
        )

        # Show embedding details
        if "embeddings" in embeddings_table.column_names and embeddings_table.num_rows > 0:
            embeddings_data: Any = embeddings_table["embeddings"][0].as_py()
            if embeddings_data:
                # Handle both single embedding and list of embeddings
                if isinstance(embeddings_data, list):
                    if isinstance(embeddings_data[0], list):
                        # List of embeddings (chunked content)
                        print(f"\n  Generated {len(embeddings_data)} embedding vectors")
                        print(f"  Embedding dimensions: {len(embeddings_data[0])}")
                        print(f"  First embedding sample (first 5 values): {embeddings_data[0][:5]}")
                    else:
                        # Single embedding
                        print(f"\n  Embedding dimensions: {len(embeddings_data)}")
                        print(f"  Embedding sample (first 5 values): {embeddings_data[:5]}")

        # Show document hash
        if "doc_id_hash" in embeddings_table.column_names and embeddings_table.num_rows > 0:
            doc_hash: str = embeddings_table["doc_id_hash"][0].as_py()
            print(f"  Document hash: {doc_hash}")

    except Exception as e:
        print(f"\n❌ Embeddings generation failed: {e}")
        logger.error(f"Embeddings error: {e}", exc_info=True)
        return 1

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 80)
    print("PIPELINE SUMMARY")
    print("=" * 80)
    print(f"✓ Ingest:     {ingest_metadata.get('processed_docs', 0)} documents")
    print(f"✓ Extract:    {extract_metadata.get('processed_docs', 0)} documents")
    print(f"✓ Chunk:      {chunk_metadata.get('total_chunks', 0)} chunks")
    print(f"✓ Embeddings: {embeddings_metadata.get('processed_docs', 0)} documents")
    print("=" * 80)
    print("\n✓ Pipeline completed successfully!")
    print(f"\nFinal table shape: {embeddings_table.num_rows} rows x {len(embeddings_table.column_names)} columns")
    print(f"Final columns: {embeddings_table.column_names}")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
