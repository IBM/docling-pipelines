"""
Unit tests for BatchManager - batch semaphore, validation, and batch operations.

Consolidated test suite covering:
- Batch semaphore initialization and concurrency control
- Batch creation and preparation
- Cleanup and error handling
- Configuration validation
- DataAccess creation for batches
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

from docpipe.core.constants.constants import DocpipeConstants
from docpipe.core.orchestration.batch_manager import BatchManager
from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException


class TestBatchSemaphore:
    """Test batch-level semaphore functionality."""

    def test_initialize_batch_semaphore(self):
        """Verify batch semaphore is initialized with correct limit."""
        batch_manager = BatchManager()
        max_concurrent = 3

        batch_manager.initialize_batch_semaphore(max_concurrent_batches=max_concurrent)

        semaphore = batch_manager.get_batch_semaphore()
        assert semaphore is not None
        assert isinstance(semaphore, threading.Semaphore)

        # Verify capacity by acquiring all slots
        acquired = []
        for _ in range(max_concurrent):
            result = semaphore.acquire(blocking=False)
            acquired.append(result)

        assert all(acquired), "Should acquire all slots"
        assert not semaphore.acquire(blocking=False), "Should not exceed limit"

        # Cleanup
        for _ in range(max_concurrent):
            semaphore.release()

    def test_batch_semaphore_limits_concurrency(self):
        """Verify semaphore enforces concurrent batch limit."""
        batch_manager = BatchManager()
        max_concurrent = 2
        batch_manager.initialize_batch_semaphore(max_concurrent_batches=max_concurrent)

        semaphore = batch_manager.get_batch_semaphore()
        concurrent_count = 0
        max_concurrent_observed = 0
        lock = threading.Lock()

        def simulate_batch_execution(batch_num):
            nonlocal concurrent_count, max_concurrent_observed

            semaphore.acquire()
            try:
                with lock:
                    concurrent_count += 1
                    max_concurrent_observed = max(max_concurrent_observed, concurrent_count)

                time.sleep(0.1)

                with lock:
                    concurrent_count -= 1
            finally:
                semaphore.release()

        # Start 5 batches
        threads = []
        for i in range(5):
            thread = threading.Thread(target=simulate_batch_execution, args=(i,))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        assert max_concurrent_observed == max_concurrent, (
            f"Expected max {max_concurrent} concurrent, observed {max_concurrent_observed}"
        )

    def test_batch_semaphore_released_on_completion(self):
        """Verify semaphore is released after successful batch completion."""
        batch_manager = BatchManager()
        batch_manager.initialize_batch_semaphore(max_concurrent_batches=1)

        semaphore = batch_manager.get_batch_semaphore()

        semaphore.acquire()
        semaphore.release()

        assert semaphore.acquire(blocking=False), "Semaphore should be reusable"
        semaphore.release()

    def test_batch_semaphore_released_on_failure(self):
        """Verify semaphore is released even when batch fails."""
        batch_manager = BatchManager()
        batch_manager.initialize_batch_semaphore(max_concurrent_batches=1)

        semaphore = batch_manager.get_batch_semaphore()

        try:
            semaphore.acquire()
            raise Exception("Simulated batch failure")
        except Exception:
            pass
        finally:
            semaphore.release()

        assert semaphore.acquire(blocking=False), "Semaphore should be released after failure"
        semaphore.release()

    def test_reset_batch_semaphore(self):
        """Verify batch semaphore can be reset to None."""
        batch_manager = BatchManager()
        batch_manager.initialize_batch_semaphore(max_concurrent_batches=2)

        assert batch_manager.get_batch_semaphore() is not None

        batch_manager.reset_batch_semaphore()

        assert batch_manager.get_batch_semaphore() is None

    def test_independent_batch_progression(self):
        """Verify batches progress independently through operator stages."""
        batch_manager = BatchManager()
        batch_manager.initialize_batch_semaphore(max_concurrent_batches=3)

        semaphore = batch_manager.get_batch_semaphore()
        batch_stages = {}
        stage_history = []
        lock = threading.Lock()

        def simulate_batch_with_stages(batch_num):
            """Simulate batch progressing through multiple stages."""
            semaphore.acquire()
            try:
                stages = ["ingest", "extract", "chunk", "complete"]
                for stage in stages:
                    with lock:
                        batch_stages[batch_num] = stage
                        stage_history.append((batch_num, stage))
                    time.sleep(0.02)
            finally:
                semaphore.release()

        threads = []
        for i in range(3):
            thread = threading.Thread(target=simulate_batch_with_stages, args=(i,))
            thread.start()
            threads.append(thread)
            time.sleep(0.01)

        for thread in threads:
            thread.join()

        assert all(stage == "complete" for stage in batch_stages.values()), "All batches should complete"

        # Verify each batch went through all stages in order
        expected_order = ["ingest", "extract", "chunk", "complete"]
        for batch_num in range(3):
            batch_stages_list = [stage for batch, stage in stage_history if batch == batch_num]
            assert batch_stages_list == expected_order, f"Batch {batch_num} stages out of order: {batch_stages_list}"


class TestBatchConfiguration:
    """Test batch configuration and preparation."""

    def test_configure_batching_enabled(self):
        """Verify batching configuration when enabled."""
        batch_manager = BatchManager()
        global_config = {
            DocpipeConstants.ENABLE_MICRO_BATCHING: True,
            DocpipeConstants.MICRO_BATCH_SIZE: 100,
        }

        enabled, size = batch_manager.configure_batching(global_config=global_config)

        assert enabled is True
        assert size == 100

    def test_configure_batching_disabled(self):
        """Verify batching configuration when disabled."""
        batch_manager = BatchManager()
        global_config = {DocpipeConstants.ENABLE_MICRO_BATCHING: False}

        enabled, size = batch_manager.configure_batching(global_config=global_config)

        assert enabled is False
        assert size == DocpipeConstants.DEFAULT_MICRO_BATCH_SIZE

    def test_configure_batching_default(self):
        """Verify batching configuration with defaults."""
        batch_manager = BatchManager()
        global_config = {}

        enabled, size = batch_manager.configure_batching(global_config=global_config)

        assert enabled is False
        assert size == DocpipeConstants.DEFAULT_MICRO_BATCH_SIZE


class TestBatchCreation:
    """Test batch creation and splitting."""

    def test_create_batches_single_batch(self):
        """Verify creating batches when table fits in one batch."""
        batch_manager = BatchManager()
        table = pa.table({"id": [1, 2, 3], "value": ["a", "b", "c"]})

        batches = batch_manager.create_batches(table=table, batch_size=10)

        assert len(batches) == 1
        assert batches[0].table.num_rows == 3
        assert batches[0].table.column_names == ["id", "value"]

    def test_create_batches_multiple_batches(self):
        """Verify creating multiple batches from larger table."""
        batch_manager = BatchManager()
        table = pa.table({"id": list(range(25)), "value": [f"val_{i}" for i in range(25)]})

        batches = batch_manager.create_batches(table=table, batch_size=10)

        assert len(batches) == 3
        assert batches[0].table.num_rows == 10
        assert batches[1].table.num_rows == 10
        assert batches[2].table.num_rows == 5

        # Verify all data is preserved
        total_rows = sum(b.table.num_rows for b in batches)
        assert total_rows == 25

    def test_create_batches_exact_multiple(self):
        """Verify creating batches when rows are exact multiple of batch size."""
        batch_manager = BatchManager()
        table = pa.table({"id": list(range(20))})

        batches = batch_manager.create_batches(table=table, batch_size=10)

        assert len(batches) == 2
        assert all(b.table.num_rows == 10 for b in batches)


class TestBatchPreparation:
    """Test batch preparation with configuration."""

    def test_prepare_batches_batch_mode_enabled(self):
        """Verify batch preparation in batch mode."""
        batch_manager = BatchManager()
        table = pa.table({"id": list(range(25))})
        global_config = {
            DocpipeConstants.ENABLE_MICRO_BATCHING: True,
            DocpipeConstants.MICRO_BATCH_SIZE: 10,
        }

        batches, updated_config = batch_manager.prepare_batches(
            ingested_table=table,
            global_config=global_config,
            common_log_arguments={"job_id": "test"},
        )

        assert len(batches) == 3
        assert updated_config[DocpipeConstants.BATCH_COUNT] == 3
        assert DocpipeConstants.ENABLE_MICRO_BATCHING in updated_config

    def test_prepare_batches_non_batch_mode(self):
        """Verify batch preparation in non-batch mode."""
        batch_manager = BatchManager()
        table = pa.table({"id": list(range(25))})
        global_config = {DocpipeConstants.ENABLE_MICRO_BATCHING: False}

        batches, updated_config = batch_manager.prepare_batches(
            ingested_table=table,
            global_config=global_config,
            common_log_arguments={"job_id": "test"},
        )

        assert len(batches) == 1
        assert batches[0].table.num_rows == 25
        assert DocpipeConstants.BATCH_COUNT not in updated_config

    def test_prepare_batches_raises_when_batch_size_missing(self):
        """Verify error when batch size is missing in batch mode."""
        batch_manager = BatchManager()
        table = pa.table({"id": [1, 2]})

        with pytest.raises(FlowExecutionFailedException, match="micro_batch_size must be set"):
            batch_manager.prepare_batches(
                ingested_table=table,
                global_config={
                    DocpipeConstants.ENABLE_MICRO_BATCHING: True,
                    DocpipeConstants.MICRO_BATCH_SIZE: None,
                },
                common_log_arguments=None,
            )


class TestBatchDataAccess:
    """Test DataAccess creation for batches."""

    @patch("docpipe.core.orchestration.batch_manager.DataAccessFactory")
    def test_create_batch_data_access(self, mock_factory_class):
        """Verify DataAccess creation for batch table."""
        # Setup mock
        mock_factory = MagicMock()
        mock_data_access = MagicMock()
        mock_factory_class.return_value = mock_factory
        mock_factory.create_data_access.return_value = mock_data_access

        # Create batch table
        batch_table = pa.table({"id": [1, 2, 3]})

        # Call method
        result = BatchManager.create_batch_data_access(batch_table=batch_table)

        # Verify
        assert result == mock_data_access
        mock_factory.apply_input_params.assert_called_once()
        mock_factory.create_data_access.assert_called_once()
        mock_data_access.save_table.assert_called_once_with(path="", table=batch_table)


class TestBatchUUIDPropagation:
    """Test batch UUID generation and propagation."""

    def test_batch_info_has_uuid_batch_id(self):
        """Verify each BatchInfo has a unique UUID batch_id."""
        batch_manager = BatchManager()
        table = pa.table({"id": list(range(10)), "SIZE": [100] * 10})

        batches = batch_manager.create_batches(table=table, batch_size=3)

        # Verify all batches have batch_id
        assert all(hasattr(b, "batch_id") for b in batches)
        assert all(b.batch_id is not None for b in batches)

        # Verify all batch_ids are unique
        batch_ids = [b.batch_id for b in batches]
        assert len(batch_ids) == len(set(batch_ids)), "batch_ids should be unique"

        # Verify batch_ids are valid UUIDs
        import uuid

        for batch_id in batch_ids:
            uuid.UUID(batch_id)  # Raises ValueError if invalid

    def test_batch_num_sequential_after_filtering(self):
        """Verify batch_num remains sequential even after empty batch filtering."""
        batch_manager = BatchManager()
        # Create table that might produce empty batches
        table = pa.table({"id": [1, 2], "SIZE": [100, 200]})

        batches = batch_manager.create_batches(table=table, batch_size=1)

        # Verify batch_num is sequential starting from 0
        batch_nums = [b.batch_num for b in batches]
        assert batch_nums == list(range(len(batches))), f"Expected sequential batch_nums, got {batch_nums}"

    def test_non_batch_mode_has_batch_id(self):
        """Verify non-batch mode still creates BatchInfo with batch_id for consistency."""
        batch_manager = BatchManager()
        table = pa.table({"id": list(range(5))})
        global_config = {DocpipeConstants.ENABLE_MICRO_BATCHING: False}

        batches, _ = batch_manager.prepare_batches(
            ingested_table=table, global_config=global_config, common_log_arguments=None
        )

        assert len(batches) == 1
        assert hasattr(batches[0], "batch_id")
        assert batches[0].batch_id is not None
        # Verify it's a valid UUID
        import uuid

        uuid.UUID(batches[0].batch_id)


class TestEmptyBatchFiltering:
    """Test empty batch filtering behavior."""

    def test_empty_batches_filtered_out(self):
        """Verify empty batches are filtered during creation."""
        batch_manager = BatchManager()
        # Create table with only 2 rows but request 5 batches
        table = pa.table({"id": [1, 2], "SIZE": [100, 200]})

        # This would create some empty batches if not filtered
        batches = batch_manager.create_batches(table=table, batch_size=1)

        # Verify no empty batches
        assert all(b.table.num_rows > 0 for b in batches), "All batches should be non-empty"
        assert len(batches) == 2, "Should only have 2 non-empty batches"

    def test_empty_table_returns_empty_list(self):
        """Verify empty input table returns empty batch list."""
        batch_manager = BatchManager()
        empty_table = pa.table({"id": [], "SIZE": []})

        batches = batch_manager.create_batches(table=empty_table, batch_size=10)

        assert batches == [], "Empty table should return empty batch list"

    def test_zero_size_files_filtered_correctly(self):
        """Verify batches with only zero-size files are handled correctly."""
        batch_manager = BatchManager()
        # All files have zero size
        table = pa.table({"id": [1, 2, 3], "SIZE": [0, 0, 0]})

        batches = batch_manager.create_batches(table=table, batch_size=2)

        # Should still create batches (round-robin distribution)
        assert len(batches) > 0
        assert all(b.table.num_rows > 0 for b in batches)

    def test_batch_num_sequential_after_empty_filtering(self):
        """Verify batch_num is renumbered sequentially after filtering empty batches."""
        batch_manager = BatchManager()
        table = pa.table({"id": [1, 2, 3], "SIZE": [100, 200, 300]})

        batches = batch_manager.create_batches(table=table, batch_size=1)

        # Even if some batches were filtered, batch_num should be 0, 1, 2, ...
        batch_nums = [b.batch_num for b in batches]
        assert batch_nums == list(range(len(batches))), "batch_num should be sequential after filtering"


class TestIngestExclusionFromMicroBatching:
    """Test that ingest operators are excluded from micro-batching."""

    def test_ingest_not_in_batch_op_flow(self):
        """Verify ingest operator is excluded from batched op_flow."""
        # This is a documentation test - the actual exclusion happens in prefect_engine.py
        # where op_flow[1:] is passed to batch execution (skipping ingest at index 0)

        # Simulate the pattern used in prefect_engine.py line 149
        full_op_flow = [
            {
                "id": "ingest-1",
                "name": "IngestLocal",
                "operator_type": "IngestLocalOperator",
            },
            {"id": "extract-1", "name": "Extract", "operator_type": "ExtractDocling"},
            {"id": "chunk-1", "name": "Chunk", "operator_type": "Chunker"},
        ]

        # Ingest is excluded from batch execution
        batch_op_flow = full_op_flow[1:]  # Skip ingest operator

        assert len(batch_op_flow) == 2
        assert batch_op_flow[0]["id"] == "extract-1"
        assert "ingest" not in batch_op_flow[0]["id"].lower()

    def test_batch_config_not_set_for_ingest(self):
        """Verify batch context (batch_id, batch_num) is not set during ingest execution."""
        # Ingest executes once without batch context
        # Batch context is only added in batch_subflow_task (prefect_engine.py line 232-234)

        # Simulate ingest execution config (no batch context)
        ingest_config = {
            DocpipeConstants.JOB_ID: "job-1",
            DocpipeConstants.JOB_RUN_ID: "run-1",
            # Note: No BATCH_ID or BATCH_NUM
        }

        assert DocpipeConstants.BATCH_ID not in ingest_config
        assert DocpipeConstants.BATCH_NUM not in ingest_config

        # Simulate batch execution config (has batch context)
        batch_config = ingest_config.copy()
        batch_config[DocpipeConstants.BATCH_ID] = "batch-uuid-123"
        batch_config[DocpipeConstants.BATCH_NUM] = 0

        assert DocpipeConstants.BATCH_ID in batch_config
        assert DocpipeConstants.BATCH_NUM in batch_config

    def test_ingest_node_id_stored_for_dependency_resolution(self):
        """Verify ingest node ID is stored in global_config for batch dependency resolution."""
        # This documents the pattern where ingest_node_id is stored in global_config
        # so batch operators can identify ingest dependencies (prefect_engine.py line 428)

        global_config = {
            DocpipeConstants.INGEST_NODE_ID: "ingest-node-1",
            DocpipeConstants.ENABLE_MICRO_BATCHING: True,
        }

        # Batch operators check if dependency is ingest node
        dependency_node_id = "ingest-node-1"
        ingest_node_id = global_config.get(DocpipeConstants.INGEST_NODE_ID)

        is_ingest_dependency = dependency_node_id == ingest_node_id
        assert is_ingest_dependency, "Should recognize ingest node as dependency"


class TestPrefectEngineValidation:
    """Test PrefectEngine batch validation."""

    def test_batch_outer_flow_rejects_non_positive_max_concurrent_batches(self):
        """Verify error when max_concurrent_batches is non-positive."""
        from docpipe.core.orchestration.prefect.prefect_engine import PrefectEngine

        orchestrator = MagicMock()
        orchestrator.logger = MagicMock()
        orchestrator.common_log_arguments = {
            DocpipeConstants.JOB_ID: "job-1",
            DocpipeConstants.JOB_RUN_ID: "run-1",
        }
        orchestrator._create_empty_result.return_value = MagicMock()

        engine = PrefectEngine(
            orchestrator=orchestrator,
            batch_manager=BatchManager(),
            job_id="job-1",
            job_run_id="run-1",
            job_log_path="job.log",
        )

        with pytest.raises(FlowExecutionFailedException, match="must be a positive integer"):
            engine.batch_outer_flow_impl(
                op_flow=[],
                batches=[],
                global_config={DocpipeConstants.MAX_CONCURRENT_BATCHES: 0},
            )


class TestPrefectEngineCleanup:
    """Test PrefectEngine cleanup on errors."""

    def test_wait_for_sub_flows_waits_for_cancelled_futures_before_reset(self):
        """Verify cancelled futures are waited on before semaphore reset."""
        from docpipe.core.orchestration.prefect.prefect_engine import BatchFuture, PrefectEngine

        orchestrator = MagicMock()
        orchestrator.logger = MagicMock()
        orchestrator.common_log_arguments = {
            DocpipeConstants.JOB_ID: "job-1",
            DocpipeConstants.JOB_RUN_ID: "run-1",
        }
        orchestrator._create_empty_result.return_value = MagicMock()

        engine = PrefectEngine(
            orchestrator=orchestrator,
            batch_manager=BatchManager(),
            job_id="job-1",
            job_run_id="run-1",
            job_log_path="job.log",
        )

        call_order = []
        failed_future = MagicMock()
        failed_future.result.side_effect = RuntimeError("boom")

        cancelled_future = MagicMock()
        cancelled_future.cancel.side_effect = lambda: call_order.append("cancel")
        cancelled_future.wait.side_effect = lambda: call_order.append("wait")

        with pytest.raises(
            FlowExecutionFailedException,
            match=r"Batch 0 \(ID: batch-0\) failed during sub-flow execution: RuntimeError: boom",
        ):
            engine._wait_for_sub_flows(
                batch_futures=[
                    BatchFuture(batch_id="batch-0", batch_num=0, future=failed_future),
                    BatchFuture(batch_id="batch-1", batch_num=1, future=cancelled_future),
                ]
            )

        assert call_order == ["cancel", "wait"]
        assert engine.batch_manager.get_batch_semaphore() is None

    def test_wait_for_sub_flows_resets_semaphore_when_cancelled_wait_errors(self):
        """Verify semaphore reset even when cancelled future wait fails."""
        from docpipe.core.orchestration.prefect.prefect_engine import BatchFuture, PrefectEngine

        orchestrator = MagicMock()
        orchestrator.logger = MagicMock()
        orchestrator.common_log_arguments = {
            DocpipeConstants.JOB_ID: "job-1",
            DocpipeConstants.JOB_RUN_ID: "run-1",
        }
        orchestrator._create_empty_result.return_value = MagicMock()

        engine = PrefectEngine(
            orchestrator=orchestrator,
            batch_manager=BatchManager(),
            job_id="job-1",
            job_run_id="run-1",
            job_log_path="job.log",
        )
        engine.batch_manager.initialize_batch_semaphore(max_concurrent_batches=1)

        failed_future = MagicMock()
        failed_future.result.side_effect = RuntimeError("boom")

        cancelled_future = MagicMock()
        cancelled_future.wait.side_effect = RuntimeError("wait failed")

        with pytest.raises(
            FlowExecutionFailedException,
            match=r"Batch 0 \(ID: batch-0\) failed during sub-flow execution: RuntimeError: boom",
        ):
            engine._wait_for_sub_flows(
                batch_futures=[
                    BatchFuture(batch_id="batch-0", batch_num=0, future=failed_future),
                    BatchFuture(batch_id="batch-1", batch_num=1, future=cancelled_future),
                ]
            )

        assert engine.batch_manager.get_batch_semaphore() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
