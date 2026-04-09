# Assisted by watsonx Code Assistant
import os
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc

from common.constants.constants import DatasiftConstants
from common.constants.operator_constants import OperatorConstants
from common.exceptions.datasift_exceptions import FlowExecutionFailedException
from common.util.data.pyarrow_handler import (
    BaseParquetTableHandler,
    get_parquet_table_handler,
)
from common.util.infrastructure.filesystem import get_data_path
from common.util.infrastructure.logging import get_logger

logger = get_logger(f"{DatasiftConstants.LOGGER_NAME} : INCREMENTAL UPDATE")


class IncrementalUpdateUtil:
    NAMESPACE = "datasift"
    TABLE_NAME = "incremental_update_metadata"
    INCREMENTAL_PROCESSING_METADATA_PATH = "/inc_process_metadata"
    PARQUET_FILE_NAME = "inc_update_metadata.parquet"

    def __init__(self):
        self.parquet_table_handler: BaseParquetTableHandler = get_parquet_table_handler()

    def delete_failed_doc(self, *, table, result_table, job_id):
        """
        Delete documents that failed processing and return the remaining document IDs.

        Args:
            table (pyarrow.Table): The input table containing document IDs.
            result_table (pyarrow.Table): The result table containing document IDs.
            job_id (str): The job ID.

        Returns:
            set: A set of remaining document IDs after deleting failed documents.
        """
        ids_to_delete = self._get_ids_to_delete(input_table=table, result_table=result_table)
        self.delete_docs_for_ids(doc_ids=ids_to_delete, job_id=job_id)
        return set(table[OperatorConstants.Misc.ID].to_pylist()) if table.num_rows != 0 else set()

    def save_metadata_for_incremental_update(
        self, *, job_id, job_run_id, tables: list[pa.Table], failed_doc_ids: list[Any] | None = None
    ):
        """
        Save incremental metadata table to cloud storage.

        Args:
            job_id (str): The job ID.
            job_run_id (str): The job run ID.
            table (pyarrow.Table): The table containing metadata.

        Returns:
            None

        Raises:
            Exception: If saving incremental metadata fails.
        """
        table_path = self.construct_table_path(job_id=job_id)
        try:
            table_to_save = None
            for table in tables:
                if table.num_rows != 0:
                    table = self._prepare_table_for_save(table=table, job_id=job_id, job_run_id=job_run_id)
                    if not table_to_save:
                        table_to_save = table
                    else:
                        table_to_save = self.concatenate_tables(table1=table_to_save, table2=table)
            if not table_to_save:
                return

            table_to_save = self.filter_rows(table=table_to_save, ids_to_delete=failed_doc_ids)
            existing_table: pa.Table | None = self._get_table(path=table_path)

            if not existing_table:
                self.parquet_table_handler.save_table(path=table_path, table=table_to_save)
            else:
                # remove the redundant columns, if exist
                updated_table = self._remove_columns_from_saved_table(table=existing_table)
                table_to_save = self.concatenate_tables(table1=table_to_save, table2=updated_table)

                self.parquet_table_handler.save_table(path=table_path, table=table_to_save)

            logger.info(
                f"Incremental metadata table saved successfully for job_id: {job_id}, job_run_id: {job_run_id}, at path: {table_path}"
            )

        except Exception as exc:
            raise FlowExecutionFailedException(
                f"Failed to save incremental metadata for job_id={job_id}, job_run_id={job_run_id} at {table_path}. Error: {exc!s}"
            ) from exc

    def concatenate_tables(self, *, table1: pa.Table, table2: pa.Table):
        """Concatenates the 2 tables that have same schema.
        If same document exists in both the tables, it retains the doc from table1."""
        # First delete the rows that are processed in this execution
        ids_to_delete = list(table1.column(OperatorConstants.Misc.ID).to_pylist())
        filtered_table2 = self.filter_rows(table=table2, ids_to_delete=ids_to_delete)

        # Add the metadata of processed documents in this execution
        return pa.concat_tables([table1, filtered_table2])

    def filter_rows(self, *, table, ids_to_delete):
        if not table or not ids_to_delete:
            return table
        column = table.column(OperatorConstants.Misc.ID)
        mask = pc.is_in(column, value_set=pa.array(ids_to_delete))
        inverted_mask = pc.invert(mask)
        return table.filter(mask=inverted_mask)

    def get_all_processed_docs(self, *, job_id: str) -> dict[str, Any]:
        """
        Retrieve processed document IDs with modification_time for a given job ID.
        Note that soft deleted documents will not be returned.
        Retrieve processed document IDs for a given job ID.

        Args:
            job_id (str): The job ID.
            doc_ids_with_modified_time (dict): A dictionary mapping document IDs to their modified times.

        Returns:
            set: A set of processed document IDs.

        Raises:
            Exception: If retrieving processed document IDs fails.
        """
        table_path = self.construct_table_path(job_id=job_id)
        try:
            logger.debug(f"Retrieving processed documents for the job id {job_id}")
            filters = [(OperatorConstants.Misc.DELETED, "=", False)]
            columns = [OperatorConstants.Misc.ID, OperatorConstants.Metadata.MODIFIED_TIME]
            table: pa.Table | None = self._get_table(path=table_path, filters=filters, columns=columns)
            if not table:
                return {}
            df = table.to_pandas()
            return dict(zip(df[OperatorConstants.Misc.ID], df[OperatorConstants.Metadata.MODIFIED_TIME], strict=False))
        except Exception as exc:
            raise FlowExecutionFailedException(
                f"Failed to retrieved process document ids for job_id={job_id} at {table_path}. Error: {exc!s}"
            ) from exc

    def get_deleted_doc_ids_from_dict(self, *, previously_processed_docs_dict: dict, doc_ids):
        """Returns a list of deleted document ids that exist in previously_processed_docs_dict and not in doc_ids."""
        if not previously_processed_docs_dict:
            return []
        return list(set(previously_processed_docs_dict.keys()) - set(doc_ids))

    def process_ingested_docs(self, *, config: dict, job_id, doc_ids: list):
        """
        Updates incremental processing metadata based on the configuration with the documents identified by the ingest operator
        """
        if config.get(DatasiftConstants.FORCE_INGEST):
            # If force_ingest is set, then delete all the previously saved metadata, to mimic a fresh ingest
            self.clear_incremental_table(job_id=job_id)

        if bool(config.get(DatasiftConstants.RETAIN_DELETED_DOCS, DatasiftConstants.RETAIN_DELETED_DOCS_DEFAULT)):
            # If configured for retaining deleted documents, do not make any changes
            return
        self.mark_soft_deleted_docs(job_id=job_id, doc_ids=doc_ids)

    def mark_soft_deleted_docs(self, *, job_id, doc_ids: list):
        """
        Mark documents as soft-deleted for a given job ID and return the deleted document IDs.

        Args:
            job_id (str): The job ID.
            doc_ids (list): A list of document IDs to mark as soft-deleted.

        Returns:
             set: A set of document IDs marked as soft-deleted.

        Raises:
            Exception: If marking documents as soft-deleted fails.
        """
        table_path = self.construct_table_path(job_id=job_id)
        try:
            # First delete previously marked as DELETED documents from previous execution
            previously_soft_deleted_doc_ids = self.get_soft_deleted_doc_ids(job_id=job_id)
            self.delete_docs_for_ids(doc_ids=list(previously_soft_deleted_doc_ids), job_id=job_id)

            table: pa.Table | None = self._get_table(path=table_path)
            doc_ids_set = set(doc_ids)
            if table is None or table.num_rows == 0:
                return doc_ids_set

            updated_table, doc_ids_to_delete = self._mark_docs_to_delete(table=table, doc_ids=doc_ids_set)
            logger.info(
                f"Marking soft deleted this document ids {doc_ids_to_delete} updating the table located at {table_path}"
            )
            self.parquet_table_handler.save_table(path=table_path, table=updated_table)
            logger.info("Successfully marked soft deleted in the table")
            return doc_ids_to_delete
        except Exception as exc:
            raise FlowExecutionFailedException(
                f"Failed to marked soft deleted document ids for job_id={job_id} at {table_path}. Error: {exc!s}"
            ) from exc

    def get_soft_deleted_doc_ids(self, *, job_id):
        """
        Retrieve the set of soft-deleted document IDs for a given job ID.

        Args:
            job_id (str): The job ID.

        Returns:
            Set: A set of soft-deleted document IDs.

        Raises:
            Exception: If retrieving soft-deleted document IDs fails.
        """
        table_path = self.construct_table_path(job_id=job_id)
        try:
            logger.info(
                f"Retrieving the soft deleted document ids for the job id {job_id} from the table located at the {table_path}"
            )
            table: pa.Table | None = self._get_table(path=table_path)
            logger.info(f"Fetched soft deleted document IDs for job_id={job_id} from {table_path}")
            return self._get_soft_deleted_ids(table=table)
        except Exception as exc:
            raise FlowExecutionFailedException(
                f"Failed to retrieved soft deleted document ids for job_id={job_id} at {table_path}. Error: {exc!s}"
            ) from exc

    def delete_docs_for_ids(self, *, doc_ids: list, job_id):
        """
        Delete rows with given document IDs for a specific job ID.

        Args:
            doc_ids (list): A list of document IDs to delete.
            job_id (str): The job ID.

        Returns:
            None

        Raises:
            Exception: If deleting document IDs fails.
        """
        table_path = self.construct_table_path(job_id=job_id)
        try:
            if doc_ids:
                logger.info(f"Deleting rows with doc_ids for job_id={job_id} from table at {table_path}")

                doc_ids_set = pa.array(doc_ids)
                delete_filter_fn = lambda table: pc.is_in(table[OperatorConstants.Misc.ID], value_set=doc_ids_set)  # noqa: E731
                self.parquet_table_handler.delete_rows(path=table_path, delete_filter_fn=delete_filter_fn)
                logger.info(f"Successfully deleted rows with doc_ids for job_id={job_id} from table at {table_path}")
        except Exception as exc:
            raise FlowExecutionFailedException(
                f"Failed to delete document ids for job_id={job_id} at {table_path}. Error: {exc!s}"
            ) from exc

    def clear_incremental_table(self, *, job_id):
        table_path = self.construct_table_path(job_id=job_id)
        self.parquet_table_handler.delete_file(path=table_path)

    def _get_table(self, *, path: str, filters=None, columns=None) -> pa.Table | None:
        try:
            logger.info(f"Fetching incremental metadata table located at '{path}")
            table: pa.Table | None = self.parquet_table_handler.read_table(path=path, filters=filters, columns=columns)
            if not table:
                return None
            logger.info(f"Successfully fetched the incremental metadata table located at {path}")
            return table
        except Exception as exc:
            raise FlowExecutionFailedException(
                f"An error occurred while fetching the incremental metadata table at '{path}'. Error details: {exc!s}"
            ) from exc

    def construct_table_path(self, *, job_id: str):
        return os.path.join(
            get_data_path(sub_dir=self.INCREMENTAL_PROCESSING_METADATA_PATH),
            job_id,
            self.PARQUET_FILE_NAME,
        )

    def _prepare_table_for_save(self, *, table: pa.Table, job_id, job_run_id):
        """
        Prepares a table for saving by appending job_id, job_run_id, and a DELETED column.

        Args:
            table (pyarrow.Table): The input table.
            job_id (str): The job ID.
            job_run_id (str): The job run ID.

        Returns:
            pyarrow.Table: The modified table with additional columns.
        """
        columns = [
            OperatorConstants.Misc.ID,
            OperatorConstants.Misc.NAME,
            OperatorConstants.Metadata.MODIFIED_TIME,
        ]
        total_rows = table.num_rows
        table_to_save = table.select(columns)

        job_id_column = pa.array([job_id] * total_rows)
        table_to_save = table_to_save.append_column(DatasiftConstants.JOB_ID, job_id_column)

        job_run_id_column = pa.array([job_run_id] * total_rows)
        table_to_save = table_to_save.append_column(DatasiftConstants.JOB_RUN_ID, job_run_id_column)

        deleted_column = pa.array([False] * total_rows)
        table_to_save = table_to_save.append_column(OperatorConstants.Misc.DELETED, deleted_column)

        return table_to_save

    def _remove_columns_from_saved_table(self, *, table: pa.Table):
        """If the saved table has redundant columns, they will be removed."""
        columns = [
            OperatorConstants.Misc.ID,
            OperatorConstants.Misc.NAME,
            OperatorConstants.Metadata.MODIFIED_TIME,
            DatasiftConstants.JOB_ID,
            DatasiftConstants.JOB_RUN_ID,
            OperatorConstants.Misc.DELETED,
        ]
        return table.select(columns)

    def _get_soft_deleted_ids(self, *, table: pa.Table) -> set:
        """
        Determine the set of soft-deleted document IDs.

        Args:
            table (pyarrow.Table): The table containing document IDs and deleted flags.

        Returns:
            set: A set of soft-deleted document IDs.
        """
        soft_deleted_ids = set()

        if table is None or table.num_rows == 0:
            return soft_deleted_ids

        for row in table.to_pylist():
            if row.get(OperatorConstants.Misc.DELETED):
                soft_deleted_ids.add(row[OperatorConstants.Misc.ID])

        return soft_deleted_ids

    def _get_ids_to_delete(self, *, input_table: pa.Table, result_table: pa.Table) -> list:
        """
        Determine document IDs to delete based on input and result tables.

        Args:
            input_table (pyarrow.Table): Input table with document IDs.
            result_table (pyarrow.Table): Result table with document IDs.

        Returns:
            list: Document IDs to delete.
        """
        input_doc_ids = set(input_table[OperatorConstants.Misc.ID].to_pylist()) if input_table.num_rows != 0 else set()
        output_doc_ids = (
            set(result_table[OperatorConstants.Misc.ID].to_pylist()) if result_table.num_rows != 0 else set()
        )

        ids_to_delete = list(input_doc_ids - output_doc_ids)

        return ids_to_delete

    def _mark_docs_to_delete(self, *, table: pa.Table, doc_ids: set) -> tuple[pa.Table | None, set[str]]:
        """
        Identify documents that exist in table and not in doc_ids and mark them as soft-deleted.
        """
        try:
            db_doc_ids_set = set()
            doc_ids_set = doc_ids
            if table is None or table.num_rows == 0:
                return None, doc_ids_set

            for row in table.to_pylist():
                if row.get(OperatorConstants.Misc.ID):
                    db_doc_ids_set.add(row[OperatorConstants.Misc.ID])

            df = table.to_pandas()
            doc_ids_to_delete = db_doc_ids_set - doc_ids_set
            if doc_ids_to_delete:
                df.loc[
                    df[OperatorConstants.Misc.ID].isin(list(doc_ids_to_delete)),
                    OperatorConstants.Misc.DELETED,
                ] = True
            updated_table = pa.Table.from_pandas(df)

            return updated_table, doc_ids_to_delete

        except Exception as exc:
            raise FlowExecutionFailedException(
                f"An error occurred while marking documents soft soft deletion. Error details: {exc!s}"
            ) from exc
