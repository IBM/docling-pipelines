"""Unit tests for incremental metadata store injection in the orchestrator."""

from unittest.mock import MagicMock, patch

import pyarrow as pa

from docpipe.core.constants.constants import DocpipeConstants, Metrics
from docpipe.core.orchestration.python.python_orchestrator import PythonOrchestrator


class TestIncrementalStoreInjection:
    """Tests that verify injected IncrementalMetadataStore is used correctly."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_empty_step_result():
        from docpipe.core.orchestration.ports.flow_engine import ExecuteStepResults

        return ExecuteStepResults(
            tables=[pa.table({"id": pa.array([], type=pa.string()), "content": pa.array([], type=pa.string())})],
            data_accesses=[MagicMock()],
            internal_metadata={Metrics.Internal.ALL_DOC_IDS: []},
        )

    # ------------------------------------------------------------------
    # Test: force_ingest=True passes injected store to IncrementalUpdateService
    # ------------------------------------------------------------------

    def test_force_ingest_calls_clear_on_injected_store(self):
        """
        When force_ingest=True, the injected IncrementalMetadataStore must be
        passed to IncrementalUpdateService.  The test mocks the service to
        avoid coupling to its internal implementation details.
        """
        mock_store = MagicMock()
        orchestrator = PythonOrchestrator(incremental_metadata_store=mock_store)
        orchestrator.job_id = "job-123"
        orchestrator.job_run_id = "run-456"
        orchestrator.context_id = "job-123"
        orchestrator.common_log_arguments = {}

        # op_flow must have at least one element — execute_flow reads op_flow[0]
        op_flow = [MagicMock()]
        params = {
            DocpipeConstants.JOB_ID: "job-123",
            DocpipeConstants.JOB_RUN_ID: "run-456",
            DocpipeConstants.FORCE_INGEST: True,
        }

        step_result = self._make_empty_step_result()
        mock_incremental_service = MagicMock()

        with (
            patch.object(orchestrator, "_execute_step", return_value=step_result),
            patch.object(orchestrator, "_populate_ingest_source_config"),
            patch.object(orchestrator, "_get_ingest_summary_message", return_value=""),
            patch.object(orchestrator, "_finalize_dag_flow"),
            patch("docpipe.core.orchestration.abstract_orchestrator.clean_up_prefect_home"),
            patch(
                "docpipe.core.orchestration.abstract_orchestrator.IncrementalUpdateService",
                return_value=mock_incremental_service,
            ) as mock_service_cls,
        ):
            orchestrator.execute_flow(op_flow=op_flow, global_config=params)

        mock_service_cls.assert_called_once_with(store=mock_store)
        mock_incremental_service.process_ingested_docs.assert_called_once()

    # ------------------------------------------------------------------
    # Test: injected store is used instead of calling create_incremental_metadata_store
    # ------------------------------------------------------------------

    def test_injected_store_used_without_calling_factory(self):
        """
        When an IncrementalMetadataStore is injected, execute_flow must use it
        directly and must NOT call create_incremental_metadata_store().
        """
        mock_store = MagicMock()
        orchestrator = PythonOrchestrator(incremental_metadata_store=mock_store)
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

        with (
            patch.object(orchestrator, "_execute_step", return_value=step_result),
            patch.object(orchestrator, "_populate_ingest_source_config"),
            patch.object(orchestrator, "_get_ingest_summary_message", return_value=""),
            patch.object(orchestrator, "_finalize_dag_flow"),
            patch("docpipe.core.orchestration.abstract_orchestrator.clean_up_prefect_home"),
            patch("docpipe.core.orchestration.abstract_orchestrator.create_incremental_metadata_store") as mock_factory,
        ):
            orchestrator.execute_flow(op_flow=op_flow, global_config=params)

        mock_factory.assert_not_called()
        # The injected store must have been used — IncrementalUpdateService
        # queries it via process_ingested_docs, which ultimately calls
        # store.get_doc_ids / store.clear / store.mark_deleted depending on config.
        # The minimum assertion is that the factory was bypassed entirely.
        assert orchestrator.incremental_metadata_store is mock_store
