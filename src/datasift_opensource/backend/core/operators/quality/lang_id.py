from logging import Logger
from typing import Any

import pyarrow as pa
from data_processing.utils.transform_utils import TransformUtils
from langdetect import detect_langs

from common.constants import OperatorConstants
from common.constants.constants import (
    AttributeDataTypes,
    DatasiftConstants,
    ExecutionStatus,
    Metrics
)
from common.util.infrastructure.logging import get_logger
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.operator_utils import OperatorUtils

logger: Logger = get_logger()


class LanguageDetect(AbstractOperator):
    """
    Detects langauge and score.
    """

    short_name: str = OperatorConstants.Operators.LANG_DETECT
    category: OperatorCategory = OperatorCategory.Quality

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.doc_column_name: str = config.get(
            OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT
        )
        self.common_log_arguments: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }
        self.filter_value: bool = config.get(OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE, False)

    def get_metadata(self) -> dict[str, Any]:
        operator_metadata = {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: self.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.Misc.LABEL: "Language Annotator",
            OperatorConstants.Config.ATTRIBUTES: {
                OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE: {
                    OperatorConstants.Misc.NAME: "Filter Unknown Language document",
                    OperatorConstants.Config.DESCRIPTION: "Filters out all documents that have no language detected",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                }
            },
            OperatorConstants.Config.FEATURES: {
                OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY: {
                    OperatorConstants.Misc.NAME: "Language Name",
                    OperatorConstants.Config.DESCRIPTION: "This stores the language of the document",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Columns.LANGUAGE_SCORE_COLUMN_KEY: {
                    OperatorConstants.Misc.NAME: "Language score",
                    OperatorConstants.Config.DESCRIPTION: "Probability score of the language",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_FLOAT,
                },
            },
        }

        return operator_metadata

    def get_required_features(self) -> list[str]:
        return [self.doc_column_name]

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Detects all the available language and their respective score in the document
        """

        OperatorUtils.validate_columns(table=table, required=[self.doc_column_name], operator_name=self.short_name)

        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=OperatorUtils.find_doc_count(table=table))

        new_doc_content: list[Any] = table[self.doc_column_name].to_pylist()
        language_name_column: list[str] = []
        language_score_column: list[float] = []
        remove_row_idx: list[int] = []
        message: str = ""

        for idx, doc_content in enumerate(new_doc_content):
            file_name_list: list[Any] = table[OperatorConstants.Misc.NAME].to_pandas().to_list()
            file_name: Any = file_name_list[idx] if idx < len(file_name_list) else "unknown"
            try:
                language: list[Any] = detect_langs(doc_content)
                language_name: str
                language_score: str
                language_name, language_score = str(language[0]).split(":")
                language_name_column.append(language_name)
                language_score_column.append(float(language_score))
            except Exception as e:
                if self.filter_value:
                    logger.error(
                        f"Used defined error for document {file_name}: {e}",
                        extra=self.common_log_arguments,
                    )
                    remove_row_idx.append(idx)
                    self.record_failed_document(
                        metadata=metadata,
                        doc_id=table[OperatorConstants.Columns.ID][idx].as_py(),
                        doc_name=str(file_name),
                        reason=f"Filter out based on user selection with error: {getattr(e, 'message', str(e)) if getattr(e, 'message', str(e)) else getattr(e, 'message', repr(e))}",
                    )
                    metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.COMPLETED_WITH_ERRORS.value
                    if not message:
                        message = "Documents with no language detected are removed from the flow"
                else:
                    language_name = "UNKNOWN"
                    language_score_val: float = 0.0
                    metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.COMPLETED_WITH_WARNINGS.value
                    logger.warning(
                        f"Exception for document {file_name}: {e}",
                        extra=self.common_log_arguments,
                    )
                    language_name_column.append(language_name)
                    language_score_column.append(float(language_score_val))
                    if not message:
                        message = "Documents with no language detected are marked as UNKNOWN"

        table = OperatorUtils.remove_rows(table=table, remove_row_idx=remove_row_idx)

        table = TransformUtils.add_column(
            table=table,
            name=OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY,
            content=language_name_column,
        )
        table = TransformUtils.add_column(
            table=table,
            name=OperatorConstants.Columns.LANGUAGE_SCORE_COLUMN_KEY,
            content=language_score_column,
        )
        logger.info(
            "Completed Language detect transform function",
            extra=self.common_log_arguments,
        )

        metadata[Metrics.External.PROCESSED_DOCS] = (
            metadata[Metrics.External.TOTAL_DOCS] - metadata[Metrics.External.FAILED_DOCS_COUNT]
        )
        metadata[Metrics.External.PROCESSED_ROWS] = table.num_rows

        if message:
            metadata[Metrics.External.PROCESSING_MESSAGE] = message

        return [table], metadata


