from typing import Any
import pyarrow as pa
import pyarrow.fs as fs
import pyarrow.parquet as pq
from data_processing.data_access import DataAccess
from data_processing.utils import TransformUtils

from common.exceptions.datasift_exceptions import DatasiftException
from common.exceptions.datasift_exceptions import ErrorCode
from common.util.constants import DatasiftConstants
from common.util.log import get_logger
from common.util.retry_utils import retry_with_exponential_backoff

logger = get_logger()


class DatasiftDataAccessCOS(DataAccess):
    """
    Implementation of the Base DataAccessLocal class to save data in memory and use it for processing in Datasift SaaS.
    Data is also saved locally in IBM Cloud Object Storage as the functionality of base class.
    """

    def __init__(
            self,
            config: dict[str, str] | None = None,
            d_sets: list[str] | None = None,
            checkpoint: bool = False,
            m_files: int = -1,
            n_samples: int = -1,
            batch_size: int = -1,
            files_to_use: list[str] = [".parquet"],
            files_to_checkpoint: list[str] = [".parquet"],
            cos_max_retries: int = 3,
            cos_backoff_factor: int = 2
    ):
        """
        Create data access class for folder based configuration
        :param path_config: dictionary of path info
        """

        super().__init__(
            d_sets=d_sets if d_sets else [],
            checkpoint=checkpoint,
            m_files=m_files,
            n_samples=n_samples,
            batch_size=batch_size,
            files_to_use=files_to_use,
            files_to_checkpoint=files_to_checkpoint
        )
        if (
            config is None
            or config.get("access_key", None) is None
            or config.get("secret_key", None) is None
        ):
            raise DatasiftException("COS credentials are not defined", 500, ErrorCode.DATASIFT_DATA_ACCESS_COS_FAILED)
        if config is None:
            self.input_folder = None
            self.output_folder = None
        else:
            self.input_folder = TransformUtils.clean_path(config["input_folder"])
            self.output_folder = TransformUtils.clean_path(config[DatasiftConstants.OUTPUT_FOLDER])
        self.cos_max_retries = cos_max_retries
        self.cos_backoff_factor = cos_backoff_factor
        self.tables = {}
        """
        Create a pyarrow cos filesystem to directly write to COS because the ArrowS3 of Parent class in not able to
        write to COS due to unknown access denied reasons.
        """
        self.cos_fs = fs.S3FileSystem(
            access_key=config.get("access_key", None),
            secret_key=config.get("secret_key", None),
            endpoint_override=config.get("url", None),
            region=config.get("region", None),
            request_timeout=300,  # Increase timeout to 5 minutes (in seconds)
            connect_timeout=60,
        )

    def get_table(self, path: str) -> tuple[pa.table, int]:
        """
        Get pyArrow table for a given path
        :param path - file path
        :return: pyArrow table from memory, if not found - from local file system; None, if the table read failed and number of operation retries.
                 Retries are performed on operation failures and are typically due to the resource overload.
        """

        # if the table exists in memory, use it for faster access
        if path in self.tables:
            logger.debug('Table found in memory')
            return self.tables[path], 0

        # Use get_file to read the parquet file as bytes
        file_content, attempts = self.get_file(path)
        
        # If file content is empty, return None
        if not file_content:
            return None, attempts
            
        try:
            # Convert bytes to PyArrow table
            table = pq.read_table(pa.BufferReader(file_content))
            logger.info(f"Successfully converted bytes to table from COS at: {path}")
            return table, attempts
        except Exception as e:
            logger.error(f"Error converting bytes to table: {e}")
            return None, attempts

    def save_table(self, path: str, table: pa.Table) -> tuple[int, dict[str, Any], int]:
        """
        Saves a pyarrow table into a member variable and to the file system.

        Args:
            table (pyarrow.Table): The pyarrow table to save.
            path (str): The path where to save the table

        Returns:
            tuple: A tuple containing:
                - size_in_memory (int): The size of the table in memory (bytes).
                - file_info (dict or None): Information about the saved file.
                - attempts (int): Number of attempts made to save the file.
        """

        # save the table in memory for faster access
        self.tables[path] = table

        try:
            # Convert PyArrow table to bytes
            sink = pa.BufferOutputStream()
            pq.write_table(table, sink)
            buffer = sink.getvalue()
            data = buffer.to_pybytes()
            
            # Use save_file to write the bytes to COS
            file_info, attempts = self.save_file(path, data)
            
            # Return the size in memory, file info, and attempts
            return len(data), file_info, attempts
        except Exception as e:
            logger.error(f"Error converting table to bytes: {e}")
            return 0, {}, 0

    def get_output_folder(self) -> str:
        if self.output_folder is None:
            return ""
        return self.output_folder

    def get_input_folder(self) -> str: #pragma: no cover
        if self.input_folder is None:
            return ""
        return self.input_folder

    def _create_cos_retry_logic(self, operation_name: str):
        """
        Helper function to create retry logic for COS operations.
        
        Args:
            operation_name (str): Name of the operation (e.g., 'read', 'write').
            
        Returns:
            tuple: A tuple containing:
                - call_count (list): List with single element to track call count.
                - retry_logic (function): The retry logic function.
        """
        call_count = [0]
        
        def retry_logic(result, exception):
            """Determine if we should retry based on the exception."""
            call_count[0] += 1
            if exception:
                if isinstance(exception, OSError):
                    return True, f"COS {operation_name} failed (credentials, permission, or path issue): {exception}"
                else:
                    return True, f"Unexpected error while {operation_name} COS: {exception}"
            return False, ""
        
        return call_count, retry_logic

    def get_file(self, path: str) -> tuple[bytes, int]:
        """
        Read a file from COS as bytes with retry logic.
        
        Args:
            path (str): Path to the file in COS.
            
        Returns:
            tuple: A tuple containing:
                - file_content (bytes): The file content as bytes.
                - attempts (int): Number of attempts made to read the file.
        """
        call_count, retry_logic = self._create_cos_retry_logic("read")
        
        @retry_with_exponential_backoff(
            max_retries=self.cos_max_retries,
            initial_delay=self.cos_backoff_factor,
            max_delay=self.cos_backoff_factor ** self.cos_max_retries,
            retry_logic=retry_logic
        )
        def _read_file():
            """Internal function to read file from COS."""
            with self.cos_fs.open_input_file(path) as file:
                file_content = file.read()
                logger.info(f"Successfully read file from COS at: {path}")
                return file_content
        
        try:
            file_content = _read_file()
            # Return attempts as call_count - 1 (excluding the successful final call)
            return file_content, max(0, call_count[0] - 1)
        except Exception:
            logger.error(f"Exhausted {self.cos_max_retries} retries. Could not read from COS at: {path}")
            # When all retries exhausted, call_count includes initial + all retries
            return b"", call_count[0]

    def save_file(self, path: str, data: bytes) -> tuple[dict[str, Any], int]:
        """
        Save bytes data to a file in COS with retry logic.
        
        Args:
            path (str): Path where to save the file in COS.
            data (bytes): The data to save.
            
        Returns:
            tuple: A tuple containing:
                - file_info (dict): Information about the saved file.
                - attempts (int): Number of attempts made to save the file.
        """
        call_count, retry_logic = self._create_cos_retry_logic("write")
        
        @retry_with_exponential_backoff(
            max_retries=self.cos_max_retries,
            initial_delay=self.cos_backoff_factor,
            max_delay=self.cos_backoff_factor ** self.cos_max_retries,
            retry_logic=retry_logic
        )
        def _write_file():
            """Internal function to write file to COS."""
            with self.cos_fs.open_output_stream(path) as file:
                file.write(data)
                logger.info(f"Successfully wrote file to COS at: {path}")
                return {"size": len(data)}
        
        try:
            file_info = _write_file()
            # Return attempts as call_count - 1 (excluding the successful final call)
            return file_info, max(0, call_count[0] - 1)
        except Exception:
            logger.error(f"Exhausted all {self.cos_max_retries} retry attempts. Failed to write to COS at: {path}")
            # When all retries exhausted, call_count includes initial + all retries
            return {}, call_count[0]

    def save_job_metadata(self, metadata: dict[str, Any]) -> tuple[dict[str, Any], int]: #pragma: no cover
        """Just have written this function to not fail in abstract classs instantiation. will be handled in """
        return {}, 0


    @staticmethod #pragma: no cover
    def validate_config(first, second):
        return True
