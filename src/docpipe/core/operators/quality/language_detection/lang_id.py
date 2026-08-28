from logging import Logger
from typing import Any

import pyarrow as pa
from data_processing.utils.transform_utils import TransformUtils

# Import adapters to trigger registration
import docpipe.core.operators.quality.language_detection.adapters.outbound  # noqa: F401
from docpipe.core.constants import OperatorConstants
from docpipe.core.constants.constants import AttributeDataTypes, DocpipeConstants, ExecutionStatus, Metrics
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.core.operators.quality.language_detection.adapters.outbound.factories.language_adapter_factory import (
    LanguageAdapterFactory,
)
from docpipe.core.operators.quality.language_detection.ports.outbound.language_service import LanguageServicePort
from docpipe.utils.infrastructure.logging import get_logger

logger: Logger = get_logger()

# Default language detection provider
DEFAULT_LANGUAGE_PROVIDER = "fasttext"
LANGUAGE_PROVIDER_KEY = "language_provider"


class LanguageDetect(AbstractOperator):
    """
    Language Detection Operator

    This operator detects the language of document content and provides confidence scores.
    It supports multiple language detection providers through a pluggable adapter system.

    Features:
    - Automatic language detection for documents
    - Confidence scores for detection accuracy
    - Optional filtering of documents with unknown languages
    - Support for multiple language detection providers
    """

    short_name: str = OperatorConstants.Operators.LANG_DETECT
    category: OperatorCategory = OperatorCategory.Quality
    owner = DocpipeConstants.OWNER_DOCPIPE

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the Language Detection Operator.

        Args:
            config: Configuration dictionary containing:
                - doc_column: Input column containing document content (default: "content")
                - filter_unknown_language: Whether to filter out documents with unknown language (default: False)
                - language_provider: Language detection provider to use (default: "fasttext")
        """
        super().__init__(config)
        self.common_log_arguments: dict[str, Any] = {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
        }
        self.filter_value: bool = config.get(OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE, False)

        # Get language detection provider from config (default: fasttext)
        self.language_provider: str = config.get(LANGUAGE_PROVIDER_KEY, DEFAULT_LANGUAGE_PROVIDER)

        # Initialize language detection adapter
        self.language_adapter: LanguageServicePort = self._initialize_language_adapter()

        logger.info(
            f"Initialized LanguageDetect operator with provider: {self.language_provider}",
            extra=self.common_log_arguments,
        )

    def _initialize_language_adapter(self) -> LanguageServicePort:
        """
        Initialize the language detection adapter based on configuration.

        This method creates and returns the appropriate adapter using LanguageAdapterFactory.
        The adapter is stored as self.language_adapter for reuse across multiple
        language detection operations.

        Returns:
            LanguageServicePort: Initialized language detection adapter

        Raises:
            ValueError: If the adapter cannot be initialized
        """
        try:
            adapter = LanguageAdapterFactory.create(adapter_name=self.language_provider)
            logger.info(
                f"Successfully initialized {self.language_provider} adapter",
                extra=self.common_log_arguments,
            )
            return adapter
        except ValueError as e:
            available_providers = LanguageAdapterFactory.list_adapters()
            logger.error(
                f"Failed to initialize language provider '{self.language_provider}': {e}. "
                f"Available providers: {available_providers}",
                extra=self.common_log_arguments,
            )
            raise

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """Get metadata."""
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: LanguageDetect.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: LanguageDetect.is_available(),
            OperatorConstants.Misc.LABEL: "Language Annotator",
            OperatorConstants.Config.DESCRIPTION: "Detect the language of each document and annotate with language name and confidence score.",
            OperatorConstants.Config.ATTRIBUTES: {
                LANGUAGE_PROVIDER_KEY: {
                    OperatorConstants.Misc.NAME: "Language Detection Provider",
                    OperatorConstants.Config.DESCRIPTION: "Language detection provider to use (fasttext or langdetect)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: DEFAULT_LANGUAGE_PROVIDER,
                    OperatorConstants.Config.VALID_VALUES: LanguageAdapterFactory.list_adapters(),
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
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

    @staticmethod
    def get_required_features() -> list[str]:
        """Get required features."""
        return [OperatorConstants.Columns.DOC_COLUMN_DEFAULT]

    def cleanup(self) -> None:
        """Release adapter resources.

        This method is called by the orchestrator to ensure proper cleanup
        of resources held by the language detection adapter.
        """
        if hasattr(self, "language_adapter") and self.language_adapter is not None:
            self.language_adapter.cleanup()
            logger.info(
                f"Released resources for {self.language_provider} adapter",
                extra=self.common_log_arguments,
            )

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Detects all the available language and their respective score in the document
        """

        OperatorUtils.validate_columns(table=table, required=[self.doc_column], operator_name=self.short_name)

        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=OperatorUtils.find_doc_count(table=table))

        new_doc_content: list[Any] = table[self.doc_column].to_pylist()
        language_name_column: list[str] = []
        language_score_column: list[float] = []
        remove_row_idx: list[int] = []
        message: str = ""

        for idx, doc_content in enumerate(new_doc_content):
            file_name_list: list[Any] = table[OperatorConstants.Misc.NAME].to_pandas().to_list()
            file_name: Any = file_name_list[idx] if idx < len(file_name_list) else "unknown"
            try:
                result = self.language_adapter.detect_language(doc_content)
                language_name_column.append(result.language_code)
                language_score_column.append(result.confidence)
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
