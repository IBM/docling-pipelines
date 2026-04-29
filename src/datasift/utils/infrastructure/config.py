"""
Environment configuration utilities for OpenSearch and other services.
Loads configuration from .env file or environment variables.
"""

import os

from dotenv import load_dotenv

from datasift.core.constants.operator_constants import OperatorConstants

# Load .env file from project root
load_dotenv()


def get_opensearch_config() -> dict:
    """
    Load OpenSearch configuration from environment variables.

    Returns:
        dict: Configuration dictionary with all OpenSearch settings using provider_config pattern.
              All provider-specific parameters (including connection settings) are in provider_config.
    """

    def str_to_bool(value: str) -> bool:
        """Convert string to boolean."""
        return value.lower() in ("true", "1", "yes", "on")

    # All OpenSearch-specific parameters go in provider_config
    provider_config: dict[str, str | bool | int] = {
        # Connection settings
        OperatorConstants.VectorDB.HOST: os.getenv("OPENSEARCH_HOST", "localhost"),
        OperatorConstants.VectorDB.PORT: int(os.getenv("OPENSEARCH_PORT", "9200")),
        OperatorConstants.VectorDB.USE_SSL: str_to_bool(os.getenv("OPENSEARCH_USE_SSL", "false")),
        OperatorConstants.VectorDB.VERIFY_CERTS: str_to_bool(os.getenv("OPENSEARCH_VERIFY_CERTS", "false")),
        # KNN engine configuration
        OperatorConstants.VectorDB.ENGINE: os.getenv("OPENSEARCH_ENGINE", "faiss"),
        OperatorConstants.VectorDB.ALGORITHM: os.getenv("OPENSEARCH_ALGORITHM", "hnsw"),
        OperatorConstants.VectorDB.SPACE_TYPE: os.getenv("OPENSEARCH_SPACE_TYPE", "l2"),
        # Performance settings
        OperatorConstants.Config.BATCH_SIZE: int(os.getenv("OPENSEARCH_BATCH_SIZE", "100")),
    }

    # Add authentication if configured
    username = os.getenv("OPENSEARCH_USERNAME")
    if username:
        provider_config[OperatorConstants.VectorDB.USERNAME] = username

    password = os.getenv("OPENSEARCH_PASSWORD")
    if password:
        provider_config[OperatorConstants.VectorDB.PASSWORD] = password

    # Add AWS auth if configured
    if str_to_bool(os.getenv("OPENSEARCH_AWS_AUTH", "false")):
        provider_config[OperatorConstants.VectorDB.AWS_AUTH] = True
        provider_config[OperatorConstants.VectorDB.AWS_REGION] = os.getenv("OPENSEARCH_AWS_REGION", "us-east-1")

    # Add JWT token if configured
    jwt_token = os.getenv("OPENSEARCH_JWT_TOKEN")
    if jwt_token:
        provider_config[OperatorConstants.VectorDB.JWT_TOKEN] = jwt_token

    # Operator-level configuration (not provider-specific)
    config = {
        # Vector dimension
        OperatorConstants.VectorDB.VECTOR_DIMENSION: int(os.getenv("OPENSEARCH_VECTOR_DIMENSION", "384")),
        # Index settings
        OperatorConstants.VectorDB.CREATE_INDEX: str_to_bool(os.getenv("OPENSEARCH_CREATE_INDEX", "true")),
        OperatorConstants.VectorDB.INDEX_NAME: os.getenv("OPENSEARCH_INDEX_NAME", "datasift_test"),
        OperatorConstants.Columns.DOC_ID_COLUMN: os.getenv("OPENSEARCH_DOC_ID_COLUMN", "doc_id_hash"),
        OperatorConstants.Columns.EMBEDDINGS_COLUMN: os.getenv("OPENSEARCH_EMBEDDINGS_COLUMN", "embeddings"),
        # Provider-specific parameters
        OperatorConstants.Config.PROVIDER_CONFIG: provider_config,
    }

    return config


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
