"""Unit tests for AbstractOrchestrator helper methods.

Methods under test:
- _handle_node_failure
- _check_and_upload_deleted_rows
- _mark_pending_batches_as_skipped
- _handle_skipped_execution
- evaluate_execution_skip
- _collect_non_recoverable_docs
- _merge_non_recoverable_docs
- _reset_non_recoverable_docs_for_batch

Uses PythonOrchestrator as the concrete subclass (it adds no logic of its own,
so it is a transparent proxy to the abstract methods under test).
"""

from unittest.mock import MagicMock, patch

import pyarrow as pa

from docpipe.core.constants.constants import DocpipeConstants, ExecutionStatus, Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import OperatorCategory
from docpipe.core.orchestration.ports.flow_engine import ExecuteStepResults
from docpipe.core.orchestration.python.python_orchestrator import PythonOrchestrator

JOB_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
JOB_RUN_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

_OP_DEF = {
    OperatorConstants.Columns.ID: "node-op",
    OperatorConstants.Columns.NAME: "some_operator",
    OperatorConstants.Misc.OPERATOR: "chunker",
}


def _make_orchestrator() -> PythonOrchestrator:
    """Return a minimally wired PythonOrchestrator suitable for unit tests."""
    orch = PythonOrchestrator()
    orch.job_id = JOB_ID
    orch.job_run_id = JOB_RUN_ID
    orch.common_log_arguments = {
        DocpipeConstants.JOB_ID: JOB_ID,
        DocpipeConstants.JOB_RUN_ID: JOB_RUN_ID,
    }
    orch.flow_execution_event_handler = MagicMock()
    orch.job_stats_service = None
    return orch


# ---------------------------------------------------------------------------
# _handle_node_failure
# ---------------------------------------------------------------------------


class TestHandleNodeFailure:
    """_handle_node_failure sets job_status, captures the error message, and
    delegates node-failure reporting to the event handler."""

    def test_sets_job_status_to_failing_in_non_batch_mode(self):
        orch = _make_orchestrator()
        orch.job_status = ExecutionStatus.RUNNING

        global_config = {DocpipeConstants.ENABLE_MICRO_BATCHING: False}
        orch._handle_node_failure(e=RuntimeError("failed"), op_def=_OP_DEF, global_config=global_config)

        assert orch.job_status == ExecutionStatus.FAILING

    def test_captures_error_message(self):
        orch = _make_orchestrator()
        global_config = {DocpipeConstants.ENABLE_MICRO_BATCHING: False}
        orch._handle_node_failure(e=RuntimeError("something went wrong"), op_def=_OP_DEF, global_config=global_config)

        assert orch.message == "something went wrong"

    def test_does_not_set_failing_when_batching_and_continue_on_failure(self):
        """In continue_on_batch_failure mode the job_status must stay RUNNING."""
        orch = _make_orchestrator()
        orch.job_status = ExecutionStatus.RUNNING

        global_config = {
            DocpipeConstants.ENABLE_MICRO_BATCHING: True,
            DocpipeConstants.CONTINUE_ON_BATCH_FAILURE: True,
        }
        orch._handle_node_failure(e=RuntimeError("batch error"), op_def=_OP_DEF, global_config=global_config)

        assert orch.job_status == ExecutionStatus.RUNNING

    def test_sets_failing_when_batching_but_continue_off(self):
        """Batching enabled but continue_on_batch_failure=False → status becomes FAILING."""
        orch = _make_orchestrator()
        orch.job_status = ExecutionStatus.RUNNING

        global_config = {
            DocpipeConstants.ENABLE_MICRO_BATCHING: True,
            DocpipeConstants.CONTINUE_ON_BATCH_FAILURE: False,
        }
        orch._handle_node_failure(e=RuntimeError("err"), op_def=_OP_DEF, global_config=global_config)

        assert orch.job_status == ExecutionStatus.FAILING

    def test_continue_flag_defaults_to_false_when_absent(self):
        """CONTINUE_ON_BATCH_FAILURE_DEFAULT is False, so absent key → status FAILING."""
        orch = _make_orchestrator()
        orch.job_status = ExecutionStatus.RUNNING

        global_config = {DocpipeConstants.ENABLE_MICRO_BATCHING: True}  # no CONTINUE_ON_BATCH_FAILURE key
        orch._handle_node_failure(e=RuntimeError("err"), op_def=_OP_DEF, global_config=global_config)

        assert orch.job_status == ExecutionStatus.FAILING

    def test_delegates_to_event_handler(self):
        """after_node_failure must be called with the correct node id and name."""
        orch = _make_orchestrator()
        exc = ValueError("extraction failed")
        global_config = {DocpipeConstants.ENABLE_MICRO_BATCHING: False}

        orch._handle_node_failure(e=exc, op_def=_OP_DEF, global_config=global_config)

        orch.flow_execution_event_handler.after_node_failure.assert_called_once_with(
            node_id=_OP_DEF[OperatorConstants.Columns.ID],
            node_name=_OP_DEF[OperatorConstants.Columns.NAME],
            global_config=global_config,
            e=exc,
        )


# ---------------------------------------------------------------------------
# _check_and_upload_deleted_rows
# ---------------------------------------------------------------------------


class TestCheckAndUploadDeletedRows:
    """_check_and_upload_deleted_rows writes queued deleted-row tables to parquet
    and is a no-op when the queue is empty or job identifiers are missing."""

    def _make_orch_with_rows(self, rows: list[pa.Table]) -> PythonOrchestrator:
        orch = _make_orchestrator()
        for row in rows:
            orch.deleted_rows_list.put(row)
        return orch

    def test_no_op_when_queue_is_empty(self):
        orch = _make_orchestrator()
        # Should not raise and must not call any parquet handler
        with patch.object(orch, "get_parquet_table_handler_impl") as mock_handler_factory:
            orch._check_and_upload_deleted_rows()
        mock_handler_factory.assert_not_called()

    def test_no_op_when_job_id_is_none(self):
        orch = _make_orchestrator()
        orch.job_id = None
        orch.deleted_rows_list.put(pa.table({"id": ["doc1"]}))

        with patch.object(orch, "get_parquet_table_handler_impl") as mock_handler_factory:
            orch._check_and_upload_deleted_rows()

        mock_handler_factory.assert_not_called()

    def test_no_op_when_job_run_id_is_none(self):
        orch = _make_orchestrator()
        orch.job_run_id = None
        orch.deleted_rows_list.put(pa.table({"id": ["doc1"]}))

        with patch.object(orch, "get_parquet_table_handler_impl") as mock_handler_factory:
            orch._check_and_upload_deleted_rows()

        mock_handler_factory.assert_not_called()

    def test_saves_combined_table_to_parquet(self):
        orch = _make_orchestrator()
        table = pa.table({"id": ["doc1", "doc2"]})
        orch.deleted_rows_list.put(table)

        mock_handler = MagicMock()
        expected_path = "/some/path/deleted.parquet"

        with (
            patch.object(orch, "get_parquet_table_handler_impl", return_value=mock_handler),
            patch.object(orch, "get_deleted_rows_table_path_impl", return_value=expected_path),
        ):
            orch._check_and_upload_deleted_rows()

        mock_handler.delete_file.assert_called_once_with(path=expected_path)
        mock_handler.save_table.assert_called_once()
        save_kwargs = mock_handler.save_table.call_args.kwargs
        assert save_kwargs["path"] == expected_path
        assert save_kwargs["table"].num_rows == 2

    def test_multiple_queued_tables_are_combined(self):
        orch = _make_orchestrator()
        orch.deleted_rows_list.put(pa.table({"id": ["a"]}))
        orch.deleted_rows_list.put(pa.table({"id": ["b", "c"]}))

        mock_handler = MagicMock()
        with (
            patch.object(orch, "get_parquet_table_handler_impl", return_value=mock_handler),
            patch.object(orch, "get_deleted_rows_table_path_impl", return_value="/path/del.parquet"),
        ):
            orch._check_and_upload_deleted_rows()

        saved_table = mock_handler.save_table.call_args.kwargs["table"]
        assert saved_table.num_rows == 3

    def test_exception_during_save_is_swallowed(self):
        """Errors during parquet save must be logged as warnings, not raised."""
        orch = _make_orchestrator()
        orch.deleted_rows_list.put(pa.table({"id": ["doc1"]}))

        mock_handler = MagicMock()
        mock_handler.save_table.side_effect = OSError("disk full")

        with (
            patch.object(orch, "get_parquet_table_handler_impl", return_value=mock_handler),
            patch.object(orch, "get_deleted_rows_table_path_impl", return_value="/path/del.parquet"),
        ):
            # Must not propagate the exception
            orch._check_and_upload_deleted_rows()


# ---------------------------------------------------------------------------
# _mark_pending_batches_as_skipped
# ---------------------------------------------------------------------------


class TestMarkPendingBatchesAsSkipped:
    """_mark_pending_batches_as_skipped delegates to job_stats_service and is a
    no-op when the service or job_run_id is absent."""

    def test_no_op_when_job_stats_service_is_none(self):
        orch = _make_orchestrator()
        orch.job_stats_service = None
        # Must not raise
        orch._mark_pending_batches_as_skipped()

    def test_no_op_when_job_run_id_is_none(self):
        orch = _make_orchestrator()
        orch.job_run_id = None
        orch.job_stats_service = MagicMock()

        orch._mark_pending_batches_as_skipped()

        orch.job_stats_service.mark_pending_batches_as_skipped.assert_not_called()

    def test_delegates_to_job_stats_service(self):
        orch = _make_orchestrator()
        mock_svc = MagicMock()
        orch.job_stats_service = mock_svc

        orch._mark_pending_batches_as_skipped()

        mock_svc.mark_pending_batches_as_skipped.assert_called_once_with(
            job_run_id=JOB_RUN_ID,
            reason="Skipped - flow failed in fail-fast mode before batch execution",
        )

    def test_exception_from_service_is_swallowed(self):
        """Errors from the stats service must be logged as warnings, not raised."""
        orch = _make_orchestrator()
        mock_svc = MagicMock()
        mock_svc.mark_pending_batches_as_skipped.side_effect = RuntimeError("db timeout")
        orch.job_stats_service = mock_svc

        # Must not propagate
        orch._mark_pending_batches_as_skipped()


# ---------------------------------------------------------------------------
# _handle_skipped_execution
# ---------------------------------------------------------------------------


class TestHandleSkippedExecution:
    """_handle_skipped_execution passes tables from prev_results through to
    new data accesses without executing the operator, and notifies the
    event handler via after_node_skipped."""

    def _make_prev_results(self, num_rows: int = 2) -> ExecuteStepResults:
        table = pa.table({"id": ["doc1", "doc2"][:num_rows], "content": ["a", "b"][:num_rows]})
        return ExecuteStepResults(data_accesses=[MagicMock()], tables=[table], internal_metadata={})

    def _make_executor(self, tables: list[pa.Table]) -> MagicMock:
        executor = MagicMock()
        executor.create_data_accesses.return_value = [MagicMock() for _ in tables]
        return executor

    def test_returns_data_accesses_and_tables(self):
        orch = _make_orchestrator()
        prev = self._make_prev_results()
        executor = self._make_executor(prev.tables)

        data_accesses, tables = orch._handle_skipped_execution(
            op_def=_OP_DEF,
            executor=executor,
            prev_results=prev,
            global_config={},
            start="2025-01-01T00:00:00",
        )

        assert len(tables) == 1
        assert tables[0].num_rows == 2
        assert len(data_accesses) == 1

    def test_tables_come_from_prev_results(self):
        orch = _make_orchestrator()
        prev_table = pa.table({"id": ["x", "y", "z"]})
        prev = ExecuteStepResults(data_accesses=[MagicMock()], tables=[prev_table], internal_metadata={})
        executor = self._make_executor([prev_table])

        _, tables = orch._handle_skipped_execution(
            op_def=_OP_DEF, executor=executor, prev_results=prev, global_config={}, start="t0"
        )

        assert tables[0].num_rows == 3

    def test_calls_after_node_skipped_on_event_handler(self):
        orch = _make_orchestrator()
        prev = self._make_prev_results()
        executor = self._make_executor(prev.tables)
        global_config = {"doc_column": "content"}

        orch._handle_skipped_execution(
            op_def=_OP_DEF,
            executor=executor,
            prev_results=prev,
            global_config=global_config,
            start="2025-01-01T00:00:00",
        )

        orch.flow_execution_event_handler.after_node_skipped.assert_called_once()
        kwargs = orch.flow_execution_event_handler.after_node_skipped.call_args.kwargs
        assert kwargs["node_id"] == _OP_DEF[OperatorConstants.Columns.ID]
        assert kwargs["node_name"] == _OP_DEF[OperatorConstants.Columns.NAME]
        assert kwargs["operator_type"] == _OP_DEF[OperatorConstants.Misc.OPERATOR]
        assert kwargs["global_config"] is global_config

    def test_column_names_populated_from_single_prev_table(self):
        """When prev_results is a single ExecuteStepResults with one table,
        column_names should reflect that table's columns."""
        orch = _make_orchestrator()
        prev = self._make_prev_results()
        executor = self._make_executor(prev.tables)

        orch._handle_skipped_execution(
            op_def=_OP_DEF, executor=executor, prev_results=prev, global_config={}, start="t0"
        )

        kwargs = orch.flow_execution_event_handler.after_node_skipped.call_args.kwargs
        assert kwargs["column_names"] == ["id", "content"]

    def test_column_names_empty_for_dict_prev_results(self):
        """When prev_results is a dict (multi-input node), column_names should be []."""
        orch = _make_orchestrator()
        table = pa.table({"id": ["a"]})
        prev_dict = {
            "branch_a": ExecuteStepResults(data_accesses=[MagicMock()], tables=[table], internal_metadata={}),
            "branch_b": ExecuteStepResults(data_accesses=[MagicMock()], tables=[table], internal_metadata={}),
        }
        executor = MagicMock()
        executor.create_data_accesses.return_value = [MagicMock(), MagicMock()]

        orch._handle_skipped_execution(
            op_def=_OP_DEF, executor=executor, prev_results=prev_dict, global_config={}, start="t0"
        )

        kwargs = orch.flow_execution_event_handler.after_node_skipped.call_args.kwargs
        assert kwargs["column_names"] == []

    def test_create_data_accesses_called_with_tables(self):
        """executor.create_data_accesses must receive the tables extracted from prev_results."""
        orch = _make_orchestrator()
        prev = self._make_prev_results()
        executor = self._make_executor(prev.tables)

        orch._handle_skipped_execution(
            op_def=_OP_DEF, executor=executor, prev_results=prev, global_config={}, start="t0"
        )

        executor.create_data_accesses.assert_called_once_with(prev.tables)


# ---------------------------------------------------------------------------
# evaluate_execution_skip
# ---------------------------------------------------------------------------


class TestEvaluateExecutionSkip:
    """evaluate_execution_skip returns True when a non-Ingest operator receives
    an empty (or absent) table, and False otherwise.  VectorDB operators with
    deleted docs are the one exception that must always run."""

    def _make_executor(self, category: OperatorCategory) -> MagicMock:
        executor = MagicMock()
        executor.get_operator.return_value.category = category
        return executor

    # --- Ingest operators are never skipped ---

    def test_ingest_operator_never_skipped_with_empty_table(self):
        orch = _make_orchestrator()
        executor = self._make_executor(OperatorCategory.Ingest)
        empty_table = pa.table({"id": pa.array([], type=pa.string())})

        assert orch.evaluate_execution_skip(executor=executor, tables=empty_table, deleted_docs_count=0) is False

    def test_ingest_operator_never_skipped_with_none_table(self):
        orch = _make_orchestrator()
        executor = self._make_executor(OperatorCategory.Ingest)

        assert orch.evaluate_execution_skip(executor=executor, tables=None, deleted_docs_count=0) is False

    # --- Non-Ingest operators are skipped when all tables are empty ---

    def test_non_ingest_skipped_with_empty_table(self):
        orch = _make_orchestrator()
        executor = self._make_executor(OperatorCategory.Quality)
        empty_table = pa.table({"id": pa.array([], type=pa.string())})

        assert orch.evaluate_execution_skip(executor=executor, tables=empty_table, deleted_docs_count=0) is True

    def test_non_ingest_skipped_with_none_tables(self):
        orch = _make_orchestrator()
        executor = self._make_executor(OperatorCategory.Functional)

        assert orch.evaluate_execution_skip(executor=executor, tables=None, deleted_docs_count=0) is True

    def test_non_ingest_skipped_when_all_tables_in_list_are_empty(self):
        orch = _make_orchestrator()
        executor = self._make_executor(OperatorCategory.Quality)
        tables = [
            pa.table({"id": pa.array([], type=pa.string())}),
            pa.table({"id": pa.array([], type=pa.string())}),
        ]

        assert orch.evaluate_execution_skip(executor=executor, tables=tables, deleted_docs_count=0) is True

    def test_non_ingest_not_skipped_when_any_table_has_rows(self):
        orch = _make_orchestrator()
        executor = self._make_executor(OperatorCategory.Quality)
        tables = [
            pa.table({"id": pa.array([], type=pa.string())}),
            pa.table({"id": ["doc1"]}),
        ]

        assert orch.evaluate_execution_skip(executor=executor, tables=tables, deleted_docs_count=0) is False

    def test_non_ingest_not_skipped_when_table_has_rows(self):
        orch = _make_orchestrator()
        executor = self._make_executor(OperatorCategory.Functional)
        table = pa.table({"id": ["doc1", "doc2"]})

        assert orch.evaluate_execution_skip(executor=executor, tables=table, deleted_docs_count=0) is False

    # --- VectorDB special case ---

    def test_vectordb_not_skipped_when_deleted_docs_exist_even_if_table_empty(self):
        """VectorDB operator must run when docs were deleted, so it can clean the index."""
        orch = _make_orchestrator()
        executor = self._make_executor(OperatorCategory.VectorDB)
        empty_table = pa.table({"id": pa.array([], type=pa.string())})

        assert orch.evaluate_execution_skip(executor=executor, tables=empty_table, deleted_docs_count=5) is False

    def test_vectordb_skipped_when_no_deleted_docs_and_table_empty(self):
        orch = _make_orchestrator()
        executor = self._make_executor(OperatorCategory.VectorDB)
        empty_table = pa.table({"id": pa.array([], type=pa.string())})

        assert orch.evaluate_execution_skip(executor=executor, tables=empty_table, deleted_docs_count=0) is True


# ---------------------------------------------------------------------------
# _collect_non_recoverable_docs
# ---------------------------------------------------------------------------


class TestCollectNonRecoverableDocs:
    """_collect_non_recoverable_docs appends non-empty non-recoverable tables
    from internal_metadata to self.non_recoverable_docs_tables."""

    def test_appends_table_when_present_and_non_empty(self):
        orch = _make_orchestrator()
        table = pa.table({"id": ["doc1", "doc2"]})
        internal_metadata = {Metrics.Internal.NON_RECOVERABLE_DOCS_TABLE: table}

        orch._collect_non_recoverable_docs(
            internal_metadata=internal_metadata,
            op_def=_OP_DEF,
            common_log_arguments={},
        )

        assert len(orch.non_recoverable_docs_tables) == 1
        assert orch.non_recoverable_docs_tables[0].num_rows == 2

    def test_does_not_append_when_table_is_empty(self):
        orch = _make_orchestrator()
        empty_table = pa.table({"id": pa.array([], type=pa.string())})
        internal_metadata = {Metrics.Internal.NON_RECOVERABLE_DOCS_TABLE: empty_table}

        orch._collect_non_recoverable_docs(
            internal_metadata=internal_metadata,
            op_def=_OP_DEF,
            common_log_arguments={},
        )

        assert len(orch.non_recoverable_docs_tables) == 0

    def test_does_not_append_when_key_absent(self):
        orch = _make_orchestrator()

        orch._collect_non_recoverable_docs(
            internal_metadata={},
            op_def=_OP_DEF,
            common_log_arguments={},
        )

        assert len(orch.non_recoverable_docs_tables) == 0

    def test_does_not_append_when_internal_metadata_is_none(self):
        orch = _make_orchestrator()

        orch._collect_non_recoverable_docs(
            internal_metadata=None,
            op_def=_OP_DEF,
            common_log_arguments={},
        )

        assert len(orch.non_recoverable_docs_tables) == 0

    def test_does_not_append_when_table_value_is_none(self):
        orch = _make_orchestrator()
        internal_metadata = {Metrics.Internal.NON_RECOVERABLE_DOCS_TABLE: None}

        orch._collect_non_recoverable_docs(
            internal_metadata=internal_metadata,
            op_def=_OP_DEF,
            common_log_arguments={},
        )

        assert len(orch.non_recoverable_docs_tables) == 0

    def test_does_not_append_when_value_is_not_a_table(self):
        orch = _make_orchestrator()
        internal_metadata = {Metrics.Internal.NON_RECOVERABLE_DOCS_TABLE: {"not": "a table"}}

        orch._collect_non_recoverable_docs(
            internal_metadata=internal_metadata,
            op_def=_OP_DEF,
            common_log_arguments={},
        )

        assert len(orch.non_recoverable_docs_tables) == 0

    def test_accumulates_across_multiple_calls(self):
        orch = _make_orchestrator()
        table_a = pa.table({"id": ["a"]})
        table_b = pa.table({"id": ["b", "c"]})

        orch._collect_non_recoverable_docs(
            internal_metadata={Metrics.Internal.NON_RECOVERABLE_DOCS_TABLE: table_a},
            op_def=_OP_DEF,
            common_log_arguments={},
        )
        orch._collect_non_recoverable_docs(
            internal_metadata={Metrics.Internal.NON_RECOVERABLE_DOCS_TABLE: table_b},
            op_def=_OP_DEF,
            common_log_arguments={},
        )

        assert len(orch.non_recoverable_docs_tables) == 2
        total_rows = sum(t.num_rows for t in orch.non_recoverable_docs_tables)
        assert total_rows == 3


# ---------------------------------------------------------------------------
# _merge_non_recoverable_docs
# ---------------------------------------------------------------------------


class TestMergeNonRecoverableDocs:
    """_merge_non_recoverable_docs concatenates accumulated tables into one,
    returning None when no tables have been collected."""

    def test_returns_none_when_no_tables_collected(self):
        orch = _make_orchestrator()

        result = orch._merge_non_recoverable_docs(global_config={}, common_log_arguments={})

        assert result is None

    def test_returns_single_table_unchanged(self):
        orch = _make_orchestrator()
        table = pa.table({"id": ["doc1", "doc2"]})
        orch.non_recoverable_docs_tables.append(table)

        result = orch._merge_non_recoverable_docs(global_config={}, common_log_arguments={})

        assert result is not None
        assert result.num_rows == 2

    def test_merges_multiple_tables_into_one(self):
        orch = _make_orchestrator()
        orch.non_recoverable_docs_tables.append(pa.table({"id": ["a"]}))
        orch.non_recoverable_docs_tables.append(pa.table({"id": ["b", "c"]}))
        orch.non_recoverable_docs_tables.append(pa.table({"id": ["d"]}))

        result = orch._merge_non_recoverable_docs(global_config={}, common_log_arguments={})

        assert result is not None
        assert result.num_rows == 4

    def test_merged_table_preserves_all_columns(self):
        orch = _make_orchestrator()
        orch.non_recoverable_docs_tables.append(pa.table({"id": ["a"], "reason": ["parse error"]}))
        orch.non_recoverable_docs_tables.append(pa.table({"id": ["b"], "reason": ["timeout"]}))

        result = orch._merge_non_recoverable_docs(global_config={}, common_log_arguments={})

        assert result is not None
        assert "id" in result.column_names
        assert "reason" in result.column_names

    def test_logs_batch_num_when_present_in_global_config(self):
        """When BATCH_NUM is in global_config the info log should mention it.
        This is a smoke test — we just verify no exception is raised."""
        orch = _make_orchestrator()
        orch.non_recoverable_docs_tables.append(pa.table({"id": ["x"]}))
        global_config = {DocpipeConstants.BATCH_NUM: 3}

        result = orch._merge_non_recoverable_docs(global_config=global_config, common_log_arguments={})

        assert result is not None

    def test_returns_none_and_does_not_raise_on_concat_error(self):
        """If pa.concat_tables fails (e.g. incompatible schemas), returns None
        and swallows the exception."""
        orch = _make_orchestrator()
        # Two tables with incompatible schemas
        orch.non_recoverable_docs_tables.append(pa.table({"id": ["a"]}))
        orch.non_recoverable_docs_tables.append(pa.table({"different_col": [1]}))

        result = orch._merge_non_recoverable_docs(global_config={}, common_log_arguments={})

        assert result is None


# ---------------------------------------------------------------------------
# _reset_non_recoverable_docs_for_batch
# ---------------------------------------------------------------------------


class TestResetNonRecoverableDocsForBatch:
    """_reset_non_recoverable_docs_for_batch clears the accumulated list when
    BATCH_NUM is present in global_config, and is a no-op otherwise."""

    def test_clears_list_when_batch_num_is_set(self):
        orch = _make_orchestrator()
        orch.non_recoverable_docs_tables.append(pa.table({"id": ["a"]}))
        orch.non_recoverable_docs_tables.append(pa.table({"id": ["b"]}))

        orch._reset_non_recoverable_docs_for_batch(
            global_config={DocpipeConstants.BATCH_NUM: 1}, common_log_arguments={}
        )

        assert orch.non_recoverable_docs_tables == []

    def test_does_not_clear_when_batch_num_is_absent(self):
        orch = _make_orchestrator()
        table = pa.table({"id": ["a"]})
        orch.non_recoverable_docs_tables.append(table)

        orch._reset_non_recoverable_docs_for_batch(global_config={}, common_log_arguments={})

        assert len(orch.non_recoverable_docs_tables) == 1

    def test_does_not_clear_when_batch_num_is_none(self):
        orch = _make_orchestrator()
        table = pa.table({"id": ["a"]})
        orch.non_recoverable_docs_tables.append(table)

        orch._reset_non_recoverable_docs_for_batch(
            global_config={DocpipeConstants.BATCH_NUM: None}, common_log_arguments={}
        )

        assert len(orch.non_recoverable_docs_tables) == 1

    def test_no_op_on_already_empty_list_with_batch_num(self):
        orch = _make_orchestrator()

        # Must not raise even if the list is already empty
        orch._reset_non_recoverable_docs_for_batch(
            global_config={DocpipeConstants.BATCH_NUM: 2}, common_log_arguments={}
        )

        assert orch.non_recoverable_docs_tables == []
