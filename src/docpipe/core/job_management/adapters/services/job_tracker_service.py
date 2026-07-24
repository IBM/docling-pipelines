"""
JobTrackerService - Production job stats service using new architecture

This service implements the JobStatsService port using only the new
hexagonal architecture components (store + aggregator). Legacy JobTracker
is no longer used in the runtime path.

Architecture:
- Uses JobStatsStore for persistence
- Uses NodeStatsAggregator for aggregation logic
- No dependency on legacy JobTracker singleton
"""

import json
from datetime import UTC, datetime
from logging import Logger
from typing import Any

from docpipe.core.constants.constants import TERMINAL_JOB_STATUSES, TERMINAL_NODE_STATES, ExecutionStatus, Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.job_management.application.services import NodeStatsAggregator
from docpipe.core.job_management.domain.models import JobStats, NodeMetadataItem, NodeStats
from docpipe.core.job_management.domain.ports import JobStatsService, JobStatsStore
from docpipe.exceptions.docpipe_exceptions import JobRunInvalidStateException
from docpipe.utils.infrastructure.logging import get_logger

logger: Logger = get_logger()


class JobTrackerService(JobStatsService):
    """
    Production job stats service using new hexagonal architecture.

    This service implements the JobStatsService port using only new
    architecture components. Legacy JobTracker is not used.

    Architecture:
    - JobStatsStore for persistence
    - NodeStatsAggregator for aggregation
    - Direct implementation of all job tracking operations
    """

    def __init__(self, *, job_stats_store: JobStatsStore, node_stats_aggregator: NodeStatsAggregator):
        """
        Initialize JobTrackerService.

        Args:
            job_stats_store: Storage adapter for job statistics
            node_stats_aggregator: Service for node stats aggregation
        """
        self.job_stats_store = job_stats_store
        self.node_stats_aggregator = node_stats_aggregator

    def start_tracking_job(
        self,
        *,
        job_id: str,
        job_run_id: str,
        flow_name: str,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Start tracking a new job run with initial statistics.

        Args:
            job_id: Unique job identifier
            job_run_id: Unique job run identifier
            flow_name: Name of the flow being executed (stored in flow_id field)
            user_id: Optional user identifier
            metadata: Optional metadata dictionary (not used - JobStats has no metadata field)

        Raises:
            ValueError: If job_run_id already exists
        """
        job_stats: JobStats = JobStats(
            job_id=job_id,
            job_run_id=job_run_id,
            flow_id=flow_name,  # Store flow_name in flow_id field
            user_id=user_id,
            status=ExecutionStatus.RUNNING,
            start_time=round(datetime.now().timestamp()),
            node_stats={},
            batch_node_stats={},
        )

        self.job_stats_store.store_job_stats(job_stats)
        logger.info(f"Started tracking job: job_id={job_id}, job_run_id={job_run_id}")

    def get_job_run_stats(self, *, job_run_id: str) -> JobStats | None:
        """
        Retrieve job-level statistics WITHOUT node_stats aggregation (lightweight).

        Args:
            job_run_id: Job run identifier

        Returns:
            JobStats with empty node_stats/batch_node_stats if found, None otherwise
        """
        # Delegate to store
        job_stats = self.job_stats_store.get_job_stats(job_run_id)

        return job_stats

    def get_job(
        self, *, job_run_id: str, include_node_stats: bool = True, include_batch_stats: bool = False
    ) -> JobStats | None:
        """
        Retrieve complete job statistics with optional aggregation.

        Args:
            job_run_id: Job run identifier
            include_node_stats: Whether to aggregate and include node statistics
            include_batch_stats: Whether to include batch-level node statistics

        Returns:
            JobStats with requested statistics if found, None otherwise
        """
        # Get job stats from store
        job_stats: JobStats | None = self.job_stats_store.get_job_stats(job_run_id)

        if not job_stats:
            return None

        # Add aggregated node stats if requested
        if include_node_stats:
            aggregated_node_stats: dict[str, NodeStats] = self.node_stats_aggregator.get_aggregated_node_stats(
                job_id=job_stats.job_id, job_run_id=job_run_id
            )
            job_stats.node_stats = aggregated_node_stats
        else:
            job_stats.node_stats = {}

        # Add batch stats if requested
        if include_batch_stats:
            batch_node_stats: dict[str, dict[str, NodeStats]] = self.node_stats_aggregator.get_batch_node_stats(
                job_id=job_stats.job_id, job_run_id=job_run_id
            )
            job_stats.batch_node_stats = batch_node_stats
        else:
            job_stats.batch_node_stats = {}

        return job_stats

    @staticmethod
    def normalize_execution_status(status: str | ExecutionStatus) -> ExecutionStatus:
        """
        Normalize external or legacy status inputs to the canonical ExecutionStatus enum.

        Accepts enum values, enum names, and case-insensitive string variants such as:
        Completed/COMPLETED, Failed/FAILED, Canceled/CANCELED.
        """
        if isinstance(status, ExecutionStatus):
            return status

        normalized_status = status.strip()
        if not normalized_status:
            raise ValueError("Invalid status: empty value")

        try:
            return ExecutionStatus(normalized_status)
        except ValueError:
            pass

        normalized_key = normalized_status.replace("-", "_").replace(" ", "_").upper()

        try:
            return ExecutionStatus[normalized_key]
        except KeyError as exc:
            raise ValueError(f"Invalid status: {status}") from exc

    def end_job(self, *, job_run_id: str, status: str, job_run_stats: dict[str, Any] | None = None) -> None:
        """
        End job tracking and update final status.

        Args:
            job_run_id: Job run identifier
            status: Final status (COMPLETED, FAILED, CANCELED)
            job_run_stats: Optional final statistics (message stored in job_stats.message field)

        Raises:
            ValueError: If job_run_id not found or status invalid
        """
        job_stats: JobStats | None = self.job_stats_store.get_job_stats(job_run_id)
        if not job_stats:
            from docpipe.exceptions.docpipe_exceptions import JobRunNotFoundException

            raise JobRunNotFoundException(message=f"Job run not found: {job_run_id}", job_run_id=job_run_id)

        normalized_status: ExecutionStatus = self.normalize_execution_status(status)

        # Update job stats
        job_stats.status = normalized_status
        job_stats.end_time = round(number=datetime.now().timestamp())
        job_stats.duration = job_stats.end_time - job_stats.start_time

        if job_run_stats and "message" in job_run_stats:
            job_stats.message = job_run_stats["message"]

        self.job_stats_store.store_job_stats(job_stats)
        logger.info(f"Ended job: job_run_id={job_run_id}, status={normalized_status.value}")

    def start_node_execution(
        self,
        *,
        job_run_id: str,
        node_id: str,
        node_name: str,
        total_docs: list[str],
        batch_id: str | None = None,
        batch_num: int | None = None,
    ) -> None:
        """
        Initialize node execution with starting statistics.

        Persists the initial node execution state so the completion path can
        later finalize it without executor-side read/merge/write logic.

        Args:
            job_run_id: Job run identifier
            node_id: Node identifier
            node_name: Human-readable node name
            total_docs: List of document IDs to be processed
            batch_id: Optional batch identifier for micro-batch execution
            batch_num: Optional batch number for micro-batch execution
        """

        # Build Running node stats with proper nested metadata structure
        metadata_item: NodeMetadataItem = NodeMetadataItem(
            id=node_id,
            operator=node_name,
            node_metadata={
                Metrics.External.TOTAL_DOCS: len(total_docs),
                Metrics.External.NODE_STATUS: ExecutionStatus.RUNNING.value,
            },
        )

        # Create initial node stats
        node_stats: NodeStats = NodeStats(
            node_id=node_id,
            name=node_name,
            start_time=round(datetime.now().timestamp()),
            total_docs=total_docs,
            node_status=ExecutionStatus.RUNNING.value,
            batch_id=batch_id,
            batch_num=batch_num,
            node_metadata=metadata_item.model_dump(),
        )

        # Persist through store interface
        self.job_stats_store.store_node_stats(job_run_id=job_run_id, node_stats=node_stats)
        logger.info(f"Started node execution: node_id={node_id}, job_run_id={job_run_id}")

    def complete_node_execution(
        self,
        *,
        job_run_id: str,
        node_id: str,
        node_name: str,
        docs_completed: list[str],
        failed_docs: list[str],
        skipped_docs: list[str],
        col_names: list[str],
        node_status: str,
        node_metadata: dict[str, Any] | None = None,
        batch_id: str | None = None,
        batch_num: int | None = None,
    ) -> None:
        """
        Finalize node execution with completion statistics.

        Looks up the previously stored node execution state for the same
        node/batch pair, merges raw completion facts, calculates derived
        timing/count fields, and persists the final node stats record.

        Args:
            job_run_id: Job run identifier
            node_id: Node identifier
            node_name: Human-readable node name
            docs_completed: List of successfully completed document IDs
            failed_docs: List of failed document IDs
            skipped_docs: List of skipped document IDs
            col_names: Column names from node output
            node_status: Final node status (COMPLETED, FAILED, etc.)
            node_metadata: Optional operator-specific metadata
            batch_id: Optional batch identifier for micro-batch execution
            batch_num: Optional batch number for micro-batch execution

        Raises:
            ValueError: If node not started
        """
        existing_node: NodeStats | None = self.job_stats_store.get_node_stats_by_batch_and_node(
            job_run_id=job_run_id, node_id=node_id, batch_id=batch_id
        )
        if existing_node is None:
            raise ValueError(f"Node execution was not started: node_id={node_id}")

        start_time: int = existing_node.start_time
        total_docs: list[str] = existing_node.total_docs or []
        # Preserve batch_num from existing node if not provided
        final_batch_num: int | None = batch_num if batch_num is not None else existing_node.batch_num

        # Calculate derived fields
        end_time: int = round(number=datetime.now().timestamp())
        time_taken: int = end_time - start_time

        # Ensure node_metadata has proper nested structure
        final_metadata: dict[str, Any] | None
        if node_metadata and not all(
            k in node_metadata for k in ["id", "operator", OperatorConstants.Metadata.NODE_METADATA]
        ):
            # Wrap raw metadata in proper structure
            metadata_item: NodeMetadataItem = NodeMetadataItem(
                id=node_id, operator=node_name, node_metadata=node_metadata
            )
            final_metadata = metadata_item.model_dump()
        else:
            # Already in proper format or None
            final_metadata = node_metadata

        # Build complete node stats
        completed_node_stats: NodeStats = NodeStats(
            node_id=node_id,
            name=node_name,
            start_time=start_time,
            end_time=end_time,
            time_taken=time_taken,
            node_status=node_status,
            col_names=col_names,
            total_docs=total_docs if total_docs else (docs_completed + failed_docs + skipped_docs),
            docs_completed=docs_completed,
            docs_completed_count=len(docs_completed),
            failed_docs=failed_docs,
            skipped_docs=skipped_docs,
            node_metadata=final_metadata,
            batch_id=batch_id,
            batch_num=final_batch_num,
        )

        # Add error field if there are failures or skips
        if failed_docs or skipped_docs:
            error_parts: list[Any] = []
            if failed_docs:
                error_parts.append(f"{len(failed_docs)} failed")
            if skipped_docs:
                error_parts.append(f"{len(skipped_docs)} skipped")
            completed_node_stats.error = f"Node completed with issues: {', '.join(error_parts)}"

        # Persist through store interface
        self.job_stats_store.store_node_stats(job_run_id=job_run_id, node_stats=completed_node_stats)
        logger.info(f"Completed node execution: node_id={node_id}, job_run_id={job_run_id}, status={node_status}")

    def fail_node_execution(
        self,
        *,
        job_run_id: str,
        node_id: str,
        node_name: str,
        exception: Exception | None = None,
        error: str | None = None,
        batch_id: str | None = None,
        batch_num: int | None = None,
    ) -> None:
        """
        Mark node execution as FAILED with error details.

        Args:
            job_run_id: Job run identifier
            node_id: Node identifier
            node_name: Human-readable node name
            exception: Optional exception that caused the failure
            error: Optional error message (ignored if exception provided)
            batch_id: Optional batch identifier for micro-batch execution
            batch_num: Optional batch number for micro-batch execution

        Raises:
            ValueError: If both exception and error are None
        """
        if exception is None and error is None:
            raise ValueError("Either exception or error must be provided")

        # Get existing start state
        existing_node: NodeStats | None = self.job_stats_store.get_node_stats_by_batch_and_node(
            job_run_id=job_run_id, node_id=node_id, batch_id=batch_id
        )

        # Extract meaningful error message (no stack trace)
        error_message: str
        if exception is not None:
            # Get just the error message, not the full traceback
            exception_str: str = str(exception)
            error_message = exception_str if exception_str else exception.__class__.__name__
        else:
            error_message = error  # type: ignore

        # Calculate timing
        end_time: int = round(datetime.now().timestamp())
        start_time: int = (
            existing_node.start_time if existing_node and getattr(existing_node, "start_time", 0) > 0 else end_time
        )
        time_taken: int = end_time - start_time

        # Preserve batch_num from existing if not provided
        final_batch_num: int | None = batch_num
        if final_batch_num is None and existing_node and existing_node.batch_num is not None:
            final_batch_num = existing_node.batch_num

        # Build failed node stats with proper nested metadata structure
        metadata_item: NodeMetadataItem = NodeMetadataItem(
            id=node_id,
            operator=node_name,
            node_metadata={
                Metrics.External.NODE_STATUS: ExecutionStatus.FAILED.value,
            },
        )

        failed_node_stats: NodeStats = NodeStats(
            node_id=node_id,
            name=node_name,
            start_time=start_time,
            end_time=end_time,
            time_taken=time_taken,
            node_status=ExecutionStatus.FAILED.value,
            error=error_message,
            col_names=[],
            total_docs=existing_node.total_docs if existing_node else [],
            docs_completed=[],
            docs_completed_count=0,
            failed_docs=[],
            skipped_docs=[],
            node_metadata=metadata_item.model_dump(),
            batch_id=batch_id,
            batch_num=final_batch_num,
        )

        self.job_stats_store.store_node_stats(job_run_id=job_run_id, node_stats=failed_node_stats)
        logger.info(f"Failed node execution: node_id={node_id}, job_run_id={job_run_id}")

    def cancel_node_execution(
        self,
        *,
        job_run_id: str,
        node_id: str,
        node_name: str,
        batch_id: str | None = None,
        batch_num: int | None = None,
    ) -> None:
        """
        Mark node execution as CANCELED.

        Args:
            job_run_id: Job run identifier
            node_id: Node identifier
            node_name: Human-readable node name
            batch_id: Optional batch identifier for micro-batch execution
            batch_num: Optional batch number for micro-batch execution
        """
        # Get existing start state
        existing_node: NodeStats | None = self.job_stats_store.get_node_stats_by_batch_and_node(
            job_run_id=job_run_id, node_id=node_id, batch_id=batch_id
        )

        # Calculate timing
        end_time: int = round(datetime.now().timestamp())
        start_time: int = (
            existing_node.start_time if existing_node and getattr(existing_node, "start_time", 0) > 0 else end_time
        )
        time_taken: int = end_time - start_time

        # Preserve batch_num from existing if not provided
        final_batch_num: int | None = batch_num
        if final_batch_num is None and existing_node and existing_node.batch_num is not None:
            final_batch_num = existing_node.batch_num

        # Build canceled node stats
        canceled_node_stats: NodeStats = NodeStats(
            node_id=node_id,
            name=node_name,
            start_time=start_time,
            end_time=end_time,
            time_taken=time_taken,
            node_status=ExecutionStatus.CANCELED.value,
            col_names=[],
            total_docs=existing_node.total_docs if existing_node else [],
            docs_completed=[],
            docs_completed_count=0,
            failed_docs=[],
            skipped_docs=[],
            node_metadata={},
            batch_id=batch_id,
            batch_num=final_batch_num,
        )

        self.job_stats_store.store_node_stats(job_run_id=job_run_id, node_stats=canceled_node_stats)
        logger.info(f"Canceled node execution: node_id={node_id}, job_run_id={job_run_id}")

    def abort_node_execution(
        self,
        *,
        job_run_id: str,
        node_id: str,
        node_name: str,
        reason: str,
        batch_id: str | None = None,
        batch_num: int | None = None,
    ) -> None:
        """
        Mark node execution as ABORTED.

        Args:
            job_run_id: Job run identifier
            node_id: Node identifier
            node_name: Human-readable node name
            reason: Reason for abort
            batch_id: Optional batch identifier for micro-batch execution
            batch_num: Optional batch number for micro-batch execution
        """
        # Get existing start state
        existing_node: NodeStats | None = self.job_stats_store.get_node_stats_by_batch_and_node(
            job_run_id=job_run_id, node_id=node_id, batch_id=batch_id
        )

        # Calculate timing
        end_time: int = round(datetime.now().timestamp())
        start_time: int = (
            existing_node.start_time if existing_node and getattr(existing_node, "start_time", 0) > 0 else end_time
        )
        time_taken: int = end_time - start_time

        # Preserve batch_num from existing if not provided
        final_batch_num: int | None = batch_num
        if final_batch_num is None and existing_node and existing_node.batch_num is not None:
            final_batch_num = existing_node.batch_num

        # Build aborted node stats with reason in metadata
        aborted_node_stats: NodeStats = NodeStats(
            node_id=node_id,
            name=node_name,
            start_time=start_time,
            end_time=end_time,
            time_taken=time_taken,
            node_status=ExecutionStatus.ABORTED.value,
            error=reason,
            col_names=[],
            total_docs=existing_node.total_docs if existing_node else [],
            docs_completed=[],
            docs_completed_count=0,
            failed_docs=[],
            skipped_docs=[],
            node_metadata={
                Metrics.External.TOTAL_DOCS: existing_node.total_docs if existing_node else 0,
                Metrics.External.NODE_STATUS: ExecutionStatus.ABORTED.value,
            },
            batch_id=batch_id,
            batch_num=final_batch_num,
        )

        self.job_stats_store.store_node_stats(job_run_id=job_run_id, node_stats=aborted_node_stats)
        logger.info(f"Aborted node execution: node_id={node_id}, job_run_id={job_run_id}, reason={reason}")

    def skip_node_execution(
        self,
        *,
        job_run_id: str,
        node_id: str,
        node_name: str,
        reason: str,
        col_names: list[str],
        batch_id: str | None = None,
        batch_num: int | None = None,
    ) -> None:
        """
        Mark node execution as SKIPPED.

        Args:
            job_run_id: Job run identifier
            node_id: Node identifier
            node_name: Human-readable node name
            reason: Reason why the node was skipped
            col_names: Column names from node output
            batch_id: Optional batch identifier for micro-batch execution
            batch_num: Optional batch number for micro-batch execution
        """
        # Get existing start state
        existing_node: NodeStats | None = self.job_stats_store.get_node_stats_by_batch_and_node(
            job_run_id=job_run_id, node_id=node_id, batch_id=batch_id
        )

        # Calculate timing
        end_time: int = round(datetime.now().timestamp())
        start_time: int = (
            existing_node.start_time if existing_node and getattr(existing_node, "start_time", 0) > 0 else end_time
        )
        time_taken: int = end_time - start_time

        # Preserve batch_num from existing if not provided
        final_batch_num: int | None = batch_num
        if final_batch_num is None and existing_node and existing_node.batch_num is not None:
            final_batch_num = existing_node.batch_num

        # Build skipped node stats with proper nested metadata structure
        metadata_item: NodeMetadataItem = NodeMetadataItem(
            id=node_id,
            operator=node_name,
            node_metadata={
                Metrics.External.TOTAL_DOCS: len(existing_node.total_docs)
                if existing_node and existing_node.total_docs
                else 0,
                Metrics.External.NODE_STATUS: ExecutionStatus.SKIPPED.value,
            },
        )

        skipped_node_stats: NodeStats = NodeStats(
            node_id=node_id,
            name=node_name,
            start_time=start_time,
            end_time=end_time,
            time_taken=time_taken,
            node_status=ExecutionStatus.SKIPPED.value,
            error=reason,
            col_names=col_names,
            total_docs=existing_node.total_docs if existing_node else [],
            docs_completed=[],
            docs_completed_count=0,
            failed_docs=[],
            skipped_docs=[],
            node_metadata=metadata_item.model_dump(),
            batch_id=batch_id,
            batch_num=final_batch_num,
        )

        self.job_stats_store.store_node_stats(job_run_id=job_run_id, node_stats=skipped_node_stats)
        logger.info(f"Skipped node execution: node_id={node_id}, job_run_id={job_run_id}, reason={reason}")

    def _merge_node_stats(
        self, *, existing_node: NodeStats | None, node_stats: dict, node_id: str, batch_id: str | None
    ) -> dict:
        """
        Helper method to merge existing and new node stats.

        Args:
            existing_node: Existing node stats from store (if any)
            node_stats: Incoming node stats to merge
            node_id: Node identifier
            batch_id: Optional batch identifier

        Returns:
            Merged stats dict ready for NodeStats construction
        """
        if isinstance(existing_node, NodeStats):
            base_stats = existing_node.model_dump()
        else:
            base_stats = existing_node or {}

        target_node_stats = base_stats | node_stats | {"node_id": node_id}
        if batch_id:
            target_node_stats["batch_id"] = batch_id
        return target_node_stats

    def update_node_stats(self, *, job_run_id: str, node_id: str, node_stats, batch_id: str | None = None) -> None:
        """
        Update node-level statistics through JobStatsStore interface.

        Fetches existing node stats, merges incoming values with existing state,
        and persists the merged result. This prevents partial updates from
        overwriting existing metadata, counters, or other fields.

        Args:
            job_run_id: Job run identifier
            node_id: Node identifier
            node_stats: Node statistics to update (NodeStats or dict)
            batch_id: Optional batch identifier for micro-batch execution
        """
        # Fetch existing node stats to merge with incoming values
        existing_node: NodeStats | None = self.job_stats_store.get_node_stats_by_batch_and_node(
            job_run_id=job_run_id, node_id=node_id, batch_id=batch_id
        )

        # Convert incoming stats to dict for merging
        if isinstance(node_stats, NodeStats):
            incoming_dict = node_stats.model_dump(exclude_unset=True)
        elif isinstance(node_stats, dict):
            incoming_dict = node_stats.copy()
        else:
            raise ValueError(f"Invalid node_stats type: {type(node_stats)}")

        # Merge existing and incoming stats
        merged_dict = self._merge_node_stats(
            existing_node=existing_node, node_stats=incoming_dict, node_id=node_id, batch_id=batch_id
        )

        # Create and persist merged NodeStats
        node_stats_dto = NodeStats(**merged_dict)
        self.job_stats_store.store_node_stats(job_run_id=job_run_id, node_stats=node_stats_dto)

    def get_node_stats(self, *, job_id: str, job_run_id: str) -> dict[str, Any]:
        """
        Retrieve aggregated node statistics.

        Args:
            job_id: Job identifier
            job_run_id: Job run identifier

        Returns:
            Dictionary mapping node_id to aggregated NodeStats
        """
        return self.node_stats_aggregator.get_aggregated_node_stats(job_id=job_id, job_run_id=job_run_id)

    def update_doc_counts(
        self, *, job_run_id: str, metadata: dict[str, Any], operator_category: str
    ) -> None:  # NOSONAR python:S3776
        """
        Update document counts based on operator execution metadata.

        Args:
            job_run_id: Job run identifier
            metadata: Operator execution metadata containing document counts
            operator_category: Category of operator (ingest, extract, etc.)

        Raises:
            ValueError: If job_run_id not found
        """
        job_stats = self.job_stats_store.get_job_stats(job_run_id)
        if not job_stats:
            from docpipe.exceptions.docpipe_exceptions import JobRunNotFoundException

            raise JobRunNotFoundException(message=f"Job run not found: {job_run_id}", job_run_id=job_run_id)

        # Update document counts from metadata
        from docpipe.core.operators.abstract_operator import OperatorCategory

        # Update deleted docs count (maps to deleted_doc_count field)
        if Metrics.External.DELETED_DOC_COUNT in metadata:
            job_stats.deleted_doc_count = metadata[Metrics.External.DELETED_DOC_COUNT]

        # Update total docs for ingest operators
        if operator_category == OperatorCategory.Ingest.value:
            if Metrics.External.TOTAL_DOCS in metadata:
                val = metadata[Metrics.External.TOTAL_DOCS]
                if isinstance(val, list):
                    job_stats.total_docs = len(val)
                elif isinstance(val, int):
                    job_stats.total_docs = val

        # Update page processing stats if present in metadata
        if OperatorConstants.Metadata.TOTAL_PAGES_PROCESSED in metadata:
            pages_count = metadata[OperatorConstants.Metadata.TOTAL_PAGES_PROCESSED]
            if isinstance(pages_count, int):
                job_stats.total_pages_processed += pages_count
                # Set execution_time to duration in seconds (current time - start time)
                current_timestamp = int(datetime.now(UTC).timestamp())
                job_stats.execution_time = current_timestamp - job_stats.start_time

        # Update page_type_stats if present in metadata
        if OperatorConstants.Metadata.PAGE_TYPE_STATS in metadata:
            new_page_type_stats = metadata[OperatorConstants.Metadata.PAGE_TYPE_STATS]
            if new_page_type_stats and isinstance(new_page_type_stats, dict):
                if job_stats.page_type_stats is None:
                    job_stats.page_type_stats = {}
                # Merge page type stats (sum counts for each page type)
                for page_type, count in new_page_type_stats.items():
                    if page_type in job_stats.page_type_stats:
                        job_stats.page_type_stats[page_type] += count
                    else:
                        job_stats.page_type_stats[page_type] = count

        self.job_stats_store.store_job_stats(job_stats)

    def bulk_store_node_stats(self, *, job_id: str, job_run_id: str, node_stats_list: list[Any]) -> None:
        """
        Bulk store multiple node statistics (micro-batching).

        Args:
            job_id: Job identifier (kept for interface compatibility)
            job_run_id: Job run identifier
            node_stats_list: List of node statistics to store

        Raises:
            IOError: If bulk operation fails
        """
        # Delegate to store (job_id not needed since job_run_id is globally unique)
        self.job_stats_store.bulk_store_node_stats(job_run_id=job_run_id, node_stats_list=node_stats_list)

    def store_job_stats(self, *, job_stats) -> None:
        """
        Store or update job-level statistics.

        Args:
            job_stats: Job statistics to store (JobStats)

        Raises:
            IOError: If storage operation fails
        """
        # Delegate to store
        self.job_stats_store.store_job_stats(job_stats)

    def request_cancel_job(self, *, job_run_id: str) -> None:
        """
        Initiate cancellation process for a running job.

        Args:
            job_run_id: Job run identifier

        Raises:
            JobRunNotFoundException: If job_run_id not found
            JobRunInvalidStateException: If job is already in terminal state
        """
        job_stats = self.job_stats_store.get_job_stats(job_run_id)
        if not job_stats:
            from docpipe.exceptions.docpipe_exceptions import JobRunNotFoundException

            raise JobRunNotFoundException(message=f"Job run not found: {job_run_id}", job_run_id=job_run_id)

        # Check if job is already in a terminal state
        if job_stats.status in TERMINAL_JOB_STATUSES:
            logger.error(f"Cannot cancel job {job_run_id}: already in terminal state {job_stats.status.value}")
            raise JobRunInvalidStateException(
                message=f"Cannot cancel job run in {job_stats.status.value} state",
                job_run_id=job_run_id,
                current_state=job_stats.status.value,
            )

        job_stats.status = ExecutionStatus.CANCELING
        self.job_stats_store.store_job_stats(job_stats)
        logger.info(f"Requested cancellation for job: {job_run_id}")

    def cancel_job_run_if_cancelling(self, *, job_run_id: str, job_log_path: str | None = None) -> bool:
        """
        Check if job is in CANCELING state and finalize as CANCELED.

        Args:
            job_run_id: Job run identifier
            job_log_path: Optional path to write job logs

        Returns:
            True if job was canceled, False otherwise
        """
        job_stats: JobStats | None = self.job_stats_store.get_job_stats(job_run_id)
        if not job_stats:
            return False

        if job_stats.status == ExecutionStatus.CANCELING:
            job_stats.status = ExecutionStatus.CANCELED
            job_stats.end_time = round(datetime.now().timestamp())
            self.job_stats_store.store_job_stats(job_stats)

            if job_log_path:
                self.write_job_logs(job_stats=job_stats, job_log_path=job_log_path)
            logger.info(msg=f"Job canceled: {job_run_id}")
            return True

        return False

    def request_delete_job_run(self, *, job_run_id: str) -> str:
        """
        Delete job run data including logs and statistics.

        Args:
            job_run_id: Job run identifier

        Returns:
            Confirmation message

        Raises:
            ValueError: If job_run_id not found
        """
        job_stats = self.job_stats_store.get_job_stats(job_run_id)
        if not job_stats:
            from docpipe.exceptions.docpipe_exceptions import JobRunNotFoundException

            raise JobRunNotFoundException(message=f"Job run not found: {job_run_id}", job_run_id=job_run_id)

        # Delete from store
        self.job_stats_store.delete_job_stats(job_run_id)

        logger.info(f"Deleted job run: {job_run_id}")
        return f"Job run {job_run_id} deleted successfully"

    @staticmethod
    def _format_schema_line(col_names: list[str] | None) -> str:
        if not col_names:
            return "Schema: unavailable"
        return f"Schema: {', '.join(str(col) for col in col_names)}"

    @staticmethod
    def _count_items(value: Any) -> int:
        if isinstance(value, list):
            return len(value)
        if value is None:
            return 0
        return int(value) if isinstance(value, int) else 0

    def _build_node_log_lines(self, node_stats: Any) -> list[str]:
        node_name: str = str(getattr(node_stats, "name", "Unknown step"))
        time_taken: Any | int = getattr(node_stats, "time_taken", 0) or 0
        node_status: str = str(getattr(node_stats, "node_status", "UNKNOWN"))
        col_names: Any | list[Any] = getattr(node_stats, "col_names", []) or []
        completed_count: Any | int = getattr(node_stats, "docs_completed_count", 0) or self._count_items(
            value=getattr(node_stats, "docs_completed", [])
        )
        failed_count = self._count_items(value=getattr(node_stats, "failed_docs", []))
        skipped_count = self._count_items(value=getattr(node_stats, "skipped_docs", []))
        total_count = self._count_items(value=getattr(node_stats, "total_docs", []))

        return [
            f"Starting execution: Step Name: {node_name}",
            f"Completed execution: {node_name}, Time = {time_taken:.2f} seconds",
            self._format_schema_line(col_names),
            (
                "Operator Summary: "
                f"total_docs={total_count}, "
                f"completed_docs={completed_count}, "
                f"failed_docs={failed_count}, "
                f"skipped_docs={skipped_count}, "
                f"node_status={node_status}"
            ),
        ]

    def get_job_run_logs(self, *, job_run_id: str) -> list[str]:
        job_stats: JobStats | None = self.get_job(job_run_id=job_run_id, include_node_stats=True)
        if not job_stats or not getattr(job_stats, "node_stats", None):
            return []

        node_stats_values: list[NodeStats] = list(job_stats.node_stats.values())
        sorted_nodes: list[NodeStats] = sorted(
            node_stats_values,
            key=lambda node: (
                getattr(node, "start_time", 0) or 0,
                getattr(node, "end_time", 0) or 0,
                str(getattr(node, "name", "")),
            ),
        )

        logs: list[str] = []
        for node in sorted_nodes:
            logs.extend(self._build_node_log_lines(node))
        return logs

    def is_job_run_complete(self, *, job_run_id: str) -> bool:
        """
        Check if job run has reached terminal state.

        Args:
            job_run_id: Job run identifier

        Returns:
            True if job is in terminal state, False otherwise
        """
        job_stats = self.job_stats_store.get_job_stats(job_run_id)
        if not job_stats:
            return False

        terminal_states = [
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELED,
        ]
        return job_stats.status in terminal_states

    def determine_and_update_final_documents_count(self, *, job_stats, dag_nodes: list[dict[str, Any]]) -> None:
        """
        Determine final status of each document and update job statistics.

        Enterprise-aligned algorithm:
        1. Mark all failed documents (from any node's failed_docs list)
        2. Identify ingest and destination nodes
        3. Mark completed documents (reached destination nodes, not failed)
        4. Mark skipped documents (from ingest, neither completed nor failed)
        5. Update job-level counts with reconciliation logging

        Args:
            job_stats: Job statistics object to update (JobStats)
            dag_nodes: List of DAG nodes with input/output edges
        """

        # Track final status of each document
        final_docs_status: dict[str, str] = {}

        # Step 1: Mark all failed documents
        self._mark_failed_documents(job_stats=job_stats, final_docs_status=final_docs_status)

        # Step 2: Identify ingest and destination nodes
        ingest_node_id, destination_node_ids = self._identify_ingest_and_destination_nodes(dag_nodes=dag_nodes)

        # Step 3: Mark completed documents (reached destination)
        self._mark_completed_documents(
            job_stats=job_stats, destination_node_ids=destination_node_ids, final_docs_status=final_docs_status
        )

        # Step 4: Mark skipped documents (not failed or completed)
        self._mark_skipped_documents(
            job_stats=job_stats, ingest_node_id=ingest_node_id, final_docs_status=final_docs_status
        )

        # Step 5: Update job-level counts with reconciliation
        self._update_job_stats_counts(job_stats=job_stats, final_docs_status=final_docs_status)

        # Persist updated job stats
        self.job_stats_store.store_job_stats(job_stats)

    def _mark_failed_documents(self, *, job_stats, final_docs_status: dict[str, str]) -> None:
        """Mark all documents that appear in any node's failed_docs list."""
        for _node_id, node_stat in job_stats.node_stats.items():
            failed_docs = node_stat.failed_docs if hasattr(node_stat, "failed_docs") else []
            for doc_id in failed_docs:
                final_docs_status[doc_id] = "FAILED"

        if final_docs_status:
            logger.info(f"Marked {len(final_docs_status)} documents as FAILED across all nodes")

    def _identify_ingest_and_destination_nodes(
        self, *, dag_nodes: list[dict[str, Any]]
    ) -> tuple[str | None, list[str]]:
        """
        Identify ingest node (no input edges) and destination nodes (no output edges).

        Returns:
            Tuple of (ingest_node_id, destination_node_ids)
        """
        ingest_node_id = None
        destination_node_ids = []

        for node in dag_nodes:
            node_id = node.get("id")
            if not node_id:
                continue

            # Ingest node: has no input edges
            if not node.get("input_edges"):
                ingest_node_id = node_id
                logger.info(f"Identified ingest node: {node_id}")

            # Destination nodes: have no output edges
            if not node.get("output_edges"):
                destination_node_ids.append(node_id)

        if destination_node_ids:
            logger.info(f"Identified {len(destination_node_ids)} destination nodes: {destination_node_ids}")
        else:
            logger.warning("No destination nodes found in DAG")

        return ingest_node_id, destination_node_ids

    def _mark_completed_documents(
        self, *, job_stats, destination_node_ids: list[str], final_docs_status: dict[str, str]
    ) -> None:
        """Mark documents that reached destination nodes (and not already failed)."""
        completed_count = 0

        for node_id in destination_node_ids:
            node_stat = job_stats.node_stats.get(node_id)
            if not node_stat:
                continue

            docs_completed = node_stat.docs_completed if hasattr(node_stat, "docs_completed") else []
            for doc_id in docs_completed:
                # Only mark as completed if not already marked as failed
                if doc_id not in final_docs_status:
                    final_docs_status[doc_id] = "COMPLETED"
                    completed_count += 1

        if completed_count > 0:
            logger.info(f"Marked {completed_count} documents as COMPLETED at destination nodes")

    def _mark_skipped_documents(
        self, *, job_stats, ingest_node_id: str | None, final_docs_status: dict[str, str]
    ) -> None:
        """Mark documents from ingest that were neither completed nor failed."""
        if not ingest_node_id:
            logger.warning("No ingest node found, cannot determine skipped documents")
            return

        ingest_node = job_stats.node_stats.get(ingest_node_id)
        if not ingest_node:
            logger.warning(f"Ingest node {ingest_node_id} not found in node_stats")
            return

        total_docs = ingest_node.total_docs if hasattr(ingest_node, "total_docs") else []
        skipped_count = 0

        for doc_id in total_docs:
            if doc_id not in final_docs_status:
                final_docs_status[doc_id] = "SKIPPED"
                skipped_count += 1

        if skipped_count > 0:
            logger.info(f"Marked {skipped_count} documents as SKIPPED (not completed or failed)")

    def _update_job_stats_counts(self, *, job_stats, final_docs_status: dict[str, str]) -> None:
        """
        Update job-level document counts based on final document status.
        Includes reconciliation logging for count inconsistencies.
        """
        from collections import Counter

        # Count documents by status
        final_counts = Counter(final_docs_status.values())
        completed_count = final_counts.get("COMPLETED", 0)
        failed_count = final_counts.get("FAILED", 0)
        skipped_count = final_counts.get("SKIPPED", 0)

        # Calculate totals
        total_classified = completed_count + failed_count + skipped_count

        # Store previous values for reconciliation logging
        prev_completed = job_stats.completed_docs or 0
        prev_failed = job_stats.failed_docs or 0
        prev_skipped = job_stats.skipped_docs or 0

        # Update job-level statistics
        job_stats.completed_docs = completed_count
        job_stats.failed_docs = failed_count
        job_stats.skipped_docs = skipped_count
        job_stats.processed_docs = total_classified

        # Reconciliation logging
        logger.info(
            f"Final document counts: completed={completed_count}, "
            f"failed={failed_count}, skipped={skipped_count}, "
            f"total_classified={total_classified}"
        )

        # Check for inconsistencies
        if prev_completed != completed_count or prev_failed != failed_count or prev_skipped != skipped_count:
            logger.info(
                f"Document count reconciliation: "
                f"completed {prev_completed}->{completed_count}, "
                f"failed {prev_failed}->{failed_count}, "
                f"skipped {prev_skipped}->{skipped_count}"
            )

        # Warn if total_docs doesn't match classified count
        total_docs_count = job_stats.total_docs or 0
        if total_docs_count > 0 and total_classified != total_docs_count:
            logger.warning(
                f"Document count mismatch: total_docs={total_docs_count} "
                f"but classified={total_classified} "
                f"(difference={total_docs_count - total_classified})"
            )

    def write_job_logs(self, *, job_stats, job_log_path: str) -> None:
        """
        Write job statistics to log file.

        Args:
            job_stats: Job statistics to write (JobStats)
            job_log_path: Path to write log file

        Raises:
            IOError: If file write fails
        """
        import os

        try:
            # Ensure directory exists
            os.makedirs(name=os.path.dirname(job_log_path), exist_ok=True)

            # Convert job stats to dict
            job_stats_dict: Any
            if isinstance(job_stats, JobStats):
                job_stats_dict = job_stats.model_dump()
            else:
                job_stats_dict = job_stats

            # Write to file
            with open(job_log_path, "w") as f:
                json.dump(job_stats_dict, f, indent=2)

            logger.info(f"Wrote job logs to: {job_log_path}")
        except Exception as e:
            logger.error(f"Failed to write job logs to {job_log_path}: {e}")
            raise OSError(f"Failed to write job logs: {e}") from e

    def list_job_runs(
        self,
        *,
        job_id: str | None = None,
        status: ExecutionStatus | str | None = None,
        limit: int = 100,
    ) -> list[JobStats]:
        """
        List job runs with optional filters.

        Args:
            job_id: Optional filter by job_id
            status: Optional filter by status
            limit: Maximum number of results

        Returns:
            List of JobStats matching filters (sorted by start_time desc)
        """
        # Delegate to store
        return self.job_stats_store.list_job_runs(job_id=job_id, status=status, limit=limit)

    def get_formatted_job_stats(self, *, job_run_id: str, include_logs: bool = False) -> Any:
        """
        Get job statistics with detailed formatting for API responses.

        Returns comprehensive job stats including:
        - node_sequence: Ordered list of node IDs by execution time
        - job_stats: Complete job-level statistics
        - node_metadata: Array of node metadata items
        - Individual node log strings as top-level keys (dynamic fields, only if include_logs=True)

        Args:
            job_run_id: Job run identifier
            include_logs: Whether to include individual node log strings as dynamic fields

        Returns:
            JobRunStatusResponse DTO ready for API response (returned as Any to avoid circular imports)

        Raises:
            JobRunNotFoundException: If job_run_id not found
        """
        from docpipe.api.dto.mappers.job_stats_mapper import JobStatsMapper
        from docpipe.exceptions.docpipe_exceptions import JobRunNotFoundException

        # Get job stats with node stats
        job_stats: JobStats | None = self.get_job(job_run_id=job_run_id, include_node_stats=True)

        if not job_stats:
            raise JobRunNotFoundException(message=f"Job run not found: {job_run_id}", job_run_id=job_run_id)

        # Delegate to mapper for enterprise-compatible model construction
        return JobStatsMapper.to_status_response(job_stats=job_stats, include_logs=include_logs)

    @staticmethod
    def _calculate_node_sequence(*, node_stats: dict) -> list[str]:
        """Calculate node execution sequence based on start_time."""
        if not node_stats:
            return []

        # Sort nodes by start_time, then end_time, then name
        sorted_nodes: list[tuple[Any, Any]] = sorted(
            node_stats.items(),
            key=lambda item: (
                item[1].get("start_time", 0) if isinstance(item[1], dict) else getattr(item[1], "start_time", 0),
                item[1].get("end_time", 0) if isinstance(item[1], dict) else getattr(item[1], "end_time", 0),
                item[1].get("name", "") if isinstance(item[1], dict) else getattr(item[1], "name", ""),
            ),
        )
        return [node_id for node_id, _ in sorted_nodes]

    @staticmethod
    def _build_node_metadata_array(*, node_stats: dict) -> list[dict]:
        """Build node_metadata array from node_stats."""
        metadata_items = []
        for node_id, node_stat in node_stats.items():
            if isinstance(node_stat, dict):
                name = node_stat.get("name", "Unknown")
                node_metadata = node_stat.get(OperatorConstants.Metadata.NODE_METADATA)
            else:
                name = getattr(node_stat, "name", "Unknown")
                node_metadata = getattr(node_stat, OperatorConstants.Metadata.NODE_METADATA, None)

            metadata_items.append(
                {
                    OperatorConstants.Misc.ID: node_id,
                    OperatorConstants.Misc.OPERATOR: name,
                    OperatorConstants.Metadata.NODE_METADATA: node_metadata,
                }
            )

        return metadata_items

    @staticmethod
    def _format_node_log_string(*, node_id: str, node_stat: Any) -> str:  # NOSONAR python:S3776
        if isinstance(node_stat, dict):
            name = node_stat.get("name", "Unknown")
            time_taken = node_stat.get("time_taken", 0) or 0
            col_names = node_stat.get("col_names", []) or []
            node_metadata = node_stat.get(OperatorConstants.Metadata.NODE_METADATA)
            node_status = node_stat.get("node_status", "Completed")
            error = node_stat.get("error", "")
        else:
            name = getattr(node_stat, "name", "Unknown")
            time_taken = getattr(node_stat, "time_taken", 0) or 0
            col_names = getattr(node_stat, "col_names", []) or []
            node_metadata = getattr(node_stat, OperatorConstants.Metadata.NODE_METADATA, None)
            node_status = getattr(node_stat, "node_status", "Completed")
            error = getattr(node_stat, "error", "")

        # Handle ExecutionStatus enum vs string
        terminal_states_values = frozenset(state.value for state in TERMINAL_NODE_STATES)
        current_status_val = node_status.value if hasattr(node_status, "value") else node_status

        # Build log string parts in correct sequence
        log_parts = []
        # 1. Starting execution
        log_parts.append(f"Starting execution: Step Name: {name}")

        # 2. Schema information
        if col_names:
            log_parts.append("\nSchema:")
            for col_name in col_names:
                log_parts.append(f"{col_name}: string")

        # 3. Operator metadata if available
        if node_metadata:
            log_parts.append("\nOperator Metadata:")
            log_parts.append(
                json.dumps(
                    {OperatorConstants.Metadata.NODE_METADATA: node_metadata, "id": node_id, "operator": name}, indent=2
                )
            )

        # 4. Completion status (only for terminal states)
        if current_status_val in terminal_states_values:
            if current_status_val == ExecutionStatus.FAILED.value:
                log_parts.append(f"\nFailed execution: {name}, time= {time_taken:.2f} seconds")
            elif current_status_val == ExecutionStatus.SKIPPED.value:
                log_parts.append(f"\nSkipped execution: {name}, time= {time_taken:.2f} seconds")
            else:
                log_parts.append(f"\nCompleted execution: {name}, time= {time_taken:.2f} seconds")

        # 5. Error details if available
        if error:
            log_parts.append("\nError Details:")
            log_parts.append(f"  {error}")

        return "\n".join(log_parts)

    def create_pending_batch_node_stats(
        self,
        *,
        job_run_id: str,
        batch_ids: list[str],
        batch_nums: list[int],
        downstream_node_ids: list[str],
        downstream_node_names: list[str],
    ) -> None:
        """
        Bulk create PENDING batch node stats for all batch/node combinations.

        Creates minimal pending stats records that will be updated when
        start_node_execution is called with the actual node name and batch_id.

        Args:
            job_run_id: Job run identifier
            batch_ids: List of batch IDs from retained batches (after empty-batch filtering)
            batch_nums: List of batch numbers corresponding to batch_ids (same length)
            downstream_node_ids: List of downstream node IDs (excluding ingest)
            downstream_node_names: List of downstream node names corresponding to node IDs (same length)

        Raises:
            ValueError: If lists length mismatch
            IOError: If bulk operation fails
        """
        if len(batch_ids) != len(batch_nums):
            raise ValueError(f"batch_ids and batch_nums must have same length: {len(batch_ids)} != {len(batch_nums)}")

        if len(downstream_node_ids) != len(downstream_node_names):
            raise ValueError(
                f"downstream_node_ids and downstream_node_names must have same length: "
                f"{len(downstream_node_ids)} != {len(downstream_node_names)}"
            )

        # Create pending node stats for all batch/node combinations
        pending_stats_list = []
        for batch_id, batch_num in zip(batch_ids, batch_nums, strict=False):
            for node_id, node_name in zip(downstream_node_ids, downstream_node_names, strict=False):
                # Create minimal pending record with proper node name
                pending_node_stats: NodeStats = NodeStats(
                    node_id=node_id,
                    name=node_name,
                    node_status=ExecutionStatus.PENDING.value,
                    batch_id=batch_id,
                    batch_num=batch_num,
                    total_docs=[],
                    docs_completed=[],
                    docs_completed_count=0,
                    failed_docs=[],
                    skipped_docs=[],
                    col_names=[],
                )
                pending_stats_list.append(pending_node_stats)

        # Bulk store all pending stats
        if pending_stats_list:
            self.job_stats_store.bulk_store_node_stats(job_run_id=job_run_id, node_stats_list=pending_stats_list)
            logger.info(
                f"Created {len(pending_stats_list)} pending batch node stats: "
                f"{len(batch_ids)} batches x {len(downstream_node_ids)} nodes"
            )
