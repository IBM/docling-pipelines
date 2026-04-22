import os
from typing import Any

import pyarrow as pa

from common.constants.constants import (
    AttributeDataTypes,
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
)
from common.constants.operator_constants import OperatorConstants
from common.util.data.incremental_update import IncrementalUpdateUtil
from common.util.infrastructure.logging import get_logger
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.ingest.ingest_utils import (
    filter_based_on_extension,
    get_filter_extensions,
    is_doc_previously_processed,
)

INPUT_FOLDER_NAME_KEY: str = "input_folder"
INCLUDE_FILTER_KEY: str = "include_filter"
EXCLUDE_FILTER_KEY: str = "exclude_filter"
DOC_COLUMN_NAME_KEY: str = "doc_column"
MAX_FILES_KEY: str = "max_files"
MAX_FILES_DEFAULT_VALUE: int = 100
MAX_FILE_SIZE_KEY: str = "max_file_size"
MAX_FILE_SIZE_DEFAULT_VALUE: int = 100

MB: int = 1024 * 1024

logger = get_logger()


class IngestLocalOperator(AbstractOperator):
    """
    Metadata-only ingest operator for loading file metadata from a local folder.

    This operator discovers files, collects metadata, and optionally stores binary content
    for downstream extraction operators. It does NOT extract text content - that is handled
    by specialized extraction operators like ExtractOperator.

    Supports:
    - Recursive directory traversal
    - File filtering by extension (include/exclude)
    - File size and count limits
    - Incremental updates (skip previously processed files)
    - Binary content storage for downstream extraction
    """

    short_name = OperatorConstants.Operators.INGEST_LOCAL
    category = OperatorCategory.Ingest

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the metadata-only ingest operator.

        Expected parameters:
        - input_folder: Path to the folder containing documents
        - include_filter: Comma-separated list of file extensions to include
        - exclude_filter: Comma-separated list of file extensions to exclude
        - max_files: Maximum number of files to ingest
        - max_file_size: Maximum file size in MB (larger files are skipped)
        - store_binary_content: Whether to store binary content for downstream extraction (default: True)
        - force_ingest: Force re-ingestion of previously processed documents
        - retain_deleted_docs: Whether to retain documents that have been deleted from source
        """
        super().__init__(config)
        self.input_folder: str = config.get(INPUT_FOLDER_NAME_KEY, "../test-data/input")
        self.max_files: int = config.get(MAX_FILES_KEY, MAX_FILES_DEFAULT_VALUE)
        self.max_file_size: int = MB * config.get(MAX_FILE_SIZE_KEY, MAX_FILE_SIZE_DEFAULT_VALUE)
        self.included_extensions: list[str] | None = get_filter_extensions(config.get(INCLUDE_FILTER_KEY))
        self.excluded_extensions: list[str] | None = get_filter_extensions(config.get(EXCLUDE_FILTER_KEY))
        self.doc_id_hash: str = config.get(
            OperatorConstants.Columns.DOC_ID_HASH, OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
        )
        self.common_log_arguments: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }
        self.force_ingest: bool = config.get(DatasiftConstants.FORCE_INGEST, False)
        self.retain_deleted_docs: bool = config.get(
            DatasiftConstants.RETAIN_DELETED_DOCS,
            DatasiftConstants.RETAIN_DELETED_DOCS_DEFAULT,
        )

        # Metadata-only mode configuration
        self.store_binary_content: bool = config.get("store_binary_content", True)

        # Will be initialized in transform method
        self.previously_processed_docs_dict: dict[str, Any] | None = None

        # Validate input parameters
        self._validate_input_parameters()

    def _validate_input_parameters(self) -> None:
        """
        Validate input parameters for the ingest local folder operator.

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Validate input folder
        if not self.input_folder:
            raise ValueError("input_folder is required")
        if not isinstance(self.input_folder, str) or not self.input_folder.strip():
            raise ValueError("input_folder must be a non-empty string")

        # Validate folder exists
        if not os.path.exists(self.input_folder):
            raise ValueError(f"input_folder does not exist: {self.input_folder}")
        if not os.path.isdir(self.input_folder):
            raise ValueError(f"input_folder is not a directory: {self.input_folder}")

        # Validate max_files
        if not isinstance(self.max_files, int):
            raise ValueError("max_files must be an integer")
        if self.max_files < 1:
            raise ValueError("max_files must be greater than 0")

        # Validate max_file_size
        if not isinstance(self.max_file_size, int):
            raise ValueError("max_file_size must be an integer")
        if self.max_file_size < 1:
            raise ValueError("max_file_size must be greater than 0")

    def transform(self, table: pa.Table | None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Operator-specific logic to convert one input Table to 0 or more output tables.
        In this case, crawl through the given folder, find all the files matchng the
        "include_filter", skip the files matching the "exclude_filter" and add the content
        to a new column named "content" in the table. The output
        column name is configurable using the "config" dictionary.
        """
        incremental_update_util: IncrementalUpdateUtil = IncrementalUpdateUtil()
        # get all previously processed doc IDs with modification time
        self.previously_processed_docs_dict = (
            None
            if self.force_ingest or not self.context_id
            else incremental_update_util.get_all_processed_docs(job_id=str(self.context_id))
        )

        doc_data: list[dict[str, Any]]
        metadata: dict[str, Any]
        doc_data, metadata = self.process_files(self.input_folder)

        # Create new table from ingested documents
        new_table = pa.Table.from_pylist(doc_data)

        if table is None:
            # No input table, use the newly created table
            table = new_table
        else:
            # Merge input table with new table by concatenating rows
            # Both tables should have compatible schemas for concatenation
            table = pa.concat_tables([table, new_table], promote_options="default")

        # Return the resulting pyarrow table and metadata
        node_status: str = ExecutionStatus.COMPLETED.value
        if metadata[Metrics.External.FAILED_DOCS_COUNT] > 0:
            node_status = ExecutionStatus.COMPLETED_WITH_ERRORS.value
        elif metadata[Metrics.External.SKIPPED_DOCS_COUNT] > 0:
            node_status = ExecutionStatus.COMPLETED_WITH_WARNINGS.value
        metadata[Metrics.External.NODE_STATUS] = node_status
        return [table], metadata

    def process_files(self, root_folder: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        data: list[dict[str, Any]] = []
        file_count: int = 0
        processed_count: int = 0

        # Initialize metadata
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=0)

        for root, dirs, files in os.walk(root_folder, topdown=True):
            if files and dirs:
                logger.info(
                    ">>> %s/%s/%s",
                    root,
                    dirs[0],
                    files[0],
                    extra=self.common_log_arguments,
                )
            elif files:
                logger.info(">>> %s/%s", root, files[0], extra=self.common_log_arguments)
            elif dirs:
                logger.info("No files found in: %s", root, extra=self.common_log_arguments)
            else:
                logger.info(
                    "No files or subdirectories found in: %s",
                    root,
                    extra=self.common_log_arguments,
                )

            for file in files:
                file_count += 1
                doc: dict[str, Any] | None = self.process_file(root, file, metadata, file_count)
                if doc:
                    processed_count += 1
                    data.append(doc)

        # Update total docs and processed count
        metadata[Metrics.External.TOTAL_DOCS] = file_count
        metadata[Metrics.External.PROCESSED_DOCS] = processed_count

        return data, metadata

    def process_file(self, root: str, file: str, metadata: dict[str, Any], file_count: int) -> dict[str, Any] | None:
        abs_path: str = os.path.join(root, file)
        stats: os.stat_result = os.stat(abs_path)
        if not self.check_constraints(
            file=file,
            file_stats=stats,
            abs_path=abs_path,
            metadata=metadata,
            file_count=file_count,
        ):
            return None
        doc_id: str = str(stats.st_ino)
        modified_time: int = round(stats.st_mtime)
        if self.previously_processed_docs_dict and is_doc_previously_processed(
            previously_processed_docs_dict=self.previously_processed_docs_dict,
            doc_id=doc_id,
            modified_time=modified_time,
        ):
            logger.info(
                f">>> Skipping ingesting already processed document : {doc_id}",
                extra=self.common_log_arguments,
            )
            return None

        doc: dict[str, Any] = {
            "id": doc_id,
            "name": abs_path,
            "size": stats.st_size,
            "created_time": round(stats.st_ctime),
            "modified_time": modified_time,
        }

        if self.extract_content(
            file=file,
            file_stats=stats,
            file_abs_path=abs_path,
            doc=doc,
            metadata=metadata,
        ):
            return doc
        return None

    def extract_content(
        self,
        file: str,
        file_stats: os.stat_result,
        file_abs_path: str,
        doc: dict[str, Any],
        metadata: dict[str, Any],
    ) -> bool:
        """
        Store file metadata and optionally binary content for downstream extraction.

        This method does NOT extract text content - it prepares files for downstream
        extraction operators by storing:
        - File path (always)
        - Binary content (if store_binary_content is True)

        Args:
            file: Filename
            file_stats: File statistics from os.stat()
            file_abs_path: Absolute path to the file
            doc: Document dictionary to populate
            metadata: Metadata dictionary for tracking

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(
            f"Storing metadata for downstream extraction: {file_abs_path}",
            extra=self.common_log_arguments,
        )
        try:
            # Always store the path
            doc["path"] = file_abs_path

            # Optionally store binary content
            if self.store_binary_content:
                with open(file_abs_path, "rb") as f:
                    doc["binary_content"] = f.read()
                logger.info(
                    f"Stored binary content ({len(doc['binary_content'])} bytes) for: {file_abs_path}",
                    extra=self.common_log_arguments,
                )
            return True
        except Exception as exc:
            logger.error(
                f"An error occurred while reading file: {file_abs_path}",
                extra=self.common_log_arguments,
            )
            self.record_failed_document(
                metadata=metadata,
                doc_id=str(file_stats.st_ino),
                doc_name=file_abs_path,
                reason=f"Couldn't read the file {file_abs_path} due to {exc!s}",
            )
            return False

    def check_constraints(
        self,
        file: str,
        file_stats: os.stat_result,
        abs_path: str,
        metadata: dict[str, Any],
        file_count: int,
    ) -> bool:
        if file_stats.st_size >= self.max_file_size:
            logger.warn(
                "File size exceeded max permitted size %s",
                file_stats.st_size,
                extra=self.common_log_arguments,
            )
            self.record_skipped_document(
                metadata=metadata,
                doc_id=str(file_stats.st_ino),
                doc_name=abs_path,
                reason=f"File Size exceeded max permitted size for the file {abs_path} with the file size {file_stats.st_size}",
            )
            return False

        elif file_count > self.max_files:
            logger.info(
                f"File count exceeded max files permitted: {self.max_files}",
                extra=self.common_log_arguments,
            )
            self.record_skipped_document(
                metadata=metadata,
                doc_id=str(file_stats.st_ino),
                doc_name=abs_path,
                reason="File count exceeded max files permitted",
            )
            return False

        elif filter_based_on_extension(file, self.excluded_extensions, self.included_extensions):
            logger.info(
                f">>> Skipping based on Filter : {file}",
                extra=self.common_log_arguments,
            )
            self.record_skipped_document(
                metadata=metadata,
                doc_id=str(file_stats.st_ino),
                doc_name=abs_path,
                reason=f"Skipping the file {abs_path} due to the extension filter. The file has the extension {file.split('.')[-1]}.",
            )
            return False
        else:
            return True

    def get_metadata(self) -> dict[str, Any]:
        """
        Get metadata about the operator including features and attributes.

        Returns operator metadata for the metadata-only ingest mode.
        """
        metadata_features = {}

        # Metadata-only mode features
        metadata_features.update(
            {
                "path": {
                    OperatorConstants.Columns.NAME: "File Path",
                    OperatorConstants.Config.DESCRIPTION: "The absolute path to the document file",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                }
            }
        )

        if self.store_binary_content:
            metadata_features.update(
                {
                    "binary_content": {
                        OperatorConstants.Columns.NAME: "Binary Content",
                        OperatorConstants.Config.DESCRIPTION: "The binary content of the document for downstream extraction",
                        OperatorConstants.Config.AVAILABLE_FOR_FILTER: False,
                        OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                        OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                    }
                }
            )

        metadata_features.update(
            {
                self.doc_id_hash: {
                    OperatorConstants.Columns.NAME: "Hash ID",
                    OperatorConstants.Config.DESCRIPTION: "Hash ID of the row",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                    OperatorConstants.Misc.IS_PRIMARY: True,
                    OperatorConstants.Misc.TAGS: [
                        OperatorConstants.Misc.MANDATORY,
                        OperatorConstants.Misc.PRIMARY,
                    ],
                }
            }
        )

        return {
            OperatorConstants.Misc.CATEGORY: self.category.value,
            OperatorConstants.Config.FEATURES: metadata_features,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.Config.ATTRIBUTES: {
                OperatorConstants.Config.MAX_FILE_SIZE: {
                    OperatorConstants.Columns.NAME: "Max File Size",
                    OperatorConstants.Config.DESCRIPTION: "If the document is larger than the given max file size, then it will be skipped",
                    OperatorConstants.Config.DEFAULT: 100,
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                OperatorConstants.Filtering.INCLUDE_FILTER_KEY: {
                    OperatorConstants.Columns.NAME: "Include File Type",
                    OperatorConstants.Config.DESCRIPTION: "File types to be included (comma-separated extensions)",
                    OperatorConstants.Config.DEFAULT: "pdf,docx,pptx,txt,md",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.LIST,
                },
                "store_binary_content": {
                    OperatorConstants.Columns.NAME: "Store Binary Content",
                    OperatorConstants.Config.DESCRIPTION: "Whether to store binary content for downstream extraction",
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
            },
        }
