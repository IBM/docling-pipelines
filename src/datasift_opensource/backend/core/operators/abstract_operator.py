from enum import Enum
from typing import Any

from data_processing.transform import AbstractTableTransform

from common.constants.operator_constants import OperatorConstants
from common.constants.constants import (
    DatasiftConstants,
    DocsStructure,
    ExecutionStatus,
    Metrics,
)
from common.util.log import get_logger
from core.operators.operator_utils import OperatorUtils

logger = get_logger()


class OperatorCategory(str, Enum):
    Extract = "Extract"
    Ingest = "Ingest"
    Functional = "Functional"
    Quality = "Quality"
    VectorDB = "VectorDB"
    Custom = "Custom"


class AbstractOperator(AbstractTableTransform):
    short_name = None
    category = None

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = config.get(OperatorConstants.Misc.NAME)
        self.id = config.get(OperatorConstants.Misc.ID)
        self.job_id = config.get(DatasiftConstants.JOB_ID)
        self.job_run_id = config.get(DatasiftConstants.JOB_RUN_ID)
        self.context_id = config.get(DatasiftConstants.CONTEXT_ID, self.job_id)
        self.output_features_to_drop = config.get(DatasiftConstants.OUTPUT_FEATURES_TO_DROP, [])
        self.updated_features = config.get(DatasiftConstants.UPDATED_FEATURES, [])
        self.validating_flow = config.get(DatasiftConstants.VALIDATING_FLOW, False)
        self.common_log_arguments = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }

    @staticmethod
    def is_available():
        return True

    def validate(self, errors: list, warnings: list, available_features: list):
        # The concrete subclasses validates the parameters passed to the operators from the flow definition
        OperatorUtils.validate_columns(available_features, self.get_required_features(), self.short_name, errors)

    def get_required_features(self):
        # The concrete subclasses will retrieve the required features.
        return []

    def get_metadata(self):
        # Returns operator metadata
        return {}

    def should_validate_field(self, *, field_value: Any) -> bool:
        # # Determine if a field should be validated.
        # from datasift_common.util.parameter_utils import is_parameterized_field

        # Always validate during execution phase
        if not self.validating_flow:
            return True
        else:
            return False

        # # During validation phase, only validate if field is NOT parameterized
        # return not is_parameterized_field(field=field_value)

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
    def record_failed_document(*, metadata: dict[str, Any], doc_id: str, doc_name: str, reason: str) -> None:
        # Record a failed document in metadata.
        metadata[Metrics.External.FAILED_DOCS_COUNT] += 1
        metadata[Metrics.External.FAILED_DOCS].append(
            DocsStructure(id=doc_id, name=doc_name, reason=reason, document_url="")
        )

    @staticmethod
    def record_skipped_document(*, metadata: dict[str, Any], doc_id: str, doc_name: str, reason: str) -> None:
        # Record a skipped document in metadata.
        metadata[Metrics.External.SKIPPED_DOCS_COUNT] += 1
        metadata[Metrics.External.SKIPPED_DOCS].append(
            DocsStructure(id=doc_id, name=doc_name, reason=reason, document_url="")
        )
