"""
Aggregation strategies for metadata fields.

Defines how different metadata fields should be aggregated across batches
in micro-batching scenarios. Each NodeMetadataItem exists per batch, and
these strategies determine how to combine them into a single aggregated view.
"""

from enum import StrEnum

from datasift.core.constants.constants import DatasiftConstants, Metrics
from datasift.core.constants.operator_constants import OperatorConstants


class AggregationStrategy(StrEnum):
    """
    Enumeration of aggregation strategies for metadata fields.

    Each strategy defines how values from multiple batch records are combined:
    - SUM: Add numeric values (e.g., processed_docs: 10 + 20 = 30)
    - UNION: Combine lists removing duplicates (e.g., failed_docs: [a,b] + [b,c] = [a,b,c])
    - PRIORITY_STATUS: Select most severe status (RUNNING > FAILED > COMPLETED)
    - MIN/MAX: Select minimum/maximum value (e.g., start_time uses MIN)
    - WEIGHTED_AVERAGE: Average with consideration of batch sizes
    - LAST_COMPLETED: Use last non-empty value (e.g., error messages)
    """

    SUM = "sum"
    AVERAGE = "average"
    WEIGHTED_AVERAGE = "weighted_average"
    MIN = "min"
    MAX = "max"

    UNION = "union"
    CONCAT = "concat"
    INTERSECTION = "intersection"

    MERGE_DICT = "merge_dict"
    DEEP_MERGE = "deep_merge"

    FIRST = "first"
    LAST = "last"
    LAST_COMPLETED = "last_completed"

    PRIORITY_STATUS = "priority_status"

    CUSTOM = "custom"


# Default aggregation strategies for standard metadata fields
# These apply to the nested node_metadata field within NodeStats
#
# OPERATOR-SPECIFIC FIELDS:
# When operators add custom metadata fields, they inherit LAST strategy by default.
# Add explicit strategies here only if different aggregation is needed.
DEFAULT_STRATEGIES = {
    # Base metadata fields (present in all operators via AbstractOperator)
    DatasiftConstants.PROCESSED_DOCS: AggregationStrategy.SUM,
    DatasiftConstants.TOTAL_DOCS: AggregationStrategy.SUM,
    Metrics.External.FAILED_DOCS_COUNT: AggregationStrategy.SUM,
    Metrics.External.SKIPPED_DOCS_COUNT: AggregationStrategy.SUM,
    DatasiftConstants.COMPLETED_DOCS: AggregationStrategy.UNION,
    DatasiftConstants.FAILED_DOCS: AggregationStrategy.UNION,
    DatasiftConstants.SKIPPED_DOCS: AggregationStrategy.UNION,
    DatasiftConstants.STATUS: AggregationStrategy.PRIORITY_STATUS,
    Metrics.External.NODE_STATUS: AggregationStrategy.PRIORITY_STATUS,
    # Timing fields
    DatasiftConstants.START_TIME: AggregationStrategy.MIN,
    DatasiftConstants.END_TIME: AggregationStrategy.MAX,
    "time_taken": AggregationStrategy.SUM,
    "progress_percentage": AggregationStrategy.WEIGHTED_AVERAGE,
    # Error handling
    Metrics.External.ERROR: AggregationStrategy.LAST_COMPLETED,
    "error_message": AggregationStrategy.LAST_COMPLETED,
    Metrics.External.PROCESSING_MESSAGE: AggregationStrategy.LAST_COMPLETED,
    # Operator-specific fields with explicit strategies
    # (Most operator fields use LAST by default and don't need explicit entries)
    # Chunker operator
    Metrics.External.TOTAL_CHUNKS: AggregationStrategy.SUM,
    # SQL Filter operator
    Metrics.External.TOTAL_DOCS: AggregationStrategy.SUM,
    "total_bytes_count": AggregationStrategy.SUM,
    "docs_after_filter": AggregationStrategy.SUM,
    "bytes_after_filter": AggregationStrategy.SUM,
    # Dedup operator
    Metrics.External.REMOVED_DOCUMENTS: AggregationStrategy.SUM,
    # VectorDB operator
    "number_of_batches": AggregationStrategy.SUM,
    # ML Enrichment operator
    "features_added": AggregationStrategy.SUM,
    Metrics.External.PROCESSED_ROWS: AggregationStrategy.SUM,
    # Doc ID Hash operator
    "hashed_rows": AggregationStrategy.SUM,
    # Redaction operator
    "total_redactions": AggregationStrategy.SUM,
    # Extract operator - page statistics
    OperatorConstants.Metadata.TOTAL_PAGES_PROCESSED: AggregationStrategy.SUM,
    OperatorConstants.Metadata.PAGE_TYPE_STATS: AggregationStrategy.DEEP_MERGE,
    # Extract operator - nested stage progress tracking
    OperatorConstants.Metadata.EXTRACTION_STAGE_PROGRESS: AggregationStrategy.DEEP_MERGE,
}
