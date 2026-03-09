from typing import Any, Optional
from dpk_ededup import (
    EdedupTransform,
    HashFilter,
    doc_column_name_key,
    int_column_name_key,
    short_name,
)

import pyarrow as pa

from common.util.constants import (
    OperatorConstants,
    DatasiftConstants,
    Metrics,
    ExecutionStatus,
)
from common.util.operator_utils import find_doc_count
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.operator_utils import OperatorUtils
from common.util.log import get_logger

FILTER_KEY: str = "filter"

logger = get_logger()


class EdedupOperator(AbstractOperator):  # pragma: no cover
    """
    Ededup (Exact De-duplication) Operator is an exact deduplication operator which can be added after Extract Operator,
    so that if there are exact duplicate documents that are extracted, it will be removed from the pyarrow table before
    proceeding with other subsequent operators. This will save time and processing power to a great extent.
    """

    short_name: str = short_name
    category: OperatorCategory = OperatorCategory.Quality

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize based on the dictionary of parameters.
        Parameters are: {"doc_column": "content", "doc_id_column": "doc_id_hash}
        """
        super().__init__(config)
        self.doc_column: str = config.get(
            OperatorConstants.DOC_COLUMN, OperatorConstants.DOC_COLUMN_DEFAULT
        )
        self.doc_id_column: str = config.get(
            OperatorConstants.DOC_ID_HASH, OperatorConstants.DOC_ID_HASH_DEFAULT
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
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }

    def get_metadata(self) -> dict[str, Any]:

        return {
            OperatorConstants.CATEGORY: self.category.value,
            OperatorConstants.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.LABEL: "De-duplicator",
        }

    def transform(
        self, table: pa.Table, file_name: Optional[str] = None
    ) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Performs exact deduplication of contents on the ededup_input pyarrow table and generates a list of output pyarrow
        tables and metadata after removing duplicates based on central hashing. It uses Data Prep Toolkit's Exact
        deduplication transform that identifies and removes identical documents in a dataset by comparing them
        hash-for-hash to ensure exact matching.
        """

        ededup_transform: EdedupTransform = EdedupTransform(self.config)

        logger.info(
            ">> Running Exact Deduplication Operation on Pyarrow tables as ededup_input",
            extra=self.common_log_arguments,
        )
        output_tables: list[pa.Table] = []
        metadata: dict[str, Any] = {}
        try:
            if table:
                output_tables, _metadata = ededup_transform.transform(
                    table=table, file_name=file_name
                )
                logger.info(
                    ">> Exact Deduplication Successful!!",
                    extra=self.common_log_arguments,
                )
                logger.info(f"Metadata : {_metadata}", extra=self.common_log_arguments)
                metadata = self.create_base_metadata(
                    total_docs_count=_metadata.get("source_documents")
                )
                metadata[Metrics.External.PROCESSED_DOCS] = _metadata.get(
                    "result_documents"
                )
                metadata[Metrics.External.SKIPPED_DOCS_COUNT] = _metadata.get(
                    "source_documents"
                ) - _metadata.get("result_documents")
                metadata[Metrics.External.REMOVED_DOCUMENTS] = len(
                    _metadata.get("removed_documents")
                )
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
                total_docs: int = find_doc_count(table=table)
                metadata = self.create_base_metadata(
                    total_docs_count=total_docs,
                    node_status=ExecutionStatus.COMPLETED_WITH_WARNINGS.value,
                )
                metadata[Metrics.External.FAILED_DOCS_COUNT] = total_docs
                metadata[Metrics.External.REMOVED_DOCUMENTS] = 0

        return output_tables, metadata


def main() -> None:  # pragma: no cover
    # 1. Create a Pyarrow table
    content: list[str] = [
        "Document content 1",
        "Document content 2",
        "Document content 1",
    ]
    doc_id_hash: list[str] = [str(101), str(102), str(103)]
    id: list[str] = [str(101), str(102), str(103)]
    name: list[str] = ["Doc 1", "Doc 2", "Doc 3"]

    data: dict[str, list[str]] = {
        OperatorConstants.DOC_COLUMN_DEFAULT: content,
        OperatorConstants.DOC_ID_HASH_DEFAULT: doc_id_hash,
        OperatorConstants.ID: id,
        OperatorConstants.NAME: name,
    }

    input_table: pa.Table = pa.table(data)
    logger.info(f"\nInput Pyarrow Table : {input_table}\n")

    config: dict[str, Any] = {}

    operator: EdedupOperator = EdedupOperator(config=config)

    print(operator)

    table: list[pa.Table]
    metadata: dict[str, Any]
    table, metadata = operator.transform(input_table)
    logger.info(f"Ededup Output Table : {table}")
    logger.info(f"Ededup Output MetaData : {metadata}")


if __name__ == "__main__":  # pragma: no cover
    exit(main())
