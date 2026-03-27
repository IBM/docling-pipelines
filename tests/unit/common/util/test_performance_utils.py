"""
Unit tests for performance utilities.
Tests for memory tracking and performance monitoring.
"""

import os
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

from common.util.infrastructure.performance import (
    cleanup_pyarrow_buffers,
    get_process_memory_mb,
    get_pyarrow_table_size_mb,
    log_elapsed_time,
    log_memory_usage,
)


class TestGetPyarrowTableSizeMb:
    """Test PyArrow table size calculation."""

    def test_get_size_simple_table(self):
        """Test getting size of a simple table."""
        table = pa.table(
            {"id": [1, 2, 3, 4, 5], "name": ["Alice", "Bob", "Charlie", "David", "Eve"]}
        )

        size = get_pyarrow_table_size_mb(table)

        assert size > 0
        assert isinstance(size, float)

    def test_get_size_none_table(self):
        """Test that None table returns 0."""
        size = get_pyarrow_table_size_mb(None)
        assert size == 0.0

    def test_get_size_empty_table(self):
        """Test getting size of empty table."""
        empty_table = pa.table(
            {
                "id": pa.array([], type=pa.int64()),
                "name": pa.array([], type=pa.string()),
            }
        )

        size = get_pyarrow_table_size_mb(empty_table)

        assert size >= 0
        assert isinstance(size, float)

    def test_get_size_large_table(self):
        """Test getting size of large table."""
        large_table = pa.table(
            {"id": list(range(10000)), "value": [f"value_{i}" for i in range(10000)]}
        )

        size = get_pyarrow_table_size_mb(large_table)

        assert size > 0
        # Large table should have measurable size
        assert size > 0.01

    def test_get_size_with_spark_runtime(self):
        """Test size calculation in Spark runtime mode."""
        table = pa.table({"id": [1, 2, 3]})

        with patch.dict(os.environ, {"IS_SPARK_RUNTIME": "TRUE"}):
            size = get_pyarrow_table_size_mb(table)
            # In Spark mode, returns minimal size
            assert size > 0

    def test_get_size_with_complex_types(self):
        """Test getting size of table with complex types."""
        complex_table = pa.table(
            {
                "id": [1, 2, 3],
                "list_col": [[1, 2, 3], [4, 5], [6, 7, 8, 9]],
                "struct_col": [
                    {"a": 1, "b": "x"},
                    {"a": 2, "b": "y"},
                    {"a": 3, "b": "z"},
                ],
            }
        )

        size = get_pyarrow_table_size_mb(complex_table)

        assert size > 0
        assert isinstance(size, float)

    def test_get_size_fallback_calculation(self):
        """Test fallback size calculation when nbytes not available."""
        table = pa.table({"id": [1, 2, 3]})

        # Mock nbytes to raise exception
        with patch.object(pa.Table, "nbytes", side_effect=AttributeError):
            size = get_pyarrow_table_size_mb(table)
            # Should use fallback calculation
            assert size >= 0


class TestGetProcessMemoryMb:
    """Test process memory tracking."""

    def test_get_process_memory_returns_dict(self):
        """Test that function returns a dictionary."""
        memory = get_process_memory_mb()

        assert isinstance(memory, dict)

    def test_get_process_memory_has_required_keys(self):
        """Test that memory dict has all required keys."""
        memory = get_process_memory_mb()

        required_keys = ["rss_mb", "vms_mb", "available_mb", "total_mb", "used_percent"]
        for key in required_keys:
            assert key in memory

    def test_get_process_memory_values_are_positive(self):
        """Test that memory values are positive numbers."""
        memory = get_process_memory_mb()

        assert memory["rss_mb"] > 0
        assert memory["vms_mb"] > 0
        assert memory["available_mb"] >= 0
        assert memory["total_mb"] > 0
        assert 0 <= memory["used_percent"] <= 100

    def test_get_process_memory_rss_less_than_total(self):
        """Test that RSS is less than total memory."""
        memory = get_process_memory_mb()

        assert memory["rss_mb"] <= memory["total_mb"]

    def test_get_process_memory_values_are_rounded(self):
        """Test that RSS and VMS values are rounded to 2 decimals."""
        memory = get_process_memory_mb()

        # Check that values are rounded
        assert isinstance(memory["rss_mb"], float)
        assert isinstance(memory["vms_mb"], float)


class TestLogElapsedTime:
    """Test elapsed time logging."""

    @pytest.fixture
    def mock_session_info(self):
        """Mock session info with track_perf enabled."""
        with patch("common.util.infrastructure.performance.get_session_info") as mock:
            session_info = MagicMock()
            session_info.track_perf = True
            mock.return_value = session_info
            yield mock

    @pytest.fixture
    def mock_session_info_disabled(self):
        """Mock session info with track_perf disabled."""
        with patch("common.util.infrastructure.performance.get_session_info") as mock:
            session_info = MagicMock()
            session_info.track_perf = False
            mock.return_value = session_info
            yield mock

    def test_log_elapsed_time_with_operator(self, mock_session_info):
        """Test logging elapsed time with operator name."""
        with patch("common.util.infrastructure.performance.logger") as mock_logger:
            with patch(
                "common.util.infrastructure.performance.get_current_timestamp"
            ) as mock_time:
                mock_time.return_value = 100
                start_time = 90

                log_elapsed_time(start_time=start_time, operator="TestOperator")

                # Should log the elapsed time
                assert mock_logger.info.called

    def test_log_elapsed_time_with_actions(self, mock_session_info):
        """Test logging elapsed time with actions."""
        with patch("common.util.infrastructure.performance.logger") as mock_logger:
            with patch(
                "common.util.infrastructure.performance.get_current_timestamp"
            ) as mock_time:
                mock_time.return_value = 100
                start_time = 90

                log_elapsed_time(
                    start_time=start_time,
                    operator="TestOperator",
                    actions=["read", "process", "write"],
                )

                assert mock_logger.info.called

    def test_log_elapsed_time_disabled(self, mock_session_info_disabled):
        """Test that logging is skipped when track_perf is disabled."""
        with patch("common.util.infrastructure.performance.logger") as mock_logger:
            log_elapsed_time(start_time=90, operator="TestOperator")

            # Should not log when disabled
            assert not mock_logger.info.called

    def test_log_elapsed_time_without_operator(self, mock_session_info):
        """Test logging elapsed time without operator name."""
        with patch("common.util.infrastructure.performance.logger") as mock_logger:
            with patch(
                "common.util.infrastructure.performance.get_current_timestamp"
            ) as mock_time:
                mock_time.return_value = 100

                log_elapsed_time(start_time=90)

                assert mock_logger.info.called


class TestLogMemoryUsage:
    """Test memory usage logging."""

    @pytest.fixture
    def mock_session_info(self):
        """Mock session info with track_perf enabled."""
        with patch("common.util.infrastructure.performance.get_session_info") as mock:
            session_info = MagicMock()
            session_info.track_perf = True
            mock.return_value = session_info
            yield mock

    @pytest.fixture
    def mock_session_info_disabled(self):
        """Mock session info with track_perf disabled."""
        with patch("common.util.infrastructure.performance.get_session_info") as mock:
            session_info = MagicMock()
            session_info.track_perf = False
            mock.return_value = session_info
            yield mock

    def test_log_memory_usage_with_single_table(self, mock_session_info):
        """Test logging memory usage with single table."""
        table = pa.table({"id": [1, 2, 3]})
        mock_logger = MagicMock()

        log_memory_usage(
            operator_name="TestOperator",
            phase="processing",
            table=table,
            logger=mock_logger,
        )

        assert mock_logger.info.called

    def test_log_memory_usage_with_list_of_tables(self, mock_session_info):
        """Test logging memory usage with list of tables."""
        tables = [
            pa.table({"id": [1, 2, 3]}),
            pa.table({"id": [4, 5, 6]}),
            pa.table({"id": [7, 8, 9]}),
        ]
        mock_logger = MagicMock()

        log_memory_usage(
            operator_name="TestOperator",
            phase="processing",
            table=tables,
            logger=mock_logger,
        )

        assert mock_logger.info.called

    def test_log_memory_usage_disabled(self, mock_session_info_disabled):
        """Test that logging is skipped when track_perf is disabled."""
        table = pa.table({"id": [1, 2, 3]})
        mock_logger = MagicMock()

        log_memory_usage(
            operator_name="TestOperator",
            phase="processing",
            table=table,
            logger=mock_logger,
        )

        # Should not log when disabled
        assert not mock_logger.info.called

    def test_log_memory_usage_without_table(self, mock_session_info):
        """Test that logging is skipped when table is None."""
        mock_logger = MagicMock()

        log_memory_usage(
            operator_name="TestOperator",
            phase="processing",
            table=None,
            logger=mock_logger,
        )

        # Should not log without table
        assert not mock_logger.info.called

    def test_log_memory_usage_with_extra_context(self, mock_session_info):
        """Test logging memory usage with extra context."""
        table = pa.table({"id": [1, 2, 3]})
        mock_logger = MagicMock()
        extra = {"custom_field": "custom_value"}

        log_memory_usage(
            operator_name="TestOperator",
            phase="processing",
            table=table,
            extra=extra,
            logger=mock_logger,
        )

        assert mock_logger.info.called

    def test_log_memory_usage_without_logger(self, mock_session_info):
        """Test logging memory usage without providing logger."""
        table = pa.table({"id": [1, 2, 3]})

        # Should use default logger
        log_memory_usage(operator_name="TestOperator", phase="processing", table=table)


class TestCleanupPyarrowBuffers:
    """Test PyArrow buffer cleanup."""

    @pytest.fixture
    def mock_session_info(self):
        """Mock session info with track_perf enabled."""
        with patch("common.util.infrastructure.performance.get_session_info") as mock:
            session_info = MagicMock()
            session_info.track_perf = True
            mock.return_value = session_info
            yield mock

    @pytest.fixture
    def mock_session_info_disabled(self):
        """Mock session info with track_perf disabled."""
        with patch("common.util.infrastructure.performance.get_session_info") as mock:
            session_info = MagicMock()
            session_info.track_perf = False
            mock.return_value = session_info
            yield mock

    def test_cleanup_pyarrow_buffers(self, mock_session_info):
        """Test cleanup of PyArrow buffers."""
        table = pa.table({"id": [1, 2, 3]})
        mock_logger = MagicMock()

        cleanup_pyarrow_buffers(
            operator_name="TestOperator",
            phase="cleanup",
            table=table,
            extra=None,
            logger=mock_logger,
        )

        # Should log memory usage
        assert mock_logger.info.called

    def test_cleanup_pyarrow_buffers_disabled(self, mock_session_info_disabled):
        """Test that cleanup is skipped when track_perf is disabled."""
        table = pa.table({"id": [1, 2, 3]})
        mock_logger = MagicMock()

        cleanup_pyarrow_buffers(
            operator_name="TestOperator",
            phase="cleanup",
            table=table,
            extra=None,
            logger=mock_logger,
        )

        # Should not log when disabled
        assert not mock_logger.info.called

    def test_cleanup_pyarrow_buffers_with_list(self, mock_session_info):
        """Test cleanup with list of tables."""
        tables = [pa.table({"id": [1, 2, 3]}), pa.table({"id": [4, 5, 6]})]
        mock_logger = MagicMock()

        cleanup_pyarrow_buffers(
            operator_name="TestOperator",
            phase="cleanup",
            table=tables,
            extra=None,
            logger=mock_logger,
        )

        assert mock_logger.info.called


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_get_pyarrow_table_size_with_single_column(self):
        """Test size calculation with single column table."""
        table = pa.table({"id": [1, 2, 3, 4, 5]})
        size = get_pyarrow_table_size_mb(table)
        assert size > 0

    def test_get_pyarrow_table_size_with_many_columns(self):
        """Test size calculation with many columns."""
        data = {f"col_{i}": list(range(100)) for i in range(50)}
        table = pa.table(data)
        size = get_pyarrow_table_size_mb(table)
        assert size > 0

    def test_log_memory_usage_with_empty_table(self):
        """Test logging memory usage with empty table."""
        with patch("common.util.infrastructure.performance.get_session_info") as mock:
            session_info = MagicMock()
            session_info.track_perf = True
            mock.return_value = session_info

            empty_table = pa.table({"id": pa.array([], type=pa.int64())})
            mock_logger = MagicMock()

            log_memory_usage(
                operator_name="TestOperator",
                phase="processing",
                table=empty_table,
                logger=mock_logger,
            )

            assert mock_logger.info.called

    def test_log_elapsed_time_with_zero_duration(self):
        """Test logging elapsed time with zero duration."""
        with patch("common.util.infrastructure.performance.get_session_info") as mock:
            session_info = MagicMock()
            session_info.track_perf = True
            mock.return_value = session_info

            with patch("common.util.infrastructure.performance.logger") as mock_logger:
                with patch(
                    "common.util.infrastructure.performance.get_current_timestamp"
                ) as mock_time:
                    mock_time.return_value = 100

                    log_elapsed_time(start_time=100, operator="TestOperator")

                    assert mock_logger.info.called


# Made with Bob
