# Assisted by watsonx Code Assistant
import os
from typing import Any

import pyarrow as pa

from datasift.core.constants.constants import DatasiftConstants
from datasift.core.constants.operator_constants import OperatorConstants
from datasift.exceptions.datasift_exceptions import FlowExecutionFailedException
from datasift.utils.data.incremental_metadata_store import (
    IncrementalMetadataRecord,
    IncrementalMetadataStore,
    create_incremental_metadata_store,
)
from datasift.utils.data.pyarrow_handler import (
    BaseParquetTableHandler,
    get_parquet_table_handler,
)
from datasift.utils.infrastructure.filesystem import get_data_path
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger(f"{DatasiftConstants.LOGGER_NAME} : INCREMENTAL UPDATE")


class IncrementalUpdateUtil:
    NAMESPACE = "datasift"
    TABLE_NAME = "incremental_update_metadata"
    INCREMENTAL_PROCESSING_METADATA_PATH = "/inc_process_metadata"
    PARQUET_FILE_NAME = "inc_update_metadata.parquet"

    def __init__(self, *, store: IncrementalMetadataStore | None = None, flow_config: dict[str, Any] | None = None):
        """
        Initialize IncrementalUpdateUtil with optional store or flow-level config.

        Args:
            store: Optional pre-configured store instance
            flow_config: Optional flow-level incremental metadata config from global_config.incremental_metadata
        """
        if store is not None:
            self.store = store
        else:
            self.store = create_incremental_metadata_store(flow_config=flow_config)
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
        try:
            records: list[IncrementalMetadataRecord] = []
            failed_doc_ids_set = set(failed_doc_ids or [])

            for table in tables:
                if table.num_rows == 0:
                    continue

                table = table.select(
                    [
                        OperatorConstants.Misc.ID,
                        OperatorConstants.Misc.NAME,
                        OperatorConstants.Metadata.MODIFIED_TIME,
                    ]
                )

                filtered_table = self.filter_rows(table=table, ids_to_delete=list(failed_doc_ids_set))
                if filtered_table is None or filtered_table.num_rows == 0:
                    continue

                records.extend(
                    self._prepare_records_for_save(
                        table=filtered_table,
                        job_id=job_id,
                        job_run_id=job_run_id,
                    )
                )

            if not records:
                return

            self.store.upsert_records(job_id=job_id, job_run_id=job_run_id, records=records)
            logger.info(
                f"Incremental metadata saved successfully for job_id={job_id}, job_run_id={job_run_id}, records={len(records)}"
            )
        except Exception as exc:
            raise FlowExecutionFailedException(
                f"Failed to save incremental metadata for job_id={job_id}, job_run_id={job_run_id}. Error: {exc!s}"
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
        ids_to_delete_set = set(ids_to_delete)
        filtered_rows = [
            row for row in table.to_pylist() if row.get(OperatorConstants.Misc.ID) not in ids_to_delete_set
        ]
        return pa.Table.from_pylist(filtered_rows, schema=table.schema)

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
        try:
            logger.debug(f"Retrieving processed documents for the job id {job_id}")
            return self.store.get_processed_docs(job_id=job_id)
        except Exception as exc:
            raise FlowExecutionFailedException(
                f"Failed to retrieve processed document ids for job_id={job_id}. Error: {exc!s}"
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
        try:
            previously_soft_deleted_doc_ids = self.get_soft_deleted_doc_ids(job_id=job_id)
            self.delete_docs_for_ids(doc_ids=list(previously_soft_deleted_doc_ids), job_id=job_id)
            return self.store.mark_missing_docs_as_deleted(job_id=job_id, doc_ids=doc_ids)
        except Exception as exc:
            raise FlowExecutionFailedException(
                f"Failed to mark soft deleted document ids for job_id={job_id}. Error: {exc!s}"
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
        try:
            return self.store.get_soft_deleted_doc_ids(job_id=job_id)
        except Exception as exc:
            raise FlowExecutionFailedException(
                f"Failed to retrieve soft deleted document ids for job_id={job_id}. Error: {exc!s}"
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
        try:
            if doc_ids:
                self.store.delete_docs(job_id=job_id, doc_ids=doc_ids)
        except Exception as exc:
            raise FlowExecutionFailedException(
                f"Failed to delete document ids for job_id={job_id}. Error: {exc!s}"
            ) from exc

    def clear_incremental_table(self, *, job_id):
        self.store.clear(job_id=job_id)
        table_path = self.construct_table_path(job_id=job_id)
        self.parquet_table_handler.delete_file(path=table_path)

    def construct_table_path(self, *, job_id: str):
        return os.path.join(
            get_data_path(sub_dir=self.INCREMENTAL_PROCESSING_METADATA_PATH),
            job_id,
            self.PARQUET_FILE_NAME,
        )

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

    def _get_soft_deleted_ids(self, *, table: pa.Table) -> set:
        soft_deleted_ids: set[str] = set()

        if table is None or table.num_rows == 0:
            return soft_deleted_ids

        for row in table.to_pylist():
            if row.get(OperatorConstants.Misc.DELETED):
                soft_deleted_ids.add(row[OperatorConstants.Misc.ID])

        return soft_deleted_ids

    def _prepare_records_for_save(
            self,
            *,
            table: pa.Table,
            job_id: str,
            job_run_id: str,
    ) -> list[IncrementalMetadataRecord]:
        rows = table.to_pylist()

        return [
            IncrementalMetadataRecord(
                job_id=job_id,
                doc_id=row[OperatorConstants.Misc.ID],
                name=row.get(OperatorConstants.Misc.NAME),
                modified_time=row.get(OperatorConstants.Metadata.MODIFIED_TIME),
                job_run_id=job_run_id,
                deleted=False,
            )
            for row in rows
            if row.get(OperatorConstants.Misc.ID)
        ]

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
