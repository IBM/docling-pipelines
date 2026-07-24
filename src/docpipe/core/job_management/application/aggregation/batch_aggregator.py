"""
Batch aggregation logic for node statistics.
This is the single source of truth for batch aggregation.
"""

from dataclasses import dataclass
from typing import Any

from docpipe.core.constants.constants import ExecutionStatus, Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.job_management.domain.models import NodeStats

from .aggregator import MetadataAggregator


@dataclass
class DocumentStats:
    """Document-level statistics."""

    total_expected: int
    completed: int
    processed: int


@dataclass
class BatchProgress:
    """Batch progress information."""

    finished: int
    total: int
    has_pending: bool
    status_counts: dict[str, int]


@dataclass
class ExtractionInfo:
    """Extraction operator information."""

    total: int
    completed: int
    is_extraction_operator: bool
    weighted_progress: float = 0.0
    stage_progress: dict[str, Any] | None = None


@dataclass
class ClassificationInfo:
    """Classification operator information."""

    total: int
    completed: int
    is_classification_operator: bool


def _get_empty_node_stats(*, node_id: str) -> NodeStats:
    """Returns empty aggregated stats for a node with no batches."""
    return NodeStats(
        node_id=node_id,
        name="Unknown",
        start_time=0,
        end_time=0,
        node_status=ExecutionStatus.PENDING.value,
        time_taken=0,
        col_names=[],
        total_docs=[],
        failed_docs=[],
        skipped_docs=[],
        docs_completed=[],
        docs_completed_count=0,
        node_metadata={},
        error="",
    )


def count_batches_by_status(*, batch_records: list[NodeStats]) -> dict[str, int]:
    """Counts batches by their status."""
    status_counts = {
        ExecutionStatus.RUNNING.value: 0,
        ExecutionStatus.QUEUED.value: 0,
        ExecutionStatus.CANCELING.value: 0,
        ExecutionStatus.CANCELED.value: 0,
        ExecutionStatus.FAILED.value: 0,
        ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
        ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        ExecutionStatus.COMPLETED.value: 0,
        ExecutionStatus.SKIPPED.value: 0,
        ExecutionStatus.PENDING.value: 0,
    }

    for record in batch_records:
        node_status = record.node_status
        if node_status in status_counts:
            status_counts[node_status] += 1

    return status_counts


def _determine_aggregated_status(*, status_counts: dict[str, int], total_batches: int) -> str:
    """Determines the aggregated node status based on batch status counts."""
    active_states = (
        status_counts[ExecutionStatus.RUNNING.value]
        + status_counts[ExecutionStatus.QUEUED.value]
        + status_counts[ExecutionStatus.PENDING.value]
        + status_counts[ExecutionStatus.CANCELING.value]
    )

    if active_states > 0:
        return ExecutionStatus.RUNNING.value

    if status_counts[ExecutionStatus.CANCELED.value] == total_batches:
        return ExecutionStatus.CANCELED.value

    if status_counts[ExecutionStatus.FAILED.value] == total_batches:
        return ExecutionStatus.FAILED.value

    if status_counts[ExecutionStatus.SKIPPED.value] == total_batches:
        return ExecutionStatus.SKIPPED.value

    has_failures = status_counts[ExecutionStatus.FAILED.value] > 0
    has_successes = (
        status_counts[ExecutionStatus.COMPLETED.value]
        + status_counts[ExecutionStatus.COMPLETED_WITH_WARNINGS.value]
        + status_counts[ExecutionStatus.SKIPPED.value]
    ) > 0

    if has_failures and has_successes:
        return ExecutionStatus.COMPLETED_WITH_ERRORS.value

    if status_counts[ExecutionStatus.COMPLETED_WITH_ERRORS.value] > 0:
        return ExecutionStatus.COMPLETED_WITH_ERRORS.value

    if status_counts[ExecutionStatus.COMPLETED_WITH_WARNINGS.value] > 0:
        return ExecutionStatus.COMPLETED_WITH_WARNINGS.value

    all_completed_or_skipped = (
        status_counts[ExecutionStatus.COMPLETED.value] + status_counts[ExecutionStatus.SKIPPED.value]
    ) == total_batches

    if all_completed_or_skipped:
        return ExecutionStatus.COMPLETED.value

    return ExecutionStatus.RUNNING.value


def _aggregate_time_fields(*, batch_records: list[NodeStats]) -> tuple:
    """Aggregates start time, end time, and time taken from batch records."""
    start_times = [r.start_time for r in batch_records if r.start_time > 0]
    end_times = [r.end_time for r in batch_records if r.end_time > 0]

    aggregated_start_time = min(start_times) if start_times else 0
    aggregated_end_time = max(end_times) if end_times else 0
    aggregated_time_taken = (
        aggregated_end_time - aggregated_start_time if aggregated_start_time > 0 and aggregated_end_time > 0 else 0
    )

    return aggregated_start_time, aggregated_end_time, aggregated_time_taken


def _aggregate_document_lists(*, batch_records: list[NodeStats]) -> tuple:
    """Aggregates document lists (UNION - deduplicate) from batch records."""
    all_col_names = set()
    all_total_docs = set()
    all_failed_docs = set()
    all_skipped_docs = set()
    all_docs_completed = set()

    for record in batch_records:
        if record.col_names:
            all_col_names.update(record.col_names)
        if record.total_docs:
            all_total_docs.update(record.total_docs)
        if record.failed_docs:
            all_failed_docs.update(record.failed_docs)
        if record.skipped_docs:
            all_skipped_docs.update(record.skipped_docs)
        if record.docs_completed:
            all_docs_completed.update(record.docs_completed)

    return all_col_names, all_total_docs, all_failed_docs, all_skipped_docs, all_docs_completed


def _aggregate_errors(*, batch_records: list[NodeStats]) -> str:
    """Concatenates error messages from batch records."""
    errors = [record.error for record in batch_records if record.error and record.error.strip()]
    return " | ".join(errors) if errors else ""


def _get_nested_metadata(*, record: NodeStats) -> dict[str, Any] | None:
    """Extracts nested node_metadata from a record."""
    if not record.node_metadata or not isinstance(record.node_metadata, dict):
        return None

    metadata = record.node_metadata
    if OperatorConstants.Metadata.NODE_METADATA in metadata and isinstance(
        metadata[OperatorConstants.Metadata.NODE_METADATA], dict
    ):
        metadata = metadata[OperatorConstants.Metadata.NODE_METADATA]

    return metadata


def _is_extraction_operator(*, batch_records: list[NodeStats]) -> bool:
    """Checks if this is an extraction operator by looking for extraction-specific fields."""
    for record in batch_records:
        metadata = _get_nested_metadata(record=record)
        if metadata and (
            "extraction_running" in metadata
            or "extraction_completed" in metadata
            or OperatorConstants.Metadata.EXTRACTION_STAGE_PROGRESS in metadata
        ):
            return True
    return False


def _is_classification_operator(*, batch_records: list[NodeStats]) -> bool:
    """Checks if this is a classification operator by looking for classification-specific fields."""
    for record in batch_records:
        metadata = _get_nested_metadata(record=record)
        if metadata and ("classification_running" in metadata or "classification_completed" in metadata):
            return True
    return False


def _extract_from_single_record(*, metadata: dict[str, Any]) -> tuple[int, int, float]:  # NOSONAR python:S3776
    """
    Extracts extraction progress from a single record's metadata and removes transient fields.

    Returns:
        tuple: (total_documents, completed_documents, weighted_progress)
    """
    total_running = 0
    total_completed = 0
    weighted_progress = 0.0
    has_transient = False

    # Priority 1: Stage-based progress (new format)
    if OperatorConstants.Metadata.EXTRACTION_STAGE_PROGRESS in metadata:
        stage_progress = metadata.get(OperatorConstants.Metadata.EXTRACTION_STAGE_PROGRESS, {})
        if isinstance(stage_progress, dict):
            # Use MAX of stage totals (not sum) since all stages process the same documents
            # Sum completed across stages for weighted progress calculation
            stage_totals = []
            for stage_data in stage_progress.values():
                if isinstance(stage_data, dict):
                    stage_totals.append(stage_data.get(OperatorConstants.Extraction.STAGE_DOCUMENTS_TOTAL, 0))
                    total_completed += stage_data.get(OperatorConstants.Extraction.STAGE_DOCUMENTS_COMPLETED, 0)

            # Use max of stage totals since stages process the same documents sequentially
            total_running = max(stage_totals) if stage_totals else 0
            weighted_progress = float(total_completed)
            has_transient = True

    # Priority 2: Legacy extraction fields (backward compatibility)
    elif "extraction_running" in metadata or "extraction_completed" in metadata:
        total_running = int(metadata.get("extraction_running", 0))
        total_completed = int(metadata.get("extraction_completed", 0))
        weighted_progress = float(total_completed)
        has_transient = True

    # Remove transient fields after reading
    if has_transient:
        # Remove stage-based transient field
        metadata.pop(OperatorConstants.Metadata.EXTRACTION_STAGE_PROGRESS, None)

        # Remove legacy transient fields
        metadata.pop("extraction_running", None)
        metadata.pop("extraction_completed", None)
        metadata.pop("progress_percentage", None)

    # Priority 3: Persistent metadata as fallback (for COMPLETED batches)
    if not has_transient:
        if Metrics.External.TOTAL_DOCS in metadata:
            total_running = int(metadata.get(Metrics.External.TOTAL_DOCS, 0))
        if Metrics.External.PROCESSED_DOCS in metadata:
            total_completed = int(metadata.get(Metrics.External.PROCESSED_DOCS, 0))
            weighted_progress = float(total_completed)

    return total_running, total_completed, weighted_progress


def _extract_classification_from_single_record(*, metadata: dict[str, Any]) -> tuple:
    """Extracts classification progress from a single record's metadata and removes transient fields."""
    total_running = 0
    total_completed = 0
    has_transient = False

    # Priority 1: Transient classification fields (present during RUNNING state)
    if "classification_running" in metadata:
        total_running = int(metadata.get("classification_running", 0))
        has_transient = True

    if "classification_completed" in metadata:
        total_completed = int(metadata.get("classification_completed", 0))
        has_transient = True

    # Remove transient fields after reading them
    # These fields should not appear in the final aggregated metadata
    if has_transient:
        metadata.pop("classification_running", None)
        metadata.pop("classification_completed", None)
        metadata.pop("progress_percentage", None)

    # Priority 2: Persistent metadata as fallback (for COMPLETED batches)
    if not has_transient:
        if Metrics.External.TOTAL_DOCS in metadata:
            total_running = int(metadata.get(Metrics.External.TOTAL_DOCS, 0))
        if Metrics.External.PROCESSED_DOCS in metadata:
            total_completed = int(metadata.get(Metrics.External.PROCESSED_DOCS, 0))

    return total_running, total_completed


def _get_extraction_progress(*, batch_records: list[NodeStats]) -> ExtractionInfo:
    """
    Extracts extraction progress from batch records if this is an extraction operator.

    ONLY extracts if extraction-specific fields are present (i.e., this is an extraction operator).
    Returns ExtractionInfo with stage_progress included.
    """
    # Check if this is an extraction operator FIRST
    if not _is_extraction_operator(batch_records=batch_records):
        return ExtractionInfo(
            total=0, completed=0, is_extraction_operator=False, weighted_progress=0.0, stage_progress=None
        )

    # Aggregate stage progress FIRST before transient fields are removed
    stage_progress = _aggregate_extraction_stage_progress(batch_records=batch_records)

    # Extract and sum values from all records (this removes transient fields)
    extraction_total = 0
    extraction_completed = 0
    weighted_progress_sum = 0.0

    for record in batch_records:
        metadata = _get_nested_metadata(record=record)
        if metadata:
            total, completed, weighted = _extract_from_single_record(metadata=metadata)
            extraction_total += total
            extraction_completed += completed
            weighted_progress_sum += weighted

    return ExtractionInfo(
        total=extraction_total,
        completed=extraction_completed,
        is_extraction_operator=True,
        weighted_progress=weighted_progress_sum,
        stage_progress=stage_progress if stage_progress else None,
    )


def _get_classification_progress(*, batch_records: list[NodeStats]) -> ClassificationInfo:
    """
    Extracts classification progress from batch records if this is a classification operator.

    ONLY extracts if classification-specific fields are present (i.e., this is a classification operator).
    Returns ClassificationInfo with zeros for non-classification operators.
    """
    # Check if this is a classification operator FIRST
    if not _is_classification_operator(batch_records=batch_records):
        return ClassificationInfo(total=0, completed=0, is_classification_operator=False)

    # Extract and sum values from all records
    classification_total = 0
    classification_completed = 0

    for record in batch_records:
        metadata = _get_nested_metadata(record=record)
        if metadata:
            running, completed = _extract_classification_from_single_record(metadata=metadata)
            classification_total += running
            classification_completed += completed

    return ClassificationInfo(
        total=classification_total, completed=classification_completed, is_classification_operator=True
    )


def _aggregate_extraction_stage_progress(*, batch_records: list[NodeStats]) -> dict[str, Any]:  # NOSONAR python:S3776
    """
    Aggregates per-stage extraction progress across all batches.

    Handles both:
    - Running batches: Have transient extraction_stage_progress metadata
    - Completed batches: Have persistent total_docs_count/processed_docs metadata

    Returns dict with structure:
    {
        "text_extraction": {
            "status": "running",
            "documents_total": 100,
            "documents_completed": 86,
            "documents_failed": 0,
            "progress_percentage": 86.0
        },
        "entity_extraction": { ... }
    }
    """
    stage_aggregates: dict[str, dict[str, Any]] = {}

    # PASS 1: Process RUNNING batches first to discover all active stages
    # This ensures we know which stages exist before processing completed batches
    for record in batch_records:
        metadata = _get_nested_metadata(record=record)
        if not metadata:
            continue

        stage_progress = metadata.get(OperatorConstants.Metadata.EXTRACTION_STAGE_PROGRESS, {})

        # Only process running batches with stage progress in Pass 1
        if isinstance(stage_progress, dict) and stage_progress:
            for stage_name, stage_data in stage_progress.items():
                if stage_name not in stage_aggregates:
                    stage_aggregates[stage_name] = {
                        OperatorConstants.Extraction.STAGE_DOCUMENTS_TOTAL: 0,
                        OperatorConstants.Extraction.STAGE_DOCUMENTS_COMPLETED: 0,
                        OperatorConstants.Extraction.STAGE_DOCUMENTS_FAILED: 0,
                        "statuses": [],
                    }

                stage_aggregates[stage_name][OperatorConstants.Extraction.STAGE_DOCUMENTS_TOTAL] += stage_data.get(
                    OperatorConstants.Extraction.STAGE_DOCUMENTS_TOTAL, 0
                )
                stage_aggregates[stage_name][OperatorConstants.Extraction.STAGE_DOCUMENTS_COMPLETED] += stage_data.get(
                    OperatorConstants.Extraction.STAGE_DOCUMENTS_COMPLETED, 0
                )
                stage_aggregates[stage_name][OperatorConstants.Extraction.STAGE_DOCUMENTS_FAILED] += stage_data.get(
                    OperatorConstants.Extraction.STAGE_DOCUMENTS_FAILED, 0
                )
                stage_aggregates[stage_name]["statuses"].append(
                    stage_data.get(
                        OperatorConstants.Extraction.STAGE_STATUS, OperatorConstants.Extraction.STAGE_STATUS_PENDING
                    )
                )

    # PASS 2: Process COMPLETED/FAILED batches now that all stages are discovered
    for record in batch_records:
        metadata = _get_nested_metadata(record=record)
        if not metadata:
            continue

        # Handle completed and failed batches (no stage progress, use persistent metadata)
        if record.node_status in (
            ExecutionStatus.COMPLETED.value,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value,
            ExecutionStatus.FAILED.value,
        ):
            # For completed/failed batches, use total_docs_count and processed_docs from nested metadata
            total_docs = metadata.get(Metrics.External.TOTAL_DOCS, 0)
            processed_docs = metadata.get(Metrics.External.PROCESSED_DOCS, 0)

            if total_docs > 0:
                # Determine which stages to update based on what's already in stage_aggregates
                # If entity_extraction exists (populated by running batches), entity extraction is enabled
                stages_to_update = ["text_extraction"]
                if "entity_extraction" in stage_aggregates:
                    stages_to_update.append("entity_extraction")

                # Add completed batch counts to all active stages
                for stage_name in stages_to_update:
                    if stage_name not in stage_aggregates:
                        stage_aggregates[stage_name] = {
                            OperatorConstants.Extraction.STAGE_DOCUMENTS_TOTAL: 0,
                            OperatorConstants.Extraction.STAGE_DOCUMENTS_COMPLETED: 0,
                            OperatorConstants.Extraction.STAGE_DOCUMENTS_FAILED: 0,
                            "statuses": [],
                        }

                    stage_aggregates[stage_name][OperatorConstants.Extraction.STAGE_DOCUMENTS_TOTAL] += total_docs
                    stage_aggregates[stage_name][OperatorConstants.Extraction.STAGE_DOCUMENTS_COMPLETED] += (
                        processed_docs
                    )

                    # Set status based on batch status
                    if record.node_status == ExecutionStatus.FAILED.value:
                        stage_aggregates[stage_name]["statuses"].append(
                            OperatorConstants.Extraction.STAGE_STATUS_FAILED
                        )
                    else:
                        stage_aggregates[stage_name]["statuses"].append(
                            OperatorConstants.Extraction.STAGE_STATUS_COMPLETED
                        )
    # PASS 1 FALLBACK: Handle running batches WITHOUT stage_progress but WITH total_docs
    for record in batch_records:
        metadata = _get_nested_metadata(record=record)
        if not metadata:
            continue

        # Skip if already processed (has stage_progress)
        stage_progress = metadata.get(OperatorConstants.Metadata.EXTRACTION_STAGE_PROGRESS, {})
        if isinstance(stage_progress, dict) and stage_progress:
            continue

        if record.node_status == ExecutionStatus.RUNNING.value:
            # Check for total_docs field (not total_docs_count which is for completed)
            total_docs = metadata.get("total_docs", 0)

            if total_docs > 0:
                # Only add to text_extraction stage for running batches without stage_progress
                # Entity extraction stage should only be added if it was actually performed
                stage_name = "text_extraction"
                if stage_name not in stage_aggregates:
                    stage_aggregates[stage_name] = {
                        OperatorConstants.Extraction.STAGE_DOCUMENTS_TOTAL: 0,
                        OperatorConstants.Extraction.STAGE_DOCUMENTS_COMPLETED: 0,
                        OperatorConstants.Extraction.STAGE_DOCUMENTS_FAILED: 0,
                        "statuses": [],
                    }

                stage_aggregates[stage_name][OperatorConstants.Extraction.STAGE_DOCUMENTS_TOTAL] += total_docs
                # Don't add to completed since we don't have progress info
                stage_aggregates[stage_name]["statuses"].append(OperatorConstants.Extraction.STAGE_STATUS_RUNNING)

    # Calculate final stage progress
    result: dict[str, Any] = {}
    for stage_name, agg in stage_aggregates.items():
        total = agg[OperatorConstants.Extraction.STAGE_DOCUMENTS_TOTAL]
        completed = agg[OperatorConstants.Extraction.STAGE_DOCUMENTS_COMPLETED]

        # Determine aggregated status (priority: running > failed > completed > pending)
        statuses = agg["statuses"]
        if OperatorConstants.Extraction.STAGE_STATUS_RUNNING in statuses:
            status = OperatorConstants.Extraction.STAGE_STATUS_RUNNING
        elif OperatorConstants.Extraction.STAGE_STATUS_FAILED in statuses:
            status = OperatorConstants.Extraction.STAGE_STATUS_FAILED
        elif all(s == OperatorConstants.Extraction.STAGE_STATUS_COMPLETED for s in statuses):
            status = OperatorConstants.Extraction.STAGE_STATUS_COMPLETED
        else:
            status = OperatorConstants.Extraction.STAGE_STATUS_PENDING

        result[stage_name] = {
            OperatorConstants.Extraction.STAGE_STATUS: status,
            OperatorConstants.Extraction.STAGE_DOCUMENTS_TOTAL: total,
            OperatorConstants.Extraction.STAGE_DOCUMENTS_COMPLETED: completed,
            OperatorConstants.Extraction.STAGE_DOCUMENTS_FAILED: agg[
                OperatorConstants.Extraction.STAGE_DOCUMENTS_FAILED
            ],
            OperatorConstants.Extraction.STAGE_PROGRESS_PERCENTAGE: round((completed / total * 100), 2)
            if total > 0
            else 0.0,
        }

    return result


def calculate_finished_batches(*, status_counts: dict[str, int]) -> int:
    """
    Calculates the number of finished batches.

    Finished = completed + failed + skipped + completed_with_warnings + completed_with_errors
    Excludes: running, pending, queued
    """
    return (
        status_counts[ExecutionStatus.COMPLETED.value]
        + status_counts[ExecutionStatus.SKIPPED.value]
        + status_counts[ExecutionStatus.COMPLETED_WITH_WARNINGS.value]
        + status_counts[ExecutionStatus.COMPLETED_WITH_ERRORS.value]
        + status_counts[ExecutionStatus.FAILED.value]
    )


def _add_progress_field(
    *, metadata: dict[str, Any], finished_batches: int, total_batches: int, status_counts: dict[str, int]
) -> None:
    """
    Adds batch-based Progress field to metadata with status breakdown.

    Format: "X of Y batches (Z%) | Completed: A, Running: B, Failed: C, Skipped: D"
    Only shows non-zero statuses (except Completed which is always shown).

    Note: COMPLETED_WITH_ERRORS and COMPLETED_WITH_WARNINGS are counted as "Completed".
    """
    if total_batches > 0:
        pct = round((finished_batches / total_batches) * 100, 2)
        base_progress = f"{finished_batches} of {total_batches} batches ({pct}%)"

        # Build status breakdown - only show non-zero counts
        status_parts = []

        # Completed count includes COMPLETED, COMPLETED_WITH_ERRORS, and COMPLETED_WITH_WARNINGS
        completed = (
            status_counts.get(ExecutionStatus.COMPLETED.value, 0)
            + status_counts.get(ExecutionStatus.COMPLETED_WITH_ERRORS.value, 0)
            + status_counts.get(ExecutionStatus.COMPLETED_WITH_WARNINGS.value, 0)
        )
        status_parts.append(f"Completed: {completed}")

        # Show Running if non-zero
        running = status_counts.get(ExecutionStatus.RUNNING.value, 0)
        if running > 0:
            status_parts.append(f"Running: {running}")

        # Show Failed if non-zero (only FAILED status, not CompletedWithErrors)
        failed = status_counts.get(ExecutionStatus.FAILED.value, 0)
        if failed > 0:
            status_parts.append(f"Failed: {failed}")

        # Show Skipped if non-zero
        skipped = status_counts.get(ExecutionStatus.SKIPPED.value, 0)
        if skipped > 0:
            status_parts.append(f"Skipped: {skipped}")

        # Combine base progress with status breakdown
        if status_parts:
            metadata[OperatorConstants.Metadata.FIELD_PROGRESS] = f"{base_progress} | {', '.join(status_parts)}"
        else:
            metadata[OperatorConstants.Metadata.FIELD_PROGRESS] = base_progress


def _add_extraction_stage_fields(
    *, metadata: dict[str, Any], extraction_info: ExtractionInfo, has_pending_batches: bool
) -> None:
    """Adds per-stage extraction fields for extraction operators."""
    if not extraction_info.stage_progress:
        return

    for stage_name, stage_data in extraction_info.stage_progress.items():
        total = stage_data.get("documents_total", 0)
        completed = stage_data.get("documents_completed", 0)

        if total > 0:
            # Determine field name based on stage
            if stage_name == "text_extraction":
                field_name = OperatorConstants.Metadata.FIELD_TEXT_EXTRACTED
            elif stage_name == "entity_extraction":
                field_name = OperatorConstants.Metadata.FIELD_ENTITIES_EXTRACTED
            else:
                # For any other stages, use a generic format
                field_name = stage_name.replace("_", " ").title()

            if has_pending_batches:
                # Batches still pending - show "(more in queue)" message
                metadata[field_name] = f"{completed} of {total} (more in queue)"
            else:
                # All batches started - show percentage
                pct = round((completed / total * 100), 2)
                metadata[field_name] = f"{completed} of {total} ({pct}%)"


def _add_classification_field(
    *, metadata: dict[str, Any], classification_info: ClassificationInfo, has_pending_batches: bool
) -> None:
    """Adds Documents Classified field for classification operators."""
    if classification_info.total > 0:
        if has_pending_batches:
            # Batches still pending - show "(more in queue)" message
            metadata[OperatorConstants.Metadata.FIELD_DOCS_CLASSIFIED] = (
                f"{classification_info.completed} of {classification_info.total} (more in queue)"
            )
        else:
            # All batches started - show percentage
            classification_pct = round((classification_info.completed / classification_info.total * 100), 2)
            metadata[OperatorConstants.Metadata.FIELD_DOCS_CLASSIFIED] = (
                f"{classification_info.completed} of {classification_info.total} ({classification_pct}%)"
            )


def _inject_metadata_fields(
    *,
    aggregated_metadata: dict[str, Any],
    aggregated_status: str,
    doc_stats: DocumentStats,
    batch_progress: BatchProgress,
    extraction_info: ExtractionInfo,
    classification_info: ClassificationInfo,
) -> None:
    """
    Injects progress and metadata fields into aggregated metadata.

    Uses data classes to group related parameters and reduce parameter count.
    """
    if OperatorConstants.Metadata.NODE_METADATA not in aggregated_metadata:
        aggregated_metadata[OperatorConstants.Metadata.NODE_METADATA] = {}

    if isinstance(aggregated_metadata[OperatorConstants.Metadata.NODE_METADATA], dict):
        metadata = aggregated_metadata[OperatorConstants.Metadata.NODE_METADATA]

        # Core document fields
        metadata[Metrics.External.TOTAL_DOCS] = doc_stats.total_expected
        metadata[Metrics.External.COMPLETED_DOCS_COUNT] = doc_stats.completed
        metadata[Metrics.External.PROCESSED_DOCS] = doc_stats.processed
        metadata[Metrics.External.NODE_STATUS] = aggregated_status

        # Add batch-based Progress field
        _add_progress_field(
            metadata=metadata,
            finished_batches=batch_progress.finished,
            total_batches=batch_progress.total,
            status_counts=batch_progress.status_counts,
        )

        # Add per-stage extraction fields for extraction operators
        if extraction_info.is_extraction_operator:
            _add_extraction_stage_fields(
                metadata=metadata, extraction_info=extraction_info, has_pending_batches=batch_progress.has_pending
            )

        # Add Documents Classified field for classification operators
        if classification_info.is_classification_operator:
            _add_classification_field(
                metadata=metadata,
                classification_info=classification_info,
                has_pending_batches=batch_progress.has_pending,
            )


def aggregate_batch_node_stats(
    *,
    node_id: str,
    batch_records: list[NodeStats],
    aggregator: MetadataAggregator,
) -> NodeStats:
    """
    Aggregates batch-level node statistics using ONLY node_stats table.

    Uses node_status field from node_stats to determine batch status and calculate progress.
    Pending/Queued batches are identified by node_status in node_stats records.
    Failed batches are considered as completed for progress calculation.

    Args:
        node_id: The node identifier
        batch_records: List of NodeStats records for this node from database
        aggregator: MetadataAggregator instance for intelligent field aggregation

    Returns:
        Dictionary with aggregated node statistics
    """
    total_batches = len(batch_records)

    if total_batches == 0:
        return _get_empty_node_stats(node_id=node_id)

    # Extract extraction and classification progress FIRST (for extraction/classification operators)
    # This must be done BEFORE metadata aggregation to remove transient fields
    extraction_info = _get_extraction_progress(batch_records=batch_records)
    classification_info = _get_classification_progress(batch_records=batch_records)

    # Aggregate status
    status_counts = count_batches_by_status(batch_records=batch_records)
    aggregated_status = _determine_aggregated_status(status_counts=status_counts, total_batches=total_batches)

    # Aggregate time fields
    aggregated_start_time, aggregated_end_time, aggregated_time_taken = _aggregate_time_fields(
        batch_records=batch_records
    )

    # Aggregate document lists
    all_col_names, all_total_docs, all_failed_docs, all_skipped_docs, all_docs_completed = _aggregate_document_lists(
        batch_records=batch_records
    )

    # Aggregate errors
    aggregated_error = _aggregate_errors(batch_records=batch_records)

    # Aggregate metadata using enterprise-compatible aggregator
    metadata_list = [record.node_metadata for record in batch_records if record.node_metadata]
    aggregated_metadata = aggregator.aggregate_metadata(metadata_list=metadata_list) if metadata_list else {}

    # Calculate statistics
    # Processed docs: sum of completed, failed, and skipped documents for the processed batches
    processed_docs = len(all_docs_completed) + len(all_failed_docs) + len(all_skipped_docs)
    # Completed docs: only successfully completed documents
    completed_docs_count = len(all_docs_completed)
    total_expected_docs = len(all_total_docs)

    # Check if there are pending batches
    has_pending_batches = (
        status_counts.get(ExecutionStatus.PENDING.value, 0) + status_counts.get(ExecutionStatus.QUEUED.value, 0)
    ) > 0

    # Calculate finished batches for progress
    finished_batches = calculate_finished_batches(status_counts=status_counts)

    # Create data class instances for cleaner parameter passing
    doc_stats = DocumentStats(
        total_expected=total_expected_docs, completed=completed_docs_count, processed=processed_docs
    )

    batch_progress = BatchProgress(
        finished=finished_batches, total=total_batches, has_pending=has_pending_batches, status_counts=status_counts
    )

    # Inject metadata fields using structured data
    _inject_metadata_fields(
        aggregated_metadata=aggregated_metadata,
        aggregated_status=aggregated_status,
        doc_stats=doc_stats,
        batch_progress=batch_progress,
        extraction_info=extraction_info,
        classification_info=classification_info,
    )

    node_name = batch_records[0].name if batch_records else "Unknown"

    return NodeStats(
        node_id=node_id,
        name=node_name,
        start_time=aggregated_start_time,
        end_time=aggregated_end_time,
        node_status=aggregated_status,
        time_taken=aggregated_time_taken,
        col_names=sorted(all_col_names),
        total_docs=sorted(all_total_docs),
        failed_docs=sorted(all_failed_docs),
        skipped_docs=sorted(all_skipped_docs),
        docs_completed=sorted(all_docs_completed),
        docs_completed_count=len(all_docs_completed),
        node_metadata=aggregated_metadata,
        error=aggregated_error,
    )
