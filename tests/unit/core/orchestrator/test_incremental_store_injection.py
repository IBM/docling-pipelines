"""Unit tests for incremental metadata service usage in the orchestrator."""

from unittest.mock import MagicMock, patch

import pyarrow as pa

from docpipe.core.constants.constants import DocpipeConstants, Metrics
from docpipe.core.orchestration.python.python_orchestrator import PythonOrchestrator


class TestIncrementalServiceUsage:
    """Tests that the orchestrator calls the singleton IncrementalUpdateService."""

    @staticmethod
    def _make_empty_step_result():
        from docpipe.core.orchestration.ports.flow_engine import ExecuteStepResults

        return ExecuteStepResults(
            tables=[pa.table({"id": pa.array([], type=pa.string()), "content": pa.array([], type=pa.string())})],
            data_accesses=[MagicMock()],
            internal_metadata={Metrics.Internal.ALL_DOC_IDS: []},
        )

    def test_force_ingest_calls_process_ingested_docs(self):
        """execute_flow must call process_ingested_docs on the singleton service."""
        orchestrator = PythonOrchestrator()
        orchestrator.job_id = "job-123"
        orchestrator.job_run_id = "run-456"
        orchestrator.context_id = "job-123"
        orchestrator.common_log_arguments = {}

        op_flow = [MagicMock()]
        params = {
            DocpipeConstants.JOB_ID: "job-123",
            DocpipeConstants.JOB_RUN_ID: "run-456",
            DocpipeConstants.FORCE_INGEST: True,
        }

        step_result = self._make_empty_step_result()
        mock_service = MagicMock()

        with (
            patch.object(orchestrator, "_execute_step", return_value=step_result),
            patch.object(orchestrator, "_populate_ingest_source_config"),
            patch.object(orchestrator, "_get_ingest_summary_message", return_value=""),
            patch.object(orchestrator, "_finalize_dag_flow"),
            patch("docpipe.core.orchestration.abstract_orchestrator.clean_up_prefect_home"),
            patch(
                "docpipe.core.orchestration.abstract_orchestrator.get_incremental_update_service",
                return_value=mock_service,
            ),
        ):
            orchestrator.execute_flow(op_flow=op_flow, global_config=params)

        mock_service.process_ingested_docs.assert_called_once()

    def test_singleton_service_used_not_recreated(self):
        """execute_flow must use the singleton service, not construct a new one."""
        orchestrator = PythonOrchestrator()
        orchestrator.job_id = "job-789"
        orchestrator.job_run_id = "run-000"
        orchestrator.context_id = "job-789"
        orchestrator.common_log_arguments = {}

        op_flow = [MagicMock()]
        params = {
            DocpipeConstants.JOB_ID: "job-789",
            DocpipeConstants.JOB_RUN_ID: "run-000",
        }

        step_result = self._make_empty_step_result()
        mock_service = MagicMock()

        with (
            patch.object(orchestrator, "_execute_step", return_value=step_result),
            patch.object(orchestrator, "_populate_ingest_source_config"),
            patch.object(orchestrator, "_get_ingest_summary_message", return_value=""),
            patch.object(orchestrator, "_finalize_dag_flow"),
            patch("docpipe.core.orchestration.abstract_orchestrator.clean_up_prefect_home"),
            patch(
                "docpipe.core.orchestration.abstract_orchestrator.get_incremental_update_service",
                return_value=mock_service,
            ) as mock_get_service,
        ):
            orchestrator.execute_flow(op_flow=op_flow, global_config=params)

        # Must have called the singleton getter exactly once
        mock_get_service.assert_called_once()
        mock_service.process_ingested_docs.assert_called_once()
