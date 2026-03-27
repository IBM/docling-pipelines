"""
Batch Manager - Handles batch creation and management for flow execution.

This class encapsulates all batch-related logic including:
- Batch creation from PyArrow tables
- Batch configuration management
- Semaphore management for concurrent operator execution
"""

import threading
from typing import Any

import pyarrow as pa
from data_processing.data_access import DataAccess, DataAccessFactory

from common.constants.constants import DatasiftConstants
from common.util.infrastructure.logging import get_logger

logger = get_logger()


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
        self._global_operator_semaphore: threading.Semaphore | None = None

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
        batching_enabled = global_config.get(DatasiftConstants.ENABLE_MICRO_BATCHING, False)
        batch_size = global_config.get(DatasiftConstants.MICRO_BATCH_SIZE, DatasiftConstants.DEFAULT_MICRO_BATCH_SIZE)
        return batching_enabled, batch_size

    def create_batches(self, *, table: pa.Table, batch_size: int) -> list[pa.Table]:
        """
        Split a PyArrow table into batches.
        
        Args:
            table: PyArrow table to split
            batch_size: Maximum number of rows per batch
            
        Returns:
            List of PyArrow tables, each containing at most batch_size rows
        """
        batches = []
        for batch in table.to_batches(max_chunksize=batch_size):
            batches.append(pa.Table.from_batches([batch]))
        return batches

    def prepare_batches(
        self, 
        *, 
        ingested_table: pa.Table, 
        global_config: dict,
        common_log_arguments: dict | None = None
    ) -> tuple[list[pa.Table], dict[str, Any]]:
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
            - batches: List of PyArrow tables (single table for non-batch mode)
            - updated_global_config: Config with batch-related parameters added
        """
        batching_enabled, batch_size = self.configure_batching(global_config=global_config)
        updated_config = global_config.copy()
        
        if batching_enabled:
            # BATCH MODE: Split table into multiple batches
            # batch_size is guaranteed to be int here since batching_enabled is True
            assert batch_size is not None, "batch_size must be set when batching is enabled"
            batches = self.create_batches(table=ingested_table, batch_size=batch_size)
            batch_count = len(batches)
            
            self.logger.info(
                f">>> Split {ingested_table.num_rows} rows into {batch_count} batches of size {batch_size}",
                extra=common_log_arguments
            )
            
            # Add batch_count to config for operators to use
            updated_config[DatasiftConstants.BATCH_COUNT] = batch_count
        else:
            # NON-BATCH MODE: Use entire table as single "batch"
            batches = [ingested_table]
            
            self.logger.info(
                f">>> Non-batch mode: Processing all {ingested_table.num_rows} rows in single execution",
                extra=common_log_arguments
            )
            
            # NOTE: Do NOT set BATCH_COUNT or BATCH_NUM in non-batch mode
            # This ensures output paths don't include batch number subdirectories
        
        return batches, updated_config

    def initialize_operator_semaphore(self, *, max_concurrent_operators: int):
        """
        Initialize the global operator semaphore for concurrent execution control.
        
        Args:
            max_concurrent_operators: Maximum number of operators that can execute concurrently
        """
        self._global_operator_semaphore = threading.Semaphore(max_concurrent_operators)
        self.logger.debug(f"Initialized operator semaphore with {max_concurrent_operators} slots")

    def get_operator_semaphore(self) -> threading.Semaphore | None:
        """
        Get the global operator semaphore.
        
        Returns:
            The global operator semaphore or None if not initialized
        """
        return self._global_operator_semaphore

    def reset_operator_semaphore(self):
        """Reset the global operator semaphore."""
        self._global_operator_semaphore = None
        self.logger.debug("Reset operator semaphore")

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

# Made with Bob
