"""Port interface for vector database services.

This port defines the contract that all vector database adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import Any

import pyarrow as pa


class VectorStorePort(ABC):
    """Port interface for vector database services.

    This interface defines the contract for vector database operations.
    Adapters implementing this port handle provider-specific details while
    the operator depends only on this abstraction.

    Attributes:
        ADAPTER_NAME: Unique identifier for the adapter (e.g., 'opensearch')
        ADAPTER_DISPLAY_NAME: Human-readable name for UI display
    """

    ADAPTER_NAME: str
    ADAPTER_DISPLAY_NAME: str

    @abstractmethod
    def index_documents(self, documents: list[tuple[str, dict[str, Any]]]) -> tuple[int, list[dict[str, Any]]]:
        """Index documents in the vector database.

        Args:
            documents: List of (doc_id, document_dict) tuples to index

        Returns:
            Tuple of (success_count, failed_items)

        Raises:
            Exception: If indexing operation fails
        """
        pass

    @abstractmethod
    def query_by_doc_names(self, doc_names: list[str], fields: list[str] | None = None) -> list[dict[str, Any]]:
        """Query documents by their names.

        Args:
            doc_names: List of document names to query
            fields: Optional list of fields to return

        Returns:
            List of matching documents

        Raises:
            Exception: If query operation fails
        """
        pass

    @abstractmethod
    def delete_documents_by_ids(self, doc_ids: list[str]) -> tuple[int, int]:
        """Delete documents by their IDs.

        Args:
            doc_ids: List of document IDs to delete

        Returns:
            Tuple of (success_count, failed_count)

        Raises:
            Exception: If delete operation fails
        """
        pass

    @abstractmethod
    def get_document_count(self) -> int:
        """Get total document count in the index.

        Returns:
            Number of documents in the index

        Raises:
            Exception: If count operation fails
        """
        pass

    @abstractmethod
    def create_index(self, *, dimension_mapping: dict[str, int]) -> None:
        """Create the vector database index if it doesn't exist.

        Args:
            dimension_mapping: Dictionary mapping vector column names to their dimensions

        Raises:
            Exception: If index creation fails
        """
        pass

    @abstractmethod
    def refresh_index(self) -> None:
        """Refresh the index to make recent changes visible.

        Raises:
            Exception: If refresh operation fails
        """
        pass

    @abstractmethod
    def index_exists(self) -> bool:
        """Check if the vector database index already exists.

        Returns:
            True if index exists, False otherwise
        """
        pass

    @abstractmethod
    def detect_vector_dimension(self, *, table: pa.Table, column_name: str | None = None) -> int | None:
        """Detect vector dimension from embeddings data.

        Args:
            table: PyArrow table containing embeddings
            column_name: Optional specific column to detect dimension for.
                        If None, uses default embeddings column.

        Returns:
            Detected dimension or None if detection fails
        """
        pass

    @abstractmethod
    def detect_all_vector_dimensions(self, table: pa.Table, *, vector_columns: list[str]) -> dict[str, int]:
        """Detect dimensions for all specified vector columns.

        Args:
            table: PyArrow table containing embeddings
            vector_columns: List of column names to detect dimensions for

        Returns:
            Dictionary mapping column names to their detected dimensions
        """
        pass
