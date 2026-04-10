#!/usr/bin/env python3
"""
OpenSearch Operator
High-level orchestrator that delegates to specialized components.
Maintains backward compatibility with the original OpenSearchOperator interface.
"""

from typing import Any

import pyarrow as pa

from common.constants.constants import AttributeDataTypes, Metrics
from common.constants.operator_constants import OperatorConstants
from common.exceptions.datasift_exceptions import DatasiftException
from common.exceptions.error_codes import ErrorCode
from common.util.infrastructure.logging import get_logger
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.vectordb.opensearch_batch_processor import OpenSearchBatchProcessor
from core.operators.vectordb.opensearch_client import OpenSearchClient
from core.operators.vectordb.opensearch_index_manager import (
    OpenSearchAlgorithmTypes,
    OpenSearchEngineTypes,
    OpenSearchIndexManager,
    VectorSimilarityTypes,
)

logger = get_logger()

# Constants for keys not yet in OperatorConstants
ENGINE_KEY: str = "engine"
ALGORITHM_KEY: str = "algorithm"
SPACE_TYPE_KEY: str = "space_type"
ENGINE_PARAMETERS_KEY: str = "engine_parameters"
SPARSE_EMBEDDINGS_COLUMN_KEY: str = "sparse_embeddings_column"
DEFAULT_BATCH_SIZE: int = 100
DEFAULT_VECTOR_DIMENSION: int = 384
NUMBER_OF_BATCHES_KEY: str = "number_of_batches"


class OpenSearchOperator(AbstractOperator):
    """
    Refactored OpenSearch operator that delegates responsibilities to specialized components.

    This operator acts as a high-level orchestrator, maintaining the same interface
    as the original implementation while delegating to:
    - OpenSearchClient: Connection management
    - OpenSearchIndexManager: Index operations
    - OpenSearchBatchProcessor: Bulk operations
    """

    short_name: str = OperatorConstants.Operators.OPENSEARCH
    category: OperatorCategory = OperatorCategory.VectorDB

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the OpenSearch operator with configuration.

        Args:
            config: Configuration dictionary containing connection, index, and engine settings
        """
        super().__init__(config)

        # Extract configuration parameters
        host: str | None = config.get(OperatorConstants.VectorDB.OPENSEARCH_HOST)
        port: int = config.get(OperatorConstants.VectorDB.OPENSEARCH_PORT, 9200)
        username: str | None = config.get(OperatorConstants.VectorDB.OPENSEARCH_USERNAME)
        password: str | None = config.get(OperatorConstants.VectorDB.OPENSEARCH_PASSWORD)
        use_ssl: bool = config.get(OperatorConstants.VectorDB.OPENSEARCH_USE_SSL, True)
        verify_certs: bool = config.get(OperatorConstants.VectorDB.OPENSEARCH_VERIFY_CERTS, True)
        aws_auth: bool = config.get(OperatorConstants.VectorDB.OPENSEARCH_AWS_AUTH, False)
        aws_region: str | None = config.get(OperatorConstants.VectorDB.OPENSEARCH_AWS_REGION)

        # Index configuration
        self.index_name: str | None = config.get(OperatorConstants.VectorDB.INDEX_NAME)
        self.doc_id_column: str = config.get(
            OperatorConstants.Columns.DOC_ID_COLUMN, OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
        )
        self.embeddings_column: str = config.get(
            OperatorConstants.Columns.EMBEDDINGS_COLUMN,
            OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT,
        )
        self.sparse_embeddings_column: str | None = config.get(SPARSE_EMBEDDINGS_COLUMN_KEY)
        self.feature_mappings: dict[str, str] = config.get(OperatorConstants.Config.FEATURE_MAPPINGS, {})
        self.available_features: dict[str, Any] = config.get(OperatorConstants.Config.AVAILABLE_FEATURES, {})
        self.batch_size: int = config.get(OperatorConstants.Config.BATCH_SIZE, DEFAULT_BATCH_SIZE)
        self.create_index: bool = config.get(OperatorConstants.VectorDB.CREATE_INDEX, True)
        self.index_settings: dict[str, Any] | None = config.get(OperatorConstants.VectorDB.INDEX_SETTINGS)
        self.config_vector_dimension: int = config.get(
            OperatorConstants.VectorDB.VECTOR_DIMENSION, DEFAULT_VECTOR_DIMENSION
        )

        # Engine and algorithm configuration
        self.engine: str = config.get(ENGINE_KEY, OpenSearchEngineTypes.FAISS)
        self.algorithm: str = config.get(ALGORITHM_KEY, OpenSearchAlgorithmTypes.HNSW)
        self.space_type: str = config.get(SPACE_TYPE_KEY, VectorSimilarityTypes.L2)
        self.engine_parameters: dict[str, Any] = config.get(ENGINE_PARAMETERS_KEY, {})

        # Validate required parameters
        if not host:
            raise DatasiftException(
                message="opensearch_host is required",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )
        if not self.index_name:
            raise DatasiftException(
                message="index_name is required", status_code=400, error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID
            )

        # Initialize components
        self.client_manager = OpenSearchClient(
            host=host,
            port=port,
            username=username,
            password=password,
            use_ssl=use_ssl,
            verify_certs=verify_certs,
            aws_auth=aws_auth,
            aws_region=aws_region,
        )

        # Get the OpenSearch client
        client = self.client_manager.get_client()

        # Initialize index manager (will be updated with detected dimension later)
        self.index_manager = OpenSearchIndexManager(
            client=client,
            index_name=self.index_name,
            engine=self.engine,
            algorithm=self.algorithm,
            space_type=self.space_type,
            vector_dimension=self.config_vector_dimension,
            engine_parameters=self.engine_parameters,
            index_settings=self.index_settings,
            available_features=self.available_features,
            feature_mappings=self.feature_mappings,
            embeddings_column=self.embeddings_column,
        )

        # Initialize batch processor
        self.batch_processor = OpenSearchBatchProcessor(
            client=client,
            index_name=self.index_name,
            batch_size=self.batch_size,
            available_features=self.available_features,
            feature_mappings=self.feature_mappings,
        )

        # Get OpenSearch version
        self.os_version: tuple[int, int, int] = self.client_manager.get_version()

        logger.info(
            f"Initialized OpenSearch operator for index: {self.index_name} "
            f"(engine: {self.engine}, algorithm: {self.algorithm}, version: {self.os_version})",
            extra=self.common_log_arguments,
        )

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Transform the input table by indexing documents in OpenSearch.
        Supports batch processing with size limits and detailed error tracking.
        Handles both single embeddings and chunked embeddings (list of embeddings).
        Auto-detects vector dimension from embeddings data.
        """
        # Initialize metadata
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=table.num_rows)
        metadata[NUMBER_OF_BATCHES_KEY] = 0

        if table.num_rows == 0:
            logger.warning("Empty table provided", extra=self.common_log_arguments)
            return [table], metadata

        # Validate required columns
        if self.doc_id_column not in table.column_names:
            missing_doc_id_error: str = f"Required column '{self.doc_id_column}' not found in table"
            logger.error(missing_doc_id_error, extra=self.common_log_arguments)
            metadata[Metrics.External.NODE_STATUS] = "failed"
            return [table], metadata

        if self.embeddings_column not in table.column_names:
            missing_embeddings_error: str = f"Required column '{self.embeddings_column}' not found in table"
            logger.error(missing_embeddings_error, extra=self.common_log_arguments)
            metadata[Metrics.External.NODE_STATUS] = "failed"
            return [table], metadata

        # Auto-detect vector dimension from embeddings data
        detected_dimension: int | None = self.index_manager.detect_vector_dimension(table)
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
            # Update index manager with detected dimension
            self.index_manager.vector_dimension = detected_dimension
        else:
            logger.info(
                f"Could not auto-detect dimension, using config value: {self.config_vector_dimension}",
                extra=self.common_log_arguments,
            )

        # Create index if needed
        if self.create_index:
            try:
                self.index_manager.create_index()
            except Exception as e:
                logger.error(f"Failed to create index: {e!s}", extra=self.common_log_arguments)
                metadata[Metrics.External.NODE_STATUS] = "failed"
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
                doc_id: str | None = row_data.get(self.doc_id_column)
                if not doc_id:
                    logger.warning(
                        f"Missing document ID at row {idx}",
                        extra=self.common_log_arguments,
                    )
                    self.record_skipped_document(
                        metadata=metadata,
                        doc_id=f"row_{idx}",
                        doc_name=f"row_{idx}",
                        reason=f"Missing {self.doc_id_column}",
                    )
                    continue

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
                    # Create separate documents for each chunk
                    for chunk_idx, chunk_embedding in enumerate(embeddings_value):
                        chunk_row_data: dict[str, Any] = row_data.copy()
                        chunk_row_data[self.embeddings_column] = chunk_embedding
                        chunk_doc_id: str = f"{doc_id}_chunk_{chunk_idx}"

                        prepared_chunk_doc: dict[str, Any] = self.batch_processor.prepare_document(chunk_row_data)
                        documents.append((chunk_doc_id, prepared_chunk_doc))
                else:
                    # Single embedding - process as before
                    prepared_doc: dict[str, Any] = self.batch_processor.prepare_document(row_data)
                    documents.append((doc_id, prepared_doc))

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

        # Create batches and process
        all_actions: list[list[dict[str, Any]]] = self.batch_processor.create_batches(documents)
        metadata[NUMBER_OF_BATCHES_KEY] = len(all_actions)

        # Process batches
        success_count: int
        failed_items: list[dict[str, Any]]
        success_count, failed_items = self.batch_processor.process_batches(all_actions)

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
            f"Successfully indexed {success_count} documents in {len(all_actions)} batches",
            extra=self.common_log_arguments,
        )

        # Refresh index
        self.index_manager.refresh_index()

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
        return self.batch_processor.query_by_doc_names(doc_names, fields)

    def delete_documents_by_ids(self, doc_ids: list[str]) -> tuple[int, int]:
        """
        Delete documents by their IDs.

        Args:
            doc_ids: List of document IDs to delete

        Returns:
            Tuple of (success_count, failed_count)
        """
        return self.batch_processor.delete_documents_by_ids(doc_ids)

    def get_document_count(self) -> int:
        """Get total document count in the index."""
        return self.batch_processor.get_document_count()

    def get_metadata(self) -> dict[str, Any]:
        """Get metadata about the operator including features and attributes."""
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: OperatorCategory.VectorDB,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: True,
            OperatorConstants.Misc.LABEL: "OpenSearch",
            OperatorConstants.Config.DESCRIPTION: "Store documents and embeddings in OpenSearch for vector similarity search with multiple engine support",
            OperatorConstants.Config.FEATURES: {
                OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: {
                    OperatorConstants.Misc.NAME: "Document ID",
                    OperatorConstants.Config.DESCRIPTION: "Unique identifier for the document",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                    OperatorConstants.Misc.IS_PRIMARY: True,
                    OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY, OperatorConstants.Misc.PRIMARY],
                },
                OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT: {
                    OperatorConstants.Misc.NAME: "Embeddings",
                    OperatorConstants.Config.DESCRIPTION: "Dense vector embeddings for similarity search",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_VECTOR,
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
                OperatorConstants.VectorDB.OPENSEARCH_HOST: {
                    OperatorConstants.Misc.NAME: "OpenSearch Host",
                    OperatorConstants.Config.DESCRIPTION: "OpenSearch server host address",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.VectorDB.OPENSEARCH_PORT: {
                    OperatorConstants.Misc.NAME: "OpenSearch Port",
                    OperatorConstants.Config.DESCRIPTION: "OpenSearch server port",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: 9200,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                OperatorConstants.VectorDB.OPENSEARCH_USERNAME: {
                    OperatorConstants.Misc.NAME: "Username",
                    OperatorConstants.Config.DESCRIPTION: "Username for OpenSearch authentication",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.VectorDB.OPENSEARCH_PASSWORD: {
                    OperatorConstants.Misc.NAME: "Password",
                    OperatorConstants.Config.DESCRIPTION: "Password for OpenSearch authentication",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.VectorDB.OPENSEARCH_USE_SSL: {
                    OperatorConstants.Misc.NAME: "Use SSL",
                    OperatorConstants.Config.DESCRIPTION: "Use SSL/TLS for connection",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.VectorDB.OPENSEARCH_VERIFY_CERTS: {
                    OperatorConstants.Misc.NAME: "Verify Certificates",
                    OperatorConstants.Config.DESCRIPTION: "Verify SSL certificates",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.VectorDB.OPENSEARCH_AWS_AUTH: {
                    OperatorConstants.Misc.NAME: "AWS Authentication",
                    OperatorConstants.Config.DESCRIPTION: "Use AWS IAM authentication",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.VectorDB.OPENSEARCH_AWS_REGION: {
                    OperatorConstants.Misc.NAME: "AWS Region",
                    OperatorConstants.Config.DESCRIPTION: "AWS region for IAM authentication",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.VectorDB.INDEX_NAME: {
                    OperatorConstants.Misc.NAME: "Index Name",
                    OperatorConstants.Config.DESCRIPTION: "Name of the OpenSearch index",
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
                OperatorConstants.VectorDB.INDEX_SETTINGS: {
                    OperatorConstants.Misc.NAME: "Index Settings",
                    OperatorConstants.Config.DESCRIPTION: "Custom OpenSearch index settings (JSON object)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                ENGINE_KEY: {
                    OperatorConstants.Misc.NAME: "KNN Engine",
                    OperatorConstants.Config.DESCRIPTION: "KNN engine type (faiss, lucene, nmslib, jvector)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OpenSearchEngineTypes.FAISS,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.ENUM,
                    OperatorConstants.Config.VALID_VALUES: OpenSearchEngineTypes.ALL_ENGINES,
                },
                ALGORITHM_KEY: {
                    OperatorConstants.Misc.NAME: "KNN Algorithm",
                    OperatorConstants.Config.DESCRIPTION: "KNN algorithm type (hnsw, ivf)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OpenSearchAlgorithmTypes.HNSW,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.ENUM,
                    OperatorConstants.Config.VALID_VALUES: OpenSearchAlgorithmTypes.ALL_ALGORITHMS,
                },
                SPACE_TYPE_KEY: {
                    OperatorConstants.Misc.NAME: "Space Type",
                    OperatorConstants.Config.DESCRIPTION: "Vector similarity metric (l2, cosine, inner_product)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: VectorSimilarityTypes.L2,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.ENUM,
                    OperatorConstants.Config.VALID_VALUES: VectorSimilarityTypes.ALL_TYPES,
                },
                OperatorConstants.VectorDB.VECTOR_DIMENSION: {
                    OperatorConstants.Misc.NAME: "Vector Dimension",
                    OperatorConstants.Config.DESCRIPTION: "Dimension of dense vector embeddings (auto-detected from data if not specified)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: DEFAULT_VECTOR_DIMENSION,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                ENGINE_PARAMETERS_KEY: {
                    OperatorConstants.Misc.NAME: "Engine Parameters",
                    OperatorConstants.Config.DESCRIPTION: "Custom engine-specific parameters (JSON object, e.g., {'ef_construction': 128, 'm': 24} for HNSW)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                OperatorConstants.Config.BATCH_SIZE: {
                    OperatorConstants.Misc.NAME: "Batch Size",
                    OperatorConstants.Config.DESCRIPTION: "Number of documents to index in each batch",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: DEFAULT_BATCH_SIZE,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                OperatorConstants.Config.FEATURE_MAPPINGS: {
                    OperatorConstants.Misc.NAME: "Feature Mappings",
                    OperatorConstants.Config.DESCRIPTION: "Map feature names to OpenSearch field names (JSON object)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                OperatorConstants.Config.AVAILABLE_FEATURES: {
                    OperatorConstants.Misc.NAME: "Available Features",
                    OperatorConstants.Config.DESCRIPTION: "Feature definitions for schema mapping (JSON object)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
            },
        }
