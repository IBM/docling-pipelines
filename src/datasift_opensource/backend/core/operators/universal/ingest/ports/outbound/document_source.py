"""Document source port - Interface for fetching documents from external sources."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator

from pydantic import BaseModel

from ...domain.models import Document


class DocumentSourcePort(ABC):
    """
    Outbound port for document sources.

    This is the primary interface that all document source adapters must implement.
    It defines the contract between the domain layer and external document sources.

    Following Hexagonal Architecture principles:
    - This port is defined in the domain layer
    - Adapters implement this interface
    - The domain depends on this abstraction, not on concrete implementations
    """

    # Metadata for connector discovery and UI display
    SOURCE_NAME: str | None = None  # Unique identifier (e.g., "filesystem", "s3", "google_drive")
    SOURCE_DISPLAY_NAME: str | None = None  # Human-readable name (e.g., "Local Filesystem")
    SOURCE_DESCRIPTION: str | None = None  # Brief description
    SOURCE_VERSION: str = "1.0.0"  # Semantic version

    @abstractmethod
    async def fetch_documents(self, config: BaseModel) -> AsyncGenerator[Document, None]:
        """
        Fetch documents from the source.

        Args:
            config: Type-safe configuration (Pydantic model specific to this source)

        Yields:
            Document: Domain documents one at a time

        Raises:
            ConnectionError: If unable to connect to source
            AuthenticationError: If authentication fails
            ValueError: If configuration is invalid
        """
        pass

    @abstractmethod
    async def test_connection(self, config: BaseModel) -> tuple[bool, str]:
        """
        Test connection to the document source.

        Args:
            config: Type-safe configuration (Pydantic model specific to this source)

        Returns:
            Tuple[bool, str]: (success, message)
                - success: True if connection successful, False otherwise
                - message: Human-readable status message
        """
        pass

    @abstractmethod
    def get_config_schema(self) -> type[BaseModel]:
        """
        Get the Pydantic configuration model for this source.

        Returns:
            type[BaseModel]: The Pydantic model class for configuration
        """
        pass

    def get_metadata(self) -> dict:
        """
        Get metadata about this source for discovery and UI purposes.

        Returns:
            dict: Metadata including name, display name, description, version
        """
        return {
            "name": self.SOURCE_NAME,
            "display_name": self.SOURCE_DISPLAY_NAME,
            "description": self.SOURCE_DESCRIPTION,
            "version": self.SOURCE_VERSION,
            "config_schema": self.get_config_schema().schema() if self.get_config_schema() else None,
        }
