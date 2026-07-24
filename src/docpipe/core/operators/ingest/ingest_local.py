import os
from typing import Any

import pyarrow as pa

from docpipe.core.constants.constants import (
    AttributeDataTypes,
    DocpipeConstants,
    ExecutionStatus,
    Metrics,
)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.incremental_metadata import IncrementalUpdateService
from docpipe.core.incremental_metadata.adapters.config import create_incremental_metadata_store
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.core.operators.ingest.ingest_utils import (
    filter_based_on_extension,
    get_filter_extensions,
    is_doc_previously_processed,
)
from docpipe.core.operators.operator_utils import get_supported_file_extensions
from docpipe.utils.infrastructure.logging import get_logger

PATH_KEY: str = "paths"
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
    Metadata-only ingest operator for loading file metadata from local files or folders.

    This operator discovers files and collects metadata for downstream extraction operators.
    It does NOT extract text content - that is handled by specialized extraction operators
    like ExtractOperator.

    Supports:
    - Single or multiple file/directory paths
    - Comma-separated paths or list of paths
    - Recursive directory traversal
    - File filtering by extension (include/exclude)
    - File size and count limits
    - Incremental updates (skip previously processed files)
    """

    short_name = OperatorConstants.Operators.INGEST_LOCAL
    category = OperatorCategory.Ingest
    owner = DocpipeConstants.OWNER_DOCPIPE

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the metadata-only ingest operator.

        Expected parameters:
        - paths: Single path, comma-separated paths, or list of paths to files/folders
        - include_filter: Comma-separated list of file extensions to include
        - exclude_filter: Comma-separated list of file extensions to exclude
        - max_files: Maximum number of files to ingest
        - max_file_size: Maximum file size in MB (larger files are skipped)
        - force_ingest: Force re-ingestion of previously processed documents
        - retain_deleted_docs: Whether to retain documents that have been deleted from source
        """
        super().__init__(config)

        # Parse paths - can be string (single or comma-separated) or list
        paths_input = config.get(OperatorConstants.Misc.PATHS, [])
        if isinstance(paths_input, list):
            self.paths = [p.strip() for p in paths_input if isinstance(p, str) and p.strip()]
        elif isinstance(paths_input, str):
            self.paths = [paths_input.strip()] if paths_input.strip() else []
        else:
            self.paths = []

        self.max_files: int = config.get(MAX_FILES_KEY, MAX_FILES_DEFAULT_VALUE)
        self.max_file_size: int = MB * config.get(MAX_FILE_SIZE_KEY, MAX_FILE_SIZE_DEFAULT_VALUE)
        self.included_extensions: list[str] | None = get_filter_extensions(config.get(INCLUDE_FILTER_KEY))
        self.excluded_extensions: list[str] | None = get_filter_extensions(config.get(EXCLUDE_FILTER_KEY))
        self.doc_id_hash: str = config.get(
            OperatorConstants.Columns.DOC_ID_HASH, OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
        )
        self.common_log_arguments: dict[str, Any] = {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
        }
        self.force_ingest: bool = config.get(DocpipeConstants.FORCE_INGEST, False)
        self.retain_deleted_docs: bool = config.get(
            DocpipeConstants.RETAIN_DELETED_DOCS,
            DocpipeConstants.RETAIN_DELETED_DOCS_DEFAULT,
        )

        # Will be initialized in transform method
        self.previously_processed_docs_dict: dict[str, Any] | None = None

        # Validate input parameters
        self._validate_input_parameters()

    def _validate_input_parameters(self) -> None:
        """
        Validate input parameters for the ingest local operator.

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Validate paths
        if not self.paths:
            raise ValueError("paths is required and cannot be empty")

        # Validate each path exists
        for path in self.paths:
            if not path or not isinstance(path, str):
                raise ValueError(f"Each path must be a non-empty string, got: {path}")
            if not os.path.exists(path):
                raise ValueError(f"Path does not exist: {path}")

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

    def transform(self, table: pa.Table | None, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Operator-specific logic to convert one input Table to 0 or more output tables.
        Processes all paths (files/folders) specified in the paths parameter, find all the files matchng the
        "include_filter", skip the files matching the "exclude_filter" and add the content
        to a new column named "content" in the table. The output
        column name is configurable using the "config" dictionary.
        """
        # Create incremental update service
        store = create_incremental_metadata_store(job_id=str(self.context_id) if self.context_id else None)
        incremental_service = IncrementalUpdateService(store=store)

        # get all previously processed doc IDs with modification time
        self.previously_processed_docs_dict = (
            None
            if self.force_ingest or not self.context_id
            else incremental_service.get_all_processed_docs(job_id=str(self.context_id))
        )

        # Process all paths and collect results
        all_doc_data: list[dict[str, Any]] = []
        combined_metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=0)

        for path in self.paths:
            logger.info(f"Processing path: {path}", extra=self.common_log_arguments)
            doc_data, path_metadata = self.process_files(path)
            all_doc_data.extend(doc_data)

            # Aggregate metadata from each path
            combined_metadata[Metrics.External.TOTAL_DOCS] += path_metadata.get(Metrics.External.TOTAL_DOCS, 0)
            combined_metadata[Metrics.External.PROCESSED_DOCS] += path_metadata.get(Metrics.External.PROCESSED_DOCS, 0)
            combined_metadata[Metrics.External.FAILED_DOCS_COUNT] += path_metadata.get(
                Metrics.External.FAILED_DOCS_COUNT, 0
            )
            combined_metadata[Metrics.External.SKIPPED_DOCS_COUNT] += path_metadata.get(
                Metrics.External.SKIPPED_DOCS_COUNT, 0
            )

            # Merge failed and skipped docs lists
            combined_metadata[Metrics.External.FAILED_DOCS].extend(path_metadata.get(Metrics.External.FAILED_DOCS, []))
            combined_metadata[Metrics.External.SKIPPED_DOCS].extend(
                path_metadata.get(Metrics.External.SKIPPED_DOCS, [])
            )

        # Create new table from all ingested documents
        new_table = pa.Table.from_pylist(all_doc_data)

        if table is None:
            # No input table, use the newly created table
            table = new_table
        else:
            # Merge input table with new table by concatenating rows
            # Both tables should have compatible schemas for concatenation
            table = pa.concat_tables([table, new_table], promote_options="default")

        # Return the resulting pyarrow table and metadata
        node_status: str = ExecutionStatus.COMPLETED.value
        if combined_metadata[Metrics.External.FAILED_DOCS_COUNT] > 0:
            node_status = ExecutionStatus.COMPLETED_WITH_ERRORS.value
        elif combined_metadata[Metrics.External.SKIPPED_DOCS_COUNT] > 0:
            node_status = ExecutionStatus.COMPLETED_WITH_WARNINGS.value
        combined_metadata[Metrics.External.NODE_STATUS] = node_status
        return [table], combined_metadata

    def process_files(self, root_folder: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Process files with streaming batch-fetch logic.

        Streams files as they're discovered and processes in batches until
        max_files newly processed documents are reached. This ensures continuous
        progress across multiple runs even when encountering already-processed files.
        """
        data: list[dict[str, Any]] = []
        examined_count: int = 0  # Total files examined
        processed_count: int = 0  # Newly processed files

        # Initialize metadata
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=0)

        # Process single file
        if os.path.isfile(root_folder):
            examined_count = 1
            single_doc: dict[str, Any] | None = self.process_file(
                os.path.dirname(root_folder), os.path.basename(root_folder), metadata
            )
            if single_doc:
                processed_count = 1
                data.append(single_doc)
        else:
            # Process directory with streaming batch logic
            for root, dirs, files in os.walk(root_folder, topdown=True):
                # Check if we've processed enough NEW files
                if processed_count >= self.max_files:
                    logger.info(
                        f"Reached max_files limit ({self.max_files}), examined {examined_count} files, processed {processed_count} new files",
                        extra=self.common_log_arguments,
                    )
                    break

                if files and dirs:
                    logger.debug(
                        ">>> %s/%s/%s",
                        root,
                        dirs[0],
                        files[0],
                        extra=self.common_log_arguments,
                    )
                elif files:
                    logger.debug(">>> %s/%s", root, files[0], extra=self.common_log_arguments)

                for file in files:
                    # Check if we've processed enough NEW files
                    if processed_count >= self.max_files:
                        logger.info(
                            f"Reached max_files limit ({self.max_files}), examined {examined_count} files, processed {processed_count} new files",
                            extra=self.common_log_arguments,
                        )
                        break

                    examined_count += 1
                    doc: dict[str, Any] | None = self.process_file(root, file, metadata)
                    if doc:
                        processed_count += 1
                        data.append(doc)
                        logger.debug(
                            f"Processed file {processed_count}/{self.max_files}: {file}",
                            extra=self.common_log_arguments,
                        )

        # Update total docs and processed count
        metadata[Metrics.External.TOTAL_DOCS] = examined_count
        metadata[Metrics.External.PROCESSED_DOCS] = processed_count

        logger.info(
            f"Completed processing: examined {examined_count} files, processed {processed_count} new files",
            extra=self.common_log_arguments,
        )

        return data, metadata

    def process_file(self, root: str, file: str, metadata: dict[str, Any]) -> dict[str, Any] | None:
        """
        Process a single file and return document metadata.

        Args:
            root: Root directory path
            file: Filename
            metadata: Metadata dictionary for tracking

        Returns:
            Document dictionary if processed successfully, None otherwise
        """
        abs_path: str = os.path.join(root, file)
        stats: os.stat_result = os.stat(abs_path)
        if not self.check_constraints(
            file=file,
            file_stats=stats,
            abs_path=abs_path,
            metadata=metadata,
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
        Store file path for downstream extraction.

        This method does NOT extract text content - it prepares files for downstream
        extraction operators by storing the file path.

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
            # Store the file path
            doc["path"] = file_abs_path
            return True
        except Exception as exc:
            logger.error(
                f"An error occurred while processing file: {file_abs_path}",
                extra=self.common_log_arguments,
            )
            self.record_failed_document(
                metadata=metadata,
                doc_id=str(file_stats.st_ino),
                doc_name=file_abs_path,
                reason=f"Couldn't process the file {file_abs_path} due to {exc!s}",
            )
            return False

    def check_constraints(
        self,
        file: str,
        file_stats: os.stat_result,
        abs_path: str,
        metadata: dict[str, Any],
    ) -> bool:
        """
        Check file constraints (size, extension filters).

        Note: max_files limit is now checked in process_files() based on
        processed_count, not total examined files.

        Args:
            file: Filename
            file_stats: File statistics
            abs_path: Absolute file path
            metadata: Metadata dictionary for tracking

        Returns:
            True if file passes constraints, False otherwise
        """
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

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """
        Get metadata about the operator including features and attributes.

        Returns operator metadata for the metadata-only ingest mode.
        """
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: IngestLocalOperator.category.value,
            OperatorConstants.Misc.LABEL: "Local File Ingest",
            OperatorConstants.Config.DESCRIPTION: "Ingest documents from local file system paths into the pipeline.",
            OperatorConstants.Config.FEATURES: {
                OperatorConstants.Columns.ID: {
                    OperatorConstants.Columns.NAME: "Document ID",
                    OperatorConstants.Config.DESCRIPTION: "Document identifier",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                },
                OperatorConstants.Columns.NAME: {
                    OperatorConstants.Columns.NAME: "File Name",
                    OperatorConstants.Config.DESCRIPTION: "The absolute path to the document file",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                },
                OperatorConstants.Columns.PATH: {
                    OperatorConstants.Columns.NAME: "File Path",
                    OperatorConstants.Config.DESCRIPTION: "The absolute path to the document file (same as name)",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                },
                OperatorConstants.Metadata.DOCUMENT_FORMAT: {
                    OperatorConstants.Columns.NAME: "Document Format",
                    OperatorConstants.Config.DESCRIPTION: "File format/extension of the document (e.g., .pdf, .xlsx)",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                },
                OperatorConstants.Misc.SIZE: {
                    OperatorConstants.Columns.NAME: "File Size",
                    OperatorConstants.Config.DESCRIPTION: "File size in bytes",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_INT64,
                },
                OperatorConstants.Metadata.CREATED_TIME: {
                    OperatorConstants.Columns.NAME: "Created Time",
                    OperatorConstants.Config.DESCRIPTION: "File creation timestamp (Unix epoch time)",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_INT64,
                },
                OperatorConstants.Metadata.MODIFIED_TIME: {
                    OperatorConstants.Columns.NAME: "Modified Time",
                    OperatorConstants.Config.DESCRIPTION: "File modification timestamp (Unix epoch time)",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_INT64,
                },
            },
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: IngestLocalOperator.is_available(),
            OperatorConstants.Config.ATTRIBUTES: {
                PATH_KEY: {
                    OperatorConstants.Columns.NAME: "Paths",
                    OperatorConstants.Config.DESCRIPTION: "Single path, comma-separated paths, or list of paths to files/folders to ingest",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                MAX_FILES_KEY: {
                    OperatorConstants.Columns.NAME: "Max Files",
                    OperatorConstants.Config.DESCRIPTION: "Maximum number of files to ingest",
                    OperatorConstants.Config.DEFAULT: MAX_FILES_DEFAULT_VALUE,
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                MAX_FILE_SIZE_KEY: {
                    OperatorConstants.Columns.NAME: "Max File Size",
                    OperatorConstants.Config.DESCRIPTION: "Maximum file size in MB. Files larger than this will be skipped",
                    OperatorConstants.Config.DEFAULT: MAX_FILE_SIZE_DEFAULT_VALUE,
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                INCLUDE_FILTER_KEY: {
                    OperatorConstants.Columns.NAME: "Include File Type",
                    OperatorConstants.Config.DESCRIPTION: "File types to be included (comma-separated extensions). Audio/video formats (wav,mp3,mp4,etc.) only available if ASR dependencies installed.",
                    OperatorConstants.Config.DEFAULT: get_supported_file_extensions(),
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.LIST,
                },
                EXCLUDE_FILTER_KEY: {
                    OperatorConstants.Columns.NAME: "Exclude File Type",
                    OperatorConstants.Config.DESCRIPTION: "File types to be excluded (comma-separated extensions)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.LIST,
                },
                DocpipeConstants.FORCE_INGEST: {
                    OperatorConstants.Columns.NAME: "Force Ingest",
                    OperatorConstants.Config.DESCRIPTION: "Force re-ingestion of previously processed documents",
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                DocpipeConstants.RETAIN_DELETED_DOCS: {
                    OperatorConstants.Columns.NAME: "Retain Deleted Documents",
                    OperatorConstants.Config.DESCRIPTION: "Whether to retain documents that have been deleted from source",
                    OperatorConstants.Config.DEFAULT: DocpipeConstants.RETAIN_DELETED_DOCS_DEFAULT,
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
            },
        }
