"""Milvus adapter for vector database operations.

This adapter implements the VectorStorePort interface for Milvus.
"""

from typing import Any

import pyarrow as pa

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.vectordb.adapters.outbound.factories.vector_store_factory import register_vector_store
from docpipe.core.operators.vectordb.adapters.outbound.milvus.batch_processor import MilvusBatchProcessor
from docpipe.core.operators.vectordb.adapters.outbound.milvus.client import MilvusClient
from docpipe.core.operators.vectordb.adapters.outbound.milvus.index_manager import MilvusIndexManager
from docpipe.core.operators.vectordb.ports.outbound.vector_store import VectorStorePort
from docpipe.utils.infrastructure.logging import get_logger
from docpipe.utils.operators.vectordb_utils import detect_all_vector_dimensions, detect_vector_dimension

logger = get_logger(__name__)

# Milvus adapter default values
DEFAULT_INDEX_TYPE = "HNSW"
DEFAULT_METRIC_TYPE = "L2"


@register_vector_store
class MilvusAdapter(VectorStorePort):
    """Adapter for Milvus vector database.

    This adapter wraps the Milvus components and provides a unified
    interface for vector database operations. It delegates to:
    - MilvusClient: Connection management
    - MilvusIndexManager: Collection operations
    - MilvusBatchProcessor: Bulk operations

    The adapter pattern allows the VectorDBOperator to work with Milvus
    without being tightly coupled to Milvus-specific implementation details.

    Supports both standalone Milvus and wx.data deployments.
    """

    ADAPTER_NAME = "milvus"
    ADAPTER_DISPLAY_NAME = "Milvus"

    def __init__(self, **adapter_config: Any) -> None:
        """Initialize Milvus adapter.

        All parameters are extracted from adapter_config, which contains the merged
        provider_config and operator-level parameters.

        Args:
            **adapter_config: Configuration dictionary containing:
                Operator-level parameters (added by VectorDBOperator):
                - index_name: Name of the collection (Milvus uses "collection" for data container)
                - vector_dimension: Dimension of vector embeddings
                - embeddings_column: Name of embeddings column
                - available_features: Feature configuration
                - feature_mappings: Column to field mappings

                Provider-specific parameters (from provider_config):
                - host: Milvus server host (default: localhost)
                - port: Milvus server port (default: 19530)
                - uri: Full URI for connection (for wx.data or cloud deployments)
                - token: API token for authentication (for wx.data)
                - username: Username for authentication (optional)
                - password: Password for authentication (optional)
                - database: Database name (default: "default")
                - ssl: Use SSL/TLS connection (optional)
                - ssl_certificate: SSL certificate path (optional)
                - batch_size: Batch size for bulk operations (default: 100)
                - index_type: Vector index algorithm (FLAT, IVF_FLAT, HNSW, etc.)
                - metric_type: Similarity metric (L2, IP, COSINE)
                - index_parameters: Index-specific parameters
        """
        # Extract operator-level parameters (added by VectorDBOperator)
        index_name = adapter_config.get(OperatorConstants.VectorDB.INDEX_NAME)
        self.embeddings_column = adapter_config.get(
            OperatorConstants.Columns.EMBEDDINGS_COLUMN, OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT
        )
        self.vector_dimension = adapter_config.get(
            OperatorConstants.VectorDB.VECTOR_DIMENSION, OperatorConstants.VectorDB.DEFAULT_VECTOR_DIMENSION
        )
        self.add_sparse_vector = adapter_config.get(
            OperatorConstants.VectorDB.ADD_SPARSE_VECTOR, OperatorConstants.VectorDB.ADD_SPARSE_VECTOR_DEFAULT
        )
        available_features = adapter_config.get(OperatorConstants.Config.AVAILABLE_FEATURES, {})
        feature_mappings = adapter_config.get(OperatorConstants.Config.FEATURE_MAPPINGS, {})

        self.collection_name = index_name
        self.primary_key_field = OperatorConstants.VectorDB.DEFAULT_PRIMARY_KEY_FIELD

        # Extract connection parameters from provider_config in adapter_config
        host = adapter_config.get(OperatorConstants.VectorDB.HOST, "localhost")
        port = adapter_config.get(OperatorConstants.VectorDB.PORT, 19530)
        uri = adapter_config.get(OperatorConstants.VectorDB.URI)
        token = adapter_config.get(OperatorConstants.VectorDB.TOKEN)
        username = adapter_config.get(OperatorConstants.VectorDB.USERNAME)
        password = adapter_config.get(OperatorConstants.VectorDB.PASSWORD)
        database = adapter_config.get(OperatorConstants.VectorDB.DATABASE, "default")
        auth_type = adapter_config.get(OperatorConstants.VectorDB.AUTH_TYPE)
        secure = adapter_config.get(OperatorConstants.VectorDB.SECURE, False)
        batch_size = adapter_config.get(OperatorConstants.Config.BATCH_SIZE, 100)

        # Extract Milvus-specific parameters from provider_config in adapter_config
        index_type = adapter_config.get(OperatorConstants.VectorDB.INDEX_TYPE, DEFAULT_INDEX_TYPE)
        metric_type = adapter_config.get(OperatorConstants.VectorDB.METRIC_TYPE, DEFAULT_METRIC_TYPE)
        index_parameters = adapter_config.get(OperatorConstants.VectorDB.INDEX_PARAMETERS, {})

        # Note: Sparse vector mode uses hardcoded index configuration in MilvusIndexManager
        # The index_type and metric_type parameters here are only used for dense vectors
        if self.add_sparse_vector:
            logger.info("Sparse vector mode enabled: using hardcoded SPARSE_INVERTED_INDEX with BM25")

        # Initialize Milvus client
        self.client_manager = MilvusClient(
            host=host,
            port=port,
            uri=uri,
            token=token,
            username=username,
            password=password,
            database=database,
            auth_type=auth_type,
            secure=secure,
        )

        # Get the Milvus client
        client = self.client_manager.get_client()

        # Initialize index manager
        self.index_manager = MilvusIndexManager(
            client=client,
            collection_name=self.collection_name or "",
            index_type=index_type,
            metric_type=metric_type,
            index_parameters=index_parameters,
            available_features=available_features,
            feature_mappings=feature_mappings,
            primary_key_field=self.primary_key_field,
            auto_id=False,
            add_sparse_vector=self.add_sparse_vector,
        )

        # Initialize batch processor
        self.batch_processor = MilvusBatchProcessor(
            client=client,
            collection_name=self.collection_name or "",
            batch_size=batch_size,
            available_features=available_features,
            feature_mappings=feature_mappings,
            primary_key_field=self.primary_key_field,
            embeddings_column=self.embeddings_column,
            add_sparse_vector=self.add_sparse_vector,
        )

        logger.info(
            f"Initialized MilvusAdapter for collection: {self.collection_name} "
            f"(index: {index_type}, metric: {metric_type})"
        )

    def index_documents(self, documents: list[tuple[str, dict[str, Any]]]) -> tuple[int, list[dict[str, Any]]]:
        """Index documents in Milvus.

        Args:
            documents: List of (doc_id, document_dict) tuples to index

        Returns:
            Tuple of (success_count, failed_items)
        """
        # Create batches
        batches = self.batch_processor.create_batches(documents=documents)

        # Process batches
        success_count, failed_items = self.batch_processor.process_batches(batches=batches)

        logger.debug(f"Indexed {success_count} documents in {len(batches)} batches, {len(failed_items)} failed")

        return success_count, failed_items

    def query_by_doc_names(self, doc_names: list[str], fields: list[str] | None = None) -> list[dict[str, Any]]:
        """Query documents by their names.

        Args:
            doc_names: List of document names to query
            fields: Optional list of fields to return

        Returns:
            List of matching documents
        """
        return self.batch_processor.query_by_doc_names(doc_names=doc_names, fields=fields)

    def delete_documents_by_ids(self, doc_ids: list[str]) -> tuple[int, int]:
        """Delete documents by their IDs.

        Args:
            doc_ids: List of document IDs to delete

        Returns:
            Tuple of (success_count, failed_count)
        """
        return self.batch_processor.delete_documents_by_ids(doc_ids=doc_ids)

    def get_document_count(self) -> int:
        """Get total document count in the collection.

        Returns:
            Number of documents in the collection
        """
        return self.batch_processor.get_document_count()

    def create_index(self, *, dimension_mapping: dict[str, int]) -> None:
        """Create the Milvus collection if it doesn't exist.

        Args:
            dimension_mapping: Dictionary mapping vector column names to their dimensions
        """
        # Pass the full dimension_mapping to create_collection for multi-model support
        self.index_manager.create_collection(dimension_mapping=dimension_mapping)
        logger.info(f"Created collection: {self.collection_name} with dimension mapping: {dimension_mapping}")

    def refresh_index(self) -> None:
        """Refresh the collection to make recent changes visible.

        Note: Milvus automatically flushes data, but we can explicitly flush if needed.
        """
        try:
            # Milvus client flush is handled automatically, but we can call it explicitly
            # The MilvusClient doesn't expose a direct flush method in the simplified API
            # Data is automatically persisted
            logger.debug(f"Collection '{self.collection_name}' data is automatically persisted")
        except Exception as e:
            logger.warning(f"Error during collection refresh: {e}")

    def index_exists(self) -> bool:
        """Check if the Milvus collection already exists.

        Returns:
            True if collection exists, False otherwise
        """
        return self.index_manager.collection_exists()

    def detect_vector_dimension(self, *, table: pa.Table, column_name: str | None = None) -> int | None:
        """Detect vector dimension from embeddings data.

        Args:
            table: PyArrow table containing embeddings
            column_name: Name of the embeddings column to detect dimension for

        Returns:
            Detected dimension or None if detection fails
        """
        col_name = column_name if column_name is not None else self.embeddings_column
        return detect_vector_dimension(table=table, embeddings_column=col_name)

    def detect_all_vector_dimensions(self, table: pa.Table, *, vector_columns: list[str]) -> dict[str, int]:
        """Detect dimensions for all specified vector columns.

        Supports multi-model embeddings by detecting dimensions for all vector columns.

        Args:
            table: PyArrow table containing embeddings
            vector_columns: List of vector column names to detect dimensions for

        Returns:
            Dictionary mapping column names to their dimensions
        """
        return detect_all_vector_dimensions(table=table, vector_columns=vector_columns)
