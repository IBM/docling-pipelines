"""Operator metadata API response Data Transfer Objects (DTOs).

This module defines Pydantic models for operator metadata API responses,
ensuring type safety, validation, and automatic OpenAPI schema generation.

Models:
    - OperatorFeature: Individual feature definition with type and metadata
    - OperatorMetadataItem: Complete operator metadata including features

Architecture:
    These DTOs are used by the router layer to convert raw metadata dictionaries
    from the service layer into properly typed, validated response models.

Validation:
    All models use centralized field definitions from field_definitions.py for:
    - String length constraints (min/max)
    - Pattern validation (regex)
    - Field descriptions for OpenAPI docs
    - Example values for API documentation

Usage:
    >>> # In router
    >>> raw_metadata = service.get_all_operator_metadata()
    >>> response = {
    ...     short_name: OperatorMetadataItem(
    ...         label=meta.get("label", short_name),
    ...         category=meta.get("category", "Unknown"),
    ...         ...
    ...     )
    ...     for short_name, meta in raw_metadata.items()
    ... }
"""

from typing import Any

from pydantic import BaseModel, Field

from docpipe.api.dto.field_definitions import (
    DESCRIPTION_PATTERN,
    OPERATOR_ATTRIBUTES_DESC,
    OPERATOR_ATTRIBUTES_MAX,
    OPERATOR_ATTRIBUTES_MIN,
    OPERATOR_CATEGORY_DESC,
    OPERATOR_CATEGORY_MAX_LENGTH,
    OPERATOR_CATEGORY_MIN_LENGTH,
    OPERATOR_CATEGORY_PATTERN,
    OPERATOR_DESCRIPTION_DESC,
    OPERATOR_DESCRIPTION_MAX_LENGTH,
    OPERATOR_DESCRIPTION_MIN_LENGTH,
    OPERATOR_FEATURE_DEFAULT_DESC,
    OPERATOR_FEATURE_DESCRIPTION_DESC,
    OPERATOR_FEATURE_DESCRIPTION_MAX_LENGTH,
    OPERATOR_FEATURE_DESCRIPTION_MIN_LENGTH,
    OPERATOR_FEATURE_FILTER_DESC,
    OPERATOR_FEATURE_IS_PRIMARY_DESC,
    OPERATOR_FEATURE_MANDATORY_VECTOR_DB_DESC,
    OPERATOR_FEATURE_NAME_DESC,
    OPERATOR_FEATURE_NAME_MAX_LENGTH,
    OPERATOR_FEATURE_NAME_MIN_LENGTH,
    OPERATOR_FEATURE_NAME_PATTERN,
    OPERATOR_FEATURE_OPENSEARCH_DESC,
    OPERATOR_FEATURE_PROPERTIES_DESC,
    OPERATOR_FEATURE_PROVIDERS_DESC,
    OPERATOR_FEATURE_REQUIRED_DESC,
    OPERATOR_FEATURE_TAGS_DESC,
    OPERATOR_FEATURE_VALID_VALUES_DESC,
    OPERATOR_FEATURE_VECTOR_DB_DESC,
    OPERATOR_FEATURES_DESC,
    OPERATOR_FEATURES_MAX,
    OPERATOR_FEATURES_MIN,
    OPERATOR_IS_AVAILABLE_DESC,
    OPERATOR_LABEL_DESC,
    OPERATOR_LABEL_MAX_LENGTH,
    OPERATOR_LABEL_MIN_LENGTH,
    OPERATOR_LABEL_PATTERN,
    OPERATOR_OWNER_DESC,
    OPERATOR_REQUIRED_FEATURES_DESC,
    OPERATOR_REQUIRED_FEATURES_MAX,
    OPERATOR_REQUIRED_FEATURES_MIN,
    OPERATOR_TYPE_DESC,
    OPERATOR_TYPE_MAX_LENGTH,
    OPERATOR_TYPE_MIN_LENGTH,
    OPERATOR_TYPE_PATTERN,
)


class OperatorFeature(BaseModel):
    """Individual operator feature definition.

    Represents a single feature (input or output) of an operator, including
    its data type, description, and usage flags.

    Features are the data fields that operators consume (inputs) or produce
    (outputs). For example:
    - extract_operator produces 'content' feature (string)
    - chunker requires 'content' feature and produces 'chunk_text' feature
    - embeddings requires 'chunk_text' and produces 'embeddings' feature (list)

    Attributes:
        type: Data type of the feature (string, int64, double, float, int32, boolean, list)
        description: Human-readable description of what the feature contains
        required: Whether this feature is required (for input features)
        default: Default value if feature is not provided
        available_for_filter: Can be used in SQL WHERE clauses for filtering
        available_for_vector_db: Can be stored in vector databases

    Example:
        >>> feature = OperatorFeature(
        ...     type="string",
        ...     description="Document content in markdown format",
        ...     required=True,
        ...     available_for_filter=True,
        ...     available_for_vector_db=False
        ... )
    """

    type: str = Field(
        min_length=OPERATOR_TYPE_MIN_LENGTH,
        max_length=OPERATOR_TYPE_MAX_LENGTH,
        pattern=OPERATOR_TYPE_PATTERN,
        description=OPERATOR_TYPE_DESC,
        examples=[
            "string",
            "int64",
            "int32",
            "int16",
            "int8",
            "double",
            "float",
            "boolean",
            "bool",
            "list",
            "json",
            "vector",
            "vector_sparse",
        ],
    )
    name: str | None = Field(
        default=None,
        min_length=OPERATOR_FEATURE_NAME_MIN_LENGTH,
        max_length=OPERATOR_FEATURE_NAME_MAX_LENGTH,
        description=OPERATOR_FEATURE_NAME_DESC,
    )
    description: str | None = Field(
        default=None,
        min_length=OPERATOR_FEATURE_DESCRIPTION_MIN_LENGTH,
        max_length=OPERATOR_FEATURE_DESCRIPTION_MAX_LENGTH,
        pattern=DESCRIPTION_PATTERN,
        description=OPERATOR_FEATURE_DESCRIPTION_DESC,
    )
    required: bool | None = Field(default=None, description=OPERATOR_FEATURE_REQUIRED_DESC)
    default: Any | None = Field(default=None, description=OPERATOR_FEATURE_DEFAULT_DESC)
    available_for_filter: bool | None = Field(default=None, description=OPERATOR_FEATURE_FILTER_DESC)
    available_for_vector_db: bool | None = Field(default=None, description=OPERATOR_FEATURE_VECTOR_DB_DESC)
    available_for_opensearch: bool | None = Field(default=None, description=OPERATOR_FEATURE_OPENSEARCH_DESC)
    mandatory_for_vector_db: bool | None = Field(default=None, description=OPERATOR_FEATURE_MANDATORY_VECTOR_DB_DESC)
    is_primary: bool | None = Field(default=None, description=OPERATOR_FEATURE_IS_PRIMARY_DESC)
    tags: list[str] | None = Field(default=None, description=OPERATOR_FEATURE_TAGS_DESC)
    properties: dict[str, Any] | None = Field(default=None, description=OPERATOR_FEATURE_PROPERTIES_DESC)
    valid_values: list[Any] | None = Field(default=None, description=OPERATOR_FEATURE_VALID_VALUES_DESC)
    providers: dict[str, Any] | None = Field(default=None, description=OPERATOR_FEATURE_PROVIDERS_DESC)


class OperatorMetadataItem(BaseModel):
    """Complete metadata for a single operator.

    Contains all information needed to understand and use an operator,
    including its category, features, requirements, and configuration attributes.

    This model is used in the API response to provide the UI with:
    - Display information (label, description)
    - Categorization (category)
    - Available features (features dict)
    - Input requirements (required_features list)
    - Configuration attributes (attributes dict)

    Attributes:
        label: Human-readable operator name (e.g., "Extract Docling", "Chunker")
        category: Operator category (Extract, Ingest, Functional, Quality, VectorDB, Unknown)
        description: Detailed description of what the operator does
        features: Dictionary mapping feature names to OperatorFeature definitions
        required_features: List of feature names that must be provided as input
        attributes: Dictionary mapping attribute names to OperatorFeature definitions (configuration parameters)

    Example:
        >>> metadata = OperatorMetadataItem(
        ...     label="Extract Docling",
        ...     category="Extract",
        ...     description="Extracts structured content from documents",
        ...     features={
        ...         "content": OperatorFeature(
        ...             type="string",
        ...             description="Extracted markdown content"
        ...         )
        ...     },
        ...     required_features=[],
        ...     attributes={
        ...         "text_extraction": OperatorFeature(
        ...             type="json",
        ...             description="Text extraction configuration with provider and settings",
        ...             required=True,
        ...             default={"provider": "docling_library", "doc_column": "doc_content"}
        ...         )
        ...     }
        ... )

    Note:
        - label defaults to operator short name if not provided
        - category defaults to "Unknown" if not provided
        - description is optional (None if not provided)
        - features defaults to empty dict
        - required_features defaults to empty list
        - attributes defaults to empty dict
    """

    label: str = Field(
        min_length=OPERATOR_LABEL_MIN_LENGTH,
        max_length=OPERATOR_LABEL_MAX_LENGTH,
        pattern=OPERATOR_LABEL_PATTERN,
        description=OPERATOR_LABEL_DESC,
        examples=["Entity Extraction (Ollama)", "Extract Docling", "Chunking", "ML Text Enrichment"],
    )
    category: str = Field(
        min_length=OPERATOR_CATEGORY_MIN_LENGTH,
        max_length=OPERATOR_CATEGORY_MAX_LENGTH,
        pattern=OPERATOR_CATEGORY_PATTERN,
        description=OPERATOR_CATEGORY_DESC,
        examples=["Extract", "Ingest", "Functional", "Quality", "VectorDB", "Storage", "Custom"],
    )
    description: str | None = Field(
        default=None,
        min_length=OPERATOR_DESCRIPTION_MIN_LENGTH,
        max_length=OPERATOR_DESCRIPTION_MAX_LENGTH,
        pattern=DESCRIPTION_PATTERN,
        description=OPERATOR_DESCRIPTION_DESC,
    )
    features: dict[str, OperatorFeature] = Field(
        default_factory=dict,
        description=OPERATOR_FEATURES_DESC,
        json_schema_extra={"minProperties": OPERATOR_FEATURES_MIN, "maxProperties": OPERATOR_FEATURES_MAX},
    )
    required_features: list[str] = Field(
        default_factory=list,
        min_length=OPERATOR_REQUIRED_FEATURES_MIN,
        max_length=OPERATOR_REQUIRED_FEATURES_MAX,
        description=OPERATOR_REQUIRED_FEATURES_DESC,
        json_schema_extra={
            "minItems": OPERATOR_REQUIRED_FEATURES_MIN,
            "maxItems": OPERATOR_REQUIRED_FEATURES_MAX,
            "items": {
                "type": "string",
                "minLength": OPERATOR_FEATURE_NAME_MIN_LENGTH,
                "maxLength": OPERATOR_FEATURE_NAME_MAX_LENGTH,
                "pattern": OPERATOR_FEATURE_NAME_PATTERN,
            },
        },
    )
    attributes: dict[str, OperatorFeature] = Field(
        default_factory=dict,
        description=OPERATOR_ATTRIBUTES_DESC,
        json_schema_extra={"minProperties": OPERATOR_ATTRIBUTES_MIN, "maxProperties": OPERATOR_ATTRIBUTES_MAX},
    )
    owner: str | None = Field(default=None, description=OPERATOR_OWNER_DESC)
    is_operator_available: bool | None = Field(default=None, description=OPERATOR_IS_AVAILABLE_DESC)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "label": "Entity Extraction (Ollama)",
                    "category": "Extract",
                    "description": "Extracts structured entities from document text using a locally running Ollama LLM, guided by a user-provided JSON schema template.",
                    "features": {
                        "entities": {
                            "type": "string",
                            "description": "JSON string of extracted entities matching the provided schema.",
                            "required": None,
                            "default": None,
                            "available_for_filter": True,
                            "available_for_vector_db": True,
                        },
                        "doc_id_hash": {
                            "type": "string",
                            "description": "Unique hash identifier for the document.",
                            "required": None,
                            "default": None,
                            "available_for_filter": None,
                            "available_for_vector_db": True,
                        },
                    },
                    "required_features": [],
                    "attributes": {
                        "text_extraction": {
                            "type": "object",
                            "description": "Text extraction configuration with provider and settings",
                            "required": False,
                            "default": {"provider": "docling_library", "doc_column": "doc_content"},
                            "available_for_filter": None,
                            "available_for_vector_db": None,
                        },
                        "entity_extraction": {
                            "type": "object",
                            "description": "Entity extraction configuration with provider and settings",
                            "required": False,
                            "default": {"provider": "none"},
                            "available_for_filter": None,
                            "available_for_vector_db": None,
                        },
                    },
                }
            ]
        }
    }
