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

from common.constants.constants import DatasiftConstants
from common.exceptions.datasift_exceptions import FlowExecutionFailedException
from core.orchestrator.batch_manager import BatchManager


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
                    max_concurrent_observed = max(
                        max_concurrent_observed, concurrent_count
                    )

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

        assert semaphore.acquire(blocking=False), (
            "Semaphore should be released after failure"
        )
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

        assert all(stage == "complete" for stage in batch_stages.values()), (
            "All batches should complete"
        )

        # Verify each batch went through all stages in order
        expected_order = ["ingest", "extract", "chunk", "complete"]
        for batch_num in range(3):
            batch_stages_list = [
                stage for batch, stage in stage_history if batch == batch_num
            ]
            assert batch_stages_list == expected_order, (
                f"Batch {batch_num} stages out of order: {batch_stages_list}"
            )


class TestBatchConfiguration:
    """Test batch configuration and preparation."""

    def test_configure_batching_enabled(self):
        """Verify batching configuration when enabled."""
        batch_manager = BatchManager()
        global_config = {
            DatasiftConstants.ENABLE_MICRO_BATCHING: True,
            DatasiftConstants.MICRO_BATCH_SIZE: 100,
        }

        enabled, size = batch_manager.configure_batching(global_config=global_config)

        assert enabled is True
        assert size == 100

    def test_configure_batching_disabled(self):
        """Verify batching configuration when disabled."""
        batch_manager = BatchManager()
        global_config = {DatasiftConstants.ENABLE_MICRO_BATCHING: False}

        enabled, size = batch_manager.configure_batching(global_config=global_config)

        assert enabled is False
        assert size == DatasiftConstants.DEFAULT_MICRO_BATCH_SIZE

    def test_configure_batching_default(self):
        """Verify batching configuration with defaults."""
        batch_manager = BatchManager()
        global_config = {}

        enabled, size = batch_manager.configure_batching(global_config=global_config)

        assert enabled is False
        assert size == DatasiftConstants.DEFAULT_MICRO_BATCH_SIZE


class TestBatchCreation:
    """Test batch creation and splitting."""

    def test_create_batches_single_batch(self):
        """Verify creating batches when table fits in one batch."""
        batch_manager = BatchManager()
        table = pa.table({"id": [1, 2, 3], "value": ["a", "b", "c"]})

        batches = batch_manager.create_batches(table=table, batch_size=10)

        assert len(batches) == 1
        assert batches[0].num_rows == 3
        assert batches[0].column_names == ["id", "value"]

    def test_create_batches_multiple_batches(self):
        """Verify creating multiple batches from larger table."""
        batch_manager = BatchManager()
        table = pa.table(
            {"id": list(range(25)), "value": [f"val_{i}" for i in range(25)]}
        )

        batches = batch_manager.create_batches(table=table, batch_size=10)

        assert len(batches) == 3
        assert batches[0].num_rows == 10
        assert batches[1].num_rows == 10
        assert batches[2].num_rows == 5

        # Verify all data is preserved
        total_rows = sum(b.num_rows for b in batches)
        assert total_rows == 25

    def test_create_batches_exact_multiple(self):
        """Verify creating batches when rows are exact multiple of batch size."""
        batch_manager = BatchManager()
        table = pa.table({"id": list(range(20))})

        batches = batch_manager.create_batches(table=table, batch_size=10)

        assert len(batches) == 2
        assert all(b.num_rows == 10 for b in batches)


class TestBatchPreparation:
    """Test batch preparation with configuration."""

    def test_prepare_batches_batch_mode_enabled(self):
        """Verify batch preparation in batch mode."""
        batch_manager = BatchManager()
        table = pa.table({"id": list(range(25))})
        global_config = {
            DatasiftConstants.ENABLE_MICRO_BATCHING: True,
            DatasiftConstants.MICRO_BATCH_SIZE: 10,
        }

        batches, updated_config = batch_manager.prepare_batches(
            ingested_table=table,
            global_config=global_config,
            common_log_arguments={"job_id": "test"},
        )

        assert len(batches) == 3
        assert updated_config[DatasiftConstants.BATCH_COUNT] == 3
        assert DatasiftConstants.ENABLE_MICRO_BATCHING in updated_config

    def test_prepare_batches_non_batch_mode(self):
        """Verify batch preparation in non-batch mode."""
        batch_manager = BatchManager()
        table = pa.table({"id": list(range(25))})
        global_config = {DatasiftConstants.ENABLE_MICRO_BATCHING: False}

        batches, updated_config = batch_manager.prepare_batches(
            ingested_table=table,
            global_config=global_config,
            common_log_arguments={"job_id": "test"},
        )

        assert len(batches) == 1
        assert batches[0].num_rows == 25
        assert DatasiftConstants.BATCH_COUNT not in updated_config

    def test_prepare_batches_raises_when_batch_size_missing(self):
        """Verify error when batch size is missing in batch mode."""
        batch_manager = BatchManager()
        table = pa.table({"id": [1, 2]})

        with pytest.raises(
            FlowExecutionFailedException, match="micro_batch_size must be set"
        ):
            batch_manager.prepare_batches(
                ingested_table=table,
                global_config={
                    DatasiftConstants.ENABLE_MICRO_BATCHING: True,
                    DatasiftConstants.MICRO_BATCH_SIZE: None,
                },
                common_log_arguments=None,
            )


class TestBatchDataAccess:
    """Test DataAccess creation for batches."""

    @patch("core.orchestrator.batch_manager.DataAccessFactory")
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob


class TestPrefectEngineValidation:
    """Test PrefectEngine batch validation."""

    def test_batch_outer_flow_rejects_non_positive_max_concurrent_batches(self):
        """Verify error when max_concurrent_batches is non-positive."""
        from core.orchestrator.prefect.prefect_engine import PrefectEngine

        orchestrator = MagicMock()
        orchestrator.logger = MagicMock()
        orchestrator.common_log_arguments = {
            DatasiftConstants.JOB_ID: "job-1",
            DatasiftConstants.JOB_RUN_ID: "run-1",
        }
        orchestrator._create_empty_result.return_value = MagicMock()

        engine = PrefectEngine(
            orchestrator=orchestrator,
            batch_manager=BatchManager(),
            job_id="job-1",
            job_run_id="run-1",
            job_log_path="job.log",
        )

        with pytest.raises(
            FlowExecutionFailedException, match="must be a positive integer"
        ):
            engine.batch_outer_flow_impl(
                op_flow=[],
                batches=[],
                global_config={DatasiftConstants.MAX_CONCURRENT_BATCHES: 0},
            )


class TestPrefectEngineCleanup:
    """Test PrefectEngine cleanup on errors."""

    def test_wait_for_sub_flows_waits_for_cancelled_futures_before_reset(self):
        """Verify cancelled futures are waited on before semaphore reset."""
        from core.orchestrator.prefect.prefect_engine import PrefectEngine

        orchestrator = MagicMock()
        orchestrator.logger = MagicMock()
        orchestrator.common_log_arguments = {
            DatasiftConstants.JOB_ID: "job-1",
            DatasiftConstants.JOB_RUN_ID: "run-1",
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
            match="Batch 0 failed during sub-flow execution: boom",
        ):
            engine._wait_for_sub_flows(
                batch_futures=[
                    (0, failed_future),
                    (1, cancelled_future),
                ]
            )

        assert call_order == ["cancel", "wait"]
        assert engine.batch_manager.get_batch_semaphore() is None

    def test_wait_for_sub_flows_resets_semaphore_when_cancelled_wait_errors(self):
        """Verify semaphore reset even when cancelled future wait fails."""
        from core.orchestrator.prefect.prefect_engine import PrefectEngine

        orchestrator = MagicMock()
        orchestrator.logger = MagicMock()
        orchestrator.common_log_arguments = {
            DatasiftConstants.JOB_ID: "job-1",
            DatasiftConstants.JOB_RUN_ID: "run-1",
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
            match="Batch 0 failed during sub-flow execution: boom",
        ):
            engine._wait_for_sub_flows(
                batch_futures=[
                    (0, failed_future),
                    (1, cancelled_future),
                ]
            )

        assert engine.batch_manager.get_batch_semaphore() is None
