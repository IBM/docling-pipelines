from enum import StrEnum
from typing import Any

from data_processing.transform import AbstractTableTransform

from docpipe.core.constants.constants import (
    DocpipeConstants,
    DocsStructure,
    ExecutionStatus,
    Metrics,
)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class OperatorCategory(StrEnum):
    Extract = "Extract"
    Ingest = "Ingest"
    Functional = "Functional"
    Quality = "Quality"
    VectorDB = "VectorDB"
    Storage = "Storage"


class AbstractOperator(AbstractTableTransform):
    short_name: str
    category: OperatorCategory
    owner: str | None = None  # None indicates custom operator, specific value (e.g., "docpipe") for built-in operators

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = config.get(OperatorConstants.Misc.NAME)
        self.id = config.get(OperatorConstants.Misc.ID)
        self.job_id = config.get(DocpipeConstants.JOB_ID)
        self.job_run_id = config.get(DocpipeConstants.JOB_RUN_ID)
        self.context_id = config.get(DocpipeConstants.CONTEXT_ID, self.job_id)
        self.output_features_to_drop = config.get(DocpipeConstants.OUTPUT_FEATURES_TO_DROP, [])
        self.updated_features = config.get(DocpipeConstants.UPDATED_FEATURES, [])
        self.validating_flow = config.get(DocpipeConstants.VALIDATING_FLOW, False)
        self.common_log_arguments = {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
        }

    @staticmethod
    def is_available():
        return True

    def validate(self, errors: list, warnings: list, available_features: list):
        # The concrete subclasses validates the parameters passed to the operators from the flow definition
        OperatorUtils.validate_columns(available_features, self.get_required_features(), self.short_name, errors)

    @staticmethod
    def get_required_features() -> list[str]:
        # The concrete subclasses will retrieve the required features.
        return []

    @staticmethod
    def get_metadata():
        # Returns operator metadata including owner
        return {}

    def should_validate_field(self, *, field_value: Any) -> bool:
        # Always validate during execution phase
        if not self.validating_flow:
            return True
        else:
            return False

    @staticmethod
    def create_base_metadata(
        *, total_docs_count: int, node_status: str = ExecutionStatus.COMPLETED.value
    ) -> dict[str, Any]:
        # Create base metadata structure with all required fields initialized.
        return {
            Metrics.External.TOTAL_DOCS: total_docs_count,
            Metrics.External.PROCESSED_DOCS: 0,
            Metrics.External.FAILED_DOCS_COUNT: 0,
            Metrics.External.FAILED_DOCS: [],
            Metrics.External.SKIPPED_DOCS_COUNT: 0,
            Metrics.External.SKIPPED_DOCS: [],
            Metrics.External.NODE_STATUS: node_status.value
            if isinstance(node_status, ExecutionStatus)
            else node_status,
        }

    @staticmethod
    def record_failed_document(
        *,
        metadata: dict[str, Any],
        doc_id: str,
        doc_name: str,
        reason: str,
    ) -> None:
        # Record a failed document in metadata.
        metadata[Metrics.External.FAILED_DOCS_COUNT] += 1
        metadata[Metrics.External.FAILED_DOCS].append(
            DocsStructure(id=doc_id, name=doc_name, reason=reason, document_url="")
        )

    @staticmethod
    def record_skipped_document(
        *,
        metadata: dict[str, Any],
        doc_id: str,
        doc_name: str,
        reason: str,
    ) -> None:
        # Record a skipped document in metadata.
        metadata[Metrics.External.SKIPPED_DOCS_COUNT] += 1
        metadata[Metrics.External.SKIPPED_DOCS].append(
            DocsStructure(id=doc_id, name=doc_name, reason=reason, document_url="")
        )
