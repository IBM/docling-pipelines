"""
Embeddings Operator

This operator generates vector embeddings for text content using various embedding providers.
It supports multiple providers (Ollama, OpenAI, etc.) and handles chunking of long text.
"""

import json
from typing import Any

import numpy as np
import pyarrow as pa

# Import adapters to trigger registration
import datasift.core.operators.functional.embeddings.adapters.outbound  # noqa: F401
from datasift.core.constants.constants import (
    AttributeDataTypes,
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
)
from datasift.core.constants.operator_constants import OperatorConstants
from datasift.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from datasift.core.operators.functional.doc_id_hash import DocIdHashOperator
from datasift.core.operators.functional.embeddings.adapters.outbound.factories.llm_adapter_factory import (
    LLMAdapterFactory,
)
from datasift.core.operators.functional.embeddings.ports.outbound.llm_service import LLMServicePort
from datasift.core.operators.operator_utils import OperatorUtils
from datasift.exceptions.datasift_exceptions import DatasiftException

# Import TransformUtils from centralized location
from datasift.utils.data.transform import TransformUtils
from datasift.utils.infrastructure.logging import get_logger
from datasift.utils.summarization_util import SummarizationUtil

logger = get_logger()

# Supported embeddings providers (for backward compatibility)
SUPPORTED_EMBEDDINGS_TYPES: list[str] = LLMAdapterFactory.list_adapters()

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
    - Multiple embedding providers (Ollama, HuggingFace, LiteLLM)
    - Multiple embedding models per provider
    - Automatic chunking for long text
    - Pre-chunked content processing
    - Document hash generation
    - Error handling per document
    - Batch processing for improved performance

    Supported Providers:
    - ollama: Local Ollama models (nomic-embed-text, llama2, etc.)
    - huggingface: HuggingFace models (all-MiniLM-L6-v2, mpnet-base-v2, etc.)
    - litellm: 100+ providers via LiteLLM (OpenAI, Azure, Anthropic, Cohere, etc.)

    LiteLLM Provider Support:
    Through the litellm provider, you can access embeddings from:
    - OpenAI (text-embedding-3-small, text-embedding-ada-002)
    - Azure OpenAI
    - Cohere (embed-english-v3.0, embed-multilingual-v3.0)
    - Bedrock (amazon.titan-embed-text-v1)
    - Vertex AI (textembedding-gecko)
    - And 100+ more providers

    To add a new provider:
    1. Create a new adapter class implementing LLMServicePort
    2. Register it using @register_llm_adapter decorator
    3. The provider will be automatically available through the factory pattern
    """

    short_name: str = OperatorConstants.Operators.EMBEDDINGS
    category: OperatorCategory = OperatorCategory.Functional
    owner = DatasiftConstants.OWNER_DATASIFT

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

        # Initialize embedding adapter
        self.embedding_adapter: LLMServicePort = self._initialize_embedding_adapter()

        logger.info(
            f"Initialized EmbeddingsOperator with adapter: {self.embeddings_type}, model: {self.embeddings_model_id}",
            extra=self.common_log_arguments,
        )

    def _initialize_embedding_adapter(self) -> LLMServicePort:
        """
        Initialize the appropriate embedding adapter based on embeddings_type.

        This method creates and returns the appropriate adapter using LLMAdapterFactory.
        The adapter is stored as self.embedding_adapter for reuse across multiple
        embedding operations.

        Returns:
            The initialized embedding adapter for the configured adapter type

        Raises:
            DatasiftException: If the adapter is unsupported or initialization fails
        """
        try:
            # Extract adapter_config if present in config
            adapter_config = self.config.get(OperatorConstants.Config.PROVIDER_CONFIG, {})

            # Create adapter using factory
            adapter = LLMAdapterFactory.create(
                adapter_name=self.embeddings_type, model_name=self.embeddings_model_id, **adapter_config
            )

            return adapter
        except Exception as e:
            raise DatasiftException(f"Failed to initialize embedding adapter '{self.embeddings_type}': {e!s}") from e

    @staticmethod
    def get_required_features() -> list[str]:
        """Return list of required input features."""
        return [OperatorConstants.Columns.DOC_COLUMN_DEFAULT]

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

        # Validate provider_config parameters
        provider_config = self.config.get(OperatorConstants.Config.PROVIDER_CONFIG, {})
        if self.should_validate_field(field_value=provider_config) and isinstance(provider_config, dict):
            # Validate max_concurrent_requests if present
            max_concurrent_requests = provider_config.get(OperatorConstants.Config.MAX_CONCURRENT_REQUESTS)
            if max_concurrent_requests is not None and self.should_validate_field(field_value=max_concurrent_requests):
                if not isinstance(max_concurrent_requests, int):
                    errors.append(
                        f"provider_config.max_concurrent_requests must be an integer, got {type(max_concurrent_requests).__name__}"
                    )
                elif max_concurrent_requests <= 0:
                    errors.append(
                        f"provider_config.max_concurrent_requests must be positive, got {max_concurrent_requests}"
                    )

            # Validate batch_size if present
            batch_size = provider_config.get(OperatorConstants.Config.BATCH_SIZE)
            if batch_size is not None and self.should_validate_field(field_value=batch_size):
                if not isinstance(batch_size, int):
                    errors.append(f"provider_config.batch_size must be an integer, got {type(batch_size).__name__}")
                elif batch_size <= 0:
                    errors.append(f"provider_config.batch_size must be positive, got {batch_size}")

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
            OperatorConstants.Config.DESCRIPTION: "Generate vector embeddings using Ollama, HuggingFace, or 100+ providers via LiteLLM (OpenAI, Azure, Cohere, watsonx.ai, etc.)",
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
                    OperatorConstants.Config.DESCRIPTION: "Embedding provider: ollama (local), huggingface (local/remote), litellm (100+ providers including OpenAI, Azure, Cohere)",
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
                OperatorConstants.Config.PROVIDER_CONFIG: {
                    OperatorConstants.Misc.NAME: "Provider Configuration",
                    OperatorConstants.Config.DESCRIPTION: (
                        "Provider-specific configuration parameters. "
                        "Ollama: max_concurrent_requests (int, default: 8) - maximum concurrent requests. "
                        "HuggingFace: batch_size (int, default: 32), use_local (bool), api_token (str), device (str). "
                        "LiteLLM: batch_size (int, default: 32), api_key (str), api_base (str). "
                        "Watsonx: batch_size (int, default: 800), api_key (str), api_base (str), container_kind (str), container_id (str), enable_rate_limiting (bool)."
                    ),
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
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
        Generate embeddings for text using the configured provider with batch processing.

        This method handles chunking of long text based on model token limits
        and generates embeddings using efficient batch processing.

        Args:
            text: List of text strings to embed
            model_name: Name of the model to use
            overlap_ratio: Overlap ratio for chunking (0.0 to 0.5)

        Returns:
            list: List of embedding vectors (one per input text)

        Raises:
            DatasiftException: If embedding generation fails
        """
        # Get token limit from adapter
        token_limit: int = self.embedding_adapter.get_model_token_limit()

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
                # Use batch processing for better performance
                batch_embeddings = self.embedding_adapter.generate_embeddings_batch(texts_to_embed)

                # Map embeddings back to original indices
                for i, embedding in enumerate(batch_embeddings):
                    embeddings_map[text_indices[i]] = embedding

            except Exception as e:
                logger.error(
                    f"Failed to generate batch embeddings: {e!s}",
                    exc_info=True,
                    extra=self.common_log_arguments,
                )
                raise DatasiftException(f"Batch embedding generation failed: {e!s}") from e

        # Process chunked texts
        for idx, chunks in chunked_texts.items():
            try:
                # Generate embeddings for chunks in batch
                chunk_embeddings = self.embedding_adapter.generate_embeddings_batch(chunks)

                # Average the chunk embeddings
                avg_embedding: list[float] = np.mean(chunk_embeddings, axis=0).tolist()
                embeddings_map[idx] = avg_embedding

            except Exception as e:
                logger.error(
                    f"Failed to generate embeddings for chunked text at index {idx}: {e!s}",
                    exc_info=True,
                    extra=self.common_log_arguments,
                )
                raise DatasiftException(f"Embedding generation failed for chunked text: {e!s}") from e

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
        chunked_content_raw: str | list[Any] = table[OperatorConstants.Columns.CHUNKED_CONTENT][idx].as_py()
        if not chunked_content_raw:
            raise DatasiftException("Chunked content is empty")

        # Parse chunked_content - it can be a JSON string or a list
        chunked_content: list[Any] = []
        if isinstance(chunked_content_raw, str):
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
                chunk_text = SummarizationUtil.build_chunk_text_for_embedding(chunk=chunk)
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
            model_name=self.embeddings_model_id,
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

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Transform the input table by adding embeddings using memory-efficient internal slicing.

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
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=OperatorUtils.find_doc_count(table=table))

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
                # Add embeddings
                slice_table = TransformUtils.add_column(
                    table=slice_table, name=self.embeddings_column, content=slice_embeddings
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
