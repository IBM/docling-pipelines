"""Filesystem content storage implementation."""

from pathlib import Path
from typing import IO, Any, ClassVar

from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.storage.file_system.abstract_file_system_storage import AbstractFileSystemStorage
from docpipe.storage.interfaces.content_storage_port import ContentStoragePort
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ContentFileSystemStorage(AbstractFileSystemStorage, ContentStoragePort):
    """
    Thread-safe singleton filesystem storage for content files (CSV, TXT, etc.).

    Stores files at: {base_dir}/{collection}/{file_name}

    Implements the singleton pattern per base directory.

    Example:
        storage = ContentFileSystemStorage(base_dir="data/reports")
        storage.write_text(
            collection="job-id/job-run-id",
            file_name="job_report_abc.csv",
            content="GUID,File name,Status\\n..."
        )
        # Creates: data/reports/job-id/job-run-id/job_report_abc.csv
    """

    # Each subclass of AbstractFileSystemStorage has its own singleton registry
    _instances: ClassVar[dict[str, "ContentFileSystemStorage"]] = {}

    # ------------------------------------------------------------------
    # AbstractFileSystemStorage I/O hooks
    # ------------------------------------------------------------------

    def save_file_content(self, *, file: IO[str], data: Any) -> None:
        """Write content to ``file``."""
        file.write(data)

    def load_file_content(self, *, file: IO[str]) -> str:
        """Read and return the full content of ``file``."""
        return file.read()

    def _missing_file_value(self) -> str:
        """Return an empty string when a file does not exist."""
        return ""

    def list_files(self, *, collection: str) -> list[Any]:
        """
        List all files in a collection, returning their contents.

        Returns:
            List of file contents as strings; empty list if the collection does not exist
        """
        try:
            collection_dir = self._get_collection_dir(collection=collection)

            if not collection_dir.exists():
                return []

            contents = []
            for file_path in collection_dir.iterdir():
                if file_path.is_file():
                    try:
                        with Path(file_path).open(encoding="utf-8") as f:
                            contents.append(f.read())
                    except Exception as e:
                        logger.warning("Failed to read %s: %s", file_path.name, e)
                        continue

            logger.debug("Listed %s files from %s", len(contents), collection)
            return contents

        except Exception as e:
            raise DocpipeException(
                f"Failed to list files in {collection}: {e}",
                error_code=ErrorCode.STORAGE_ERROR,
            ) from e

    # ------------------------------------------------------------------
    # ContentStoragePort implementation — delegates to generic operations
    # ------------------------------------------------------------------

    def check_data_availability(self, *, collection: str) -> tuple[bool, str]:
        """
        Check whether ingest parquet files exist under the given collection.

        Parquet files are expected at:
            {base_dir}/{collection}/data/ingest*_0/output.parquet

        Args:
            collection: Sub-path of the form ``"{job_id}/{job_run_id}"``.

        Returns:
            Tuple of (is_available: bool, error_message: str).
        """
        data_dir = self._get_collection_dir(collection=collection) / "data"

        if not data_dir.exists():
            return False, f"Data directory not found: {data_dir}"

        ingest_dirs = list(data_dir.glob("ingest*_0"))
        if not ingest_dirs:
            return False, f"No ingest operator directory found in {data_dir}"

        for ingest_dir in ingest_dirs:
            parquet_file = ingest_dir / "output.parquet"
            if parquet_file.exists():
                logger.info("Found ingest parquet file: %s", parquet_file)
                return True, ""

        return False, f"No ingest parquet file found in {data_dir}"

    def write_text(self, *, collection: str, file_name: str, content: str) -> str:
        """Write content to a file. Delegates to write_file."""
        return self.write_file(collection=collection, file_name=file_name, data=content)

    def read_text(self, *, collection: str, file_name: str) -> str:
        """Read content from a file. Delegates to read_file."""
        return self.read_file(collection=collection, file_name=file_name)

    def file_exists(self, *, collection: str, file_name: str) -> bool:
        """Check whether a file exists. Delegates to base file_exists."""
        return super().file_exists(collection=collection, file_name=file_name)

    def delete_file(self, *, collection: str, file_name: str) -> bool:
        """Delete a file. Delegates to base delete_file."""
        return super().delete_file(collection=collection, file_name=file_name)
