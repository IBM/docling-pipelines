"""
NodeStatsAggregator - Centralized aggregation logic for node statistics.

This service encapsulates ALL aggregation logic so that JobStatsStore
implementations don't need to duplicate it. Stores only fetch raw data,
and this service handles the aggregation.
"""

from collections import defaultdict

from docpipe.core.constants.constants import DocpipeConstants, ExecutionStatus
from docpipe.core.job_management.application.aggregation import MetadataAggregator, aggregate_batch_node_stats
from docpipe.core.job_management.domain.models import NodeStats
from docpipe.core.job_management.domain.ports import JobStatsStore
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class NodeStatsAggregator:
    """
    Common aggregation layer for node statistics.

    This class encapsulates ALL aggregation logic so that JobStatsStore
    implementations don't need to duplicate it. Stores only fetch raw data,
    and this class handles the aggregation.

    Benefits:
    - Single source of truth for aggregation logic
    - Stores remain simple (just data access)
    - Consistent behavior across all storage backends
    - Easy to test and maintain
    """

    def __init__(self, *, job_stats_store: JobStatsStore):
        """
        Initialize NodeStatsAggregator.

        Args:
            job_stats_store: Storage adapter for fetching raw node stats
        """
        self.job_stats_store = job_stats_store
        self.metadata_aggregator = MetadataAggregator()

    def get_aggregated_node_stats(self, *, job_id: str, job_run_id: str) -> dict[str, NodeStats]:
        """
        Get aggregated node statistics.

        This method:
        1. Fetches ALL raw node stats from store
        2. Separates batch vs non-batch records
        3. Groups batch records by node_id
        4. Applies shared aggregation logic
        5. Returns aggregated results

        Args:
            job_id: Job identifier
            job_run_id: Job run identifier

        Returns:
            Dictionary mapping node_id to aggregated NodeStats
        """
        # Step 1: Fetch ALL raw records from store
        all_records = self.job_stats_store.get_node_stats(job_run_id=job_run_id)

        if not all_records:
            return {}

        # Handle both dict (legacy PickleJobStatsStore) and list (new stores) return types
        if isinstance(all_records, dict):
            # Legacy PickleJobStatsStore returns dict[str, NodeStats]
            records_list = list(all_records.values())
        elif isinstance(all_records, list):
            # New stores return List[NodeStats]
            records_list = all_records
        else:
            logger.error(f"Unexpected return type from get_node_stats: {type(all_records)}")
            return {}

        # Step 2: Separate batch vs non-batch records
        batch_records = [r for r in records_list if getattr(r, DocpipeConstants.BATCH_ID, None) is not None]
        non_batch_records = [r for r in records_list if getattr(r, DocpipeConstants.BATCH_ID, None) is None]

        result = {}

        # Step 3: Process batch records (need aggregation)
        if batch_records:
            # Group by node_id
            batch_records_by_node = defaultdict(list)
            for record in batch_records:
                node_id = getattr(record, "id", getattr(record, DocpipeConstants.NODE_ID, None))
                if node_id:
                    batch_records_by_node[node_id].append(record)

            # Step 4: Aggregate each node's batch records
            for node_id, node_batch_records in batch_records_by_node.items():
                # Skip nodes where ALL batches are PENDING/QUEUED
                all_pending = all(
                    getattr(r, "node_status", ExecutionStatus.PENDING.value)
                    in (ExecutionStatus.PENDING.value, ExecutionStatus.QUEUED.value)
                    for r in node_batch_records
                )
                if all_pending:
                    continue

                # Use shared aggregation function
                aggregated_stats = aggregate_batch_node_stats(
                    node_id=node_id, batch_records=node_batch_records, aggregator=self.metadata_aggregator
                )

                if aggregated_stats:
                    result[node_id] = aggregated_stats

        # Step 5: Add non-batch records directly (no aggregation needed)
        for record in non_batch_records:
            node_id = getattr(record, "id", getattr(record, DocpipeConstants.NODE_ID, None))
            if node_id:
                result[node_id] = record

        return result

    def get_batch_node_stats(self, *, job_id: str, job_run_id: str) -> dict[str, dict[str, NodeStats]]:
        """
        Get batch-level node statistics (no aggregation).

        Returns raw batch records grouped by node_id, then batch_id.
        Matches micro-batching specification.

        Args:
            job_id: Job identifier
            job_run_id: Job run identifier

        Returns:
            Nested dict: {node_id: {batch_id: NodeStats}}
        """
        # Use store's get_batch_node_stats which already groups correctly
        return self.job_stats_store.get_batch_node_stats(job_run_id=job_run_id)
