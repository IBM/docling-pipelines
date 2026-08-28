"""DocumentSetStorage port interface.

Defines the abstract contract for the data-plane storage of document sets.
Implementations write/read PyArrow table data to a backend-specific store and
return an AttachmentRef describing where the data lives.

Example backends:
  - DuckDB: writes to a DuckDB table, returns AttachmentRef with
    name=table_name and details={"database_path": ..., "table_name": ...}.
"""

from abc import ABC, abstractmethod
from typing import Any

import pyarrow as pa

from docpipe.core.assets.common.domain.models.attachment_ref import AttachmentRef
from docpipe.core.assets.document_sets.domain.types import HealthCheckResult


class DocumentSetStorage(ABC):
    """Abstract port for document set data-plane operations.

    Implementations handle writing and reading the actual PyArrow table data.
    The caller never specifies table names or database paths — the adapter
    derives those from ``doc_set_name`` and its own configuration, then returns
    an ``AttachmentRef`` describing where the data was stored.
    """

    @abstractmethod
    def store(self, *, doc_set_name: str, data: pa.Table) -> AttachmentRef:
        """Write PyArrow table data and return an AttachmentRef.

        Creates the backing table if it does not exist, otherwise upserts on
        the ``id`` column.

        Args:
            doc_set_name: Logical name of the document set (used to derive the
                physical table/path name).
            data: PyArrow table to persist. Must contain an ``id`` column.

        Returns:
            AttachmentRef populated with backend-specific coordinates.

        Raises:
            DocpipeException: If the data is invalid or the write fails.
        """
        ...

    @abstractmethod
    def load(self, *, attachment_ref: AttachmentRef, limit: int | None = None) -> pa.Table:
        """Read PyArrow table data from the location described by attachment_ref.

        Args:
            attachment_ref: AttachmentRef returned by a previous ``store()`` call.
            limit: Maximum number of rows to return, or None for all rows.

        Returns:
            PyArrow table containing the requested data.

        Raises:
            DocpipeException: If the attachment ref is invalid or the read fails.
        """
        ...

    @abstractmethod
    def delete(self, *, attachment_ref: AttachmentRef) -> bool:
        """Drop the backing table/resource described by attachment_ref.

        Args:
            attachment_ref: AttachmentRef identifying what to delete.

        Returns:
            True if the resource existed and was deleted, False if it was absent.

        Raises:
            DocpipeException: If the deletion fails.
        """
        ...

    @abstractmethod
    def get_metrics(self, *, attachment_ref: AttachmentRef) -> dict[str, int]:
        """Compute aggregate metrics for the stored data.

        Args:
            attachment_ref: AttachmentRef identifying the backing resource.

        Returns:
            Dictionary with keys: total_documents, total_size_bytes, total_pages.

        Raises:
            DocpipeException: If the attachment ref is invalid or computation fails.
        """
        ...

    @abstractmethod
    def exists(self, *, attachment_ref: AttachmentRef) -> bool:
        """Check whether the backing resource described by attachment_ref exists.

        Args:
            attachment_ref: AttachmentRef to check.

        Returns:
            True if the resource exists, False otherwise.
        """
        ...

    @abstractmethod
    def health_check(self) -> HealthCheckResult:
        """Check the health status of the storage backend.

        Returns:
            HealthCheckResult with healthy flag, message, and optional details.
            Must not raise; errors must be reflected in the result.
        """
        ...

    @classmethod
    @abstractmethod
    def validate_config(cls, *, config: dict[str, Any]) -> list[str]:
        """Validate adapter configuration before instantiation.

        Args:
            config: Configuration dictionary (e.g. {"database_path": "..."}).

        Returns:
            List of validation error messages; empty if configuration is valid.
        """
        ...
