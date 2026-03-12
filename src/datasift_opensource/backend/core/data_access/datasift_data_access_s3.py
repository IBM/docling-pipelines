"""
DataAccess implementation for AWS S3 with session token support.
"""

from typing import Any

import pyarrow as pa
import pyarrow.fs as fs
import pyarrow.parquet as pq
from data_processing.data_access import DataAccess
from data_processing.utils import TransformUtils

from common.constants.constants import DatasiftConstants
from common.exceptions.datasift_exceptions import DatasiftException, ErrorCode
from common.util.log import get_logger
from common.util.retry_utils import retry_with_exponential_backoff

logger = get_logger(__name__)


class DatasiftDataAccessS3(DataAccess):
    """
    Implementation of DataAccess for AWS S3 with support for session tokens.
    This extends the base DataAccess class to work with MCSP temporary credentials.
    Uses PyArrow's S3FileSystem which supports session tokens natively.
    """

    def __init__(
        self,
        config: dict[str, str] | None = None,
        d_sets: list[str] | None = None,
        checkpoint: bool = False,
        m_files: int = -1,
        n_samples: int = -1,
        batch_size: int = -1,
        files_to_use: list[str] | None = None,
        files_to_checkpoint: list[str] | None = None,
        s3_max_retries: int = 3,
        s3_backoff_factor: int = 2,
    ):
        """
        Create data access class for S3 with session token support.

        Args:
            config: Configuration dictionary containing S3 credentials and paths
            d_sets: List of data sets to use
            checkpoint: Flag to return only files that don't exist in output directory
            m_files: Max amount of files to return
            n_samples: Amount of files to randomly sample
            batch_size: Batch size for processing
            files_to_use: File extensions to include
            files_to_checkpoint: File extensions to use for checkpointing
            s3_max_retries: Number of retries for S3 operations
            s3_backoff_factor: Backoff factor for retries
        """
        super().__init__(
            d_sets=d_sets if d_sets else [],
            checkpoint=checkpoint,
            m_files=m_files,
            n_samples=n_samples,
            batch_size=batch_size,
            files_to_use=files_to_use if files_to_use else [".parquet"],
            files_to_checkpoint=files_to_checkpoint if files_to_checkpoint else [".parquet"],
        )

        if not config:
            raise DatasiftException(
                "S3 configuration is required",
                500,
                ErrorCode.DATASIFT_DATA_ACCESS_S3_FAILED,
            )

        if not config.get("access_key") or not config.get("secret_key"):
            raise DatasiftException(
                "S3 credentials (access_key and secret_key) are required",
                500,
                ErrorCode.DATASIFT_DATA_ACCESS_S3_FAILED,
            )

        self.input_folder = TransformUtils.clean_path(config.get("input_folder", ""))
        self.output_folder = TransformUtils.clean_path(config.get(DatasiftConstants.OUTPUT_FOLDER, ""))
        self.s3_max_retries = s3_max_retries
        self.s3_backoff_factor = s3_backoff_factor
        self.tables = {}

        # Create PyArrow S3FileSystem with session token support
        s3_fs_kwargs = {
            "access_key": config.get("access_key"),
            "secret_key": config.get("secret_key"),
            "region": config.get("region"),
            "request_timeout": 300,
            "connect_timeout": 60,
        }

        # Add session token if provided (required for temporary credentials)
        if config.get("session_token"):
            s3_fs_kwargs["session_token"] = config.get("session_token")

        # Add endpoint if provided (for non-AWS S3-compatible storage)
        if config.get("url"):
            s3_fs_kwargs["endpoint_override"] = config.get("url")

        self.s3_fs = fs.S3FileSystem(**s3_fs_kwargs)

    def get_table(self, path: str) -> tuple[pa.Table | None, int]:
        """
        Get PyArrow table for a given path.

        Args:
            path: File path

        Returns:
            Tuple of (PyArrow table or None if failed, number of retries)
        """
        if path in self.tables:
            logger.debug("Table found in memory")
            return self.tables[path], 0

        file_content, attempts = self.get_file(path)

        if not file_content:
            return None, attempts

        try:
            table = pq.read_table(pa.BufferReader(file_content))
            logger.info(f"Successfully converted bytes to table from S3 at: {path}")
            return table, attempts
        except Exception as e:
            logger.error(f"Error converting bytes to table: {e}", exc_info=True)
            return None, attempts

    def save_table(self, path: str, table: pa.Table) -> tuple[int, dict[str, Any], int]:
        """
        Save PyArrow table to a file.

        Args:
            path: File path
            table: PyArrow table to save

        Returns:
            Tuple of (size in memory, file info dict, number of retries)
        """
        self.tables[path] = table

        try:
            sink = pa.BufferOutputStream()
            pq.write_table(table, sink)
            buffer = sink.getvalue()
            data = buffer.to_pybytes()

            file_info, attempts = self.save_file(path, data)

            return len(data), file_info, attempts
        except Exception as e:
            logger.error(f"Error converting table to bytes: {e}", exc_info=True)
            return 0, {}, 0

    def get_output_folder(self) -> str:
        """
        Get output folder as a string.

        Returns:
            Output folder path
        """
        return self.output_folder if self.output_folder else ""

    def get_input_folder(self) -> str:
        """
        Get input folder as a string.

        Returns:
            Input folder path
        """
        return self.input_folder if self.input_folder else ""

    def get_file(self, path: str) -> tuple[bytes, int]:
        """
        Read a file from S3 as bytes with retry logic.

        Args:
            path: Path to the file in S3

        Returns:
            Tuple of (file content as bytes, number of attempts)
        """
        call_count, retry_logic = self._create_s3_retry_logic(operation_name="read")

        @retry_with_exponential_backoff(
            max_retries=self.s3_max_retries,
            initial_delay=self.s3_backoff_factor,
            max_delay=self.s3_backoff_factor**self.s3_max_retries,
            retry_logic=retry_logic,
        )
        def _read_file():
            """Internal function to read file from S3."""
            with self.s3_fs.open_input_file(path) as file:
                file_content = file.read()
                logger.info(f"Successfully read file from S3 at: {path}")
                return file_content

        try:
            file_content = _read_file()
            return file_content, max(0, call_count[0] - 1)
        except Exception:
            logger.error(f"Exhausted {self.s3_max_retries} retries. Could not read from S3 at: {path}")
            return b"", call_count[0]

    def save_file(self, path: str, data: bytes) -> tuple[dict[str, Any], int]:
        """
        Save bytes data to a file in S3 with retry logic.

        Args:
            path: Path where to save the file in S3
            data: The data to save

        Returns:
            Tuple of (file info dict, number of attempts)
        """
        call_count, retry_logic = self._create_s3_retry_logic(operation_name="write")

        @retry_with_exponential_backoff(
            max_retries=self.s3_max_retries,
            initial_delay=self.s3_backoff_factor,
            max_delay=self.s3_backoff_factor**self.s3_max_retries,
            retry_logic=retry_logic,
        )
        def _write_file():
            """Internal function to write file to S3."""
            with self.s3_fs.open_output_stream(path) as file:
                file.write(data)
                logger.info(f"Successfully wrote file to S3 at: {path}")
                return {"size": len(data)}

        try:
            file_info = _write_file()
            return file_info, max(0, call_count[0] - 1)
        except Exception:
            logger.error(f"Exhausted all {self.s3_max_retries} retry attempts. Failed to write to S3 at: {path}")
            return {}, call_count[0]

    def save_job_metadata(self, metadata: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """
        Save job metadata (placeholder implementation).

        Args:
            metadata: Dictionary containing job metadata

        Returns:
            Tuple of (empty dict, 0 retries)
        """
        return {}, 0

    @staticmethod
    def validate_config(first: dict[str, str], second: dict[str, str]) -> bool:
        """
        Validate configuration.

        Args:
            first: First configuration dictionary
            second: Second configuration dictionary

        Returns:
            True if valid
        """
        return True

    @staticmethod
    def _create_s3_retry_logic(*, operation_name: str) -> tuple[list[int], Any]:
        """
        Helper function to create retry logic for S3 operations.

        Args:
            operation_name: Name of the operation (e.g., 'read', 'write')

        Returns:
            Tuple of (call count list, retry logic function)
        """
        call_count = [0]

        def retry_logic(result, exception):
            """Determine if we should retry based on the exception."""
            call_count[0] += 1
            if exception:
                if isinstance(exception, OSError):
                    return (
                        True,
                        f"S3 {operation_name} failed (credentials, permission, or path issue): {exception}",
                    )
                return True, f"Unexpected error while {operation_name} S3: {exception}"
            return False, ""

        return call_count, retry_logic
