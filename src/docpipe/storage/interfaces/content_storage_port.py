"""Content storage port — interface for storing and retrieving content by (collection, file_name)."""

from abc import ABC, abstractmethod


class ContentStoragePort(ABC):
    """
    Interface for content storage addressed by (collection, file_name).

    The storage path is always: <base_dir>/<collection>/<file_name>
    This is true for both filesystem and object-store backends (e.g. COS,
    where <collection>/<file_name> maps directly to the object key suffix).

    Collections represent logical groupings (e.g., job_id/job_run_id).
    file_name is the name of the content file within a collection
    (e.g., ``job_report_abc.csv``).

    Each storage backend implements ``check_data_availability`` according to
    its own storage model:
    - ``ContentFileSystemStorage``: checks for local parquet files under the
      collection directory.
    - A COS/S3 adapter would check the corresponding bucket prefix instead.

    docling-pipelines implementation: ContentFileSystemStorage
    """

    @abstractmethod
    def write_text(self, *, collection: str, file_name: str, content: str) -> str:
        """
        Write text content to storage.

        Args:
            collection: Logical grouping (e.g., ``job_id/job_run_id``)
            file_name: Name of the file within the collection (e.g., ``job_report_abc.csv``)
            content: Text content to write

        Returns:
            Storage path or object key where the content was written

        Raises:
            StorageValidationError: If collection or file_name is invalid
            DocpipeException: If the write operation fails
        """

    @abstractmethod
    def read_text(self, *, collection: str, file_name: str) -> str:
        """
        Read text content from storage.

        Args:
            collection: Logical grouping
            file_name: Name of the file within the collection

        Returns:
            Content as a string, or an empty string if the file does not exist.

        Raises:
            StorageValidationError: If collection or file_name is invalid
            DocpipeException: If the read operation fails

        Note:
            Implementations must return an empty string rather than raising
            when the file does not exist. This ensures consistent behavior across
            backends and allows callers to distinguish between "file not found"
            and actual read failures.
        """

    @abstractmethod
    def file_exists(self, *, collection: str, file_name: str) -> bool:
        """
        Check whether a file exists in storage.

        Args:
            collection: Logical grouping
            file_name: Name of the file within the collection

        Returns:
            True if the file exists, False otherwise
        """

    @abstractmethod
    def delete_file(self, *, collection: str, file_name: str) -> bool:
        """
        Delete a file from storage.

        Args:
            collection: Logical grouping
            file_name: Name of the file within the collection

        Returns:
            True if the file was deleted, False if it did not exist

        Raises:
            StorageValidationError: If collection or file_name is invalid
            DocpipeException: If the delete operation fails
        """

    @abstractmethod
    def check_data_availability(self, *, collection: str) -> tuple[bool, str]:
        """
        Check whether the underlying data required for report generation is
        available within the given collection.

        Each backend implements this according to its own storage model.
        For filesystem deployments this means checking for ingest parquet files.
        For object-store backends (COS, S3) this means checking the equivalent
        bucket prefix.

        Args:
            collection: Logical grouping identifying the job run data
                        (e.g. ``"{job_id}/{job_run_id}"``).

        Returns:
            Tuple of (is_available: bool, error_message: str).
            ``error_message`` is an empty string when ``is_available`` is True.
        """
