"""
Batch Manager - Handles batch creation and management for flow execution.

This class encapsulates all batch-related logic including:
- Batch creation from PyArrow tables
- Batch configuration management
- Semaphore management for concurrent operator execution
- UUID batch_id generation for retained batches
"""

import threading
import uuid
from typing import Any

import pyarrow as pa
from data_processing.data_access import DataAccess, DataAccessFactory

from docpipe.core.constants.constants import DocpipeConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class BatchInfo:
    """Container for batch data with metadata."""

    def __init__(self, *, batch_id: str, batch_num: int, table: pa.Table):
        self.batch_id = batch_id
        self.batch_num = batch_num
        self.table = table


class BatchManager:
    """
    Manages batch creation and execution control for flow processing.

    Responsibilities:
    - Split PyArrow tables into batches based on configuration
    - Manage global operator semaphore for concurrent execution control
    - Create DataAccess objects for batch tables
    - Determine batch mode vs non-batch mode execution
    """

    def __init__(self):
        """Initialize the batch manager."""
        self.logger = get_logger()
        self._batch_semaphore: threading.Semaphore | None = None

    def configure_batching(self, *, global_config: dict) -> tuple[bool, int | None]:
        """
        Determine batching configuration from global config.

        Args:
            global_config: Global configuration dictionary

        Returns:
            Tuple of (batching_enabled, batch_size)
            - batching_enabled: Whether micro-batching is enabled
            - batch_size: Size of each batch (None if batching disabled)
        """
        batching_enabled = global_config.get(DocpipeConstants.ENABLE_MICRO_BATCHING, False)
        batch_size = global_config.get(DocpipeConstants.MICRO_BATCH_SIZE, DocpipeConstants.DEFAULT_MICRO_BATCH_SIZE)
        return batching_enabled, batch_size

    def create_batches(self, *, table: pa.Table, batch_size: int) -> list[BatchInfo]:  # NOSONAR python:S3776
        """
        Split a PyArrow table into batches based on file size for balanced workload distribution.

        Filters out empty batches and assigns UUID batch_id to each retained batch.
        Uses file-size-based batching when SIZE column exists, falls back to record-count batching.

        Algorithm:
        - If SIZE column exists: Uses greedy bin-packing to distribute files by size
        - If SIZE column missing: Falls back to simple record-count batching
        - Memory-efficient: Uses numpy arrays and PyArrow's zero-copy operations
        - Schema-preserving: Uses PyArrow's take() which maintains exact schema structure

        Args:
            table: PyArrow table containing file metadata with SIZE field (in bytes)
            batch_size: Target number of records per batch (used as fallback or to calculate num_batches)

        Returns:
            List of BatchInfo objects with batch_id, batch_num, and non-empty tables
        """
        import numpy as np

        num_rows = table.num_rows

        # Handle empty table
        if num_rows == 0:
            return []

        # Check if SIZE column exists for file-size-based batching
        if OperatorConstants.Misc.SIZE not in table.column_names:
            self.logger.warning(
                f"SIZE column not found in table. Falling back to record-count batching. "
                f"Available columns: {table.column_names}"
            )
            # Fallback to record-count batching with empty-batch filtering
            batches = []
            batch_num = 0
            for batch in table.to_batches(max_chunksize=batch_size):
                batch_table = pa.Table.from_batches([batch])

                # Filter out empty batches
                if batch_table.num_rows == 0:
                    self.logger.debug(f"Skipping empty batch at position {batch_num}")
                    continue

                # Generate UUID batch_id for retained batch
                batch_id = str(uuid.uuid4())
                batches.append(BatchInfo(batch_id=batch_id, batch_num=batch_num, table=batch_table))
                batch_num += 1

            return batches

        # Calculate number of batches based on batch_size
        num_batches = max(1, (num_rows + batch_size - 1) // batch_size)

        # Extract file sizes as numpy array (memory-efficient, zero-copy when possible)
        size_column = table.column(OperatorConstants.Misc.SIZE)
        size_array = size_column.to_numpy(zero_copy_only=False)

        # Handle None/null values and negative sizes
        size_array = np.where(np.isnan(size_array) | (size_array < 0), 0, size_array).astype(np.int64)

        total_size = size_array.sum()

        # Handle edge case: all files have zero size
        if total_size == 0:
            self.logger.warning("All files have zero size. Using simple round-robin distribution.")
            # Simple round-robin: create batches directly using take() to preserve schema
            result_batches = []
            batch_num = 0
            for batch_idx in range(num_batches):
                indices = list(range(batch_idx, num_rows, num_batches))
                if indices:
                    batch_table = table.take(indices)
                    # Filter out empty batches
                    if batch_table.num_rows == 0:
                        continue
                    batch_id = str(uuid.uuid4())
                    result_batches.append(BatchInfo(batch_id=batch_id, batch_num=batch_num, table=batch_table))
                    batch_num += 1
            return result_batches

        # Create index array and sort by size (largest first) for better bin-packing
        sorted_indices = np.argsort(-size_array)  # Negative for descending order

        # Initialize batch tracking arrays (memory-efficient)
        batch_sizes = np.zeros(num_batches, dtype=np.int64)
        batch_assignments = np.zeros(num_rows, dtype=np.int32)

        # Greedy bin-packing: assign each file to the batch with smallest current total
        for i in range(num_rows):
            file_idx = sorted_indices[i]
            file_size = size_array[file_idx]
            # Find batch with minimum cumulative size
            min_batch_idx = np.argmin(batch_sizes)
            batch_assignments[file_idx] = min_batch_idx
            batch_sizes[min_batch_idx] += file_size

        # Log batch size distribution for monitoring
        mb_divisor = 1024 * 1024
        total_size_mb = total_size / mb_divisor
        avg_size_mb = total_size_mb / num_batches
        size_distribution = [f"Batch {i}: {batch_sizes[i] / mb_divisor:.2f} MB" for i in range(num_batches)]
        self.logger.info(
            f"Created {num_batches} size-balanced batches. "
            f"Total size: {total_size_mb:.2f} MB, Avg per batch: {avg_size_mb:.2f} MB. "
            f"Distribution: {'; '.join(size_distribution)}"
        )

        # Convert to BatchInfo objects using take() which preserves schema exactly
        result_batches = []
        batch_num = 0
        for batch_idx in range(num_batches):
            # Get indices for this batch (maintains original order)
            batch_indices: Any = np.nonzero(batch_assignments == batch_idx)[0]
            if len(batch_indices) > 0:
                batch_table = table.take(batch_indices.tolist())
                # Filter out empty batches
                if batch_table.num_rows == 0:
                    self.logger.debug(f"Skipping empty batch at index {batch_idx}")
                    continue
                # Generate UUID batch_id for retained batch
                batch_id = str(uuid.uuid4())
                result_batches.append(BatchInfo(batch_id=batch_id, batch_num=batch_num, table=batch_table))
                batch_num += 1

        return result_batches

    def prepare_batches(
        self, *, ingested_table: pa.Table, global_config: dict, common_log_arguments: dict | None = None
    ) -> tuple[list[BatchInfo], dict[str, Any]]:
        """
        Prepare batches for execution based on configuration.

        This method determines whether to use batch mode or non-batch mode
        and prepares the appropriate batch list and updated global config.

        Args:
            ingested_table: The ingested PyArrow table
            global_config: Global configuration dictionary
            common_log_arguments: Common logging arguments

        Returns:
            Tuple of (batches, updated_global_config)
            - batches: List of BatchInfo objects (single BatchInfo for non-batch mode)
            - updated_global_config: Config with batch-related parameters added
        """
        batching_enabled, batch_size = self.configure_batching(global_config=global_config)
        updated_config = global_config.copy()

        if batching_enabled:
            # BATCH MODE: Split table into multiple batches
            if batch_size is None:
                raise FlowExecutionFailedException("micro_batch_size must be set when micro-batching is enabled")
            batches = self.create_batches(table=ingested_table, batch_size=batch_size)
            batch_count = len(batches)

            self.logger.info(
                f">>> Split {ingested_table.num_rows} rows into {batch_count} batches of size {batch_size}",
                extra=common_log_arguments,
            )

            # Add batch_count to config for operators to use
            updated_config[DocpipeConstants.BATCH_COUNT] = batch_count
        else:
            # NON-BATCH MODE: Use entire table as single "batch"
            # Create a single BatchInfo with batch_id for consistency
            batch_id: str = str(uuid.uuid4())
            batches = [BatchInfo(batch_id=batch_id, batch_num=0, table=ingested_table)]

            self.logger.info(
                f">>> Non-batch mode: Processing all {ingested_table.num_rows} rows in single execution",
                extra=common_log_arguments,
            )

            # NOTE: Do NOT set BATCH_COUNT or BATCH_NUM in non-batch mode
            # This ensures output paths don't include batch number subdirectories

        return batches, updated_config

    def initialize_batch_semaphore(self, *, max_concurrent_batches: int):
        """
        Initialize the batch semaphore for concurrent batch execution control.

        Args:
            max_concurrent_batches: Maximum number of batches that can execute concurrently
        """
        self._batch_semaphore = threading.Semaphore(max_concurrent_batches)
        self.logger.debug(f"Initialized batch semaphore with {max_concurrent_batches} slots")

    def get_batch_semaphore(self) -> threading.Semaphore | None:
        """
        Get the batch semaphore.

        Returns:
            The batch semaphore or None if not initialized
        """
        return self._batch_semaphore

    def reset_batch_semaphore(self):
        """Reset the batch semaphore."""
        self._batch_semaphore = None
        self.logger.debug("Reset batch semaphore")

    @staticmethod
    def create_batch_data_access(*, batch_table: pa.Table) -> DataAccess:
        """
        Create a DataAccess object for a batch table.

        Args:
            batch_table: PyArrow table for the batch

        Returns:
            DataAccess object containing the batch table
        """
        data_access_factory = DataAccessFactory()
        config = {"data_config": {"da_class": "data_processing.data_access.DataAccessMemory"}}
        data_access_factory.apply_input_params(config)
        batch_data_access = data_access_factory.create_data_access()
        batch_data_access.save_table(path="", table=batch_table)
        return batch_data_access
