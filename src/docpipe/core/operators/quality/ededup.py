from typing import Any

import pyarrow as pa
from dpk_ededup import (
    EdedupTransform,
    HashFilter,
    doc_column_name_key,
    int_column_name_key,
)

from docpipe.core.constants.constants import (
    DocpipeConstants,
    ExecutionStatus,
    Metrics,
)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.utils.infrastructure.logging import get_logger

FILTER_KEY: str = "filter"

logger = get_logger()


class EdedupOperator(AbstractOperator):
    """
    Ededup (Exact De-duplication) Operator is an exact deduplication operator which can be added after Extract Operator,
    so that if there are exact duplicate documents that are extracted, it will be removed from the pyarrow table before
    proceeding with other subsequent operators. This will save time and processing power to a great extent.
    """

    short_name: str = OperatorConstants.Operators.EDEDUP
    category: OperatorCategory = OperatorCategory.Quality
    owner = DocpipeConstants.OWNER_DOCPIPE

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize based on the dictionary of parameters.
        Parameters are: {"doc_column": "content", "doc_id_column": "doc_id_hash}
        """
        super().__init__(config)
        self.doc_id_column: str = config.get(
            OperatorConstants.Columns.DOC_ID_HASH, OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
        )
        self.filter: HashFilter = config.get(FILTER_KEY, HashFilter({}))
        self.config.update(
            {
                doc_column_name_key: self.doc_column,
                int_column_name_key: self.doc_id_column,
                FILTER_KEY: self.filter,
            }
        )
        self.common_log_arguments: dict[str, Any] = {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
        }
        self._ededup_transform: EdedupTransform = EdedupTransform(self.config)

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """Get metadata."""
        return {
            OperatorConstants.Misc.CATEGORY: EdedupOperator.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: EdedupOperator.is_available(),
            OperatorConstants.Misc.LABEL: "De-duplicator",
            OperatorConstants.Config.DESCRIPTION: "Exact deduplication operator that removes duplicate documents based on content hash",
        }

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Performs exact deduplication of contents on the ededup_input pyarrow table and generates a list of output pyarrow
        tables and metadata after removing duplicates based on central hashing. It uses Data Prep Toolkit's Exact
        deduplication transform that identifies and removes identical documents in a dataset by comparing them
        hash-for-hash to ensure exact matching.
        """

        logger.info(
            ">> Running Exact Deduplication Operation on Pyarrow tables as ededup_input",
            extra=self.common_log_arguments,
        )
        output_tables: list[pa.Table] = []
        metadata: dict[str, Any] = {}
        try:
            if table is not None and table.num_rows > 0:
                output_tables, _metadata = self._ededup_transform.transform(table=table, file_name=file_name)
                logger.info(
                    ">> Exact Deduplication Successful!!",
                    extra=self.common_log_arguments,
                )
                logger.info("Metadata : %s", _metadata, extra=self.common_log_arguments)
                metadata = self.create_base_metadata(total_docs_count=_metadata.get("source_documents"))
                metadata[Metrics.External.PROCESSED_DOCS] = _metadata.get("result_documents")
                metadata[Metrics.External.SKIPPED_DOCS_COUNT] = _metadata.get("source_documents") - _metadata.get(
                    "result_documents"
                )
                metadata[Metrics.External.REMOVED_DOCUMENTS] = len(_metadata.get("removed_documents"))
                metadata.update(
                    OperatorUtils.find_skipped_docs(
                        input_table=table,
                        output_table=output_tables[0],
                        reason="This document was identified as a duplicate and removed.",
                    )
                )
        finally:
            if not output_tables:
                output_tables = [table]
                logger.info(
                    ">> Exact Deduplication Not Successful!!",
                    extra=self.common_log_arguments,
                )
            if not metadata:
                total_docs: int = OperatorUtils.find_doc_count(table=table)
                metadata = self.create_base_metadata(
                    total_docs_count=total_docs,
                    node_status=ExecutionStatus.COMPLETED_WITH_WARNINGS.value,
                )
                metadata[Metrics.External.FAILED_DOCS_COUNT] = total_docs
                metadata[Metrics.External.REMOVED_DOCUMENTS] = 0

        return output_tables, metadata
