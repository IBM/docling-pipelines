import copy
import pprint
from abc import abstractmethod
from queue import Queue
from typing import Any

import pyarrow as pa
from data_processing.data_access import DataAccess, DataAccessFactory

from docpipe.core.constants.constants import (
    DocpipeConstants,
    ExecutionStatus,
    Metrics,
)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.data_access.data_access_utils import DataAccessUtils
from docpipe.core.job_management.domain.ports import JobStatsService
from docpipe.core.operators.abstract_operator import AbstractOperator
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.utils.infrastructure.logging import get_logger
from docpipe.utils.orchestration.deleted_rows_tracker import update_deleted_rows

logger = get_logger()


class AbstractOperatorExecutor:
    def __init__(
        self,
        *,
        name: str,
        operator: str,
        params: dict,
        job_stats_service: JobStatsService | None = None,
    ):
        """
        Initialize operator executor with explicit dependency injection.

        Args:
            name: The name of the step mentioned in the flow. Note that the name of the step is different from the operator name.
                  This is because the user can have multiple steps with the same operator but different name.
                  For example, we can have a flow with one regex operator for e-mail and another regex operator for ssn.
            operator: Identifies the operator to be executed
            params: dictionary of configuration information used while executing the operator
            job_stats_service: Optional job statistics service for tracking node execution
        """
        self._name = name
        self._operator = operator
        self._params = params | {OperatorConstants.Columns.NAME: name}
        self._job_stats_service = job_stats_service
        job_id: str = str(self._params.get(DocpipeConstants.JOB_ID))
        job_run_id: str = str(self._params.get(DocpipeConstants.JOB_RUN_ID))
        DataAccessUtils.add_intermediate_storage_config(
            config=self._params,
            job_id=job_id,
            job_run_id=job_run_id,
        )

    def execute(
        self,
        *,
        data_access: DataAccess | dict[str, DataAccess | None] | None,
        deleted_rows_list: Queue[pa.Table] | None,
    ) -> tuple[list[DataAccess], dict[str, Any]]:
        input_tables = self._get_input_tables(data_access=data_access)
        out_tables, metadata = self._execute_impl(tables=input_tables)
        if deleted_rows_list is not None:
            deleted_rows = update_deleted_rows(
                prev_tables=input_tables,
                current_tables=out_tables,
                op=self.get_operator(),
                skip_columns=[
                    OperatorConstants.Columns.KVP_COLUMN,
                    OperatorConstants.Columns.DOC_COLUMN,
                ],
            )
            if deleted_rows.num_rows > 0:
                deleted_rows_list.put(deleted_rows)
        output_data_accesses = self.create_data_accesses(out_tables)

        return output_data_accesses, metadata

    def create_data_accesses(self, tables):
        data_accesses = []
        for index, table in enumerate(tables):
            data_access_factory = DataAccessFactory()
            params_copy = copy.deepcopy(self._params)
            # Add node name + index of the branch to the output folder
            DataAccessUtils.add_node_name_to_output_folder(
                params=params_copy, node_name=f"{params_copy['name']}_{index}"
            )
            data_access_factory.apply_input_params(params_copy)
            output_data_access = data_access_factory.create_data_access()
            output_file_path = self.get_output_file_path(data_access=output_data_access)

            # Note: memmap path replacement is now handled by CustomDataAccessLocal.save_table()
            # The custom class caches tables with memmap paths (memory efficient)
            # but writes expanded data to parquet files (persistent and portable)
            output_data_access.save_table(output_file_path, table)
            data_accesses.append(output_data_access)
        return data_accesses

    @abstractmethod
    def get_operator(self) -> AbstractOperator:
        # The concrete class implements the method by returning the operator for the corresponding orchestrator.
        pass

    def validate(self, *, errors: list, warnings: list, available_features: list):
        op = self.get_operator()
        op.validate(errors, warnings, available_features)

    def get_metadata(self):
        """
        The concrete subclasses give the given operator metadata identified by _operator by passing the given table
        """
        op = self.get_operator()
        return op.get_metadata()

    def _execute_impl(self, tables: pa.Table | dict[str, pa.Table] | None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        The concrete subclasses execute the given operator identified by _operator by passing the given tables
        """
        raise NotImplementedError("Subclasses must implement _execute_impl")

    def _get_input_tables(
        self,
        *,
        data_access: DataAccess | dict[str, DataAccess | None] | None,
    ) -> pa.Table | dict[str, pa.Table] | None:
        if data_access is None:
            tables = None
        elif isinstance(data_access, DataAccess):
            input_file_path = self.get_output_file_path(data_access=data_access)
            tables, _ = data_access.get_table(input_file_path)
        else:
            tables = {}
            for link_name, access in data_access.items():
                if access is None:
                    # Note: Merge operators should be ready to receive an empty list of tables, or a list with a single table.
                    continue
                input_file_path = self.get_output_file_path(data_access=access)
                table, _ = access.get_table(input_file_path)
                tables[link_name] = table
        return tables

    def set_default_node_stats(self, *, tables: pa.Table | dict[str, pa.Table] | None):
        """Initialize node statistics for the current node execution.

        Builds the initial node statistics inputs from the current node input
        tables and delegates persistence to the job stats service.

        Args:
            tables: Input tables for the current node. This may be a single
                PyArrow table, a dict of PyArrow tables keyed by input link
                name, or None for nodes without upstream input data.
        """
        node_id = self._params[OperatorConstants.Columns.ID]
        logger.info(f"Initializing stats for node '{self._name}' (ID: {node_id}).")

        # Use injected job stats service
        if not self._job_stats_service:
            logger.warning(f"Job stats service not available for node '{node_id}'")
            return

        # Extract batch_id and batch_num from params if micro-batching is enabled
        batch_id = self._params.get(DocpipeConstants.BATCH_ID)
        batch_num = self._params.get(DocpipeConstants.BATCH_NUM)

        self._job_stats_service.start_node_execution(
            job_run_id=self._params[DocpipeConstants.JOB_RUN_ID],
            node_id=node_id,
            node_name=self._name,
            total_docs=OperatorUtils.get_unique_ids(tables=tables),
            batch_id=batch_id,
            batch_num=batch_num,
        )
        logger.info(f"Initial stats for node '{node_id}' stored successfully.")

    def update_final_node_stats(self, *, tables: list[pa.Table], metadata: dict):
        """Finalize node statistics for the current node execution.

        Extracts completed, failed, skipped, schema, and status information
        from the node outputs and operator metadata, then delegates final node
        statistics assembly and persistence to the job stats service.

        Args:
            tables: Output PyArrow tables produced by the current node.
            metadata: Operator metadata for the current node execution,
                including node status and optional failed/skipped document
                details.
        """
        node_id = self._params[OperatorConstants.Columns.ID]
        job_run_id = self._params[DocpipeConstants.JOB_RUN_ID]
        logger.info(f"Updating final stats for node '{node_id}'.")

        # Use injected job stats service
        if not self._job_stats_service:
            logger.warning(f"Job stats service not available for node '{node_id}'")
            return

        # Extract batch_id and batch_num from params if micro-batching is enabled
        batch_id = self._params.get(DocpipeConstants.BATCH_ID)
        batch_num = self._params.get(DocpipeConstants.BATCH_NUM)

        # Extract document IDs from tables
        all_doc_ids = OperatorUtils.get_unique_ids(tables=tables) if tables else []

        # Extract failed and skipped document IDs from metadata
        failed_docs = [
            doc.get("id", "") for doc in metadata.get(Metrics.External.FAILED_DOCS, []) if isinstance(doc, dict)
        ]
        skipped_docs = [
            doc.get("id", "") for doc in metadata.get(Metrics.External.SKIPPED_DOCS, []) if isinstance(doc, dict)
        ]

        # docs_completed = documents in output tables that are NOT failed or skipped
        failed_and_skipped_set = set(failed_docs + skipped_docs)
        docs_completed = [doc_id for doc_id in all_doc_ids if doc_id not in failed_and_skipped_set]
        col_names = tables[0].column_names if tables else []
        node_status = metadata.get(Metrics.External.NODE_STATUS, ExecutionStatus.COMPLETED.value)

        logger.info(
            f"Node '{node_id}' stats summary: "
            f"{len(docs_completed)} completed, "
            f"{len(failed_docs)} failed, "
            f"{len(skipped_docs)} skipped."
        )

        if failed_docs or skipped_docs:
            logger.warning(
                f"Node '{node_id}' completed with issues: failed={len(failed_docs)}, skipped={len(skipped_docs)}"
            )

        self._job_stats_service.complete_node_execution(
            job_run_id=job_run_id,
            node_id=node_id,
            node_name=self._name,
            docs_completed=docs_completed,
            failed_docs=failed_docs,
            skipped_docs=skipped_docs,
            col_names=col_names,
            node_status=node_status,
            node_metadata=metadata,
            batch_id=batch_id,
            batch_num=batch_num,
        )
        logger.info(f"Final stats for node '{node_id}' stored successfully.")

    @staticmethod
    def get_output_file_path(*, data_access):
        output_folder = data_access.get_output_folder()
        if output_folder is None:
            return ""
        if not output_folder.endswith("/"):
            output_folder += "/"
        return output_folder + "output.parquet"

    def _log_start(self, *, op_logger, node_id, name, short_name, common_log_arguments):
        op_logger.info(
            "Starting execution: Step Name: %s, operator: %s",
            name,
            short_name,
            extra=common_log_arguments,
        )

    def _log_completion(self, *, op_logger, name, time_taken, result, metadata, common_log_arguments):
        # Schema and metadata moved to DEBUG - they're shown in formatted output
        if result[0] and result[0][0]:
            op_logger.debug("Schema:%s", str(result[0][0].schema), extra=common_log_arguments)
        op_logger.debug("Operator Metadata:\n%s", pprint.pformat(metadata, indent=2))
        op_logger.info(
            "Completed execution: %s, time= %.2f seconds",
            name,
            time_taken,
            extra=common_log_arguments,
        )

    def _process_table_for_empty_docs(self, *, table: pa.Table, doc_column: str, metadata: dict[str, Any]) -> pa.Table:
        """
        Process a single table to handle empty documents using PyArrow operations.

        Args:
            table: PyArrow table to process
            doc_column: Name of the document content column
            metadata: Metadata dictionary to update

        Returns:
            Processed PyArrow table with empty documents removed
        """
        import pyarrow.compute as pc

        # Skip processing if table is empty
        if table.num_rows == 0:
            return table

        # Check if doc_column exists in the table
        if doc_column not in table.column_names:
            return table

        doc_col = table[doc_column]

        # Create mask for empty documents: null OR empty/whitespace-only strings
        is_null = pc.is_null(doc_col)  # type: ignore[attr-defined]
        doc_col_filled = pc.fill_null(doc_col, "")  # type: ignore[attr-defined]
        stripped = pc.utf8_trim_whitespace(doc_col_filled)  # type: ignore[attr-defined]
        is_empty_string = pc.equal(pc.utf8_length(stripped), 0)  # type: ignore[attr-defined]
        is_empty_mask = pc.or_(is_null, is_empty_string)  # type: ignore[attr-defined]

        # Get indices of empty documents for metadata tracking
        empty_doc_indices = pc.indices_nonzero(is_empty_mask).to_pylist()  # type: ignore[attr-defined]

        # If no empty documents, return table as is
        if not empty_doc_indices:
            return table

        # Save empty documents to incremental metadata
        empty_docs_table = table.filter(is_empty_mask)
        self._save_empty_docs_to_incremental_metadata(table=empty_docs_table, empty_doc_indices=empty_doc_indices)

        # Add empty documents as skipped in metadata
        self._add_empty_docs_to_skipped_metadata(table=table, empty_doc_indices=empty_doc_indices, metadata=metadata)

        # Filter out empty documents using inverted mask
        non_empty_mask = pc.invert(is_empty_mask)  # type: ignore[attr-defined]
        filtered_table = table.filter(non_empty_mask)

        return filtered_table if filtered_table.num_rows > 0 else table.slice(0, 0)

    def _save_empty_docs_to_incremental_metadata(self, *, table: pa.Table, empty_doc_indices: list):
        """
        Save empty documents to incremental metadata so they are marked as processed
        and won't be reprocessed in subsequent incremental runs.

        Args:
            table: The PyArrow table containing all documents
            empty_doc_indices: List of indices for documents with empty content
        """
        if not empty_doc_indices:
            return

        try:
            from docpipe.core.incremental_metadata import IncrementalUpdateService
            from docpipe.core.incremental_metadata.adapters.config import create_incremental_metadata_store

            # Create a table with only the empty documents
            empty_docs_table = table.take(empty_doc_indices)

            # Initialize incremental update service
            job_id = self._params.get(DocpipeConstants.JOB_ID)
            store = create_incremental_metadata_store(job_id=job_id)
            incremental_service = IncrementalUpdateService(store=store)

            # Save empty documents to incremental metadata
            incremental_service.save_metadata_for_incremental_update(
                job_id=self._params.get(DocpipeConstants.JOB_ID),
                job_run_id=self._params.get(DocpipeConstants.JOB_RUN_ID),
                tables=[empty_docs_table],
                failed_doc_ids=None,
            )

            logger.info(
                f"Saved {len(empty_doc_indices)} empty documents to incremental metadata",
                extra={
                    DocpipeConstants.JOB_ID: self._params.get(DocpipeConstants.JOB_ID),
                    DocpipeConstants.JOB_RUN_ID: self._params.get(DocpipeConstants.JOB_RUN_ID),
                },
            )
        except Exception as e:
            logger.warning(
                f"Failed to save empty documents to incremental metadata: {e!s}",
                extra={
                    DocpipeConstants.JOB_ID: self._params.get(DocpipeConstants.JOB_ID),
                    DocpipeConstants.JOB_RUN_ID: self._params.get(DocpipeConstants.JOB_RUN_ID),
                },
            )

    def _add_empty_docs_to_skipped_metadata(
        self, *, table: pa.Table, empty_doc_indices: list, metadata: dict[str, Any]
    ):
        """
        Add empty documents to the skipped documents list in metadata.

        Args:
            table: The PyArrow table containing all documents
            empty_doc_indices: List of indices for documents with empty content
            metadata: Metadata dictionary to update
        """
        if not empty_doc_indices:
            return

        operator = self.get_operator()

        # Extract columns once for better performance
        id_col = table[OperatorConstants.Columns.ID] if OperatorConstants.Columns.ID in table.column_names else None
        name_col = (
            table[OperatorConstants.Columns.NAME] if OperatorConstants.Columns.NAME in table.column_names else None
        )

        for idx in empty_doc_indices:
            doc_id = id_col[idx].as_py() if id_col is not None else f"doc_{idx}"
            doc_name = name_col[idx].as_py() if name_col is not None else f"document_{idx}"

            logger.info(
                f"Skipping document '{doc_name}' (ID: {doc_id}) due to empty content",
                extra={
                    DocpipeConstants.JOB_ID: self._params.get(DocpipeConstants.JOB_ID),
                    DocpipeConstants.JOB_RUN_ID: self._params.get(DocpipeConstants.JOB_RUN_ID),
                },
            )

            operator.record_skipped_document(
                metadata=metadata, doc_id=str(doc_id), doc_name=str(doc_name), reason="Extracted content is empty"
            )

        # Update processed_docs count to exclude empty documents
        if Metrics.External.PROCESSED_DOCS in metadata:
            metadata[Metrics.External.PROCESSED_DOCS] = metadata[Metrics.External.PROCESSED_DOCS] - len(
                empty_doc_indices
            )

        # Update node status to indicate completion with warnings if there are skipped docs
        if empty_doc_indices:
            metadata[Metrics.External.NODE_STATUS] = OperatorUtils.merge_status(
                metadata.get(Metrics.External.NODE_STATUS, ExecutionStatus.COMPLETED.value),
                ExecutionStatus.COMPLETED_WITH_WARNINGS.value,
            )

    def _handle_empty_documents(
        self, *, out_tables: list[pa.Table], metadata: dict[str, Any]
    ) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Handle empty documents after operator execution.
        - Check if DOC_COLUMN is empty for any documents
        - Save empty docs to incremental processing metadata
        - Remove empty docs from the PyArrow table
        - Add empty docs as skipped documents in metadata

        Args:
            out_tables: List of output PyArrow tables from operator execution
            metadata: Metadata dictionary from operator execution

        Returns:
            tuple: (processed_tables, updated_metadata)
        """
        if not out_tables or len(out_tables) == 0:
            return out_tables, metadata

        processed_tables = []
        operator = self.get_operator()
        doc_column = getattr(operator, "doc_column", OperatorConstants.Columns.DOC_COLUMN_DEFAULT)

        for item in out_tables:
            # Handle nested lists (e.g., from branching operator which returns multiple branches)
            if isinstance(item, list):
                processed_branch = []
                for table in item:
                    processed_table = self._process_table_for_empty_docs(
                        table=table, doc_column=doc_column, metadata=metadata
                    )
                    processed_branch.append(processed_table)
                processed_tables.append(processed_branch)
            else:
                processed_table = self._process_table_for_empty_docs(
                    table=item, doc_column=doc_column, metadata=metadata
                )
                processed_tables.append(processed_table)

        return processed_tables, metadata
