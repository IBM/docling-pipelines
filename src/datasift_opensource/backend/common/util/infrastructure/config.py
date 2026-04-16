"""
Environment configuration utilities for OpenSearch and other services.
Loads configuration from .env file or environment variables.
"""

import os

from dotenv import load_dotenv

from common.constants.operator_constants import OperatorConstants

# Load .env file from project root
load_dotenv()


def get_opensearch_config() -> dict:
    """
    Load OpenSearch configuration from environment variables.

    Returns:
        dict: Configuration dictionary with all OpenSearch settings using vectordb_parameters pattern
    """

    def str_to_bool(value: str) -> bool:
        """Convert string to boolean."""
        return value.lower() in ("true", "1", "yes", "on")

    # OpenSearch-specific parameters go in vectordb_parameters
    vectordb_parameters: dict[str, str | bool] = {
        OperatorConstants.VectorDB.ENGINE: os.getenv("OPENSEARCH_ENGINE", "faiss"),
        OperatorConstants.VectorDB.ALGORITHM: os.getenv("OPENSEARCH_ALGORITHM", "hnsw"),
        OperatorConstants.VectorDB.SPACE_TYPE: os.getenv("OPENSEARCH_SPACE_TYPE", "l2"),
    }

    # Add AWS auth if configured
    if str_to_bool(os.getenv("OPENSEARCH_AWS_AUTH", "false")):
        vectordb_parameters[OperatorConstants.VectorDB.AWS_AUTH] = True
        vectordb_parameters[OperatorConstants.VectorDB.AWS_REGION] = os.getenv("OPENSEARCH_AWS_REGION", "us-east-1")

    # Add JWT token if configured
    jwt_token = os.getenv("OPENSEARCH_JWT_TOKEN")
    if jwt_token:
        vectordb_parameters[OperatorConstants.VectorDB.JWT_TOKEN] = jwt_token

    config = {
        # Connection settings
        "host": os.getenv("OPENSEARCH_HOST", "localhost"),
        "port": int(os.getenv("OPENSEARCH_PORT", "9200")),
        "use_ssl": str_to_bool(os.getenv("OPENSEARCH_USE_SSL", "false")),
        "verify_certs": str_to_bool(os.getenv("OPENSEARCH_VERIFY_CERTS", "false")),
        # Authentication
        "username": os.getenv("OPENSEARCH_USERNAME"),
        "password": os.getenv("OPENSEARCH_PASSWORD"),
        # Vector dimension
        "vector_dimension": int(os.getenv("OPENSEARCH_VECTOR_DIMENSION", "384")),
        # Performance settings
        "batch_size": int(os.getenv("OPENSEARCH_BATCH_SIZE", "100")),
        "create_index": str_to_bool(os.getenv("OPENSEARCH_CREATE_INDEX", "true")),
        # Index configuration
        "index_name": os.getenv("OPENSEARCH_INDEX_NAME", "datasift_test"),
        "doc_id_column": os.getenv("OPENSEARCH_DOC_ID_COLUMN", "doc_id_hash"),
        "embeddings_column": os.getenv("OPENSEARCH_EMBEDDINGS_COLUMN", "embeddings"),
        # OpenSearch-specific parameters
        OperatorConstants.VectorDB.VECTORDB_PARAMETERS: vectordb_parameters,
    }

    # Remove None values for optional parameters
    return {k: v for k, v in config.items() if v is not None}


def get_env_var(key: str, default: str | None = None) -> str | None:
    """
    Get environment variable value.

    Args:
        key: Environment variable key
        default: Default value if not found

    Returns:
        str: Environment variable value or default
    """
    return os.getenv(key, default)


def get_env_bool(key: str, default: bool = False) -> bool:
    """
    Get boolean environment variable value.

    Args:
        key: Environment variable key
        default: Default value if not found

    Returns:
        bool: Environment variable value as boolean
    """
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def get_env_int(key: str, default: int = 0) -> int:
    """
    Get integer environment variable value.

    Args:
        key: Environment variable key
        default: Default value if not found

    Returns:
        int: Environment variable value as integer
    """
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default
