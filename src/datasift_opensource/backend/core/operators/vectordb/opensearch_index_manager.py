#!/usr/bin/env python3
"""
OpenSearch Index Manager
Handles index creation, validation, and schema management for OpenSearch.
"""

import pyarrow as pa
from typing import Any, ClassVar

from opensearchpy import OpenSearch

from common.util.log import get_logger

logger = get_logger()


# Engine-Algorithm compatibility
ENGINE_ALGORITHM_SUPPORT: dict[str, list[str]] = {
    "faiss": ["hnsw", "ivf"],
    "lucene": ["hnsw"],
    "nmslib": ["hnsw"],
    "jvector": ["hnsw"],
}

# Default parameters for engine-algorithm combinations
ENGINE_ALGORITHM_DEFAULT_PARAMETERS: dict[tuple[str, str], dict[str, int]] = {
    ("faiss", "hnsw"): {"ef_construction": 128, "m": 24},
    ("faiss", "ivf"): {"nlist": 128, "nprobe": 8},
    ("lucene", "hnsw"): {"ef_construction": 128, "m": 16},
    ("nmslib", "hnsw"): {"ef_construction": 128, "m": 24},
    ("jvector", "hnsw"): {"ef_construction": 128, "m": 16},
}


class OpenSearchEngineTypes:
    """KNN engine types supported by OpenSearch"""
    FAISS: str = "faiss"
    LUCENE: str = "lucene"
    NMSLIB: str = "nmslib"
    JVECTOR: str = "jvector"
    ALL_ENGINES: ClassVar[list[str]] = [FAISS, LUCENE, NMSLIB, JVECTOR]


class OpenSearchAlgorithmTypes:
    """KNN algorithm types supported by OpenSearch"""
    HNSW: str = "hnsw"
    IVF: str = "ivf"
    ALL_ALGORITHMS: ClassVar[list[str]] = [HNSW, IVF]


class VectorSimilarityTypes:
    """Vector similarity metrics"""
    L2: str = "l2"
    COSINE: str = "cosine"
    INNER_PRODUCT: str = "inner_product"
    ALL_TYPES: ClassVar[list[str]] = [L2, COSINE, INNER_PRODUCT]


class OpenSearchIndexManager:
    """
    Manages OpenSearch index operations including creation, validation, and schema management.
    
    Responsibilities:
    - Index creation with proper KNN configuration
    - Index validation and compatibility checking
    - Schema mapping generation
    - Engine-specific parameter management
    - Vector dimension detection
    """

    def __init__(
        self,
        client: OpenSearch,
        index_name: str,
        engine: str = "faiss",
        algorithm: str = "hnsw",
        space_type: str = "l2",
        vector_dimension: int = 384,
        engine_parameters: dict[str, Any] | None = None,
        index_settings: dict[str, Any] | None = None,
        available_features: dict[str, Any] | None = None,
        feature_mappings: dict[str, str] | None = None,
        embeddings_column: str = "embeddings",
    ) -> None:
        """
        Initialize the index manager.

        Args:
            client: OpenSearch client instance
            index_name: Name of the index
            engine: KNN engine (faiss, lucene, nmslib, jvector)
            algorithm: KNN algorithm (hnsw, ivf)
            space_type: Similarity metric (l2, cosine, inner_product)
            vector_dimension: Dimension of vector embeddings
            engine_parameters: Custom engine-specific parameters
            index_settings: Custom index settings
            available_features: Feature configuration
            feature_mappings: Column to field mappings
            embeddings_column: Name of embeddings column
        """
        self.client = client
        self.index_name = index_name
        self.engine = engine
        self.algorithm = algorithm
        self.space_type = space_type
        self.vector_dimension = vector_dimension
        self.engine_parameters = engine_parameters or {}
        self.index_settings = index_settings
        self.available_features = available_features or {}
        self.feature_mappings = feature_mappings or {}
        self.embeddings_column = embeddings_column

        self._validate_engine_algorithm()

    def _validate_engine_algorithm(self) -> None:
        """Validate engine and algorithm compatibility."""
        if self.engine not in OpenSearchEngineTypes.ALL_ENGINES:
            raise ValueError(f"Invalid engine '{self.engine}'. Supported: {OpenSearchEngineTypes.ALL_ENGINES}")

        if self.algorithm not in OpenSearchAlgorithmTypes.ALL_ALGORITHMS:
            raise ValueError(
                f"Invalid algorithm '{self.algorithm}'. Supported: {OpenSearchAlgorithmTypes.ALL_ALGORITHMS}"
            )

        supported_algorithms: list[str] = ENGINE_ALGORITHM_SUPPORT.get(self.engine, [])
        if self.algorithm not in supported_algorithms:
            raise ValueError(
                f"Algorithm '{self.algorithm}' not supported by engine '{self.engine}'. "
                f"Supported algorithms: {supported_algorithms}"
            )

    def _get_engine_parameters(self) -> dict[str, Any]:
        """Get engine parameters, merging defaults with custom parameters."""
        param_key: tuple[str, str] = (self.engine, self.algorithm)
        default_params: dict[str, Any] = ENGINE_ALGORITHM_DEFAULT_PARAMETERS.get(param_key, {}).copy()

        if self.engine_parameters:
            default_params.update(self.engine_parameters)

        return default_params

    def detect_vector_dimension(self, table: pa.Table) -> int | None:
        """
        Auto-detect vector dimension from the embeddings column in the PyArrow table.

        Handles both flat embeddings and nested (chunked) embeddings:
        - Flat: [float1, float2, ..., floatN] -> dimension is length of list
        - Nested: [[emb1], [emb2], ...] -> dimension is length of first inner list

        Args:
            table: PyArrow table containing embeddings

        Returns:
            Detected dimension or None if detection fails
        """
        if self.embeddings_column not in table.column_names:
            logger.debug(f"Embeddings column '{self.embeddings_column}' not found in table")
            return None

        if table.num_rows == 0:
            logger.debug("Cannot detect dimension from empty table")
            return None

        try:
            embeddings_col: pa.ChunkedArray = table[self.embeddings_column]

            for idx in range(min(table.num_rows, 10)):  # Check first 10 rows
                embedding_value: Any = embeddings_col[idx].as_py()

                if embedding_value is None:
                    continue

                if not isinstance(embedding_value, list):
                    logger.warning(f"Embedding at row {idx} is not a list: {type(embedding_value)}")
                    continue

                if len(embedding_value) == 0:
                    continue

                # Check if this is nested embeddings (chunked)
                if isinstance(embedding_value[0], list):
                    # Nested structure: [[emb1], [emb2], ...]
                    if len(embedding_value[0]) > 0:
                        dimension: int = len(embedding_value[0])
                        logger.info(f"Auto-detected vector dimension: {dimension} (from chunked embeddings)")
                        return dimension
                elif isinstance(embedding_value[0], (int, float)):
                    # Flat structure: [float1, float2, ...]
                    dimension: int = len(embedding_value)
                    logger.info(f"Auto-detected vector dimension: {dimension} (from flat embeddings)")
                    return dimension
                else:
                    logger.warning(
                        f"Unexpected embedding structure at row {idx}: first element is {type(embedding_value[0])}"
                    )
                    continue

            logger.warning("Could not find valid embeddings in first 10 rows for dimension detection")
            return None

        except Exception as e:
            logger.warning(f"Error detecting vector dimension: {e!s}")
            return None

    def create_index_mapping(self) -> dict[str, Any]:
        """Create index mapping based on available features and feature mappings."""
        properties: dict[str, Any] = {}

        # Process each feature
        for feature_name, feature_config in self.available_features.items():
            if not feature_config.get("available_for_vector_db", False):
                continue

            mapped_name: str = self.feature_mappings.get(feature_name, feature_name)
            feature_type: str = feature_config.get("type", "text")

            # Map feature types to OpenSearch types
            if feature_type == "vector":
                # Dense vector field with engine-specific configuration
                properties[mapped_name] = {
                    "type": "knn_vector",
                    "dimension": self.vector_dimension,
                    "method": {
                        "name": self.algorithm,
                        "space_type": self.space_type,
                        "engine": self.engine,
                        "parameters": self._get_engine_parameters(),
                    },
                }
            elif feature_type == "vector_sparse":
                properties[mapped_name] = {"type": "rank_features"}
            elif feature_type == "string":
                properties[mapped_name] = {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
                }
            elif feature_type == "int64":
                properties[mapped_name] = {"type": "long"}
            elif feature_type == "float":
                properties[mapped_name] = {"type": "float"}
            elif feature_type == "boolean":
                properties[mapped_name] = {"type": "boolean"}
            elif feature_type in ("object", "json", "nested"):
                properties[mapped_name] = {
                    "type": "object",
                    "enabled": True,
                }
            else:
                properties[mapped_name] = {"type": "text"}

        return {
            "mappings": {
                "properties": properties,
                "_meta": {
                    "engine": self.engine,
                    "algorithm": self.algorithm,
                    "space_type": self.space_type,
                    "created_by": "datasift-opensource",
                },
            }
        }

    def create_index(self) -> None:
        """Create the OpenSearch index if it doesn't exist."""
        if self.client.indices.exists(index=self.index_name):
            logger.info(f"Index {self.index_name} already exists")
            self.validate_existing_index()
            return

        # Build index configuration
        index_body: dict[str, Any] = self.create_index_mapping()

        # Add custom settings if provided
        if self.index_settings:
            index_body["settings"] = self.index_settings
        else:
            # Default settings for KNN
            index_body["settings"] = {
                "index": {
                    "knn": True,
                    "knn.algo_param.ef_search": 100,
                    "number_of_shards": 2,
                    "number_of_replicas": 1,
                }
            }

        # Create index
        self.client.indices.create(index=self.index_name, body=index_body)
        logger.info(f"Created index {self.index_name} with engine {self.engine} and algorithm {self.algorithm}")

    def validate_existing_index(self) -> None:
        """Validate that existing index configuration matches requested settings."""
        try:
            mappings: dict[str, Any] = self.client.indices.get_mapping(index=self.index_name)
            index_mappings: dict[str, Any] = mappings.get(self.index_name, {}).get("mappings", {})
            meta: dict[str, Any] = index_mappings.get("_meta", {})

            existing_engine: str | None = meta.get("engine")
            existing_algorithm: str | None = meta.get("algorithm")

            if existing_engine and existing_engine != self.engine:
                logger.warning(
                    f"Engine mismatch: index has '{existing_engine}', config specifies '{self.engine}'"
                )

            if existing_algorithm and existing_algorithm != self.algorithm:
                logger.warning(
                    f"Algorithm mismatch: index has '{existing_algorithm}', config specifies '{self.algorithm}'"
                )
        except Exception as e:
            logger.warning(f"Could not validate existing index: {e}")

    def index_exists(self) -> bool:
        """Check if the index exists."""
        try:
            return self.client.indices.exists(index=self.index_name)
        except Exception as e:
            logger.error(f"Error checking index existence: {e}")
            return False

    def delete_index(self) -> bool:
        """
        Delete the index.
        
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            if self.index_exists():
                self.client.indices.delete(index=self.index_name)
                logger.info(f"Deleted index {self.index_name}")
                return True
            else:
                logger.warning(f"Index {self.index_name} does not exist")
                return False
        except Exception as e:
            logger.error(f"Error deleting index: {e}")
            return False

    def refresh_index(self) -> None:
        """Refresh the index to make recent changes visible."""
        try:
            self.client.indices.refresh(index=self.index_name)
            logger.debug(f"Refreshed index {self.index_name}")
        except Exception as e:
            logger.warning(f"Failed to refresh index: {e!s}")
