#!/usr/bin/env python3
"""
OpenSearch Operator
Implements document storage and indexing in OpenSearch/Elasticsearch.
Supports multiple KNN engines, algorithms, incremental updates, and query capabilities.
"""

import json
from typing import Any, ClassVar

import boto3
import pyarrow as pa
from botocore.credentials import Credentials
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection, helpers

from common.constants.constants import Metrics
from common.constants.operator_constants import OperatorConstants
from common.util.log import get_logger
from core.operators.abstract_operator import (
    AbstractOperator,
    OperatorCategory,
)

logger = get_logger()


# OpenSearch-specific configuration key constants
ENGINE_KEY: str = "engine"
ALGORITHM_KEY: str = "algorithm"
SPACE_TYPE_KEY: str = "space_type"
ENGINE_PARAMETERS_KEY: str = "engine_parameters"
SPARSE_EMBEDDINGS_COLUMN_KEY: str = "sparse_embeddings_column"

# Batch processing constants
DEFAULT_BATCH_SIZE: int = 100
MAX_BATCH_SIZE_MB: int = 3  # Maximum batch size in MB
BULK_INSERT_TIMEOUT: int = 180  # 3 minutes timeout
DEFAULT_VECTOR_DIMENSION: int = 384

# Query constants
SCROLL_TIMEOUT: str = "2m"
SCROLL_BATCH_SIZE: int = 1000
BULK_DELETE_BATCH_SIZE: int = 500


class OpenSearchEngineTypes:
    """KNN engine types supported by OpenSearch"""

    FAISS: str = "faiss"
    LUCENE: str = "lucene"
    NMSLIB: str = "nmslib"
    JVECTOR: str = "jvector"

    ALL_ENGINES: ClassVar[list[str]] = [FAISS, LUCENE, NMSLIB, JVECTOR]
    RECOMMENDED_ENGINES: ClassVar[list[str]] = [FAISS, LUCENE]


class OpenSearchAlgorithmTypes:
    """KNN algorithm types supported by OpenSearch"""

    HNSW: str = "hnsw"
    IVF: str = "ivf"

    ALL_ALGORITHMS: ClassVar[list[str]] = [HNSW, IVF]
    DEFAULT_ALGORITHM: str = HNSW


class VectorSimilarityTypes:
    """Vector similarity metrics"""

    L2: str = "l2"
    COSINE: str = "cosine"
    INNER_PRODUCT: str = "inner_product"

    ALL_TYPES: ClassVar[list[str]] = [L2, COSINE, INNER_PRODUCT]
    DEFAULT: str = L2


# Engine-Algorithm compatibility
ENGINE_ALGORITHM_SUPPORT: dict[str, list[str]] = {
    OpenSearchEngineTypes.FAISS: [
        OpenSearchAlgorithmTypes.HNSW,
        OpenSearchAlgorithmTypes.IVF,
    ],
    OpenSearchEngineTypes.LUCENE: [OpenSearchAlgorithmTypes.HNSW],
    OpenSearchEngineTypes.NMSLIB: [OpenSearchAlgorithmTypes.HNSW],
    OpenSearchEngineTypes.JVECTOR: [OpenSearchAlgorithmTypes.HNSW],
}

# Default parameters for engine-algorithm combinations
ENGINE_ALGORITHM_DEFAULT_PARAMETERS: dict[tuple[str, str], dict[str, int]] = {
    (OpenSearchEngineTypes.FAISS, OpenSearchAlgorithmTypes.HNSW): {
        "ef_construction": 128,
        "m": 24,
    },
    (OpenSearchEngineTypes.FAISS, OpenSearchAlgorithmTypes.IVF): {
        "nlist": 128,
        "nprobe": 8,
    },
    (OpenSearchEngineTypes.LUCENE, OpenSearchAlgorithmTypes.HNSW): {
        "ef_construction": 128,
        "m": 16,
    },
    (OpenSearchEngineTypes.NMSLIB, OpenSearchAlgorithmTypes.HNSW): {
        "ef_construction": 128,
        "m": 24,
    },
    (OpenSearchEngineTypes.JVECTOR, OpenSearchAlgorithmTypes.HNSW): {
        "ef_construction": 128,
        "m": 16,
    },
}


class OpenSearchOperator(AbstractOperator):
    """
    Operator for storing documents and embeddings in OpenSearch.
    Supports multiple KNN engines, algorithms, incremental updates, and query capabilities.
    """

    short_name: str = "opensearch"
    category: OperatorCategory = OperatorCategory.VectorDB

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the OpenSearch operator with configuration.

        Args:
            config: Configuration dictionary containing connection, index, and engine settings
        """
        super().__init__(config)

        # OpenSearch connection parameters
        self.host: str | None = config.get(OperatorConstants.VectorDB.OPENSEARCH_HOST)
        self.port: int = config.get(OperatorConstants.VectorDB.OPENSEARCH_PORT, 9200)
        self.username: str | None = config.get(OperatorConstants.VectorDB.OPENSEARCH_USERNAME)
        self.password: str | None = config.get(OperatorConstants.VectorDB.OPENSEARCH_PASSWORD)
        self.use_ssl: bool = config.get(OperatorConstants.VectorDB.OPENSEARCH_USE_SSL, True)
        self.verify_certs: bool = config.get(OperatorConstants.VectorDB.OPENSEARCH_VERIFY_CERTS, True)
        self.aws_auth: bool = config.get(OperatorConstants.VectorDB.OPENSEARCH_AWS_AUTH, False)
        self.aws_region: str | None = config.get(OperatorConstants.VectorDB.OPENSEARCH_AWS_REGION)

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
        # This will be set to the detected dimension or fall back to config value
        self.vector_dimension: int = self.config_vector_dimension
        self.dimension_auto_detected: bool = False

        # Engine and algorithm configuration
        self.engine: str = config.get(ENGINE_KEY, OpenSearchEngineTypes.FAISS)
        self.algorithm: str = config.get(ALGORITHM_KEY, OpenSearchAlgorithmTypes.HNSW)
        self.space_type: str = config.get(SPACE_TYPE_KEY, VectorSimilarityTypes.L2)
        self.engine_parameters: dict[str, Any] = config.get(ENGINE_PARAMETERS_KEY, {})

        # Validate input parameters
        self._validate_input_parameters()

        # Validate engine and algorithm compatibility
        self._validate_engine_algorithm()

        # Initialize OpenSearch client
        self.client: OpenSearch = self._create_client()

        # Get OpenSearch version
        self.os_version: tuple[int, int, int] = self._get_opensearch_version()

        logger.info(
            f"Initialized OpenSearch operator for index: {self.index_name} "
            f"(engine: {self.engine}, algorithm: {self.algorithm}, version: {self.os_version})",
            extra=self.common_log_arguments,
        )

    def _validate_input_parameters(self) -> None:
        """
        Validate input parameters for the OpenSearch operator.

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Validate required parameters
        if not self.host:
            raise ValueError("opensearch_host is required")
        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError("opensearch_host must be a non-empty string")

        if not self.index_name:
            raise ValueError("index_name is required")
        if not isinstance(self.index_name, str) or not self.index_name.strip():
            raise ValueError("index_name must be a non-empty string")

        # Validate port
        if not isinstance(self.port, int):
            raise ValueError("opensearch_port must be an integer")
        if self.port < 1 or self.port > 65535:
            raise ValueError("opensearch_port must be between 1 and 65535")

        # Validate batch size
        if not isinstance(self.batch_size, int):
            raise ValueError("batch_size must be an integer")
        if self.batch_size < 1:
            raise ValueError("batch_size must be greater than 0")

        # Validate vector dimension
        if not isinstance(self.config_vector_dimension, int):
            raise ValueError("vector_dimension must be an integer")
        if self.config_vector_dimension < 1:
            raise ValueError("vector_dimension must be greater than 0")

        # Validate AWS auth configuration
        if self.aws_auth and not self.aws_region:
            raise ValueError("aws_region is required when aws_auth is enabled")

        # Validate engine
        if self.engine not in OpenSearchEngineTypes.ALL_ENGINES:
            raise ValueError(
                f"Invalid engine '{self.engine}'. Must be one of: {', '.join(OpenSearchEngineTypes.ALL_ENGINES)}"
            )

        # Validate algorithm
        if self.algorithm not in OpenSearchAlgorithmTypes.ALL_ALGORITHMS:
            raise ValueError(
                f"Invalid algorithm '{self.algorithm}'. Must be one of: {', '.join(OpenSearchAlgorithmTypes.ALL_ALGORITHMS)}"
            )

        # Validate space type
        if self.space_type not in VectorSimilarityTypes.ALL_TYPES:
            raise ValueError(
                f"Invalid space_type '{self.space_type}'. Must be one of: {', '.join(VectorSimilarityTypes.ALL_TYPES)}"
            )

    def _validate_engine_algorithm(self) -> None:
        """Validate engine and algorithm compatibility"""
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

    def _create_client(self) -> OpenSearch:
        """Create and return an OpenSearch client with appropriate authentication"""
        connection_params: dict[str, Any] = {
            "hosts": [{"host": self.host, "port": self.port}],
            "use_ssl": self.use_ssl,
            "verify_certs": self.verify_certs,
            "connection_class": RequestsHttpConnection,
            "timeout": 60,
        }

        # Add authentication
        if self.aws_auth:
            credentials: Credentials | None = boto3.Session().get_credentials()
            auth: AWSV4SignerAuth = AWSV4SignerAuth(credentials, self.aws_region or "us-east-1")
            connection_params["http_auth"] = auth
        elif self.username and self.password:
            connection_params["http_auth"] = (self.username, self.password)

        return OpenSearch(**connection_params)

    def _get_opensearch_version(self) -> tuple[int, int, int]:
        """Get OpenSearch server version"""
        try:
            info: dict[str, Any] = self.client.info()
            version_string: str = info.get("version", {}).get("number", "0.0.0")
            parts: list[str] = version_string.split(".")
            return tuple(int(p) for p in parts[:3])  # type: ignore
        except Exception as e:
            logger.warning(
                f"Could not retrieve OpenSearch version: {e}",
                extra=self.common_log_arguments,
            )
            return (0, 0, 0)

    def _get_engine_parameters(self) -> dict[str, Any]:
        """Get engine parameters, merging defaults with custom parameters"""
        param_key: tuple[str, str] = (self.engine, self.algorithm)
        default_params: dict[str, Any] = ENGINE_ALGORITHM_DEFAULT_PARAMETERS.get(param_key, {}).copy()

        if self.engine_parameters:
            default_params.update(self.engine_parameters)

        return default_params

    def _detect_vector_dimension(self, table: pa.Table) -> int | None:
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
            logger.debug(
                f"Embeddings column '{self.embeddings_column}' not found in table",
                extra=self.common_log_arguments,
            )
            return None

        if table.num_rows == 0:
            logger.debug(
                "Cannot detect dimension from empty table",
                extra=self.common_log_arguments,
            )
            return None

        try:
            # Get the first non-null embedding
            embeddings_col: pa.ChunkedArray = table[self.embeddings_column]

            for idx in range(min(table.num_rows, 10)):  # Check first 10 rows
                embedding_value: Any = embeddings_col[idx].as_py()

                if embedding_value is None:
                    continue

                if not isinstance(embedding_value, list):
                    logger.warning(
                        f"Embedding at row {idx} is not a list: {type(embedding_value)}",
                        extra=self.common_log_arguments,
                    )
                    continue

                if len(embedding_value) == 0:
                    continue

                # Check if this is nested embeddings (chunked)
                if isinstance(embedding_value[0], list):
                    # Nested structure: [[emb1], [emb2], ...]
                    # Get dimension from first inner list
                    if len(embedding_value[0]) > 0:
                        dimension: int = len(embedding_value[0])
                        logger.info(
                            f"Auto-detected vector dimension: {dimension} (from chunked embeddings)",
                            extra=self.common_log_arguments,
                        )
                        return dimension
                elif isinstance(embedding_value[0], (int, float)):
                    # Flat structure: [float1, float2, ...]
                    dimension: int = len(embedding_value)
                    logger.info(
                        f"Auto-detected vector dimension: {dimension} (from flat embeddings)",
                        extra=self.common_log_arguments,
                    )
                    return dimension
                else:
                    logger.warning(
                        f"Unexpected embedding structure at row {idx}: first element is {type(embedding_value[0])}",
                        extra=self.common_log_arguments,
                    )
                    continue

            logger.warning(
                "Could not find valid embeddings in first 10 rows for dimension detection",
                extra=self.common_log_arguments,
            )
            return None

        except Exception as e:
            logger.warning(
                f"Error detecting vector dimension: {e!s}",
                extra=self.common_log_arguments,
            )
            return None

    def _create_index_mapping(self) -> dict[str, Any]:
        """Create index mapping based on available features and feature mappings"""
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
                # Support for object/nested types - enables dynamic mapping for JSON objects
                # Don't pre-define properties - let OpenSearch dynamically map each document
                # This allows SQL queries on nested fields while handling schema variations from LLM extraction
                # Using "enabled": true allows the field to be indexed and queried
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

    def _create_index(self) -> None:
        """Create the OpenSearch index if it doesn't exist"""
        if self.client.indices.exists(index=self.index_name):
            logger.info(
                f"Index {self.index_name} already exists",
                extra=self.common_log_arguments,
            )
            # Validate existing index configuration
            self._validate_existing_index()
            return

        # Build index configuration
        index_body: dict[str, Any] = self._create_index_mapping()

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
        logger.info(
            f"Created index {self.index_name} with engine {self.engine} and algorithm {self.algorithm}",
            extra=self.common_log_arguments,
        )

    def _validate_existing_index(self) -> None:
        """Validate that existing index configuration matches requested settings"""
        try:
            mappings: dict[str, Any] = self.client.indices.get_mapping(index=self.index_name)
            index_mappings: dict[str, Any] = mappings.get(self.index_name, {}).get("mappings", {})
            meta: dict[str, Any] = index_mappings.get("_meta", {})

            existing_engine: str | None = meta.get("engine")
            existing_algorithm: str | None = meta.get("algorithm")

            if existing_engine and existing_engine != self.engine:
                logger.warning(
                    f"Engine mismatch: index has '{existing_engine}', config specifies '{self.engine}'",
                    extra=self.common_log_arguments,
                )

            if existing_algorithm and existing_algorithm != self.algorithm:
                logger.warning(
                    f"Algorithm mismatch: index has '{existing_algorithm}', config specifies '{self.algorithm}'",
                    extra=self.common_log_arguments,
                )
        except Exception as e:
            logger.warning(
                f"Could not validate existing index: {e}",
                extra=self.common_log_arguments,
            )

    def _prepare_document(self, row_data: dict[str, Any]) -> dict[str, Any]:
        """Prepare a document for indexing by mapping columns to index fields"""
        import json

        doc: dict[str, Any] = {}

        for feature_name, feature_config in self.available_features.items():
            if not feature_config.get("available_for_vector_db", False):
                continue

            mapped_name: str = self.feature_mappings.get(feature_name, feature_name)

            if feature_name in row_data:
                value: Any = row_data[feature_name]

                if value is None:
                    continue

                # Convert numpy arrays to lists
                if hasattr(value, "tolist"):
                    value = value.tolist()

                # Parse JSON strings for object/nested types
                feature_type: str = feature_config.get("type", "text")
                if feature_type in ("object", "nested", "json") and isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        # If parsing fails, keep as string
                        pass

                doc[mapped_name] = value

        return doc

    def _calculate_batch_size_bytes(self, documents: list[dict[str, Any]]) -> int:
        """Calculate approximate size of documents in bytes"""
        try:
            return len(json.dumps(documents).encode("utf-8"))
        except Exception:
            return 0

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Transform the input table by indexing documents in OpenSearch.
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
            error_msg: str = f"Required column '{self.doc_id_column}' not found in table"
            logger.error(error_msg, extra=self.common_log_arguments)
            metadata[Metrics.External.NODE_STATUS] = "failed"
            return [table], metadata

        if self.embeddings_column not in table.column_names:
            error_msg: str = f"Required column '{self.embeddings_column}' not found in table"
            logger.error(error_msg, extra=self.common_log_arguments)
            metadata[Metrics.External.NODE_STATUS] = "failed"
            return [table], metadata

        # Auto-detect vector dimension from embeddings data
        detected_dimension: int | None = self._detect_vector_dimension(table)
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
            self.vector_dimension = detected_dimension
            self.dimension_auto_detected = True
        else:
            logger.info(
                f"Could not auto-detect dimension, using config value: {self.config_vector_dimension}",
                extra=self.common_log_arguments,
            )
            self.vector_dimension = self.config_vector_dimension
            self.dimension_auto_detected = False

        # Create index if needed
        if self.create_index:
            try:
                self._create_index()
            except Exception as e:
                logger.error(f"Failed to create index: {e!s}", extra=self.common_log_arguments)
                metadata[Metrics.External.NODE_STATUS] = "failed"
                return [table], metadata

        # Prepare documents for bulk indexing with size-aware batching
        all_actions: list[list[dict[str, Any]]] = []
        current_batch: list[dict[str, Any]] = []
        current_batch_size: int = 0
        max_batch_size_bytes: int = MAX_BATCH_SIZE_MB * 1024 * 1024

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
                        reason="Missing document ID",
                    )
                    continue

                # Get embeddings and check if it's a nested list (chunked embeddings)
                embeddings_value: Any = row_data.get(self.embeddings_column)

                # Detect if embeddings is a list of embeddings (chunked content)
                # The embeddings operator outputs [[emb1], [emb2], [emb3]] for chunked content
                # where each emb is a vector like [0.1, 0.2, ..., 0.4096]
                is_chunked: bool = False
                if embeddings_value and isinstance(embeddings_value, list) and len(embeddings_value) > 0:
                    # Check if first element is also a list (nested structure)
                    if isinstance(embeddings_value[0], list):
                        # Further check: if the first element's first item is a number,
                        # then we have chunked embeddings [[emb1], [emb2], ...]
                        if len(embeddings_value[0]) > 0 and isinstance(embeddings_value[0][0], (int, float)):
                            # This is chunked embeddings - treat all cases as chunked
                            is_chunked = True
                            logger.debug(
                                f"Detected chunked embeddings with {len(embeddings_value)} chunks for doc {doc_id}",
                                extra=self.common_log_arguments,
                            )

                if is_chunked:
                    # Create separate documents for each chunk
                    # embeddings_value is [[emb1], [emb2], ...] where each emb is the actual vector
                    for chunk_idx, chunk_embedding in enumerate(embeddings_value):
                        # Create a copy of row_data for this chunk
                        chunk_row_data: dict[str, Any] = row_data.copy()

                        # chunk_embedding is already the flat embedding vector [0.1, 0.2, ..., 0.4096]
                        # Update the embeddings to be the single chunk embedding
                        chunk_row_data[self.embeddings_column] = chunk_embedding

                        # Create unique document ID for this chunk
                        chunk_doc_id: str = f"{doc_id}_chunk_{chunk_idx}"

                        # Prepare document
                        doc: dict[str, Any] = self._prepare_document(chunk_row_data)

                        action: dict[str, Any] = {
                            "_index": self.index_name,
                            "_id": chunk_doc_id,
                            "_source": doc,
                        }

                        # Check batch size
                        action_size: int = self._calculate_batch_size_bytes([action])
                        if current_batch and (
                            current_batch_size + action_size > max_batch_size_bytes
                            or len(current_batch) >= self.batch_size
                        ):
                            all_actions.append(current_batch)
                            current_batch = []
                            current_batch_size = 0

                        current_batch.append(action)
                        current_batch_size += action_size
                else:
                    # Single embedding - process as before
                    # Prepare document
                    doc: dict[str, Any] = self._prepare_document(row_data)

                    action: dict[str, Any] = {
                        "_index": self.index_name,
                        "_id": doc_id,
                        "_source": doc,
                    }

                    # Check batch size
                    action_size: int = self._calculate_batch_size_bytes([action])
                    if current_batch and (
                        current_batch_size + action_size > max_batch_size_bytes or len(current_batch) >= self.batch_size
                    ):
                        all_actions.append(current_batch)
                        current_batch = []
                        current_batch_size = 0

                    current_batch.append(action)
                    current_batch_size += action_size

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

        # Add remaining batch
        if current_batch:
            all_actions.append(current_batch)

        # Bulk index documents
        metadata["number_of_batches"] = len(all_actions)
        success_count: int = 0

        for batch_idx, batch in enumerate(all_actions):
            try:
                logger.info(
                    f"Processing batch {batch_idx + 1}/{len(all_actions)} with {len(batch)} documents",
                    extra=self.common_log_arguments,
                )

                success: int
                failed: list[dict[str, Any]]
                success, failed = helpers.bulk(
                    self.client,
                    batch,
                    raise_on_error=False,
                    raise_on_exception=False,
                    request_timeout=BULK_INSERT_TIMEOUT,
                )
                success_count += success

                if failed:
                    for item in failed:
                        error_info: dict[str, Any] = item.get("index", {})
                        doc_id: str = error_info.get("_id", "unknown")
                        error_msg: str = error_info.get("error", {}).get("reason", "Unknown error")
                        self.record_failed_document(
                            metadata=metadata,
                            doc_id=doc_id,
                            doc_name=doc_id,
                            reason=error_msg[:100],
                        )

            except Exception as e:
                logger.error(
                    f"Batch {batch_idx + 1} indexing failed: {e!s}",
                    extra=self.common_log_arguments,
                )
                for action in batch:
                    doc_id: str = action.get("_id", "unknown")
                    self.record_failed_document(metadata=metadata, doc_id=doc_id, doc_name=doc_id, reason=str(e))

        metadata[Metrics.External.PROCESSED_DOCS] = success_count
        logger.info(
            f"Successfully indexed {success_count} documents in {len(all_actions)} batches",
            extra=self.common_log_arguments,
        )

        # Refresh index
        try:
            self.client.indices.refresh(index=self.index_name)
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
        if not doc_names:
            return []

        try:
            # Build query
            query: dict[str, Any] = {
                "query": {"terms": {"name.keyword": doc_names}},
                "size": len(doc_names),
            }

            if fields:
                query["_source"] = fields

            response: dict[str, Any] = self.client.search(index=self.index_name, body=query)
            hits: list[dict[str, Any]] = response.get("hits", {}).get("hits", [])

            return [hit["_source"] for hit in hits]

        except Exception as e:
            logger.error(f"Error querying documents: {e!s}", extra=self.common_log_arguments)
            return []

    def delete_documents_by_ids(self, doc_ids: list[str]) -> tuple[int, int]:
        """
        Delete documents by their IDs.

        Args:
            doc_ids: List of document IDs to delete

        Returns:
            Tuple of (success_count, failed_count)
        """
        if not doc_ids:
            return 0, 0

        success_count: int = 0
        failed_count: int = 0

        try:
            # Process in batches
            for i in range(0, len(doc_ids), BULK_DELETE_BATCH_SIZE):
                batch: list[str] = doc_ids[i : i + BULK_DELETE_BATCH_SIZE]

                # Build bulk delete actions
                actions: list[dict[str, Any]] = [
                    {"_op_type": "delete", "_index": self.index_name, "_id": doc_id} for doc_id in batch
                ]

                success: int
                failed: list[dict[str, Any]]
                success, failed = helpers.bulk(self.client, actions, raise_on_error=False, raise_on_exception=False)

                success_count += success
                failed_count += len(failed)

            logger.info(
                f"Deleted {success_count} documents, {failed_count} failed",
                extra=self.common_log_arguments,
            )

        except Exception as e:
            logger.error(f"Error deleting documents: {e!s}", extra=self.common_log_arguments)
            failed_count = len(doc_ids)

        return success_count, failed_count

    def get_document_count(self) -> int:
        """Get total document count in the index"""
        try:
            response: dict[str, Any] = self.client.count(index=self.index_name)
            return response.get("count", 0)
        except Exception as e:
            logger.error(
                f"Error getting document count: {e!s}",
                extra=self.common_log_arguments,
            )
            return 0

    def get_metadata(self) -> dict[str, Any]:
        """Get metadata about the operator including features and attributes"""
        return {
            "sdk": True,
            "category": "vectordb",
            "is_operator_available": True,
            "label": "OpenSearch",
            "description": "Store documents and embeddings in OpenSearch for vector similarity search with multiple engine support",
            "features": {
                "doc_id_hash": {
                    "name": "Document ID",
                    "description": "Unique identifier for the document",
                    "available_for_vector_db": True,
                    "mandatory_for_vector_db": True,
                    "type": "string",
                    "is_primary": True,
                    "tags": ["mandatory", "primary"],
                },
                "embeddings": {
                    "name": "Embeddings",
                    "description": "Dense vector embeddings for similarity search",
                    "available_for_vector_db": True,
                    "mandatory_for_vector_db": True,
                    "type": "vector",
                    "tags": ["mandatory"],
                },
                "sparse_embeddings": {
                    "name": "Sparse Embeddings",
                    "description": "Sparse vector embeddings for hybrid search",
                    "available_for_vector_db": True,
                    "type": "vector_sparse",
                    "tags": [],
                },
                "content": {
                    "name": "Document Content",
                    "description": "The text content of the document",
                    "available_for_filter": True,
                    "available_for_vector_db": True,
                    "type": "string",
                    "tags": [],
                },
            },
            "attributes": {
                "opensearch_host": {
                    "name": "OpenSearch Host",
                    "description": "OpenSearch server host address",
                    "required": True,
                    "type": "string",
                },
                "opensearch_port": {
                    "name": "OpenSearch Port",
                    "description": "OpenSearch server port",
                    "required": False,
                    "default": 9200,
                    "type": "integer",
                },
                "index_name": {
                    "name": "Index Name",
                    "description": "Name of the OpenSearch index",
                    "required": True,
                    "type": "string",
                },
                "engine": {
                    "name": "KNN Engine",
                    "description": "KNN engine type (faiss, lucene, nmslib, jvector)",
                    "required": False,
                    "default": "faiss",
                    "type": "select",
                    "options": OpenSearchEngineTypes.ALL_ENGINES,
                },
                "algorithm": {
                    "name": "KNN Algorithm",
                    "description": "KNN algorithm type (hnsw, ivf)",
                    "required": False,
                    "default": "hnsw",
                    "type": "select",
                    "options": OpenSearchAlgorithmTypes.ALL_ALGORITHMS,
                },
                "space_type": {
                    "name": "Space Type",
                    "description": "Vector similarity metric (l2, cosine, inner_product)",
                    "required": False,
                    "default": "l2",
                    "type": "select",
                    "options": VectorSimilarityTypes.ALL_TYPES,
                },
                "vector_dimension": {
                    "name": "Vector Dimension",
                    "description": "Dimension of dense vector embeddings",
                    "required": False,
                    "default": 384,
                    "type": "integer",
                },
                "batch_size": {
                    "name": "Batch Size",
                    "description": "Number of documents to index in each batch",
                    "required": False,
                    "default": 100,
                    "type": "integer",
                },
            },
        }


def main() -> None:
    """Example usage of the OpenSearch operator"""
    import numpy as np
    import pyarrow as pa

    # Example configuration
    config: dict[str, Any] = {
        "opensearch_host": "localhost",
        "opensearch_port": 9200,
        "opensearch_username": "admin",
        "opensearch_password": "admin",  # pragma: allowlist secret
        "opensearch_use_ssl": False,
        "opensearch_verify_certs": False,
        "index_name": "datasift_documents",
        "doc_id_column": "doc_id_hash",
        "embeddings_column": "embeddings",
        "vector_dimension": 384,
        "engine": "faiss",
        "algorithm": "hnsw",
        "space_type": "l2",
        "batch_size": 100,
        "create_index": True,
        "available_features": {
            "doc_id_hash": {
                "name": "Document ID",
                "available_for_vector_db": True,
                "mandatory_for_vector_db": True,
                "type": "string",
                "is_primary": True,
            },
            "content": {
                "name": "Content",
                "available_for_vector_db": True,
                "type": "string",
            },
            "embeddings": {
                "name": "Embeddings",
                "available_for_vector_db": True,
                "mandatory_for_vector_db": True,
                "type": "vector",
            },
        },
        "feature_mappings": {
            "doc_id_hash": "pk",
            "content": "text",
            "embeddings": "vector_embeddings",
        },
    }

    # Create sample data
    sample_data: dict[str, list[Any]] = {
        "doc_id_hash": ["doc1", "doc2", "doc3"],
        "content": [
            "This is the first document",
            "This is the second document",
            "This is the third document",
        ],
        "embeddings": [
            np.random.rand(384).tolist(),
            np.random.rand(384).tolist(),
            np.random.rand(384).tolist(),
        ],
    }

    # Create PyArrow table
    table: pa.Table = pa.table(sample_data)

    # Initialize operator
    operator: OpenSearchOperator = OpenSearchOperator(config)

    # Transform (index documents)
    _result_tables: list[pa.Table]
    metadata: dict[str, Any]
    _result_tables, metadata = operator.transform(table)

    print(f"Indexed {metadata[Metrics.External.PROCESSED_DOCS]} documents")
    print(f"Failed: {metadata[Metrics.External.FAILED_DOCS_COUNT]}")
    print(f"Batches: {metadata.get('number_of_batches', 0)}")
    print(f"Total documents in index: {operator.get_document_count()}")

    # Query example
    docs: list[dict[str, Any]] = operator.query_by_doc_names(["doc1", "doc2"])
    print(f"Found {len(docs)} documents by name")


if __name__ == "__main__":
    main()
