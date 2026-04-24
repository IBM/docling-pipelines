"""
Generic Vector Database Operator
"""

from typing import Any

import pyarrow as pa

# Import adapters to trigger registration
import core.operators.vectordb.adapters.outbound  # noqa: F401
from common.constants.constants import AttributeDataTypes, ExecutionStatus, Metrics
from common.constants.operator_constants import OperatorConstants
from common.exceptions.datasift_exceptions import DatasiftException
from common.exceptions.error_codes import ErrorCode
from common.util.infrastructure.logging import get_logger
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.vectordb.adapters.outbound.factories.vector_store_factory import VectorStoreFactory
from core.operators.vectordb.ports.outbound.vector_store import VectorStorePort

logger = get_logger()

# Constants
ENGINE_KEY: str = "engine"
ALGORITHM_KEY: str = "algorithm"
SPACE_TYPE_KEY: str = "space_type"
VECTOR_DB_TYPE_KEY: str = "vector_db_type"
VECTOR_DB_TYPE_DEFAULT: str = "opensearch"
ENGINE_PARAMETERS_KEY: str = "engine_parameters"
SPARSE_EMBEDDINGS_COLUMN_KEY: str = "sparse_embeddings_column"
DEFAULT_BATCH_SIZE: int = 100
DEFAULT_VECTOR_DIMENSION: int = 384
NUMBER_OF_BATCHES_KEY: str = "number_of_batches"


class VectorDBOperator(AbstractOperator):
    """
    Generic vector database operator using hexagonal architecture.

    This operator works with any vector database through the VectorStorePort interface.
    It delegates to provider-specific adapters (OpenSearch, Pinecone, Weaviate, etc.)
    without being tightly coupled to any specific implementation.

    Supported Vector Databases:
    - opensearch: OpenSearch with multiple KNN engines (faiss, lucene, nmslib)

    To add a new vector database:
    1. Create an adapter class implementing VectorStorePort
    2. Register it using @register_vector_store decorator
    3. The provider will be automatically available
    """

    short_name: str = "vectordb"
    category: OperatorCategory = OperatorCategory.VectorDB

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the Vector Database operator with configuration.

        Args:
            config: Configuration dictionary containing:
                - vector_db_type: Type of vector database ("opensearch", etc.)
                - Provider-specific configuration parameters
        """
        super().__init__(config)

        # Get vector database type
        self.vector_db_type: str = config.get(VECTOR_DB_TYPE_KEY, VECTOR_DB_TYPE_DEFAULT)

        # Extract common configuration
        self.index_name: str | None = config.get(OperatorConstants.VectorDB.INDEX_NAME)
        self.doc_id_column: str = config.get(
            OperatorConstants.Columns.DOC_ID_COLUMN, OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
        )
        self.embeddings_column: str = config.get(
            OperatorConstants.Columns.EMBEDDINGS_COLUMN,
            OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT,
        )
        self.create_index: bool = config.get(OperatorConstants.VectorDB.CREATE_INDEX, True)
        self.config_vector_dimension: int = config.get(
            OperatorConstants.VectorDB.VECTOR_DIMENSION, DEFAULT_VECTOR_DIMENSION
        )

        # Initialize adapter using factory
        try:
            # Extract vectordb_parameters (adapter-specific config like host, port, engine, etc.)
            adapter_config = self.config.get(OperatorConstants.VectorDB.VECTORDB_PARAMETERS, {})

            # Add operator-level parameters that the adapter needs
            adapter_config[OperatorConstants.VectorDB.INDEX_NAME] = self.index_name
            adapter_config[OperatorConstants.VectorDB.VECTOR_DIMENSION] = self.config_vector_dimension
            adapter_config[OperatorConstants.Columns.EMBEDDINGS_COLUMN] = self.embeddings_column
            adapter_config[OperatorConstants.Config.AVAILABLE_FEATURES] = self.config.get(
                OperatorConstants.Config.AVAILABLE_FEATURES, {}
            )
            adapter_config[OperatorConstants.Config.FEATURE_MAPPINGS] = self.config.get(
                OperatorConstants.Config.FEATURE_MAPPINGS, {}
            )

            self.adapter: VectorStorePort = VectorStoreFactory.create(self.vector_db_type, **adapter_config)
        except Exception as e:
            raise DatasiftException(
                message=f"Failed to initialize vector database adapter '{self.vector_db_type}': {e!s}",
                status_code=500,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            ) from e

        logger.info(
            f"Initialized VectorDBOperator with adapter: {self.vector_db_type}, index: {self.index_name}",
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

        # Validate index_name
        if self.should_validate_field(field_value=self.index_name):
            if not self.index_name:
                errors.append("index_name is required for VectorDBOperator")

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Transform the input table by indexing documents in the vector database.
        Supports batch processing with size limits and detailed error tracking.
        Handles both single embeddings and chunked embeddings (list of embeddings).
        Auto-detects vector dimension from embeddings data.
        """
        # Initialize metadata
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=table.num_rows)
        metadata["number_of_batches"] = 0

        if table.num_rows == 0:
            logger.warning("Empty table provided", extra=self.common_log_arguments)
            return [table], metadata

        # Validate required columns
        if self.doc_id_column not in table.column_names:
            missing_doc_id_msg: str = f"Required column '{self.doc_id_column}' not found in table"
            logger.error(missing_doc_id_msg, extra=self.common_log_arguments)
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.FAILED.value
            return [table], metadata

        if self.embeddings_column not in table.column_names:
            missing_embeddings_msg: str = f"Required column '{self.embeddings_column}' not found in table"
            logger.error(missing_embeddings_msg, extra=self.common_log_arguments)
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.FAILED.value
            return [table], metadata

        # Auto-detect vector dimension from embeddings data
        detected_dimension: int | None = self.adapter.detect_vector_dimension(table)
        if detected_dimension is not None:
            if detected_dimension != self.config_vector_dimension:
                logger.info(
                    f"Using auto-detected vector dimension: {detected_dimension} "
                    f"(config specified: {self.config_vector_dimension})",
                    extra=self.common_log_arguments,
                )
            else:
                logger.info(
                    f"Auto-detected vector dimension matches config: {detected_dimension}",
                    extra=self.common_log_arguments,
                )
            dimension_to_use = detected_dimension
        else:
            logger.info(
                f"Could not auto-detect dimension, using config value: {self.config_vector_dimension}",
                extra=self.common_log_arguments,
            )
            dimension_to_use = self.config_vector_dimension

        # Create index if needed
        if self.create_index:
            try:
                self.adapter.create_index(dimension_to_use)
            except Exception as e:
                logger.error(f"Failed to create index: {e!s}", extra=self.common_log_arguments)
                metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.FAILED.value
                return [table], metadata

        # Prepare documents for bulk indexing
        documents: list[tuple[str, dict[str, Any]]] = []

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

                # Get embeddings and check if it's a nested list (chunked embeddings)
                embeddings_value: Any = row_data.get(self.embeddings_column)

                # Detect if embeddings is a list of embeddings (chunked content)
                is_chunked: bool = False
                if embeddings_value and isinstance(embeddings_value, list) and len(embeddings_value) > 0:
                    if isinstance(embeddings_value[0], list):
                        if len(embeddings_value[0]) > 0 and isinstance(embeddings_value[0][0], (int, float)):
                            is_chunked = True
                            logger.debug(
                                f"Detected chunked embeddings with {len(embeddings_value)} chunks for doc {doc_id}",
                                extra=self.common_log_arguments,
                            )

                if is_chunked:
                    # Get chunked_content if available
                    chunked_content_list: list[dict[str, Any]] = row_data.get(
                        OperatorConstants.Columns.CHUNKED_CONTENT, []
                    )

                    # Create separate documents for each chunk
                    for chunk_idx, chunk_embedding in enumerate(embeddings_value):
                        chunk_row_data: dict[str, Any] = row_data.copy()
                        chunk_row_data[self.embeddings_column] = chunk_embedding

                        # Replace content field with chunk-specific text
                        if chunk_idx < len(chunked_content_list):
                            chunk_text: str = chunked_content_list[chunk_idx].get(OperatorConstants.Columns.CHUNK, "")
                            if chunk_text:
                                # Update the content column with chunk text instead of full document
                                chunk_row_data[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] = chunk_text

                        chunk_doc_id: str = f"{doc_id}_chunk_{chunk_idx}"
                        documents.append((chunk_doc_id, chunk_row_data))
                else:
                    # Single embedding - process as before
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

        # Index documents using adapter
        try:
            success_count, failed_items = self.adapter.index_documents(documents)
            metadata["number_of_batches"] = len(documents) // 100 + (1 if len(documents) % 100 else 0)

            # Record failed documents
            for item in failed_items:
                error_info: dict[str, Any] = item.get("index", {})
                failed_doc_id: str = error_info.get("_id", "unknown")
                failure_reason: str = error_info.get("error", {}).get("reason", "Unknown error")
                self.record_failed_document(
                    metadata=metadata,
                    doc_id=failed_doc_id,
                    doc_name=failed_doc_id,
                    reason=failure_reason[:100],
                )

            metadata[Metrics.External.PROCESSED_DOCS] = success_count
            logger.info(
                f"Successfully indexed {success_count} documents",
                extra=self.common_log_arguments,
            )

        except Exception as e:
            logger.error(f"Failed to index documents: {e!s}", extra=self.common_log_arguments)
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
        return self.adapter.query_by_doc_names(doc_names, fields)

    def delete_documents_by_ids(self, doc_ids: list[str]) -> tuple[int, int]:
        """
        Delete documents by their IDs.

        Args:
            doc_ids: List of document IDs to delete

        Returns:
            Tuple of (success_count, failed_count)
        """
        return self.adapter.delete_documents_by_ids(doc_ids)

    def get_document_count(self) -> int:
        """Get total document count in the index."""
        return self.adapter.get_document_count()

    def get_metadata(self) -> dict[str, Any]:
        """Get metadata about the operator including features and attributes.

        This metadata describes the generic vector database operator interface.
        Provider-specific parameters should be passed via the 'vectordb_parameters' configuration.
        """
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: OperatorCategory.VectorDB,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: True,
            OperatorConstants.Misc.LABEL: "Vector Database",
            OperatorConstants.Config.DESCRIPTION: "Store documents and embeddings in vector databases for similarity search. Supports multiple providers (OpenSearch, Pinecone, Weaviate, etc.) through adapters.",
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
                VECTOR_DB_TYPE_KEY: {
                    OperatorConstants.Misc.NAME: "Vector Database Type",
                    OperatorConstants.Config.DESCRIPTION: "Type of vector database provider (opensearch, pinecone, weaviate, etc.)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: VECTOR_DB_TYPE_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.VectorDB.HOST: {
                    OperatorConstants.Misc.NAME: "Vector Database Host",
                    OperatorConstants.Config.DESCRIPTION: "Vector database server host address",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.VectorDB.PORT: {
                    OperatorConstants.Misc.NAME: "Vector Database Port",
                    OperatorConstants.Config.DESCRIPTION: "Vector database server port",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: 9200,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                OperatorConstants.VectorDB.USERNAME: {
                    OperatorConstants.Misc.NAME: "Username",
                    OperatorConstants.Config.DESCRIPTION: "Username for database authentication",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.VectorDB.PASSWORD: {
                    OperatorConstants.Misc.NAME: "Password",
                    OperatorConstants.Config.DESCRIPTION: "Password for database authentication",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.VectorDB.USE_SSL: {
                    OperatorConstants.Misc.NAME: "Use SSL",
                    OperatorConstants.Config.DESCRIPTION: "Use SSL/TLS for connection",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.VectorDB.VERIFY_CERTS: {
                    OperatorConstants.Misc.NAME: "Verify Certificates",
                    OperatorConstants.Config.DESCRIPTION: "Verify SSL certificates",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.VectorDB.INDEX_NAME: {
                    OperatorConstants.Misc.NAME: "Index Name",
                    OperatorConstants.Config.DESCRIPTION: "Name of the vector database index/collection",
                    OperatorConstants.Config.REQUIRED: True,
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
                SPARSE_EMBEDDINGS_COLUMN_KEY: {
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
                OperatorConstants.VectorDB.VECTORDB_PARAMETERS: {
                    OperatorConstants.Misc.NAME: "Provider-Specific Parameters",
                    OperatorConstants.Config.DESCRIPTION: "Provider-specific configuration parameters (JSON object). For OpenSearch: engine, algorithm, space_type, engine_parameters, index_settings, aws_auth, aws_region, etc.",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
            },
        }
