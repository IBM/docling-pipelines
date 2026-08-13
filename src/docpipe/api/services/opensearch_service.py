"""OpenSearch service for document retrieval with ACL enforcement."""

import logging

from opensearchpy import OpenSearch
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class OpenSearchConfig(BaseSettings):
    """OpenSearch configuration settings."""

    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    opensearch_use_ssl: bool = False
    opensearch_verify_certs: bool = False
    opensearch_username: str = ""
    opensearch_password: str = ""
    opensearch_default_index: str = "documents"
    opensearch_timeout: int = 30
    opensearch_max_retries: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_credentials(self) -> "OpenSearchConfig":
        """Reject configuration with empty credentials."""
        if not self.opensearch_username or not self.opensearch_password:
            raise ValueError(
                "OpenSearch credentials must be provided via environment variables "
                "(OPENSEARCH_USERNAME and OPENSEARCH_PASSWORD)"
            )
        return self


class OpenSearchService:
    """Service for managing OpenSearch connections and operations."""

    def __init__(self, *, config: OpenSearchConfig | None = None):
        """Initialize the service, loading configuration from the environment if not provided."""
        self.config = config or OpenSearchConfig()
        self._client: OpenSearch | None = None
        logger.info(
            "OpenSearch service initialized for %s:%d",
            self.config.opensearch_host,
            self.config.opensearch_port,
        )

    def get_client(self) -> OpenSearch:
        """Get or create OpenSearch client with connection pooling.

        Returns:
            OpenSearch client instance

        Raises:
            Exception: If connection to OpenSearch fails
        """
        if self._client is None:
            try:
                self._client = OpenSearch(
                    hosts=[
                        {
                            "host": self.config.opensearch_host,
                            "port": self.config.opensearch_port,
                        }
                    ],
                    http_auth=(
                        self.config.opensearch_username,
                        self.config.opensearch_password,
                    ),
                    use_ssl=self.config.opensearch_use_ssl,
                    verify_certs=self.config.opensearch_verify_certs,
                    ssl_show_warn=False,
                    timeout=self.config.opensearch_timeout,
                    max_retries=self.config.opensearch_max_retries,
                    retry_on_timeout=True,
                )
                logger.info("OpenSearch client created successfully")
            except Exception as e:
                logger.error("Failed to create OpenSearch client: %s", e)
                raise

        return self._client

    def health_check(self) -> bool:
        """Check OpenSearch cluster health.

        Returns:
            True if cluster is healthy, False otherwise
        """
        try:
            client = self.get_client()
            health = client.cluster.health()
            status = health.get("status", "red")
            logger.info("OpenSearch cluster health: %s", status)
            return status in ["green", "yellow"]
        except Exception as e:
            logger.error("OpenSearch health check failed: %s", e)
            return False

    def index_exists(self, *, index_name: str) -> bool:
        """Check if an index exists.

        Args:
            index_name: Name of the index to check

        Returns:
            True if index exists, False otherwise
        """
        try:
            client = self.get_client()
            exists = client.indices.exists(index=index_name)
            logger.debug("Index '%s' exists: %s", index_name, exists)
            return exists
        except Exception as e:
            logger.error("Error checking index existence: %s", e)
            return False

    def close(self) -> None:
        """Close and release the OpenSearch client connection."""
        if self._client is not None:
            try:
                self._client.close()
                logger.info("OpenSearch client connection closed")
            except Exception as e:
                logger.error("Error closing OpenSearch client: %s", e)
            finally:
                self._client = None


# Dependency for FastAPI
def get_opensearch_service() -> OpenSearchService:
    """FastAPI dependency to get OpenSearch service instance.

    Returns:
        OpenSearchService instance
    """
    return OpenSearchService()
