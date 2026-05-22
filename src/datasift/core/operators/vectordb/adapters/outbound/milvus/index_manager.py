#!/usr/bin/env python3
"""
Milvus Index Manager
Handles collection creation, validation, and schema management for Milvus.
"""

from typing import Any, ClassVar

from pymilvus import CollectionSchema, DataType, FieldSchema, Function, FunctionType, MilvusClient

from datasift.core.constants import OperatorConstants
from datasift.exceptions.datasift_exceptions import DatasiftException
from datasift.exceptions.error_codes import ErrorCode
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger()


class MilvusMetricTypes:
    """Vector similarity metrics supported by Milvus"""

    L2: str = "L2"
    IP: str = "IP"  # Inner Product
    COSINE: str = "COSINE"
    BM25: str = "BM25"  # BM25 for sparse vectors
    ALL_TYPES: ClassVar[list[str]] = [L2, IP, COSINE, BM25]


class MilvusIndexTypes:
    """Index types supported by Milvus"""

    # Dense vector index types
    FLAT: str = "FLAT"
    IVF_FLAT: str = "IVF_FLAT"
    IVF_SQ8: str = "IVF_SQ8"
    IVF_PQ: str = "IVF_PQ"
    HNSW: str = "HNSW"
    DISKANN: str = "DISKANN"
    AUTOINDEX: str = "AUTOINDEX"

    # Sparse vector index types
    SPARSE_INVERTED_INDEX: str = "SPARSE_INVERTED_INDEX"
    SPARSE_WAND: str = "SPARSE_WAND"

    ALL_DENSE_TYPES: ClassVar[list[str]] = [FLAT, IVF_FLAT, IVF_SQ8, IVF_PQ, HNSW, DISKANN, AUTOINDEX]
    ALL_SPARSE_TYPES: ClassVar[list[str]] = [SPARSE_INVERTED_INDEX, SPARSE_WAND]
    ALL_TYPES: ClassVar[list[str]] = ALL_DENSE_TYPES + ALL_SPARSE_TYPES


# Default parameters for index types
INDEX_DEFAULT_PARAMETERS: dict[str, dict[str, Any]] = {
    # Dense vector index parameters
    MilvusIndexTypes.FLAT: {},
    MilvusIndexTypes.IVF_FLAT: {"nlist": 128},
    MilvusIndexTypes.IVF_SQ8: {"nlist": 128},
    MilvusIndexTypes.IVF_PQ: {"nlist": 128, "m": 8, "nbits": 8},
    MilvusIndexTypes.HNSW: {"M": 16, "efConstruction": 200},
    MilvusIndexTypes.DISKANN: {},
    MilvusIndexTypes.AUTOINDEX: {},
    # Sparse vector index parameters
    MilvusIndexTypes.SPARSE_INVERTED_INDEX: {"drop_ratio_build": 0.2},
    MilvusIndexTypes.SPARSE_WAND: {"drop_ratio_build": 0.2},
}


class MilvusIndexManager:
    """
    Manages Milvus collection operations including creation, validation, and schema management.

    Responsibilities:
    - Collection creation with proper schema and index configuration
    - Collection validation and compatibility checking
    - Schema mapping generation
    - Index-specific parameter management
    - Vector dimension detection
    """

    def __init__(
        self,
        *,
        client: MilvusClient,
        collection_name: str,
        index_type: str = MilvusIndexTypes.HNSW,
        metric_type: str = MilvusMetricTypes.L2,
        vector_dimension: int = OperatorConstants.VectorDB.DEFAULT_VECTOR_DIMENSION,
        index_parameters: dict[str, Any] | None = None,
        available_features: dict[str, Any] | None = None,
        feature_mappings: dict[str, str] | None = None,
        embeddings_column: str = OperatorConstants.Operators.EMBEDDINGS,
        primary_key_field: str = OperatorConstants.VectorDB.DEFAULT_PRIMARY_KEY_FIELD,
        auto_id: bool = False,
        add_sparse_vector: bool = False,
    ) -> None:
        """
        Initialize the index manager.

        Args:
            connection_alias: Milvus connection alias
            collection_name: Name of the collection
            index_type: Index type (FLAT, IVF_FLAT, HNSW, etc.)
            metric_type: Similarity metric (L2, IP, COSINE)
            vector_dimension: Dimension of vector embeddings
            index_parameters: Custom index-specific parameters
            available_features: Feature configuration
            feature_mappings: Column to field mappings
            embeddings_column: Name of embeddings column
            primary_key_field: Name of primary key field
            auto_id: Whether to auto-generate IDs
            add_sparse_vector: Whether to use sparse vectors instead of dense vectors
        """
        self.client = client
        self.collection_name = collection_name
        self.index_type = index_type
        self.metric_type = metric_type
        self.vector_dimension = vector_dimension
        self.index_parameters = index_parameters or {}
        self.available_features = available_features or {}
        self.feature_mappings = feature_mappings or {}
        self.embeddings_column = embeddings_column
        self.primary_key_field = primary_key_field
        self.auto_id = auto_id
        self.add_sparse_vector = add_sparse_vector

        self._validate_index_type()
        self._validate_metric_type()

    def _validate_index_type(self) -> None:
        """Validate index type. Skip validation in sparse mode as index type is set programmatically."""
        logger.info(f"Validating index type: index_type={self.index_type}, add_sparse_vector={self.add_sparse_vector}")

        # Skip validation in sparse mode
        if self.add_sparse_vector:
            logger.info(f"Sparse mode enabled, skipping index type validation (using {self.index_type})")
            return

        # Validate dense index types
        if self.index_type not in MilvusIndexTypes.ALL_DENSE_TYPES:
            raise DatasiftException(
                message=f"MilvusDB Error: Invalid index type '{self.index_type}'. Supported: {MilvusIndexTypes.ALL_DENSE_TYPES}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

    def _validate_metric_type(self) -> None:
        """Validate metric type and ensure sparse mode uses BM25."""
        if self.metric_type not in MilvusMetricTypes.ALL_TYPES:
            raise DatasiftException(
                message=f"MilvusDB Error: Invalid metric type '{self.metric_type}'. Supported: {MilvusMetricTypes.ALL_TYPES}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        # Validate that sparse mode requires BM25 metric type
        if self.add_sparse_vector and self.metric_type.upper() != MilvusMetricTypes.BM25:
            raise DatasiftException(
                message=f"Sparse vector mode requires metric_type='BM25', but got '{self.metric_type}'",
                status_code=400,
                error_code=ErrorCode.INVALID_CONFIGURATION,
            )

    def _get_index_parameters(self) -> dict[str, Any]:
        """Get index parameters, merging defaults with custom parameters."""
        default_params = INDEX_DEFAULT_PARAMETERS.get(self.index_type, {}).copy()

        if self.index_parameters:
            default_params.update(self.index_parameters)

        # Remove dimension for sparse vectors (not needed for BM25)
        if self.add_sparse_vector and "dim" in default_params:
            del default_params["dim"]

        return default_params

    def _create_schema_fields(self) -> list[FieldSchema]:
        """
        Create schema fields based on available features.
        Handles both dense and sparse vector modes.

        Returns:
            List of FieldSchema objects
        """
        fields: list[FieldSchema] = []

        # Add primary key field
        fields.append(
            FieldSchema(
                name=self.primary_key_field,
                dtype=DataType.VARCHAR,
                is_primary=True,
                auto_id=self.auto_id,
                max_length=512,
            )
        )

        if self.add_sparse_vector:
            # SPARSE MODE: Add content field (BM25 input) and sparse vector field (BM25 output)
            content_field_name = self.feature_mappings.get(OperatorConstants.Columns.DOC_COLUMN_DEFAULT, "text")

            # Content field - user provides text data
            # Set enable_analyzer=True to enable BM25 function for sparse vector generation
            fields.append(
                FieldSchema(
                    name=content_field_name,
                    dtype=DataType.VARCHAR,
                    max_length=65535,
                    enable_analyzer=True,
                )
            )

            # Sparse vector field - auto-generated by BM25 function
            # Get Milvus field name (sparse_embeddings -> sparse_vector)
            sparse_vector_field_name = self.feature_mappings.get(
                OperatorConstants.Columns.SPARSE_EMBEDDINGS_COLUMN_DEFAULT,
                OperatorConstants.VectorDB.SPARSE_VECTOR_FIELD_NAME,
            )
            fields.append(
                FieldSchema(
                    name=sparse_vector_field_name,
                    dtype=DataType.SPARSE_FLOAT_VECTOR,
                    description="Sparse text embeddings generated by BM25",
                )
            )

            # Also add dense embeddings field if present in feature_mappings
            if self.embeddings_column in self.feature_mappings:
                vector_field_name = self.feature_mappings.get(self.embeddings_column, self.embeddings_column)
                fields.append(
                    FieldSchema(
                        name=vector_field_name,
                        dtype=DataType.FLOAT_VECTOR,
                        dim=self.vector_dimension,
                    )
                )
        else:
            # DENSE MODE: Add dense vector field and content field
            # Get vector field name from feature mappings
            vector_field_name = self.feature_mappings.get(self.embeddings_column, self.embeddings_column)
            fields.append(
                FieldSchema(
                    name=vector_field_name,
                    dtype=DataType.FLOAT_VECTOR,
                    dim=self.vector_dimension,
                )
            )

            # Add content field for dense mode as well
            content_field_name = self.feature_mappings.get(OperatorConstants.Columns.DOC_COLUMN_DEFAULT, "text")
            fields.append(
                FieldSchema(
                    name=content_field_name,
                    dtype=DataType.VARCHAR,
                    max_length=65535,
                )
            )

        # Add other fields from feature_mappings (only fields that are actually mapped)
        for source_column_name, milvus_field_name in self.feature_mappings.items():
            # Skip if this is the embeddings column (already added)
            if source_column_name == self.embeddings_column:
                continue

            # Skip content field (already added)
            if source_column_name == OperatorConstants.Columns.DOC_COLUMN_DEFAULT:
                continue

            # Skip sparse embeddings field (already added in sparse mode)
            if source_column_name == OperatorConstants.Columns.SPARSE_EMBEDDINGS_COLUMN_DEFAULT:
                continue

            # Skip if this field maps to the primary key (already added)
            if milvus_field_name == self.primary_key_field:
                continue

            # Skip if this field maps to vector or sparse_vector (already added)
            if milvus_field_name in (
                OperatorConstants.VectorDB.DENSE_VECTOR_FIELD_NAME,
                OperatorConstants.VectorDB.SPARSE_VECTOR_FIELD_NAME,
            ):
                continue

            # Get feature config for type information
            feature_config = self.available_features.get(source_column_name, {})

            # Skip if explicitly marked as unavailable for vector db
            if feature_config.get(OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB) is False:
                continue

            # Map feature type to Milvus DataType
            feature_type = feature_config.get("type", "text")
            dtype = self._map_feature_type_to_milvus_dtype(feature_type=feature_type)

            if dtype:
                field_params: dict[str, Any] = {"name": milvus_field_name, "dtype": dtype}

                # Add max_length for VARCHAR fields
                if dtype == DataType.VARCHAR:
                    field_params["max_length"] = 65535

                fields.append(FieldSchema(**field_params))

        return fields

    def _map_feature_type_to_milvus_dtype(self, *, feature_type: str) -> DataType | None:
        """
        Map feature type to Milvus DataType.

        Args:
            feature_type: Feature type string

        Returns:
            Milvus DataType or None if not supported
        """
        type_mapping: dict[str, DataType] = {
            "text": DataType.VARCHAR,
            "string": DataType.VARCHAR,
            "keyword": DataType.VARCHAR,
            "long": DataType.INT64,
            "integer": DataType.INT32,
            "short": DataType.INT16,
            "byte": DataType.INT8,
            "double": DataType.DOUBLE,
            "float": DataType.FLOAT,
            "boolean": DataType.BOOL,
            "date": DataType.VARCHAR,  # Store as string
            "json": DataType.JSON,
        }

        return type_mapping.get(feature_type)

    def collection_exists(self) -> bool:
        """
        Check if collection exists.

        Returns:
            True if collection exists, False otherwise
        """
        try:
            return self.client.has_collection(collection_name=self.collection_name)  # type: ignore[return-value]
        except Exception as e:
            logger.error(f"Error checking collection existence: {e}")
            return False

    def _create_bm25_function(self) -> Any:
        """
        Create BM25 function for sparse vector generation.

        Returns:
            Function object for BM25 text-to-sparse-vector conversion
        """

        content_field_name = self.feature_mappings.get(OperatorConstants.Columns.DOC_COLUMN_DEFAULT, "text")
        vector_field_name = self.feature_mappings.get(
            OperatorConstants.Columns.SPARSE_EMBEDDINGS_COLUMN_DEFAULT,
            OperatorConstants.VectorDB.SPARSE_VECTOR_FIELD_NAME,
        )

        return Function(
            name="text_bm25_emb",
            function_type=FunctionType.BM25,
            input_field_names=[content_field_name],
            output_field_names=[vector_field_name],
            params={},
        )

    def create_collection(self) -> None:
        """
        Create the Milvus collection if it doesn't exist.
        Handles both dense and sparse vector modes.

        For sparse mode with BM25:
        - Creates collection with schema (NO index during creation)
        - Index must be created separately after data insertion

        Raises:
            DatasiftException: If collection creation fails
        """
        if self.collection_exists():
            raise DatasiftException(
                message=f"Collection '{self.collection_name}' already exists. Please use a different collection name or delete the existing collection.",
                status_code=409,
                error_code=ErrorCode.OPERATOR_EXECUTION_FAILED,
            )

        try:
            # Create schema fields
            fields = self._create_schema_fields()

            # Log schema field details
            field_names = [f.name for f in fields]
            logger.info(
                f"[MILVUS COLLECTION] Creating collection '{self.collection_name}' with {len(fields)} fields: {field_names}"
            )

            # Create collection schema with BM25 function for sparse mode
            if self.add_sparse_vector:
                logger.info(
                    "[MILVUS COLLECTION] Sparse vector mode enabled - creating BM25 function for text-to-sparse-vector conversion"
                )
                bm25_function = self._create_bm25_function()

                # Log BM25 function details
                content_field = self.feature_mappings.get(OperatorConstants.Columns.DOC_COLUMN_DEFAULT, "text")
                sparse_field = OperatorConstants.VectorDB.SPARSE_VECTOR_FIELD_NAME
                logger.info(f"BM25 function: '{content_field}' -> '{sparse_field}'")

                schema = CollectionSchema(
                    fields=fields,
                    description=f"Collection for {self.collection_name}",
                    functions=[bm25_function],
                )

                # For sparse mode: Use MilvusClient's create_collection with schema
                # This properly handles the connection internally
                self.client.create_collection(
                    collection_name=self.collection_name,
                    schema=schema,
                )

                logger.info(
                    f"[MILVUS COLLECTION] ✓ Collection '{self.collection_name}' created successfully with BM25 function"
                )

                # Now create index on sparse_vector field AFTER collection creation
                sparse_vector_field_name = self.feature_mappings.get(
                    OperatorConstants.Columns.SPARSE_EMBEDDINGS_COLUMN_DEFAULT,
                    OperatorConstants.VectorDB.SPARSE_VECTOR_FIELD_NAME,
                )

                # Get index parameters (without dimension for sparse vectors)
                params_dict = self._get_index_parameters()

                # Prepare and create index for sparse vector
                index_params = self.client.prepare_index_params()
                index_params.add_index(
                    field_name=sparse_vector_field_name,
                    index_type=self.index_type,
                    metric_type=self.metric_type,
                    params=params_dict,
                )

                self.client.create_index(
                    collection_name=self.collection_name,
                    index_params=index_params,
                )

                logger.info(
                    f"[MILVUS COLLECTION] ✓ Sparse vector index created on '{sparse_vector_field_name}' "
                    f"(index_type={self.index_type}, metric={self.metric_type})"
                )
            else:
                # For dense mode: Create collection with index
                logger.info(
                    f"[MILVUS COLLECTION] Dense vector mode - creating collection with dimension {self.vector_dimension}"
                )

                schema = CollectionSchema(
                    fields=fields,
                    description=f"Collection for {self.collection_name}",
                )

                # Get index parameters dictionary
                params_dict = self._get_index_parameters()

                # Prepare index params for dense vectors
                index_params = self.client.prepare_index_params()
                vector_field_name = self.feature_mappings.get(
                    self.embeddings_column, OperatorConstants.VectorDB.DENSE_VECTOR_FIELD_NAME
                )

                logger.info(f"[MILVUS COLLECTION] Creating index on dense vector field '{vector_field_name}'")

                index_params.add_index(
                    field_name=vector_field_name,
                    index_type=self.index_type,
                    metric_type=self.metric_type,
                    params=params_dict,
                )

                # Create collection with schema and index params
                self.client.create_collection(
                    collection_name=self.collection_name,
                    schema=schema,
                    index_params=index_params,
                )

                logger.info(
                    f"[MILVUS COLLECTION] ✓ Collection '{self.collection_name}' created successfully "
                    f"(index_type={self.index_type}, metric={self.metric_type}, dimension={self.vector_dimension})"
                )

        except Exception as e:
            raise DatasiftException(
                message=f"MilvusDB Error: Failed to create collection '{self.collection_name}': {e}",
                status_code=500,
                error_code=ErrorCode.OPERATOR_EXECUTION_FAILED,
            ) from e

    def get_collection_info(self) -> dict[str, Any]:
        """
        Get collection information.

        Returns:
            Dictionary with collection details

        Raises:
            DatasiftException: If collection doesn't exist or retrieval fails
        """
        if not self.collection_exists():
            raise DatasiftException(
                message=f"MilvusDB Error: Collection '{self.collection_name}' does not exist",
                status_code=404,
                error_code=ErrorCode.OPERATOR_EXECUTION_FAILED,
            )

        try:
            stats = self.client.get_collection_stats(collection_name=self.collection_name)
            return {
                "name": self.collection_name,
                "row_count": stats.get("row_count", 0),
                "exists": True,
            }
        except Exception as e:
            raise DatasiftException(
                message=f"MilvusDB Error: Failed to get collection info for '{self.collection_name}': {e}",
                status_code=500,
                error_code=ErrorCode.OPERATOR_EXECUTION_FAILED,
            ) from e

    def drop_collection(self) -> None:
        """
        Drop the collection.

        Raises:
            DatasiftException: If collection drop fails
        """
        try:
            if self.collection_exists():
                self.client.drop_collection(collection_name=self.collection_name)
                logger.info(f"Dropped collection '{self.collection_name}'")
            else:
                logger.warning(f"Collection '{self.collection_name}' does not exist, nothing to drop")
        except Exception as e:
            raise DatasiftException(
                message=f"MilvusDB Error: Failed to drop collection '{self.collection_name}': {e}",
                status_code=500,
                error_code=ErrorCode.OPERATOR_EXECUTION_FAILED,
            ) from e
