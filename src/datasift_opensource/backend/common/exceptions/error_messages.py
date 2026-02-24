from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict

class ValidationMessage(BaseModel):
    """
    this class can be used to bind together validation error message and its extra arguments for validation alert model

    """
    message: Optional[str] = None
    message_code : Optional[str] = None

    model_config = ConfigDict(extra='allow')


    @classmethod
    def create(cls, message: str, message_code: Optional[str] = None, **kwargs)-> "ValidationMessage":
        """
        Factory method to create a ValidationMessage with extra attributes.

        Args:
            message (str): The validation message.
            message_code (Optional[str]): Optional code for the message.
            **extras (Any): Any additional fields to include.

        Returns:
            ValidationMessage: An instance of the class with all fields.
        """
        return cls(message=message, message_code=message_code, **kwargs)




class ValidationCodeMessages(str, Enum):
    MISSING_FEATURES= """Not all required features for {operator_name} operator are available - required: {missing_features},
        Missing one or more operators:  {missing_operators}, 
        Please consider adding the missing operators to ensure full functionality
        """

    MISSING_COLUMNS= """Not all required columns for {operator_name} operator are present in the table - required {missing_features},
        Missing one or more operators:  {missing_operators},
        Please consider adding the missing operators to ensure full functionality """

    MISSING_SEQUENCE_PIPELINE= """The sequence pipeline is missing in the flow definition."""

    OPERATOR_NAME_REPEATED="""Same operator name(s) are used for multiple operators, operator(s): {operators}"""

    MISSING_MODEL_ID_FOR_EMBEDDINGS = """Missing model id for generating embeddings. Model ID not found in project settings or configuration."""
    
    INVALID_EMBEDDINGS_MODEL_ID = """Invalid embeddings model ID '{model_id}'. This model is not available to generate embeddings. Please verify the model ID."""
    
    FOUNDATION_MODELS_UNAVAILABLE = """Unable to retrieve foundation models in this environment."""

    EXTRACT_OPERATOR_MISSING="""Extract operator is either missing or not connected in the flow."""

    CHUNKER_OPERATOR_MISSING="""Chunker operator is either missing or not connected in the flow or is placed after the Embeddings operator."""

    INGEST_OPERATOR_MISPLACED = """The first operator in the flow must be an "Ingest data" operator"""

    GENERATE_OUTPUT_MISSING="""The last operator is not a "Generate Output" operator"""

    MULTIPLE_EXTRACTED_DETECTED = """Multiple extract operators detected. Ensure they are used correctly"""

    PIPELINE_NOT_FOUND_ERROR="""Flow must have 'dag'."""

    DAG_PIPELINE_MISSING = """The DAG pipeline is empty or missing."""

    MISSING_NODE_ID = """ID is missing for the node"""

    MISSING_NODE_NAME = """Name is missing for the node"""

    GET_OPERATOR_FAILED="""Failed to get operator."""

    SQL_FILTER_ID_DROP_ATTEMPTED="""ID column drop was attempted"""

    SQL_FILTER_CONTENT_DROP_ATTEMPTED="""Content column drop was attempted"""

    SQL_FILTER_PAGES_DROP="""Pages Processed column drop was attempted"""

    SQL_FILTER_INVALID_COLUMN="""Invalid column name. Please ensure the filter_criteria has correct column names"""

    MILVUS_COLLECTION_NAME_NOT_PROVIDED ="""The collection name is not provided."""

    MILVUS_FEATURE_MAPPING_MISSING="""The mappings from features to the collection columns is not provided."""

    MILVUS_INVALID_FEATURE_MAPPING="""f"Some of the features in the feature mappings are not available: {missing_features}"""

    MILVUS_COLLECTION_COLUMN_NOT_MAPPED = """The collection column is not mapped for the feature '{feature_name}'"""

    MILVUS_VECTOR_COLUMN_MISSING = """f"No column of type {column_name} found in the feature mappings. A vector type column is required."""

    MILVUS_SPARSE_COLUMN_MISSING= """f"No column of type {column_name} found in the existing collection. A sparse vector type column is required."""

    MILVUS_CONTENT_COLUMN_NOT_FOUND ="""Content column '{content_column}' is not found in the feature mappings. Content column mapping is required when using sparse vectors."""

    MILVUS_PRIMARY_KEY_NOT_FOUND="""No primary key column found in the feature mappings. A primary key column is required."""

    MILVUS_COLLECTION_COLUMN_INVALID = """The collection does not have required fields: {expected_columns}. The present schema is: {collection_columns_for_validation}."""

    MILVUS_VECTOR_FIELD_CANNOT_BE_CREATED_DYNAMICALLY = (
        "Column '{column_name}' of type '{feature_type}' is not present in the '{collection_name}' collection. "
        "Vector fields cannot be created dynamically and must be defined in the collection schema."
    )

    MILVUS_COLUMN_NAME_NOT_PRESENT_IN_COLLECTION = """Column '{column_name}' is not present in the '{collection_name}' collection."""

    MILVUS_FEATURE_COLUMN_MAPPING_TYPE_MISMATCH= """Mismatch of types for the mapping between feature '{feature_name}' of type '{feature_type}' and collection column '{column_name}' of type '{column_type}'."""

    MILVUS_PRIMARY_FEATURE_TO_COLUMN_NOT_MAPPED="""{primary_feature} feature is not mapped to the primary key column {primary_column_name}."""

    MILVUS_VECTOR_DIMENSION_SCHEMA_DIMENSION_MISSMATCH="""The input vector dimension {dimensions} do not match with the existing schema dimension, {schema_dimension}."""

    MILVUS_MANDATORY_FEATURE_MAPPING_MISSING="""Mappings are missing for mandatory features: {missing_features}"""

    CHUNKER_INVALID_CHUNK_TYPE="Invalid chunk_type: {chunk_type}"

    CHUNKER_OPERATOR_MISPLACED = "Invalid Flow definition. Chunking operator placed after Embeddings operator. Please rearrange the chunking operator in the flow"

    EMBEDDINGS_INVALID_TYPE= "Invalid embeddings type: {embeddings_type}"

    DROPPING_MANDATORY_FEATURES = "Mandatory features drop attempted: {mandatory_features} By node: '{operator}', mandatory features cannot be dropped"

    RENAMING_MANDATORY_FEATURES = "Mandatory features rename attempted: {mandatory_features}, renaming of mandatory features is not allowed"

    PARAMETERS_MISSING_IN_SOURCE = """Parameter/s {parameters} cannot be found in {parameter_source}."""

    PARAMETERS_WITH_INCORRECT_TYPE = """Parameter/s {parameters} have incorrect type."""

    CONNECTION_BINARY_READ = """Connectivity Service Error. Failed to retrieve binary content."""

    FLIGHT_UNAVAILABLE_ERROR = """Failed to connect to Flight service. Please check network connectivity or Flight service availability."""

    FLIGHT_FILE_RETRIEVAL_ERROR = """Error occurred while retrieving file '{path}' from flight: {error}"""

    DISJOINT_OPERATORS_DETECTED = """Flow contains disconnected operators. Ensure every operator has valid input and output connections."""

    MISSING_CATALOG_OR_SCHEMA = """{operator} Operator missing either catalog name or schema name or both. Please add valid names."""

    ENTITY_EXTRACTION_MISSING = """Ensure Entity Extraction is enabled for the Extract Data Operator."""