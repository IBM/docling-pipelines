#!/usr/bin/env python3
"""
OpenSearch Index Manager
Handles index creation, validation, and schema management for OpenSearch.
"""

import json
from copy import deepcopy
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any, ClassVar

from opensearchpy import OpenSearch

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.exceptions.docpipe_exceptions import TROUBLESHOOTING_DOCS_URL, DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.utils.infrastructure.logging import get_logger
from docpipe.utils.operators.vectordb_utils import build_mapping_dict

logger = get_logger()

# Allowlisted OpenSearch mapping properties (O(1) lookup)
SUPPORTED_MAPPING_OVERRIDES: set[str] = {
    "analyzer",
    "search_analyzer",
    "copy_to",
    "boost",
    "index",
    "store",
    "similarity",
    "normalizer",
    "fields",
}


def _deep_merge(*, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively merge override dict into base dict.

    Args:
        base: Base dictionary
        override: Override dictionary

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(base=result[key], override=value)
        else:
            result[key] = deepcopy(value)

    return result


# Reserved field names that cannot be overridden by user schemas
RESERVED_FIELDS: set[str] = {
    "metadata",
    "_id",
    "_source",
    "_meta",
}


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
        *,
        index_name: str,
        engine: str = "faiss",
        algorithm: str = "hnsw",
        space_type: str = "l2",
        engine_parameters: dict[str, Any] | None = None,
        index_settings: dict[str, Any] | None = None,
        available_features: dict[str, Any] | None = None,
        feature_mappings: list[dict[str, str]] | None = None,
        schema_template_path: str | None = None,
    ) -> None:
        """
        Initialize the index manager.

        Args:
            client: OpenSearch client instance
            index_name: Name of the index
            engine: KNN engine (faiss, lucene, nmslib, jvector)
            algorithm: KNN algorithm (hnsw, ivf)
            space_type: Similarity metric (l2, cosine, inner_product)
            engine_parameters: Custom engine-specific parameters
            index_settings: Custom index settings
            available_features: Feature configuration
            feature_mappings: Canonical list-of-dicts column to field mappings
            schema_template_path: Optional path to JSON schema template file
        """
        self.client = client
        self.index_name = index_name
        self.engine = engine
        self.algorithm = algorithm
        self.space_type = space_type
        self.engine_parameters = engine_parameters or {}
        self.index_settings = index_settings
        self.available_features = available_features or {}
        self.feature_mappings: list[dict[str, str]] = feature_mappings or []
        self._mapping_dict: dict[str, str] = build_mapping_dict(self.feature_mappings)
        self.schema_template_path = schema_template_path

        self._validate_engine_algorithm()

    def _validate_engine_algorithm(self) -> None:
        """Validate engine and algorithm compatibility."""
        if self.engine not in OpenSearchEngineTypes.ALL_ENGINES:
            raise DocpipeException(
                message=f"Invalid engine '{self.engine}'. Supported: {OpenSearchEngineTypes.ALL_ENGINES}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        if self.algorithm not in OpenSearchAlgorithmTypes.ALL_ALGORITHMS:
            raise DocpipeException(
                message=f"Invalid algorithm '{self.algorithm}'. Supported: {OpenSearchAlgorithmTypes.ALL_ALGORITHMS}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        supported_algorithms: list[str] = ENGINE_ALGORITHM_SUPPORT.get(self.engine, [])
        if self.algorithm not in supported_algorithms:
            raise DocpipeException(
                message=f"Algorithm '{self.algorithm}' not supported by engine '{self.engine}'. "
                f"Supported algorithms: {supported_algorithms}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

    def _get_engine_parameters(self) -> dict[str, Any]:
        """Get engine parameters, merging defaults with custom parameters."""
        param_key: tuple[str, str] = (self.engine, self.algorithm)
        default_params: dict[str, Any] = ENGINE_ALGORITHM_DEFAULT_PARAMETERS.get(param_key, {}).copy()

        if self.engine_parameters:
            default_params.update(self.engine_parameters)

        return default_params

    def _load_schema_template(self) -> dict[str, Any] | None:
        """
        Load JSON schema template from file path.

        Uses a hybrid approach:
        - Absolute paths: Load from filesystem
        - Relative paths: Load from package resources (schemas/ directory)
          Uses only the filename to prevent path traversal attacks

        Returns:
            Loaded schema dictionary, or None if file not found (triggers fallback)
        """
        if not self.schema_template_path:
            return None

        schema_path = Path(self.schema_template_path)

        # Load schema content
        try:
            if schema_path.is_absolute():
                # Absolute path: load from filesystem
                if not schema_path.exists():
                    logger.warning(
                        f"Schema template file not found: {schema_path}. Falling back to dynamic schema generation."
                    )
                    return None

                with Path(schema_path).open() as f:
                    schema = json.load(f)
                logger.info(f"Loaded schema template from filesystem: {schema_path}")
            else:
                # Relative path: load from package resources
                # Use only the filename to prevent path traversal
                template_name = schema_path.name
                try:
                    resource = files("docpipe.core.operators.vectordb").joinpath("schemas", template_name)

                    # Use as_file() for better compatibility with zipped wheels and containers
                    with as_file(resource) as resource_path:
                        with Path(resource_path).open() as f:
                            schema = json.load(f)

                    logger.info(f"Loaded schema template from package resources: schemas/{template_name}")
                except (FileNotFoundError, AttributeError) as e:
                    logger.warning(
                        f"Schema template not found in package resources: schemas/{template_name}. "
                        f"Falling back to dynamic schema generation. Error: {e}"
                    )
                    return None

            # Return schema without validation
            # Validation will happen in build_index_body() after placeholder replacement
            return deepcopy(schema)
        except json.JSONDecodeError as e:
            logger.warning(
                f"Invalid JSON in schema template {self.schema_template_path}: {e}. "
                f"Falling back to dynamic schema generation."
            )
            return None
        except Exception as e:
            logger.warning(
                f"Error loading schema template {self.schema_template_path}: {e}. "
                f"Falling back to dynamic schema generation."
            )
            return None

    def _replace_placeholders(self, *, obj: Any) -> Any:
        """
        Recursively replace placeholders in schema template.

        Placeholders:
            __ENGINE__ -> self.engine
            __ALGORITHM__ -> self.algorithm
            __SPACE_TYPE__ -> self.space_type
            __ENGINE_PARAMETERS__ -> self._get_engine_parameters()

        Args:
            obj: Object to process (dict, list, or primitive)

        Returns:
            Object with placeholders replaced
        """
        if isinstance(obj, dict):
            return {k: self._replace_placeholders(obj=v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._replace_placeholders(obj=item) for item in obj]
        if isinstance(obj, str):
            # Check if entire string is a placeholder
            if obj == "__ENGINE__":
                return self.engine
            if obj == "__ALGORITHM__":
                return self.algorithm
            if obj == "__SPACE_TYPE__":
                return self.space_type
            if obj == "__ENGINE_PARAMETERS__":
                return self._get_engine_parameters()

            # Otherwise, replace placeholders within string
            result = obj
            replacements = {
                "__ENGINE__": self.engine,
                "__ALGORITHM__": self.algorithm,
                "__SPACE_TYPE__": self.space_type,
            }
            for placeholder, value in replacements.items():
                if placeholder in result:
                    result = result.replace(placeholder, value)
            return result
        return obj

    def _validate_schema(self, *, schema: dict[str, Any]) -> None:
        """
        Validate schema structure and configuration.

        Validates:
        - Schema metadata (name, version)
        - Required OpenSearch sections
        - Vector field configuration
        - Parameter ranges
        - Nested field depth
        - Analyzer references

        Args:
            schema: Schema dictionary to validate

        Raises:
            DocpipeException: If schema validation fails
        """
        # A. Schema metadata validation
        if OperatorConstants.VectorDB.SCHEMA_KEY_SCHEMA_NAME not in schema:
            raise DocpipeException(
                message=f"Schema missing required '{OperatorConstants.VectorDB.SCHEMA_KEY_SCHEMA_NAME}' field",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        if OperatorConstants.VectorDB.SCHEMA_KEY_SCHEMA_VERSION not in schema:
            raise DocpipeException(
                message=f"Schema missing required '{OperatorConstants.VectorDB.SCHEMA_KEY_SCHEMA_VERSION}' field",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        # Validate version is positive integer
        schema_version = schema[OperatorConstants.VectorDB.SCHEMA_KEY_SCHEMA_VERSION]
        if not isinstance(schema_version, int) or schema_version <= 0:
            raise DocpipeException(
                message=f"Schema version must be a positive integer, got: {schema_version}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        # B. Required OpenSearch sections
        if OperatorConstants.VectorDB.SCHEMA_KEY_SETTINGS not in schema:
            raise DocpipeException(
                message=f"Schema missing required '{OperatorConstants.VectorDB.SCHEMA_KEY_SETTINGS}' section",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        # Schema can be either:
        # 1. Full schema with 'mappings' (complete field definitions)
        # 2. Template schema with 'field_types' (type templates for dynamic generation)
        has_mappings = OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS in schema
        has_field_types = OperatorConstants.VectorDB.SCHEMA_KEY_FIELD_TYPES in schema

        if not has_mappings and not has_field_types:
            raise DocpipeException(
                message=f"Schema must have either '{OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS}' (full schema) or '{OperatorConstants.VectorDB.SCHEMA_KEY_FIELD_TYPES}' (template schema)",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        # Validate full schema structure if mappings present
        if has_mappings:
            mappings = schema.get(OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS, {})
            if OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES not in mappings:
                raise DocpipeException(
                    message=f"Schema mappings missing required '{OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES}' section",
                    status_code=400,
                    error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
                )

        # Validate full schema structure (only for schemas with mappings)
        if has_mappings:
            # C. Vector field validation
            self._validate_vector_fields(schema=schema)
            # D. Parameter validation
            self._validate_parameters(schema=schema)
            # E. Nested field depth
            self._validate_field_depth(schema=schema)

        # F. Analyzer validation (for both full and template schemas)
        self._validate_analyzers(schema=schema)

    def _validate_vector_fields(self, *, schema: dict[str, Any]) -> None:
        """
        Validate vector field configuration in schema.
        Only called for full schemas with mappings.

        Args:
            schema: Schema dictionary to validate

        Raises:
            DocpipeException: If vector field validation fails
        """
        properties = schema.get(OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS, {}).get(
            OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES, {}
        )

        # Find all knn_vector fields
        vector_fields = []
        for field_name, field_config in properties.items():
            if (
                isinstance(field_config, dict)
                and field_config.get("type") == OperatorConstants.VectorDB.SCHEMA_KEY_KNN_VECTOR
            ):
                vector_fields.append((field_name, field_config))

        # Validate at least one vector field exists
        if not vector_fields:
            raise DocpipeException(
                message=f"Schema must contain at least one '{OperatorConstants.VectorDB.SCHEMA_KEY_KNN_VECTOR}' field",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        # Validate each vector field
        for field_name, field_config in vector_fields:
            # Validate dimension
            dimension = field_config.get("dimension")
            if dimension is None:
                raise DocpipeException(
                    message=f"Vector field '{field_name}' missing required 'dimension' property",
                    status_code=400,
                    error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
                )

            if not isinstance(dimension, int) or dimension <= 0:
                raise DocpipeException(
                    message=f"Vector field '{field_name}' dimension must be positive integer, got: {dimension}",
                    status_code=400,
                    error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
                )

            # Validate method configuration
            method = field_config.get("method", {})
            if not isinstance(method, dict):
                raise DocpipeException(
                    message=f"Vector field '{field_name}' method must be a dictionary",
                    status_code=400,
                    error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
                )

            # Validate engine
            engine = method.get("engine")
            if engine and engine not in OpenSearchEngineTypes.ALL_ENGINES:
                raise DocpipeException(
                    message=f"Vector field '{field_name}' has invalid engine '{engine}'. "
                    f"Supported: {OpenSearchEngineTypes.ALL_ENGINES}",
                    status_code=400,
                    error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
                )

            # Validate algorithm
            algorithm = method.get("name")
            if algorithm and algorithm not in OpenSearchAlgorithmTypes.ALL_ALGORITHMS:
                raise DocpipeException(
                    message=f"Vector field '{field_name}' has invalid algorithm '{algorithm}'. "
                    f"Supported: {OpenSearchAlgorithmTypes.ALL_ALGORITHMS}",
                    status_code=400,
                    error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
                )

            # Validate engine/algorithm compatibility
            if engine and algorithm:
                supported_algorithms = ENGINE_ALGORITHM_SUPPORT.get(engine, [])
                if algorithm not in supported_algorithms:
                    raise DocpipeException(
                        message=f"Vector field '{field_name}': algorithm '{algorithm}' not supported by engine '{engine}'. "
                        f"Supported algorithms: {supported_algorithms}",
                        status_code=400,
                        error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
                    )

    def _validate_parameters(self, *, schema: dict[str, Any]) -> None:
        """
        Validate parameter ranges for HNSW and IVF algorithms.

        Args:
            schema: Schema dictionary to validate
        """
        properties = schema.get(OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS, {}).get(
            OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES, {}
        )

        for field_name, field_config in properties.items():
            if (
                not isinstance(field_config, dict)
                or field_config.get("type") != OperatorConstants.VectorDB.SCHEMA_KEY_KNN_VECTOR
            ):
                continue

            method = field_config.get("method", {})
            algorithm = method.get("name")
            parameters = method.get("parameters", {})

            if not isinstance(parameters, dict):
                continue

            # HNSW parameter validation
            if algorithm == "hnsw":
                # m parameter
                m = parameters.get("m")
                if m is not None:
                    if not isinstance(m, int) or m < 2:
                        logger.warning(f"Vector field '{field_name}': HNSW parameter 'm' should be >= 2, got: {m}")
                    elif m < 4 or m > 64:
                        logger.warning(
                            f"Vector field '{field_name}': HNSW parameter 'm' outside optimal range [4-64], got: {m}"
                        )

                # ef_construction parameter
                ef_construction = parameters.get("ef_construction")
                if ef_construction is not None:
                    if not isinstance(ef_construction, int) or ef_construction < 1:
                        logger.warning(
                            f"Vector field '{field_name}': HNSW parameter 'ef_construction' should be >= 1, got: {ef_construction}"
                        )
                    elif ef_construction < 32 or ef_construction > 1024:
                        logger.warning(
                            f"Vector field '{field_name}': HNSW parameter 'ef_construction' outside optimal range [32-1024], got: {ef_construction}"
                        )

                # ef_search parameter
                ef_search = parameters.get("ef_search")
                if ef_search is not None:
                    if not isinstance(ef_search, int) or ef_search < 1:
                        logger.warning(
                            f"Vector field '{field_name}': HNSW parameter 'ef_search' should be >= 1, got: {ef_search}"
                        )
                    elif ef_search < 10 or ef_search > 2000:
                        logger.warning(
                            f"Vector field '{field_name}': HNSW parameter 'ef_search' outside optimal range [10-2000], got: {ef_search}"
                        )

            # IVF parameter validation
            elif algorithm == "ivf":
                # nlist parameter
                nlist = parameters.get("nlist")
                if nlist is not None:
                    if not isinstance(nlist, int) or nlist < 1:
                        logger.warning(
                            f"Vector field '{field_name}': IVF parameter 'nlist' should be >= 1, got: {nlist}"
                        )
                    elif nlist < 1 or nlist > 32768:
                        logger.warning(
                            f"Vector field '{field_name}': IVF parameter 'nlist' outside optimal range [1-32768], got: {nlist}"
                        )

                # nprobes parameter
                nprobes = parameters.get("nprobes")
                if nprobes is not None and nlist is not None:
                    if not isinstance(nprobes, int) or nprobes < 1:
                        logger.warning(
                            f"Vector field '{field_name}': IVF parameter 'nprobes' should be >= 1, got: {nprobes}"
                        )
                    elif nprobes > nlist:
                        logger.warning(
                            f"Vector field '{field_name}': IVF parameter 'nprobes' ({nprobes}) should be <= nlist ({nlist})"
                        )

    def _validate_field_depth(self, *, schema: dict[str, Any]) -> None:
        """
        Validate nested field depth and total field count.

        Args:
            schema: Schema dictionary to validate
        """
        properties = schema.get(OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS, {}).get(
            OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES, {}
        )

        def count_depth(obj: Any, current_depth: int = 0) -> int:
            """Recursively count maximum nesting depth."""
            if not isinstance(obj, dict):
                return current_depth

            max_depth = current_depth
            if OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES in obj:
                for prop_value in obj[OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES].values():
                    depth = count_depth(obj=prop_value, current_depth=current_depth + 1)
                    max_depth = max(max_depth, depth)

            return max_depth

        def count_fields(obj: Any) -> int:
            """Recursively count total number of fields."""
            if not isinstance(obj, dict):
                return 0

            count = 0
            if OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES in obj:
                count += len(obj[OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES])
                for prop_value in obj[OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES].values():
                    count += count_fields(obj=prop_value)

            return count

        # Check maximum nesting depth
        max_depth = count_depth(obj={OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES: properties})
        if max_depth > 3:
            logger.warning(
                f"Schema has deeply nested fields (depth: {max_depth}). "
                f"Consider flattening structure for better performance."
            )

        # Check total field count
        total_fields = count_fields(obj={OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES: properties})
        if total_fields > 1000:
            logger.warning(
                f"Schema has many fields (count: {total_fields}). Consider reducing field count for better performance."
            )

    def _validate_analyzers(self, *, schema: dict[str, Any]) -> None:
        """
        Validate analyzer references in schema.

        Args:
            schema: Schema dictionary to validate
        """
        settings = schema.get(OperatorConstants.VectorDB.SCHEMA_KEY_SETTINGS, {})
        analysis = settings.get(OperatorConstants.VectorDB.SCHEMA_KEY_ANALYSIS, {})

        # Get defined analyzers
        defined_analyzers = set()
        if "analyzer" in analysis:
            defined_analyzers.update(analysis["analyzer"].keys())

        # Check for analyzer references in mappings
        properties = schema.get(OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS, {}).get(
            OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES, {}
        )

        def check_analyzer_refs(obj: Any, path: str = "") -> None:
            """Recursively check analyzer references."""
            if not isinstance(obj, dict):
                return

            # Check if this field has an analyzer
            analyzer = obj.get("analyzer")
            if analyzer and isinstance(analyzer, str):
                # Check if it's a custom analyzer
                if analyzer not in ["standard", "simple", "whitespace", "stop", "keyword", "pattern", "fingerprint"]:
                    if analyzer not in defined_analyzers:
                        logger.warning(
                            f"Field '{path}' references undefined analyzer '{analyzer}'. "
                            f"Defined analyzers: {list(defined_analyzers)}"
                        )

            # Recursively check nested properties
            if OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES in obj:
                for prop_name, prop_value in obj[OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES].items():
                    new_path = f"{path}.{prop_name}" if path else prop_name
                    check_analyzer_refs(obj=prop_value, path=new_path)

            # Check fields (for multi-field mappings)
            if "fields" in obj:
                for field_name, field_value in obj["fields"].items():
                    new_path = f"{path}.{field_name}" if path else field_name
                    check_analyzer_refs(obj=field_value, path=new_path)

        check_analyzer_refs(obj={OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES: properties})

    def build_index_body(self, *, dimension_mapping: dict[str, int]) -> dict[str, Any]:
        """
        Build index body for OpenSearch.

        Args:
            dimension_mapping: Dictionary mapping vector column names to their dimensions

        Tries to use schema template if schema_template_path is provided.
        Falls back to dynamic generation if template not found or invalid.

        Returns:
            Complete index body with settings and mappings
        """
        # Try template-based approach if path provided
        if self.schema_template_path:
            loaded_schema = self._load_schema_template()

            if loaded_schema is not None:
                # Template loaded successfully
                logger.info(f"Building index body from schema template: {self.schema_template_path}")
                schema = self._replace_placeholders(obj=loaded_schema)

                if (
                    isinstance(schema, dict)
                    and OperatorConstants.VectorDB.SCHEMA_KEY_FIELD_TYPES in schema
                    and OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS not in schema
                ):
                    schema = self._build_index_body_from_field_type_template(
                        schema=schema, dimension_mapping=dimension_mapping
                    )

                # Inject runtime metadata (must happen before validation)
                if isinstance(schema, dict) and OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS in schema:
                    if (
                        OperatorConstants.VectorDB.SCHEMA_KEY_META
                        not in schema[OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS]
                    ):
                        schema[OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS][
                            OperatorConstants.VectorDB.SCHEMA_KEY_META
                        ] = {}
                    schema[OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS][
                        OperatorConstants.VectorDB.SCHEMA_KEY_META
                    ].update(
                        {
                            "engine": self.engine,
                            "algorithm": self.algorithm,
                            "space_type": self.space_type,
                            "created_by": "docling-pipelines",
                            OperatorConstants.Config.FEATURE_MAPPINGS: self.feature_mappings,
                        }
                    )

                # Validate schema only if it has schema_name and schema_version
                # (i.e., it's a formal schema template, not a test schema)
                # Validation happens AFTER placeholder replacement and _meta injection
                if (
                    OperatorConstants.VectorDB.SCHEMA_KEY_SCHEMA_NAME in schema
                    and OperatorConstants.VectorDB.SCHEMA_KEY_SCHEMA_VERSION in schema
                ):
                    self._validate_schema(schema=schema)

                # Return only OpenSearch-compatible sections (settings and mappings)
                # Remove metadata fields like schema_name, schema_version, field_types, indexing_rules
                index_body = {}
                if OperatorConstants.VectorDB.SCHEMA_KEY_SETTINGS in schema:
                    index_body[OperatorConstants.VectorDB.SCHEMA_KEY_SETTINGS] = schema[
                        OperatorConstants.VectorDB.SCHEMA_KEY_SETTINGS
                    ]
                if OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS in schema:
                    index_body[OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS] = schema[
                        OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS
                    ]

                return index_body

        # Fall back to dynamic generation
        logger.info("Building index body using dynamic feature mapping")
        index_body = self.create_index_mapping(dimension_mapping=dimension_mapping)

        # Add settings
        if self.index_settings:
            index_body[OperatorConstants.VectorDB.SCHEMA_KEY_SETTINGS] = self.index_settings
        else:
            index_body[OperatorConstants.VectorDB.SCHEMA_KEY_SETTINGS] = {
                "index": {
                    "knn": True,
                    "knn.algo_param.ef_search": 100,
                    "number_of_shards": 2,
                    "number_of_replicas": 1,
                }
            }

        return index_body

    def create_index_mapping(self, *, dimension_mapping: dict[str, int]) -> dict[str, Any]:
        """Create index mapping based on available features and feature mappings.

        Args:
            dimension_mapping: Dictionary mapping vector column names to their dimensions
        """
        properties: dict[str, Any] = {}

        # Process each feature
        for feature_name, feature_config in self.available_features.items():
            if not feature_config.get(OperatorConstants.Misc.FEATURE_ATTR_AVAILABLE_FOR_VECTOR_DB, False):
                continue

            mapped_name = self._mapping_dict.get(feature_name, feature_name)
            feature_type: str = feature_config.get("type", "text")

            # Map feature types to OpenSearch types
            if feature_type == "vector":
                # Get dimension for this specific vector column
                dimension = dimension_mapping.get(feature_name) or dimension_mapping.get(mapped_name)
                if dimension is None:
                    raise ValueError(
                        f"No dimension found for vector column '{feature_name}' (mapped to '{mapped_name}')"
                    )

                # Dense vector field with engine-specific configuration
                properties[mapped_name] = {
                    "type": OperatorConstants.VectorDB.SCHEMA_KEY_KNN_VECTOR,
                    "dimension": dimension,
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
            elif feature_type == "nested":
                properties[mapped_name] = {
                    "type": "nested",
                }
            elif feature_type in ("object", "json"):
                properties[mapped_name] = {
                    "type": "object",
                    "enabled": True,
                }
            else:
                properties[mapped_name] = {"type": "text"}

        # Add metadata object mapping for auto-aggregated metadata columns
        properties["metadata"] = {
            "type": "object",
            "dynamic": True,  # Allow dynamic fields in metadata
        }
        logger.debug("Added 'metadata' object mapping for auto-aggregated metadata columns")

        return {
            OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS: {
                OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES: properties,
                OperatorConstants.VectorDB.SCHEMA_KEY_META: {
                    "engine": self.engine,
                    "algorithm": self.algorithm,
                    "space_type": self.space_type,
                    "created_by": "docling-pipelines",
                    OperatorConstants.Config.FEATURE_MAPPINGS: self.feature_mappings,
                },
            }
        }

    def _build_index_body_from_field_type_template(
        self, *, schema: dict[str, Any], dimension_mapping: dict[str, int]
    ) -> dict[str, Any]:
        """
        Convert a field-type schema template into a valid OpenSearch index body.

        Args:
            schema: Schema template dictionary
            dimension_mapping: Dictionary mapping vector column names to their dimensions

        Supports schemas with or without settings or custom analysis blocks.
        Resolves configurations dynamically by matching features against indexing_rules.
        """
        logger.debug("Building index body using template schema: %s", schema.get("schema_name", "unknown"))

        # 1. Safely handle settings and drop empty/null analysis dictionaries
        schema_settings = deepcopy(schema.get(OperatorConstants.VectorDB.SCHEMA_KEY_SETTINGS, {}))
        analysis_settings = schema_settings.get(OperatorConstants.VectorDB.SCHEMA_KEY_ANALYSIS, {})
        if not analysis_settings or not analysis_settings.get("analyzer"):
            schema_settings.pop(OperatorConstants.VectorDB.SCHEMA_KEY_ANALYSIS, None)

        # 2. Add mapping explosion protection for dynamic metadata fields
        if "index" not in schema_settings:
            schema_settings["index"] = {}
        if "mapping.total_fields.limit" not in schema_settings["index"]:
            schema_settings["index"]["mapping.total_fields.limit"] = 2000
            logger.debug("Added mapping.total_fields.limit=2000 to prevent mapping explosion")

        index_body = {
            OperatorConstants.VectorDB.SCHEMA_KEY_SETTINGS: schema_settings,
            OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS: {OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES: {}},
        }

        properties = index_body[OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS][
            OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES
        ]
        field_types = schema.get(OperatorConstants.VectorDB.SCHEMA_KEY_FIELD_TYPES, {})
        indexing_rules = schema.get(OperatorConstants.VectorDB.SCHEMA_KEY_INDEXING_RULES, {})

        # 2. Map logical feature columns onto physical target structures
        for feature_name, feature_config in self.available_features.items():
            if not feature_config.get("available_for_vector_db", True):
                logger.debug("Skipping feature %s: Not available for VectorDB.", feature_name)
                continue

            mapped_name = self._mapping_dict.get(feature_name, feature_name)

            # Validate against reserved fields
            if mapped_name in RESERVED_FIELDS:
                logger.warning(
                    f"Skipping reserved field '{mapped_name}' (feature='{feature_name}'). "
                    f"Reserved fields: {RESERVED_FIELDS}"
                )
                continue

            system_type = feature_config.get("type", "string")

            # Dual lookup resolution pattern: Internal Logical Name -> Target Physical Name
            rule = indexing_rules.get(feature_name) or indexing_rules.get(mapped_name, {})
            target_field_type = rule.get("field_type", system_type)

            # Retrieve schema-defined property blueprint
            template_mapping = deepcopy(field_types.get(target_field_type))
            if not template_mapping:
                raise DocpipeException(
                    message=(
                        f"Unknown field type '{target_field_type}' for feature '{feature_name}' "
                        f"(mapped to '{mapped_name}'). Available field types in schema: "
                        f"{list(field_types.keys())}"
                    ),
                    status_code=400,
                    error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
                )

            # Filter property modifications using the validation allowlist
            overrides = {k: v for k, v in rule.items() if k in SUPPORTED_MAPPING_OVERRIDES}

            # Merge overrides into our mapping properties payload
            properties[mapped_name] = _deep_merge(base=template_mapping, override=overrides)

            # Override dimension for vector fields from runtime-detected dimension_mapping
            if properties[mapped_name].get("type") == OperatorConstants.VectorDB.SCHEMA_KEY_KNN_VECTOR:
                # Look up dimension using both feature_name and mapped_name
                dimension = dimension_mapping.get(feature_name) or dimension_mapping.get(mapped_name)
                if dimension is None:
                    raise ValueError(
                        f"No dimension found for vector column '{feature_name}' (mapped to '{mapped_name}') "
                        f"in dimension_mapping: {dimension_mapping}"
                    )
                properties[mapped_name]["dimension"] = dimension
                logger.debug(f"Applied runtime dimension {dimension} to vector field '{mapped_name}'")

        return index_body

    def update_feature_mappings_in_index(self) -> None:
        """Write feature_mappings into the index _meta block.

        Mirrors enterprise _update_new_feature_mappings_in_index(): called after
        every index create or validate so that _meta.feature_mappings always reflects
        the mappings active on the current run. This is the value Source 3 of
        VectorDBMetadataFetcher._resolve_opensearch_feature_mappings() reads back.

        Silently skips if index does not exist or if feature_mappings is empty.
        """
        if not self.feature_mappings:
            return
        try:
            self.client.indices.put_mapping(
                index=self.index_name,
                body={
                    OperatorConstants.VectorDB.SCHEMA_KEY_META: {
                        OperatorConstants.Config.FEATURE_MAPPINGS: self.feature_mappings
                    }
                },
            )
            logger.debug("Updated _meta.feature_mappings for index %s", self.index_name)
        except Exception as exc:
            logger.warning("Failed to update _meta.feature_mappings for index %s: %s", self.index_name, exc)

    def create_index(self, *, dimension_mapping: dict[str, int]) -> None:
        """
        Create the OpenSearch index if it doesn't exist.

        Args:
            dimension_mapping: Dictionary mapping vector column names to their dimensions

        Raises:
            DocpipeException: If index creation fails
        """
        if self.client.indices.exists(index=self.index_name):
            logger.info(f"Index {self.index_name} already exists")
            self.validate_existing_index(dimension_mapping=dimension_mapping)
            self.update_feature_mappings_in_index()
            return

        try:
            # Build index configuration
            index_body = self.build_index_body(dimension_mapping=dimension_mapping)

            logger.info(f"OpenSearch index body for '{self.index_name}': {json.dumps(index_body, default=str)}")

            # Create index
            self.client.indices.create(index=self.index_name, body=index_body)
            logger.info(f"Created index {self.index_name} with engine {self.engine} and algorithm {self.algorithm}")
            # feature_mappings already baked into _meta by build_index_body;
            # call update to keep _meta in sync if mappings changed since last run
            self.update_feature_mappings_in_index()
        except Exception as exc:
            # Handle race condition where another worker created the index between our check and create call
            error_msg = str(exc).lower()
            error_repr = repr(exc).lower()
            status_code = getattr(exc, "status_code", 0)

            # 1. Broad catch for already exists
            # (Matches: resource_already_exists, index_already_exists, "already exists", etc.)
            is_already_exists = (
                ("exists" in error_msg and ("already" in error_msg or status_code in [400, 409]))
                or ("exists" in error_repr and ("already" in error_repr or status_code in [400, 409]))
                or "resource_already_exists_exception" in error_msg
                or "resource_already_exists_exception" in error_repr
            )

            if is_already_exists:
                logger.info(f"Index '{self.index_name}' was created by another worker, validating and proceeding.")
                self.validate_existing_index(dimension_mapping=dimension_mapping)
                self.update_feature_mappings_in_index()
                return

            # 2. Diagnostic logging for genuine failures
            logger.error(
                f"Index creation failed with raw error: msg='{error_msg}', repr='{error_repr}', status={status_code}"
            )

            from docpipe.exceptions.docpipe_exceptions import DocpipeException
            from docpipe.exceptions.error_codes import ErrorCode

            raise DocpipeException(
                message=f"Failed to create OpenSearch index '{self.index_name}': {exc}",
                status_code=500,
                error_code=ErrorCode.OPENSEARCH_INDEX_ERROR,
                more_info=f"{TROUBLESHOOTING_DOCS_URL}#issue-opensearch-index-creation-failed",
            ) from exc

    def validate_existing_index(self, *, dimension_mapping: dict[str, int]) -> None:
        """Validate that existing index configuration matches requested settings and vector dimensions."""
        try:
            mappings: dict[str, Any] = self.client.indices.get_mapping(index=self.index_name)
            index_mappings: dict[str, Any] = mappings.get(self.index_name, {}).get(
                OperatorConstants.VectorDB.SCHEMA_KEY_MAPPINGS, {}
            )
            meta: dict[str, Any] = index_mappings.get(OperatorConstants.VectorDB.SCHEMA_KEY_META, {})
            properties: dict[str, Any] = index_mappings.get(OperatorConstants.VectorDB.SCHEMA_KEY_PROPERTIES, {})

            existing_engine: str | None = meta.get(OperatorConstants.VectorDB.ENGINE)
            existing_algorithm: str | None = meta.get(OperatorConstants.VectorDB.ALGORITHM)

            if existing_engine and existing_engine != self.engine:
                logger.warning(f"Engine mismatch: index has '{existing_engine}', config specifies '{self.engine}'")

            if existing_algorithm and existing_algorithm != self.algorithm:
                logger.warning(
                    f"Algorithm mismatch: index has '{existing_algorithm}', config specifies '{self.algorithm}'"
                )

            mismatches: list[str] = []
            for vector_column, runtime_dimension in dimension_mapping.items():
                mapped_field_name = self._mapping_dict.get(vector_column, vector_column)
                field_mapping = properties.get(mapped_field_name)

                if not field_mapping:
                    mismatches.append(
                        f"field '{mapped_field_name}' (source '{vector_column}') is missing from existing index mapping"
                    )
                    continue

                if field_mapping.get("type") != OperatorConstants.VectorDB.SCHEMA_KEY_KNN_VECTOR:
                    mismatches.append(
                        f"field '{mapped_field_name}' (source '{vector_column}') is not a "
                        f"{OperatorConstants.VectorDB.SCHEMA_KEY_KNN_VECTOR} field"
                    )
                    continue

                existing_dimension = field_mapping.get("dimension")
                if existing_dimension != runtime_dimension:
                    mismatches.append(
                        f"field '{mapped_field_name}' (source '{vector_column}') has existing dimension "
                        f"{existing_dimension} but current run produced {runtime_dimension}"
                    )

            if mismatches:
                raise DocpipeException(
                    message=(
                        f"Vector dimension mismatch for existing OpenSearch index '{self.index_name}': "
                        + "; ".join(mismatches)
                    ),
                    status_code=400,
                    error_code=ErrorCode.OPENSEARCH_INDEX_ERROR,
                    more_info=f"{TROUBLESHOOTING_DOCS_URL}#issue-opensearch-index-creation-failed",
                )
        except DocpipeException:
            raise
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
