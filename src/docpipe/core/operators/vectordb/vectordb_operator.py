"""
Generic Vector Database Operator
"""

import hashlib
from typing import Any

import pyarrow as pa

from docpipe.core.constants.constants import AttributeDataTypes, DocpipeConstants, ExecutionStatus, Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.core.operators.vectordb.adapters.outbound.factories.vector_store_factory import VectorStoreFactory
from docpipe.core.operators.vectordb.ports.outbound.vector_store import VectorStorePort
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.utils.core.memmap_file_utils import (
    read_embedding_metadata,
    yield_chunks_from_file,
    yield_embeddings_from_memmap_file,
)
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()

# Register adapters lazily to avoid importing optional dependencies
# OpenSearch adapter (always available - no optional dependencies)
try:
    from docpipe.core.operators.vectordb.adapters.outbound.opensearch.adapter import OpenSearchAdapter  # noqa: F401

    logger.debug("OpenSearch adapter registered (eager)")
except ImportError as e:
    logger.warning(f"Failed to register OpenSearch adapter: {e}")

# Milvus adapter (lazy - requires pymilvus)
VectorStoreFactory.register_lazy(
    "milvus", "docpipe.core.operators.vectordb.adapters.outbound.milvus.adapter", "MilvusAdapter"
)
logger.debug("Milvus adapter registered (lazy)")

# Constants
ENGINE_KEY: str = "engine"
ALGORITHM_KEY: str = "algorithm"
SPACE_TYPE_KEY: str = "space_type"
PROVIDER_DEFAULT: str = "opensearch"
ENGINE_PARAMETERS_KEY: str = "engine_parameters"
SCHEMA_TEMPLATE_PATH_KEY: str = "schema_template_path"
DEFAULT_BATCH_SIZE: int = 100
DEFAULT_VECTOR_DIMENSION: int = 384
NUMBER_OF_BATCHES_KEY: str = "number_of_batches"


class VectorDBOperator(AbstractOperator):  # type: ignore[misc]
    """
    Generic vector database operator using hexagonal architecture.

    This operator works with any vector database through the VectorStorePort interface.
    It delegates to provider-specific adapters (OpenSearch, Milvus).
    without being tightly coupled to any specific implementation.

    Supported Vector Databases:
    - opensearch: OpenSearch with multiple KNN engines (faiss, lucene, nmslib)

    To add a new vector database:
    1. Create an adapter class implementing VectorStorePort
    2. Register it using @register_vector_store decorator
    3. The provider will be automatically available
    """

    short_name: str = OperatorConstants.Operators.VECTORDB
    category: OperatorCategory = OperatorCategory.VectorDB
    owner = DocpipeConstants.OWNER_DOCPIPE

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the Vector Database operator with configuration.

        Args:
            config: Configuration dictionary containing:
                - provider: Type of vector database ("opensearch", etc.)
                - Provider-specific configuration parameters
        """
        super().__init__(config)

        # Get vector database type
        self.provider: str = config.get(OperatorConstants.Config.PROVIDER, PROVIDER_DEFAULT)

        # Extract common configuration
        self.doc_id_column: str = config.get(
            OperatorConstants.Columns.DOC_ID_COLUMN, OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
        )
        self.create_index: bool = config.get(OperatorConstants.VectorDB.CREATE_INDEX, True)
        self.add_sparse_vector: bool = config.get(
            OperatorConstants.VectorDB.ADD_SPARSE_VECTOR, OperatorConstants.VectorDB.ADD_SPARSE_VECTOR_DEFAULT
        )

        # Initialize adapter using factory
        try:
            # provider_config carries all provider-specific parameters including the
            # resource name. Each adapter is responsible for validating its own required keys.
            adapter_config = self.config.get(OperatorConstants.Config.PROVIDER_CONFIG, {})

            # Validate that provider_config is not empty
            if not adapter_config:
                raise DocpipeException(
                    message=(
                        f"'provider_config' is required but missing or empty for provider '{self.provider}'. "
                        f"Connection parameters and the resource name must be supplied inside 'provider_config'."
                    ),
                    status_code=400,
                    error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
                )

            available_features = self.config.get(OperatorConstants.Config.AVAILABLE_FEATURES, {})
            adapter_config[OperatorConstants.Config.AVAILABLE_FEATURES] = available_features

            # Use user-provided feature_mappings when present; otherwise compute defaults
            # from available_features so _meta.feature_mappings is never stored as [].
            user_mappings: list[dict[str, str]] = self.config.get(OperatorConstants.Config.FEATURE_MAPPINGS, [])
            if not user_mappings and available_features:
                from docpipe.core.operators.vectordb.metadata_fetcher import compute_default_feature_mappings

                user_mappings = compute_default_feature_mappings(
                    available_features,
                    add_sparse_vector=self.add_sparse_vector,
                    content_column=self.doc_column,
                )
                logger.debug(
                    "No feature_mappings provided — computed defaults from available_features for provider '%s'",
                    self.provider,
                )
            # Store canonical list-of-dicts back into config so validation sees one shape
            self.config[OperatorConstants.Config.FEATURE_MAPPINGS] = user_mappings
            adapter_config[OperatorConstants.Config.FEATURE_MAPPINGS] = user_mappings
            # Add sparse vector configuration if present (Milvus-specific)
            if OperatorConstants.VectorDB.ADD_SPARSE_VECTOR in self.config:
                adapter_config[OperatorConstants.VectorDB.ADD_SPARSE_VECTOR] = self.config[
                    OperatorConstants.VectorDB.ADD_SPARSE_VECTOR
                ]

            # Pass schema_template_path if provided (operator-level config)
            schema_template_path = self.config.get(SCHEMA_TEMPLATE_PATH_KEY)
            if schema_template_path:
                adapter_config[SCHEMA_TEMPLATE_PATH_KEY] = schema_template_path

            self.adapter: VectorStorePort = VectorStoreFactory.create(self.provider, **adapter_config)
        except Exception as e:
            raise DocpipeException(
                message=f"Failed to initialize vector database adapter '{self.provider}': {e!s}",
                status_code=500,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            ) from e

        logger.info(
            "Initialized VectorDBOperator with adapter: %s",
            self.provider,
            extra=self.common_log_arguments,
        )

    def validate(self, errors: list[str], warnings: list[str], available_features: list[str]) -> None:
        """
        Validate operator configuration.
        Args:
            errors: List to append validation errors
            warnings: List to append validation warnings
            available_features: List of available features from previous operators
        """
        super().validate(errors=errors, warnings=warnings, available_features=available_features)

        # Validate that every mandatory_for_vector_db feature has a feature mapping.
        # Mirrors enterprise validate_mandatory_feature_mappings(): a VectorDB write
        # will fail at runtime if a mandatory feature has no mapped column.
        feature_mappings: list[dict[str, str]] = self.config.get(OperatorConstants.Config.FEATURE_MAPPINGS, [])
        op_available_features: dict = self.config.get(OperatorConstants.Config.AVAILABLE_FEATURES, {})
        if feature_mappings and op_available_features:
            mapped_feature_names: set[str] = {
                entry["feature_name"] for entry in feature_mappings if "feature_name" in entry
            }
            mandatory_missing = [
                name
                for name, meta in op_available_features.items()
                if meta.get(OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB, False)
                and name not in mapped_feature_names
            ]
            if mandatory_missing:
                errors.append("Mappings are missing for mandatory features: " + ", ".join(sorted(mandatory_missing)))

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Transform the input table by indexing documents in the vector database.
        Supports batch processing with size limits and detailed error tracking.
        Handles both single embeddings and chunked embeddings (list of embeddings).
        Auto-detects vector dimension from embeddings data.

        Metrics:
        Document-level metrics:
        - processed_docs: Count of documents successfully processed (all chunks indexed)
        - failed_docs_count: Count of documents that failed (preparation or any chunk failure)

        Chunk-level metrics:
        - chunks_indexed_successfully: Count of chunks successfully indexed
        - chunks_failed_to_index: Count of chunks that failed to index
        - total_chunks_to_index: Total count of chunks prepared for indexing

        Important: If ANY chunk of a document fails to index, the entire document is marked as failed.
        """
        # Count unique documents (not chunks) for accurate documents_in_scope
        # Also build mapping from doc_id_hash to original id for failure tracking
        unique_doc_ids: set[str] = set()
        doc_hash_to_id: dict[str, str] = {}
        id_column = OperatorConstants.Misc.ID

        if self.doc_id_column and self.doc_id_column in table.column_names:
            for idx in range(table.num_rows):
                doc_hash = table[self.doc_id_column][idx].as_py()
                if doc_hash:
                    unique_doc_ids.add(str(doc_hash))
                    # Build mapping from doc_id_hash to original id
                    if id_column in table.column_names:
                        original_id = table[id_column][idx].as_py()
                        if original_id:
                            doc_hash_to_id[str(doc_hash)] = str(original_id)
        total_unique_docs = len(unique_doc_ids) if unique_doc_ids else table.num_rows

        # Initialize metadata
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=total_unique_docs)
        metadata[NUMBER_OF_BATCHES_KEY] = 0

        if table.num_rows == 0:
            logger.warning("Empty table provided", extra=self.common_log_arguments)
            return [table], metadata

        # Validate required doc_id column
        if self.doc_id_column not in table.column_names:
            missing_doc_id_msg: str = f"Required column '{self.doc_id_column}' not found in table"
            logger.error(missing_doc_id_msg, extra=self.common_log_arguments)
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.FAILED.value
            return [table], metadata

        # Identify all DENSE vector columns from available_features
        vector_columns = [
            col_name
            for col_name, feature_config in self.config.get(OperatorConstants.Config.AVAILABLE_FEATURES, {}).items()
            if feature_config.get("type") == "vector" and feature_config.get("available_for_vector_db", False)
        ]

        # Handle sparse vector mode
        if self.add_sparse_vector:
            # Sparse mode: dense embeddings are optional
            if not vector_columns:
                logger.info("Pure sparse vector mode: no dense embeddings, using BM25 only")
                dimension_mapping = {}  # No dense vectors to detect
            else:
                # Dual mode: detect dimensions for dense vectors
                dimension_mapping = self.adapter.detect_all_vector_dimensions(table, vector_columns=vector_columns)
                logger.info(
                    f"Sparse + dense mode: detected dimensions for {len(vector_columns)} column(s): {dimension_mapping}",
                    extra=self.common_log_arguments,
                )
        else:
            # Dense-only mode: at least one dense vector column required
            if not vector_columns:
                error_msg = "No vector columns found in available_features. Cannot proceed without embeddings."
                logger.error(error_msg, extra=self.common_log_arguments)
                metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.FAILED.value
                return [table], metadata

            logger.info(
                f"Detecting dimensions for {len(vector_columns)} vector column(s): {vector_columns}",
                extra=self.common_log_arguments,
            )

            # Auto-detect dimensions for all vector columns
            dimension_mapping = self.adapter.detect_all_vector_dimensions(table, vector_columns=vector_columns)

            if not dimension_mapping:
                error_msg = f"Failed to auto-detect dimensions for vector columns: {vector_columns}"
                logger.error(error_msg, extra=self.common_log_arguments)
                metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.FAILED.value
                return [table], metadata

            logger.info(f"Auto-detected dimensions: {dimension_mapping}", extra=self.common_log_arguments)

        # Create index if needed
        if self.create_index:
            try:
                if self.adapter.index_exists():
                    logger.info(
                        "Resource already exists, validating schema",
                        extra=self.common_log_arguments,
                    )
                    self.adapter.validate_existing_schema(dimension_mapping=dimension_mapping)
                else:
                    self.adapter.create_index(dimension_mapping=dimension_mapping)
            except Exception as e:
                logger.error(f"Failed to create or validate index: {e!s}", extra=self.common_log_arguments)
                # Mark all unique documents as failed when index creation fails
                # Use original document IDs (from 'id' column) for consistency
                for doc_hash in unique_doc_ids:
                    original_id = doc_hash_to_id.get(doc_hash, doc_hash)
                    self.record_failed_document(
                        metadata=metadata,
                        doc_id=original_id,
                        doc_name=original_id,
                        reason=f"Failed to create index: {e!s}",
                    )
                metadata[Metrics.External.PROCESSED_DOCS] = 0
                metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.FAILED.value
                return [table], metadata

        # Prepare documents for bulk indexing
        documents: list[tuple[str, dict[str, Any]]] = []
        # Map chunk IDs back to original document IDs for failure tracking
        chunk_id_to_doc_id: dict[str, str] = {}

        for idx in range(table.num_rows):
            try:
                # Extract row data
                row_data: dict[str, Any] = {}
                for col_name in table.column_names:
                    value: Any = table[col_name][idx].as_py()
                    row_data[col_name] = value

                # Get document ID
                row_doc_id: Any = row_data.get(self.doc_id_column)
                if not row_doc_id:
                    logger.warning(
                        f"Missing document ID at row {idx}",
                        extra=self.common_log_arguments,
                    )
                    self.record_skipped_document(
                        metadata=metadata,
                        doc_id=f"row_{idx}",
                        doc_name=f"row_{idx}",
                        reason="Missing document ID",
                    )
                    continue

                doc_id: str = str(row_doc_id)

                # Check if we have chunked content
                chunked_content_value: Any = row_data.get(OperatorConstants.Columns.CHUNKED_CONTENT)

                # Determine if chunked based on chunked_content structure
                is_chunked: bool = False
                chunks_filepath: str | None = None

                if (
                    isinstance(chunked_content_value, dict)
                    and DocpipeConstants.CHUNKS_MEMMAP_FILE in chunked_content_value
                ):
                    # File references for chunks
                    chunks_filepath = chunked_content_value[DocpipeConstants.CHUNKS_MEMMAP_FILE]
                    is_chunked = True
                    logger.debug(
                        f"Detected file references for chunked data - chunks: {chunks_filepath}",
                        extra=self.common_log_arguments,
                    )
                elif isinstance(chunked_content_value, list) and len(chunked_content_value) > 0:
                    # In-memory chunks
                    is_chunked = True
                    logger.debug(
                        f"Detected in-memory chunked content with {len(chunked_content_value)} chunks for doc {doc_id}",
                        extra=self.common_log_arguments,
                    )

                if is_chunked:
                    # Collect embeddings data for all vector columns
                    vector_column_data: dict[str, Any] = {}
                    vector_column_filepaths: dict[str, str] = {}
                    vector_column_generators: dict[str, Any] = {}
                    num_chunks: int | None = None

                    for vec_col in vector_columns:
                        embeddings_value: Any = row_data.get(vec_col)

                        if embeddings_value is None:
                            continue

                        # Check if file reference
                        if (
                            isinstance(embeddings_value, dict)
                            and DocpipeConstants.EMBEDDINGS_MEMMAP_FILE in embeddings_value
                        ):
                            embeddings_filepath = embeddings_value[DocpipeConstants.EMBEDDINGS_MEMMAP_FILE]
                            vector_column_filepaths[vec_col] = embeddings_filepath
                            # Get dimension and create generator
                            dim = read_embedding_metadata(embeddings_filepath)
                            vector_column_generators[vec_col] = yield_embeddings_from_memmap_file(
                                embeddings_filepath, dim
                            )
                        elif isinstance(embeddings_value, list) and len(embeddings_value) > 0:
                            # In-memory embeddings
                            vector_column_data[vec_col] = embeddings_value
                            # Validate chunk count consistency
                            if num_chunks is None:
                                num_chunks = len(embeddings_value)
                            elif num_chunks != len(embeddings_value):
                                raise ValueError(
                                    f"Inconsistent chunk counts for doc {doc_id}: "
                                    f"expected {num_chunks}, got {len(embeddings_value)} for column {vec_col}"
                                )

                    # Process chunks
                    if chunks_filepath and vector_column_filepaths:
                        # File-based streaming for memory efficiency
                        logger.debug(
                            f"Using yield for streaming {len(vector_column_filepaths)} vector columns from files",
                            extra=self.common_log_arguments,
                        )
                        chunks_gen = yield_chunks_from_file(chunks_filepath)

                        # Create list of (column_name, generator) tuples for zip
                        vec_col_names = list(vector_column_generators.keys())
                        vec_gens = [vector_column_generators[col] for col in vec_col_names]

                        # Zip all generators together with chunks
                        for _chunk_idx, chunk_and_embeddings in enumerate(zip(chunks_gen, *vec_gens, strict=True)):
                            chunk_row_data: dict[str, Any] = row_data.copy()

                            # First element is chunk_data, rest are embeddings
                            chunk_data = chunk_and_embeddings[0]
                            chunk_embeddings = chunk_and_embeddings[1:]

                            # Add embeddings from all vector columns
                            for vec_col, chunk_embedding in zip(vec_col_names, chunk_embeddings, strict=True):
                                chunk_row_data[vec_col] = chunk_embedding.tolist()

                            # Parse chunk data (it's a JSON string)
                            import json

                            chunk_dict = json.loads(chunk_data) if isinstance(chunk_data, str) else chunk_data
                            chunk_text: str = chunk_dict.get(OperatorConstants.Columns.CHUNK, "")
                            if chunk_text:
                                # Update the content column with chunk text instead of full document
                                chunk_row_data[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] = chunk_text

                            file_id: str = str(row_data.get(id_column, doc_id))
                            chunk_doc_id: str = VectorDBOperator.generate_composite_pk(
                                file_id=file_id, chunk_content=chunk_text
                            )
                            documents.append((chunk_doc_id, chunk_row_data))
                            # Track mapping from chunk ID to original document ID
                            chunk_id_to_doc_id[chunk_doc_id] = doc_id
                    else:
                        # In-memory processing
                        chunked_content_list: list[dict[str, Any]] = row_data.get(
                            OperatorConstants.Columns.CHUNKED_CONTENT, []
                        )

                        # Determine number of chunks from chunked_content or in-memory embeddings
                        if num_chunks is None:
                            num_chunks = len(chunked_content_list)

                        for chunk_idx in range(num_chunks):
                            chunk_row_data = row_data.copy()

                            # Add embeddings from all vector columns
                            for vec_col, embeddings_list in vector_column_data.items():
                                if chunk_idx < len(embeddings_list):
                                    chunk_row_data[vec_col] = embeddings_list[chunk_idx]

                            # Replace content field with chunk-specific text
                            chunk_text = ""
                            if chunk_idx < len(chunked_content_list):
                                chunk_text = chunked_content_list[chunk_idx].get(OperatorConstants.Columns.CHUNK, "")
                                if chunk_text:
                                    # Update the content column with chunk text instead of full document
                                    chunk_row_data[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] = chunk_text

                            file_id = str(row_data.get(id_column, doc_id))
                            chunk_doc_id = VectorDBOperator.generate_composite_pk(
                                file_id=file_id, chunk_content=chunk_text
                            )
                            documents.append((chunk_doc_id, chunk_row_data))
                            # Track mapping from chunk ID to original document ID
                            chunk_id_to_doc_id[chunk_doc_id] = doc_id
                else:
                    # Non-chunked document - process as-is with all vector columns
                    documents.append((doc_id, row_data))

            except Exception as e:
                logger.error(
                    f"Error preparing document at row {idx}: {e!s}",
                    extra=self.common_log_arguments,
                )
                self.record_failed_document(
                    metadata=metadata,
                    doc_id=f"row_{idx}",
                    doc_name=f"row_{idx}",
                    reason=str(e),
                )

        # Stale PK cleanup — delete chunks from previous runs that are no longer present
        # in this run's document set. This covers both legacy-format PKs and genuinely
        # stale chunks from updated documents. The set difference handles all cases uniformly.
        if documents and unique_doc_ids:
            try:
                # Build the set of new PKs per doc from the prepared documents list
                new_pks_by_doc: dict[str, set[str]] = {}
                for chunk_pk, _ in documents:
                    parent_doc = chunk_id_to_doc_id.get(chunk_pk, chunk_pk)
                    new_pks_by_doc.setdefault(parent_doc, set()).add(chunk_pk)

                # Query existing PKs from the store for all docs in this batch
                existing_pks_by_doc: dict[str, set[str]] = self.adapter.get_chunk_ids_for_documents(
                    list(unique_doc_ids)
                )

                # Compute stale PKs = existing - new (per document)
                stale_pks: list[str] = []
                for doc_id_key, existing_pks in existing_pks_by_doc.items():
                    new_pks = new_pks_by_doc.get(doc_id_key, set())
                    stale_pks.extend(existing_pks - new_pks)

                if stale_pks:
                    logger.info(
                        "Deleting %s stale chunk(s) before insert",
                        len(stale_pks),
                        extra=self.common_log_arguments,
                    )
                    self.adapter.delete_documents_by_ids(stale_pks)

            except Exception as e:
                logger.warning(
                    "Stale PK cleanup failed (insert will proceed): %s",
                    e,
                    extra=self.common_log_arguments,
                )

        # Index documents using adapter
        try:
            success_count, failed_chunks = self.adapter.index_documents(documents)
            metadata[NUMBER_OF_BATCHES_KEY] = len(documents) // 100 + (1 if len(documents) % 100 else 0)

            # Track chunk-level metrics
            total_chunks_to_index = len(documents)
            chunks_failed_to_index = len(failed_chunks)
            chunks_indexed = success_count

            metadata[Metrics.External.TOTAL_CHUNKS_TO_INDEX] = total_chunks_to_index
            metadata[Metrics.External.CHUNKS_INDEXED_SUCCESSFULLY] = chunks_indexed
            metadata[Metrics.External.CHUNKS_FAILED_TO_INDEX] = chunks_failed_to_index

            # Track which original documents had chunk failures
            failed_doc_ids: set[str] = set()

            for failed_chunk in failed_chunks:
                error_info: dict[str, Any] = failed_chunk.get("index", {})
                failed_chunk_id: str = error_info.get("_id", "unknown")
                failure_reason: str = error_info.get("error", {}).get("reason", "Unknown error")

                # Determine original document ID
                original_doc_id = chunk_id_to_doc_id.get(failed_chunk_id, failed_chunk_id)

                # Only track document-level failure if we can determine the original document
                if original_doc_id:
                    failed_doc_ids.add(original_doc_id)
                    logger.warning(
                        f"Chunk indexing failed: {failed_chunk_id} (document: {original_doc_id}) - {failure_reason[:100]}",
                        extra=self.common_log_arguments,
                    )
                else:
                    logger.warning(
                        f"Chunk indexing failed: {failed_chunk_id} - {failure_reason[:100]}",
                        extra=self.common_log_arguments,
                    )

            # Record document-level failures for documents with any chunk failures
            for doc_id in failed_doc_ids:
                self.record_failed_document(
                    metadata=metadata,
                    doc_id=doc_id,
                    doc_name=doc_id,  # We don't have doc_name at this point
                    reason="One or more chunks failed to index",
                )

            # Calculate document-level metrics
            # processed_docs = total documents - (preparation failures + indexing failures)
            total_docs_processed = table.num_rows - metadata.get(Metrics.External.FAILED_DOCS_COUNT, 0)
            metadata[Metrics.External.PROCESSED_DOCS] = total_docs_processed

            logger.info(
                f"VectorDB indexing complete: {total_docs_processed}/{table.num_rows} documents processed, "
                f"{chunks_indexed}/{total_chunks_to_index} chunks indexed successfully",
                extra=self.common_log_arguments,
            )

        except Exception as e:
            logger.error(f"Failed to index documents: {e!s}", extra=self.common_log_arguments)
            # Mark all documents as failed when the entire indexing operation fails
            # Use original document IDs (from 'id' column) for consistency
            unique_doc_hashes_from_chunks: set[str] = set()
            for doc_id, _ in documents:
                original_doc_hash = chunk_id_to_doc_id.get(doc_id, doc_id)
                unique_doc_hashes_from_chunks.add(original_doc_hash)

            for doc_hash in unique_doc_hashes_from_chunks:
                original_id = doc_hash_to_id.get(doc_hash, doc_hash)
                self.record_failed_document(
                    metadata=metadata,
                    doc_id=original_id,
                    doc_name=original_id,
                    reason=f"Indexing operation failed: {e!s}",
                )
            metadata[Metrics.External.PROCESSED_DOCS] = 0
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.FAILED.value
            return [table], metadata

        # Refresh index
        try:
            self.adapter.refresh_index()
        except Exception as e:
            logger.warning(f"Failed to refresh index: {e!s}", extra=self.common_log_arguments)

        return [table], metadata

    def query_by_doc_names(self, doc_names: list[str], fields: list[str] | None = None) -> list[dict[str, Any]]:
        """
        Query documents by their names.

        Args:
            doc_names: List of document names to query
            fields: Optional list of fields to return

        Returns:
            List of matching documents
        """
        return list(self.adapter.query_by_doc_names(doc_names, fields))

    def delete_documents_by_ids(self, doc_ids: list[str]) -> tuple[int, int]:
        """
        Delete documents by their IDs.

        Args:
            doc_ids: List of document IDs to delete

        Returns:
            Tuple of (success_count, failed_count)
        """
        result = self.adapter.delete_documents_by_ids(doc_ids)
        return (int(result[0]), int(result[1]))

    def get_document_count(self) -> int:
        """Get total document count in the index."""
        return int(self.adapter.get_document_count())

    @staticmethod
    def generate_composite_pk(*, file_id: str, chunk_content: str) -> str:
        """Generate a composite primary key from file identity and chunk content.

        The key is unique per file regardless of content, preventing collisions
        between different files with identical content.

        Args:
            file_id: The file identifier (e.g. file path from the id column).
                     Hashed to handle special characters and length constraints.
            chunk_content: The text content of the chunk. Hashed to produce a
                           stable, fixed-length content fingerprint.

        Returns:
            Composite PK string in the format ``{file_hash}_{content_hash}``
            where each hash is the full 128-character SHA3-512 hex digest
            -- unique per (file, chunk content) pair.
        """
        file_hash = hashlib.sha3_512(file_id.encode()).hexdigest()
        content_hash = hashlib.sha3_512(chunk_content.encode()).hexdigest()
        return f"{file_hash}_{content_hash}"

    @staticmethod
    def _get_vectordb_provider_schemas() -> dict[str, Any]:
        """Return per-provider JSON Schema dicts for the provider_config field.

        Add a new entry here when registering a new VectorDB adapter.
        """
        from docpipe.core.operators.operator_utils import OperatorUtils
        from docpipe.core.operators.vectordb.adapters.outbound.milvus.config import (
            ADAPTER_NAME as MILVUS_ADAPTER_NAME,
        )
        from docpipe.core.operators.vectordb.adapters.outbound.milvus.config import (
            MilvusConfig,
        )
        from docpipe.core.operators.vectordb.adapters.outbound.opensearch.config import (
            ADAPTER_NAME as OPENSEARCH_ADAPTER_NAME,
        )
        from docpipe.core.operators.vectordb.adapters.outbound.opensearch.config import (
            OpenSearchConfig,
        )

        return {
            OPENSEARCH_ADAPTER_NAME: OperatorUtils.model_schema_to_docpipe(schema=OpenSearchConfig.model_json_schema()),
            MILVUS_ADAPTER_NAME: OperatorUtils.model_schema_to_docpipe(schema=MilvusConfig.model_json_schema()),
        }

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """Get metadata about the operator including features and attributes.

        This metadata describes the generic vector database operator interface.
        Provider-specific parameters should be passed via the 'provider_config' configuration.
        """
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: VectorDBOperator.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: VectorDBOperator.is_available(),
            OperatorConstants.Misc.LABEL: "Vector Database",
            OperatorConstants.Config.DESCRIPTION: "Store documents and embeddings in vector databases for similarity search. Supports OpenSearch and Milvus through adapters.",
            OperatorConstants.Config.FEATURES: {
                OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: {
                    OperatorConstants.Misc.NAME: "Document ID",
                    OperatorConstants.Config.DESCRIPTION: "Unique identifier for the document",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TYPE: "string",
                    OperatorConstants.Misc.IS_PRIMARY: True,
                    OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY, OperatorConstants.Misc.PRIMARY],
                },
                OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT: {
                    OperatorConstants.Misc.NAME: "Embeddings",
                    OperatorConstants.Config.DESCRIPTION: "Dense vector embeddings for similarity search",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TYPE: "vector",
                    OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY],
                },
                OperatorConstants.Columns.SPARSE_EMBEDDINGS_COLUMN_DEFAULT: {
                    OperatorConstants.Misc.NAME: "Sparse Embeddings",
                    OperatorConstants.Config.DESCRIPTION: "Sparse vector embeddings for hybrid search",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_VECTOR_SPARSE,
                    OperatorConstants.Misc.TAGS: [],
                },
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: {
                    OperatorConstants.Misc.NAME: "Document Content",
                    OperatorConstants.Config.DESCRIPTION: "The text content of the document",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                    OperatorConstants.Misc.TAGS: [],
                },
            },
            OperatorConstants.Config.ATTRIBUTES: {
                OperatorConstants.Config.PROVIDER: {
                    OperatorConstants.Misc.NAME: "Vector Database Provider",
                    OperatorConstants.Config.DESCRIPTION: "Type of vector database provider. Supported values: opensearch, milvus.",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: PROVIDER_DEFAULT,
                    OperatorConstants.Config.VALID_VALUES: VectorStoreFactory.list_adapters(),
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Columns.DOC_ID_COLUMN: {
                    OperatorConstants.Misc.NAME: "Document ID Column",
                    OperatorConstants.Config.DESCRIPTION: "Column containing document IDs",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Columns.DOC_ID_HASH_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Columns.EMBEDDINGS_COLUMN: {
                    OperatorConstants.Misc.NAME: "Embeddings Column",
                    OperatorConstants.Config.DESCRIPTION: "Column containing dense vector embeddings",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Columns.SPARSE_EMBEDDINGS_COLUMN: {
                    OperatorConstants.Misc.NAME: "Sparse Embeddings Column",
                    OperatorConstants.Config.DESCRIPTION: "Column containing sparse vector embeddings for hybrid search",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.VectorDB.CREATE_INDEX: {
                    OperatorConstants.Misc.NAME: "Create Index",
                    OperatorConstants.Config.DESCRIPTION: "Create index if it doesn't exist",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.VectorDB.VECTOR_DIMENSION: {
                    OperatorConstants.Misc.NAME: "Vector Dimension",
                    OperatorConstants.Config.DESCRIPTION: "Dimension of dense vector embeddings (auto-detected from data if not specified)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: DEFAULT_VECTOR_DIMENSION,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                OperatorConstants.Config.BATCH_SIZE: {
                    OperatorConstants.Misc.NAME: "Batch Size",
                    OperatorConstants.Config.DESCRIPTION: "Number of documents to index in each batch",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: DEFAULT_BATCH_SIZE,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                OperatorConstants.Config.PROVIDER_CONFIG: {
                    OperatorConstants.Misc.NAME: "Provider-Specific Parameters",
                    OperatorConstants.Config.DESCRIPTION: (
                        "Provider-specific configuration parameters (JSON object). "
                        "Must include the resource name key required by the target backend "
                        "(e.g. index_name, collection_name, table_name). "
                        "Also accepts all connection and index parameters specific to the provider."
                    ),
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                    OperatorConstants.Config.PROVIDERS: VectorDBOperator._get_vectordb_provider_schemas(),
                },
            },
        }
