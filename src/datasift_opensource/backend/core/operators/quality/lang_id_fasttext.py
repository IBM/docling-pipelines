"""
FastText Language Detection Operator

This operator detects document language using Facebook's FastText model (176+ languages).
It implements efficient memory management through reference counting for parallel flow execution.
"""

from logging import Logger
from typing import Any

import pyarrow as pa
from data_processing.utils.transform_utils import TransformUtils

from common.constants.constants import (
    AttributeDataTypes,
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
)
from common.constants.operator_constants import OperatorConstants
from common.util.infrastructure.logging import get_logger
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.operator_utils import OperatorUtils
from core.operators.quality.fasttext_model_manager import FastTextModelManager

logger: Logger = get_logger()


class LanguageDetectFastText(AbstractOperator):
    """
    Detects language using FastText model.

    Features:
    - 176+ language support
    - Memory-efficient singleton model with reference counting
    - Configurable filtering of unknown languages
    """

    short_name: str = OperatorConstants.Operators.LANG_DETECT_FASTTEXT
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

        # Initialize model manager and acquire model
        self.model_manager = FastTextModelManager()
        self.fasttext_model: Any | None = None

        try:
            self.fasttext_model = self.model_manager.acquire_model()
            logger.info(
                f"FastText model acquired successfully. Reference count: {self.model_manager.get_ref_count()}",
                extra=self.common_log_arguments,
            )
        except Exception as e:
            logger.error(
                f"Failed to acquire FastText model: {e}",
                extra=self.common_log_arguments,
            )
            self.fasttext_model = None

    def cleanup(self) -> None:
        """
        Release the FastText model when operator is done.
        This is called by the orchestrator in the finally block.
        """
        if self.fasttext_model is not None:
            self.model_manager.release_model()
            logger.info(
                f"FastText model released. Reference count: {self.model_manager.get_ref_count()}",
                extra=self.common_log_arguments,
            )
            self.fasttext_model = None

    def get_metadata(self) -> dict[str, Any]:
        operator_metadata = {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: self.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.Misc.LABEL: "Language Annotator (FastText)",
            OperatorConstants.Config.DESCRIPTION: "Detects document language using FastText model (176+ languages)",
            OperatorConstants.Config.ATTRIBUTES: {
                OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE: {
                    OperatorConstants.Misc.NAME: "Filter Unknown Language document",
                    OperatorConstants.Config.DESCRIPTION: "Filters out all documents that have no language detected",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
            },
            OperatorConstants.Config.FEATURES: {
                OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY: {
                    OperatorConstants.Misc.NAME: "Language Name",
                    OperatorConstants.Config.DESCRIPTION: "This stores the language of the document (ISO 639-1 code)",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Columns.LANGUAGE_SCORE_COLUMN_KEY: {
                    OperatorConstants.Misc.NAME: "Language score",
                    OperatorConstants.Config.DESCRIPTION: "Probability score of the language detection",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_FLOAT,
                },
            },
        }

        return operator_metadata

    def get_required_features(self) -> list[str]:
        return [self.doc_column_name]

    def _detect_with_fasttext(self, text: str) -> tuple[str, float]:
        """
        Detect language using FastText model.

        Returns:
            Tuple of (language_code, confidence_score)
        """
        if self.fasttext_model is None:
            raise RuntimeError("FastText model not available")

        # Clean text for better detection
        cleaned_text = text.replace("\n", " ").strip()
        if not cleaned_text:
            raise ValueError("Empty text provided")

        # FastText returns predictions in format: (('__label__en',), array([0.99]))
        predictions = self.fasttext_model.predict(cleaned_text, k=1)

        # Extract language code (remove '__label__' prefix)
        # predictions[0] is a tuple of labels, predictions[1] is array of probabilities
        if len(predictions) >= 2 and len(predictions[0]) > 0 and len(predictions[1]) > 0:
            language_code = predictions[0][0].replace("__label__", "")
            confidence = float(predictions[1][0])
            return language_code, confidence
        else:
            raise ValueError("FastText returned invalid predictions")

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Detects language and confidence score for each document using FastText.
        """

        OperatorUtils.validate_columns(table=table, required=[self.doc_column_name], operator_name=self.short_name)

        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=OperatorUtils.find_doc_count(table=table))

        new_doc_content: list[Any] = table[self.doc_column_name].to_pylist()
        language_name_column: list[str] = []
        language_score_column: list[float] = []
        remove_row_idx: list[int] = []
        message: str = ""

        fasttext_success_count = 0

        for idx, doc_content in enumerate(new_doc_content):
            file_name_list: list[Any] = table[OperatorConstants.Misc.NAME].to_pandas().to_list()
            file_name: Any = file_name_list[idx] if idx < len(file_name_list) else "unknown"

            language_name: str = "UNKNOWN"
            language_score: float = 0.0

            try:
                if self.fasttext_model is None:
                    raise RuntimeError("FastText model not available")

                language_name, language_score = self._detect_with_fasttext(doc_content)
                fasttext_success_count += 1
                language_name_column.append(language_name)
                language_score_column.append(language_score)

            except Exception as e:
                if self.filter_value:
                    logger.error(
                        f"Language detection failed for document {file_name}: {e}",
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
                    language_score = 0.0
                    metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.COMPLETED_WITH_WARNINGS.value
                    logger.warning(
                        f"Exception for document {file_name}: {e}",
                        extra=self.common_log_arguments,
                    )
                    language_name_column.append(language_name)
                    language_score_column.append(language_score)
                    if not message:
                        message = "Documents with no language detected are marked as UNKNOWN"

        # Log detection statistics
        logger.info(
            f"Language detection completed. FastText: {fasttext_success_count}, Failed: {len(remove_row_idx)}",
            extra=self.common_log_arguments,
        )

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
            "Completed FastText language detect transform function",
            extra=self.common_log_arguments,
        )

        metadata[Metrics.External.PROCESSED_DOCS] = (
            metadata[Metrics.External.TOTAL_DOCS] - metadata[Metrics.External.FAILED_DOCS_COUNT]
        )
        metadata[Metrics.External.PROCESSED_ROWS] = table.num_rows

        if message:
            metadata[Metrics.External.PROCESSING_MESSAGE] = message

        return [table], metadata

