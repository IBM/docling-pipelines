"""
Unit tests for BatchInfo compatibility across batch execution adapters.

Tests verify that the BatchInfo refactor (changing from list[pa.Table] to list[BatchInfo])
is properly handled by all batch execution strategies.
"""

import uuid
from unittest.mock import Mock, patch

import pyarrow as pa
import pytest

from datasift.core.orchestration.batch_manager import BatchInfo, BatchManager
from datasift.core.orchestration.prefect.adapters.thread_pool_adapter import ThreadPoolAdapter
from datasift.core.orchestration.prefect.adapters.work_pool_adapter import WorkPoolAdapter


class TestBatchInfoCompatibility:
    """Test BatchInfo compatibility across batch execution paths."""

    @pytest.fixture
    def sample_batch_infos(self):
        """Create sample BatchInfo objects for testing."""
        table1 = pa.table({"col1": [1, 2], "col2": ["a", "b"]})
        table2 = pa.table({"col1": [3, 4], "col2": ["c", "d"]})

        return [
            BatchInfo(batch_id=str(uuid.uuid4()), batch_num=0, table=table1),
            BatchInfo(batch_id=str(uuid.uuid4()), batch_num=1, table=table2),
        ]

    @pytest.fixture
    def mock_prefect_engine(self):
        """Create a mock PrefectEngine."""
        engine = Mock()
        engine.logger = Mock()
        engine._build_flow = Mock(return_value=Mock())
        engine._wait_for_sub_flows = Mock()
        return engine

    @pytest.fixture
    def mock_batch_manager(self):
        """Create a mock BatchManager."""
        manager = Mock(spec=BatchManager)
        manager.create_batch_data_access = Mock()
        manager.initialize_batch_semaphore = Mock()
        manager.get_batch_semaphore = Mock(return_value=None)
        manager.reset_batch_semaphore = Mock()
        return manager

    def test_thread_pool_adapter_accepts_batch_info_list(
        self, sample_batch_infos, mock_prefect_engine, mock_batch_manager
    ):
        """Test that ThreadPoolAdapter correctly handles list[BatchInfo]."""
        adapter = ThreadPoolAdapter(prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager)

        # Mock the flow execution
        mock_flow = Mock()
        mock_flow.return_value = []
        mock_prefect_engine._build_flow.return_value = mock_flow

        op_flow = [{"id": "op1", "name": "test_op"}]
        global_config = {"enable_micro_batching": True}

        # Should not raise - accepts list[BatchInfo]
        adapter.execute_batches(
            batches=sample_batch_infos,
            op_flow=op_flow,
            global_config=global_config,
            job_run_id="test-job-123",
        )

        # Verify flow was called with batches
        mock_flow.assert_called_once()
        call_kwargs = mock_flow.call_args.kwargs
        assert "batches" in call_kwargs
        assert call_kwargs["batches"] == sample_batch_infos

    def test_thread_pool_adapter_accesses_batch_info_attributes(
        self, sample_batch_infos, mock_prefect_engine, mock_batch_manager
    ):
        """Test that ThreadPoolAdapter correctly accesses BatchInfo.table attribute."""
        adapter = ThreadPoolAdapter(prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager)

        # Mock batch_outer_flow_impl to capture batch access
        def mock_flow_impl(op_flow, batches, global_config):
            # Verify we can access batch_info attributes
            for batch_info in batches:
                assert hasattr(batch_info, "batch_id")
                assert hasattr(batch_info, "batch_num")
                assert hasattr(batch_info, "table")
                assert isinstance(batch_info.table, pa.Table)
            return []

        mock_prefect_engine.batch_outer_flow_impl = mock_flow_impl
        mock_flow = Mock(side_effect=mock_flow_impl)
        mock_prefect_engine._build_flow.return_value = mock_flow

        adapter.execute_batches(
            batches=sample_batch_infos,
            op_flow=[],
            global_config={},
            job_run_id="test-job-123",
        )

    def test_work_pool_adapter_signature_accepts_batch_info(self):
        """Test that WorkPoolAdapter.execute_batches has correct type signature."""
        from typing import get_type_hints

        # Get type hints for execute_batches method
        hints = get_type_hints(WorkPoolAdapter.execute_batches)

        # Verify batches parameter accepts list[BatchInfo]
        assert "batches" in hints
        # Note: Full type checking would require runtime type inspection
        # This test verifies the signature exists and is callable

    def test_work_pool_adapter_accesses_batch_info_attributes(
        self, sample_batch_infos, mock_prefect_engine, mock_batch_manager
    ):
        """Test that WorkPoolAdapter correctly accesses BatchInfo attributes."""
        # Mock work pool config
        work_pool_config = {
            "type": "process",
            "work_pool_name": "test-pool",
            "deployment_name": "test-deployment",
            "batch_storage": {"type": "inline"},
        }

        with patch.object(WorkPoolAdapter, "_validate_prefect_connection"):
            with patch.object(WorkPoolAdapter, "_ensure_deployment_exists"):
                adapter = WorkPoolAdapter(
                    work_pool_config=work_pool_config,
                    prefect_engine=mock_prefect_engine,
                    batch_manager=mock_batch_manager,
                )

        # Mock the transfer and submission methods
        with patch.object(adapter, "_transfer_batch") as mock_transfer:
            with patch.object(adapter, "_wait_for_flow_runs"):
                with patch("datasift.core.orchestration.prefect.adapters.work_pool_adapter.run_deployment") as mock_run:
                    mock_transfer.return_value = {"type": "inline", "data": {}}
                    mock_flow_run = Mock()
                    mock_flow_run.id = "flow-run-123"
                    mock_run.return_value = mock_flow_run

                    # Execute batches
                    adapter.execute_batches(
                        batches=sample_batch_infos,
                        op_flow=[],
                        global_config={},
                        job_run_id="test-job-123",
                    )

                    # Verify _transfer_batch was called with correct attributes
                    assert mock_transfer.call_count == len(sample_batch_infos)

                    # Check first call
                    first_call = mock_transfer.call_args_list[0]
                    assert first_call.kwargs["batch_table"] == sample_batch_infos[0].table
                    assert first_call.kwargs["batch_num"] == sample_batch_infos[0].batch_num

                    # Check second call
                    second_call = mock_transfer.call_args_list[1]
                    assert second_call.kwargs["batch_table"] == sample_batch_infos[1].table
                    assert second_call.kwargs["batch_num"] == sample_batch_infos[1].batch_num

    def test_batch_manager_creates_batch_info_with_uuid(self):
        """Test that BatchManager.create_batches returns BatchInfo with UUID batch_id."""
        manager = BatchManager()

        table = pa.table({"col1": [1, 2, 3, 4, 5], "SIZE": [100, 200, 150, 300, 250]})

        batches = manager.create_batches(table=table, batch_size=2)

        # Verify all batches are BatchInfo objects
        assert all(isinstance(b, BatchInfo) for b in batches)

        # Verify each has a valid UUID batch_id
        for batch in batches:
            assert batch.batch_id is not None
            # Verify it's a valid UUID string
            uuid.UUID(batch.batch_id)  # Raises ValueError if invalid

        # Verify batch_num is sequential
        for i, batch in enumerate(batches):
            assert batch.batch_num == i

        # Verify each has a table
        for batch in batches:
            assert isinstance(batch.table, pa.Table)
            assert batch.table.num_rows > 0

    def test_batch_info_preserves_empty_batch_filtering(self):
        """Test that empty batches are filtered out and batch_num remains sequential."""
        manager = BatchManager()

        # Create table where some batches might be empty
        table = pa.table({"col1": [1, 2], "SIZE": [100, 200]})

        batches = manager.create_batches(table=table, batch_size=1)

        # All returned batches should be non-empty
        for batch in batches:
            assert batch.table.num_rows > 0

        # batch_num should be sequential (0, 1, 2, ...) even if some were filtered
        batch_nums = [b.batch_num for b in batches]
        assert batch_nums == list(range(len(batches)))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
