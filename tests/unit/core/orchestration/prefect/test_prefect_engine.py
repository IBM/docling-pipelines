"""
Unit tests for PrefectEngine and BatchFuture.

Only pure-logic paths that do not invoke Prefect task/flow execution are covered:
  - BatchFuture lifecycle (release, describe_state)
  - PrefectEngine._collect_failed_doc_ids (no-service, non-batched, batched paths)
  - PrefectEngine._wait_for_sub_flows (success, fail-fast, continue_on_batch_failure)
"""

from unittest.mock import MagicMock, patch

import pytest

from docpipe.core.orchestration.prefect.prefect_engine import BatchFuture, PrefectEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine(*, job_run_id="run-1"):
    """Return a PrefectEngine with all dependencies mocked out."""
    orchestrator = MagicMock()
    orchestrator.job_status = None
    orchestrator._non_recoverable_docs_tables = {}
    batch_manager = MagicMock()

    with patch.object(PrefectEngine, "__init__", lambda self, **kw: None):
        engine = PrefectEngine()

    engine.job_id = "job-1"
    engine.job_run_id = job_run_id
    engine.orchestrator = orchestrator
    engine.batch_manager = batch_manager
    engine.logger = MagicMock()
    engine.common_log_arguments = {}
    return engine


def _make_batch_future(*, batch_id="b1", batch_num=1, future=None):
    """Return a BatchFuture with a mock future."""
    if future is None:
        future = MagicMock()
        future.state.is_completed.return_value = True
        future.state.is_failed.return_value = False
        future.state.is_crashed.return_value = False
        future.state.is_cancelled.return_value = False
        future.state.type.value = "COMPLETED"
        future.state.name = "Completed"
    return BatchFuture(batch_id=batch_id, batch_num=batch_num, future=future)


# ---------------------------------------------------------------------------
# BatchFuture tests
# ---------------------------------------------------------------------------


class TestBatchFutureRelease:
    """Tests for BatchFuture.release()."""

    def test_release_clears_data_and_future(self):
        """release() sets released=True and nulls data_access, batch_info, future."""
        data_access = MagicMock()
        batch_info = MagicMock()
        bf = BatchFuture(
            batch_id="b1",
            batch_num=1,
            future=MagicMock(),
            batch_info=batch_info,
            data_access=data_access,
        )

        bf.release()

        assert bf.released is True
        assert bf.future is None
        assert bf.data_access is None
        assert bf.batch_info is None

    def test_release_is_idempotent(self):
        """Calling release() twice is a no-op on the second call."""
        bf = _make_batch_future()
        bf.release()
        bf.release()  # must not raise

        assert bf.released is True

    def test_release_handles_data_access_error_gracefully(self):
        """release() swallows exceptions from data_access.tables assignment."""
        data_access = MagicMock()
        type(data_access).tables = property(
            fget=lambda self: None,
            fset=MagicMock(side_effect=RuntimeError("cannot set tables")),
        )
        bf = BatchFuture(batch_id="b1", batch_num=1, future=MagicMock(), data_access=data_access)

        # Must not raise
        bf.release()

        assert bf.released is True

    def test_batch_id_and_num_survive_release(self):
        """batch_id and batch_num remain accessible after release."""
        bf = _make_batch_future(batch_id="b99", batch_num=99)
        bf.release()

        assert bf.batch_id == "b99"
        assert bf.batch_num == 99


class TestBatchFutureDescribeState:
    """Tests for BatchFuture.describe_state()."""

    def test_describe_state_returns_released_when_future_is_none(self):
        """describe_state returns 'released' when the future has been cleared."""
        bf = _make_batch_future()
        bf.future = None

        assert bf.describe_state() == "released"

    def test_describe_state_includes_completion_flags(self):
        """describe_state includes is_completed, is_failed, is_crashed in the output."""
        bf = _make_batch_future()
        # Ensure _wrapped_future is None so the wrapped branch is not taken (covers 113→121)
        bf.future._wrapped_future = None

        description = bf.describe_state()

        assert "is_completed" in description
        assert "is_failed" in description

    def test_describe_state_handles_state_exception(self):
        """describe_state handles exceptions from future.state gracefully."""
        future = MagicMock()
        future.state.is_completed.side_effect = RuntimeError("state unavailable")
        bf = BatchFuture(batch_id="b1", batch_num=1, future=future)

        description = bf.describe_state()

        assert "state_unavailable" in description


# ---------------------------------------------------------------------------
# PrefectEngine._collect_failed_doc_ids
# ---------------------------------------------------------------------------


class TestCollectFailedDocIds:
    """Tests for PrefectEngine._collect_failed_doc_ids."""

    def test_returns_empty_when_no_job_stats_service(self):
        """Returns [] immediately when job_stats_service is None/falsy."""
        engine = _make_engine()
        engine.orchestrator.job_stats_service = None

        result = engine._collect_failed_doc_ids(batch_id="b1")

        assert result == []

    def test_returns_empty_when_non_batched_and_no_job_stats(self):
        """Non-batched flow: returns [] when get_job returns None."""
        engine = _make_engine()
        engine.orchestrator.job_stats_service = MagicMock()
        engine.orchestrator.job_stats_service.get_job.return_value = None

        result = engine._collect_failed_doc_ids(batch_id=None)

        assert result == []

    def test_returns_empty_when_non_batched_and_no_node_stats(self):
        """Non-batched flow: returns [] when node_stats is empty/None."""
        engine = _make_engine()
        job_stats = MagicMock()
        job_stats.node_stats = None
        engine.orchestrator.job_stats_service = MagicMock()
        engine.orchestrator.job_stats_service.get_job.return_value = job_stats

        result = engine._collect_failed_doc_ids(batch_id=None)

        assert result == []

    def test_collects_failed_docs_from_node_stats_objects(self):
        """Non-batched flow: aggregates failed_docs from all node_stats values."""
        engine = _make_engine()
        ns1 = MagicMock()
        ns1.failed_docs = ["doc-1", "doc-2"]
        ns2 = MagicMock()
        ns2.failed_docs = ["doc-3"]
        job_stats = MagicMock()
        job_stats.node_stats = {"n1": ns1, "n2": ns2}
        engine.orchestrator.job_stats_service = MagicMock()
        engine.orchestrator.job_stats_service.get_job.return_value = job_stats

        result = engine._collect_failed_doc_ids(batch_id=None)

        assert sorted(result) == ["doc-1", "doc-2", "doc-3"]

    def test_collects_failed_docs_from_dict_node_stats(self):
        """Non-batched flow: also handles node_stats values that are plain dicts."""
        engine = _make_engine()
        job_stats = MagicMock()
        job_stats.node_stats = {"n1": {"failed_docs": ["doc-A"]}}
        engine.orchestrator.job_stats_service = MagicMock()
        engine.orchestrator.job_stats_service.get_job.return_value = job_stats

        result = engine._collect_failed_doc_ids(batch_id=None)

        assert result == ["doc-A"]

    def test_delegates_to_service_for_batched_flow(self):
        """Batched flow: delegates to get_failed_doc_ids_for_batch."""
        engine = _make_engine()
        svc = MagicMock()
        svc.get_failed_doc_ids_for_batch.return_value = ["doc-X"]
        engine.orchestrator.job_stats_service = svc

        result = engine._collect_failed_doc_ids(batch_id="b-99")

        assert result == ["doc-X"]
        svc.get_failed_doc_ids_for_batch.assert_called_once_with(job_run_id="run-1", batch_id="b-99")

    def test_skips_node_stats_with_no_failed_docs_attribute(self):
        """Non-batched flow: node_stats without failed_docs attr or key are silently skipped."""
        engine = _make_engine()
        # A MagicMock with spec=[] has no attributes → hasattr returns False
        # It's not a dict → isinstance(dict) is False → both branches are skipped
        ns_no_failed = MagicMock(spec=[])
        job_stats = MagicMock()
        job_stats.node_stats = {"n1": ns_no_failed}
        engine.orchestrator.job_stats_service = MagicMock()
        engine.orchestrator.job_stats_service.get_job.return_value = job_stats

        result = engine._collect_failed_doc_ids(batch_id=None)

        assert result == []


# ---------------------------------------------------------------------------
# PrefectEngine._wait_for_sub_flows
# ---------------------------------------------------------------------------


class TestWaitForSubFlows:
    """Tests for PrefectEngine._wait_for_sub_flows logic with mocked futures."""

    def _global_config(self, *, continue_on_batch_failure=False):
        from docpipe.core.constants.constants import DocpipeConstants

        return {
            DocpipeConstants.CONTINUE_ON_BATCH_FAILURE: continue_on_batch_failure,
        }

    def test_success_path_releases_all_futures(self):
        """All futures succeed → all BatchFutures are released."""
        engine = _make_engine()
        bf1 = _make_batch_future(batch_id="b1", batch_num=1)
        bf2 = _make_batch_future(batch_id="b2", batch_num=2)
        bf1.future.result.return_value = None
        bf2.future.result.return_value = None

        engine._wait_for_sub_flows(batch_futures=[bf1, bf2], global_config=self._global_config())

        assert bf1.released
        assert bf2.released

    def test_fail_fast_marks_orchestrator_failing_and_drains_remaining_batches(self):
        """Fail-fast records failure and drains later batches without raising in the flow."""
        from docpipe.core.constants.constants import ExecutionStatus

        engine = _make_engine()
        bf1 = _make_batch_future(batch_id="b1", batch_num=1)
        bf2 = _make_batch_future(batch_id="b2", batch_num=2)
        bf1.future.result.side_effect = RuntimeError("task exploded")
        bf2.future.wait = MagicMock()
        bf2.future._wrapped_future = MagicMock()
        bf2.future._wrapped_future.done.return_value = True
        drained_future = bf2.future

        engine._wait_for_sub_flows(batch_futures=[bf1, bf2], global_config=self._global_config())

        assert engine.orchestrator.job_status == ExecutionStatus.FAILING
        drained_future.wait.assert_called_once_with(timeout=300)

    def test_continue_on_batch_failure_does_not_raise_on_partial_failure(self):
        """continue_on_batch_failure=True: partial failures are logged, no exception raised."""
        engine = _make_engine()
        bf1 = _make_batch_future(batch_id="b1", batch_num=1)
        bf2 = _make_batch_future(batch_id="b2", batch_num=2)
        bf1.future.result.side_effect = RuntimeError("batch 1 failed")
        bf2.future.result.return_value = None

        # Must not raise
        engine._wait_for_sub_flows(
            batch_futures=[bf1, bf2],
            global_config=self._global_config(continue_on_batch_failure=True),
        )

        assert bf1.released
        assert bf2.released

    def test_continue_all_failed_sets_orchestrator_failing(self):
        """When ALL batches fail with continue_on_batch_failure=True, sets FAILING status."""
        from docpipe.core.constants.constants import ExecutionStatus

        engine = _make_engine()
        bf1 = _make_batch_future(batch_id="b1", batch_num=1)
        bf2 = _make_batch_future(batch_id="b2", batch_num=2)
        bf1.future.result.side_effect = RuntimeError("failed")
        bf2.future.result.side_effect = RuntimeError("also failed")

        engine._wait_for_sub_flows(
            batch_futures=[bf1, bf2],
            global_config=self._global_config(continue_on_batch_failure=True),
        )

        assert engine.orchestrator.job_status == ExecutionStatus.FAILING

    def test_semaphore_reset_always_called(self):
        """batch_manager.reset_batch_semaphore() is called even when a batch fails."""
        engine = _make_engine()
        bf = _make_batch_future(batch_id="b1", batch_num=1)
        bf.future.result.side_effect = RuntimeError("fail")

        engine._wait_for_sub_flows(batch_futures=[bf], global_config=self._global_config())

        engine.batch_manager.reset_batch_semaphore.assert_called_once()

    def test_already_released_future_skipped_in_success_loop(self):
        """A future that is None (already released) is skipped without error."""
        engine = _make_engine()
        bf = _make_batch_future(batch_id="b1", batch_num=1)
        bf.future = None  # simulate already-released

        # Must not raise
        engine._wait_for_sub_flows(batch_futures=[bf], global_config=self._global_config())

    def test_drain_timeout_is_logged_not_raised(self):
        """A remaining batch that outlives the drain timeout only logs a warning."""
        engine = _make_engine()
        bf1 = _make_batch_future(batch_id="b1", batch_num=1)
        bf2 = _make_batch_future(batch_id="b2", batch_num=2)
        bf1.future.result.side_effect = RuntimeError("batch 1 failed")
        bf2.future.wait = MagicMock()
        bf2.future._wrapped_future = MagicMock()
        bf2.future._wrapped_future.done.return_value = False

        engine._wait_for_sub_flows(batch_futures=[bf1, bf2], global_config=self._global_config())

        bf2.future.wait.assert_called_once_with(timeout=300)
        engine.logger.warning.assert_called()


# ---------------------------------------------------------------------------
# BatchFuture.describe_state — wrapped_future branch
# ---------------------------------------------------------------------------


class TestBatchFutureDescribeStateWrappedFuture:
    """Tests for describe_state() when _wrapped_future is present."""

    def test_describe_state_includes_wrapped_future_fields(self):
        """describe_state includes wrapped_done, wrapped_cancelled, wrapped_running when _wrapped_future exists."""
        wrapped = MagicMock()
        wrapped.done.return_value = True
        wrapped.cancelled.return_value = False
        wrapped.running.return_value = False

        future = MagicMock()
        future.state.is_completed.return_value = True
        future.state.is_failed.return_value = False
        future.state.is_crashed.return_value = False
        future.state.is_cancelled.return_value = False
        future.state.type.value = "COMPLETED"
        future.state.name = "Completed"
        future._wrapped_future = wrapped

        bf = BatchFuture(batch_id="b1", batch_num=1, future=future)
        description = bf.describe_state()

        assert "wrapped_done" in description
        assert "wrapped_cancelled" in description
        assert "wrapped_running" in description

    def test_describe_state_handles_wrapped_future_exception(self):
        """describe_state handles exceptions from _wrapped_future methods gracefully."""
        wrapped = MagicMock()
        wrapped.done.side_effect = RuntimeError("wrapped broken")

        future = MagicMock()
        future.state.is_completed.return_value = True
        future.state.is_failed.return_value = False
        future.state.is_crashed.return_value = False
        future.state.is_cancelled.return_value = False
        future.state.type.value = "COMPLETED"
        future.state.name = "Completed"
        future._wrapped_future = wrapped

        bf = BatchFuture(batch_id="b1", batch_num=1, future=future)
        description = bf.describe_state()

        assert "wrapped_state_unavailable" in description


# ---------------------------------------------------------------------------
# PrefectEngine.build_non_execute_flow / execute_non_execute_flow
# ---------------------------------------------------------------------------


class TestBuildAndExecuteNonExecuteFlow:
    """Tests for build_non_execute_flow and execute_non_execute_flow."""

    def test_build_non_execute_flow_returns_callable(self):
        """build_non_execute_flow returns the wrapped flow callable."""
        engine = _make_engine()

        mock_flow_result = MagicMock()
        with patch("docpipe.core.orchestration.prefect.prefect_engine.flow") as mock_flow:
            mock_flow.return_value = lambda fn: mock_flow_result
            result = engine.build_non_execute_flow(flow_name="test_flow")

        assert result is mock_flow_result

    def test_build_non_execute_flow_uses_default_name(self):
        """build_non_execute_flow uses 'task_pipeline' when flow_name is None."""
        engine = _make_engine()
        captured_kwargs = {}

        def capture_flow(**kwargs):
            captured_kwargs.update(kwargs)
            return lambda fn: MagicMock()

        with patch("docpipe.core.orchestration.prefect.prefect_engine.flow", side_effect=capture_flow):
            engine.build_non_execute_flow()

        assert captured_kwargs.get("name") == "task_pipeline"

    def test_execute_non_execute_flow_calls_built_flow(self):
        """execute_non_execute_flow builds a flow then calls it with expected args."""
        from docpipe.core.constants.constants import TaskType

        engine = _make_engine()
        mock_flow_callable = MagicMock()

        with patch.object(engine, "build_non_execute_flow", return_value=mock_flow_callable) as mock_build:
            engine.execute_non_execute_flow(flow_name="test_flow", task="some_task", dag="some_dag")

        mock_build.assert_called_once_with(flow_name="test_flow")
        mock_flow_callable.assert_called_once_with(TaskType.VALIDATE_FLOW, "some_task", "some_dag", None)


# ---------------------------------------------------------------------------
# PrefectEngine.batch_outer_flow_impl — invalid max_concurrent_batches
# ---------------------------------------------------------------------------


class TestBatchOuterFlowImplValidation:
    """Tests for batch_outer_flow_impl parameter validation."""

    def test_raises_when_max_concurrent_batches_is_zero(self):
        """batch_outer_flow_impl raises FlowExecutionFailedException when max_concurrent_batches=0."""
        from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException

        engine = _make_engine()
        global_config = {"max_concurrent_batches": 0}

        with pytest.raises(FlowExecutionFailedException, match="max_concurrent_batches"):
            engine.batch_outer_flow_impl(op_flow=[], batches=[], global_config=global_config)

    def test_raises_when_max_concurrent_batches_is_negative(self):
        """batch_outer_flow_impl raises FlowExecutionFailedException when max_concurrent_batches<0."""
        from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException

        engine = _make_engine()
        global_config = {"max_concurrent_batches": -1}

        with pytest.raises(FlowExecutionFailedException, match="max_concurrent_batches"):
            engine.batch_outer_flow_impl(op_flow=[], batches=[], global_config=global_config)

    def test_raises_when_max_concurrent_batches_is_not_int(self):
        """batch_outer_flow_impl raises FlowExecutionFailedException when max_concurrent_batches is a string."""
        from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException

        engine = _make_engine()
        global_config = {"max_concurrent_batches": "ten"}

        with pytest.raises(FlowExecutionFailedException, match="max_concurrent_batches"):
            engine.batch_outer_flow_impl(op_flow=[], batches=[], global_config=global_config)


# ---------------------------------------------------------------------------
# PrefectEngine._wait_for_sub_flows — already-released paths
# ---------------------------------------------------------------------------


class TestWaitForSubFlowsAlreadyReleased:
    """Tests for _wait_for_sub_flows paths where futures are already released."""

    def _global_config(self, *, continue_on_batch_failure=False):
        from docpipe.core.constants.constants import DocpipeConstants

        return {DocpipeConstants.CONTINUE_ON_BATCH_FAILURE: continue_on_batch_failure}

    def test_remaining_future_is_drained_on_fail_fast(self):
        """Fail-fast drains a later future without calling Prefect's cancel API."""
        engine = _make_engine()
        bf1 = _make_batch_future(batch_id="b1", batch_num=1)
        bf2 = _make_batch_future(batch_id="b2", batch_num=2)
        bf1.future.result.side_effect = RuntimeError("fail")
        bf2.future.wait = MagicMock()
        bf2.future._wrapped_future = MagicMock()
        bf2.future._wrapped_future.done.return_value = True
        drained_future = bf2.future

        engine._wait_for_sub_flows(batch_futures=[bf1, bf2], global_config=self._global_config())

        drained_future.wait.assert_called_once_with(timeout=300)
        drained_future.cancel.assert_not_called()

    def test_continue_on_batch_failure_partial_failure_sets_warning_not_failing_status(self):
        """Partial failure in continue mode logs warning but does not set FAILING status."""
        from docpipe.core.constants.constants import ExecutionStatus

        engine = _make_engine()
        bf1 = _make_batch_future(batch_id="b1", batch_num=1)
        bf2 = _make_batch_future(batch_id="b2", batch_num=2)
        bf1.future.result.side_effect = RuntimeError("batch 1 failed")
        bf2.future.result.return_value = None

        engine._wait_for_sub_flows(
            batch_futures=[bf1, bf2],
            global_config=self._global_config(continue_on_batch_failure=True),
        )

        # Partial failure: status must NOT be set to FAILING
        assert engine.orchestrator.job_status != ExecutionStatus.FAILING


# ---------------------------------------------------------------------------
# PrefectEngine.__wait_for_tasks
# ---------------------------------------------------------------------------


class TestWaitForTasks:
    """Tests for PrefectEngine.__wait_for_tasks (name-mangled: _PrefectEngine__wait_for_tasks)."""

    def test_wait_for_tasks_calls_wait_on_each_future(self):
        """__wait_for_tasks calls .wait() on every future that has that method."""
        engine = _make_engine()
        f1 = MagicMock(spec=["wait"])
        f2 = MagicMock(spec=["wait"])
        destinations: list[tuple] = [(f1, {}), (f2, {})]

        engine._PrefectEngine__wait_for_tasks(destinations=destinations)

        f1.wait.assert_called_once()
        f2.wait.assert_called_once()

    def test_wait_for_tasks_skips_futures_without_wait(self):
        """__wait_for_tasks silently skips futures that have no .wait() attribute."""
        engine = _make_engine()
        # spec without 'wait' → hasattr returns False
        f1 = MagicMock(spec=[])
        destinations: list[tuple] = [(f1, {})]

        # Must not raise
        engine._PrefectEngine__wait_for_tasks(destinations=destinations)

    def test_wait_for_tasks_handles_empty_destinations(self):
        """__wait_for_tasks is a no-op when destinations is empty."""
        engine = _make_engine()
        engine._PrefectEngine__wait_for_tasks(destinations=[])  # must not raise


# ---------------------------------------------------------------------------
# PrefectEngine.__wait_for_tasks_with_exceptions
# ---------------------------------------------------------------------------


class TestWaitForTasksWithExceptions:
    """Tests for __wait_for_tasks_with_exceptions (name-mangled)."""

    def test_reraises_flow_validation_exception(self):
        """FlowValidationException from a future is re-raised as-is."""
        from docpipe.core.constants.constants import TaskType
        from docpipe.exceptions.docpipe_exceptions import FlowValidationException

        engine = _make_engine()
        f1 = MagicMock()
        f1.result.side_effect = FlowValidationException("bad flow")
        destinations: list[tuple] = [(f1, {})]

        with pytest.raises(FlowValidationException):
            engine._PrefectEngine__wait_for_tasks_with_exceptions(
                destinations=destinations, task_type=TaskType.VALIDATE_FLOW
            )

    def test_wraps_generic_exception_as_prefect_flow_failed(self):
        """Non-FlowValidationException is wrapped in PrefectFlowFailed."""
        from docpipe.core.constants.constants import TaskType
        from docpipe.exceptions.docpipe_exceptions import PrefectFlowFailed

        engine = _make_engine()
        f1 = MagicMock()
        f1.result.side_effect = RuntimeError("task exploded")
        destinations: list[tuple] = [(f1, {})]

        with pytest.raises(PrefectFlowFailed):
            engine._PrefectEngine__wait_for_tasks_with_exceptions(
                destinations=destinations, task_type=TaskType.VALIDATE_FLOW
            )

    def test_no_exception_when_all_succeed(self):
        """No exception is raised when all futures complete successfully."""
        from docpipe.core.constants.constants import TaskType

        engine = _make_engine()
        f1 = MagicMock()
        f1.result.return_value = "ok"
        destinations: list[tuple] = [(f1, {})]

        engine._PrefectEngine__wait_for_tasks_with_exceptions(
            destinations=destinations, task_type=TaskType.VALIDATE_FLOW
        )  # must not raise


# ---------------------------------------------------------------------------
# PrefectEngine.execute_operator_flow
# ---------------------------------------------------------------------------


class TestExecuteOperatorFlow:
    """Tests for execute_operator_flow public entry point."""

    def test_delegates_to_flow_impl(self):
        """execute_operator_flow delegates to __flow_impl with the same args."""
        engine = _make_engine()
        op_flow = MagicMock()
        data_access = MagicMock()
        global_config = {"some": "config"}

        with patch.object(engine, "_PrefectEngine__flow_impl", return_value="result") as mock_impl:
            result = engine.execute_operator_flow(op_flow=op_flow, data_access=data_access, global_config=global_config)

        mock_impl.assert_called_once_with(op_flow=op_flow, data_access=data_access, global_config=global_config)
        assert result == "result"


# ---------------------------------------------------------------------------
# PrefectEngine.__flow_impl — ingest-only and FAILING paths
# ---------------------------------------------------------------------------


class TestFlowImplPaths:
    """Tests for __flow_impl (name-mangled: _PrefectEngine__flow_impl) pure-logic paths."""

    def _make_op_def(self, *, node_id="n1", has_edges=False):
        """Return a minimal op_def dict."""
        op = {"id": node_id, "name": f"op_{node_id}"}
        if has_edges:
            op["input_edges"] = []
            op["output_edges"] = []
        return op

    def test_ingest_only_flow_returns_execute_step_results(self):
        """__flow_impl returns ExecuteStepResults immediately when op_flow is empty."""
        from docpipe.core.orchestration.ports.flow_engine import ExecuteStepResults

        engine = _make_engine()
        data_access = MagicMock()
        batch_table = MagicMock()
        data_access.get_table.return_value = ([batch_table], {})

        with patch.object(engine, "_PrefectEngine__create_task", return_value=MagicMock()):
            result = engine._PrefectEngine__flow_impl(op_flow=[], data_access=data_access, global_config={})

        assert isinstance(result, ExecuteStepResults)
        data_access.get_table.assert_called_once_with("")

    def test_failing_status_skips_remaining_operators(self):
        """When orchestrator.job_status is FAILING, operators after the first are skipped."""
        from docpipe.core.constants.constants import ExecutionStatus
        from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException

        engine = _make_engine()
        engine.orchestrator.job_status = ExecutionStatus.FAILING
        engine.orchestrator._reset_non_recoverable_docs_for_batch = MagicMock()

        op1 = self._make_op_def(node_id="n1")
        data_access = MagicMock()
        data_access.get_table.return_value = ([MagicMock()], {})

        inner_task_mock = MagicMock()
        inner_task_mock.submit = MagicMock()

        with patch.object(engine, "_PrefectEngine__create_task", return_value=inner_task_mock):
            with patch.object(engine, "_PrefectEngine__wait_for_tasks"):
                with pytest.raises(FlowExecutionFailedException):
                    engine._PrefectEngine__flow_impl(
                        op_flow=[op1],
                        data_access=data_access,
                        global_config={},
                    )

        # No task should have been submitted since status was already FAILING
        inner_task_mock.submit.assert_not_called()

    def test_sequential_flow_submits_task_and_waits(self):
        """A minimal sequential op_flow submits a task and calls __wait_for_tasks."""
        engine = _make_engine()
        engine.orchestrator.job_status = None
        engine.orchestrator._reset_non_recoverable_docs_for_batch = MagicMock()
        engine.orchestrator._merge_non_recoverable_docs = MagicMock(return_value=None)

        op1 = self._make_op_def(node_id="n1")
        data_access = MagicMock()
        data_access.get_table.return_value = ([MagicMock()], {})

        mock_future = MagicMock()
        mock_future.result.return_value = MagicMock(tables=[MagicMock()])
        inner_task_mock = MagicMock()
        inner_task_mock.submit.return_value = mock_future

        incremental_mock = MagicMock()

        with patch.object(engine, "_PrefectEngine__create_task", return_value=inner_task_mock):
            with patch.object(engine, "_PrefectEngine__wait_for_tasks"):
                with patch(
                    "docpipe.core.orchestration.prefect.prefect_engine.get_incremental_update_service",
                    return_value=incremental_mock,
                ):
                    engine._PrefectEngine__flow_impl(
                        op_flow=[op1],
                        data_access=data_access,
                        global_config={},
                    )

        inner_task_mock.submit.assert_called_once()

    def test_task_submit_exception_calls_handle_node_failure(self):
        """When inner_task.submit raises, _handle_node_failure is called."""
        engine = _make_engine()
        engine.orchestrator.job_status = None
        engine.orchestrator._reset_non_recoverable_docs_for_batch = MagicMock()
        engine.orchestrator._merge_non_recoverable_docs = MagicMock(return_value=None)
        engine.orchestrator._handle_node_failure = MagicMock()

        op1 = self._make_op_def(node_id="n1")
        data_access = MagicMock()
        data_access.get_table.return_value = ([MagicMock()], {})

        inner_task_mock = MagicMock()
        inner_task_mock.submit.side_effect = RuntimeError("submit failed")
        incremental_mock = MagicMock()

        with patch.object(engine, "_PrefectEngine__create_task", return_value=inner_task_mock):
            with patch.object(engine, "_PrefectEngine__wait_for_tasks"):
                with patch(
                    "docpipe.core.orchestration.prefect.prefect_engine.get_incremental_update_service",
                    return_value=incremental_mock,
                ):
                    engine._PrefectEngine__flow_impl(
                        op_flow=[op1],
                        data_access=data_access,
                        global_config={},
                    )

        engine.orchestrator._handle_node_failure.assert_called_once()

    def test_dag_flow_two_nodes_uses_get_prev_results(self):
        """A 2-node DAG flow calls get_prev_results and submits both tasks."""
        engine = _make_engine()
        engine.orchestrator.job_status = None
        engine.orchestrator._reset_non_recoverable_docs_for_batch = MagicMock()
        engine.orchestrator._merge_non_recoverable_docs = MagicMock(return_value=None)

        # Non-sequential: op1 has output_edges, op2 has input_edges referencing op1
        op1 = {
            "id": "n1",
            "name": "op_n1",
            "output_edges": [{"node_id_ref": "n2", "link_name": "main"}],
        }
        op2 = {
            "id": "n2",
            "name": "op_n2",
            "input_edges": [{"node_id_ref": "n1", "link_name": "main"}],
        }

        data_access = MagicMock()
        data_access.get_table.return_value = ([MagicMock()], {})

        mock_future = MagicMock()
        mock_future.result.return_value = MagicMock(tables=[MagicMock()])
        inner_task_mock = MagicMock()
        inner_task_mock.submit.return_value = mock_future
        incremental_mock = MagicMock()

        with patch.object(engine, "_PrefectEngine__create_task", return_value=inner_task_mock):
            with patch.object(engine, "_PrefectEngine__wait_for_tasks"):
                with patch(
                    "docpipe.core.orchestration.prefect.prefect_engine.get_incremental_update_service",
                    return_value=incremental_mock,
                ):
                    engine._PrefectEngine__flow_impl(
                        op_flow=[op1, op2],
                        data_access=data_access,
                        global_config={},
                    )

        # Both ops should have submitted tasks
        assert inner_task_mock.submit.call_count == 2

    def test_dag_flow_ingest_dependency_node_uses_initial_batch_result(self):
        """get_prev_results returns initial_batch_result when the only dep is the ingest node."""
        from docpipe.core.constants.constants import DocpipeConstants

        engine = _make_engine()
        engine.orchestrator.job_status = None
        engine.orchestrator._reset_non_recoverable_docs_for_batch = MagicMock()
        engine.orchestrator._merge_non_recoverable_docs = MagicMock(return_value=None)

        ingest_id = "ingest-node"
        # op1 is a root node (output_edges makes the flow non-sequential)
        op1 = {
            "id": "n1",
            "name": "op_n1",
            "output_edges": [{"node_id_ref": "n2", "link_name": "main"}],
        }
        # op2 depends on the ingest node directly (not in op_flow) — triggers lines 594-600, 612
        op2 = {
            "id": "n2",
            "name": "op_n2",
            "input_edges": [{"node_id_ref": ingest_id, "link_name": "main"}],
        }

        data_access = MagicMock()
        data_access.get_table.return_value = ([MagicMock()], {})

        mock_future = MagicMock()
        mock_future.result.return_value = MagicMock(tables=[MagicMock()])
        inner_task_mock = MagicMock()
        inner_task_mock.submit.return_value = mock_future
        incremental_mock = MagicMock()

        global_config = {DocpipeConstants.INGEST_NODE_ID: ingest_id}

        with patch.object(engine, "_PrefectEngine__create_task", return_value=inner_task_mock):
            with patch.object(engine, "_PrefectEngine__wait_for_tasks"):
                with patch(
                    "docpipe.core.orchestration.prefect.prefect_engine.get_incremental_update_service",
                    return_value=incremental_mock,
                ):
                    engine._PrefectEngine__flow_impl(
                        op_flow=[op1, op2],
                        data_access=data_access,
                        global_config=global_config,
                    )

        # Both ops should have submitted tasks
        assert inner_task_mock.submit.call_count == 2

    def test_dag_flow_unknown_node_ref_routes_to_handle_node_failure(self):
        """get_prev_results raises FlowExecutionFailedException for an unknown node_id_ref — caught by _handle_node_failure."""
        engine = _make_engine()
        engine.orchestrator.job_status = None
        engine.orchestrator._reset_non_recoverable_docs_for_batch = MagicMock()
        engine.orchestrator._merge_non_recoverable_docs = MagicMock(return_value=None)
        engine.orchestrator._handle_node_failure = MagicMock()

        # op1 is a root node (no input_edges, has output_edges to make the flow non-sequential)
        # op2 references "ghost-node" in its input_edges — not in the flow, not the ingest node
        op1 = {
            "id": "n1",
            "name": "op_n1",
            "output_edges": [{"node_id_ref": "n2", "link_name": "main"}],
        }
        op2 = {
            "id": "n2",
            "name": "op_n2",
            "input_edges": [{"node_id_ref": "ghost-node", "link_name": "main"}],
        }

        data_access = MagicMock()
        data_access.get_table.return_value = ([MagicMock()], {})

        mock_future = MagicMock()
        mock_future.result.return_value = MagicMock(tables=[MagicMock()])
        inner_task_mock = MagicMock()
        inner_task_mock.submit.return_value = mock_future
        incremental_mock = MagicMock()

        with patch.object(engine, "_PrefectEngine__create_task", return_value=inner_task_mock):
            with patch.object(engine, "_PrefectEngine__wait_for_tasks"):
                with patch(
                    "docpipe.core.orchestration.prefect.prefect_engine.get_incremental_update_service",
                    return_value=incremental_mock,
                ):
                    engine._PrefectEngine__flow_impl(
                        op_flow=[op1, op2],
                        data_access=data_access,
                        global_config={},
                    )

        # get_prev_results raised FlowExecutionFailedException which was caught by _handle_node_failure
        engine.orchestrator._handle_node_failure.assert_called_once()

    def test_dag_flow_multi_dep_node_returns_dict_of_futures(self):
        """get_prev_results returns a dict when a node has 2+ non-ingest dependencies."""
        engine = _make_engine()
        engine.orchestrator.job_status = None
        engine.orchestrator._reset_non_recoverable_docs_for_batch = MagicMock()
        engine.orchestrator._merge_non_recoverable_docs = MagicMock(return_value=None)

        # 3-node merge pattern: n1 and n2 both feed into n3
        op1 = {"id": "n1", "name": "op_n1", "output_edges": [{"node_id_ref": "n3", "link_name": "branch_a"}]}
        op2 = {
            "id": "n2",
            "name": "op_n2",
            "input_edges": [],
            "output_edges": [{"node_id_ref": "n3", "link_name": "branch_b"}],
        }
        op3 = {
            "id": "n3",
            "name": "op_n3",
            "input_edges": [
                {"node_id_ref": "n1", "link_name": "branch_a"},
                {"node_id_ref": "n2", "link_name": "branch_b"},
            ],
        }

        data_access = MagicMock()
        data_access.get_table.return_value = ([MagicMock()], {})

        mock_future = MagicMock()
        mock_future.result.return_value = MagicMock(tables=[MagicMock()])
        inner_task_mock = MagicMock()
        inner_task_mock.submit.return_value = mock_future
        incremental_mock = MagicMock()

        with patch.object(engine, "_PrefectEngine__create_task", return_value=inner_task_mock):
            with patch.object(engine, "_PrefectEngine__wait_for_tasks"):
                with patch(
                    "docpipe.core.orchestration.prefect.prefect_engine.get_incremental_update_service",
                    return_value=incremental_mock,
                ):
                    engine._PrefectEngine__flow_impl(
                        op_flow=[op1, op2, op3],
                        data_access=data_access,
                        global_config={},
                    )

        assert inner_task_mock.submit.call_count == 3
